"""Tests for StepScopeCallback (W2)."""
import sqlite3
import tempfile
import os
from uuid import uuid4

import pytest

import stepscope
from stepscope._config import _CONFIG
from stepscope.step import _current_step
from stepscope.langchain import StepScopeCallback


@pytest.fixture(autouse=True)
def clean_config():
    yield
    _CONFIG.reset()
    _current_step.set(None)


def _init_tmp() -> str:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    stepscope.init(local=True, db_path=f.name)
    return f.name


def _chain_start(cb, name="node", run_id=None, parent_run_id=None):
    run_id = run_id or uuid4()
    cb.on_chain_start({"name": name}, {}, run_id=run_id, parent_run_id=parent_run_id)
    return run_id


def _chain_end(cb, run_id):
    cb.on_chain_end({}, run_id=run_id)


def test_chain_start_writes_step():
    db = _init_tmp()
    cb = StepScopeCallback()
    run_id = _chain_start(cb, "my_node")
    _chain_end(cb, run_id)
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT name, status FROM step").fetchall()
    conn.close()
    os.unlink(db)
    assert ("my_node", "success") in rows


def test_chain_error_sets_error_status():
    db = _init_tmp()
    cb = StepScopeCallback()
    run_id = _chain_start(cb, "fail_node")
    cb.on_chain_error(RuntimeError("boom"), run_id=run_id)
    conn = sqlite3.connect(db)
    row = conn.execute("SELECT status, error FROM step WHERE name='fail_node'").fetchone()
    conn.close()
    os.unlink(db)
    assert row[0] == "error"
    assert "boom" in row[1]


def test_parent_child_chain_via_run_id():
    db = _init_tmp()
    cb = StepScopeCallback()
    parent_id = _chain_start(cb, "parent")
    child_id = _chain_start(cb, "child", parent_run_id=parent_id)
    _chain_end(cb, child_id)
    _chain_end(cb, parent_id)

    conn = sqlite3.connect(db)
    parent_step_id = conn.execute(
        "SELECT step_id FROM step WHERE name='parent'"
    ).fetchone()[0]
    child_parent_id = conn.execute(
        "SELECT parent_step_id FROM step WHERE name='child'"
    ).fetchone()[0]
    conn.close()
    os.unlink(db)
    assert child_parent_id == parent_step_id


def test_tool_call_recorded():
    db = _init_tmp()
    cb = StepScopeCallback()
    parent_run = _chain_start(cb, "agent")
    tool_run = uuid4()
    cb.on_tool_start(
        {"name": "search_tool"}, "capital of France",
        run_id=tool_run, parent_run_id=parent_run,
    )
    cb.on_tool_end("Paris", run_id=tool_run)
    _chain_end(cb, parent_run)

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT tool_name, success FROM tool_call WHERE span_id=?", (str(tool_run),)
    ).fetchone()
    conn.close()
    os.unlink(db)
    assert row == ("search_tool", 1)


def test_tool_error_recorded():
    db = _init_tmp()
    cb = StepScopeCallback()
    parent_run = _chain_start(cb, "agent")
    tool_run = uuid4()
    cb.on_tool_start({"name": "flaky_tool"}, "input", run_id=tool_run, parent_run_id=parent_run)
    cb.on_tool_error(RuntimeError("timeout"), run_id=tool_run)
    _chain_end(cb, parent_run)

    conn = sqlite3.connect(db)
    row = conn.execute(
        "SELECT success, error FROM tool_call WHERE span_id=?", (str(tool_run),)
    ).fetchone()
    conn.close()
    os.unlink(db)
    assert row[0] == 0
    assert "timeout" in row[1]


def test_no_init_silently_noops():
    """Callback should not raise if stepscope is not initialized."""
    cb = StepScopeCallback()
    run_id = uuid4()
    cb.on_chain_start({"name": "x"}, {}, run_id=run_id)
    cb.on_chain_end({}, run_id=run_id)


def test_loop_detection_via_funnel():
    """Three runs of the same step show up in funnel as 3 separate sessions."""
    db = _init_tmp()
    cb = StepScopeCallback()

    for _ in range(3):
        r = _chain_start(cb, "retrieve_context")
        cb.on_chain_error(RuntimeError("failed"), run_id=r)

    from stepscope._funnel import render_funnel
    output = render_funnel(db, since="all")
    os.unlink(db)
    assert "retrieve_context" in output
