from __future__ import annotations

import sqlite3

import pytest

from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
from ideahub_mcp.tools.get import GetInput, get_idea
from ideahub_mcp.tools.link import LinkInput, link_ideas
from ideahub_mcp.tools.promote import PromoteInput, promote_checkpoint


@pytest.fixture
def seeded_actor(conn: sqlite3.Connection) -> str:
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now'))"
    )
    return "a1"


def test_promote_changes_kind_to_idea(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    cp = checkpoint_idea(
        conn,
        CheckpointInput(
            content="load-bearing trace",
            scope="s1",
            actor=seeded_actor,
            kind_label="decision",
        ),
    )
    promote_checkpoint(
        conn, PromoteInput(id=cp.id, actor=seeded_actor)
    )
    row = conn.execute(
        "SELECT kind FROM idea WHERE id = ?", (cp.id,)
    ).fetchone()
    assert row[0] == "idea"


def test_promote_preserves_id_and_links(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    cp = checkpoint_idea(
        conn,
        CheckpointInput(content="trace alpha", scope="s1", actor=seeded_actor),
    )
    other = capture_idea(
        conn,
        CaptureInput(content="durable thought", scope="s1", actor=seeded_actor),
    )
    link_ideas(
        conn,
        LinkInput(source_id=other.id, target_id=cp.id, kind="evolved_from"),
    )
    promote_checkpoint(conn, PromoteInput(id=cp.id, actor=seeded_actor))
    # The link still resolves under the same id.
    out = get_idea(conn, GetInput(id=cp.id))
    assert out.id == cp.id


def test_promote_writes_promotion_note(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    cp = checkpoint_idea(
        conn,
        CheckpointInput(
            content="will harden",
            scope="s1",
            actor=seeded_actor,
            kind_label="assumption",
        ),
    )
    promote_checkpoint(conn, PromoteInput(id=cp.id, actor=seeded_actor))
    out = get_idea(conn, GetInput(id=cp.id))
    promotion_notes = [n for n in out.notes if n.kind == "promotion"]
    assert len(promotion_notes) == 1
    assert "assumption" in promotion_notes[0].content


def test_promote_twice_raises_loud(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    cp = checkpoint_idea(
        conn,
        CheckpointInput(content="once", scope="s1", actor=seeded_actor),
    )
    promote_checkpoint(conn, PromoteInput(id=cp.id, actor=seeded_actor))
    with pytest.raises(IdeaHubError) as excinfo:
        promote_checkpoint(conn, PromoteInput(id=cp.id, actor=seeded_actor))
    assert excinfo.value.code == "not_a_checkpoint"


def test_promote_unknown_id_raises(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    with pytest.raises(IdeaHubError) as excinfo:
        promote_checkpoint(
            conn, PromoteInput(id="nonexistent", actor=seeded_actor)
        )
    assert excinfo.value.code == "idea_not_found"


def test_promote_idea_kind_rejected(
    conn: sqlite3.Connection, seeded_actor: str
) -> None:
    out = capture_idea(
        conn,
        CaptureInput(content="already an idea", scope="s1", actor=seeded_actor),
    )
    with pytest.raises(IdeaHubError) as excinfo:
        promote_checkpoint(conn, PromoteInput(id=out.id, actor=seeded_actor))
    assert excinfo.value.code == "not_a_checkpoint"


def test_no_demote_verb_exists() -> None:
    # Promotion is one-way by design: the audit constrains demotion entirely.
    from ideahub_mcp import tools

    assert not hasattr(tools, "demote")
