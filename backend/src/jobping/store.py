"""저장소 — DynamoDB 와, 테스트/드라이런용 인메모리 구현.

핵심 연산은 두 개의 **조건부 쓰기**다:

* `put_job_if_new` — `attribute_not_exists(job_id)`. 성공하면 신규 공고다.
  조회-후-쓰기 두 번이 아니라 한 번이고, 동시 실행돼도 한 쪽만 신규로 본다.
* `claim_delivery` — 같은 조건. 같은 사람에게 같은 공고를 두 번 보내지 않는다.
  Lambda 가 재시도돼도, notifier 가 두 번 돌아도 안전하다.

로직(collector/notifier)은 이 인터페이스만 보고 짜고, 테스트는 `MemoryStore`
로 돌린다. moto 같은 DynamoDB 흉내 라이브러리 없이도 전체 흐름이 검증된다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Protocol

from .models import Job

JOB_TTL = timedelta(days=90)
DELIVERY_TTL = timedelta(days=7)


class Store(Protocol):
    def put_job_if_new(self, job: Job, now: datetime) -> bool: ...
    def get_jobs(self, keys: Iterable[tuple[str, str]]) -> list[dict]: ...
    def list_devices(self) -> list[dict]: ...
    def delete_device(self, install_id: str) -> None: ...
    def claim_delivery(self, install_id: str, job_id: str, status: str,
                       now: datetime, extra: dict | None = None) -> bool: ...
    def list_pending_deliveries(self) -> list[dict]: ...
    def mark_delivery_sent(self, install_id: str, job_id: str, now: datetime) -> None: ...
    def get_health(self, adapter: str) -> dict | None: ...
    def put_health(self, adapter: str, record: dict) -> None: ...


# ---------------------------------------------------------------- in-memory

class MemoryStore:
    def __init__(self) -> None:
        self.jobs: dict[tuple[str, str], dict] = {}
        self.devices: dict[str, dict] = {}
        self.deliveries: dict[tuple[str, str], dict] = {}
        self.health: dict[str, dict] = {}

    def put_job_if_new(self, job: Job, now: datetime) -> bool:
        key = (job.company, job.job_id)
        if key in self.jobs:
            return False
        self.jobs[key] = job.to_item(now)
        return True

    def get_jobs(self, keys):
        return [self.jobs[k] for k in keys if k in self.jobs]

    def list_devices(self):
        return [d for d in self.devices.values() if d.get("push_enabled", True)]

    def delete_device(self, install_id):
        self.devices.pop(install_id, None)

    def claim_delivery(self, install_id, job_id, status, now, extra=None):
        key = (install_id, job_id)
        if key in self.deliveries:
            return False
        self.deliveries[key] = {"install_id": install_id, "job_id": job_id,
                                "status": status, "created_at": now.isoformat(),
                                **(extra or {})}
        return True

    def list_pending_deliveries(self):
        return [d for d in self.deliveries.values() if d["status"] == "pending"]

    def mark_delivery_sent(self, install_id, job_id, now):
        d = self.deliveries.get((install_id, job_id))
        if d:
            d["status"] = "sent"
            d["sent_at"] = now.isoformat()

    def get_health(self, adapter):
        return self.health.get(adapter)

    def put_health(self, adapter, record):
        self.health[adapter] = dict(record)


# ---------------------------------------------------------------- DynamoDB

class DynamoStore:
    def __init__(self, jobs: str, devices: str, deliveries: str, health: str,
                 resource: Any = None) -> None:
        import boto3
        ddb = resource or boto3.resource("dynamodb")
        self._jobs = ddb.Table(jobs)
        self._devices = ddb.Table(devices)
        self._deliveries = ddb.Table(deliveries)
        self._health = ddb.Table(health)

    def put_job_if_new(self, job, now):
        from botocore.exceptions import ClientError
        try:
            self._jobs.put_item(
                Item=job.to_item(now),
                ConditionExpression="attribute_not_exists(job_id)",
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def get_jobs(self, keys):
        keys = list(keys)
        if not keys:
            return []
        out: list[dict] = []
        # BatchGetItem 은 100개까지. 그 이상은 나눠 부른다.
        for i in range(0, len(keys), 100):
            chunk = [{"company": c, "job_id": j} for c, j in keys[i:i + 100]]
            resp = self._jobs.meta.client.batch_get_item(
                RequestItems={self._jobs.name: {"Keys": chunk}})
            out.extend(resp["Responses"].get(self._jobs.name, []))
            unprocessed = resp.get("UnprocessedKeys", {}).get(self._jobs.name)
            while unprocessed:
                resp = self._jobs.meta.client.batch_get_item(
                    RequestItems={self._jobs.name: unprocessed})
                out.extend(resp["Responses"].get(self._jobs.name, []))
                unprocessed = resp.get("UnprocessedKeys", {}).get(self._jobs.name)
        return out

    def list_devices(self):
        # 디바이스가 수천 개를 넘기 전까지는 Scan 이 가장 단순하고 충분하다.
        # 그 이상이 되면 push_enabled 를 파티션 키로 둔 GSI 로 바꾼다.
        from boto3.dynamodb.conditions import Attr
        items: list[dict] = []
        kwargs: dict = {"FilterExpression": Attr("push_enabled").eq(True)}
        while True:
            resp = self._devices.scan(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                return items
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def delete_device(self, install_id):
        self._devices.delete_item(Key={"install_id": install_id})

    def claim_delivery(self, install_id, job_id, status, now, extra=None):
        from botocore.exceptions import ClientError
        item = {"install_id": install_id, "job_id": job_id, "status": status,
                "created_at": now.isoformat(),
                "expires_at": int((now + DELIVERY_TTL).timestamp()),
                **(extra or {})}
        try:
            self._deliveries.put_item(
                Item=item, ConditionExpression="attribute_not_exists(job_id)")
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def list_pending_deliveries(self):
        from boto3.dynamodb.conditions import Attr
        items: list[dict] = []
        kwargs: dict = {"FilterExpression": Attr("status").eq("pending")}
        while True:
            resp = self._deliveries.scan(**kwargs)
            items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                return items
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def mark_delivery_sent(self, install_id, job_id, now):
        self._deliveries.update_item(
            Key={"install_id": install_id, "job_id": job_id},
            UpdateExpression="SET #s = :s, sent_at = :t",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":s": "sent", ":t": now.isoformat()},
        )

    def get_health(self, adapter):
        return self._health.get_item(Key={"adapter": adapter}).get("Item")

    def put_health(self, adapter, record):
        self._health.put_item(Item={"adapter": adapter, **record})
