"""어댑터 테스트.

픽스처는 실제 응답을 그대로 저장한 것이다(scripts/verify.py --save-fixture).
덕분에 사이트가 바뀌었을 때 "우리 코드 회귀"와 "사이트 구조 변경"을 구분할 수
있다. 픽스처로는 통과하는데 라이브에서 실패하면 사이트가 바뀐 것이다.
"""

import pytest

from jobping import registry
from jobping.adapters import NeedsDiscovery
from jobping.adapters.base import AdapterError, get_path, parse_date
from jobping.adapters.mokahr import MokaHRAdapter, TeslaKoreaAdapter
from jobping.adapters.samsung import SamsungAdapter
from jobping.adapters.skcareers import SKCareersAdapter


class TestRegistry:
    def test_metadata_is_complete(self):
        for key, adapter in registry.ADAPTERS.items():
            assert key and adapter.key == key
            assert adapter.display_name and adapter.site_url

    def test_verified_adapters_declare_companies(self):
        """회사를 하나도 안 내보내는 소스가 검증됨으로 표시되면 안 된다."""
        for adapter in registry.verified_adapters():
            assert adapter.companies, f"{adapter.key} 에 회사 목록이 없다"

    def test_app_company_keys_are_unique(self):
        keys = [c.key for c in registry.app_companies()]
        assert len(keys) == len(set(keys))

    def test_unknown_key_names_the_options(self):
        with pytest.raises(KeyError, match="samsung"):
            registry.get("nope")


#: 공고가 없는 정상 응답. 목록이 비어도 카운터 엘리먼트는 남는다.
SAMSUNG_EMPTY_PAGE = '<input class="divCnt" data-value="16" data-max="2">'


class TestSamsung:
    @pytest.fixture
    def jobs(self, fixture_text, fake_client):
        # 픽스처는 data-max="2" 라 2페이지까지 요청한다. 2페이지는 비워 둔다.
        client = fake_client(fixture_text("samsung_list.html"), SAMSUNG_EMPTY_PAGE)
        return SamsungAdapter().fetch(client)

    def test_parses_every_item(self, jobs):
        assert len(jobs) == 9

    def test_maps_subsidiary_to_company_key(self, jobs):
        """그룹 통합 포털이므로 계열사별로 갈라져야 한다."""
        assert {j.company for j in jobs} >= {"samsung_dx", "samsung_ds", "samsung_sdi"}

    def test_builds_permalink_from_share_button(self, jobs):
        # data-value 는 "22,878" 처럼 천 단위 구분자가 들어 있다.
        assert jobs[0].url == "https://www.samsungcareers.com/hr/?no=22878"
        assert jobs[0].source_id == "22878"

    def test_keeps_trailing_slash_in_path(self, jobs):
        """`/hr/?no=` 를 `/hr?no=` 로 바꾸면 안 된다. 서버가 다르게 취급한다."""
        assert "/hr/?no=" in jobs[0].url

    def test_collects_roles_from_flag_tags(self, jobs):
        """사용자가 찾는 키워드는 제목이 아니라 세부 직무에 있다."""
        roles = jobs[0].roles
        assert len(roles) == 12
        assert "[Big Data센터] SW개발 (데이터 엔지니어링)" in roles

    def test_parses_posting_start_date(self, jobs):
        assert jobs[0].posted_at is not None
        assert (jobs[0].posted_at.year, jobs[0].posted_at.month) == (2026, 8)

    def test_stops_at_last_page(self, fixture_text, fake_client):
        """data-max 가 총 페이지 수다. 그 이상은 요청하지 않는다."""
        html = fixture_text("samsung_list.html")  # data-max="2"
        client = fake_client(html, html)
        SamsungAdapter().fetch(client)
        assert len(client.calls) == 2

    def test_sends_experienced_filter(self, fixture_text, fake_client):
        client = fake_client(fixture_text("samsung_list.html"), SAMSUNG_EMPTY_PAGE)
        SamsungAdapter().fetch(client)
        assert client.calls[0]["data"]["strType"] == "B"

    def test_sends_every_required_param(self, fixture_text, fake_client):
        """하나라도 빠지면 서버가 500을 준다."""
        client = fake_client(fixture_text("samsung_list.html"), SAMSUNG_EMPTY_PAGE)
        SamsungAdapter().fetch(client)
        assert set(client.calls[0]["data"]) == {
            "currentPageNo", "intNo", "strVal", "strTxt", "strKey",
            "strCompany", "strType", "strOrderBy", "strEntity",
        }

    def test_empty_list_is_not_an_error(self, fake_client):
        client = fake_client('<input class="divCnt" data-value="0" data-max="0">')
        assert SamsungAdapter().fetch(client) == []

    def test_unrecognized_markup_raises(self, fake_client):
        with pytest.raises(AdapterError, match="바뀌었"):
            SamsungAdapter().fetch(fake_client("<div>서비스 점검 중입니다</div>"))

    def test_items_without_expected_structure_raise(self, fake_client):
        html = '<input class="divCnt" data-max="1"><li><span>공고</span></li>'
        with pytest.raises(AdapterError, match="파싱하지 못했다"):
            SamsungAdapter().fetch(fake_client(html))


