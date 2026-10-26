"""키워드 매칭.

원래 계획의 "제목에 키워드가 포함되면 알림"은 한국어 공고에서 그대로 쓰면
샌다. 실제로 부딪히는 문제들:

* 띄어쓰기가 제각각이다. "데브옵스", "Dev Ops", "DevOps", "dev-ops"
* 사용자는 한글로 넣고 공고는 영어로 나온다. "인프라" vs "Infrastructure"
* 경력직 앱인데 "신입/인턴" 공고가 계속 잡힌다

정규화 + 동의어 + 제외어 세 가지로 해결한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import re

from .companies import BY_KEY
from .models import Job, normalize_text, spaced_text

#: 한 그룹 안의 단어는 서로 같은 것으로 본다. 사용자가 어느 쪽을 넣든 매칭된다.
SYNONYM_GROUPS: tuple[tuple[str, ...], ...] = (
    ("devops", "데브옵스"),
    ("infra", "infrastructure", "인프라"),
    ("semiconductor", "반도체", "소자"),
    ("backend", "server", "백엔드", "서버"),
    ("frontend", "프론트엔드", "프론트"),
    ("ios", "아이오에스"),
    ("android", "안드로이드"),
    ("machinelearning", "ml", "머신러닝"),
    ("데이터엔지니어", "dataengineer"),
    ("보안", "security"),
    ("클라우드", "cloud"),
    ("플랫폼", "platform"),
    ("sre", "sitereliability"),
    ("qa", "품질", "quality"),
)

#: 경력직 알림 앱이므로 기본으로 걸러낸다. 사용자가 설정에서 끌 수 있게 한다.
DEFAULT_EXCLUDES: tuple[str, ...] = ("인턴", "intern", "신입공채", "체험형")

#: 1회 수집당 한 디바이스에 보낼 개별 푸시 최대 개수.
#: 넘으면 "새 공고 N건" 묶음 1건으로 대체한다. 상한이 없으면 채용 시즌에
#: 알림 20개가 한꺼번에 터지고, 사용자는 그날로 알림을 끈다.
MAX_PUSH_PER_RUN = 5

_SYNONYMS: dict[str, frozenset[str]] = {}
for _group in SYNONYM_GROUPS:
    _normalized = frozenset(normalize_text(w) for w in _group)
    for _word in _normalized:
        _SYNONYMS[_word] = _normalized


def expand(keyword: str) -> frozenset[str]:
    """키워드를 동의어 집합으로 넓힌다."""
    norm = normalize_text(keyword)
    return _SYNONYMS.get(norm, frozenset({norm})) if norm else frozenset()


# 영문 키워드는 **알파벳/숫자 경계**를 요구한다. 한국어는 요구하지 않는다.
#
# 이유는 두 언어가 다르게 붙기 때문이다. 한국어는 "반도체공정엔지니어"처럼
# 띄어쓰기 없이 합성되므로 부분문자열 매칭이 꼭 필요하다. 영어는 그렇지
# 않아서, 같은 규칙을 적용하면 엉뚱한 데 걸린다. 라이브 데이터에서 실제로
# 나온 것들:
#
#   "SRE"    가 "Sr. Employee Relation Specialist" 에 걸림 (Sr.+Employee)
#   "ML"     이 "HTML 퍼블리셔" 에 걸림
#   "intern" 이 "Internal Tools Engineer" 를 **제외어로** 걸러냄
#
# 마지막 것이 특히 나쁘다. 오탐은 알림 하나로 끝나지만, 잘못된 제외는 공고가
# 조용히 사라져서 아무도 눈치채지 못한다.
#
# 경계는 `\b` 가 아니라 "앞뒤가 영숫자가 아닐 것"으로 잡는다. 파이썬에서
# 한글은 `\w` 라서 `\b` 를 쓰면 "AI개발자" 의 "AI" 를 못 찾는다.

_ASCII_ONLY = re.compile(r"^[a-z0-9]+$")

#: 영문 키워드 뒤에 붙어도 같은 뜻으로 볼 어미들.
#: 경계만 엄격히 걸면 "engineer" 가 "Engineering" 을 놓친다. 영문 공고가
#: 전체의 절반 가까이라(쿠팡·테슬라) 그냥 두면 손실이 크다.
#: 이 목록에 "al" 은 없다 — 있으면 "intern" 이 "Internal" 을 다시 잡는다.
ASCII_SUFFIXES = ("s", "es", "ing", "er", "ers", "ed", "ment", "ments", "ship", "ships")


def _ascii_bounded(variant: str) -> re.Pattern:
    suffixes = "|".join(ASCII_SUFFIXES)
    return re.compile(
        rf"(?<![a-z0-9]){re.escape(variant)}(?:{suffixes})?(?![a-z0-9])"
    )


def _contains(variant: str, collapsed: str, spaced: str) -> bool:
    if not _ASCII_ONLY.match(variant):
        return variant in collapsed
    pattern = _ascii_bounded(variant)
    # 두 형태를 다 본다. 공백을 지운 형태에서만 보이는 것("Dev Ops" → devops)과
    # 공백을 남긴 형태에서만 보이는 것("…Engineer (SRE)" → … sre)이 둘 다 있다.
    return bool(pattern.search(spaced) or pattern.search(collapsed))


@dataclass(frozen=True, slots=True)
class MatchResult:
    job: Job
    keyword: str  # 사용자가 입력한 원래 표기. 알림 문구에 그대로 쓴다


def spaced_haystack(job: Job) -> str:
    """단어 경계 검사를 위한, 구분자를 공백으로만 바꾼 형태."""
    parts = (job.title, job.department, *job.roles)
    return spaced_text(" ".join(filter(None, parts)))


def haystack(job: Job) -> str:
    """매칭 대상 텍스트: 제목 + 부서 + 세부 직무.

    `roles`가 매칭 품질의 대부분을 만든다. 삼성 공고 제목은 "R&D분야 경력사원
    채용(DX부문)" 처럼 뭉뚱그려져 있고, 사용자가 찾는 "데이터 엔지니어링"은
    그 안에 묶인 세부 직무에 있다. 제목만 보면 거의 아무것도 걸리지 않는다.

    공고 본문은 보지 않는다. 저장하지 않기 때문이다(docs/PLAN.md 4절).
    """
    parts = (job.title, job.department, *job.roles)
    return normalize_text(" ".join(filter(None, parts)))


def match(
    job: Job,
    keywords: list[str],
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> MatchResult | None:
    """첫 번째로 걸리는 키워드를 돌려준다. 없으면 None.

    제외어가 먼저 적용된다. "DevOps 인턴"은 DevOps 키워드가 있어도 걸러진다.
    키워드가 비어 있으면 제외어만 거르고 전부 통과시킨다(keyword=""). 키워드는
    선택이다 — 안 넣은 사람은 고른 회사의 새 공고를 다 받는다.
    """
    collapsed = haystack(job)
    spaced = spaced_haystack(job)
    for raw in excludes:
        excluded = normalize_text(raw)
        if excluded and _contains(excluded, collapsed, spaced):
            return None
    if not keywords:
        return MatchResult(job=job, keyword="")
    for keyword in keywords:
        if any(_contains(v, collapsed, spaced) for v in expand(keyword)):
            return MatchResult(job=job, keyword=keyword)
    return None


def match_all(
    jobs: list[Job],
    keywords: list[str],
    companies: list[str] | None = None,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> list[MatchResult]:
    wanted = set(companies) if companies else None
    results = []
    for job in jobs:
        if wanted is not None and job.company not in wanted:
            continue
        hit = match(job, keywords, excludes)
        if hit:
            results.append(hit)
    return results


def notification_plan(results: list[MatchResult]) -> list[str]:
    """매칭 결과 → 실제로 보낼 알림 문구 목록.

    상한을 넘으면 개별 알림 대신 묶음 하나로 접는다.
    """
    if not results:
        return []
    if len(results) > MAX_PUSH_PER_RUN:
        companies = sorted({display_name(r.job.company) for r in results})
        return [f"새 공고 {len(results)}건 ({', '.join(companies)})"]
    return [f"[{display_name(r.job.company)}] {r.job.title}" for r in results]


def display_name(company_key: str) -> str:
    """알림에 쓸 회사 이름. 등록되지 않은 계열사는 키를 그대로 보여준다."""
    company = BY_KEY.get(company_key)
    return company.display_name if company else company_key
