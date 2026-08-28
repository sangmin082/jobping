"""SK 그룹 통합 채용 포털 — www.skcareers.com.

`recruit.skhynix.com`이 아니라 여기가 소스다. SK하이닉스를 포함한 계열사
27곳의 공고가 한 엔드포인트로 나온다.

`POST /Recruit/GetRecruitList`는 **일곱 개 파라미터를 모두 보내야 한다.**
하나라도 빠지면 ASP.NET 모델 바인딩이 실패해 커스텀 404 페이지를 돌려준다
(에러가 아니라 404라서 원인을 찾기 어렵다). `sort`와 `jobRole`은 빈 문자열이
아니라 `0`이어야 한다.

페이지네이션이 없다. 한 번에 전체 목록을 주고 화면에서 잘라 보여준다.
"""

from __future__ import annotations

from ..companies import SK, resolve
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path

BASE = "https://www.skcareers.com"
LIST_URL = f"{BASE}/Recruit/GetRecruitList"
JOB_URL = f"{BASE}/Recruit/Detail/{{notice_id}}"

#: 일곱 개 전부 필수. sort/jobRole 은 "0", 나머지는 빈 문자열이 전체 조회.
LIST_PARAMS = {
    "sort": "0",
    "searchText": "",
    "corpCode": "",
    "jobRole": "0",
    "recruitType": "",
    "workingType": "",
    "workingRegion": "",
}

# recruitType 은 **Accept-Language 에 따라 표기가 바뀐다** — 영어로 요청하면
# "Experienced", 한국어로 요청하면 "경력"이 온다. 그래서 두 표기를 모두 받는다.
#
# 모르는 값이 오면 조용히 걸러내지 않고 예외를 던진다. 필터가 아무것도 통과
# 시키지 못하면 결과가 0건이 되는데, 그건 "채용이 없다"와 구분되지 않는다.
# 사용자는 앱이 고장난 걸 모른 채 알림을 기다리게 된다.

#: 경력자에게 보여줄 유형. '무관'은 신입/경력 모두 지원 가능한 공고다.
EXPERIENCED_TYPES = frozenset({"Experienced", "Irrelevant", "경력", "무관"})

#: 걸러내는 게 정상인 유형.
_FILTERED_TYPES = frozenset({"New", "Intern", "신입", "인턴"})


class SKCareersAdapter(Adapter):
    key = "skcareers"
    display_name = "SK"
    site_url = f"{BASE}/Recruit"
    companies = SK
    verified = True

    def fetch(self, client: Client) -> list[Job]:
        payload = client.post_json(
            LIST_URL,
            data=LIST_PARAMS,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": self.site_url,
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if payload.get("success") is not True:
            raise AdapterError(f"skcareers: success 가 참이 아님 — {payload!r:.200}")

        rows = get_path(payload, "list")
        if not isinstance(rows, list):
            raise AdapterError(f"skcareers: list 가 배열이 아님 — {type(rows).__name__}")

        total = payload.get("totalCount")
        if isinstance(total, int) and total != len(rows):
            # 페이지네이션이 없다고 알고 있으므로, 어긋나면 그 전제가 깨진 것이다.
            raise AdapterError(
                f"skcareers: totalCount({total}) 와 실제 건수({len(rows)})가 다르다. "
                "페이지네이션이 생겼을 수 있다."
            )

        unknown = {
            str(r.get("recruitType"))
            for r in rows
            if r.get("recruitType") not in EXPERIENCED_TYPES | _FILTERED_TYPES
        }
        if unknown:
            raise AdapterError(
                f"skcareers: 모르는 recruitType {sorted(unknown)}. "
                "표기가 바뀌었다면 필터가 전부 걸러내 0건이 된다."
            )

        return [
            self._to_job(row)
            for row in rows
            if row.get("recruitType") in EXPERIENCED_TYPES
        ]

    def _to_job(self, row: dict) -> Job:
        notice_id = row.get("noticeID")
        title = row.get("title")
        if not notice_id or not title:
            raise AdapterError(
                f"skcareers: noticeID/title 누락. 키: {sorted(row)[:15]}"
            )
        corp = str(row.get("corpName") or "")
        # jobRole 은 "기획/서비스 기획/운영 • 영업/B2C 영업,B2B 영업" 처럼
        # 여러 직무를 구분자로 이어붙인 문자열이다. 매칭을 위해 쪼갠다.
        roles = tuple(
            part.strip()
            for chunk in str(row.get("jobRole") or "").split("•")
            for part in chunk.split(",")
            if part.strip()
        )
        return Job.make(
            company=resolve(self.key, corp, corp),
            title=str(title),
            url=JOB_URL.format(notice_id=notice_id),
            source_id=str(notice_id),
            location=row.get("workingArea") or None,
            department=corp or None,
            employment_type=row.get("workingType") or None,
            roles=roles,
        )
