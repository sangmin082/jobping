"""테슬라 — 채용 검색 페이지가 쓰는 공개 JSON 상태 API.

한 번의 요청으로 전 세계 공고를 통째로 준다(부서/지역/고용형태는 ID로 오고,
같은 응답 안의 사전으로 풀어야 한다). 페이지네이션이 없어서 수집이 단순하다.

주의: 이 엔드포인트는 데이터센터 IP에서 403을 준다(관측됨). AWS Lambda에서도
같은 차단에 걸릴 수 있다. 대응 단계는 docs/PLAN.md 2절 참고.
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path

STATE_URL = "https://www.tesla.com/cua-api/apps/careers/state"
JOB_URL = "https://www.tesla.com/careers/search/job/{id}"

# 테슬라 응답은 키를 한 글자로 줄여 쓴다. 언젠가 풀네임으로 바뀔 수 있으니
# 둘 다 받아준다.
_TITLE_KEYS = ("t", "title")
_DEPT_KEYS = ("dp", "department")
_LOC_KEYS = ("l", "location")
_TYPE_KEYS = ("y", "type")


class TeslaAdapter(Adapter):
    key = "tesla"
    display_name = "Tesla"
    site_url = "https://www.tesla.com/careers/search"
    verified = False  # scripts/verify.py tesla 를 통과시킨 뒤 True 로 올린다

    def fetch(self, client: Client) -> list[Job]:
        payload = client.get_json(
            STATE_URL,
            headers={"Referer": "https://www.tesla.com/careers/search"},
        )
        listings = get_path(payload, "listings")
        if not isinstance(listings, list):
            raise AdapterError(f"tesla: listings 가 배열이 아님 — {type(listings).__name__}")

        departments = _lookup(payload, "departments")
        locations = _lookup(payload, "locations")
        types = _lookup(payload, "types")

        jobs: list[Job] = []
        for row in listings:
            job_id = row.get("id")
            if job_id is None:
                raise AdapterError(f"tesla: id 없는 공고 — 키 {sorted(row)[:15]}")
            jobs.append(
                Job.make(
                    company=self.key,
                    title=_first(row, _TITLE_KEYS, required=True),
                    url=JOB_URL.format(id=job_id),
                    source_id=str(job_id),
                    location=locations.get(_first(row, _LOC_KEYS)),
                    department=departments.get(_first(row, _DEPT_KEYS)),
                    employment_type=types.get(_first(row, _TYPE_KEYS)),
                )
            )
        return jobs


def _lookup(payload: dict, key: str) -> dict:
    """`[{"id": 3, "name": "Engineering"}, ...]` → `{3: "Engineering"}`."""
    rows = payload.get(key)
    if not isinstance(rows, list):
        return {}
    table: dict = {}
    for row in rows:
        if isinstance(row, dict) and "id" in row:
            table[row["id"]] = row.get("name") or row.get("t")
    return table


def _first(row: dict, keys: tuple[str, ...], required: bool = False):
    for key in keys:
        if row.get(key) not in (None, ""):
            return row[key]
    if required:
        raise AdapterError(
            f"tesla: {keys} 중 어느 키도 없음. 응답 구조가 바뀌었다. "
            f"실제 키: {sorted(row)[:15]}"
        )
    return None
