"""저장소 계약 테스트 — 같은 테스트를 MemoryStore 와 SQLiteStore 에 돌린다.

collector/notifier/api 는 MemoryStore 로 검증돼 있다. SQLiteStore 가 같은 계약을
지키면 그 검증이 오라클 배포에도 그대로 성립한다.
"""

from datetime import datetime, timedelta, timezone

import pytest

from jobping.models import Job
from jobping.sqlite_store import SQLiteStore
from jobping.store import MemoryStore

NOW = datetime(2026, 10, 26, 3, 0, tzinfo=timezone.utc)


def job(i, company="sk_hynix", day=1):
    return Job.make(company=company, title=f"Job {i}", url=f"https://x.com/{company}/{i}",
                    source_id=str(i), roles=("Infra",))


@pytest.fixture(params=["memory", "sqlite-mem", "sqlite-file"])
def store(request, tmp_path):
    if request.param == "memory":
        return MemoryStore()
    if request.param == "sqlite-mem":
        return SQLiteStore(":memory:")
    return SQLiteStore(str(tmp_path / "jobping.db"))


class TestJobs:
    def test_put_if_new_is_true_once(self, store):
        assert store.put_job_if_new(job(1), NOW) is True
        assert store.put_job_if_new(job(1), NOW) is False

    def test_get_jobs_by_key_round_trips(self, store):
        j = job(1)
        store.put_job_if_new(j, NOW)
        got = store.get_jobs([(j.company, j.job_id), ("nope", "nope")])
        assert len(got) == 1
        assert got[0]["title"] == "Job 1" and got[0]["roles"] == ["Infra"]

    def test_query_newest_first_with_since_and_limit(self, store):
        for i in range(5):
            store.put_job_if_new(job(i), NOW + timedelta(hours=i))
        rows = store.query_jobs("sk_hynix", limit=3)
        assert [r["title"] for r in rows] == ["Job 4", "Job 3", "Job 2"]
        since = (NOW + timedelta(hours=2)).isoformat()
        assert [r["title"] for r in store.query_jobs("sk_hynix", limit=10, since=since)] == ["Job 4", "Job 3"]

    def test_query_is_per_company(self, store):
        store.put_job_if_new(job(1, "sk_hynix"), NOW)
        store.put_job_if_new(job(2, "tesla_kr"), NOW)
        assert [r["company"] for r in store.query_jobs("tesla_kr", limit=10)] == ["tesla_kr"]


class TestDevices:
    def test_upsert_and_get(self, store):
        store.put_device({"install_id": "a", "push_enabled": True, "keywords": ["x"]})
        store.put_device({"install_id": "a", "push_enabled": True, "keywords": ["y"]})
        assert store.get_device("a")["keywords"] == ["y"]
        assert store.get_device("nope") is None

    def test_list_only_push_enabled(self, store):
        store.put_device({"install_id": "on", "push_enabled": True})
        store.put_device({"install_id": "off", "push_enabled": False})
        assert [d["install_id"] for d in store.list_devices()] == ["on"]

    def test_delete(self, store):
        store.put_device({"install_id": "a", "push_enabled": True})
        store.delete_device("a")
        assert store.get_device("a") is None


class TestDeliveries:
    def test_claim_is_true_once(self, store):
        assert store.claim_delivery("a", "j1", "sent", NOW) is True
        assert store.claim_delivery("a", "j1", "sent", NOW) is False
        assert store.claim_delivery("b", "j1", "sent", NOW) is True

    def test_pending_then_sent(self, store):
        store.claim_delivery("a", "j1", "pending", NOW, {"title": "T", "company": "c"})
        store.claim_delivery("a", "j2", "sent", NOW)
        pending = store.list_pending_deliveries()
        assert [(p["job_id"], p["title"]) for p in pending] == [("j1", "T")]
        store.mark_delivery_sent("a", "j1", NOW)
        assert store.list_pending_deliveries() == []


class TestHealth:
    def test_put_get_list(self, store):
        assert store.get_health("naver") is None
        store.put_health("naver", {"last_fetched": 31})
        store.put_health("naver", {"last_fetched": 32})
        assert store.get_health("naver")["last_fetched"] == 32
        assert store.list_health() == [{"adapter": "naver", "last_fetched": 32}]


class TestSQLiteOnly:
    def test_purge_removes_expired_rows(self):
        s = SQLiteStore(":memory:")
        s.put_job_if_new(job(1), NOW - timedelta(days=100))   # TTL 90일 지남
        s.put_job_if_new(job(2), NOW)
        s.claim_delivery("a", "j", "sent", NOW - timedelta(days=10))  # TTL 7일 지남
        assert s.purge_expired(NOW) == (1, 1)
        assert s.counts()["jobs"] == 1

    def test_two_connections_see_each_others_writes(self, tmp_path):
        """API 서버와 수집 타이머는 별개 프로세스다. 같은 파일을 연다."""
        path = str(tmp_path / "db.sqlite")
        a, b = SQLiteStore(path), SQLiteStore(path)
        a.put_job_if_new(job(1), NOW)
        assert b.put_job_if_new(job(1), NOW) is False
        assert b.query_jobs("sk_hynix", limit=5)[0]["title"] == "Job 1"

    def test_korean_text_survives(self):
        s = SQLiteStore(":memory:")
        j = Job.make(company="sk_hynix", title="반도체 공정 엔지니어 (경력)", url="https://x.com/1")
        s.put_job_if_new(j, NOW)
        assert s.query_jobs("sk_hynix", limit=1)[0]["title"] == "반도체 공정 엔지니어 (경력)"
