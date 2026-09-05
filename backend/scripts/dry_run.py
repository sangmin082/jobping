#!/usr/bin/env python3
"""전체 파이프라인을 로컬에서, 아무것도 보내지 않고 돌린다.

    python scripts/dry_run.py                     # 첫 실행 = 시딩. 저장만 하고 알림 없음
    python scripts/dry_run.py                     # 두 번째 = 그 사이 새로 뜬 공고만 신규
    python scripts/dry_run.py --keywords 반도체,SRE --companies sk_hynix,tesla_kr
    python scripts/dry_run.py --sources naver,kakao --quiet   # 조용한 시간 시뮬레이션
    python scripts/dry_run.py --reset             # 로컬 상태 삭제

상태는 .dry-run-state.json 에 남는다. AWS 계정도, 자격 증명도 필요 없다.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from jobping import collector, notifier, registry  # noqa: E402
from jobping.alerts import Alerts  # noqa: E402
from jobping.models import Job  # noqa: E402
from jobping.store import MemoryStore  # noqa: E402

STATE = pathlib.Path(__file__).resolve().parents[1] / ".dry-run-state.json"


def load_state() -> MemoryStore:
    store = MemoryStore()
    if STATE.exists():
        raw = json.loads(STATE.read_text(encoding="utf-8"))
        store.jobs = {tuple(k.split("|", 1)): v for k, v in raw.get("jobs", {}).items()}
        store.health = raw.get("health", {})
        store.deliveries = {tuple(k.split("|", 1)): v for k, v in raw.get("deliveries", {}).items()}
    return store


def save_state(store: MemoryStore) -> None:
    STATE.write_text(json.dumps({
        "jobs": {f"{c}|{j}": v for (c, j), v in store.jobs.items()},
        "health": store.health,
        "deliveries": {f"{i}|{j}": v for (i, j), v in store.deliveries.items()},
    }, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--keywords", default="DevOps,SRE,반도체")
    ap.add_argument("--companies", default="", help="비우면 전체")
    ap.add_argument("--tier", default="pro", choices=["free", "pro"])
    ap.add_argument("--sources", default="", help="쉼표 구분. 비우면 검증된 전체")
    ap.add_argument("--quiet", action="store_true", help="조용한 시간으로 취급")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset:
        STATE.unlink(missing_ok=True)
        print("상태 삭제됨"); return 0

    store = load_state()
    first = not store.health
    adapters = registry.verified_adapters()
    if args.sources:
        wanted = set(args.sources.split(","))
        adapters = [a for a in adapters if a.key in wanted]
    alerts = Alerts(None)
    now = datetime.now(timezone.utc)

    print(f"{'시딩 실행' if first else '증분 실행'} — 소스 {len(adapters)}개\n")
    report = collector.run(store, adapters, now=now, alerts=alerts)
    for s in report.sources:
        tag = "실패 " + s.error if s.error else "시딩" if s.seeded else "폭증→알림 보류" if s.storm else ""
        print(f"  {s.key:10s} 수집 {s.fetched:4d}  신규 {s.new:4d}  {s.duration_ms:5d}ms  {tag}")
    print(f"\n신규 {report.total_new}건, 알림 대상 {len(report.notify)}건")
    for text in alerts.sent:
        print("  SLACK:", text)

    device = {"install_id": "local-device", "device_token": "deadbeef", "push_enabled": True,
              "tier": args.tier, "keywords": [k for k in args.keywords.split(",") if k],
              "companies": [c for c in args.companies.split(",") if c]}
    plan = notifier.plan(store, [device], report.notify, now=now, quiet=args.quiet)
    print(f"\n디바이스(tier={args.tier}, 키워드={device['keywords']}, 회사={device['companies'] or '전체'})")
    if plan.pending:
        print(f"  조용한 시간 — {plan.pending}건 보류(pending)")
    for p in plan.pushes:
        print(f"  PUSH [{p.title}] {p.body}")
        if p.url:
            print(f"       {p.url}")
    if not plan.pushes and not plan.pending:
        print("  보낼 것 없음")

    save_state(store)
    print(f"\n상태 저장: {STATE.name} (공고 {len(store.jobs)}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
