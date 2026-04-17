from __future__ import annotations

import sqlite3

from pydantic import BaseModel, Field

from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.ids import new_ulid


class AnnotateInput(BaseModel):
    id: str
    content: str = Field(..., min_length=1)
    actor: str
    originator: str | None = None
    kind: str | None = None


class AnnotateOutput(BaseModel):
    note_id: str
    idea_id: str
    kind: str | None
    created_at: str


def annotate_idea(conn: sqlite3.Connection, input_: AnnotateInput) -> AnnotateOutput:
    exists = conn.execute("SELECT 1 FROM idea WHERE id = ?", (input_.id,)).fetchone()
    if not exists:
        raise IdeaHubError(
            code="idea_not_found",
            message=f"No idea with id={input_.id}",
            fix="Call list_ideas or dump_ideas to discover valid ids.",
        )
    note_id = new_ulid()
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO idea_note "
        "(id, idea_id, kind, content, actor_id, originator_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            note_id,
            input_.id,
            input_.kind,
            input_.content,
            input_.actor,
            input_.originator,
            now,
        ),
    )
    return AnnotateOutput(
        note_id=note_id, idea_id=input_.id, kind=input_.kind, created_at=now
    )
