"""Workday(CXS) 공용 어댑터.

야놀자가 이걸 쓴다. 테넌트가 달라도 요청/응답 형태가 같아서 어댑터 하나로
여러 회사를 커버한다. 세 조각은 채용 페이지 주소에서 그대로 읽힌다:

    https://{tenant}.{wd_host}.myworkdayjobs.com/{locale}/{site}

값이 맞는지 확인하는 방법: 사이트를 잘못 적으면 404가, 맞는데 공고가 없으면
200 + 빈 배열이 온다. 둘을 구분할 수 있으므로 "0건"을 오류로 오해하지 않는다.
"""

from __future__ import annotations

from ..companies import YANOLJA
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path

PAGE_SIZE = 20  # 서버가 요청과 무관하게 20으로 잘라 주기도 한다
MAX_PAGES = 25


class WorkdayAdapter(Adapter):
    tenant: str = ""
    wd_host: str = "wd1"
    site: str = ""
    locale: str = "ko-KR"

    @property
    def base(self) -> str:
        return f"https://{self.tenant}.{self.wd_host}.myworkdayjobs.com"

    @property
    def api_url(self) -> str:
        return f"{self.base}/wday/cxs/{self.tenant}/{self.site}/jobs"

    def fetch(self, client: Client) -> list[Job]:
        if not (self.tenant and self.site):
            raise AdapterError(f"{self.key}: tenant/site 가 설정되지 않았다")

        jobs: list[Job] = []
        seen: set[str] = set()
        for page in range(MAX_PAGES):
            payload = client.post_json(
                self.api_url,
                json={"appliedFacets": {}, "limit": PAGE_SIZE,
                      "offset": page * PAGE_SIZE, "searchText": ""},
                headers={"Content-Type": "application/json",
                         "Referer": f"{self.base}/{self.locale}/{self.site}"},
            )
            rows = get_path(payload, "jobPostings")
            if not isinstance(rows, list):
                raise AdapterError(f"{self.key}: jobPostings 가 배열이 아님")
            if not rows:
                break

            for row in rows:
                job = self._to_job(row)
                # offset 페이징 중 목록이 갱신되면 같은 공고가 두 번 나온다.
                if job.job_id in seen:
                    continue
                seen.add(job.job_id)
                jobs.append(job)

            if len(rows) < PAGE_SIZE:
                break
        return jobs

    def _to_job(self, row: dict) -> Job:
        path = row.get("externalPath")
        title = row.get("title")
        if not path or not title:
            raise AdapterError(f"{self.key}: externalPath/title 누락. 키: {sorted(row)[:15]}")
        return Job.make(
            company=self.key,
            title=str(title),
            url=f"{self.base}/{self.locale}/{self.site}{path}",
            # bulletFields[0] 이 관례적으로 요구사항 번호(JR12345)다.
            source_id=_bullet(row) or str(path),
            location=row.get("locationsText"),
            # postedOn 은 "Posted 3 Days Ago" 같은 상대 표현이라 날짜로
            # 되돌릴 수 없다. first_seen_at 을 쓴다.
            posted_at=None,
        )


def _bullet(row: dict) -> str | None:
    fields = row.get("bulletFields")
    if isinstance(fields, list) and fields and isinstance(fields[0], str):
        return fields[0]
    return None


class YanoljaAdapter(WorkdayAdapter):
    key, display_name = "yanolja", "야놀자"
    site_url = "https://yanolja.wd102.myworkdayjobs.com/ko-KR/External_Yanolja"
    tenant, wd_host, site = "yanolja", "wd102", "External_Yanolja"
    companies = YANOLJA
    verified = True
