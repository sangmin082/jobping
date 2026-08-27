"""Workday(CXS) 공용 어댑터.

한국 대기업은 대부분 자체 채용 시스템이라 회사별 어댑터가 불가피하지만,
외국계·계열사·해외법인 상당수는 Workday를 쓴다. Workday의 CXS API는 테넌트가
달라도 요청/응답 형태가 동일해서, **이 어댑터 하나로 회사 수십 곳을 커버**할
수 있다. 새 회사를 붙이는 비용이 '어댑터 작성'이 아니라 '설정 3줄'이 된다.

    class AcmeAdapter(WorkdayAdapter):
        key, display_name = "acme", "Acme"
        tenant, wd_host, site = "acme", "wd3", "Acme_Careers"

URL 세 조각은 회사 채용 페이지 주소에서 그대로 읽힌다:
    https://{tenant}.{wd_host}.myworkdayjobs.com/{site}
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path

PAGE_SIZE = 20  # Workday가 요청과 무관하게 20으로 잘라 돌려주는 경우가 있다
MAX_PAGES = 25  # 500건. 한 회사가 이보다 많으면 필터를 좁히는 게 맞다


class WorkdayAdapter(Adapter):
    tenant: str = ""
    wd_host: str = "wd1"
    site: str = ""
    search_text: str = ""

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
        seen_paths: set[str] = set()
        for page in range(MAX_PAGES):
            payload = client.post_json(
                self.api_url,
                json={
                    "appliedFacets": {},
                    "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE,
                    "searchText": self.search_text,
                },
                headers={
                    "Content-Type": "application/json",
                    "Referer": f"{self.base}/{self.site}",
                },
            )
            postings = get_path(payload, "jobPostings")
            if not isinstance(postings, list):
                raise AdapterError(f"{self.key}: jobPostings 가 배열이 아님")
            if not postings:
                break

            for row in postings:
                path = row.get("externalPath")
                title = row.get("title")
                if not path or not title:
                    raise AdapterError(
                        f"{self.key}: externalPath/title 누락. 키: {sorted(row)[:15]}"
                    )
                # offset 페이징 중 목록이 갱신되면 같은 공고가 두 페이지에
                # 걸쳐 나온다. 중복 제거는 여기서 한다.
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                jobs.append(
                    Job.make(
                        company=self.key,
                        title=title,
                        url=f"{self.base}/{self.site}{path}",
                        # bulletFields[0] 이 관례적으로 요구사항 번호(JR12345)다.
                        source_id=_bullet(row) or path,
                        location=row.get("locationsText"),
                        # postedOn 은 "Posted 3 Days Ago" 같은 상대 표현이라
                        # 날짜로 되돌릴 수 없다. first_seen_at 을 쓴다.
                        posted_at=None,
                    )
                )

            if len(postings) < PAGE_SIZE:
                break
        return jobs


def _bullet(row: dict) -> str | None:
    fields = row.get("bulletFields")
    if isinstance(fields, list) and fields and isinstance(fields[0], str):
        return fields[0]
    return None
