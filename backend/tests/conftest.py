import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_json():
    def _load(name: str):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def fixture_text():
    def _load(name: str):
        return (FIXTURES / name).read_text(encoding="utf-8")
    return _load


class FakeClient:
    """네트워크 없이 어댑터를 돌리기 위한 대역.

    호출 순서대로 준비된 응답을 돌려준다. 페이지네이션 로직도 이걸로 검증된다.
    """

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def _next(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self.responses:
            raise AssertionError(f"준비된 응답보다 많이 호출됨: {method} {url}")
        return self.responses.pop(0)

    def get_json(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post_json(self, url, **kwargs):
        return self._next("POST", url, **kwargs)

    def get_text(self, url, **kwargs):
        return self._next("GET", url, **kwargs)

    def post_text(self, url, **kwargs):
        return self._next("POST", url, **kwargs)


@pytest.fixture
def fake_client():
    return FakeClient