class TestSKCareers:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("skcareers_list.json")

    def test_keeps_only_experienced_postings(self, payload, fake_client):
        jobs = SKCareersAdapter().fetch(fake_client(payload))
        titles = {j.title for j in jobs}
        assert all("Junior Talent" not in t for t in titles)

    def test_maps_subsidiary_to_company_key(self, payload, fake_client):
        jobs = SKCareersAdapter().fetch(fake_client(payload))
        assert all(j.company.startswith(("sk_", "tmap", "isc", "ige")) for j in jobs)

    def test_builds_detail_url(self, payload, fake_client):
        jobs = SKCareersAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://www.skcareers.com/Recruit/Detail/R")

    def test_splits_job_roles(self, payload, fake_client):
        """jobRole 은 '기획/운영 • 영업/B2C 영업,B2B 영업' 처럼 이어붙인 문자열이다."""
        jobs = SKCareersAdapter().fetch(fake_client(payload))
        assert all("•" not in role for j in jobs for role in j.roles)

    def test_sends_every_required_param(self, payload, fake_client):
        """하나라도 빠지면 ASP.NET 이 404 페이지를 준다 — 에러가 아니라 404다."""
        client = fake_client(payload)
        SKCareersAdapter().fetch(client)
        sent = client.calls[0]["data"]
        assert set(sent) == {"sort", "searchText", "corpCode", "jobRole",
                             "recruitType", "workingType", "workingRegion"}
        assert sent["sort"] == "0" and sent["jobRole"] == "0"

    @pytest.mark.parametrize("recruit_type", ["Experienced", "경력"])
    def test_accepts_both_locales(self, payload, fake_client, recruit_type):
        """recruitType 표기는 Accept-Language 에 따라 영어/한국어로 바뀐다."""
        for row in payload["list"]:
            row["recruitType"] = recruit_type
        jobs = SKCareersAdapter().fetch(fake_client(payload))
        assert len(jobs) == len(payload["list"])

    def test_unknown_recruit_type_raises_instead_of_filtering_everything(
        self, payload, fake_client
    ):
        """조용히 0건이 되면 '채용이 없다'와 구분되지 않는다.

        사용자는 앱이 고장난 줄 모르고 오지 않는 알림을 기다리게 된다.
        """
        for row in payload["list"]:
            row["recruitType"] = "Erfahren"
        with pytest.raises(AdapterError, match="recruitType"):
            SKCareersAdapter().fetch(fake_client(payload))

    def test_total_count_mismatch_raises(self, payload, fake_client):
        """페이지네이션이 없다는 전제가 깨지면 조용히 일부만 수집하게 된다."""
        payload["totalCount"] = 999
        with pytest.raises(AdapterError, match="totalCount"):
            SKCareersAdapter().fetch(fake_client(payload))

    def test_failure_flag_raises(self, fake_client):
        with pytest.raises(AdapterError, match="success"):
            SKCareersAdapter().fetch(fake_client({"success": False}))


