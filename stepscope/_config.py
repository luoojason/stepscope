from __future__ import annotations

import sys
import threading
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from stepscope.sqlite_buffer import SqliteBuffer


@dataclass
class StepScopeConfig:
    session_id: str
    buffer: "SqliteBuffer"


class _ConfigHolder:
    _instance: Optional[StepScopeConfig] = None
    _lock: threading.Lock = threading.Lock()

    def require(self) -> StepScopeConfig:
        if self._instance is None:
            raise RuntimeError(
                "stepscope not initialized. Call stepscope.init() first."
            )
        return self._instance

    def reset(self) -> None:
        with self._lock:
            self._instance = None


_CONFIG = _ConfigHolder()


def init(
    *,
    api_key: Optional[str] = None,
    local: bool = False,
    db_path: str = "./stepscope.db",
) -> None:
    import atexit

    from stepscope.sqlite_buffer import SqliteBuffer

    if not local and api_key is None:
        print(
            "stepscope: no api_key and local=False; events dropped. "
            "Pass local=True for SQLite or api_key=... for hosted.",
            file=sys.stderr,
        )
        return

    with _CONFIG._lock:
        buf = SqliteBuffer(db_path)
        _CONFIG._instance = StepScopeConfig(
            session_id=str(uuid.uuid4()),
            buffer=buf,
        )
        atexit.register(buf.flush)
