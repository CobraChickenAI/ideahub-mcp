from __future__ import annotations

import sqlite3

from pydantic import BaseModel, field_validator

from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.util.clock import utcnow_iso

LINK_KINDS = {"related", "supersedes", "evolved_from", "duplicate"}


class LinkInput(BaseModel):
    source_id: str
    target_id: str
    kind: str
    task_ref: str | None = None

    @field_validator("task_ref", mode="before")
    @classmethod
    def _empty_task_ref_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v == "":
            return None
        return v


class LinkOutput(BaseModel):
    source_id: str
    target_id: str
    kind: str
    created: bool
    task_ref: str | None = None


def link_ideas(conn: sqlite3.Connection, input_: LinkInput) -> LinkOutput:
    if input_.kind not in LINK_KINDS:
        raise IdeaHubError(
            code="invalid_link",
            message=f"Unknown link kind: {input_.kind}",
            fix=f"Use one of {sorted(LINK_KINDS)}.",
        )
    if input_.source_id == input_.target_id:
        raise IdeaHubError(
            code="invalid_link",
            message="Cannot link an idea to itself.",
            fix="Pick distinct source and target ids.",
        )
    for which, idea_id in (("source", input_.source_id), ("target", input_.target_id)):
        if not conn.execute("SELECT 1 FROM idea WHERE id = ?", (idea_id,)).fetchone():
            raise IdeaHubError(
                code="idea_not_found",
                message=f"No idea with id={idea_id} ({which})",
                fix="Call list_ideas or dump_ideas to discover valid ids.",
            )

    src, tgt = input_.source_id, input_.target_id
    if input_.kind == "related" and src > tgt:
        src, tgt = tgt, src

    existing = conn.execute(
        "SELECT task_ref FROM idea_link "
        "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
        (src, tgt, input_.kind),
    ).fetchone()
    if existing:
        # Idempotent hit: return the stored task_ref so the caller learns when the
        # edge was first established. Asymmetric with capture dedup by design.
        return LinkOutput(
            source_id=src,
            target_id=tgt,
            kind=input_.kind,
            created=False,
            task_ref=existing[0],
        )

    conn.execute(
        "INSERT INTO idea_link (source_idea_id, target_idea_id, kind, created_at, task_ref) "
        "VALUES (?, ?, ?, ?, ?)",
        (src, tgt, input_.kind, utcnow_iso(), input_.task_ref),
    )
    return LinkOutput(
        source_id=src,
        target_id=tgt,
        kind=input_.kind,
        created=True,
        task_ref=input_.task_ref,
    )
