"""회사(계열사) 레지스트리.

삼성·SK는 **그룹 통합 채용 포털**을 쓴다. 즉 수집 소스 하나가 계열사 수십
곳의 공고를 함께 내보낸다. 그래서 "수집 소스"와 "회사"는 1:1이 아니다:

    소스 samsung   → 삼성전자 DX부문, 삼성전자 DS부문, 삼성SDI, … (26곳)
    소스 skcareers → SK하이닉스, SK텔레콤, SK이노베이션, … (27곳)
    소스 tesla_kr  → 테슬라 코리아 (1곳)

사용자가 고르는 단위는 계열사이지 그룹이 아니다. 반도체 공고를 원하는
사람에게 삼성생명 공고를 보내면 안 된다. 그래서 `Job.company`는 계열사
키이고, DynamoDB 파티션 키도 이걸 쓴다.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Company:
    key: str           # 'samsung_ds' — 앱과 DB가 쓰는 안정적인 식별자
    display_name: str  # '삼성전자 DS부문'
    source: str        # 이 회사를 내보내는 어댑터 키
    code: str = ""     # 소스 쪽 원본 코드 (삼성 strCompany 등)
    #: 소스가 같은 회사를 다르게 부르는 표기들.
    #: SK 포털은 Accept-Language 에 따라 회사명을 한국어/영어로 바꿔 준다.
    aliases: tuple[str, ...] = ()


def slugify(name: str) -> str:
    """소스가 새 계열사를 추가해도 수집이 멈추지 않게 하는 대체 키.

    아래 목록에 없는 회사가 나와도 공고는 그대로 저장된다. 다만 앱의 회사
    선택 목록에는 노출되지 않는다(사람이 한 번 확인하고 등록해야 한다).
    """
    text = unicodedata.normalize("NFKC", name).strip().lower()
    return re.sub(r"[^a-z0-9가-힣]+", "_", text).strip("_")


# 삼성 — strCompany 코드는 채용 포털의 필터 체크박스에서 그대로 가져왔다.
SAMSUNG: tuple[Company, ...] = tuple(
    Company(key=key, display_name=name, source="samsung", code=code)
    for key, name, code in (
        ("samsung_dx", "삼성전자 DX부문", "C10CAA"),
        ("samsung_ds", "삼성전자 DS부문", "C10CAH"),
        ("samsung_display", "삼성디스플레이", "C90"),
        ("samsung_sdi", "삼성SDI", "C31"),
        ("samsung_electro", "삼성전기", "C40"),
        ("samsung_sds", "삼성SDS", "C60"),
        ("samsung_biologics", "삼성바이오로직스", "DA0"),
        ("samsung_bioepis", "삼성바이오에피스", "DB0"),
        ("samsung_life", "삼성생명", "E11"),
        ("samsung_fire", "삼성화재", "E21"),
        ("samsung_card", "삼성카드", "E31"),
        ("samsung_securities", "삼성증권", "E40"),
        ("samsung_am", "삼성자산운용", "EF0"),
        ("samsung_heavy", "삼성중공업", "D60"),
        ("samsung_ena", "삼성E&A", "D80"),
        ("samsung_ct_const", "삼성물산 건설부문", "B12"),
        ("samsung_ct_trading", "삼성물산 상사부문", "B11"),
        ("samsung_ct_resort", "삼성물산 리조트부문", "E71"),
        ("samsung_ct_fashion", "삼성물산 패션부문", "E7A"),
        ("hotel_shilla", "호텔신라", "E50"),
        ("cheil", "제일기획", "E60"),
        ("s1", "에스원", "E80"),
        ("smc", "삼성서울병원", "EA0"),
        ("samsung_welstory", "삼성웰스토리", "WCW"),
        ("samsung_sales", "삼성전자판매", "WBG"),
        ("sgr", "삼성글로벌리서치", "M20"),
    )
)

# SK — 소스가 코드가 아니라 회사명을 준다. 그 회사명은 요청 언어에 따라
# 한국어/영어로 달라지므로 두 표기를 모두 등록한다.
SK: tuple[Company, ...] = tuple(
    Company(key=key, display_name=name, source="skcareers", aliases=(en,))
    for key, name, en in (
        ("sk_hynix", "SK하이닉스", "SK hynix"),
        ("sk_telecom", "SK텔레콤", "SK telecom"),
        ("sk_innovation", "SK이노베이션", "SK innovation"),
        ("sk_on", "SK온", "SK on"),
        ("sk_broadband", "SK브로드밴드", "SK broadband"),
        ("sk_inc_ax", "SK주식회사(AX)", "SK inc.(AX)"),
        ("sk_siltron", "SK실트론", "SK siltron"),
        ("sk_keyfoundry", "SK키파운드리", "SK keyfoundry"),
        ("sk_ecoplant", "SK에코플랜트", "SK ecoplant"),
        ("sk_enmove", "SK엔무브", "SK enmove"),
        ("sk_gas", "SK가스", "SK gas"),
        ("sk_signet", "SK시그넷", "SK signet"),
        ("sk_biopharm", "SK바이오팜", "SK biopharmaceuticals"),
        ("sk_bioscience", "SK바이오사이언스", "SK bioscience"),
        ("sk_chemicals", "SK케미칼", "SK chemicals"),
        ("sk_airplus", "SK에어플러스", "SK airplus"),
        ("sk_plasma", "SK플라즈마", "SK plasma"),
        ("sk_oceanplant", "SK오션플랜트", "SK oceanplant"),
        ("sk_ons", "SK오앤에스", "SK ons"),
        ("sk_forest", "SK임업", "SK forest"),
        ("sk_leaveo", "SK리비오", "SK Leaveo"),
        ("tmap", "티맵모빌리티", "Tmap Mobility"),
        ("isc", "아이에스시", "ISC"),
        ("ige", "아이지이", "IGE"),
        ("ensolve", "엔솔브(주)", "EnSolve Co.,Ltd"),
        ("hweechan", "휘찬", "Hweechan Co.,Ltd."),
    )
)

TESLA: tuple[Company, ...] = (
    Company(key="tesla_kr", display_name="테슬라 코리아", source="tesla_kr"),
)

ALL: tuple[Company, ...] = SAMSUNG + SK + TESLA

BY_KEY: dict[str, Company] = {c.key: c for c in ALL}

#: 소스가 주는 식별자 → 회사 키. 소스마다 코드를 주기도 하고(삼성 strCompany)
#: 표시명을 주기도 해서(삼성 목록 HTML의 회사명, SK corpName) 둘 다 등록한다.
#: 소스별로 분리해야 서로 다른 그룹의 코드가 겹쳐도 안전하다.
_BY_CODE: dict[tuple[str, str], str] = {}
for _c in ALL:
    for _id in (_c.code, _c.display_name, *_c.aliases):
        if _id:
            _BY_CODE.setdefault((_c.source, _id), _c.key)


def resolve(source: str, code: str, fallback_name: str = "") -> str:
    """소스가 준 코드/이름을 회사 키로 바꾼다.

    등록되지 않은 계열사는 슬러그로 대체한다. 그룹이 계열사를 추가했다고
    수집이 멈추면 안 되기 때문이다.
    """
    key = _BY_CODE.get((source, code))
    if key:
        return key
    # SK는 "SK chemicals(LS)"처럼 괄호로 사업부를 덧붙인다. 앞부분으로 재시도.
    trimmed = code.split("(")[0].strip()
    if trimmed != code:
        key = _BY_CODE.get((source, trimmed))
        if key:
            return key
    return slugify(code or fallback_name) or f"{source}_unknown"
