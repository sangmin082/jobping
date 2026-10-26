"""collector — 시딩, 폭증 차단, 헬스 카운터, 소스 격리."""

from datetime import datetime, timezone

import pytest

from jobping import collector
from jobping.adapters.base import Adapter, AdapterError, NeedsDiscovery
from jobping.alerts import Alerts
from jobping.models import Job
from jobping.store import MemoryStore

NOW = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)


def job(i, company="acme"):
    return Job.make(company=company, title=f"Engineer {i}", url=f"https://acme.com/jobs/{i}", source_id=str(i))


class Fake(Adapter):
    key = "acme"
    display_name = "Acme"
    site_url = "https://acme.com"
    verified = True

    def __init__(self, jobs=None, error=None):
        self._jobs, self._error = jobs or [], error

    def fetch(self, client):
        if self._error:
            raise self._error
        return list(self._jobs)


@pytest.fixture
def store():
    return MemoryStore()


@pytest.fixture
def alerts():
    return Alerts(None)


class TestSeeding:
    def test_first_run_stores_but_does_not_notify(self, store, alerts):
        """첫 배포 때 전체 공고가 알림으로 나가면 그날로 앱은 삭제된다."""
        r = collector.run(store, [Fake([job(i) for i in range(50)])], now=NOW, alerts=alerts)
        assert r.sources[0].seeded
        assert r.total_new == 50
        assert r.notify == []
        assert len(store.jobs) == 50

    def test_second_run_notifies_only_new(self, store, alerts):
        collector.run(store, [Fake([job(1), job(2)])], now=NOW, alerts=alerts)
        r = collector.run(store, [Fake([job(1), job(2), job(3)])], now=NOW, alerts=alerts)
        assert [j.source_id for j in r.notify] == ["3"]


class TestCompanyCounts:
    def test_health_counts_jobs_per_affiliate(self, store, alerts):
        """소스 하나가 계열사 여럿을 낸다. 앱은 계열사별 공고 수를 보여준다."""
        jobs = [job(1, "acme_a"), job(2, "acme_a"), job(3, "acme_b")]
        collector.run(store, [Fake(jobs)], now=NOW, alerts=alerts)
        h = store.get_health("acme")
        assert h["last_fetched"] == 3
        assert h["company_counts"] == {"acme_a": 2, "acme_b": 1}

    def test_affiliate_with_no_jobs_drops_out(self, store, alerts):
        collector.run(store, [Fake([job(1, "acme_a"), job(2, "acme_b")])], now=NOW, alerts=alerts)
        collector.run(store, [Fake([job(1, "acme_a")])], now=NOW, alerts=alerts)
        assert store.get_health("acme")["company_counts"] == {"acme_a": 1}


class TestStormGuard:
    def test_sudden_flood_is_held_back_and_reported(self, store, alerts):
        """job_id 체계가 바뀌면 전부 신규로 잡힌다. 그걸 알림으로 보내면 안 된다."""
        collector.run(store, [Fake([job(i) for i in range(100)])], now=NOW, alerts=alerts)
        r = collector.run(store, [Fake([job(i, company="acme2") for i in range(100)])],
                          now=NOW, alerts=alerts)
        assert r.sources[0].storm
        assert r.notify == []
        assert any("폭증" in t for t in alerts.sent)

    def test_normal_daily_volume_passes(self, store, alerts):
        collector.run(store, [Fake([job(i) for i in range(100)])], now=NOW, alerts=alerts)
        r = collector.run(store, [Fake([job(i) for i in range(120)])], now=NOW, alerts=alerts)
        assert not r.sources[0].storm
        assert len(r.notify) == 20


class TestHealth:
    def test_failure_increments_streak_and_alerts(self, store, alerts):
        collector.run(store, [Fake(error=AdapterError("boom"))], now=NOW, alerts=alerts)
        collector.run(store, [Fake(error=AdapterError("boom"))], now=NOW, alerts=alerts)
        assert store.health["acme"]["consecutive_failures"] == 2
        assert sum("수집 실패" in t for t in alerts.sent) == 2

    def test_success_resets_failure_streak(self, store, alerts):
        collector.run(store, [Fake(error=AdapterError("boom"))], now=NOW, alerts=alerts)
        collector.run(store, [Fake([job(1)])], now=NOW, alerts=alerts)
        assert store.health["acme"]["consecutive_failures"] == 0

    def test_zero_results_alert_only_after_three_in_a_row(self, store, alerts):
        """새벽·주말엔 진짜 0건이다. 한 번으로 알리면 오탐만 쌓인다."""
        for _ in range(3):
            collector.run(store, [Fake([])], now=NOW, alerts=alerts)
        assert sum("연속 0건" in t for t in alerts.sent) == 1
        collector.run(store, [Fake([])], now=NOW, alerts=alerts)
        assert sum("연속 0건" in t for t in alerts.sent) == 1  # 4회째는 또 안 보낸다

    def test_unimplemented_source_is_skipped_silently(self, store, alerts):
        r = collector.run(store, [Fake(error=NeedsDiscovery("나중에"))], now=NOW, alerts=alerts)
        assert r.sources[0].skipped
        assert alerts.sent == []
        assert "acme" not in store.health


class TestIsolation:
    def test_one_failing_source_does_not_stop_the_others(self, store, alerts):
        class Good(Fake):
            key = "good"
        r = collector.run(store, [Fake(error=RuntimeError("x")), Good([job(1, "good")])],
                          now=NOW, alerts=alerts)
        by = {s.key: s for s in r.sources}
        assert by["acme"].error and by["good"].new == 1

    def test_summary_is_one_line(self, store, alerts):
        r = collector.run(store, [Fake([job(1)])], now=NOW, alerts=alerts)
        assert "\n" not in r.summary() and "acme:1/1 SEED" in r.summary()
