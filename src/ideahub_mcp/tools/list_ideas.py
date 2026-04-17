from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel, Field, field_validator

from ideahub_mcp.util.coerce import coerce_str_list


class ListInput(BaseModel):
    scope: str | None = None
    actor: str | None = None
    originator: str | None = None
    tags_any: list[str] = Field(default_factory=list)
    tags_all: list[str] = Field(default_factory=list)
    since: str | None = None
    until: str | None = None
    limit: int = 50
    include_archived: bool = False

    @field_validator("tags_any", "tags_all", mode="before")
    @classmethod
    def _coerce_tag_list(cls, v: object) -> list[str]:
        return coerce_str_list(v)


class ListItem(BaseModel):
    id: str
    scope: str
    actor: str
    preview: str
    created_at: str


class ListOutput(BaseModel):
    items: list[ListItem]
    count: int


def _preview(content: str) -> str:
    first = content.splitlines()[0] if content else ""
    return first[:120]


def list_ideas(conn: sqlite3.Connection, input_: ListInput) -> ListOutput:
    where: list[str] = []
    params: list[object] = []
    if input_.scope:
        where.append("scope = ?")
        params.append(input_.scope)
    if input_.actor:
        where.append("actor_id = ?")
        params.append(input_.actor)
    if input_.originator:
        where.append("originator_id = ?")
        params.append(input_.originator)
    if input_.since:
        where.append("created_at >= ?")
        params.append(input_.since)
    if input_.until:
        where.append("created_at <= ?")
        params.append(input_.until)
    if not input_.include_archived:
        where.append("archived_at IS NULL")

    sql = (
        "SELECT id, content, scope, actor_id, created_at, tags FROM idea"
        + (" WHERE " + " AND ".join(where) if where else "")
        + " ORDER BY created_at DESC LIMIT ?"
    )
    params.append(input_.limit)
    rows = conn.execute(sql, params).fetchall()

    items: list[ListItem] = []
    tags_any = {t.lower() for t in input_.tags_any}
    tags_all = {t.lower() for t in input_.tags_all}
    for r in rows:
        try:
            row_tags = {t.lower() for t in json.loads(r[5])}
        except json.JSONDecodeError:
            row_tags = set()
        if tags_any and row_tags.isdisjoint(tags_any):
            continue
        if tags_all and not tags_all.issubset(row_tags):
            continue
        items.append(
            ListItem(
                id=r[0],
                scope=r[2],
                actor=r[3],
                preview=_preview(r[1]),
                created_at=r[4],
            )
        )
    return ListOutput(items=items, count=len(items))
