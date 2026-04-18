from __future__ import annotations

import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ideahub_mcp.tools.candidates import CandidateItem, score_candidates_for_write
from ideahub_mcp.tools.capture import TaskContext
from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.coerce import coerce_str_list
from ideahub_mcp.util.ids import new_ulid


class CheckpointInput(BaseModel):
    content: str = Field(..., min_length=1)
    scope: str
    actor: str
    originator: str | None = None
    tags: list[str] = Field(default_factory=list)
    task_ref: str | None = None
    kind_label: Literal["observation", "decision", "assumption", "question", "next_step"] | None = None
    actor_created: bool = False

    @field_validator("tags", mode="before")
    @classmethod
    def _coerce_tags(cls, v: object) -> list[str]:
        return coerce_str_list(v)

    @field_validator("task_ref", mode="before")
    @classmethod
    def _empty_task_ref_to_none(cls, v: object) -> object:
        if isinstance(v, str) and v == "":
            return None
        return v


class CheckpointOutput(BaseModel):
    id: str
    kind: str
    kind_label: str | None
    scope: str
    actor: str
    originator: str | None
    created_at: str
    task_ref: str | None
    suggested_tags: list[str]
    actor_created: bool = False
    annotate_candidates: list[CandidateItem] = Field(default_factory=list)
    related_candidates: list[CandidateItem] = Field(default_factory=list)
    task_context: TaskContext = Field(
        default_factory=lambda: TaskContext(task_ref=None, recent_ids=[])
    )


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


# Intentionally duplicated in capture.py — keep in sync.
def _task_context(
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


def checkpoint_idea(conn: sqlite3.Connection, input_: CheckpointInput) -> CheckpointOutput:
    new_id = new_ulid()
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO idea "
        "(id, content, scope, actor_id, originator_id, tags, created_at, kind, task_ref, kind_label) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'checkpoint', ?, ?)",
        (
            new_id,
            input_.content,
            input_.scope,
            input_.actor,
            input_.originator,
            json.dumps(input_.tags),
            now,
            input_.task_ref,
            input_.kind_label,
        ),
    )
    cands = score_candidates_for_write(
        conn,
        content=input_.content,
        scope=input_.scope,
        originator=input_.originator,
        task_ref=input_.task_ref,
        exclude_id=new_id,
    )
    return CheckpointOutput(
        id=new_id,
        kind="checkpoint",
        kind_label=input_.kind_label,
        scope=input_.scope,
        actor=input_.actor,
        originator=input_.originator,
        created_at=now,
        task_ref=input_.task_ref,
        suggested_tags=_suggest_tags(conn, input_.content),
        actor_created=input_.actor_created,
        annotate_candidates=cands.annotate_candidates,
        related_candidates=cands.related_candidates,
        task_context=_task_context(conn, input_.task_ref, new_id),
    )
