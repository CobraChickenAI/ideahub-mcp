from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel

from ideahub_mcp.errors import IdeaHubError


class RelatedInput(BaseModel):
    id: str
    max: int = 10
    cross_scope: bool = False
    include_archived: bool = False
    include_checkpoints: bool = False


class RelatedItem(BaseModel):
    id: str
    preview: str
    tag_overlap: int
    shared_originator: bool
    created_at: str


class RelatedOutput(BaseModel):
    items: list[RelatedItem]


def _preview(content: str) -> str:
    first = content.splitlines()[0] if content else ""
    return first[:120]


def related_ideas(conn: sqlite3.Connection, input_: RelatedInput) -> RelatedOutput:
    row = conn.execute(
        "SELECT tags, scope, originator_id FROM idea WHERE id = ?", (input_.id,)
    ).fetchone()
    if row is None:
        raise IdeaHubError(
            code="idea_not_found",
            message=f"No idea with id={input_.id}",
            fix="Call list_ideas or dump_ideas to discover valid ids.",
        )
    try:
        src_tags = set(json.loads(row[0]))
    except json.JSONDecodeError:
        src_tags = set()
    src_scope = row[1]
    src_originator = row[2]

    where = ["id != ?"]
    params: list[object] = [input_.id]
    if not input_.cross_scope:
        where.append("scope = ?")
        params.append(src_scope)
    if not input_.include_archived:
        where.append("archived_at IS NULL")
    if not input_.include_checkpoints:
        where.append("kind = 'idea'")

    sql = (
        "SELECT id, content, tags, originator_id, created_at FROM idea "
        f"WHERE {' AND '.join(where)} ORDER BY created_at DESC"
    )
    rows = conn.execute(sql, params).fetchall()

    items: list[RelatedItem] = []
    for r in rows:
        try:
            tags = set(json.loads(r[2]))
        except json.JSONDecodeError:
            tags = set()
        overlap = len(src_tags & tags)
        shared = bool(src_originator) and r[3] == src_originator
        items.append(
            RelatedItem(
                id=r[0],
                preview=_preview(r[1]),
                tag_overlap=overlap,
                shared_originator=shared,
                created_at=r[4],
            )
        )

    # Stable sort by (overlap DESC, shared_originator DESC); recency already applied.
    items.sort(key=lambda i: (-i.tag_overlap, 0 if i.shared_originator else 1))
    return RelatedOutput(items=items[: input_.max])
