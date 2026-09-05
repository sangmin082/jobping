from __future__ import annotations

import functools
import json
import logging

import boto3

from ..alerts import Alerts
from ..apns import APNsClient
from ..settings import Settings
from ..store import DynamoStore

logging.getLogger().setLevel(logging.INFO)


@functools.lru_cache(maxsize=None)
def settings() -> Settings:
    return Settings.from_env()


@functools.lru_cache(maxsize=None)
def store() -> DynamoStore:
    s = settings()
    return DynamoStore(s.jobs_table, s.devices_table, s.deliveries_table, s.health_table)


@functools.lru_cache(maxsize=None)
def ssm_value(name: str) -> str | None:
    """SSM Parameter Store 에서 한 번만 읽는다. 콜드스타트당 1회."""
    if not name:
        return None
    resp = boto3.client("ssm").get_parameter(Name=name, WithDecryption=True)
    return resp["Parameter"]["Value"]


@functools.lru_cache(maxsize=None)
def alerts() -> Alerts:
    return Alerts(ssm_value(settings().slack_webhook_param))


@functools.lru_cache(maxsize=None)
def apns() -> APNsClient | None:
    s = settings()
    key = ssm_value(s.apns_key_param)
    if not (key and s.apns_key_id and s.apns_team_id and s.apns_bundle_id):
        logging.warning("APNs 미설정 — 푸시를 보내지 않는다")
        return None
    return APNsClient(key_pem=key, key_id=s.apns_key_id, team_id=s.apns_team_id,
                      bundle_id=s.apns_bundle_id, environment=s.apns_environment)


def enqueue(queue_url: str, body: dict) -> None:
    boto3.client("sqs").send_message(QueueUrl=queue_url, MessageBody=json.dumps(body))
