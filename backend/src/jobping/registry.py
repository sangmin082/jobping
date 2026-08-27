"""어댑터 레지스트리."""

from __future__ import annotations

from .adapters import (
    Adapter,
    HyundaiAdapter,
    KakaoAdapter,
    KiaAdapter,
    LGAdapter,
    NaverAdapter,
    SamsungAdapter,
    SKHynixAdapter,
    TeslaAdapter,
)

# 1차 대상 3사를 앞에 둔다.
_CLASSES: tuple[type[Adapter], ...] = (
    SamsungAdapter,
    SKHynixAdapter,
    TeslaAdapter,
    HyundaiAdapter,
    KiaAdapter,
    LGAdapter,
    NaverAdapter,
    KakaoAdapter,
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
