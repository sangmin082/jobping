"""LG 그룹 통합 채용 포털 — careers.lg.com.

목록 API가 별도 호스트(`api.careers.lg.com/rmk`)에 있다. 페이지는 847바이트
SPA 셸이라 아무것도 없고, 번들 안의 axios `baseURL` 에서 호스트를 찾았다.

`POST /job/retrieveJobNoticesList` 에 JSON 본문으로 필터 여덟 개를 **전부**
보낸다(빈 값이라도). 응답은 페이지네이션 없이 한 번에 전부다.

계열사 16곳이 섞여 나온다 — LG전자뿐 아니라 LG CNS·에너지솔루션·유플러스·
디스플레이·화학 등. `companyCode` 로 갈라 계열사 키를 붙인다.
"""

from __future__ import annotations

from ..companies import LG, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

BASE = "https://careers.lg.com"
API = "https://api.careers.lg.com/rmk/job/retrieveJobNoticesList"
JOB_URL = f"{BASE}/apply/detail?id={{notice_id}}"

#: 여덟 개 전부 보낸다. 브라우저 번들의 기본값 그대로.
LIST_BODY = {
    "lnbSearch": "",
    "hashTagText": "",
    "recDate": "CREATION_DATE",
    "order": "DESC",
    "careerList": [],
    "companyCodeList": [],
    "desireLocList": [],
    "jobGroupList": [],
}

#: careerTypeCode. B=경력, D=신입/경력 — 둘 다 경력자가 지원할 수 있다.
EXPERIENCED_CODES = frozenset({"B", "D"})
#: A=신입, C=인턴, E=산학장학생 — 걸러내는 게 정상.
_FILTERED_CODES = frozenset({"A", "C", "E"})


class LGAdapter(Adapter):
    key = "lg"
    display_name = "LG"
    site_url = f"{BASE}/apply"
    companies = LG
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        payload = client.post_json(
            API,
            json=LIST_BODY,
            headers={"Content-Type": "application/json",
                     "Origin": BASE, "Referer": f"{BASE}/"},
        )
        if payload.get("status") != "S":
            raise AdapterError(f"lg: status 가 S 가 아님 — {payload!r:.200}")
        rows = get_path(payload, "data.jobNoticeList")
        if not isinstance(rows, list):
            raise AdapterError("lg: data.jobNoticeList 가 배열이 아님")

        unknown = {
            str(r.get("careerTypeCode"))
            for r in rows
            if r.get("careerTypeCode") not in EXPERIENCED_CODES | _FILTERED_CODES
        }
        if unknown:
            raise AdapterError(
                f"lg: 모르는 careerTypeCode {sorted(unknown)}. "
                "코드 체계가 바뀌었다면 필터가 전부 걸러내 0건이 된다."
            )

        jobs = []
        for row in rows:
            # SAVE 는 아직 게시 전인 임시저장 상태다. 링크가 열리지 않는다.
            if row.get("noticeStatus") != "POSTING":
                continue
            if row.get("careerTypeCode") not in EXPERIENCED_CODES:
                continue
            jobs.append(self._to_job(row))
        return jobs

    def _to_job(self, row: dict) -> Job:
        notice_id = row.get("jobNoticeId")
        title = row.get("jobNoticeName")
        if not notice_id or not title:
            raise AdapterError(f"lg: jobNoticeId/jobNoticeName 누락. 키: {sorted(row)[:15]}")
        code = str(row.get("companyCode") or "")
        name = str(row.get("companyName") or "")
        roles = tuple(
            x for x in (row.get("jobGroupName"), row.get("jobGroupName2")) if x
        )
        return Job.make(
            company=resolve(self.key, code, name),
            title=str(title),
            url=JOB_URL.format(notice_id=notice_id),
            source_id=str(notice_id),
            # recDateDiff 는 마감까지 남은 일수라 게시일이 아니다. 게시일 필드가
            # 목록 응답에 없어서 first_seen_at 에 맡긴다.
            posted_at=None,
            location=row.get("workLocationName") or None,
            department=name or None,
            employment_type=row.get("careerTypeName") or None,
            roles=roles,
        )
