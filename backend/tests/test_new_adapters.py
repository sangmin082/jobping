"""이번에 추가된 소스들의 테스트.

픽스처는 실제 응답을 그대로 줄인 것이다. 픽스처는 통과하는데 라이브가
실패하면 사이트가 바뀐 것이고, 둘 다 실패하면 우리 코드가 깨진 것이다.
"""

import re

import pytest

from jobping.adapters.base import AdapterError
from jobping.adapters.greenhouse import (
    KOREA,
    CoupangAdapter,
    DaangnAdapter,
    GreenhouseAdapter,
)
from jobping.adapters.hmg import HyundaiAdapter, KiaAdapter
from jobping.adapters.kakao import KakaoAdapter
from jobping.adapters.naver import NaverAdapter
from jobping.adapters.workday import WorkdayAdapter, YanoljaAdapter


class TestNaver:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("naver_list.json")

    def test_uses_the_detail_link_the_api_provides(self, payload, fake_client):
        """직접 조립하지 않는다. 응답이 정확한 주소를 준다."""
        jobs = NaverAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://recruit.navercorp.com/rcrt/view.do?annoId=")

    def test_splits_group_by_subsidiary(self, payload, fake_client):
        jobs = NaverAdapter().fetch(fake_client(payload))
        assert {j.company for j in jobs} <= {
            "naver", "naver_webtoon", "naver_cloud", "naver_labs", "snow"}

    def test_keeps_experienced_and_open_to_both(self, payload, fake_client):
        for row, ent in zip(payload["list"], ["경력", "무관", "신입", "인턴", "경력"]):
            row["entTypeCdNm"] = ent
        jobs = NaverAdapter().fetch(fake_client(payload))
        assert len(jobs) == 3

    def test_unknown_entry_type_raises(self, payload, fake_client):
        """조용히 0건이 되면 '채용이 없다'와 구분되지 않는다."""
        for row in payload["list"]:
            row["entTypeCdNm"] = "Experienced"
        with pytest.raises(AdapterError, match="entTypeCdNm"):
            NaverAdapter().fetch(fake_client(payload))

    def test_parses_yyyymmdd_start_date(self, payload, fake_client):
        jobs = NaverAdapter().fetch(fake_client(payload))
        assert jobs[0].posted_at is not None
        assert jobs[0].posted_at.year == 2026

    def test_collects_job_family_and_role(self, payload, fake_client):
        jobs = NaverAdapter().fetch(fake_client(payload))
        assert jobs[0].roles  # classCdNm + subJobCdNm

    def test_stops_when_total_reached(self, payload, fake_client):
        client = fake_client(payload)
        NaverAdapter().fetch(client)
        assert len(client.calls) == 1

    def test_sends_get_not_post(self, payload, fake_client):
        """POST 로 부르면 200 과 함께 '접근권한이 없습니다' HTML 이 온다."""
        client = fake_client(payload)
        NaverAdapter().fetch(client)
        assert client.calls[0]["method"] == "GET"


class TestKakao:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("kakao_list.json")

    def test_walks_every_job_type(self, payload, fake_client):
        """파라미터 없이 부르면 기술 직군만 온다. 직군을 순회해야 전부 모인다."""
        client = fake_client(payload, payload, payload)  # 탐색 1 + 직군 2
        KakaoAdapter().fetch(client)
        parts = [c["params"].get("part") for c in client.calls]
        assert parts[0] is None
        assert set(parts[1:]) == {"TECHNOLOGY", "DESIGN"}

    def test_dedupes_across_job_types(self, payload, fake_client):
        """같은 공고가 여러 직군에 잡혀도 한 번만 남아야 한다."""
        client = fake_client(payload, payload, payload)
        jobs = KakaoAdapter().fetch(client)
        assert len(jobs) == len(payload["jobList"])

    def test_builds_job_url_from_real_id(self, payload, fake_client):
        jobs = KakaoAdapter().fetch(fake_client(payload, payload, payload))
        assert jobs[0].url == "https://careers.kakao.com/jobs/P-14472"

    def test_skill_tags_become_roles(self, payload, fake_client):
        """기술 태그가 제목에 없는 키워드를 잡아준다."""
        jobs = KakaoAdapter().fetch(fake_client(payload, payload, payload))
        assert any("Algorithm/ML" in j.roles for j in jobs)

    def test_does_not_store_the_posting_body(self, payload, fake_client):
        """본문 저장 금지 — docs/PLAN.md 4절 (저작권 / 심사 4.5.2)."""
        jobs = KakaoAdapter().fetch(fake_client(payload, payload, payload))
        stored = " ".join(str(v) for j in jobs for v in j.to_item().values())
        assert "우리 조직은" not in stored
        assert "우대사항" not in stored

    def test_closed_postings_are_dropped(self, payload, fake_client):
        for row in payload["jobList"]:
            row["closeFlag"] = True
        assert KakaoAdapter().fetch(fake_client(payload, payload, payload)) == []

    def test_missing_job_type_list_raises(self, payload, fake_client):
        """직군 목록이 없으면 기술 직군만 조용히 모으게 된다."""
        payload["jobTypeCountDtoList"] = []
        with pytest.raises(AdapterError, match="jobTypeCountDtoList"):
            KakaoAdapter().fetch(fake_client(payload))


