"""아직 구현하지 않은 회사들의 자리표시자.

각 회사가 어떤 방식으로 공고를 내보내는지 조사 결과를 주석으로 남긴다.
구현 순서를 정할 때 이 메모가 근거가 된다. 이들은 레지스트리에는 등록되지만
`verified=False`이므로 앱의 회사 목록에는 노출되지 않는다.
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, NeedsDiscovery


class _Skeleton(Adapter):
    note = ""

    def fetch(self, client: Client) -> list[Job]:
        raise NeedsDiscovery(f"{self.key}: 미구현. {self.note}")


class HyundaiAdapter(_Skeleton):
    key, display_name = "hyundai", "현대자동차"
    site_url = "https://careers.hyundai.com"
    note = "개발 컨테이너 egress 정책에서 차단되어 구조 미확인."


class KiaAdapter(_Skeleton):
    key, display_name = "kia", "기아"
    site_url = "https://careers.kia.com"
    note = "현대차와 채용 플랫폼을 공유할 가능성이 높다. 현대차 확정 후 재사용 검토."


class LGAdapter(_Skeleton):
    key, display_name = "lge", "LG전자"
    site_url = "https://careers.lg.com"
    note = "LG그룹 통합 채용 포털. 계열사 필터가 필요하다(LG전자만 뽑아야 함)."


class NaverAdapter(_Skeleton):
    key, display_name = "naver", "네이버"
    site_url = "https://recruit.navercorp.com"
    note = "HTML 200 응답 확인됨(101KB). 세 곳 중 서버 렌더링 가능성이 가장 높아 다음 구현 1순위."


class KakaoAdapter(_Skeleton):
    key, display_name = "kakao", "카카오"
    site_url = "https://careers.kakao.com"
    note = "HTML 200 응답 확인됨. 목록은 XHR일 가능성이 있어 확인 필요."
