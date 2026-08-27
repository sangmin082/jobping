"""삼성전자 — samsungcareers.com.

**상태: 엔드포인트 미확정.**

이 사이트는 완전 클라이언트 렌더링 SPA다. 실제로 HTML을 받아보면 응답
52KB 안에 "job"이라는 문자열이 한 번도 나오지 않는다. 즉 HTML 파싱으로는
어떤 방법으로도 공고를 얻을 수 없고, 브라우저가 호출하는 XHR 엔드포인트를
알아내야 한다.

엔드포인트를 알아냈다면 아래 `ENDPOINT`/`REQUEST`/`SPEC` 세 곳만 채우면
된다. 절차는 docs/ADAPTER-GUIDE.md (회사당 5분). 그 전까지 이 어댑터는
`NeedsDiscovery`를 던지고, 수집기는 이걸 장애가 아니라 '미설정'으로 집계한다.
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, JsonListSpec, NeedsDiscovery

BASE = "https://www.samsungcareers.com"

#: 예: ("POST", f"{BASE}/rest/job/list")  — DevTools에서 확인한 값으로 교체
ENDPOINT: tuple[str, str] | None = None

#: 위 요청에 함께 보내야 하는 것들. json=/params= 중 해당하는 것만.
REQUEST: dict = {}

#: 응답 → Job 매핑. list_path 와 각 키 이름은 실제 응답을 보고 채운다.
SPEC: JsonListSpec | None = None


class SamsungAdapter(Adapter):
    key = "samsung"
    display_name = "삼성전자"
    site_url = BASE
    verified = False

    def fetch(self, client: Client) -> list[Job]:
        if ENDPOINT is None or SPEC is None:
            raise NeedsDiscovery(
                "samsung: 채용 목록 XHR 엔드포인트가 아직 확정되지 않았다. "
                "samsungcareers.com 은 SPA라 HTML 파싱이 불가능하다. "
                "docs/ADAPTER-GUIDE.md 절차대로 엔드포인트를 확인한 뒤 "
                "adapters/samsung.py 의 ENDPOINT/REQUEST/SPEC 를 채워라."
            )
        method, url = ENDPOINT
        payload = (client.post_json if method.upper() == "POST" else client.get_json)(
            url, headers={"Referer": self.site_url}, **REQUEST
        )
        return SPEC.parse(payload)
