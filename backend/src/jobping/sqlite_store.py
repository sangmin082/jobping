"""SQLite 저장소 — 서버 한 대(오라클 VM)에서 돌 때 DynamoDB 대신 쓴다.

`Store` 인터페이스를 그대로 구현하므로 collector/notifier/api 는 바뀌지 않는다.
DynamoDB 의 조건부 쓰기는 `INSERT OR IGNORE` + `rowcount` 로 옮겼다 — 행이
들어갔으면 1, 이미 있었으면 0 이다. 같은 의미(신규 판정, 중복 발송 방지)를
한 문장으로 보장한다.

동시성: API 서버(스레드 여럿)와 수집 타이머(별도 프로세스)가 같은 파일을
연다. WAL 모드면 읽기와 쓰기가 서로 막지 않고, 쓰기끼리는 busy_timeout 동안
기다린다. 연결 하나를 스레드들이 나눠 쓰므로 잠금으로 감싼다.

TTL: DynamoDB 처럼 자동 삭제가 없어서 `purge_expired()` 를 수집 시작 때 부른다.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime
from typing import Iterable

from .models import Job
from .store import DELIVERY_TTL

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    company       TEXT NOT NULL,
    job_id        TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    expires_at    INTEGER NOT NULL,
    data          TEXT NOT NULL,
    PRIMARY KEY (company, job_id)
);
-- 회사별 최신순 목록. DynamoDB 의 LSI by_first_seen 에 해당한다.
CREATE INDEX IF NOT EXISTS jobs_by_first_seen ON jobs (company, first_seen_at);

CREATE TABLE IF NOT EXISTS devices (
    install_id   TEXT PRIMARY KEY,
    push_enabled INTEGER NOT NULL DEFAULT 1,
    data         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    install_id TEXT NOT NULL,
    job_id     TEXT NOT NULL,
    status     TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    data       TEXT NOT NULL,
    PRIMARY KEY (install_id, job_id)
);
CREATE INDEX IF NOT EXISTS deliveries_by_status ON deliveries (status);

CREATE TABLE IF NOT EXISTS health (
    adapter TEXT PRIMARY KEY,
    data    TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, timeout=30, check_same_thread=False,
                                   isolation_level=None)  # autocommit; 트랜잭션은 명시적으로
        self._db.row_factory = sqlite3.Row
        with self._lock:
            if path != ":memory:":
                self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA busy_timeout=30000")
            self._db.execute("PRAGMA synchronous=NORMAL")
            self._db.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._db.execute(sql, params)

    def _all(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._db.execute(sql, params).fetchall()

    # ------------------------------------------------------------ jobs

    def put_job_if_new(self, job: Job, now: datetime) -> bool:
        item = job.to_item(now)
        cur = self._exec(
            "INSERT OR IGNORE INTO jobs (company, job_id, first_seen_at, expires_at, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (item["company"], item["job_id"], item["first_seen_at"], item["expires_at"],
             json.dumps(item, ensure_ascii=False)),
        )
        return cur.rowcount == 1

    def get_jobs(self, keys: Iterable[tuple[str, str]]) -> list[dict]:
        out = []
        for company, job_id in keys:
            rows = self._all("SELECT data FROM jobs WHERE company = ? AND job_id = ?",
                             (company, job_id))
            out.extend(json.loads(r["data"]) for r in rows)
        return out

    def query_jobs(self, company: str, *, limit: int, since: str | None = None) -> list[dict]:
        if since:
            rows = self._all(
                "SELECT data FROM jobs WHERE company = ? AND first_seen_at > ? "
                "ORDER BY first_seen_at DESC LIMIT ?", (company, since, limit))
        else:
            rows = self._all(
                "SELECT data FROM jobs WHERE company = ? ORDER BY first_seen_at DESC LIMIT ?",
                (company, limit))
        return [json.loads(r["data"]) for r in rows]

    # ------------------------------------------------------------ devices

    def list_devices(self) -> list[dict]:
        rows = self._all("SELECT data FROM devices WHERE push_enabled = 1")
        return [json.loads(r["data"]) for r in rows]

    def get_device(self, install_id: str) -> dict | None:
        rows = self._all("SELECT data FROM devices WHERE install_id = ?", (install_id,))
        return json.loads(rows[0]["data"]) if rows else None

    def put_device(self, device: dict) -> None:
        self._exec(
            "INSERT INTO devices (install_id, push_enabled, data) VALUES (?, ?, ?) "
            "ON CONFLICT(install_id) DO UPDATE SET push_enabled = excluded.push_enabled, "
            "data = excluded.data",
            (device["install_id"], 1 if device.get("push_enabled", True) else 0,
             json.dumps(device, ensure_ascii=False)),
        )

    def delete_device(self, install_id: str) -> None:
        self._exec("DELETE FROM devices WHERE install_id = ?", (install_id,))

    # ------------------------------------------------------------ deliveries

    def claim_delivery(self, install_id: str, job_id: str, status: str,
                       now: datetime, extra: dict | None = None) -> bool:
        record = {"install_id": install_id, "job_id": job_id, "status": status,
                  "created_at": now.isoformat(), **(extra or {})}
        cur = self._exec(
            "INSERT OR IGNORE INTO deliveries (install_id, job_id, status, expires_at, data) "
            "VALUES (?, ?, ?, ?, ?)",
            (install_id, job_id, status, int((now + DELIVERY_TTL).timestamp()),
             json.dumps(record, ensure_ascii=False)),
        )
        return cur.rowcount == 1

    def list_pending_deliveries(self) -> list[dict]:
        rows = self._all("SELECT data FROM deliveries WHERE status = 'pending'")
        return [json.loads(r["data"]) for r in rows]

    def mark_delivery_sent(self, install_id: str, job_id: str, now: datetime) -> None:
        rows = self._all("SELECT data FROM deliveries WHERE install_id = ? AND job_id = ?",
                         (install_id, job_id))
        if not rows:
            return
        record = json.loads(rows[0]["data"])
        record.update(status="sent", sent_at=now.isoformat())
        self._exec("UPDATE deliveries SET status = 'sent', data = ? "
                   "WHERE install_id = ? AND job_id = ?",
                   (json.dumps(record, ensure_ascii=False), install_id, job_id))

    # ------------------------------------------------------------ health

    def get_health(self, adapter: str) -> dict | None:
        rows = self._all("SELECT data FROM health WHERE adapter = ?", (adapter,))
        return json.loads(rows[0]["data"]) if rows else None

    def put_health(self, adapter: str, record: dict) -> None:
        self._exec(
            "INSERT INTO health (adapter, data) VALUES (?, ?) "
            "ON CONFLICT(adapter) DO UPDATE SET data = excluded.data",
            (adapter, json.dumps(record, ensure_ascii=False)),
        )

    def list_health(self) -> list[dict]:
        rows = self._all("SELECT adapter, data FROM health")
        return [{"adapter": r["adapter"], **json.loads(r["data"])} for r in rows]

    # ------------------------------------------------------------ 유지보수

    def purge_expired(self, now: datetime) -> tuple[int, int]:
        """DynamoDB TTL 을 대신한다. (지운 공고 수, 지운 발송 기록 수)."""
        ts = int(now.timestamp())
        jobs = self._exec("DELETE FROM jobs WHERE expires_at < ?", (ts,)).rowcount
        deliveries = self._exec("DELETE FROM deliveries WHERE expires_at < ?", (ts,)).rowcount
        return jobs, deliveries

    def counts(self) -> dict[str, int]:
        return {t: self._all(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]
                for t in ("jobs", "devices", "deliveries", "health")}