class TestGreenhouse:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("greenhouse_jobs.json")

    def test_prefers_the_company_configured_url(self, payload, fake_client):
        jobs = DaangnAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://about.daangn.com")

    def test_falls_back_to_a_board_url(self, payload, fake_client):
        for row in payload["jobs"]:
            row["absolute_url"] = None
        jobs = DaangnAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://boards.greenhouse.io/daangn/jobs/")

    def test_uses_first_published_not_updated_at(self, payload, fake_client):
        """updated_at 은 공고를 손볼 때마다 갱신된다. 게시일이 아니다."""
        jobs = DaangnAdapter().fetch(fake_client(payload))
        posted = {j.posted_at for j in jobs if j.posted_at}
        assert posted and all(p.year >= 2020 for p in posted)

    def test_coupang_keeps_only_korean_locations(self, payload, fake_client):
        payload["jobs"][0]["location"] = {"name": "Seoul, South Korea"}
        payload["jobs"][1]["location"] = {"name": "Taipei, Taiwan"}
        payload["jobs"][2]["location"] = {"name": "Mountain View, USA"}
        jobs = CoupangAdapter().fetch(fake_client(payload))
        assert all("Korea" in (j.location or "") or "SEOUL" in (j.location or "").upper()
                   for j in jobs)
        assert not any("Taiwan" in (j.location or "") for j in jobs)

    @pytest.mark.parametrize("name", ["Seoul, South Korea", "South Korea", "서울", "SEOUL"])
    def test_korea_pattern_matches_real_spellings(self, name):
        assert KOREA.search(name)

    def test_filtering_everything_out_raises(self, payload, fake_client):
        """근무지 표기가 바뀌면 조용히 0건이 된다. 그건 장애다."""
        for row in payload["jobs"]:
            row["location"] = {"name": "Mars"}
        with pytest.raises(AdapterError, match="근무지"):
            CoupangAdapter().fetch(fake_client(payload))

    def test_unconfigured_token_is_an_error(self, fake_client):
        class Bare(GreenhouseAdapter):
            key = "bare"
        with pytest.raises(AdapterError, match="board_token"):
            Bare().fetch(fake_client({}))


