"""공고 도메인 모델.

핵심 설계 결정 두 가지:

1. **`first_seen_at`이 "신규" 판정의 기준이다.** `posted_at`이 아니다.
   테슬라 API는 게시일을 아예 주지 않고, 어떤 사이트는 공고를 수정할 때
   게시일을 갱신해버린다. 우리가 처음 본 시각만이 신뢰할 수 있다.

2. **`job_id`는 URL 정규화 뒤에 계산한다.** 채용 페이지 URL에는 유입 경로
   추적 파라미터가 자주 붙는데, 그걸 그대로 해시에 넣으면 같은 공고가 매
   수집마다 신규로 잡혀서 알림이 폭주한다.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 값이 바뀌어도 같은 공고를 가리키는, 버려도 되는 쿼리 파라미터들.
_TRACKING_PARAMS = re.compile(
    r"^(utm_|_ga|gclid|fbclid|msclkid|ref|referrer|source|src|from|"
    r"jsessionid|phpsessid|sid|sessionid|cid|trk|trackingid)",
    re.IGNORECASE,
)


def clean_url(url: str) -> str:
    """저장하고 사용자에게 링크로 보여줄 URL.

    추적 파라미터만 걷어내고 경로와 프래그먼트는 **그대로 둔다.** 프래그먼트를
    지우면 해시 라우팅 SPA에서 링크가 망가진다 — MokaHR(테슬라) 공고 주소는
    `.../100000166#/job/{id}` 라서 `#` 뒤가 곧 공고 식별자다. 경로의 끝
    슬래시도 건드리지 않는다. 서버에 따라 `/hr/` 와 `/hr` 가 다르게 동작한다.
    """
    parts = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not _TRACKING_PARAMS.match(k)
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path,
                       urlencode(query), parts.fragment))


def identity_url(url: str) -> str:
    """`job_id` 해시에만 쓰는 정규화 형태. 사용자에게 보여주지 않는다.

    같은 공고를 가리키는 표기 차이를 하나로 모으는 게 목적이라, 표시용보다
    공격적으로 정규화한다. 프래그먼트는 남긴다 — SPA에서는 그게 경로다.
    """
    parts = urlsplit(clean_url(url))
    query = sorted(parse_qsl(parts.query, keep_blank_values=True))
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                       urlencode(query), parts.fragment))


def normalize_text(text: str) -> str:
    """비교용 정규화: NFKC → 소문자 → 공백/구분자 제거.

    'Dev Ops', 'DevOps', 'dev-ops', 'ＤｅｖＯｐｓ'가 모두 같아진다.
    한국어 공고 제목은 띄어쓰기가 제각각이라 이 단계가 없으면 매칭이 샌다.
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[\s\-_./·ㆍ,()\[\]]+", "", text)


@dataclass(frozen=True, slots=True)
class Job:
    company: str
    title: str
    url: str
    job_id: str
    posted_at: datetime | None = None
    location: str | None = None
    department: str | None = None
    employment_type: str | None = None
    source_id: str | None = None
    #: 공고 하나가 여러 세부 직무를 묶고 있는 경우의 직무명들.
    #: 삼성 공고 하나에는 "[Big Data센터] SW개발 (데이터 엔지니어링)" 같은
    #: 세부 직무가 10여 개 붙어 있고, 사용자가 찾는 키워드는 제목이 아니라
    #: 여기에 있다. 매칭 품질이 이 필드에 크게 좌우된다.
    roles: tuple[str, ...] = ()

    @classmethod
    def make(
        cls,
        *,
        company: str,
        title: str,
        url: str,
        source_id: str | None = None,
        posted_at: datetime | None = None,
        location: str | None = None,
        department: str | None = None,
        employment_type: str | None = None,
        roles: tuple[str, ...] = (),
    ) -> "Job":
        title = " ".join(title.split())
        if not title:
            raise ValueError(f"{company}: 제목이 비어 있는 공고")
        url = clean_url(url)
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"{company}: 절대 URL이 아님 — {url!r}")

        # 사이트가 주는 고유 ID가 있으면 그걸 쓴다. 제목이 수정돼도 같은
        # 공고로 남는다. 없을 때만 URL+제목으로 대체한다.
        seed = source_id if source_id else f"{identity_url(url)}|{normalize_text(title)}"
        job_id = hashlib.sha1(f"{company}|{seed}".encode()).hexdigest()[:16]

        return cls(
            company=company,
            title=title,
            url=url,
            job_id=job_id,
            posted_at=posted_at,
            location=location,
            department=department,
            employment_type=employment_type,
            source_id=source_id,
            roles=tuple(" ".join(r.split()) for r in roles if r and r.strip()),
        )

    def to_item(self, first_seen_at: datetime | None = None) -> dict:
        """DynamoDB `jobs` 테이블에 넣을 형태."""
        seen = first_seen_at or datetime.now(timezone.utc)
        item = {k: v for k, v in asdict(self).items() if v is not None}
        item["posted_at"] = self.posted_at.isoformat() if self.posted_at else None
        item["roles"] = list(self.roles)
        item["first_seen_at"] = seen.isoformat()
        item["expires_at"] = int(seen.timestamp()) + 90 * 24 * 3600
        return {k: v for k, v in item.items() if v is not None and v != []}
