"""LG · 토스 · 라인 어댑터 테스트. 픽스처는 실제 응답을 줄인 것."""

import pytest

from jobping.adapters.base import AdapterError
from jobping.adapters.lg import LGAdapter
from jobping.adapters.line import LineAdapter
from jobping.adapters.toss import TossAdapter


class TestLG:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("lg_list.json")

    def test_splits_group_by_subsidiary(self, payload, fake_client):
        jobs = LGAdapter().fetch(fake_client(payload))
        assert jobs and all(j.company.startswith(("lg_", "hsad", "biztech", "hi_", "robostar", "dno"))
                            for j in jobs)

    def test_keeps_experienced_and_open_to_both(self, payload, fake_client):
        rows = payload["data"]["jobNoticeList"]
        for row, code in zip(rows, ["B", "D", "A", "C", "E", "B", "B", "B"]):
            row["careerTypeCode"] = code
            row["noticeStatus"] = "POSTING"
        jobs = LGAdapter().fetch(fake_client(payload))
        assert len(jobs) == 5

    def test_drops_unposted_drafts(self, payload, fake_client):
        """SAVE 는 임시저장이라 링크가 열리지 않는다."""
        for row in payload["data"]["jobNoticeList"]:
            row["careerTypeCode"] = "B"
            row["noticeStatus"] = "SAVE"
        assert LGAdapter().fetch(fake_client(payload)) == []

    def test_unknown_career_code_raises(self, payload, fake_client):
        for row in payload["data"]["jobNoticeList"]:
            row["careerTypeCode"] = "Z"
        with pytest.raises(AdapterError, match="careerTypeCode"):
            LGAdapter().fetch(fake_client(payload))

    def test_detail_url_uses_query_id(self, payload, fake_client):
        jobs = LGAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://careers.lg.com/apply/detail?id=")

    def test_sends_all_eight_filters(self, payload, fake_client):
        client = fake_client(payload)
        LGAdapter().fetch(client)
        assert set(client.calls[0]["json"]) == {
            "lnbSearch", "hashTagText", "recDate", "order",
            "careerList", "companyCodeList", "desireLocList", "jobGroupList",
        }

    def test_non_success_status_raises(self, fake_client):
        with pytest.raises(AdapterError, match="status"):
            LGAdapter().fetch(fake_client({"status": "E", "msg": "오류"}))


class TestToss:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("toss_job_groups.json")

    def test_one_job_per_group_not_per_variant(self, payload, fake_client):
        """같은 제목의 변형 넷을 알림 넷으로 보내면 스팸이다."""
        jobs = TossAdapter().fetch(fake_client(payload))
        assert len(jobs) == len(payload["success"])

    def test_subsidiary_comes_from_metadata(self, payload, fake_client):
        jobs = TossAdapter().fetch(fake_client(payload))
        assert all(j.company.startswith("toss") for j in jobs)
        assert "toss_unknown" not in {j.company for j in jobs}

    def test_all_subsidiaries_missing_raises(self, payload, fake_client):
        """메타데이터 질문 문구가 바뀌면 조용히 전부 unknown 이 된다. 그건 장애다."""
        for group in payload["success"]:
            group["primary_job"]["metadata"] = []
        with pytest.raises(AdapterError, match="자회사"):
            TossAdapter().fetch(fake_client(payload))

    def test_uses_company_configured_url(self, payload, fake_client):
        jobs = TossAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://toss.im/career/job-detail?gh_jid=")

    def test_does_not_store_job_description(self, payload, fake_client):
        payload["success"][0]["primary_job"]["metadata"].append(
            {"name": "Job Description을 작성해 주세요.", "value": "# 합류하게 될 팀에 대해"})
        jobs = TossAdapter().fetch(fake_client(payload))
        stored = " ".join(str(v) for v in jobs[0].to_item().values())
        assert "합류하게" not in stored

    def test_missing_primary_job_raises(self, fake_client):
        with pytest.raises(AdapterError, match="primary_job"):
            TossAdapter().fetch(fake_client({"success": [{"id": 1, "title": "x"}]}))


