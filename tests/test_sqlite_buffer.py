import sqlite3
import tempfile
import os

from stepscope.sqlite_buffer import SqliteBuffer
from stepscope.step import Step


def _make_step(name: str, session_id: str = "sess-1", parent: str = None) -> Step:
    return Step(step_id=f"step-{name}", session_id=session_id, parent_step_id=parent, name=name)


def test_schema_created():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    SqliteBuffer(path)
    conn = sqlite3.connect(path)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    os.unlink(path)
    assert {"session", "step"} <= tables


def test_write_start_and_end():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    buf = SqliteBuffer(path)
    s = _make_step("parse")
    buf.write_step_start(s)
    buf.write_step_end(s, status="success")
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT name, status FROM step WHERE step_id=?", (s.step_id,)).fetchone()
    conn.close()
    os.unlink(path)
    assert row == ("parse", "success")


def test_error_status_written():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    buf = SqliteBuffer(path)
    s = _make_step("fail")
    buf.write_step_start(s)
    buf.write_step_end(s, status="error", error="timeout")
    conn = sqlite3.connect(path)
    row = conn.execute("SELECT status, error FROM step WHERE step_id=?", (s.step_id,)).fetchone()
    conn.close()
    os.unlink(path)
    assert row == ("error", "timeout")
