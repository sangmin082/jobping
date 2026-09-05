"""카카오 — careers.kakao.com.

`GET /public/api/job-list`. 파라미터 없이 부르면 **기술 직군만** 돌아온다
(기본값이 TECHNOLOGY다). 다행히 응답의 `jobTypeCountDtoList`가 존재하는 직군과
각 건수를 알려주므로, 그걸 읽어서 직군별로 순회한다. 카카오가 직군을 추가해도
자동으로 따라간다.

이 API는 공고 **본문 전문**(`introduction`, `workContentDesc`, `qualification`)
까지 내려준다. 저장하지 않는다 — docs/PLAN.md 4절.
"""

from __future__ import annotations

from ..companies import KAKAO, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

BASE = "https://careers.kakao.com"
LIST_URL = f"{BASE}/public/api/job-list"
JOB_URL = f"{BASE}/jobs/{{real_id}}"

MAX_PAGES = 30


class KakaoAdapter(Adapter):
    key = "kakao"
    display_name = "카카오"
    site_url = f"{BASE}/jobs"
    companies = KAKAO
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        first = self._page(client, part=None, page=1)
        parts = [
            str(row["jobType"])
            for row in first.get("jobTypeCountDtoList") or []
            if isinstance(row, dict) and row.get("jobType")
        ]
        if not parts:
            raise AdapterError(
                "kakao: jobTypeCountDtoList 가 비었다. 직군 목록을 알 수 없으면 "
                "기술 직군만 수집하게 되므로 조용히 일부만 모으는 상태가 된다."
            )

        jobs: list[Job] = []
        seen: set[str] = set()
        for part in parts:
            for page in range(1, MAX_PAGES + 1):
                payload = self._page(client, part=part, page=page)
                rows = get_path(payload, "jobList")
                if not isinstance(rows, list):
                    raise AdapterError(f"kakao: jobList 가 배열이 아님 ({part})")
                for row in rows:
                    job = self._to_job(row)
                    if job is None or job.job_id in seen:
                        continue
                    seen.add(job.job_id)
                    jobs.append(job)
                if page >= int(payload.get("totalPage") or 1):
                    break
        return jobs

    def _page(self, client: Client, part: str | None, page: int) -> dict:
        params = {"page": page}
        if part:
            params["part"] = part
        return client.get_json(LIST_URL, params=params,
                               headers={"Referer": self.site_url})

    def _to_job(self, row: dict) -> Job | None:
        if row.get("closeFlag") is True:
            return None
        real_id = row.get("realId")
        title = row.get("jobOfferTitle")
        if not real_id or not title:
            raise AdapterError(f"kakao: realId/jobOfferTitle 누락. 키: {sorted(row)[:15]}")

        company = str(row.get("companyName") or "")
        # skillSetList 가 이 앱에서 가장 값어치 있는 필드다. "Algorithm/ML",
        # "Backend" 같은 기술 태그가 제목에 없을 때 매칭을 살린다.
        skills = tuple(
            str(s.get("skillSetName"))
            for s in row.get("skillSetList") or []
            if isinstance(s, dict) and s.get("skillSetName")
        )
        roles = tuple(
            x for x in (row.get("jobPartName"), row.get("jobTypeName"), *skills) if x
        )
        return Job.make(
            company=resolve(self.key, company, company),
            title=str(title),
            url=JOB_URL.format(real_id=real_id),
            source_id=str(real_id),
            posted_at=parse_date(row.get("regDate")),
            location=row.get("locationName") or None,
            department=row.get("jobPartName") or None,
            employment_type=row.get("employeeTypeName") or None,
            roles=roles,
        )
