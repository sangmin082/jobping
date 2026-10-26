"""앱이 쓰는 읽기/쓰기 API. API Gateway HTTP API → Lambda 하나에서 경로로 분기한다.

    POST /v1/devices     구독 정보 등록/갱신 (install_id 기준 upsert)
    GET  /v1/jobs        구독한 계열사들의 최신 공고, first_seen_at 내림차순
    GET  /v1/companies   구독 가능한 계열사 + 소스 헬스

인증은 아직 없다 — 로그인이 없고, 이 단계에서 돈이 걸린 엔드포인트도 없다.
남용 방어는 API Gateway 스로틀링 + `install_id` 형식 검사로 충분하다. 결제가
붙는 5단계에서 서명 헤더를 추가한다.

핸들러 로직은 `route()` 가 전부다. 이벤트를 흉내 낸 dict 로 테스트한다.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from . import registry
from .companies import BY_KEY
from .models import normalize_text
from .store import Store

MAX_LIMIT = 100
MAX_COMPANIES_PER_QUERY = 60
MAX_KEYWORD_LEN = 40
MAX_KEYWORDS = 20
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def route(store: Store, event: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    method = (event.get("requestContext", {}).get("http", {}).get("method") or event.get("httpMethod") or "GET").upper()
    path = event.get("rawPath") or event.get("path") or "/"
    query = event.get("queryStringParameters") or {}
    try:
        if method == "GET" and path == "/v1/companies":
            return _ok(get_companies(store))
        if method == "GET" and path == "/v1/jobs":
            return _ok(get_jobs(store, query))
        if method == "POST" and path == "/v1/devices":
            return _ok(put_device(store, _json_body(event), now))
        if method == "GET" and path == "/v1/health":
            return _ok({"ok": True})
        raise ApiError(404, f"no route for {method} {path}")
    except ApiError as exc:
        return _err(exc.status, exc.message)


# ---------------------------------------------------------------- handlers

def get_companies(store: Store) -> dict:
    health = {h["adapter"]: h for h in store.list_health()}
    items = []
    for c in registry.app_companies():
        h = health.get(c.source, {})
        items.append({
            "key": c.key, "display_name": c.display_name, "source": c.source,
            "group": _group_of(c.source),
            "last_success_at": h.get("last_success_at"),
            "last_fetched": _int(h.get("last_fetched")),
        })
    # free_tier 는 전면 무료 전에 나간 앱(빌드 12)이 필수 필드로 읽는다. 빼면 그 앱의
    # 회사 목록이 깨진다. 값은 API 입력 상한이라 그 앱에서도 사실상 제한이 없다.
    return {"companies": items, "free_tier": {"max_keywords": MAX_KEYWORDS,
                                                "max_companies": len(items)}}


def get_jobs(store: Store, query: dict) -> dict:
    raw = (query.get("companies") or "").strip()
    if not raw:
        raise ApiError(400, "companies 파라미터가 필요하다 (쉼표 구분 계열사 키)")
    companies = [c for c in raw.split(",") if c]
    unknown = [c for c in companies if c not in BY_KEY]
    if unknown:
        raise ApiError(400, f"모르는 계열사: {unknown[:5]}")
    if len(companies) > MAX_COMPANIES_PER_QUERY:
        raise ApiError(400, f"계열사는 한 번에 {MAX_COMPANIES_PER_QUERY}곳까지")
    limit = _limit(query.get("limit"))
    since = query.get("since") or None
    if since:
        try:
            datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise ApiError(400, "since 는 ISO8601 이어야 한다")

    rows: list[dict] = []
    for company in companies:
        rows.extend(store.query_jobs(company, limit=limit, since=since))
    rows.sort(key=lambda r: r.get("first_seen_at", ""), reverse=True)
    rows = rows[:limit]
    return {"jobs": [_public_job(r) for r in rows],
            "next_since": rows[0]["first_seen_at"] if rows else since}


def put_device(store: Store, body: dict, now: datetime) -> dict:
    install_id = str(body.get("install_id") or "")
    if not _UUID.match(install_id):
        raise ApiError(400, "install_id 는 UUID 여야 한다")
    keywords = _clean_keywords(body.get("keywords"))
    companies = _clean_companies(body.get("companies"))
    token = body.get("device_token")
    if token is not None and not re.fullmatch(r"[0-9a-fA-F]{32,200}", str(token)):
        raise ApiError(400, "device_token 형식이 잘못됐다")

    existing = store.get_device(install_id) or {}
    device = {
        **existing,
        "install_id": install_id,
        "keywords": keywords,
        "companies": companies,
        "push_enabled": bool(body.get("push_enabled", True)),
        "tier": existing.get("tier", "free"),   # 전면 무료라 쓰는 곳이 없다. 예전 앱 호환용으로만 둔다
        "updated_at": now.isoformat(),
        "created_at": existing.get("created_at", now.isoformat()),
        "app_version": str(body.get("app_version") or existing.get("app_version") or ""),
    }
    if token:
        device["device_token"] = str(token)
    store.put_device(device)
    tier = device["tier"]
    return {
        "install_id": install_id, "tier": tier,
        "effective": {"keywords": keywords, "companies": companies},
        "push_registered": bool(device.get("device_token")),
    }


# ---------------------------------------------------------------- helpers

def _clean_keywords(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(400, "keywords 는 배열이어야 한다")
    out: list[str] = []
    seen: set[str] = set()
    for k in raw:
        k = " ".join(str(k).split())
        if not k:
            continue
        if len(k) > MAX_KEYWORD_LEN:
            raise ApiError(400, f"키워드가 너무 길다: {k[:20]}…")
        # 매칭이 같은 것으로 보는 표기("Dev Ops"/"devops")는 하나로 센다.
        # 안 그러면 같은 키워드가 키워드 상한(20개)에서 두 자리를 차지한다.
        norm = normalize_text(k)
        if norm and norm not in seen:
            seen.add(norm)
            out.append(k)
    if len(out) > MAX_KEYWORDS:
        raise ApiError(400, f"키워드는 {MAX_KEYWORDS}개까지")
    return out


def _clean_companies(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ApiError(400, "companies 는 배열이어야 한다")
    out: list[str] = []
    for c in raw:
        c = str(c)
        if c not in BY_KEY:
            raise ApiError(400, f"모르는 계열사: {c}")
        if c not in out:
            out.append(c)
    return out


def _limit(raw) -> int:
    try:
        n = int(raw) if raw is not None else 50
    except ValueError:
        raise ApiError(400, "limit 은 정수여야 한다")
    return max(1, min(n, MAX_LIMIT))


def _public_job(row: dict) -> dict:
    return {k: _plain(row.get(k)) for k in (
        "company", "job_id", "title", "url", "posted_at", "first_seen_at",
        "location", "department", "employment_type", "roles",
    ) if row.get(k) is not None}


def _plain(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, list):
        return [_plain(x) for x in v]
    return v


def _int(v):
    return int(v) if isinstance(v, (int, Decimal)) else None


def _group_of(source: str) -> str:
    return registry.get(source).display_name


def _json_body(event: dict) -> dict:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64
        body = base64.b64decode(body).decode()
    try:
        data = json.loads(body)
    except ValueError:
        raise ApiError(400, "본문이 JSON 이 아니다")
    if not isinstance(data, dict):
        raise ApiError(400, "본문은 JSON 객체여야 한다")
    return data


def _ok(data: dict, status: int = 200) -> dict:
    return {"statusCode": status,
            "headers": {"content-type": "application/json; charset=utf-8",
                        "cache-control": "no-store"},
            "body": json.dumps(data, ensure_ascii=False, default=_plain)}


def _err(status: int, message: str) -> dict:
    return _ok({"error": message}, status)
