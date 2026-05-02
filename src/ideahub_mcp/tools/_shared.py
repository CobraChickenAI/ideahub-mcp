from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel


class TaskContext(BaseModel):
    task_ref: str | None
    recent_ids: list[str]


def suggest_tags(conn: sqlite3.Connection, content: str, limit: int = 5) -> list[str]:
    rows = conn.execute("SELECT tags FROM idea WHERE tags != '[]'").fetchall()
    known: set[str] = set()
    for (tags_json,) in rows:
        try:
            known.update(json.loads(tags_json))
        except json.JSONDecodeError:
            continue
    lowered = content.lower()
    return sorted([t for t in known if t.lower() in lowered])[:limit]


def task_context(
    conn: sqlite3.Connection, task_ref: str | None, current_id: str
) -> TaskContext:
    if not task_ref:
        return TaskContext(task_ref=None, recent_ids=[])
    rows = conn.execute(
        "SELECT id FROM idea WHERE task_ref = ? AND id != ? "
        "ORDER BY created_at DESC LIMIT 10",
        (task_ref, current_id),
    ).fetchall()
    return TaskContext(task_ref=task_ref, recent_ids=[r[0] for r in rows])
