from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional

from stepscope._config import _CONFIG
from stepscope._ids import new_step_id

_current_step: ContextVar[Optional["Step"]] = ContextVar(
    "stepscope_step", default=None
)


@dataclass
class Step:
    step_id: str
    session_id: str
    parent_step_id: Optional[str]
    name: str


@contextmanager
def step(name: str, *, parent_step_id: Optional[str] = None):
    cfg = _CONFIG.require()
    parent = parent_step_id or (
        _current_step.get().step_id if _current_step.get() else None
    )
    s = Step(
        step_id=new_step_id(),
        session_id=cfg.session_id,
        parent_step_id=parent,
        name=name,
    )
    cfg.buffer.write_step_start(s)
    token = _current_step.set(s)
    try:
        yield s
        cfg.buffer.write_step_end(s, status="success")
    except Exception as e:
        cfg.buffer.write_step_end(s, status="error", error=str(e))
        raise
    finally:
        _current_step.reset(token)


def trace(name: str):
    def deco(fn):
        def wrapper(*args, **kwargs):
            with step(name):
                return fn(*args, **kwargs)
        return wrapper
    return deco
