"""notifier — 티어 제한, 상한·묶음, 조용한 시간, 중복 방지, 410 처리."""

from datetime import datetime, timezone

import httpx
import pytest

from jobping import notifier
from jobping.alerts import Alerts
from jobping.apns import APNsClient
from jobping.models import Job
from jobping.store import MemoryStore

NOW_DAY = datetime(2026, 9, 5, 3, 0, tzinfo=timezone.utc)    # 12:00 KST
NOW_NIGHT = datetime(2026, 9, 5, 16, 0, tzinfo=timezone.utc)  # 01:00 KST


def job(i, company="sk_hynix", title=None):
    return Job.make(company=company, title=title or f"DevOps Engineer {i}",
                    url=f"https://x.com/{company}/{i}", source_id=str(i))


def device(**over):
    base = {"install_id": "dev-1", "device_token": "tok", "push_enabled": True,
            "tier": "pro", "keywords": ["devops"], "companies": []}
    return {**base, **over}


@pytest.fixture
def store():
    return MemoryStore()


class TestFilters:
    def test_free_tier_is_not_cut(self):
        """전면 무료. 무료 디바이스도 키워드·회사를 전부 쓴다."""
        d = device(tier="free", keywords=["a", "b", "c"], companies=["x", "y", "z", "w"])
        assert notifier.effective_filters(d) == (["a", "b", "c"], ["x", "y", "z", "w"])

    def test_free_user_second_keyword_matches(self, store):
        d = device(tier="free", keywords=["ios", "devops"])
        p = notifier.plan(store, [d], [job(1)], now=NOW_DAY, quiet=False)
        assert len(p.pushes) == 1

    def test_no_keywords_sends_every_job_at_chosen_companies(self, store):
        """키워드는 선택이다. 비우면 고른 회사의 새 공고를 다 받는다."""
        d = device(keywords=[], companies=["sk_hynix"])
        jobs = [job(1, title="회계 담당자"), job(2, company="naver", title="회계 담당자")]
        p = notifier.plan(store, [d], jobs, now=NOW_DAY, quiet=False)
        assert [x.body for x in p.pushes] == ["회계 담당자"]
        assert p.pushes[0].title == "SK하이닉스"

    def test_no_keywords_still_applies_excludes(self, store):
        d = device(keywords=[], companies=["sk_hynix"])
        p = notifier.plan(store, [d], [job(1, title="DevOps 인턴")], now=NOW_DAY, quiet=False)
        assert p.pushes == []

    def test_nothing_chosen_sends_nothing(self, store):
        """회사도 키워드도 없으면 전체 공고가 다 걸린다. 그건 스팸이라 안 보낸다."""
        d = device(keywords=[], companies=[])
        p = notifier.plan(store, [d], [job(1)], now=NOW_DAY, quiet=False)
        assert p.pushes == []


class TestCapAndBundle:
    def test_individual_pushes_under_cap(self, store):
        p = notifier.plan(store, [device()], [job(i) for i in range(3)], now=NOW_DAY, quiet=False)
        assert len(p.pushes) == 3
        assert p.pushes[0].title == "SK하이닉스" and p.pushes[0].job_id

    def test_over_cap_collapses_into_one_bundle(self, store):
        """알림 20개가 한 번에 터지면 그날로 알림이 꺼진다."""
        p = notifier.plan(store, [device()], [job(i) for i in range(9)], now=NOW_DAY, quiet=False)
        assert len(p.pushes) == 1
        assert p.pushes[0].title == "새 공고 9건"
        assert len(p.pushes[0].job_ids) == 9

    def test_company_filter_applies(self, store):
        p = notifier.plan(store, [device(companies=["tesla_kr"])],
                          [job(1, "sk_hynix"), job(2, "tesla_kr")], now=NOW_DAY, quiet=False)
        assert [x.thread_id for x in p.pushes] == ["tesla_kr"]


