from __future__ import annotations

import hashlib
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
CREATE TABLE IF NOT EXISTS llm_call (
    span_id          TEXT PRIMARY KEY,
    step_id          TEXT NOT NULL,
    gen_ai_system    TEXT,
    gen_ai_model     TEXT,
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    latency_ms       REAL,
    response_hash    TEXT,
    response_preview TEXT,
    response_length  INTEGER,
    started_at       REAL NOT NULL,
    ended_at         REAL
);
CREATE INDEX IF NOT EXISTS idx_llm_step ON llm_call(step_id);
CREATE TABLE IF NOT EXISTS tool_call (
    span_id         TEXT PRIMARY KEY,
    step_id         TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    args_preview    TEXT,
    args_length     INTEGER,
    result_preview  TEXT,
    result_length   INTEGER,
    success         INTEGER,
    error           TEXT,
    latency_ms      REAL,
    started_at      REAL NOT NULL,
    ended_at        REAL
);
CREATE INDEX IF NOT EXISTS idx_tool_step ON tool_call(step_id);
"""

_PREVIEW_LEN = 200


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _preview(text: str) -> str:
    if len(text) <= _PREVIEW_LEN * 2:
        return text
    return text[:_PREVIEW_LEN] + "…" + text[-_PREVIEW_LEN:]


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
        self.write_step_end_by_id(s.step_id, status=status, error=error)

    def write_step_end_by_id(
        self, step_id: str, *, status: str, error: Optional[str] = None
    ) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE step SET status=?, ended_at=?, error=? WHERE step_id=?",
                (status, time.time(), error, step_id),
            )
            self._conn.commit()

    def write_llm_call(
        self,
        *,
        span_id: str,
        step_id: str,
        gen_ai_system: Optional[str],
        gen_ai_model: Optional[str],
        input_tokens: Optional[int],
        output_tokens: Optional[int],
        started_at: float,
        response_text: Optional[str] = None,
    ) -> None:
        ended_at = time.time()
        resp_hash = _hash(response_text) if response_text else None
        resp_preview = _preview(response_text) if response_text else None
        resp_len = len(response_text) if response_text else None
        latency = round((ended_at - started_at) * 1000, 2)
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO llm_call
                   (span_id, step_id, gen_ai_system, gen_ai_model,
                    input_tokens, output_tokens, latency_ms,
                    response_hash, response_preview, response_length,
                    started_at, ended_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (span_id, step_id, gen_ai_system, gen_ai_model,
                 input_tokens, output_tokens, latency,
                 resp_hash, resp_preview, resp_len,
                 started_at, ended_at),
            )
            self._conn.commit()

    def write_tool_call_start(
        self,
        *,
        span_id: str,
        step_id: str,
        tool_name: str,
        args_preview: Optional[str],
        args_length: int,
        started_at: float,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR IGNORE INTO tool_call
                   (span_id, step_id, tool_name, args_preview, args_length, started_at)
                   VALUES (?,?,?,?,?,?)""",
                (span_id, step_id, tool_name, args_preview, args_length, started_at),
            )
            self._conn.commit()

    def write_tool_call_end(
        self,
        *,
        span_id: str,
        success: bool,
        result_preview: Optional[str] = None,
        result_length: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        ended_at = time.time()
        with self._lock:
            row = self._conn.execute(
                "SELECT started_at FROM tool_call WHERE span_id=?", (span_id,)
            ).fetchone()
            latency = round((ended_at - row[0]) * 1000, 2) if row else None
            self._conn.execute(
                """UPDATE tool_call
                   SET success=?, result_preview=?, result_length=?,
                       error=?, latency_ms=?, ended_at=?
                   WHERE span_id=?""",
                (int(success), result_preview, result_length,
                 error, latency, ended_at, span_id),
            )
            self._conn.commit()

    def flush(self) -> None:
        with self._lock:
            self._conn.commit()
