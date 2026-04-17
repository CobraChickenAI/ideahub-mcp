from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from ideahub_mcp.errors import IdeaHubError


class RecognizeInput(BaseModel):
    id: str | None = None


class ActorRecord(BaseModel):
    id: str
    kind: str
    display_name: str
    first_seen_at: str


class RecognizeOutput(BaseModel):
    actors: list[ActorRecord]


def recognize_actor(conn: sqlite3.Connection, input_: RecognizeInput) -> RecognizeOutput:
    if input_.id:
        row = conn.execute(
            "SELECT id, kind, display_name, first_seen_at FROM actor WHERE id = ?",
            (input_.id,),
        ).fetchone()
        if not row:
            raise IdeaHubError(
                code="actor_not_found",
                message=f"No actor with id={input_.id}",
                fix="Call recognize_actor with no id to list all actors.",
            )
        return RecognizeOutput(
            actors=[
                ActorRecord(id=row[0], kind=row[1], display_name=row[2], first_seen_at=row[3])
            ]
        )
    rows = conn.execute(
        "SELECT id, kind, display_name, first_seen_at FROM actor ORDER BY first_seen_at ASC"
    ).fetchall()
    return RecognizeOutput(
        actors=[
            ActorRecord(id=r[0], kind=r[1], display_name=r[2], first_seen_at=r[3])
            for r in rows
        ]
    )
