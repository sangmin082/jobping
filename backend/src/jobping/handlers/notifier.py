"""SQS(신규 공고) → 매칭 → APNs.  또는 EventBridge(아침 08:00 KST) → 보류분 발송."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from .. import notifier
from ..models import Job
from .common import alerts, apns, settings, store

log = logging.getLogger(__name__)


def handler(event, context):
    now = datetime.now(timezone.utc)
    s = settings()
    devices = store().list_devices()

    if event.get("flush"):
        p = notifier.plan_flush(store(), devices, now=now)
    else:
        keys = []
        for record in event.get("Records", []):
            body = json.loads(record["body"])
            keys.extend((j["company"], j["job_id"]) for j in body.get("jobs", []))
        jobs = [_from_item(i) for i in store().get_jobs(keys)]
        quiet = notifier.is_quiet(now, s.quiet_start_hour_kst, s.quiet_end_hour_kst)
        p = notifier.plan(store(), devices, jobs, now=now, quiet=quiet)

    client = apns()
    if client is None or not p.pushes:
        log.info("notifier: devices=%d matched=%d pushes=%d pending=%d (발송 안 함)",
                 len(devices), p.matched_devices, len(p.pushes), p.pending)
        return {"pushes": len(p.pushes), "pending": p.pending, "sent": 0}
    report = notifier.send(store(), client, p.pushes, now=now, alerts=alerts())
    log.info("notifier: sent=%d failed=%d unregistered=%d pending=%d",
             report.sent, report.failed, report.unregistered, p.pending)
    return {"pushes": len(p.pushes), "pending": p.pending, "sent": report.sent}


def _from_item(item: dict) -> Job:
    """DynamoDB 아이템 → Job. job_id 는 저장된 값을 그대로 쓴다."""
    from datetime import datetime as dt
    posted = item.get("posted_at")
    return Job(
        company=item["company"], title=item["title"], url=item["url"], job_id=item["job_id"],
        posted_at=dt.fromisoformat(posted) if posted else None,
        location=item.get("location"), department=item.get("department"),
        employment_type=item.get("employment_type"), source_id=item.get("source_id"),
        roles=tuple(item.get("roles") or ()),
    )
