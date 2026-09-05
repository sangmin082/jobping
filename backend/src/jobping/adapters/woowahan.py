"""우아한형제들 — career.woowahan.com.

목록은 `GET /w1/recruits?page=N&size=M` (page 는 0부터). 채용구분·고용형태·
직무군이 텍스트가 아니라 **코드**(`BA003002`)로만 오고, 코드표는 별도
엔드포인트 `/w1/common/common-item/all` 에 있다(844개 항목, `groupCode` 로
묶임). 그래서 매 수집마다 코드표를 먼저 받아 해석한다 — 코드를 하드코딩하면
우아한형제들이 항목을 추가했을 때 조용히 걸러지거나 잘못 표시된다.

`recruitContents` 는 공고 본문이다. 저장하지 않는다(docs/PLAN.md 4절).
"""

from __future__ import annotations

from ..companies import WOOWA, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

BASE = "https://career.woowahan.com"
LIST_URL = f"{BASE}/w1/recruits"
CODES_URL = f"{BASE}/w1/common/common-item/all"
JOB_URL = f"{BASE}/recruitment/{{number}}/detail"

PAGE_SIZE = 100
MAX_PAGES = 20

GROUP_CAREER = "BA003"      # 채용구분: 신입 / 경력 / 신입경력
GROUP_EMPLOYMENT = "BA002"  # 고용형태: 정규직 / 기간제 / 인턴
GROUP_JOB = "BA005"         # 직무군: Tech / Product / …

#: 코드표의 텍스트 기준. 경력자에게 보여줄 채용구분.
EXPERIENCED_TEXTS = frozenset({"경력", "신입/경력", "무관"})
_FILTERED_TEXTS = frozenset({"신입", "채용구분"})  # 000 번은 그룹 제목이다
_INTERN_TEXTS = frozenset({"인턴"})


class WoowahanAdapter(Adapter):
    key = "woowahan"
    display_name = "우아한형제들"
    site_url = f"{BASE}/recruitment/"
    companies = WOOWA
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        codes = self._codes(client)
        jobs: list[Job] = []
        seen: set[str] = set()
        for page in range(MAX_PAGES):
            payload = client.get_json(
                LIST_URL,
                params={"page": page, "size": PAGE_SIZE},
                headers={"Accept": "application/json", "Referer": self.site_url},
            )
            if str(payload.get("code")) != "2000":
                raise AdapterError(f"woowahan: code={payload.get('code')} — {payload!r:.200}")
            rows = get_path(payload, "data.list")
            if not isinstance(rows, list):
                raise AdapterError("woowahan: data.list 가 배열이 아님")
            if not rows:
                break

            for row in rows:
                job = self._to_job(row, codes)
                if job is None or job.job_id in seen:
                    continue
                seen.add(job.job_id)
                jobs.append(job)

            total_pages = payload.get("data", {}).get("totalPageNumber")
            if isinstance(total_pages, int) and page + 1 >= total_pages:
                break
            if len(rows) < PAGE_SIZE:
                break
        return jobs

    def _codes(self, client: Client) -> dict[str, str]:
        payload = client.get_json(CODES_URL, headers={"Accept": "application/json",
                                                       "Referer": self.site_url})
        items = get_path(payload, "data")
        if not isinstance(items, list) or not items:
            raise AdapterError("woowahan: 코드표(common-item/all)가 비었다")
        table = {
            str(it["code"]): str(it["text"])
            for it in items
            if isinstance(it, dict) and it.get("code") and it.get("text")
        }
        if not any(k.startswith(GROUP_CAREER) for k in table):
            raise AdapterError(f"woowahan: 코드표에 채용구분({GROUP_CAREER}) 그룹이 없다")
        return table

    def _to_job(self, row: dict, codes: dict[str, str]) -> Job | None:
        if row.get("isHidden"):
            return None
        career = codes.get(_code(row.get("careerType")) or "")
        if career is None:
            raise AdapterError(
                f"woowahan: careerType 코드 {_code(row.get('careerType'))!r} 가 "
                "코드표에 없다. 코드표를 확인할 것."
            )
        if career in _FILTERED_TEXTS:
            return None
        if career not in EXPERIENCED_TEXTS:
            raise AdapterError(
                f"woowahan: 모르는 채용구분 {career!r}. 표기가 바뀌었다면 "
                "필터가 전부 걸러내 0건이 된다."
            )
        employment = codes.get(_code(row.get("employmentType")) or "")
        if employment in _INTERN_TEXTS:
            return None

        number = row.get("recruitNumber")
        title = row.get("recruitName")
        if not number or not title:
            raise AdapterError(f"woowahan: recruitNumber/recruitName 누락. 키: {sorted(row)[:15]}")

        corp = str(row.get("recruitCorporationNumber") or "")
        job_group = codes.get(_code(row.get("jobGroup")) or "")
        return Job.make(
            company=resolve(self.key, corp, corp),
            title=str(title),
            url=JOB_URL.format(number=number),
            source_id=str(number),
            posted_at=parse_date(str(row.get("recruitOpenDate") or "").replace(" ", "T") or None),
            department=job_group,
            employment_type=employment,
            roles=tuple(x for x in (job_group,) if x),
        )


def _code(value) -> str | None:
    return value.get("recruitItemCode") if isinstance(value, dict) else None
