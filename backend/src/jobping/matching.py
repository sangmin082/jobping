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

from .models import Job, normalize_text

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


@dataclass(frozen=True, slots=True)
class MatchResult:
    job: Job
    keyword: str  # 사용자가 입력한 원래 표기. 알림 문구에 그대로 쓴다


def haystack(job: Job) -> str:
    """매칭 대상 텍스트.

    제목과 부서만 본다. 공고 본문은 저장하지 않기 때문이다(저작권 및 앱스토어
    가이드라인 — docs/PLAN.md 4절).
    """
    return normalize_text(" ".join(filter(None, (job.title, job.department))))


def match(
    job: Job,
    keywords: list[str],
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> MatchResult | None:
    """첫 번째로 걸리는 키워드를 돌려준다. 없으면 None.

    제외어가 먼저 적용된다. "DevOps 인턴"은 DevOps 키워드가 있어도 걸러진다.
    """
    text = haystack(job)
    if any(normalize_text(x) in text for x in excludes if normalize_text(x)):
        return None
    for keyword in keywords:
        if any(variant in text for variant in expand(keyword)):
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
        companies = sorted({r.job.company for r in results})
        return [f"새 공고 {len(results)}건 ({', '.join(companies)})"]
    return [f"[{r.job.company}] {r.job.title}" for r in results]
