"""현대차그룹 채용 플랫폼 공용 어댑터 (talent.hyundai.com / career.kia.com).

두 사이트가 같은 시스템을 쓴다. 다른 건 호스트, API 번호(`AP-HM-` / `AP-KM-`),
`hgrCd`(현대차 1, 기아 2), `X-HKMC-SERVICE` 헤더뿐이라 어댑터를 공유한다.

파라미터를 하나라도 빼면 HTTP 500과 함께 **채용 사이트 HTML 페이지**가
돌아온다. JSON 에러가 아니라서 원인을 찾기 어렵다. `hgrCd`가 틀리면 200 +
빈 목록이라 더 고약하다 — 그래서 값이 페이지의 `common.constant.js` 에서
읽어온 것임을 주석으로 남겨둔다.
"""

from __future__ import annotations

from ..companies import BY_KEY
from ..http import Client
from ..models import Job
from .base import Adapter, AdapterError, get_path, parse_date

PAGE_SIZE = 20
MAX_PAGES = 30

#: channelCodeNm. 경력자에게 보여줄 유형.
EXPERIENCED_CHANNELS = frozenset({"경력", "계약직"})


class HMGAdapter(Adapter):
    host: str = ""
    api_id: str = ""
    hgr_cd: str = ""
    service: str = ""

    @property
    def list_url(self) -> str:
        return f"{self.host}/api/rec/{self.api_id}"

    def job_url(self, row: dict) -> str:
        # 공고는 (연도, 유형, 일련번호) 세 값으로 식별된다. 상세 페이지가
        # 이 셋을 쿼리로 받는다.
        return (f"{self.host}{self.detail_path}?recuYy={row['recuYy']}"
                f"&recuType={row['recuType']}&recuCls={row['recuCls']}")

    detail_path: str = "/apply/applyView.hc"

    #: 사이트마다 받는 파라미터 집합이 다르다. 현대차는 직무/직종/부문까지,
    #: 기아는 구분/부문/지역만 받는다. 없는 걸 보내면 400이 난다.
    extra_params: tuple[str, ...] = ()

    def fetch(self, client: Client) -> list[Job]:
        if not (self.host and self.api_id and self.hgr_cd):
            raise AdapterError(f"{self.key}: host/api_id/hgr_cd 가 설정되지 않았다")

        jobs: list[Job] = []
        seen: set[str] = set()
        for page in range(1, MAX_PAGES + 1):
            params = {
                "hgrCd": self.hgr_cd,
                "lang": "ko",
                "page": page,
                "pageblock": PAGE_SIZE,
                "searchText": "",
                **{name: "" for name in self.extra_params},
            }
            payload = client.get_json(
                self.list_url,
                params=params,
                headers={
                    "Referer": f"{self.host}/apply/applyList",
                    "X-HKMC-SERVICE": self.service,
                    # 브라우저의 axios 는 로그인 전 sessionStorage 값(null)을
                    # 그대로 헤더에 실어 문자열 "null" 로 보낸다. 기아 서버는
                    # 이 헤더가 **아예 없으면** 400 을 주고, "null" 이면 통과시킨다.
                    # 빈 문자열도 400 이다. 현대차는 없어도 되지만 같은 플랫폼이라
                    # 둘 다 보낸다.
                    "X-HKMC-TOKEN": "null",
                    "X-HKMC-EMP-TOKEN": "null",
                },
            )
            rows = get_path(payload, "data.list")
            if not isinstance(rows, list):
                raise AdapterError(f"{self.key}: data.list 가 배열이 아님")
            if not rows:
                break

            for row in rows:
                job = self._to_job(row)
                if job is None or job.job_id in seen:
                    continue
                seen.add(job.job_id)
                jobs.append(job)

            total = payload.get("data", {}).get("listCnt")
            if isinstance(total, int) and page * PAGE_SIZE >= total:
                break
            if len(rows) < PAGE_SIZE:
                break
        return jobs

    def _to_job(self, row: dict) -> Job | None:
        channel = row.get("channelCodeNm")
        # '신입'/'인턴' 공고를 여기서 걸러낸다. 모르는 값은 통과시킨다 —
        # 새 유형이 생겼을 때 조용히 버리는 것보다 낫고, 제목 기반 제외어가
        # 한 번 더 걸러준다.
        if channel in ("신입", "인턴"):
            return None

        for key in ("recuYy", "recuType", "recuCls", "recuNoticeNm"):
            if row.get(key) in (None, ""):
                raise AdapterError(f"{self.key}: {key} 누락. 키: {sorted(row)[:15]}")

        # hashTag 는 직무가 아니라 "9월 신입채용" 같은 캠페인 라벨이라 뺀다.
        # 넣으면 키워드 '경력'이 모든 공고에 걸리고, 우리가 남긴 경력 공고의
        # roles 에 '신입채용' 이 섞여 들어간다.
        # '기타'도 마찬가지로 매칭에 도움이 안 된다.
        roles = tuple(
            x for x in (row.get("secCodeNm"), row.get("fldCodeNm"))
            if x and x != "기타"
        )
        return Job.make(
            company=self.key,
            title=str(row["recuNoticeNm"]),
            url=self.job_url(row),
            source_id=f"{row['recuYy']}-{row['recuType']}-{row['recuCls']}",
            posted_at=parse_date(_ymd(row.get("applyStartDt"))),
            location=row.get("workPlaceCodeNm") or None,
            department=row.get("secCodeNm") or None,
            employment_type=channel or None,
            roles=roles,
        )


def _ymd(value) -> str | None:
    text = str(value or "")
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}" if len(text) == 8 and text.isdigit() else None


class HyundaiAdapter(HMGAdapter):
    key, display_name = "hyundai", "현대자동차"
    site_url = "https://talent.hyundai.com/apply/applyList.hc"
    host, api_id, hgr_cd, service = "https://talent.hyundai.com", "AP-HM-FO-02700", "1", "HM"
    detail_path = "/apply/applyView.hc"
    extra_params = ("searchFieldList", "searchOccupList", "searchPlaceList",
                    "searchSectorList", "jdSec", "srcOrd", "intnsvYn")
    companies = (BY_KEY["hyundai"],)
    verified = True


class KiaAdapter(HMGAdapter):
    """기아 — 현대차와 같은 플랫폼. `X-HKMC-TOKEN: null` 헤더가 없으면 400."""

    key, display_name = "kia", "기아"
    site_url = "https://career.kia.com/apply/applyList.kc"
    host, api_id, hgr_cd, service = "https://career.kia.com", "AP-KM-FO-02700", "2", "KM"
    detail_path = "/apply/applyView.kc"
    extra_params = ("searchSectorList", "searchSecList", "searchPlaceList")
    companies = (BY_KEY["kia"],)
    verified = True
