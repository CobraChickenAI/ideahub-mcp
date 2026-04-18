from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel, Field, field_validator

from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.coerce import coerce_str_list
from ideahub_mcp.util.ids import new_ulid


class CaptureInput(BaseModel):
    content: str = Field(..., min_length=1)
    scope: str
    actor: str
    originator: str | None = None
    tags: list[str] = Field(default_factory=list)
    actor_created: bool = False
    task_ref: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: object) -> list[str]:
        return coerce_str_list(v)


class CaptureOutput(BaseModel):
    id: str
    scope: str
    actor: str
    originator: str | None
    created_at: str
    suggested_tags: list[str]
    actor_created: bool = False
    task_ref: str | None = None


IDEMPOTENCY_SECONDS = 5


def _suggest_tags(conn: sqlite3.Connection, content: str, limit: int = 5) -> list[str]:
    rows = conn.execute("SELECT tags FROM idea WHERE tags != '[]'").fetchall()
    known: set[str] = set()
    for (tags_json,) in rows:
        try:
            known.update(json.loads(tags_json))
        except json.JSONDecodeError:
            continue
    lowered = content.lower()
    return sorted([t for t in known if t.lower() in lowered])[:limit]


def capture_idea(conn: sqlite3.Connection, input_: CaptureInput) -> CaptureOutput:
    dup = conn.execute(
        "SELECT id, created_at FROM idea "
        "WHERE actor_id = ? AND scope = ? "
        "  AND content = ? "
        "  AND (julianday('now') - julianday(created_at)) * 86400 < ?",
        (input_.actor, input_.scope, input_.content, IDEMPOTENCY_SECONDS),
    ).fetchone()
    if dup:
        # Dedup: storage keeps first writer's task_ref; response echoes caller's.
        return CaptureOutput(
            id=dup[0],
            scope=input_.scope,
            actor=input_.actor,
            originator=input_.originator,
            created_at=dup[1],
            suggested_tags=_suggest_tags(conn, input_.content),
            actor_created=input_.actor_created,
            task_ref=input_.task_ref,
        )

    new_id = new_ulid()
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO idea "
        "(id, content, scope, actor_id, originator_id, tags, created_at, task_ref) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            new_id,
            input_.content,
            input_.scope,
            input_.actor,
            input_.originator,
            json.dumps(input_.tags),
            now,
            input_.task_ref,
        ),
    )
    return CaptureOutput(
        id=new_id,
        scope=input_.scope,
        actor=input_.actor,
        originator=input_.originator,
        created_at=now,
        suggested_tags=_suggest_tags(conn, input_.content),
        actor_created=input_.actor_created,
        task_ref=input_.task_ref,
    )
