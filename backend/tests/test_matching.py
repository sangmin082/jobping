import pytest

from jobping.matching import (
    MAX_PUSH_PER_RUN,
    expand,
    match,
    match_all,
    notification_plan,
)
from jobping.models import Job

_n = 0


def job(title, company="samsung", department=None):
    global _n
    _n += 1
    return Job.make(company=company, title=title, department=department,
                    url=f"https://x.com/j/{_n}")


class TestSpacingVariants:
    @pytest.mark.parametrize("title", [
        "DevOps Engineer", "Dev Ops 엔지니어", "dev-ops 담당", "DEVOPS(경력)",
    ])
    def test_user_keyword_matches_regardless_of_spacing(self, title):
        assert match(job(title), ["DevOps"]) is not None


class TestSynonyms:
    @pytest.mark.parametrize("keyword,title", [
        ("인프라", "Infrastructure Engineer"),
        ("infrastructure", "인프라 엔지니어"),
        ("반도체", "Semiconductor Process Engineer"),
        ("백엔드", "Server Developer"),
        ("머신러닝", "ML Engineer"),
    ])
    def test_korean_keyword_finds_english_posting(self, keyword, title):
        """사용자는 한글로 넣고 공고는 영어로 뜬다. 이게 핵심 시나리오다."""
        hit = match(job(title), [keyword])
        assert hit is not None
        assert hit.keyword == keyword  # 알림 문구엔 사용자 표기를 그대로 쓴다

    def test_unknown_keyword_falls_back_to_itself(self):
        assert expand("쿠버네티스") == frozenset({"쿠버네티스"})


class TestExcludes:
    @pytest.mark.parametrize("title", ["DevOps 인턴", "DevOps Intern", "체험형 DevOps"])
    def test_excluded_even_when_keyword_matches(self, title):
        assert match(job(title), ["devops"]) is None

    def test_excludes_can_be_disabled(self):
        assert match(job("DevOps 인턴"), ["devops"], excludes=()) is not None


class TestDepartmentField:
    def test_department_is_searched_too(self):
        assert match(job("Staff Engineer", department="Infrastructure"), ["인프라"])


class TestCompanyFilter:
    def test_only_subscribed_companies(self):
        jobs = [job("DevOps", company="samsung"), job("DevOps", company="tesla")]
        hits = match_all(jobs, ["devops"], companies=["tesla"])
        assert [h.job.company for h in hits] == ["tesla"]

    def test_no_filter_means_all(self):
        jobs = [job("DevOps", company="samsung"), job("DevOps", company="tesla")]
        assert len(match_all(jobs, ["devops"])) == 2


class TestNotificationPlan:
    def test_empty(self):
        assert notification_plan([]) == []

    def test_individual_below_cap(self):
        hits = match_all([job("DevOps A"), job("DevOps B")], ["devops"])
        assert notification_plan(hits) == ["[samsung] DevOps A", "[samsung] DevOps B"]

    def test_collapses_above_cap(self):
        """상한이 없으면 채용 시즌에 알림 20개가 한 번에 터진다."""
        hits = match_all([job(f"DevOps {i}") for i in range(MAX_PUSH_PER_RUN + 1)],
                         ["devops"])
        plan = notification_plan(hits)
        assert len(plan) == 1
        assert f"{MAX_PUSH_PER_RUN + 1}건" in plan[0]
