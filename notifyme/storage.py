from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunRecord:
    id: int
    name: str
    kind: str
    status: str
    detail: str
    started_at: str
    finished_at: str
    duration: float
    exit_code: int | None
    summary: str
    metrics: dict[str, Any]


class Storage:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self._init_schema()

    def start_run(self, name: str, kind: str, detail: str, params: dict[str, Any] | None = None) -> int:
        now = self._now()
        with self.lock, self._connection() as conn:
            cursor = conn.execute(
                """
                insert into task_runs(name, kind, status, detail, params, started_at)
                values (?, ?, ?, ?, ?, ?)
                """,
                (name, kind, "running", detail, json.dumps(params or {}, ensure_ascii=False), now),
            )
            run_id = int(cursor.lastrowid)
            conn.execute(
                "insert into task_events(run_id, event_type, message, created_at) values (?, ?, ?, ?)",
                (run_id, "started", detail, now),
            )
            return run_id

    def finish_run(
        self,
        run_id: int,
        status: str,
        summary: str,
        metrics: dict[str, Any] | None = None,
        exit_code: int | None = None,
    ) -> None:
        now = self._now()
        with self.lock, self._connection() as conn:
            row = conn.execute("select started_at from task_runs where id = ?", (run_id,)).fetchone()
            duration = 0.0
            if row:
                duration = max(0.0, (datetime.fromisoformat(now) - datetime.fromisoformat(row["started_at"])).total_seconds())
            conn.execute(
                """
                update task_runs
                set status = ?, finished_at = ?, duration = ?, exit_code = ?, summary = ?, metrics = ?
                where id = ?
                """,
                (status, now, duration, exit_code, summary, json.dumps(metrics or {}, ensure_ascii=False), run_id),
            )
            conn.execute(
                "insert into task_events(run_id, event_type, message, created_at) values (?, ?, ?, ?)",
                (run_id, status, summary, now),
            )

    def cancel_run(self, run_id: int, reason: str = "cancelled") -> None:
        self.finish_run(run_id, "cancelled", reason)

    def recent_runs(self, limit: int = 10) -> list[RunRecord]:
        with self.lock, self._connection() as conn:
            rows = conn.execute(
                """
                select * from task_runs
                order by id desc
                limit ?
                """,
                (limit,),
            ).fetchall()
        return [self._record(row) for row in rows]

    def find_runs(self, name: str, limit: int = 5) -> list[RunRecord]:
        with self.lock, self._connection() as conn:
            rows = conn.execute(
                """
                select * from task_runs
                where lower(name) = lower(?)
                order by id desc
                limit ?
                """,
                (name, limit),
            ).fetchall()
        return [self._record(row) for row in rows]

    def last_run(self) -> RunRecord | None:
        runs = self.recent_runs(1)
        return runs[0] if runs else None

    def get_setting(self, key: str, default: str = "") -> str:
        with self.lock, self._connection() as conn:
            row = conn.execute("select value from settings where key = ?", (key,)).fetchone()
            return str(row["value"]) if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.lock, self._connection() as conn:
            conn.execute(
                """
                insert into settings(key, value)
                values (?, ?)
                on conflict(key) do update set value = excluded.value
                """,
                (key, value),
            )

    def _init_schema(self) -> None:
        with self.lock, self._connection() as conn:
            conn.executescript(
                """
                create table if not exists task_runs (
                    id integer primary key autoincrement,
                    name text not null,
                    kind text not null,
                    status text not null,
                    detail text not null default '',
                    params text not null default '{}',
                    started_at text not null,
                    finished_at text not null default '',
                    duration real not null default 0,
                    exit_code integer,
                    summary text not null default '',
                    metrics text not null default '{}'
                );

                create index if not exists idx_task_runs_name on task_runs(name);
                create index if not exists idx_task_runs_status on task_runs(status);
                create index if not exists idx_task_runs_started_at on task_runs(started_at);

                create table if not exists task_events (
                    id integer primary key autoincrement,
                    run_id integer,
                    event_type text not null,
                    message text not null default '',
                    created_at text not null,
                    foreign key(run_id) references task_runs(id)
                );

                create table if not exists settings (
                    key text primary key,
                    value text not null
                );
                """
            )

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _record(row: sqlite3.Row) -> RunRecord:
        try:
            metrics = json.loads(row["metrics"] or "{}")
        except json.JSONDecodeError:
            metrics = {}
        return RunRecord(
            id=int(row["id"]),
            name=str(row["name"]),
            kind=str(row["kind"]),
            status=str(row["status"]),
            detail=str(row["detail"]),
            started_at=str(row["started_at"]),
            finished_at=str(row["finished_at"]),
            duration=float(row["duration"] or 0),
            exit_code=row["exit_code"],
            summary=str(row["summary"]),
            metrics=metrics,
        )
