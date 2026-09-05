"""토스 — toss.im/career.

속은 Greenhouse 다(`gh_jid`, 10자리 ID). 그런데 공개 보드 토큰을 못 찾았고
(`toss`, `toss-im`, `vivarepublica` … 전부 404), 토스가 자체 API 로 감싸서
내보낸다: `GET api-public.toss.im/api/v3/ipd-eggnog/career/job-groups`.

응답은 **그룹** 단위다. "Product Designer" 그룹 하나에 Greenhouse 공고
여러 개(`jobs[]`)가 묶여 있고 사이트도 그룹으로 보여준다. 우리도 그룹당
1건으로 낸다 — 같은 제목의 변형 넷을 알림 넷으로 보내면 스팸이다.

주의 두 가지:
* 응답이 **6MB** 다. 메타데이터에 공고 본문 전문(Job Description)이 들어
  있어서다. 본문은 저장하지 않는다(docs/PLAN.md 4절)
* 자회사·고용형태·직군이 고정 필드가 아니라 `metadata[]` 안에 **한국어 질문
  문구를 이름으로** 들어 있다("포지션의 소속 자회사를 선택해 주세요."). 문구가
  바뀌면 조용히 None 이 되므로 부분 문자열로 찾고, 자회사를 하나도 못 찾으면
  예외를 던진다.
"""

from __future__ import annotations

from ..companies import TOSS, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

BASE = "https://toss.im/career"
API = "https://api-public.toss.im/api/v3/ipd-eggnog/career/job-groups"
JOB_URL = f"{BASE}/job-detail?gh_jid={{gh_jid}}"

#: metadata[].name 에 이 문자열이 포함된 항목을 찾는다.
META_COMPANY = "자회사"
META_EMPLOYMENT = "Employment_Type"
META_CATEGORY = "Job Category"


class TossAdapter(Adapter):
    key = "toss"
    display_name = "토스"
    site_url = f"{BASE}/jobs"
    companies = TOSS
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        payload = client.get_json(
            API,
            headers={"Accept": "application/json",
                     "Origin": "https://toss.im", "Referer": self.site_url},
        )
        if payload.get("resultType") not in (None, "SUCCESS"):
            raise AdapterError(f"toss: resultType={payload.get('resultType')!r}")
        groups = get_path(payload, "success")
        if not isinstance(groups, list):
            raise AdapterError(f"toss: success 가 배열이 아님 — {type(groups).__name__}")

        jobs = []
        found_company = False
        for group in groups:
            job = self._to_job(group)
            if job is None:
                continue
            found_company = found_company or job.company != "toss_unknown"
            jobs.append(job)

        if groups and not found_company:
            raise AdapterError(
                "toss: 어느 공고에서도 자회사 메타데이터를 찾지 못했다. "
                "메타데이터 질문 문구가 바뀌었을 수 있다."
            )
        return jobs

    def _to_job(self, group: dict) -> Job | None:
        primary = group.get("primary_job")
        if not isinstance(primary, dict):
            raise AdapterError(f"toss: primary_job 없음. 키: {sorted(group)[:10]}")
        gh_id = primary.get("id")
        title = group.get("title") or primary.get("title")
        if not gh_id or not title:
            raise AdapterError(f"toss: id/title 누락. 키: {sorted(primary)[:12]}")

        company_name = _meta(primary, META_COMPANY)
        location = primary.get("location")
        location = location.get("name") if isinstance(location, dict) else None
        category = _meta(primary, META_CATEGORY)

        return Job.make(
            company=resolve(self.key, company_name or "", company_name or "")
            if company_name else "toss_unknown",
            title=str(title),
            url=str(primary.get("absolute_url") or JOB_URL.format(gh_jid=gh_id)),
            source_id=str(gh_id),
            posted_at=parse_date(primary.get("first_published")),
            location=location,
            department=category,
            employment_type=_meta(primary, META_EMPLOYMENT),
            roles=tuple(x for x in (category,) if x),
        )


def _meta(job: dict, name_fragment: str) -> str | None:
    for item in job.get("metadata") or []:
        if isinstance(item, dict) and name_fragment in str(item.get("name") or ""):
            value = item.get("value")
            return str(value) if value not in (None, "") else None
    return None
