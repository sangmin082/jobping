"""EventBridge(30분) → 수집 → 신규 공고 키를 SQS 로 넘긴다.

SQS 메시지는 **실행당 하나**다. 공고마다 하나씩 보내면 notifier 가 디바이스별
상한(5건)과 묶음을 계산할 수 없다 — 이번 실행의 신규 전체를 한 번에 봐야 한다.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from .. import collector, registry
from .common import alerts, enqueue, settings, store

log = logging.getLogger(__name__)


def handler(event, context):
    now = datetime.now(timezone.utc)
    report = collector.run(
        store(), registry.verified_adapters(), now=now, alerts=alerts(),
        timeout_s=settings().adapter_timeout_s,
    )
    log.info("collector: %s", report.summary())

    if report.notify and settings().new_jobs_queue_url:
        enqueue(settings().new_jobs_queue_url, {
            "run_at": now.isoformat(),
            "jobs": [{"company": j.company, "job_id": j.job_id} for j in report.notify],
        })
    return {"new": report.total_new, "notify": len(report.notify), "summary": report.summary()}
