from __future__ import annotations

import sqlite3

import pytest

from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea


@pytest.fixture
def seeded_actor(conn: sqlite3.Connection) -> str:
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now'))"
    )
    return "a1"


def test_checkpoint_writes_row_with_kind_checkpoint(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="assumption: the scorer should weight FTS first",
            scope="s1",
            actor=seeded_actor,
            task_ref="writeback-phase-1",
            kind_label="assumption",
        ),
    )
    row = conn.execute(
        "SELECT kind, task_ref, content FROM idea WHERE id = ?", (out.id,)
    ).fetchone()
    assert row[0] == "checkpoint"
    assert row[1] == "writeback-phase-1"
    assert row[2] == "[assumption] assumption: the scorer should weight FTS first"
    assert out.kind == "checkpoint"
    assert out.task_ref == "writeback-phase-1"


def test_checkpoint_accepts_tags(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="x",
            scope="s1",
            actor=seeded_actor,
            tags=["scorer", "phase-1"],
        ),
    )
    import json
    row = conn.execute("SELECT tags FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert set(json.loads(row[0])) == {"scorer", "phase-1"}


def test_checkpoint_task_ref_optional(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(content="drive-by observation", scope="s1", actor=seeded_actor),
    )
    assert out.task_ref is None
