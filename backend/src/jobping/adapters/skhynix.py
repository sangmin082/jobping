"""SK하이닉스 — recruit.skhynix.com.

**상태: 엔드포인트 미확정.**

이 호스트는 개발 컨테이너의 egress 정책에서 차단되어 있어 구조를 직접
확인하지 못했다. 삼성과 같은 방식(DevTools로 XHR 확인 → 아래 세 상수 채우기)
으로 5분이면 확정된다. docs/ADAPTER-GUIDE.md 참고.
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, JsonListSpec, NeedsDiscovery

BASE = "https://recruit.skhynix.com"

ENDPOINT: tuple[str, str] | None = None
REQUEST: dict = {}
SPEC: JsonListSpec | None = None


class SKHynixAdapter(Adapter):
    key = "skhynix"
    display_name = "SK하이닉스"
    site_url = BASE
    verified = False

    def fetch(self, client: Client) -> list[Job]:
        if ENDPOINT is None or SPEC is None:
            raise NeedsDiscovery(
                "skhynix: 채용 목록 엔드포인트가 아직 확정되지 않았다. "
                "docs/ADAPTER-GUIDE.md 절차대로 확인한 뒤 "
                "adapters/skhynix.py 의 ENDPOINT/REQUEST/SPEC 를 채워라."
            )
        method, url = ENDPOINT
        payload = (client.post_json if method.upper() == "POST" else client.get_json)(
            url, headers={"Referer": self.site_url}, **REQUEST
        )
        return SPEC.parse(payload)
