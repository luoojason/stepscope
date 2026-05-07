import sqlite3
import tempfile
import os
import pytest

import stepscope
from stepscope._config import _CONFIG
from stepscope.step import _current_step


@pytest.fixture(autouse=True)
def clean_config():
    yield
    _CONFIG.reset()
    _current_step.set(None)


def _init_tmp():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    stepscope.init(local=True, db_path=tmp.name)
    return tmp.name


def test_step_writes_row():
    db = _init_tmp()
    with stepscope.step("hello"):
        pass
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT name, status FROM step").fetchall()
    conn.close()
    os.unlink(db)
    assert rows == [("hello", "success")]


def test_sequential_steps_no_parent():
    db = _init_tmp()
    with stepscope.step("a"):
        pass
    with stepscope.step("b"):
        pass
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT name, parent_step_id FROM step ORDER BY started_at"
    ).fetchall()
    conn.close()
    os.unlink(db)
    assert rows == [("a", None), ("b", None)]


def test_nested_step_gets_parent_id():
    _init_tmp()
    with stepscope.step("outer") as outer:
        with stepscope.step("inner") as inner:
            pass
    assert inner.parent_step_id == outer.step_id


def test_explicit_parent_step_id_overrides_contextvar():
    _init_tmp()
    with stepscope.step("outer"):
        with stepscope.step("sibling", parent_step_id="explicit-id") as s:
            pass
    assert s.parent_step_id == "explicit-id"


def test_step_error_sets_status():
    db = _init_tmp()
    with pytest.raises(ValueError):
        with stepscope.step("boom"):
            raise ValueError("oops")
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT status, error FROM step WHERE name='boom'").fetchone()
    conn.close()
    os.unlink(db)
    assert row[0] == "error"
    assert "oops" in row[1]


def test_no_init_raises():
    with pytest.raises(RuntimeError, match="not initialized"):
        with stepscope.step("x"):
            pass
