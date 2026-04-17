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
