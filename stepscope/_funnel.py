from __future__ import annotations

import sqlite3
import time
from typing import Optional


def _since_to_epoch(since: str) -> Optional[float]:
    if since == "all":
        return None
    units = {"h": 3600, "d": 86400}
    unit = since[-1]
    if unit not in units:
        raise ValueError(f"Unknown since unit {since!r}. Use '24h', '7d', or 'all'.")
    return time.time() - int(since[:-1]) * units[unit]


def render_funnel(db_path: str, *, since: str = "24h") -> str:
    since_epoch = _since_to_epoch(since)
    conn = sqlite3.connect(db_path)
    try:
        if since_epoch is not None:
            rows = conn.execute(
                """SELECT name, COUNT(DISTINCT session_id) AS n
                   FROM step WHERE started_at >= ?
                   GROUP BY name ORDER BY MIN(started_at)""",
                (since_epoch,),
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM step WHERE started_at >= ?",
                (since_epoch,),
            ).fetchone()[0]
        else:
            rows = conn.execute(
                """SELECT name, COUNT(DISTINCT session_id) AS n
                   FROM step GROUP BY name ORDER BY MIN(started_at)""",
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(DISTINCT session_id) FROM step"
            ).fetchone()[0]
    finally:
        conn.close()

    if not rows:
        return f"No data (since={since})"

    max_n = max(n for _, n in rows)
    bar_width = 16
    lines = [f"Step funnel (last {since}, {total} sessions)", "─" * 52]
    for name, n in rows:
        pct = round(100 * n / total) if total else 0
        filled = round(bar_width * n / max_n) if max_n else 0
        bar = "█" * filled
        lines.append(f"{name:<22} {bar:<{bar_width}}  {n} ({pct}%)")
    return "\n".join(lines)