class TestHMG:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("hmg_list.json")

    def test_parses_hyundai_postings(self, payload, fake_client):
        jobs = HyundaiAdapter().fetch(fake_client(payload))
        assert jobs and all(j.company == "hyundai" for j in jobs)

    def test_identifies_a_posting_by_three_fields(self, payload, fake_client):
        """공고는 (연도, 유형, 일련번호) 조합으로만 식별된다."""
        jobs = HyundaiAdapter().fetch(fake_client(payload))
        assert re.fullmatch(r"\d{4}-\w+-\d+", jobs[0].source_id)
        assert len({j.source_id for j in jobs}) == len(jobs)

    def test_detail_url_carries_all_three(self, payload, fake_client):
        jobs = HyundaiAdapter().fetch(fake_client(payload))
        assert all(k in jobs[0].url for k in ("recuYy=", "recuType=", "recuCls="))

    def test_drops_new_graduate_and_intern_channels(self, payload, fake_client):
        for row, channel in zip(payload["data"]["list"], ["경력", "신입", "인턴", "계약직", "경력"]):
            row["channelCodeNm"] = channel
        jobs = HyundaiAdapter().fetch(fake_client(payload))
        assert len(jobs) == 3

    def test_unknown_channel_is_kept(self, payload, fake_client):
        """모르는 유형을 조용히 버리면 새 채널이 생겼을 때 공고를 놓친다."""
        for row in payload["data"]["list"]:
            row["channelCodeNm"] = "신규채널"
        assert len(HyundaiAdapter().fetch(fake_client(payload))) == 5

    def test_generic_category_is_not_a_role(self, payload, fake_client):
        """'기타'는 직무가 아니다. 매칭에 넣으면 잡음만 는다."""
        for row in payload["data"]["list"]:
            row["secCodeNm"] = "기타"
            row["fldCodeNm"] = "Data Engineering"
        jobs = HyundaiAdapter().fetch(fake_client(payload))
        assert jobs[0].roles == ("Data Engineering",)

    def test_campaign_hashtag_is_not_a_role(self, payload, fake_client):
        """hashTag 는 "9월 신입채용" 같은 캠페인 라벨이다. 직무가 아니다.

        넣으면 키워드 '경력'이 전부에 걸리고, 경력 공고의 roles 에 '신입채용'
        이 섞여 들어간다.
        """
        jobs = HyundaiAdapter().fetch(fake_client(payload))
        assert not any("채용" in r for j in jobs for r in j.roles)

    def test_sends_the_params_this_site_accepts(self, payload, fake_client):
        """현대차와 기아가 받는 파라미터 집합이 다르다. 없는 걸 보내면 400이다."""
        client = fake_client(payload)
        HyundaiAdapter().fetch(client)
        sent = set(client.calls[0]["params"])
        assert "jdSec" in sent and "searchOccupList" in sent
        assert client.calls[0]["params"]["hgrCd"] == "1"

    def test_kia_sends_its_own_narrower_param_set(self, payload, fake_client):
        client = fake_client(payload)
        KiaAdapter().fetch(client)
        sent = set(client.calls[0]["params"])
        assert "jdSec" not in sent
        assert "searchSecList" in sent
        assert client.calls[0]["params"]["hgrCd"] == "2"

    def test_kia_sends_the_null_token_headers(self, payload, fake_client):
        """기아 서버는 X-HKMC-TOKEN 헤더가 없으면 400, 문자열 "null" 이면 통과다.

        브라우저의 axios 가 로그인 전 sessionStorage 값(null)을 그대로 실어
        보내는 걸 서버가 기대하고 있다. 빈 문자열도 400 이다.
        """
        client = fake_client(payload)
        KiaAdapter().fetch(client)
        headers = client.calls[0]["headers"]
        assert headers["X-HKMC-TOKEN"] == "null"
        assert headers["X-HKMC-EMP-TOKEN"] == "null"

    def test_missing_identifier_raises(self, payload, fake_client):
        payload["data"]["list"][0].pop("recuCls")
        with pytest.raises(AdapterError, match="recuCls"):
            HyundaiAdapter().fetch(fake_client(payload))


class TestWorkday:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("workday_jobs.json")

    def test_builds_absolute_urls_with_locale(self, payload, fake_client):
        jobs = YanoljaAdapter().fetch(fake_client(payload))
        assert jobs[0].url == (
            "https://yanolja.wd102.myworkdayjobs.com/ko-KR/External_Yanolja"
            "/job/Seoul/Staff-Infrastructure-Engineer_JR-1001"
        )
        assert jobs[0].source_id == "JR-1001"

    def test_relative_posted_on_is_not_a_date(self, payload, fake_client):
        """"Posted 3 Days Ago" 는 날짜로 되돌릴 수 없다."""
        jobs = YanoljaAdapter().fetch(fake_client(payload))
        assert all(j.posted_at is None for j in jobs)

    def test_empty_board_is_not_an_error(self, fake_client):
        """야놀자는 지금 공고가 0건이다. 잘못된 site 는 404 라서 구분된다."""
        assert YanoljaAdapter().fetch(fake_client({"total": 0, "jobPostings": []})) == []

    def test_dedupes_across_pages(self, payload, fake_client):
        from jobping.adapters.workday import PAGE_SIZE
        rows = payload["jobPostings"]
        full = {"jobPostings": (rows * PAGE_SIZE)[:PAGE_SIZE]}
        client = fake_client(full, payload)
        jobs = YanoljaAdapter().fetch(client)
        assert len(client.calls) == 2
        assert len(jobs) == len(rows)

    def test_unconfigured_tenant_is_an_error(self, fake_client):
        class Bare(WorkdayAdapter):
            key = "bare"
        with pytest.raises(AdapterError, match="tenant"):
            Bare().fetch(fake_client({}))
