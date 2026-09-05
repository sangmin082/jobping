"""환경 변수 → 설정. Lambda 에서는 template.yaml 이, 로컬에서는 셸이 채운다."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"환경 변수 {name} 이 없다")
    return value


@dataclass(frozen=True)
class Settings:
    jobs_table: str
    devices_table: str
    deliveries_table: str
    health_table: str
    new_jobs_queue_url: str
    #: SSM Parameter Store 경로. 값 자체는 Lambda 시작 시 한 번 읽는다.
    slack_webhook_param: str
    apns_key_param: str        # .p8 본문
    apns_key_id: str
    apns_team_id: str
    apns_bundle_id: str
    apns_environment: str      # "sandbox" | "production"
    #: 한 소스의 fetch 에 허용하는 시간. 넘으면 그 소스만 실패로 친다.
    adapter_timeout_s: int = 60
    #: 조용한 시간(KST). 이 사이엔 푸시를 보류했다가 끝나는 시각에 묶어 보낸다.
    quiet_start_hour_kst: int = 23
    quiet_end_hour_kst: int = 8

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            jobs_table=_env("JOBS_TABLE"),
            devices_table=_env("DEVICES_TABLE"),
            deliveries_table=_env("DELIVERIES_TABLE"),
            health_table=_env("HEALTH_TABLE"),
            new_jobs_queue_url=_env("NEW_JOBS_QUEUE_URL", ""),
            slack_webhook_param=_env("SLACK_WEBHOOK_PARAM", ""),
            apns_key_param=_env("APNS_KEY_PARAM", ""),
            apns_key_id=_env("APNS_KEY_ID", ""),
            apns_team_id=_env("APNS_TEAM_ID", ""),
            apns_bundle_id=_env("APNS_BUNDLE_ID", ""),
            apns_environment=_env("APNS_ENVIRONMENT", "sandbox"),
            adapter_timeout_s=int(_env("ADAPTER_TIMEOUT_S", "60")),
        )
