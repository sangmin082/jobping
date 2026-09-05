"""APNs 클라이언트 — 토큰(.p8) 인증, HTTP/2.

Apple 이 요구하는 것:
* HTTP/2 — `httpx` 에 `http2=True`. 표준 라이브러리로는 안 된다
* `authorization: bearer <JWT>` — ES256 으로 서명, **발급 후 20분~60분 사이에
  갱신**. 너무 자주 갱신해도(1분 미만) 거부한다. 50분마다 새로 만든다
* `apns-topic` = 번들 ID, `apns-push-type: alert`

응답 처리에서 중요한 건 **410 Unregistered** 다. 앱이 삭제됐거나 토큰이
바뀐 것이므로 그 디바이스를 지워야 한다. 안 지우면 매 실행마다 실패 요청이
쌓이고 Apple 이 우리를 노이즈로 본다.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx
import jwt

log = logging.getLogger(__name__)

HOSTS = {
    "production": "https://api.push.apple.com",
    "sandbox": "https://api.sandbox.push.apple.com",
}
TOKEN_LIFETIME_S = 50 * 60


@dataclass(frozen=True)
class PushResult:
    ok: bool
    status: int
    reason: str = ""

    @property
    def unregistered(self) -> bool:
        return self.status == 410 or self.reason in ("Unregistered", "BadDeviceToken")


class APNsClient:
    def __init__(self, *, key_pem: str, key_id: str, team_id: str, bundle_id: str,
                 environment: str = "sandbox", transport: httpx.BaseTransport | None = None):
        self.key_pem = key_pem
        self.key_id = key_id
        self.team_id = team_id
        self.bundle_id = bundle_id
        self.host = HOSTS[environment]
        self._token: str | None = None
        self._token_issued = 0.0
        self._http = httpx.Client(http2=transport is None, base_url=self.host,
                                  timeout=10, transport=transport)

    def _bearer(self, now: float | None = None) -> str:
        now = now if now is not None else time.time()
        if self._token is None or now - self._token_issued > TOKEN_LIFETIME_S:
            self._token = jwt.encode(
                {"iss": self.team_id, "iat": int(now)},
                self.key_pem, algorithm="ES256", headers={"kid": self.key_id},
            )
            self._token_issued = now
        return self._token

    def send(self, device_token: str, payload: dict, *, collapse_id: str | None = None) -> PushResult:
        headers = {
            "authorization": f"bearer {self._bearer()}",
            "apns-topic": self.bundle_id,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id[:64]
        try:
            resp = self._http.post(f"/3/device/{device_token}", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            return PushResult(ok=False, status=0, reason=f"transport: {exc}")
        if resp.status_code == 200:
            return PushResult(ok=True, status=200)
        reason = ""
        try:
            reason = resp.json().get("reason", "")
        except ValueError:
            pass
        return PushResult(ok=False, status=resp.status_code, reason=reason)

    def close(self) -> None:
        self._http.close()


def alert_payload(title: str, body: str, *, job_id: str | None = None,
                  url: str | None = None, thread_id: str | None = None) -> dict:
    aps: dict = {"alert": {"title": title, "body": body}, "sound": "default"}
    if thread_id:
        aps["thread-id"] = thread_id
    payload: dict = {"aps": aps}
    if job_id:
        payload["job_id"] = job_id
    if url:
        payload["url"] = url
    return payload
