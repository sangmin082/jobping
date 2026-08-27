"""어댑터 기반 클래스와 JSON 목록 추출 규격."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from ..http import Client
from ..models import Job


class AdapterError(RuntimeError):
    """어댑터가 응답을 받았지만 해석에 실패했다. 사이트 구조 변경 신호."""


class NeedsDiscovery(AdapterError):
    """엔드포인트가 아직 확정되지 않은 어댑터.

    일반 오류와 구분한다. 운영 알림에서 '망가짐'과 '아직 설정 안 됨'을
    섞으면 진짜 장애를 놓친다.
    """


class Adapter(ABC):
    key: str = ""
    display_name: str = ""
    site_url: str = ""

    #: 실제 응답으로 파싱이 확인된 어댑터만 True.
    #: False인 어댑터는 앱의 회사 목록에 노출하지 않는다. 동작하지 않는 회사가
    #: 목록에 보이면 사용자는 '알림이 없네'가 아니라 '채용이 없네'로 오해한다.
    verified: bool = False

    @abstractmethod
    def fetch(self, client: Client) -> list[Job]:
        ...

    def __repr__(self) -> str:
        return f"<{type(self).__name__} {self.key}>"


def get_path(data: Any, path: str) -> Any:
    """`"data.list"`, `"result.items.0"` 같은 점 경로로 중첩 값을 꺼낸다.

    빈 경로는 루트를 뜻한다(응답이 곧 배열인 경우).
    """
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


class JsonListSpec:
    """JSON 응답 → `Job` 목록 매핑 규격.

    엔드포인트를 새로 알아냈을 때 파이썬 코드를 짜는 대신 이 규격만 채우면
    되게 하려는 것이다. 새 회사 추가 비용을 '어댑터 작성'에서 '필드 매핑'으로
    낮춘다. 자세한 절차는 docs/ADAPTER-GUIDE.md 참고.
    """

    def __init__(
        self,
        *,
        company: str,
        list_path: str,
        title_key: str,
        url: Callable[[dict], str],
        id_key: str | None = None,
        location_key: str | None = None,
        department_key: str | None = None,
        employment_type_key: str | None = None,
        posted_at_key: str | None = None,
        posted_at_parser: Callable[[Any], datetime | None] | None = None,
    ) -> None:
        self.company = company
        self.list_path = list_path
        self.title_key = title_key
        self.url = url
        self.id_key = id_key
        self.location_key = location_key
        self.department_key = department_key
        self.employment_type_key = employment_type_key
        self.posted_at_key = posted_at_key
        self.posted_at_parser = posted_at_parser or parse_iso

    def parse(self, payload: Any) -> list[Job]:
        rows = get_path(payload, self.list_path)
        if not isinstance(rows, Iterable) or isinstance(rows, (str, bytes, dict)):
            raise AdapterError(
                f"{self.company}: {self.list_path!r} 가 배열이 아니라 "
                f"{type(rows).__name__}"
            )
        jobs: list[Job] = []
        for row in rows:
            if not isinstance(row, dict):
                raise AdapterError(f"{self.company}: 목록 원소가 dict가 아님 — {row!r:.80}")
            title = row.get(self.title_key)
            if not title:
                raise AdapterError(
                    f"{self.company}: 제목 키 {self.title_key!r} 가 비어 있음. "
                    f"원소 키: {sorted(row)[:15]}"
                )
            posted = None
            if self.posted_at_key and row.get(self.posted_at_key) is not None:
                posted = self.posted_at_parser(row[self.posted_at_key])
            jobs.append(
                Job.make(
                    company=self.company,
                    title=str(title),
                    url=self.url(row),
                    source_id=_opt_str(row, self.id_key),
                    posted_at=posted,
                    location=_opt_str(row, self.location_key),
                    department=_opt_str(row, self.department_key),
                    employment_type=_opt_str(row, self.employment_type_key),
                )
            )
        return jobs


def _opt_str(row: dict, key: str | None) -> str | None:
    if not key:
        return None
    value = row.get(key)
    return str(value) if value not in (None, "") else None


def parse_iso(value: Any) -> datetime | None:
    """ISO8601 또는 epoch(초/밀리초)를 UTC datetime으로.

    파싱 실패는 예외로 올리지 않는다. 게시일은 부가 정보이고, 신규 판정은
    `first_seen_at`으로 하므로 날짜 하나 때문에 수집 전체를 실패시킬 이유가 없다.
    """
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip().replace("Z", "+00:00")
    for candidate in (text, text.replace(".", "-").replace("/", "-")):
        try:
            dt = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    return None
