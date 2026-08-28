#!/usr/bin/env python3
"""어댑터를 실제 사이트에 붙여 확인하는 로컬 도구.

    python scripts/verify.py tesla                  # 한 곳 실행
    python scripts/verify.py --all                  # 전부 실행
    python scripts/verify.py tesla --save-fixture   # 응답을 테스트 픽스처로 저장
    python scripts/verify.py tesla --json           # 파싱 결과를 JSON으로

개발 컨테이너는 egress가 제한돼 있어 여러 채용 사이트에 닿지 못한다.
이 스크립트는 네트워크가 열린 개인 장비에서 돌리는 걸 전제로 한다.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from jobping import registry  # noqa: E402
from jobping.companies import BY_KEY  # noqa: E402
from jobping.adapters import NeedsDiscovery  # noqa: E402
from jobping.http import Client, FetchError  # noqa: E402
from jobping.matching import display_name  # noqa: E402
from jobping.models import Job  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "tests" / "fixtures"

OK, SKIP, FAIL = "\033[32m✓\033[0m", "\033[33m–\033[0m", "\033[31m✗\033[0m"


def run_one(key: str, save_fixture: bool, as_json: bool, limit: int) -> str:
    adapter = registry.get(key)
    client = Client()
    if save_fixture:
        _patch_for_fixture(client, key)

    started = time.monotonic()
    try:
        jobs = adapter.fetch(client)
    except NeedsDiscovery as exc:
        print(f"{SKIP} {key:10s} 미설정 — {exc}")
        return "skipped"
    except (FetchError, Exception) as exc:  # noqa: BLE001 - 도구이므로 전부 보고
        print(f"{FAIL} {key:10s} 실패 — {type(exc).__name__}: {exc}")
        if not isinstance(exc, FetchError):
            traceback.print_exc()
        return "failed"
    finally:
        client.close()

    elapsed = (time.monotonic() - started) * 1000
    print(f"{OK} {key:10s} {len(jobs):4d}건  {elapsed:6.0f}ms"
          f"{'' if adapter.verified else '  (verified=False — 결과가 맞으면 True 로 올릴 것)'}")
    _report(jobs, as_json, limit)
    return "ok"


def _report(jobs: list[Job], as_json: bool, limit: int) -> None:
    if not jobs:
        print("   ⚠ 0건. 필터가 과한지, 엔드포인트가 빈 목록을 주는지 확인할 것.")
        return
    if as_json:
        print(json.dumps([j.to_item() for j in jobs[:limit]],
                         ensure_ascii=False, indent=2, default=str))
        return
    for job in jobs[:limit]:
        meta = " / ".join(filter(None, (job.location, job.employment_type)))
        print(f"   • [{display_name(job.company)}] {job.title[:60]}")
        if meta:
            print(f"     {meta}")
        if job.roles:
            shown = ", ".join(job.roles[:2])
            more = f" 외 {len(job.roles) - 2}개" if len(job.roles) > 2 else ""
            print(f"     직무: {shown[:80]}{more}")
        print(f"     {job.url}")
    if len(jobs) > limit:
        print(f"   … 외 {len(jobs) - limit}건 (--limit 로 더 보기)")

    # 중복 job_id 는 곧 알림 누락이다. 조용히 넘어가면 안 된다.
    ids = [j.job_id for j in jobs]
    if len(set(ids)) != len(ids):
        dupes = len(ids) - len(set(ids))
        print(f"   ⚠ job_id 중복 {dupes}건 — source_id 선택이 잘못됐을 수 있다.")

    urls = [j.url for j in jobs]
    if len(set(urls)) != len(urls):
        print(f"   ⚠ URL 중복 {len(urls) - len(set(urls))}건 — 링크가 전부 같은 곳으로 간다.")

    # 앱 회사 목록에 없는 계열사는 사용자가 구독할 수 없다.
    unknown = sorted({j.company for j in jobs if j.company not in BY_KEY})
    if unknown:
        print(f"   ⚠ 미등록 계열사 {len(unknown)}곳: {', '.join(unknown[:6])}")
        print("     companies.py 에 추가해야 앱에서 구독할 수 있다.")


def _patch_for_fixture(client: Client, key: str) -> None:
    """원본 응답을 tests/fixtures 에 떨궈서 오프라인 테스트에 쓰게 한다."""
    FIXTURES.mkdir(parents=True, exist_ok=True)
    original = client.request

    def wrapper(method: str, url: str, **kwargs):
        res = original(method, url, **kwargs)
        suffix = "json" if "json" in res.headers.get("content-type", "") else "html"
        path = FIXTURES / f"{key}.{suffix}"
        path.write_text(res.text, encoding="utf-8")
        print(f"   ↳ 픽스처 저장: {path.relative_to(FIXTURES.parents[2])}")
        return res

    client.request = wrapper  # type: ignore[method-assign]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("adapters", nargs="*", help=f"대상: {', '.join(registry.ADAPTERS)}")
    parser.add_argument("--all", action="store_true", help="등록된 어댑터 전부")
    parser.add_argument("--save-fixture", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    keys = list(registry.ADAPTERS) if args.all else args.adapters
    if not keys:
        parser.error("어댑터 이름을 주거나 --all 을 쓸 것")

    counts = {"ok": 0, "skipped": 0, "failed": 0}
    for key in keys:
        try:
            counts[run_one(key, args.save_fixture, args.json, args.limit)] += 1
        except KeyError as exc:
            print(f"{FAIL} {exc}")
            counts["failed"] += 1

    print(f"\n성공 {counts['ok']} / 미설정 {counts['skipped']} / 실패 {counts['failed']}")
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
