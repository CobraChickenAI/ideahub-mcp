import sqlite3

import pytest

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.link import LinkInput, link_ideas


def _two(conn: sqlite3.Connection) -> tuple[str, str]:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    a = capture_idea(conn, CaptureInput(content="a", actor="human:m", scope="global"))
    b = capture_idea(conn, CaptureInput(content="b", actor="human:m", scope="global"))
    return a.id, b.id


def test_link_creates(conn: sqlite3.Connection) -> None:
    a, b = _two(conn)
    out = link_ideas(conn, LinkInput(source_id=a, target_id=b, kind="supersedes"))
    assert out.created is True


def test_related_canonicalizes(conn: sqlite3.Connection) -> None:
    a, b = _two(conn)
    small, large = sorted([a, b])
    out = link_ideas(conn, LinkInput(source_id=large, target_id=small, kind="related"))
    assert out.source_id == small
    assert out.target_id == large


def test_duplicate_link_is_noop(conn: sqlite3.Connection) -> None:
    a, b = _two(conn)
    first = link_ideas(conn, LinkInput(source_id=a, target_id=b, kind="related"))
    second = link_ideas(conn, LinkInput(source_id=a, target_id=b, kind="related"))
    assert first.created is True
    assert second.created is False


def test_unknown_id_raises(conn: sqlite3.Connection) -> None:
    a, _ = _two(conn)
    with pytest.raises(IdeaHubError) as exc:
        link_ideas(conn, LinkInput(source_id=a, target_id="nope", kind="related"))
    assert exc.value.code == "idea_not_found"


def test_self_link_rejected(conn: sqlite3.Connection) -> None:
    a, _ = _two(conn)
    with pytest.raises(IdeaHubError) as exc:
        link_ideas(conn, LinkInput(source_id=a, target_id=a, kind="related"))
    assert exc.value.code == "invalid_link"


def test_link_persists_task_ref(conn: sqlite3.Connection) -> None:
    src, tgt = _two(conn)
    out = link_ideas(
        conn,
        LinkInput(
            source_id=src,
            target_id=tgt,
            kind="related",
            task_ref="writeback-phase-1",
        ),
    )
    row = conn.execute(
        "SELECT task_ref FROM idea_link "
        "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
        (out.source_id, out.target_id, out.kind),
    ).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"


def test_link_accepts_checkpoint_ids(conn: sqlite3.Connection) -> None:
    """Links between checkpoints, or between a checkpoint and an idea, must succeed."""
    from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
    resolve_actor(conn, explicit="human:michael", client_info_name=None)
    idea = capture_idea(
        conn,
        CaptureInput(content="durable", scope="global", actor="human:michael"),
    )
    cp = checkpoint_idea(
        conn,
        CheckpointInput(content="trace", scope="global", actor="human:michael"),
    )
    out = link_ideas(
        conn,
        LinkInput(source_id=idea.id, target_id=cp.id, kind="related"),
    )
    assert out.created is True


def test_link_empty_task_ref_becomes_none(conn: sqlite3.Connection) -> None:
    src, tgt = _two(conn)
    out = link_ideas(
        conn,
        LinkInput(source_id=src, target_id=tgt, kind="related", task_ref=""),
    )
    row = conn.execute(
        "SELECT task_ref FROM idea_link "
        "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
        (out.source_id, out.target_id, out.kind),
    ).fetchone()
    assert row[0] is None
    assert out.task_ref is None


def test_link_idempotency_preserves_first_task_ref(conn: sqlite3.Connection) -> None:
    src, tgt = _two(conn)
    link_ideas(
        conn,
        LinkInput(source_id=src, target_id=tgt, kind="related", task_ref="first"),
    )
    second = link_ideas(
        conn,
        LinkInput(source_id=src, target_id=tgt, kind="related", task_ref="second"),
    )
    assert second.created is False
    row = conn.execute(
        "SELECT task_ref FROM idea_link "
        "WHERE source_idea_id = ? AND target_idea_id = ? AND kind = ?",
        (second.source_id, second.target_id, second.kind),
    ).fetchone()
    assert row[0] == "first"
    assert second.task_ref == "first"