class TestMokaHR:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("tesla_kr_jobs.json")

    def test_parses_tesla_korea_postings(self, payload, fake_client):
        jobs = TeslaKoreaAdapter().fetch(fake_client(payload))
        assert len(jobs) == 4
        assert all(j.company == "tesla_kr" for j in jobs)

    def test_keeps_hash_route_in_url(self, payload, fake_client):
        """해시 라우팅 SPA다. 프래그먼트를 지우면 전부 홈으로 간다."""
        jobs = TeslaKoreaAdapter().fetch(fake_client(payload))
        assert "#/job/" in jobs[0].url
        assert len({j.url for j in jobs}) == len(jobs)

    def test_reads_location_from_custom_field(self, payload, fake_client):
        """근무지가 고정 필드가 아니라 회사가 만든 커스텀 필드에 들어 있다."""
        jobs = TeslaKoreaAdapter().fetch(fake_client(payload))
        assert jobs[0].location == "Seoul, Korea"

    def test_parses_opened_at(self, payload, fake_client):
        jobs = TeslaKoreaAdapter().fetch(fake_client(payload))
        assert jobs[0].posted_at is not None

    def test_error_code_raises(self, fake_client):
        with pytest.raises(AdapterError, match="code="):
            TeslaKoreaAdapter().fetch(fake_client({"code": 1001, "data": {}}))

    def test_unconfigured_org_is_an_error(self, fake_client):
        class Bare(MokaHRAdapter):
            key = "bare"
        with pytest.raises(AdapterError, match="org_id"):
            Bare().fetch(fake_client({}))

    def test_dedupes_across_pages(self, payload, fake_client):
        """offset 페이징 중 목록이 갱신되면 같은 공고가 두 페이지에 걸쳐 나온다."""
        from jobping.adapters.mokahr import PAGE_SIZE
        rows = payload["data"]["jobs"]
        full = {"code": 0, "data": {"jobs": (rows * PAGE_SIZE)[:PAGE_SIZE]}}
        client = fake_client(full, payload)
        jobs = TeslaKoreaAdapter().fetch(client)
        assert len(client.calls) == 2
        assert len(jobs) == len(rows)


class TestUnimplementedAdapters:
    @pytest.mark.parametrize("key", ["hyundai", "kia", "lge", "naver", "kakao"])
    def test_raise_needs_discovery_not_generic_error(self, key, fake_client):
        """'아직 구현 안 됨'과 '망가짐'을 운영 알림에서 구분하기 위한 계약."""
        with pytest.raises(NeedsDiscovery):
            registry.get(key).fetch(fake_client())

    def test_are_hidden_from_the_app(self):
        hidden = {"hyundai", "kia", "lge", "naver", "kakao"}
        assert not hidden & {a.key for a in registry.verified_adapters()}


class TestGetPath:
    def test_walks_nested_dicts_and_lists(self):
        assert get_path({"a": {"b": [{"c": 1}]}}, "a.b.0.c") == 1

    def test_empty_path_is_root(self):
        assert get_path([1, 2], "") == [1, 2]

    def test_missing_key_lists_what_was_there(self):
        with pytest.raises(AdapterError, match="alpha"):
            get_path({"alpha": 1}, "beta")


class TestParseDate:
    @pytest.mark.parametrize("value,year", [
        ("2026-08-01", 2026),
        ("2026-06-17T23:00", 2026),
        ("2026-08-01T09:30:00Z", 2026),
        ("2026.08.20", 2026),
        (1767225600, 2026),
        (1767225600000, 2026),
    ])
    def test_accepts_shapes_seen_in_the_wild(self, value, year):
        assert parse_date(value).year == year

    @pytest.mark.parametrize("value", [None, "", "곧 마감", "August 24, 2026(Mon)"])
    def test_unparseable_returns_none_instead_of_raising(self, value):
        # 게시일은 부가 정보다. 신규 판정은 first_seen_at 이 한다.
        assert parse_date(value) is None


class TestMokaHRCommitment:
    def test_chinese_employment_type_is_translated(self, fixture_json, fake_client):
        """MokaHR 은 중국 ATS라 고용형태를 중국어로 준다."""
        jobs = TeslaKoreaAdapter().fetch(fake_client(fixture_json("tesla_kr_jobs.json")))
        assert jobs[0].employment_type == "정규직"

    def test_unknown_value_is_kept_verbatim(self, fake_client):
        payload = {"code": 0, "data": {"jobs": [
            {"id": "x", "title": "T", "commitment": "顾问"},
        ]}}
        jobs = TeslaKoreaAdapter().fetch(fake_client(payload))
        assert jobs[0].employment_type == "顾问"
