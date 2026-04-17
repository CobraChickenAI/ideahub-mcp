import sqlite3

import pytest

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.archive import ArchiveInput, archive_idea
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.list_ideas import ListInput, list_ideas


def test_archive_sets_archived_at_and_writes_note(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(conn, CaptureInput(content="x", actor="human:m", scope="global"))
    out = archive_idea(conn, ArchiveInput(id=cap.id, reason="stale", actor="human:m"))
    assert out.archived_at
    note = conn.execute(
        "SELECT kind, content FROM idea_note WHERE id = ?", (out.note_id,)
    ).fetchone()
    assert note == ("archive", "stale")


def test_archive_is_idempotent(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(conn, CaptureInput(content="x", actor="human:m", scope="global"))
    first = archive_idea(conn, ArchiveInput(id=cap.id, reason="stale", actor="human:m"))
    second = archive_idea(conn, ArchiveInput(id=cap.id, reason="again", actor="human:m"))
    assert first.archived_at == second.archived_at
    notes = conn.execute(
        "SELECT COUNT(*) FROM idea_note WHERE idea_id = ? AND kind='archive'", (cap.id,)
    ).fetchone()
    assert notes[0] == 1


def test_archive_unknown_raises(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    with pytest.raises(IdeaHubError) as exc:
        archive_idea(conn, ArchiveInput(id="nope", reason="r", actor="human:m"))
    assert exc.value.code == "idea_not_found"


def test_archive_hides_from_list(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    cap = capture_idea(conn, CaptureInput(content="x", actor="human:m", scope="global"))
    archive_idea(conn, ArchiveInput(id=cap.id, reason="stale", actor="human:m"))
    assert list_ideas(conn, ListInput()).count == 0
    assert list_ideas(conn, ListInput(include_archived=True)).count == 1
