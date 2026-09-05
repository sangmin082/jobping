"""어댑터 레지스트리."""

from __future__ import annotations

from .adapters import (
    Adapter,
    CoupangAdapter,
    DaangnAdapter,
    HyundaiAdapter,
    KakaoAdapter,
    KiaAdapter,
    LGAdapter,
    LineAdapter,
    NaverAdapter,
    SamsungAdapter,
    SKCareersAdapter,
    TeslaKoreaAdapter,
    TossAdapter,
    WoowahanAdapter,
    YanoljaAdapter,
)
from .companies import Company

# 동작이 확인된 소스를 앞에 둔다.
_CLASSES: tuple[type[Adapter], ...] = (
    SamsungAdapter,
    SKCareersAdapter,
    NaverAdapter,
    KakaoAdapter,
    HyundaiAdapter,
    CoupangAdapter,
    DaangnAdapter,
    YanoljaAdapter,
    TeslaKoreaAdapter,
    KiaAdapter,
    LGAdapter,
    LineAdapter,
    WoowahanAdapter,
    TossAdapter,
)

ADAPTERS: dict[str, Adapter] = {cls.key: cls() for cls in _CLASSES}


def get(key: str) -> Adapter:
    try:
        return ADAPTERS[key]
    except KeyError:
        raise KeyError(f"알 수 없는 어댑터 {key!r}. 가능한 값: {', '.join(ADAPTERS)}")


def all_adapters() -> list[Adapter]:
    return list(ADAPTERS.values())


def verified_adapters() -> list[Adapter]:
    """앱에 노출해도 되는 어댑터만."""
    return [a for a in ADAPTERS.values() if a.verified]


def app_companies() -> list[Company]:
    """앱의 회사 선택 화면에 띄울 목록.

    검증된 소스가 내보내는 계열사만 노출한다. 공고가 실제로 흐르지 않는
    회사를 목록에 띄우면 사용자는 앱이 고장난 줄 모르고 채용이 없다고 믿는다.
    """
    return [c for adapter in verified_adapters() for c in adapter.companies]
