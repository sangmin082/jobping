"""공용 HTTP 클라이언트.

채용 사이트는 대부분 봇 차단이 걸려 있다. 데이터센터 IP에서 오는
`python-requests/2.x` User-Agent는 거의 확실히 막힌다. 그래서 기본값으로
브라우저에 준하는 헤더 일습을 보내되, User-Agent에는 우리 연락처를 남겨서
차단하고 싶은 운영자가 우리를 특정할 수 있게 한다. 숨어서 긁는 게 아니라
예의를 지키면서 긁는 쪽이다.
"""

from __future__ import annotations

import logging

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

CONTACT_URL = "https://github.com/sangmin082/jobping"

# 실제 브라우저가 보내는 헤더 집합. 이 중 하나만 빠져도 403을 주는 WAF가 있다.
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        f"(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 JobPingBot/0.1 (+{CONTACT_URL})"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}

DEFAULT_TIMEOUT = (5, 20)  # (connect, read)


class FetchError(RuntimeError):
    """네트워크 계층 실패. 어댑터 파싱 실패와 구분하기 위해 따로 둔다."""


class Client:
    def __init__(self, timeout: tuple[int, int] = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(BROWSER_HEADERS)
        # 5xx와 429만 재시도한다. 403은 재시도해도 안 풀리고, 오히려 차단을
        # 굳히므로 즉시 포기하고 위로 올린다.
        retry = Retry(
            total=2,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.timeout)
        try:
            res = self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise FetchError(f"{method} {url} 실패: {exc}") from exc
        if res.status_code >= 400:
            hint = ""
            if res.status_code in (403, 406):
                hint = (
                    " — 봇 차단으로 보인다. 데이터센터 IP(Lambda 포함)에서는"
                    " 흔하다. docs/PLAN.md 2절의 대응 단계를 참고."
                )
            raise FetchError(f"{method} {url} → HTTP {res.status_code}{hint}")
        return res

    def get_json(self, url: str, **kwargs) -> dict | list:
        return self._as_json(self.request("GET", url, **kwargs))

    def post_json(self, url: str, **kwargs) -> dict | list:
        return self._as_json(self.request("POST", url, **kwargs))

    def get_text(self, url: str, **kwargs) -> str:
        return self.request("GET", url, **kwargs).text

    def post_text(self, url: str, **kwargs) -> str:
        """POST 로 HTML 조각을 받아오는 경우(삼성 list.data)."""
        return self.request("POST", url, **kwargs).text

    @staticmethod
    def _as_json(res: requests.Response) -> dict | list:
        try:
            return res.json()
        except ValueError as exc:
            # SPA 셸 HTML이 돌아온 경우가 대부분이다. 엔드포인트가 틀렸다는 뜻.
            head = res.text[:120].replace("\n", " ")
            raise FetchError(
                f"{res.url} 가 JSON이 아니다 (content-type="
                f"{res.headers.get('content-type')!r}): {head!r}"
            ) from exc

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
