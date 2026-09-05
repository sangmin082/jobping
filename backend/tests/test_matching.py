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


def job(title, company="samsung_dx", department=None, roles=()):
    global _n
    _n += 1
    return Job.make(company=company, title=title, department=department,
                    roles=roles, url=f"https://x.com/j/{_n}")


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


class TestRoles:
    """실제 데이터에서 매칭의 대부분은 세부 직무에서 나온다.

    삼성 공고 제목은 "R&D분야 경력사원 채용(DX부문)" 처럼 뭉뚱그려져 있고,
    "데이터 엔지니어링"은 그 안에 묶인 직무 태그에만 있다.
    """

    def test_role_tag_matches_when_title_does_not(self):
        posting = job(
            "R&D분야 외국인 경력사원 채용(DX부문)",
            roles=("[Big Data센터] SW개발 (데이터 엔지니어링)",
                   "[생산기술연구소] 기구개발 (학습기반 로봇조작 AI)"),
        )
        assert match(posting, ["데이터 엔지니어링"]) is not None
        assert match(posting, ["데이터 엔지니어링"]).keyword == "데이터 엔지니어링"

    def test_same_posting_without_roles_does_not_match(self):
        assert match(job("R&D분야 외국인 경력사원 채용(DX부문)"),
                     ["데이터 엔지니어링"]) is None

    def test_synonyms_apply_to_roles(self):
        posting = job("DC 설비 운용 전문가 영입",
                      roles=("Infra/Infra 운용/관리/최적화",))
        assert match(posting, ["인프라"]) is not None


class TestCompanyFilter:
    def test_only_subscribed_companies(self):
        """그룹이 아니라 계열사 단위로 걸러야 한다.

        반도체 공고를 원하는 사람에게 삼성생명 공고를 보내면 안 된다.
        """
        jobs = [job("DevOps", company="samsung_ds"),
                job("DevOps", company="samsung_life")]
        hits = match_all(jobs, ["devops"], companies=["samsung_ds"])
        assert [h.job.company for h in hits] == ["samsung_ds"]

    def test_no_filter_means_all(self):
        jobs = [job("DevOps", company="samsung_ds"), job("DevOps", company="tesla_kr")]
        assert len(match_all(jobs, ["devops"])) == 2


class TestNotificationPlan:
    def test_empty(self):
        assert notification_plan([]) == []

    def test_uses_human_readable_company_names(self):
        """알림에 'samsung_dx' 가 뜨면 안 된다."""
        hits = match_all([job("DevOps A"), job("DevOps B")], ["devops"])
        assert notification_plan(hits) == [
            "[삼성전자 DX부문] DevOps A", "[삼성전자 DX부문] DevOps B",
        ]

    def test_unregistered_company_falls_back_to_its_key(self):
        hits = match_all([job("DevOps", company="sk신규회사")], ["devops"])
        assert notification_plan(hits) == ["[sk신규회사] DevOps"]

    def test_collapses_above_cap(self):
        """상한이 없으면 채용 시즌에 알림 20개가 한 번에 터진다."""
        hits = match_all([job(f"DevOps {i}") for i in range(MAX_PUSH_PER_RUN + 1)],
                         ["devops"])
        plan = notification_plan(hits)
        assert len(plan) == 1
        assert f"{MAX_PUSH_PER_RUN + 1}건" in plan[0]


class TestAsciiBoundaries:
    """영문 키워드는 알파벳/숫자 경계를 지켜야 한다.

    한국어는 "반도체공정엔지니어"처럼 붙여 쓰므로 부분문자열 매칭이 필요하지만,
    영어에 같은 규칙을 쓰면 엉뚱하게 걸린다. 전부 라이브 데이터에서 나온 것들이다.
    """

    @pytest.mark.parametrize("title", [
        "Sr. Employee Relation Specialist",
        "Senior Employee Experience Lead",
    ])
    def test_short_acronym_does_not_cross_word_boundaries(self, title):
        assert match(job(title), ["SRE"]) is None

    @pytest.mark.parametrize("title", [
        "Site Reliability Engineer (SRE)",
        "SRE 엔지니어",
        "Platform SRE, Seoul",
    ])
    def test_short_acronym_still_matches_as_a_word(self, title):
        assert match(job(title), ["SRE"]) is not None

    def test_ml_does_not_match_html(self):
        assert match(job("HTML 퍼블리셔"), ["ML"]) is None

    def test_ml_synonym_still_reaches_ml_engineer(self):
        assert match(job("ML Engineer"), ["머신러닝"]) is not None

    def test_long_keywords_keep_separator_insensitive_matching(self):
        """긴 키워드는 기존대로 붙여쓰기/띄어쓰기를 무시한다."""
        assert match(job("Dev-Ops 엔지니어"), ["DevOps"]) is not None

    def test_korean_keywords_are_unaffected(self):
        assert match(job("데이터 품질 관리"), ["품질"]) is not None

    @pytest.mark.parametrize("title", [
        "Internal Tools Engineer", "International Sales Manager", "Internal Audit Lead",
    ])
    def test_intern_exclusion_does_not_swallow_internal_postings(self, title):
        """제외어 오작동은 오탐보다 나쁘다.

        오탐은 알림 하나로 끝나지만, 잘못된 제외는 공고가 조용히 사라져서
        아무도 눈치채지 못한다.
        """
        assert match(job(title), ["engineer", "sales", "audit"]) is not None

    def test_intern_exclusion_still_catches_real_internships(self):
        assert match(job("Software Engineering Internship"), ["engineer"]) is None

    @pytest.mark.parametrize("keyword,title", [
        ("engineer", "Software Engineering Manager"),
        ("develop", "Backend Developers"),
        ("manage", "Product Management Lead"),
    ])
    def test_common_english_suffixes_are_allowed(self, keyword, title):
        """경계만 엄격히 걸면 'engineer' 가 'Engineering' 을 놓친다."""
        assert match(job(title), [keyword]) is not None

    def test_ascii_keyword_matches_inside_a_korean_compound(self):
        """한글은 파이썬 정규식에서 단어문자라 \\b 로는 못 잡는다."""
        assert match(job("AI개발자 채용"), ["AI"]) is not None
