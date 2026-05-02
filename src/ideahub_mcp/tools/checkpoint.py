from __future__ import annotations

import json
import sqlite3
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ideahub_mcp.tools._shared import TaskContext, suggest_tags, task_context
from ideahub_mcp.tools.candidates import CandidateItem, candidates_or_empty
from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.coerce import normalize_task_ref
from ideahub_mcp.util.hashing import compute_content_hash
from ideahub_mcp.util.ids import new_ulid
from ideahub_mcp.util.types import StrList


class CheckpointInput(BaseModel):
    content: str = Field(..., min_length=1)
    scope: str
    actor: str
    originator: str | None = None
    tags: StrList = Field(default_factory=list)
    task_ref: str | None = None
    kind_label: (
        Literal["observation", "decision", "assumption", "question", "next_step"] | None
    ) = None
    actor_created: bool = False
    candidates: int = Field(default=5, ge=0, le=10)

    @field_validator("task_ref", mode="before")
    @classmethod
    def _normalize_task_ref(cls, v: object) -> object:
        return normalize_task_ref(v)


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


def checkpoint_idea(conn: sqlite3.Connection, input_: CheckpointInput) -> CheckpointOutput:
    new_id = new_ulid()
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO idea "
        "(id, content, scope, actor_id, originator_id, tags, created_at, kind, task_ref,"
        " kind_label, content_hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'checkpoint', ?, ?, ?)",
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
            compute_content_hash(input_.content),
        ),
    )
    cands = candidates_or_empty(
        conn,
        candidates=input_.candidates,
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
        suggested_tags=suggest_tags(conn, input_.content),
        actor_created=input_.actor_created,
        annotate_candidates=cands.annotate_candidates,
        related_candidates=cands.related_candidates,
        task_context=task_context(conn, input_.task_ref, new_id),
    )