class TestLine:
    @pytest.fixture
    def payload(self, fixture_json):
        return fixture_json("line_page_data.json")

    def test_keeps_only_korean_published_open_postings(self, payload, fake_client):
        jobs = LineAdapter().fetch(fake_client(payload))
        assert jobs
        assert all("Bundang" in (j.location or "") or "Seoul" in (j.location or "")
                   for j in jobs)

    def test_drops_unpublished(self, payload, fake_client):
        for edge in payload["result"]["data"]["allStrapiJobs"]["edges"]:
            edge["node"]["publish"] = False
        assert LineAdapter().fetch(fake_client(payload)) == []

    def test_drops_expired_unless_until_filled(self, payload, fake_client):
        edges = payload["result"]["data"]["allStrapiJobs"]["edges"]
        for edge in edges:
            edge["node"]["publish"] = True
            edge["node"]["end_date"] = "2020-01-01T00:00:00.000Z"
            edge["node"]["until_filled"] = False
        assert LineAdapter().fetch(fake_client(payload)) == []
        for edge in edges:
            edge["node"]["until_filled"] = True
        assert LineAdapter().fetch(fake_client(payload))

    def test_drops_entry_level(self, payload, fake_client):
        edges = payload["result"]["data"]["allStrapiJobs"]["edges"]
        for edge in edges:
            edge["node"]["publish"] = True
            edge["node"]["end_date"] = None
            edge["node"]["employment_type"] = [{"id": 9, "name": "Full-time (Entry level)"}]
        assert LineAdapter().fetch(fake_client(payload)) == []

    def test_thai_postings_are_excluded(self, payload, fake_client):
        jobs = LineAdapter().fetch(fake_client(payload))
        assert not any("Bangkok" in (j.location or "") for j in jobs)

    def test_no_korean_city_at_all_raises(self, payload, fake_client):
        """도시 표기가 바뀌면 조용히 0건이 된다. 그건 장애다."""
        for edge in payload["result"]["data"]["allStrapiJobs"]["edges"]:
            edge["node"]["cities"] = [{"name": "Bangkok", "id": 1}]
        with pytest.raises(AdapterError, match="한국 도시"):
            LineAdapter().fetch(fake_client(payload))

    def test_detail_url_uses_strapi_id(self, payload, fake_client):
        jobs = LineAdapter().fetch(fake_client(payload))
        assert jobs[0].url.startswith("https://careers.linecorp.com/ko/jobs/")


class TestWoowahan:
    from jobping.adapters.woowahan import WoowahanAdapter as _A

    @pytest.fixture
    def client(self, fixture_json, fake_client):
        # 첫 호출은 코드표, 그다음이 목록이다.
        return fake_client(fixture_json("woowahan_codes.json"),
                           fixture_json("woowahan_recruits.json"))

    def test_resolves_codes_through_the_live_table(self, client):
        jobs = self._A().fetch(client)
        assert jobs
        assert client.calls[0]["url"].endswith("/common-item/all")
        assert all(j.employment_type in {"정규직", "기간제", None} for j in jobs)

    def test_detail_url_uses_recruit_number(self, client):
        jobs = self._A().fetch(client)
        assert jobs[0].url.startswith("https://career.woowahan.com/recruitment/R")

    def test_unknown_career_code_raises(self, fixture_json, fake_client):
        rec = fixture_json("woowahan_recruits.json")
        for row in rec["data"]["list"]:
            row["careerType"] = {"recruitItemCode": "BA003999"}
        with pytest.raises(AdapterError, match="코드표에 없다"):
            self._A().fetch(fake_client(fixture_json("woowahan_codes.json"), rec))

    def test_entry_level_is_dropped(self, fixture_json, fake_client):
        rec = fixture_json("woowahan_recruits.json")
        for row in rec["data"]["list"]:
            row["careerType"] = {"recruitItemCode": "BA003001"}  # 신입
        assert self._A().fetch(fake_client(fixture_json("woowahan_codes.json"), rec)) == []

    def test_intern_employment_is_dropped(self, fixture_json, fake_client):
        rec = fixture_json("woowahan_recruits.json")
        for row in rec["data"]["list"]:
            row["employmentType"] = {"recruitItemCode": "BA002003"}  # 인턴
        assert self._A().fetch(fake_client(fixture_json("woowahan_codes.json"), rec)) == []

    def test_empty_code_table_raises(self, fixture_json, fake_client):
        with pytest.raises(AdapterError, match="코드표"):
            self._A().fetch(fake_client({"code": "2000", "data": []}))

    def test_does_not_store_recruit_contents(self, fixture_json, fake_client):
        rec = fixture_json("woowahan_recruits.json")
        rec["data"]["list"][0]["recruitContents"] = "<p>담당 업무는 다음과 같습니다</p>"
        jobs = self._A().fetch(fake_client(fixture_json("woowahan_codes.json"), rec))
        assert "담당 업무" not in " ".join(str(v) for v in jobs[0].to_item().values())
