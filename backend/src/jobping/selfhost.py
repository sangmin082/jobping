"""서버 한 대(오라클 VM 등)에서 돌리는 진입점.

    python -m jobping.selfhost collect   # 수집 → 신규 판정 → 매칭 → 발송 (30분 타이머)
    python -m jobping.selfhost flush     # 조용한 시간 보류분 발송 (08:00 KST 타이머)
    python -m jobping.selfhost serve     # 앱 API (Caddy 뒤에서 127.0.0.1:8080)
    python -m jobping.selfhost status    # 소스 헬스와 테이블 건수

AWS 판과의 차이는 연결부뿐이다. 로직(collector / notifier / api)은 같은 모듈을
그대로 부른다.

* SQS 가 없다. Lambda 에선 수집과 발송을 큐로 나눴지만, 서버 한 대에선 같은
  프로세스에서 이어 부르면 된다. 발송이 실패해도 신규 판정은 이미 저장됐고
  deliveries 조건부 쓰기 덕에 재실행해도 중복 발송이 없다.
* 비밀값은 SSM 이 아니라 환경 변수(/etc/jobping/env)에서 읽는다.

설정 (환경 변수):
    JOBPING_DB            SQLite 파일 경로 (기본 /var/lib/jobping/jobping.db)
    SLACK_WEBHOOK_URL     운영 알림. 비우면 로그로만 남는다
    APNS_KEY_FILE         .p8 파일 경로. 비우면 발송을 건너뛴다(수집·매칭은 돈다)
    APNS_KEY_ID / APNS_TEAM_ID / APNS_BUNDLE_ID
    APNS_ENVIRONMENT      sandbox | production (TestFlight 빌드는 production)
    JOBPING_SOURCES       쉼표 구분. 비우면 검증된 소스 전체
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import api, collector, notifier, registry
from .alerts import Alerts
from .apns import APNsClient
from .sqlite_store import SQLiteStore

log = logging.getLogger("jobping")

DEFAULT_DB = "/var/lib/jobping/jobping.db"
MAX_BODY = 64 * 1024


# ---------------------------------------------------------------- 구성

def open_store() -> SQLiteStore:
    return SQLiteStore(os.environ.get("JOBPING_DB", DEFAULT_DB))


def make_alerts() -> Alerts:
    return Alerts(os.environ.get("SLACK_WEBHOOK_URL") or None)


def make_apns() -> APNsClient | None:
    key_file = os.environ.get("APNS_KEY_FILE", "")
    key_id = os.environ.get("APNS_KEY_ID", "")
    team_id = os.environ.get("APNS_TEAM_ID", "")
    bundle_id = os.environ.get("APNS_BUNDLE_ID", "")
    if not (key_file and key_id and team_id and bundle_id):
        log.warning("APNs 미설정 — 푸시를 보내지 않는다 (수집·매칭은 정상)")
        return None
    try:
        with open(key_file, encoding="utf-8") as f:
            key = f.read()
    except OSError as exc:
        log.error("APNs 키 파일을 못 읽었다: %s", exc)
        return None
    return APNsClient(key_pem=key, key_id=key_id, team_id=team_id, bundle_id=bundle_id,
                      environment=os.environ.get("APNS_ENVIRONMENT", "sandbox"))


def selected_adapters():
    adapters = registry.verified_adapters()
    wanted = {s for s in os.environ.get("JOBPING_SOURCES", "").split(",") if s}
    return [a for a in adapters if a.key in wanted] if wanted else adapters


# ---------------------------------------------------------------- 명령

def cmd_collect(store, alerts: Alerts, apns: APNsClient | None, *,
                now: datetime | None = None, adapters=None) -> dict:
    now = now or datetime.now(timezone.utc)
    purged = store.purge_expired(now)
    report = collector.run(store, adapters if adapters is not None else selected_adapters(),
                           now=now, alerts=alerts)
    log.info("collect: %s (만료 삭제 %s)", report.summary(), purged)

    devices = store.list_devices()
    plan = notifier.plan(store, devices, report.notify, now=now,
                         quiet=notifier.is_quiet(now))
    sent = _send(store, apns, plan, now, alerts)
    result = {"new": report.total_new, "notify": len(report.notify),
              "devices": len(devices), "pushes": len(plan.pushes),
              "pending": plan.pending, "sent": sent}
    log.info("collect 결과: %s", result)
    return result


def cmd_flush(store, alerts: Alerts, apns: APNsClient | None, *,
              now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    plan = notifier.plan_flush(store, store.list_devices(), now=now)
    sent = _send(store, apns, plan, now, alerts)
    result = {"pushes": len(plan.pushes), "sent": sent}
    log.info("flush 결과: %s", result)
    return result


def _send(store, apns, plan, now, alerts) -> int:
    if not plan.pushes:
        return 0
    if apns is None:
        log.info("APNs 미설정이라 %d건을 보내지 않았다", len(plan.pushes))
        return 0
    return notifier.send(store, apns, plan.pushes, now=now, alerts=alerts).sent


def cmd_status(store) -> dict:
    return {"counts": store.counts(),
            "health": sorted(store.list_health(), key=lambda h: h["adapter"])}


# ---------------------------------------------------------------- HTTP

def make_handler(store):
    """api.route() 는 API Gateway 이벤트 dict 를 받는다. HTTP 요청을 그 모양으로 바꾼다."""

    class Handler(BaseHTTPRequestHandler):
        server_version = "jobping"

        def _dispatch(self, method: str) -> None:
            parts = urlsplit(self.path)
            query = {k: v[0] for k, v in parse_qs(parts.query).items()}
            body = None
            if method == "POST":
                length = int(self.headers.get("Content-Length") or 0)
                if length > MAX_BODY:
                    return self._reply(413, {"content-type": "application/json"},
                                       json.dumps({"error": "본문이 너무 크다"}))
                body = self.rfile.read(length).decode("utf-8", "replace") if length else None
            event = {"requestContext": {"http": {"method": method}},
                     "rawPath": parts.path, "queryStringParameters": query, "body": body}
            resp = api.route(store, event)
            self._reply(resp["statusCode"], resp.get("headers", {}), resp.get("body", ""))

        def _reply(self, status: int, headers: dict, body: str) -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            for k, v in headers.items():
                self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            self._dispatch("GET")

        def do_POST(self):  # noqa: N802
            self._dispatch("POST")

        def log_message(self, fmt, *args):  # 접근 로그는 Caddy 가 남긴다
            pass

    return Handler


def serve(store, host: str, port: int) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(store))
    log.info("API 서버 %s:%d", host, port)
    httpd.serve_forever()


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s",
                        stream=sys.stdout)
    ap = argparse.ArgumentParser(prog="jobping", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("collect")
    sub.add_parser("flush")
    sub.add_parser("status")
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8080)
    args = ap.parse_args(argv)

    store = open_store()
    if args.cmd == "serve":
        serve(store, args.host, args.port)
        return 0
    if args.cmd == "status":
        print(json.dumps(cmd_status(store), ensure_ascii=False, indent=1))
        return 0
    alerts, apns = make_alerts(), make_apns()
    try:
        fn = cmd_collect if args.cmd == "collect" else cmd_flush
        print(json.dumps(fn(store, alerts, apns), ensure_ascii=False))
    finally:
        if apns:
            apns.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
