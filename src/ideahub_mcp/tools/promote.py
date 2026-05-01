from __future__ import annotations

import sqlite3

from pydantic import BaseModel, Field

from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.get import GetInput, GetOutput, get_idea
from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.ids import new_ulid


class PromoteInput(BaseModel):
    id: str = Field(..., min_length=1)
    actor: str
    originator: str | None = None


def promote_checkpoint(conn: sqlite3.Connection, input_: PromoteInput) -> GetOutput:
    """Promote a checkpoint to a durable idea, preserving its id.

    One-way: an idea cannot be demoted back to a checkpoint. The original
    ``kind_label`` is recorded in a ``kind='promotion'`` note so the
    provenance trail survives the kind change.
    """
    row = conn.execute(
        "SELECT kind, kind_label FROM idea WHERE id = ?", (input_.id,)
    ).fetchone()
    if row is None:
        raise IdeaHubError(
            code="idea_not_found",
            message=f"No idea with id={input_.id}",
            fix="Call list_ideas or dump_ideas to discover valid ids.",
        )
    current_kind, kind_label = row
    if current_kind != "checkpoint":
        raise IdeaHubError(
            code="not_a_checkpoint",
            message=f"Idea {input_.id} is kind={current_kind}, cannot promote.",
            fix=(
                "Only checkpoints can be promoted. If you want to capture a new "
                "idea, call `capture` instead."
            ),
        )

    now = utcnow_iso()
    note_id = new_ulid()
    conn.execute("BEGIN")
    try:
        conn.execute(
            "UPDATE idea SET kind = 'idea' WHERE id = ?", (input_.id,)
        )
        note_content = (
            f"promoted from checkpoint (was kind_label={kind_label})"
            if kind_label is not None
            else "promoted from checkpoint"
        )
        conn.execute(
            "INSERT INTO idea_note "
            "(id, idea_id, kind, content, actor_id, originator_id, created_at) "
            "VALUES (?, ?, 'promotion', ?, ?, ?, ?)",
            (
                note_id,
                input_.id,
                note_content,
                input_.actor,
                input_.originator,
                now,
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise

    return get_idea(conn, GetInput(id=input_.id))
