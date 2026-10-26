"""API — 이벤트 dict 를 흉내 내 route() 를 직접 부른다. API Gateway 없이 검증된다."""

import json
from datetime import datetime, timezone

import pytest

from jobping import api
from jobping.models import Job
from jobping.store import MemoryStore

NOW = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)
UUID = "6f1a7b7e-3c1d-4a6e-9c3b-2b9c1d4e5f60"


def ev(method, path, query=None, body=None):
    return {"requestContext": {"http": {"method": method}}, "rawPath": path,
            "queryStringParameters": query or {},
            "body": json.dumps(body) if body is not None else None}


def call(store, *a, **k):
    resp = api.route(store, ev(*a, **k), now=NOW)
    return resp["statusCode"], json.loads(resp["body"])


@pytest.fixture
def store():
    s = MemoryStore()
    for i, (company, t) in enumerate([("sk_hynix", 1), ("sk_hynix", 3), ("tesla_kr", 2), ("samsung_ds", 4)]):
        job = Job.make(company=company, title=f"Job {i}", url=f"https://x.com/{company}/{i}", source_id=str(i))
        s.put_job_if_new(job, datetime(2026, 9, t, tzinfo=timezone.utc))
    s.put_health("skcareers", {"last_success_at": "2026-09-05T02:30:00+00:00", "last_fetched": 88})
    return s


class TestCompanies:
    def test_lists_only_app_companies_with_health(self, store):
        status, body = call(store, "GET", "/v1/companies")
        assert status == 200
        by = {c["key"]: c for c in body["companies"]}
        assert by["sk_hynix"]["last_fetched"] == 88
        assert by["sk_hynix"]["group"] == "SK"
        assert by["tesla_kr"]["last_success_at"] is None
        # 예전 앱 호환용. 값은 사실상 무제한(키워드 상한 20, 회사는 전체)이다.
        assert body["free_tier"] == {"max_keywords": 20, "max_companies": len(body["companies"])}


class TestJobs:
    def test_requires_companies(self, store):
        status, body = call(store, "GET", "/v1/jobs")
        assert status == 400 and "companies" in body["error"]

    def test_merges_companies_newest_first(self, store):
        status, body = call(store, "GET", "/v1/jobs", {"companies": "sk_hynix,tesla_kr"})
        assert status == 200
        assert [j["title"] for j in body["jobs"]] == ["Job 1", "Job 2", "Job 0"]
        assert body["next_since"] == body["jobs"][0]["first_seen_at"]

    def test_since_returns_only_newer(self, store):
        _, body = call(store, "GET", "/v1/jobs", {"companies": "sk_hynix,tesla_kr,samsung_ds",
                                                   "since": "2026-09-02T00:00:00+00:00"})
        assert {j["title"] for j in body["jobs"]} == {"Job 1", "Job 3"}

    def test_rejects_unknown_company(self, store):
        status, body = call(store, "GET", "/v1/jobs", {"companies": "sk_hynix,nope"})
        assert status == 400 and "nope" in body["error"]

    def test_limit_is_clamped(self, store):
        _, body = call(store, "GET", "/v1/jobs", {"companies": "sk_hynix", "limit": "99999"})
        assert len(body["jobs"]) <= api.MAX_LIMIT
        _, body = call(store, "GET", "/v1/jobs", {"companies": "sk_hynix", "limit": "1"})
        assert len(body["jobs"]) == 1

    def test_does_not_leak_internal_fields(self, store):
        _, body = call(store, "GET", "/v1/jobs", {"companies": "sk_hynix"})
        assert "expires_at" not in body["jobs"][0]


class TestDevices:
    def test_upsert_creates_then_updates(self, store):
        status, body = call(store, "POST", "/v1/devices", body={
            "install_id": UUID, "device_token": "ab" * 32,
            "keywords": ["DevOps", " dev ops ", "devops"], "companies": ["sk_hynix"]})
        assert status == 200
        assert body["tier"] == "free" and body["push_registered"]
        assert store.devices[UUID]["keywords"] == ["DevOps"]  # 중복·공백 정리

        call(store, "POST", "/v1/devices", body={"install_id": UUID, "keywords": ["iOS"], "companies": []})
        d = store.devices[UUID]
        assert d["keywords"] == ["iOS"] and d["device_token"] == "ab" * 32  # 토큰은 유지

    def test_free_user_gets_every_keyword_and_company(self, store):
        """전면 무료. 티어로 자르지 않는다."""
        companies = ["sk_hynix", "tesla_kr", "samsung_ds", "naver"]
        _, body = call(store, "POST", "/v1/devices", body={
            "install_id": UUID, "keywords": ["a", "b"], "companies": companies})
        assert body["tier"] == "free"
        assert body["effective"] == {"keywords": ["a", "b"], "companies": companies}

    def test_client_cannot_set_tier(self, store):
        """티어는 결제 검증만 바꾼다. 본문의 tier 는 무시된다."""
        call(store, "POST", "/v1/devices", body={"install_id": UUID, "tier": "pro"})
        assert store.devices[UUID]["tier"] == "free"

    @pytest.mark.parametrize("bad", [{}, {"install_id": "not-a-uuid"},
                                     {"install_id": UUID, "keywords": "devops"},
                                     {"install_id": UUID, "companies": ["nope"]},
                                     {"install_id": UUID, "device_token": "zz"}])
    def test_validation(self, store, bad):
        status, _ = call(store, "POST", "/v1/devices", body=bad)
        assert status == 400

    def test_non_json_body(self, store):
        resp = api.route(store, {**ev("POST", "/v1/devices"), "body": "{not json"}, now=NOW)
        assert resp["statusCode"] == 400


class TestRouting:
    def test_unknown_route_is_404(self, store):
        status, _ = call(store, "GET", "/v1/nope")
        assert status == 404

    def test_health(self, store):
        assert call(store, "GET", "/v1/health") == (200, {"ok": True})

    def test_json_is_utf8_not_escaped(self, store):
        resp = api.route(store, ev("GET", "/v1/companies"), now=NOW)
        assert "SK하이닉스" in resp["body"]
