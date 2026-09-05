"""운영자 알림 — Slack 웹훅.

알림은 **드물어야 의미가 있다.** 매 실행마다 요약을 보내면 3일 안에 채널을
음소거하게 된다. 그래서 보내는 조건을 좁게 잡는다(collector.py 참고):
소스 예외, 연속 3회 0건, 신규 폭증(스키마 변경 의심), notifier 실패.
"""

from __future__ import annotations

import json
import logging
import urllib.request

log = logging.getLogger(__name__)


class Alerts:
    def __init__(self, webhook_url: str | None) -> None:
        self.webhook_url = webhook_url
        self.sent: list[str] = []  # 테스트와 드라이런에서 들여다본다

    def send(self, text: str) -> None:
        self.sent.append(text)
        if not self.webhook_url:
            log.warning("SLACK(미설정): %s", text)
            return
        body = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            self.webhook_url, data=body, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=5).read()
        except Exception as exc:  # noqa: BLE001 — 알림 실패로 본 작업을 죽이지 않는다
            log.error("Slack 전송 실패: %s", exc)
