"""어댑터 기반 클래스."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from ..companies import Company
from ..http import Client
from ..models import Job


class AdapterError(RuntimeError):
    """어댑터가 응답을 받았지만 해석에 실패했다. 사이트 구조 변경 신호."""


class NeedsDiscovery(AdapterError):
    """엔드포인트가 아직 확정되지 않은 어댑터.

    일반 오류와 구분한다. 운영 알림에서 '망가짐'과 '아직 구현 안 됨'을
    섞으면 진짜 장애를 놓친다.
    """


class Adapter(ABC):
    key: str = ""
    display_name: str = ""
    site_url: str = ""

    #: 이 소스가 내보내는 계열사들. 삼성·SK처럼 그룹 통합 포털이면 수십 개다.
    companies: tuple[Company, ...] = ()

    #: 실제 응답으로 파싱이 확인된 어댑터만 True.
    #: False면 앱의 회사 목록에 노출하지 않는다. 동작하지 않는 회사가 목록에
    #: 보이면 사용자는 '알림이 없네'가 아니라 '채용이 없네'로 오해한다.
    verified: bool = False

    @abstractmethod
    def fetch(self, client: Client) -> list[Job]:
        ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.key}>"


def get_path(data: Any, path: str) -> Any:
    """`"data.jobs"`, `"result.items.0"` 같은 점 경로로 중첩 값을 꺼낸다."""
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                raise AdapterError(f"경로 {path!r} 의 {part!r} 에서 끊김")
        elif isinstance(cur, dict):
            if part not in cur:
                raise AdapterError(
                    f"경로 {path!r} 의 {part!r} 가 응답에 없음. "
                    f"가진 키: {sorted(cur)[:15]}"
                )
            cur = cur[part]
        else:
            raise AdapterError(f"경로 {path!r} 를 {type(cur).__name__} 에 적용할 수 없음")
    return cur


def parse_date(value: Any) -> datetime | None:
    """ISO8601, `2026.08.20`, epoch(초/밀리초)를 UTC datetime으로.

    파싱 실패는 예외로 올리지 않는다. 게시일은 부가 정보이고 신규 판정은
    `first_seen_at`이 하므로, 날짜 하나 때문에 수집 전체를 실패시킬 이유가 없다.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(".", "-").replace("/", "-")):
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None
