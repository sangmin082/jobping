"""수집 실행 — 소스별 fetch → 신규 판정 → 헬스 기록 → 알림 대상 결정.

세 가지 방어가 이 모듈의 존재 이유다.

**시딩.** 소스를 처음 돌리면 그 소스의 공고 전부가 "신규"다. 첫 배포 때
1,108건이 한꺼번에 알림으로 나가면 그날로 앱은 삭제된다. 헬스 레코드가 없는
소스는 저장만 하고 알림 대상에서 뺀다.

**폭증 차단.** job_id 계산 방식이 바뀌거나 사이트가 개편되면 기존 공고 전부가
신규로 잡힌다. 한 소스에서 신규가 `max(30, 절반)` 을 넘으면 이번 실행은 그
소스를 알림에서 빼고 운영자에게 알린다. 진짜로 하루에 공고 50개를 올리는
회사는 없다.

**0건 판정.** 새벽·주말엔 진짜 0건이라 한 번 0건은 정상이다. 연속 3회면 알린다.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime

from .adapters import Adapter, NeedsDiscovery
from .alerts import Alerts
from .http import Client
from .models import Job
from .store import Store

log = logging.getLogger(__name__)

ZERO_STREAK_ALERT = 3
STORM_MIN = 30
STORM_RATIO = 0.5


@dataclass
class SourceResult:
    key: str
    fetched: int = 0
    new: int = 0
    duration_ms: int = 0
    error: str | None = None
    seeded: bool = False
    storm: bool = False
    skipped: bool = False   # NeedsDiscovery — 미구현이지 장애가 아니다


@dataclass
class RunReport:
    started_at: datetime
    sources: list[SourceResult] = field(default_factory=list)
    #: 알림 대상 신규 공고. 시딩/폭증 소스는 제외돼 있다.
    notify: list[Job] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(s.new for s in self.sources)

    def summary(self) -> str:
        parts = []
        for s in self.sources:
            if s.skipped:
                continue
            tag = ("ERR" if s.error else "SEED" if s.seeded else "STORM" if s.storm else "ok")
            parts.append(f"{s.key}:{s.fetched}/{s.new}{'' if tag == 'ok' else ' ' + tag}")
        return " ".join(parts)


def run(store: Store, adapters: list[Adapter], *, now: datetime, alerts: Alerts,
        timeout_s: int = 60, client: Client | None = None) -> RunReport:
    report = RunReport(started_at=now)
    client = client or Client()

    with ThreadPoolExecutor(max_workers=min(6, max(1, len(adapters)))) as pool:
        futures = {pool.submit(_fetch, a, client): a for a in adapters}
        # 소스마다 개별 타임아웃. 하나가 늘어져도 나머지는 정상 처리된다.
        deadline = time.monotonic() + timeout_s
        for future, adapter in futures.items():
            result = SourceResult(key=adapter.key)
            started = time.monotonic()
            try:
                jobs = future.result(timeout=max(0.0, deadline - time.monotonic()))
            except FutureTimeout:
                result.error = f"{timeout_s}s 타임아웃"
                jobs = None
            except NeedsDiscovery as exc:
                result.skipped = True
                log.info("%s 건너뜀: %s", adapter.key, exc)
                report.sources.append(result)
                continue
            except Exception as exc:  # noqa: BLE001 — 소스 하나의 실패는 실행을 못 죽인다
                result.error = f"{type(exc).__name__}: {exc}"
                jobs = None
            result.duration_ms = int((time.monotonic() - started) * 1000)
            _absorb(store, adapter, jobs, result, now, alerts, report)
            report.sources.append(result)
    return report


def _fetch(adapter: Adapter, client: Client) -> list[Job]:
    return adapter.fetch(client)


def _absorb(store: Store, adapter: Adapter, jobs: list[Job] | None,
            result: SourceResult, now: datetime, alerts: Alerts, report: RunReport) -> None:
    health = store.get_health(adapter.key) or {}
    consecutive_failures = int(health.get("consecutive_failures", 0))
    consecutive_zero = int(health.get("consecutive_zero", 0))

    if jobs is None:
        consecutive_failures += 1
        alerts.send(f":x: `{adapter.key}` 수집 실패 ({consecutive_failures}회 연속): {result.error}")
        store.put_health(adapter.key, {
            **health, "last_error": result.error, "last_error_at": now.isoformat(),
            "consecutive_failures": consecutive_failures,
        })
        return

    result.fetched = len(jobs)
    new_jobs = [job for job in jobs if store.put_job_if_new(job, now)]
    result.new = len(new_jobs)

    first_run = not health
    if first_run:
        result.seeded = True
    elif result.new > max(STORM_MIN, int(result.fetched * STORM_RATIO)):
        result.storm = True
        alerts.send(
            f":warning: `{adapter.key}` 신규 {result.new}/{result.fetched}건 — 폭증. "
            "job_id 체계나 사이트 구조가 바뀌었을 수 있다. 이번 실행은 알림을 보내지 않았다."
        )
    else:
        report.notify.extend(new_jobs)

    if result.fetched == 0:
        consecutive_zero += 1
        if consecutive_zero == ZERO_STREAK_ALERT:
            alerts.send(f":thinking_face: `{adapter.key}` {ZERO_STREAK_ALERT}회 연속 0건. "
                        "필터가 전부 걸러내거나 엔드포인트가 빈 목록을 주는지 확인할 것.")
    else:
        consecutive_zero = 0

    # 소스 하나가 계열사 여럿을 낸다(삼성 포털 → 삼성전자·삼성SDI…). 앱의 "현재 공고 N건"은
    # 계열사 단위여야 해서 계열사별로도 센다. 0건인 계열사는 키가 없다.
    counts: dict[str, int] = {}
    for job in jobs:
        counts[job.company] = counts.get(job.company, 0) + 1

    store.put_health(adapter.key, {
        "last_success_at": now.isoformat(),
        "last_fetched": result.fetched,
        "company_counts": counts,
        "last_new": result.new,
        "consecutive_failures": 0,
        "consecutive_zero": consecutive_zero,
    })
