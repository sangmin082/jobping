"""아직 구현하지 않은 회사들의 자리표시자.

지금은 비어 있다. 새 회사를 조사할 때 여기에 `_Skeleton` 을 상속해 어디까지
확인했는지 `note` 로 남기면, 레지스트리에는 뜨되 `verified=False` 라 앱에는
노출되지 않는다.
"""

from __future__ import annotations

from ..http import Client
from ..models import Job
from .base import Adapter, NeedsDiscovery


class _Skeleton(Adapter):
    note = ""

    def fetch(self, client: Client) -> list[Job]:
        raise NeedsDiscovery(f"{self.key}: 미구현. {self.note}")
