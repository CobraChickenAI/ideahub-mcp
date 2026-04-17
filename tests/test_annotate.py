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


def test_annotate_unknown_raises(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    with pytest.raises(IdeaHubError) as exc:
        annotate_idea(conn, AnnotateInput(id="nope", content="x", actor="human:m"))
    assert exc.value.code == "idea_not_found"
