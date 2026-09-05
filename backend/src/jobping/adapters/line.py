"""라인 — careers.linecorp.com.

Gatsby 정적 사이트다. 공고 데이터가 빌드 시점에 `page-data.json` 으로 구워져
나오므로 API 가 아니라 그 JSON 을 그대로 읽는다. 번들 안에
`/page-data/app-data.json` 이 보이면 Gatsby 라는 뜻이고, 목록 페이지 경로를
`/page-data/{경로}/page-data.json` 으로 바꾸면 데이터가 나온다.

전 세계 공고 378건이 한 파일에 들어 있다(태국 236, 대만 78). 한국 도시로
추리고, `publish` 가 참이고 마감이 지나지 않은 것만 남긴다 — `publish=False`
인 한국 공고 40건 중 대부분이 마감일이 지난 것이었다. 이 플래그가 사이트의
"현재 노출 중"에 해당한다.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..companies import LINE, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

BASE = "https://careers.linecorp.com"
DATA_URL = f"{BASE}/page-data/ko/jobs/page-data.json"
JOB_URL = f"{BASE}/ko/jobs/{{strapi_id}}"

#: 이 도시가 근무지에 포함된 공고만 한국 공고로 본다.
KOREA_CITIES = frozenset({"Bundang", "Seoul", "분당", "서울"})

#: employment_type 이름. 'Full-time (Entry level)' 이 신입이다.
_ENTRY_LEVEL = "entry level"


class LineAdapter(Adapter):
    key = "line"
    display_name = "라인"
    site_url = f"{BASE}/ko/jobs/"
    companies = LINE
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        payload = client.get_json(DATA_URL, headers={"Referer": self.site_url})
        edges = get_path(payload, "result.data.allStrapiJobs.edges")
        if not isinstance(edges, list):
            raise AdapterError("line: allStrapiJobs.edges 가 배열이 아님")

        now = datetime.now(timezone.utc)
        jobs = []
        korean = 0
        for edge in edges:
            node = edge.get("node") if isinstance(edge, dict) else None
            if not isinstance(node, dict):
                raise AdapterError("line: edge.node 가 dict 가 아님")
            cities = {c.get("name") for c in node.get("cities") or [] if isinstance(c, dict)}
            if not cities & KOREA_CITIES:
                continue
            korean += 1
            if not node.get("publish"):
                continue
            end = parse_date(node.get("end_date"))
            if end and end < now and not node.get("until_filled"):
                continue
            job = self._to_job(node)
            if job is not None:
                jobs.append(job)

        if edges and not korean:
            raise AdapterError(
                f"line: 공고 {len(edges)}건 중 한국 도시가 하나도 없다. "
                "도시 표기가 바뀌었을 수 있다."
            )
        return jobs

    def _to_job(self, node: dict) -> Job | None:
        strapi_id = node.get("strapiId")
        title = node.get("title") or node.get("title_en")
        if not strapi_id or not title:
            raise AdapterError(f"line: strapiId/title 누락. 키: {sorted(node)[:15]}")

        employment = _first_name(node.get("employment_type"))
        if employment and _ENTRY_LEVEL in employment.lower():
            return None

        companies = [c.get("name") for c in node.get("companies") or [] if isinstance(c, dict)]
        company_name = str(companies[0]) if companies else "LINE Plus"
        roles = tuple(
            c.get("name")
            for key in ("job_unit", "job_fields")
            for c in node.get(key) or []
            if isinstance(c, dict) and c.get("name")
        )
        cities = [c.get("name") for c in node.get("cities") or [] if isinstance(c, dict)]
        return Job.make(
            company=resolve(self.key, company_name, company_name),
            title=str(title),
            url=JOB_URL.format(strapi_id=strapi_id),
            source_id=str(strapi_id),
            posted_at=parse_date(node.get("start_date")),
            location=", ".join(str(c) for c in cities) or None,
            department=company_name,
            employment_type=employment,
            roles=roles,
        )


def _first_name(items) -> str | None:
    for item in items or []:
        if isinstance(item, dict) and item.get("name"):
            return str(item["name"])
    return None
