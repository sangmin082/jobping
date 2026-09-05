"""네이버 — recruit.navercorp.com.

`GET /rcrt/loadJobList.do` 하나로 네이버·웹툰·클라우드·랩스·SNOW 공고가 함께
나온다. **GET이어야 한다** — POST로 부르면 200과 함께
`alert('접근권한이 없습니다')` HTML이 돌아온다(에러가 아니다).

응답이 `jobDetailLink`로 공고 주소를 직접 준다. 우리가 URL을 조립할 필요가
없는 유일한 소스다.
"""

from __future__ import annotations

from ..companies import NAVER, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

BASE = "https://recruit.navercorp.com"
LIST_URL = f"{BASE}/rcrt/loadJobList.do"
JOB_URL = f"{BASE}/rcrt/view.do?annoId={{anno_id}}"

PAGE_SIZE = 10  # 서버가 firstIndex 와 무관하게 10개씩 준다
MAX_PAGES = 30

#: entTypeCdNm. '무관'은 신입/경력 모두 지원 가능한 공고다.
EXPERIENCED_TYPES = frozenset({"경력", "무관"})
_FILTERED_TYPES = frozenset({"신입", "인턴"})


class NaverAdapter(Adapter):
    key = "naver"
    display_name = "네이버"
    site_url = f"{BASE}/rcrt/list.do"
    companies = NAVER
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        jobs: list[Job] = []
        seen: set[str] = set()
        for page in range(MAX_PAGES):
            payload = client.get_json(
                LIST_URL,
                params={"firstIndex": page * PAGE_SIZE},
                headers={"Referer": self.site_url,
                         "X-Requested-With": "XMLHttpRequest"},
            )
            rows = get_path(payload, "list")
            if not isinstance(rows, list):
                raise AdapterError(f"naver: list 가 배열이 아님 — {type(rows).__name__}")
            if not rows:
                break

            unknown = {
                str(r.get("entTypeCdNm"))
                for r in rows
                if r.get("entTypeCdNm") not in EXPERIENCED_TYPES | _FILTERED_TYPES
            }
            if unknown:
                raise AdapterError(
                    f"naver: 모르는 entTypeCdNm {sorted(unknown)}. "
                    "표기가 바뀌었다면 필터가 전부 걸러내 0건이 된다."
                )

            for row in rows:
                job = self._to_job(row)
                if job is None or job.job_id in seen:
                    continue
                seen.add(job.job_id)
                jobs.append(job)

            total = payload.get("totalSize")
            if isinstance(total, int) and (page + 1) * PAGE_SIZE >= total:
                break
            if len(rows) < PAGE_SIZE:
                break
        return jobs

    def _to_job(self, row: dict) -> Job | None:
        if row.get("entTypeCdNm") not in EXPERIENCED_TYPES:
            return None
        anno_id = row.get("annoId")
        title = row.get("annoSubject")
        if not anno_id or not title:
            raise AdapterError(f"naver: annoId/annoSubject 누락. 키: {sorted(row)[:15]}")

        company = str(row.get("sysCompanyCdNm") or "")
        # 직군(classCdNm)과 직무(subJobCdNm)가 나뉘어 온다. 둘 다 매칭 대상이다.
        roles = tuple(
            part.strip()
            for key in ("classCdNm", "subJobCdNm")
            for part in str(row.get(key) or "").split(",")
            if part.strip()
        )
        return Job.make(
            company=resolve(self.key, company, company),
            title=str(title),
            # 응답이 주는 링크를 그대로 쓴다. 없을 때만 조립한다.
            url=str(row.get("jobDetailLink") or JOB_URL.format(anno_id=anno_id)),
            source_id=str(anno_id),
            posted_at=parse_date(_ymd(row.get("staYmd"))),
            department=company or None,
            employment_type=row.get("empTypeCdNm") or None,
            roles=roles,
        )


def _ymd(value) -> str | None:
    """`"20260827"` → `"2026-08-27"`."""
    text = str(value or "")
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 and text.isdigit() else None
