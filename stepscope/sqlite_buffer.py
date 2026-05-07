from __future__ import annotations

import sqlite3
import threading
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from stepscope.step import Step

_DDL = """
CREATE TABLE IF NOT EXISTS session (
    session_id   TEXT PRIMARY KEY,
    user_id      TEXT,
    started_at   REAL NOT NULL,
    ended_at     REAL,
    metadata     TEXT
);
CREATE TABLE IF NOT EXISTS step (
    step_id         TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES session(session_id),
    parent_step_id  TEXT,
    name            TEXT NOT NULL,
    status          TEXT,
    started_at      REAL NOT NULL,
    ended_at        REAL,
    error           TEXT,
    attrs           TEXT
);
CREATE INDEX IF NOT EXISTS idx_step_session ON step(session_id);
CREATE INDEX IF NOT EXISTS idx_step_name    ON step(name);
"""


class SqliteBuffer:
    def __init__(self, db_path: str) -> None:
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(_DDL)
        self._conn.commit()

    def _ensure_session(self, session_id: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO session (session_id, started_at) VALUES (?, ?)",
            (session_id, time.time()),
        )

    def write_step_start(self, s: "Step") -> None:
        with self._lock:
            self._ensure_session(s.session_id)
            self._conn.execute(
                """INSERT INTO step
                   (step_id, session_id, parent_step_id, name, status, started_at)
                   VALUES (?, ?, ?, ?, 'in_progress', ?)""",
                (s.step_id, s.session_id, s.parent_step_id, s.name, time.time()),
            )
            self._conn.commit()

    def write_step_end(
        self, s: "Step", *, status: str, error: Optional[str] = None
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE step SET status=?, ended_at=?, error=? WHERE step_id=?",
                (status, time.time(), error, s.step_id),
            )
            self._conn.commit()

    def flush(self) -> None:
        with self._lock:
            self._conn.commit()
