import pytest

from jobping import registry
from jobping.adapters import NeedsDiscovery
from jobping.adapters.base import AdapterError, JsonListSpec, get_path, parse_iso
from jobping.adapters.tesla import TeslaAdapter
from jobping.adapters.workday import WorkdayAdapter


class TestRegistry:
    def test_keys_are_unique_and_nonempty(self):
        for key, adapter in registry.ADAPTERS.items():
            assert key and adapter.key == key
            assert adapter.display_name and adapter.site_url

    def test_unverified_adapters_are_hidden_from_the_app(self):
        for adapter in registry.verified_adapters():
            assert adapter.verified

    def test_unknown_key_names_the_options(self):
        with pytest.raises(KeyError, match="tesla"):
            registry.get("nope")


class TestTesla:
    def test_resolves_id_references_to_names(self, load_fixture, fake_client):
        jobs = TeslaAdapter().fetch(fake_client(load_fixture("tesla_state.json")))
        assert len(jobs) == 4
        first = jobs[0]
        assert first.title == "Senior DevOps Engineer"
        assert first.location == "Palo Alto, California"
        assert first.department == "Engineering & Information Technology"
        assert first.employment_type == "Full-time"
        assert first.url == "https://www.tesla.com/careers/search/job/240001"

    def test_accepts_long_form_keys(self, load_fixture, fake_client):
        """테슬라가 축약 키를 풀네임으로 바꿔도 죽지 않아야 한다."""
        jobs = TeslaAdapter().fetch(fake_client(load_fixture("tesla_state.json")))
        assert jobs[3].title == "Production Associate"
        assert jobs[3].location == "Seoul, South Korea"

    def test_missing_listings_reports_structure_change(self, fake_client):
        with pytest.raises(AdapterError, match="listings"):
            TeslaAdapter().fetch(fake_client({"departments": []}))

    def test_job_ids_are_unique(self, load_fixture, fake_client):
        jobs = TeslaAdapter().fetch(fake_client(load_fixture("tesla_state.json")))
        assert len({j.job_id for j in jobs}) == len(jobs)


class _DemoWorkday(WorkdayAdapter):
    key, display_name = "demo", "Demo"
    tenant, wd_host, site = "demo", "wd3", "Demo_Careers"


class TestWorkday:
    def test_builds_absolute_urls(self, load_fixture, fake_client):
        jobs = _DemoWorkday().fetch(fake_client(load_fixture("workday_jobs.json")))
        assert len(jobs) == 2
        assert jobs[0].url == (
            "https://demo.wd3.myworkdayjobs.com/Demo_Careers"
            "/job/Seoul/Staff-Infrastructure-Engineer_JR-1001"
        )
        assert jobs[0].source_id == "JR-1001"
        assert jobs[0].posted_at is None  # "Posted 3 Days Ago" 는 날짜가 아니다

    def test_stops_on_short_page(self, load_fixture, fake_client):
        client = fake_client(load_fixture("workday_jobs.json"))
        _DemoWorkday().fetch(client)
        assert len(client.calls) == 1  # 2건 < PAGE_SIZE 이므로 다음 페이지를 안 부른다

    def test_dedupes_across_pages(self, load_fixture, fake_client):
        """offset 페이징 중 목록이 갱신되면 같은 공고가 두 번 나온다."""
        page = load_fixture("workday_jobs.json")
        full = {"jobPostings": page["jobPostings"] * 10}  # 20건 = PAGE_SIZE
        client = fake_client(full, page)
        jobs = _DemoWorkday().fetch(client)
        assert len(client.calls) == 2
        assert len(jobs) == 2

    def test_unconfigured_tenant_is_an_error(self, fake_client):
        class Bare(WorkdayAdapter):
            key = "bare"
        with pytest.raises(AdapterError, match="tenant"):
            Bare().fetch(fake_client({}))


class TestUnconfiguredAdapters:
    @pytest.mark.parametrize("key", ["samsung", "skhynix", "hyundai", "naver"])
    def test_raise_needs_discovery_not_generic_error(self, key, fake_client):
        """'아직 설정 안 됨'과 '망가짐'을 운영 알림에서 구분하기 위한 계약."""
        with pytest.raises(NeedsDiscovery):
            registry.get(key).fetch(fake_client())


class TestGetPath:
    def test_walks_nested_dicts_and_lists(self):
        assert get_path({"a": {"b": [{"c": 1}]}}, "a.b.0.c") == 1

    def test_empty_path_is_root(self):
        assert get_path([1, 2], "") == [1, 2]

    def test_missing_key_lists_what_was_there(self):
        with pytest.raises(AdapterError, match="alpha"):
            get_path({"alpha": 1}, "beta")


class TestJsonListSpec:
    def test_maps_rows_to_jobs(self):
        spec = JsonListSpec(
            company="acme",
            list_path="data.list",
            title_key="jobTitle",
            id_key="jobId",
            location_key="workPlace",
            posted_at_key="regDate",
            url=lambda row: f"https://acme.com/jobs/{row['jobId']}",
        )
        jobs = spec.parse({"data": {"list": [
            {"jobId": "A1", "jobTitle": "DevOps", "workPlace": "수원",
             "regDate": "2026-08-01"},
        ]}})
        assert jobs[0].source_id == "A1"
        assert jobs[0].location == "수원"
        assert jobs[0].posted_at.year == 2026

    def test_missing_title_key_names_the_available_keys(self):
        spec = JsonListSpec(company="acme", list_path="", title_key="jobTitle",
                            url=lambda row: "https://acme.com/1")
        with pytest.raises(AdapterError, match="jobId"):
            spec.parse([{"jobId": "A1"}])


class TestParseIso:
    @pytest.mark.parametrize("value,year", [
        ("2026-08-01", 2026),
        ("2026-08-01T09:30:00Z", 2026),
        ("2026/08/01", 2026),
        (1767225600, 2026),
        (1767225600000, 2026),
    ])
    def test_accepts_common_shapes(self, value, year):
        assert parse_iso(value).year == year

    @pytest.mark.parametrize("value", [None, "", "곧 마감"])
    def test_unparseable_returns_none_instead_of_raising(self, value):
        # 게시일은 부가 정보다. 이것 때문에 수집 전체가 실패하면 안 된다.
        assert parse_iso(value) is None