class TestDedupe:
    def test_same_job_is_never_sent_twice_to_the_same_device(self, store):
        notifier.plan(store, [device()], [job(1)], now=NOW_DAY, quiet=False)
        p = notifier.plan(store, [device()], [job(1)], now=NOW_DAY, quiet=False)
        assert p.pushes == []

    def test_different_devices_each_get_it(self, store):
        p = notifier.plan(store, [device(install_id="a"), device(install_id="b")],
                          [job(1)], now=NOW_DAY, quiet=False)
        assert len(p.pushes) == 2


class TestQuietHours:
    @pytest.mark.parametrize("utc_hour,expected", [(3, False), (13, False), (14, True), (16, True), (22, True), (23, False)])
    def test_window_is_23_to_08_kst(self, utc_hour, expected):
        now = datetime(2026, 9, 5, utc_hour, 0, tzinfo=timezone.utc)
        assert notifier.is_quiet(now) is expected

    def test_night_matches_are_held_as_pending(self, store):
        p = notifier.plan(store, [device()], [job(1), job(2)], now=NOW_NIGHT, quiet=True)
        assert p.pushes == [] and p.pending == 2
        assert all(d["status"] == "pending" for d in store.deliveries.values())

    def test_morning_flush_bundles_pending_per_device(self, store):
        notifier.plan(store, [device()], [job(i) for i in range(7)], now=NOW_NIGHT, quiet=True)
        p = notifier.plan_flush(store, [device()], now=NOW_DAY)
        assert len(p.pushes) == 1 and p.pushes[0].title == "새 공고 7건"

    def test_flush_skips_devices_that_disappeared(self, store):
        notifier.plan(store, [device()], [job(1)], now=NOW_NIGHT, quiet=True)
        p = notifier.plan_flush(store, [], now=NOW_DAY)
        assert p.pushes == []

    def test_pending_job_is_not_re_pushed_in_daytime(self, store):
        """보류된 공고가 다음 실행에서 다시 신규로 잡혀도 두 번 가면 안 된다."""
        notifier.plan(store, [device()], [job(1)], now=NOW_NIGHT, quiet=True)
        p = notifier.plan(store, [device()], [job(1)], now=NOW_DAY, quiet=False)
        assert p.pushes == []


def apns_with(status: int, reason: str = ""):
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"reason": reason} if reason else {}
        return httpx.Response(status, json=body)
    key = _test_key()
    return APNsClient(key_pem=key, key_id="KID", team_id="TEAM", bundle_id="com.x.y",
                      transport=httpx.MockTransport(handler))


def _test_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    k = ec.generate_private_key(ec.SECP256R1())
    return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                           serialization.NoEncryption()).decode()


class TestSend:
    def test_success_marks_deliveries_sent(self, store):
        store.devices["dev-1"] = device()
        p = notifier.plan(store, [device()], [job(1)], now=NOW_DAY, quiet=False)
        r = notifier.send(store, apns_with(200), p.pushes, now=NOW_DAY, alerts=Alerts(None))
        assert r.sent == 1
        assert store.deliveries[("dev-1", job(1).job_id)]["status"] == "sent"

    def test_410_removes_the_device(self, store):
        """지우지 않으면 매 실행마다 실패 요청이 쌓이고 Apple 이 우리를 노이즈로 본다."""
        store.devices["dev-1"] = device()
        p = notifier.plan(store, [device()], [job(1)], now=NOW_DAY, quiet=False)
        r = notifier.send(store, apns_with(410, "Unregistered"), p.pushes, now=NOW_DAY, alerts=Alerts(None))
        assert r.unregistered == 1 and "dev-1" not in store.devices

    def test_other_failures_alert_once(self, store):
        alerts = Alerts(None)
        p = notifier.plan(store, [device()], [job(1), job(2)], now=NOW_DAY, quiet=False)
        r = notifier.send(store, apns_with(500, "InternalServerError"), p.pushes, now=NOW_DAY, alerts=alerts)
        assert r.failed == 2 and len(alerts.sent) == 1

    def test_bearer_token_is_reused_within_lifetime(self):
        client = apns_with(200)
        a = client._bearer(now=1_000_000)
        b = client._bearer(now=1_000_000 + 40 * 60)
        c = client._bearer(now=1_000_000 + 55 * 60)
        assert a == b and a != c
