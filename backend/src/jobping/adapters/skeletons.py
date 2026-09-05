"""아직 구현하지 않은 회사들의 자리표시자.

각 회사를 조사하면서 알아낸 것을 주석으로 남긴다. 구현 순서를 정할 때 이
메모가 근거가 된다. 레지스트리에는 등록되지만 `verified=False`이므로 앱의
회사 목록에는 노출되지 않는다.
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, NeedsDiscovery


class _Skeleton(Adapter):
    note = ""

    def fetch(self, client: Client) -> list[Job]:
        raise NeedsDiscovery(f"{self.key}: 미구현. {self.note}")


class LGAdapter(_Skeleton):
    key, display_name = "lge", "LG전자"
    site_url = "https://careers.lg.com/apply"
    note = ("응답이 847바이트짜리 SPA 셸이라 목록 XHR을 찾아야 한다. "
            "LG그룹 통합 포털이므로 계열사 필터(LG전자만)가 필요할 것이다.")


class LineAdapter(_Skeleton):
    key, display_name = "line", "라인"
    site_url = "https://careers.linecorp.com/ko/jobs/"
    note = "SPA 셸(33KB). 인라인 데이터도 API 경로도 노출돼 있지 않아 번들을 읽어야 한다."


class WoowahanAdapter(_Skeleton):
    key, display_name = "woowahan", "우아한형제들"
    site_url = "https://career.woowahan.com/recruitment/"
    note = "SPA 셸(22KB). 위와 동일."


class TossAdapter(_Skeleton):
    key, display_name = "toss", "토스"
    site_url = "https://toss.im/career/jobs"
    note = ("Next.js. __NEXT_DATA__ 는 있는데 prefetch 에 공고가 없고 "
            "색상 설정 등만 들어 있다. 목록은 클라이언트에서 별도 API로 가져온다.")
