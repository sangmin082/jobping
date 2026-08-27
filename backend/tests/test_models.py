from datetime import datetime, timezone

import pytest

from jobping.models import Job, canonical_url, normalize_text


class TestCanonicalUrl:
    def test_strips_tracking_params_and_fragment(self):
        assert canonical_url(
            "https://Www.Tesla.com/careers/job/123/?utm_source=x&gclid=y&lang=ko#apply"
        ) == "https://www.tesla.com/careers/job/123?lang=ko"

    def test_sorts_remaining_query(self):
        a = canonical_url("https://x.com/j?b=2&a=1")
        b = canonical_url("https://x.com/j?a=1&b=2")
        assert a == b


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
