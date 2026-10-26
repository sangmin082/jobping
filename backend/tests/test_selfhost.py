"""서버 한 대 실행기 — 수집→발송 파이프라인과 HTTP 어댑터."""

import json
import threading
import urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

import pytest

from jobping import selfhost
from jobping.adapters.base import Adapter
from jobping.alerts import Alerts
from jobping.models import Job
from jobping.sqlite_store import SQLiteStore

DAY = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)    # 12:00 KST
NIGHT = datetime(2026, 10, 26, 16, 0, tzinfo=timezone.utc)  # 01:00 KST
UUID = "6f1a7b7e-3c1d-4a6e-9c3b-2b9c1d4e5f60"


class Fake(Adapter):
    key, display_name, site_url, verified = "acme", "Acme", "https://acme.com", True

    def __init__(self, titles):
        self.titles = titles

    def fetch(self, client):
        return [Job.make(company="sk_hynix", title=t, url=f"https://acme.com/{i}", source_id=t)
                for i, t in enumerate(self.titles)]


@pytest.fixture
def store():
    s = SQLiteStore(":memory:")
    s.put_device({"install_id": UUID, "device_token": "ab" * 32, "push_enabled": True,
                  "tier": "pro", "keywords": ["devops"], "companies": []})
    return s


class TestCollect:
    def test_first_run_seeds_and_sends_nothing(self, store):
        r = selfhost.cmd_collect(store, Alerts(None), None, now=DAY,
                                 adapters=[Fake(["DevOps A", "Designer"])])
        assert r["new"] == 2 and r["notify"] == 0 and r["pushes"] == 0

    def test_second_run_plans_a_push_for_the_new_match(self, store):
        selfhost.cmd_collect(store, Alerts(None), None, now=DAY, adapters=[Fake(["DevOps A"])])
        r = selfhost.cmd_collect(store, Alerts(None), None, now=DAY,
                                 adapters=[Fake(["DevOps A", "DevOps B", "Designer"])])
        assert r["notify"] == 2 and r["pushes"] == 1
        assert r["sent"] == 0  # APNs 미설정 — 계획까지만

    def test_night_match_is_held_then_flushed(self, store):
        selfhost.cmd_collect(store, Alerts(None), None, now=NIGHT, adapters=[Fake(["DevOps A"])])
        r = selfhost.cmd_collect(store, Alerts(None), None, now=NIGHT,
                                 adapters=[Fake(["DevOps A", "DevOps B"])])
        assert r["pending"] == 1 and r["pushes"] == 0
        f = selfhost.cmd_flush(store, Alerts(None), None, now=DAY)
        assert f["pushes"] == 1


@pytest.fixture
def server(store):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), selfhost.make_handler(store))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def http(url, data=None):
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


class TestHTTP:
    def test_health(self, server):
        assert http(f"{server}/v1/health") == (200, {"ok": True})

    def test_companies_lists_korean_names(self, server):
        status, body = http(f"{server}/v1/companies")
        assert status == 200
        assert any(c["display_name"] == "SK하이닉스" for c in body["companies"])

    def test_device_post_then_jobs_get(self, server, store):
        status, body = http(f"{server}/v1/devices",
                            {"install_id": UUID, "keywords": ["iOS"], "companies": ["sk_hynix"]})
        assert status == 200 and body["tier"] == "pro"   # 기존 티어 유지
        store.put_job_if_new(Job.make(company="sk_hynix", title="iOS Dev", url="https://x.com/1"), DAY)
        status, body = http(f"{server}/v1/jobs?companies=sk_hynix&limit=5")
        assert status == 200 and body["jobs"][0]["title"] == "iOS Dev"

    def test_validation_error_is_400_json(self, server):
        status, body = http(f"{server}/v1/jobs")
        assert status == 400 and "companies" in body["error"]

    def test_unknown_route_is_404(self, server):
        assert http(f"{server}/nope")[0] == 404

    def test_oversized_body_is_rejected(self, server):
        status, _ = http(f"{server}/v1/devices", {"install_id": UUID, "pad": "x" * 70_000})
        assert status == 413
