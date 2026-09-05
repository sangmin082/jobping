from .base import Adapter, AdapterError, NeedsDiscovery
from .greenhouse import CoupangAdapter, DaangnAdapter, GreenhouseAdapter
from .hmg import HMGAdapter, HyundaiAdapter, KiaAdapter
from .kakao import KakaoAdapter
from .lg import LGAdapter
from .line import LineAdapter
from .mokahr import MokaHRAdapter, TeslaKoreaAdapter
from .naver import NaverAdapter
from .samsung import SamsungAdapter
from .skcareers import SKCareersAdapter
from .toss import TossAdapter
from .woowahan import WoowahanAdapter
from .workday import WorkdayAdapter, YanoljaAdapter

__all__ = [
    "Adapter",
    "AdapterError",
    "NeedsDiscovery",
    # 공용 ATS 어댑터 — 상속해서 회사를 붙인다
    "GreenhouseAdapter",
    "MokaHRAdapter",
    "WorkdayAdapter",
    "HMGAdapter",
    # 소스
    "SamsungAdapter",
    "SKCareersAdapter",
    "TeslaKoreaAdapter",
    "NaverAdapter",
    "KakaoAdapter",
    "DaangnAdapter",
    "CoupangAdapter",
    "YanoljaAdapter",
    "HyundaiAdapter",
    "KiaAdapter",
    "LGAdapter",
    "TossAdapter",
    "LineAdapter",
    "WoowahanAdapter",
]
