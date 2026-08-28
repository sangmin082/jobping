from datetime import datetime, timezone

import pytest

from jobping.models import Job, clean_url, identity_url, normalize_text


class TestCleanUrl:
    """저장하고 사용자에게 보여줄 URL — 눌렀을 때 실제로 열려야 한다."""

    def test_strips_tracking_params(self):
        assert clean_url(
            "https://x.com/careers/job/123?utm_source=a&gclid=b&lang=ko"
        ) == "https://x.com/careers/job/123?lang=ko"

    def test_keeps_fragment(self):
        """해시 라우팅 SPA에서는 프래그먼트가 곧 공고 경로다."""
        url = "https://hire-r1.mokahr.com/social-recruitment/tesla/100000166#/job/abc"
        assert clean_url(url) == url

    def test_keeps_trailing_slash(self):
        """`/hr/?no=1` 과 `/hr?no=1` 을 다르게 취급하는 서버가 있다."""
        assert clean_url("https://x.com/hr/?no=1") == "https://x.com/hr/?no=1"


class TestIdentityUrl:
    """해시 계산용 정규화 — 사용자에게 보여주지 않으므로 더 공격적으로 줄인다."""

    def test_sorts_query_and_drops_trailing_slash(self):
        assert identity_url("https://X.com/j/1/?b=2&a=1") == "https://x.com/j/1?a=1&b=2"

    def test_keeps_fragment_so_spa_jobs_stay_distinct(self):
        a = identity_url("https://x.com/site#/job/1")
        b = identity_url("https://x.com/site#/job/2")
        assert a != b


class TestJobId:
    def test_tracking_param_does_not_create_a_new_job(self):
        """이게 깨지면 매 수집마다 같은 공고로 알림이 다시 간다."""
        base = "https://x.com/careers/job/9"
        assert (
            Job.make(company="c", title="T", url=base).job_id
            == Job.make(company="c", title="T", url=f"{base}?utm_source=push").job_id
        )

    def test_source_id_survives_title_edit(self):
        first = Job.make(company="c", title="DevOps Engineer",
                         url="https://x.com/j/1", source_id="JR1")
        edited = Job.make(company="c", title="DevOps Engineer (경력)",
                          url="https://x.com/j/1?v=2", source_id="JR1")
        assert first.job_id == edited.job_id

    def test_without_source_id_title_change_makes_new_id(self):
        first = Job.make(company="c", title="A", url="https://x.com/j/1")
        second = Job.make(company="c", title="B", url="https://x.com/j/1")
        assert first.job_id != second.job_id

    def test_same_title_different_company_differs(self):
        a = Job.make(company="samsung", title="T", url="https://x.com/j/1")
        b = Job.make(company="tesla", title="T", url="https://x.com/j/1")
        assert a.job_id != b.job_id

    def test_title_whitespace_is_collapsed(self):
        assert Job.make(company="c", title="  A   B ",
                        url="https://x.com/j/1").title == "A B"

    @pytest.mark.parametrize("bad", ["", "   "])
    def test_empty_title_rejected(self, bad):
        with pytest.raises(ValueError):
            Job.make(company="c", title=bad, url="https://x.com/j/1")

    def test_relative_url_rejected(self):
        with pytest.raises(ValueError):
            Job.make(company="c", title="T", url="/careers/job/1")

    def test_spa_hash_routes_are_distinct_jobs(self):
        """프래그먼트만 다른 공고들이 하나로 합쳐지면 안 된다."""
        base = "https://hire-r1.mokahr.com/social-recruitment/tesla/100000166"
        a = Job.make(company="tesla_kr", title="A", url=f"{base}#/job/aaa")
        b = Job.make(company="tesla_kr", title="A", url=f"{base}#/job/bbb")
        assert a.job_id != b.job_id


class TestRoles:
    def test_whitespace_is_collapsed_and_blanks_dropped(self):
        job = Job.make(company="c", title="T", url="https://x.com/1",
                       roles=("  SW개발 (데이터  엔지니어링) ", "", "   "))
        assert job.roles == ("SW개발 (데이터 엔지니어링)",)

    def test_absent_roles_are_not_written_to_dynamodb(self):
        assert "roles" not in Job.make(
            company="c", title="T", url="https://x.com/1").to_item()

    def test_present_roles_are_written_as_a_list(self):
        item = Job.make(company="c", title="T", url="https://x.com/1",
                        roles=("A", "B")).to_item()
        assert item["roles"] == ["A", "B"]


class TestNormalizeText:
    @pytest.mark.parametrize("raw", ["DevOps", "Dev Ops", "dev-ops", "ＤｅｖＯｐｓ", "Dev.Ops"])
    def test_variants_collapse(self, raw):
        assert normalize_text(raw) == "devops"


class TestToItem:
    def test_sets_ttl_and_first_seen(self):
        seen = datetime(2026, 1, 1, tzinfo=timezone.utc)
        item = Job.make(company="c", title="T", url="https://x.com/j/1").to_item(seen)
        assert item["first_seen_at"] == "2026-01-01T00:00:00+00:00"
        assert item["expires_at"] == int(seen.timestamp()) + 90 * 24 * 3600
        assert "posted_at" not in item  # None 은 DynamoDB 에 넣지 않는다
