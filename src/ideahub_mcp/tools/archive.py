from __future__ import annotations

import sqlite3

from pydantic import BaseModel, Field

from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.ids import new_ulid


class ArchiveInput(BaseModel):
    id: str
    reason: str = Field(..., min_length=1)
    actor: str
    originator: str | None = None


class ArchiveOutput(BaseModel):
    id: str
    archived_at: str
    note_id: str


def archive_idea(conn: sqlite3.Connection, input_: ArchiveInput) -> ArchiveOutput:
    row = conn.execute(
        "SELECT archived_at FROM idea WHERE id = ?", (input_.id,)
    ).fetchone()
    if row is None:
        raise IdeaHubError(
            code="idea_not_found",
            message=f"No idea with id={input_.id}",
            fix="Call list_ideas or dump_ideas to discover valid ids.",
        )
    if row[0]:
        existing_note = conn.execute(
            "SELECT id FROM idea_note WHERE idea_id = ? AND kind = 'archive' "
            "ORDER BY created_at DESC LIMIT 1",
            (input_.id,),
        ).fetchone()
        return ArchiveOutput(
            id=input_.id,
            archived_at=row[0],
            note_id=existing_note[0] if existing_note else "",
        )

    now = utcnow_iso()
    note_id = new_ulid()
    conn.execute("BEGIN")
    try:
        conn.execute(
            "UPDATE idea SET archived_at = ? WHERE id = ?", (now, input_.id)
        )
        conn.execute(
            "INSERT INTO idea_note (id, idea_id, kind, content, actor_id, originator_id, created_at) "
            "VALUES (?, ?, 'archive', ?, ?, ?, ?)",
            (note_id, input_.id, input_.reason, input_.actor, input_.originator, now),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return ArchiveOutput(id=input_.id, archived_at=now, note_id=note_id)
