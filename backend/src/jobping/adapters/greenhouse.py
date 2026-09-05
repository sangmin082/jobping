"""Greenhouse 채용 보드 공용 어댑터.

당근과 쿠팡이 이걸 쓴다. 보드 API가 공개돼 있고 인증도 필요 없어서, 회사를
붙이는 비용이 사실상 **보드 토큰 문자열 하나**다.

    class AcmeAdapter(GreenhouseAdapter):
        key, display_name = "acme", "Acme"
        board_token = "acme"

토큰은 회사 채용 페이지 주소나 지원 링크의 `boards.greenhouse.io/{token}` 에서
읽는다. 페이지네이션이 없다 — 한 번에 전부 준다.

주의: Greenhouse 응답에는 경력/신입 구분 필드가 없다. `matching.DEFAULT_EXCLUDES`
가 제목의 '인턴'/'intern'을 걸러주는 것이 유일한 방어다.
"""

from __future__ import annotations

import re

from ..companies import COUPANG, DAANGN
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false"


class GreenhouseAdapter(Adapter):
    board_token: str = ""

    #: 근무지가 이 정규식에 맞는 공고만 남긴다. 쿠팡처럼 전 세계 공고를
    #: 한 보드에 올리는 회사는 이걸로 국내만 추린다. None 이면 전부 통과.
    location_filter: re.Pattern | None = None

    def fetch(self, client: Client) -> list[Job]:
        if not self.board_token:
            raise AdapterError(f"{self.key}: board_token 이 설정되지 않았다")

        payload = client.get_json(API.format(token=self.board_token))
        rows = get_path(payload, "jobs")
        if not isinstance(rows, list):
            raise AdapterError(f"{self.key}: jobs 가 배열이 아님 — {type(rows).__name__}")

        jobs = []
        for row in rows:
            location = _location(row)
            if self.location_filter and not self.location_filter.search(location or ""):
                continue
            jobs.append(self._to_job(row, location))

        if rows and not jobs and self.location_filter:
            raise AdapterError(
                f"{self.key}: 공고 {len(rows)}건 중 근무지 필터를 통과한 게 하나도 없다. "
                "근무지 표기가 바뀌었을 수 있다."
            )
        return jobs

    def _to_job(self, row: dict, location: str | None) -> Job:
        job_id = row.get("id")
        title = row.get("title")
        if not job_id or not title:
            raise AdapterError(f"{self.key}: id/title 누락. 키: {sorted(row)[:15]}")
        return Job.make(
            company=self.key,
            # absolute_url 은 회사가 직접 설정한 공고 주소다. 우리가 조립한
            # boards.greenhouse.io 링크보다 이쪽이 사용자가 기대하는 화면이다.
            url=str(row.get("absolute_url") or
                    f"https://boards.greenhouse.io/{self.board_token}/jobs/{job_id}"),
            title=str(title),
            source_id=str(job_id),
            # first_published 가 최초 게시일이다. updated_at 은 공고를 손볼
            # 때마다 갱신되므로 게시일로 쓰면 안 된다.
            posted_at=parse_date(row.get("first_published")),
            location=location,
        )


def _location(row: dict) -> str | None:
    value = row.get("location")
    if isinstance(value, dict):
        return value.get("name") or None
    return str(value) if value else None


#: 한국 근무지로 인정할 표기들. 쿠팡 보드 기준으로 확인했다.
KOREA = re.compile(r"korea|seoul|서울|한국|대한민국", re.IGNORECASE)


class DaangnAdapter(GreenhouseAdapter):
    key, display_name = "daangn", "당근"
    site_url = "https://careers.daangn.com/jobs/"
    board_token = "daangn"
    companies = DAANGN
    verified = True


class CoupangAdapter(GreenhouseAdapter):
    key, display_name = "coupang", "쿠팡"
    site_url = "https://www.coupang.jobs/kr/jobs/"
    board_token = "coupang"
    # 보드에 전 세계 공고 689건이 올라온다. 국내만 추린다.
    location_filter = KOREA
    companies = COUPANG
    verified = True
