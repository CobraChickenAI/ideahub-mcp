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


def test_checkpoint_returns_candidates_and_task_context(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    from ideahub_mcp.tools.capture import CaptureInput, capture_idea
    prior = capture_idea(
        conn,
        CaptureInput(content="scorer ladder phase-1", scope="s1",
                     actor=seeded_actor, task_ref="t1"),
    )
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="scorer ladder sibling",
            scope="s1",
            actor=seeded_actor,
            task_ref="t1",
        ),
    )
    assert prior.id in [c.id for c in out.annotate_candidates]
    assert out.task_context.task_ref == "t1"
    assert isinstance(out.task_context.recent_ids, list)


def test_checkpoint_empty_task_ref_becomes_none(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(
            content="empty task_ref trace",
            scope="s1",
            actor=seeded_actor,
            task_ref="",
        ),
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] is None
    assert out.task_ref is None


def test_checkpoint_does_not_surface_itself_as_candidate(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = checkpoint_idea(
        conn,
        CheckpointInput(content="unique sentinel content zebra", scope="s1",
                        actor=seeded_actor),
    )
    all_candidate_ids = (
        {c.id for c in out.annotate_candidates}
        | {c.id for c in out.related_candidates}
    )
    assert out.id not in all_candidate_ids
