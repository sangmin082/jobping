"""MokaHR(hire-r1.mokahr.com) 채용 사이트 공용 어댑터.

테슬라 코리아가 이걸 쓴다. 테슬라 본사 API(`www.tesla.com/cua-api/...`)는
데이터센터 IP에 403을 주지만, MokaHR은 차단이 없고 게시일까지 준다.

MokaHR은 여러 회사가 쓰는 ATS라, 이 클래스를 상속해 `org_id`/`site_id`만
바꾸면 새 회사가 붙는다. 두 값은 채용 사이트 주소에서 그대로 읽힌다:

    https://hire-r1.mokahr.com/social-recruitment/{org_id}/{site_id}
"""

from __future__ import annotations

from ..companies import TESLA
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

HOST = "https://hire-r1.mokahr.com"
API_URL = f"{HOST}/api/outer/ats-apply/website/jobs/v2"

PAGE_SIZE = 50
MAX_PAGES = 20

#: MokaHR 은 중국 ATS라 고용형태를 중국어로 준다. 한국어 앱에 그대로 노출할 수
#: 없다. 모르는 값은 원문 그대로 두어 정보가 사라지지 않게 한다.
COMMITMENTS = {
    "全职": "정규직",
    "兼职": "파트타임",
    "实习": "인턴",
    "合同工": "계약직",
    "临时工": "임시직",
    "Full-time": "정규직",
    "Part-time": "파트타임",
    "Intern": "인턴",
    "Contract": "계약직",
}


class MokaHRAdapter(Adapter):
    org_id: str = ""
    site_id: str = ""
    locale: str = "en-US"

    @property
    def base_url(self) -> str:
        return f"{HOST}/social-recruitment/{self.org_id}/{self.site_id}"

    def job_url(self, job_id: str) -> str:
        # 해시 라우팅 SPA다. 프래그먼트가 곧 경로다.
        return f"{self.base_url}#/job/{job_id}"

    def fetch(self, client: Client) -> list[Job]:
        if not (self.org_id and self.site_id):
            raise AdapterError(f"{self.key}: org_id/site_id 가 설정되지 않았다")

        jobs: list[Job] = []
        seen: set[str] = set()
        for page in range(MAX_PAGES):
            payload = client.post_json(
                API_URL,
                json={
                    "orgId": self.org_id,
                    "siteId": self.site_id,
                    "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE,
                    "needStat": True,
                    "locale": self.locale,
                },
                headers={"Content-Type": "application/json",
                         "Referer": self.base_url},
            )
            if payload.get("code") != 0:
                raise AdapterError(f"{self.key}: code={payload.get('code')} — {payload!r:.200}")

            rows = get_path(payload, "data.jobs")
            if not isinstance(rows, list):
                raise AdapterError(f"{self.key}: data.jobs 가 배열이 아님")
            if not rows:
                break

            for row in rows:
                job = self._to_job(row)
                # offset 페이징 중 목록이 갱신되면 같은 공고가 두 번 나온다.
                if job.job_id not in seen:
                    seen.add(job.job_id)
                    jobs.append(job)

            if len(rows) < PAGE_SIZE:
                break
        return jobs

    def _to_job(self, row: dict) -> Job:
        job_id = row.get("id")
        title = row.get("title")
        if not job_id or not title:
            raise AdapterError(f"{self.key}: id/title 누락. 키: {sorted(row)[:15]}")

        department = _name(row.get("department"))
        function = _name(row.get("zhineng"))  # MokaHR 내부 명칭. 직군에 해당한다.

        return Job.make(
            company=self.key,
            title=str(title),
            url=self.job_url(str(job_id)),
            source_id=str(job_id),
            # openedAt 이 게시일이다. 없으면 등록 시각으로 대체한다.
            posted_at=parse_date(row.get("openedAt") or row.get("createdAt")),
            location=_location(row),
            department=department,
            employment_type=_commitment(row.get("commitment")),
            roles=tuple(x for x in (function,) if x),
        )


def _commitment(value) -> str | None:
    if not value:
        return None
    return COMMITMENTS.get(str(value), str(value))


def _name(value) -> str | None:
    return value.get("name") if isinstance(value, dict) else None


def _location(row: dict) -> str | None:
    """근무지는 고정 필드가 아니라 회사가 만든 커스텀 필드에 들어 있다."""
    fields = row.get("customFields")
    if not isinstance(fields, dict):
        return None
    for field in fields.values():
        if isinstance(field, dict) and "location" in str(field.get("name", "")).lower():
            return field.get("value") or None
    return None


class TeslaKoreaAdapter(MokaHRAdapter):
    key = "tesla_kr"
    display_name = "테슬라 코리아"
    site_url = f"{HOST}/social-recruitment/tesla/100000166"
    org_id, site_id = "tesla", "100000166"
    companies = TESLA
    verified = True
