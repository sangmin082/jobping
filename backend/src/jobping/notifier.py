"""알림 계획과 발송.

입력은 이번 실행의 신규 공고 목록과 디바이스 목록. 출력은 디바이스별로
"무엇을, 어떤 문구로" 보낼지의 계획이다. 계획과 발송을 나눈 이유는 계획이
순수 함수라 테스트하기 쉽고, 드라이런에서 실제 발송 없이 결과를 볼 수 있어서다.

규칙:
* 무료 티어는 서버에서 자른다 — 키워드 1개, 회사 3곳. 앱이 막아도 서버가 막는다
* 디바이스당 1회 실행 최대 5건. 넘으면 "새 공고 N건" 묶음 하나
* 조용한 시간(23–08 KST)엔 보류(`pending`)했다가 아침에 묶어 보낸다
* `deliveries` 조건부 쓰기로 같은 (사람, 공고) 는 한 번만 보낸다
* APNs 410 은 디바이스 삭제
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .alerts import Alerts
from .apns import APNsClient, alert_payload
from .matching import MAX_PUSH_PER_RUN, display_name, match_all
from .models import Job
from .store import Store

log = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

FREE_MAX_KEYWORDS = 1
FREE_MAX_COMPANIES = 3


@dataclass
class Push:
    install_id: str
    device_token: str
    title: str
    body: str
    job_ids: list[str]                 # 이 푸시가 대표하는 공고들
    job_id: str | None = None          # 단건이면 딥링크 대상
    url: str | None = None
    thread_id: str | None = None


@dataclass
class Plan:
    pushes: list[Push] = field(default_factory=list)
    pending: int = 0      # 조용한 시간이라 보류한 (디바이스, 공고) 수
    matched_devices: int = 0


def is_quiet(now: datetime, start_hour: int = 23, end_hour: int = 8) -> bool:
    hour = now.astimezone(KST).hour
    return hour >= start_hour or hour < end_hour


def effective_filters(device: dict) -> tuple[list[str], list[str]]:
    """티어에 따라 키워드·회사를 자른다. 순서는 사용자가 등록한 순서다."""
    keywords = [k for k in device.get("keywords") or [] if k]
    companies = [c for c in device.get("companies") or [] if c]
    if device.get("tier", "free") != "pro":
        keywords, companies = keywords[:FREE_MAX_KEYWORDS], companies[:FREE_MAX_COMPANIES]
    return keywords, companies


def plan(store: Store, devices: list[dict], jobs: list[Job], *, now: datetime,
         quiet: bool) -> Plan:
    result = Plan()
    if not jobs:
        return result
    for device in devices:
        token = device.get("device_token")
        install_id = device.get("install_id")
        if not token or not install_id:
            continue
        keywords, companies = effective_filters(device)
        if not keywords:
            continue
        hits = match_all(jobs, keywords, companies=companies or None)
        # 이미 보냈거나 보류 중인 공고는 뺀다. 조건부 쓰기라 동시 실행에도 안전하다.
        fresh = []
        for hit in hits:
            status = "pending" if quiet else "sent"
            extra = {"title": hit.job.title, "company": hit.job.company,
                     "url": hit.job.url, "keyword": hit.keyword}
            if store.claim_delivery(install_id, hit.job.job_id, status, now, extra):
                fresh.append(hit)
        if not fresh:
            continue
        result.matched_devices += 1
        if quiet:
            result.pending += len(fresh)
            continue
        result.pushes.extend(_pushes_for(install_id, token, [
            (h.job.job_id, h.job.company, h.job.title, h.job.url, h.keyword) for h in fresh
        ]))
    return result


def plan_flush(store: Store, devices: list[dict], *, now: datetime) -> Plan:
    """보류된 것을 디바이스별로 묶어 아침에 보낸다."""
    result = Plan()
    by_device: dict[str, list[dict]] = {}
    for d in store.list_pending_deliveries():
        by_device.setdefault(d["install_id"], []).append(d)
    tokens = {d.get("install_id"): d.get("device_token") for d in devices}
    for install_id, items in by_device.items():
        token = tokens.get(install_id)
        if not token:
            continue  # 디바이스가 사라졌다. 보류분은 TTL 로 사라진다
        result.matched_devices += 1
        result.pushes.extend(_pushes_for(install_id, token, [
            (i["job_id"], i.get("company", ""), i.get("title", ""), i.get("url"), i.get("keyword", ""))
            for i in items
        ]))
    return result


def _pushes_for(install_id: str, token: str,
                items: list[tuple[str, str, str, str | None, str]]) -> list[Push]:
    if len(items) > MAX_PUSH_PER_RUN:
        companies = sorted({display_name(c) for _, c, _, _, _ in items})
        shown = ", ".join(companies[:3]) + (" 외" if len(companies) > 3 else "")
        return [Push(install_id=install_id, device_token=token,
                     title=f"새 공고 {len(items)}건", body=shown,
                     job_ids=[i[0] for i in items])]
    return [
        Push(install_id=install_id, device_token=token,
             title=display_name(company), body=title, job_ids=[job_id],
             job_id=job_id, url=url, thread_id=company)
        for job_id, company, title, url, _kw in items
    ]


@dataclass
class SendReport:
    sent: int = 0
    failed: int = 0
    unregistered: int = 0


def send(store: Store, apns: APNsClient, pushes: list[Push], *, now: datetime,
         alerts: Alerts) -> SendReport:
    report = SendReport()
    for push in pushes:
        payload = alert_payload(push.title, push.body, job_id=push.job_id,
                                url=push.url, thread_id=push.thread_id)
        result = apns.send(push.device_token, payload,
                           collapse_id=push.job_id or f"bundle-{push.install_id}")
        if result.ok:
            report.sent += 1
            for job_id in push.job_ids:
                store.mark_delivery_sent(push.install_id, job_id, now)
        elif result.unregistered:
            report.unregistered += 1
            store.delete_device(push.install_id)
        else:
            report.failed += 1
            log.error("APNs 실패 %s: %s %s", push.install_id, result.status, result.reason)
    if report.failed:
        alerts.send(f":x: APNs 발송 실패 {report.failed}건 (성공 {report.sent}, 등록해제 {report.unregistered})")
    return report
