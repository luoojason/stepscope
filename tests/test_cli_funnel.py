import sqlite3
import tempfile
import os
import time

from stepscope._funnel import render_funnel


def _make_db_with_steps(steps: list[tuple[str, str]]) -> str:
    """Create a temp SQLite DB with the given (session_id, step_name) pairs."""
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    conn = sqlite3.connect(f.name)
    conn.executescript("""
        CREATE TABLE session (session_id TEXT PRIMARY KEY, started_at REAL NOT NULL);
        CREATE TABLE step (
            step_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            parent_step_id TEXT, name TEXT NOT NULL,
            status TEXT, started_at REAL NOT NULL, ended_at REAL, error TEXT, attrs TEXT
        );
    """)
    now = time.time()
    sessions = {sid for sid, _ in steps}
    for sid in sessions:
        conn.execute("INSERT INTO session VALUES (?, ?)", (sid, now))
    for i, (sid, name) in enumerate(steps):
        conn.execute(
            "INSERT INTO step VALUES (?,?,NULL,?,'success',?,?,NULL,NULL)",
            (f"step-{i}", sid, name, now + i * 0.001, now + i * 0.001 + 0.0001),
        )
    conn.commit()
    conn.close()
    return f.name


def test_funnel_two_steps_one_session():
    db = _make_db_with_steps([("s1", "hello"), ("s1", "world")])
    output = render_funnel(db, since="all")
    os.unlink(db)
    assert "hello" in output
    assert "world" in output
    assert "100%" in output


def test_funnel_drop_off():
    steps = [
        ("s1", "parse"), ("s1", "retrieve"), ("s1", "respond"),
        ("s2", "parse"), ("s2", "retrieve"),
        ("s3", "parse"),
    ]
    db = _make_db_with_steps(steps)
    output = render_funnel(db, since="all")
    os.unlink(db)
    assert "parse" in output
    assert "100%" in output  # parse: 3/3
    assert "67%" in output   # retrieve: 2/3
    assert "33%" in output   # respond: 1/3


def test_funnel_no_data():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    conn = sqlite3.connect(f.name)
    conn.executescript("""
        CREATE TABLE session (session_id TEXT PRIMARY KEY, started_at REAL NOT NULL);
        CREATE TABLE step (
            step_id TEXT PRIMARY KEY, session_id TEXT NOT NULL,
            parent_step_id TEXT, name TEXT NOT NULL,
            status TEXT, started_at REAL NOT NULL, ended_at REAL, error TEXT, attrs TEXT
        );
    """)
    conn.commit()
    conn.close()
    output = render_funnel(f.name, since="all")
    os.unlink(f.name)
    assert "No data" in output
