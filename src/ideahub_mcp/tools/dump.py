from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel

DUMP_HINT = (
    "If you see duplicates, call link_ideas with kind='duplicate'. "
    "If a thought evolved, call link_ideas with kind='evolved_from'."
)


class DumpInput(BaseModel):
    scope: str | None = None
    since: str | None = None
    actor: str | None = None
    originator: str | None = None
    limit_tokens: int = 50_000
    include_all_notes: bool = False
    include_archived: bool = False


class DumpOutput(BaseModel):
    blob: str
    count: int
    truncated: bool
    scope_resolved: str
    hint: str


def _tokens(text: str) -> int:
    return len(text) // 4


def dump_ideas(conn: sqlite3.Connection, input_: DumpInput) -> DumpOutput:
    where: list[str] = []
    params: list[object] = []
    if input_.scope:
        where.append("scope = ?")
        params.append(input_.scope)
    if input_.since:
        where.append("created_at >= ?")
        params.append(input_.since)
    if input_.actor:
        where.append("actor_id = ?")
        params.append(input_.actor)
    if input_.originator:
        where.append("originator_id = ?")
        params.append(input_.originator)
    if not input_.include_archived:
        where.append("archived_at IS NULL")

    sql = (
        "SELECT id, content, scope, actor_id, originator_id, tags, created_at FROM idea"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY created_at DESC"
    )
    rows = conn.execute(sql, params).fetchall()

    blocks: list[str] = []
    count = 0
    truncated = False
    accumulated = 0
    for r in rows:
        idea_id, content, scope, actor, originator, tags_json, created_at = r
        header = f"## [{idea_id}] {created_at} • {actor}"
        if originator:
            header += f" via {originator}"
        block_lines = [header, content]
        try:
            tags = json.loads(tags_json)
        except json.JSONDecodeError:
            tags = []
        if tags:
            block_lines.append(f"tags: {tags}")

        if input_.include_all_notes:
            notes = conn.execute(
                "SELECT created_at, actor_id, content FROM idea_note "
                "WHERE idea_id = ? ORDER BY created_at ASC",
                (idea_id,),
            ).fetchall()
            for n in notes:
                block_lines.append(f"  (note) {n[0]} • {n[1]}: {n[2]}")
        else:
            latest = conn.execute(
                "SELECT created_at, actor_id, content FROM idea_note "
                "WHERE idea_id = ? ORDER BY created_at DESC LIMIT 1",
                (idea_id,),
            ).fetchone()
            if latest:
                block_lines.append(f"  (latest note) {latest[0]} • {latest[1]}: {latest[2]}")

        block = "\n".join(block_lines) + "\n"
        block_tokens = _tokens(block)
        if accumulated + block_tokens > input_.limit_tokens:
            truncated = True
            break
        blocks.append(block)
        accumulated += block_tokens
        count += 1

    return DumpOutput(
        blob="\n".join(blocks),
        count=count,
        truncated=truncated,
        scope_resolved=input_.scope or "",
        hint=DUMP_HINT,
    )
