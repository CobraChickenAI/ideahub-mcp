import sqlite3

import pytest

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.annotate import AnnotateInput, annotate_idea
from ideahub_mcp.tools.capture import CaptureInput, capture_idea


def test_annotate_appends(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(conn, CaptureInput(content="base", actor="human:m", scope="global"))
    a = annotate_idea(conn, AnnotateInput(id=cap.id, content="note1", actor="human:m"))
    b = annotate_idea(conn, AnnotateInput(id=cap.id, content="note2", actor="human:m"))
    assert a.idea_id == cap.id
    assert a.note_id != b.note_id
    assert a.kind is None


def test_annotate_accepts_kind(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(conn, CaptureInput(content="base", actor="human:m", scope="global"))
    a = annotate_idea(
        conn,
        AnnotateInput(
            id=cap.id, content="disproven by X", actor="human:m", kind="counterexample"
        ),
    )
    assert a.kind == "counterexample"
    row = conn.execute(
        "SELECT kind FROM idea_note WHERE id = ?", (a.note_id,)
    ).fetchone()
    assert row[0] == "counterexample"


def test_annotate_persists_task_ref(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(conn, CaptureInput(content="base", actor="human:m", scope="global"))
    out = annotate_idea(
        conn,
        AnnotateInput(
            id=cap.id,
            content="correction",
            actor="human:m",
            task_ref="writeback-phase-1",
        ),
    )
    row = conn.execute(
        "SELECT task_ref FROM idea_note WHERE id = ?", (out.note_id,)
    ).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"


def test_annotate_unknown_raises(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    with pytest.raises(IdeaHubError) as exc:
        annotate_idea(conn, AnnotateInput(id="nope", content="x", actor="human:m"))
    assert exc.value.code == "idea_not_found"


def test_annotate_accepts_checkpoint_id(conn: sqlite3.Connection) -> None:
    """Checkpoints are first-class rows; annotating one must succeed."""
    from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
    resolve_actor(conn, explicit="human:michael", client_info_name=None)
    cp = checkpoint_idea(
        conn,
        CheckpointInput(
            content="in-flight trace", scope="global", actor="human:michael"
        ),
    )
    out = annotate_idea(
        conn,
        AnnotateInput(
            id=cp.id,
            content="later note on the trace",
            actor="human:michael",
        ),
    )
    assert out.idea_id == cp.id


def test_annotate_empty_task_ref_becomes_none(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(
        conn, CaptureInput(content="base", actor="human:m", scope="global")
    )
    out = annotate_idea(
        conn,
        AnnotateInput(
            id=cap.id, content="note", actor="human:m", task_ref=""
        ),
    )
    row = conn.execute(
        "SELECT task_ref FROM idea_note WHERE id = ?", (out.note_id,)
    ).fetchone()
    assert row[0] is None
    assert out.task_ref is None
