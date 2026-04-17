import sqlite3

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.related import RelatedInput, related_ideas


def test_related_scoring_orders_by_tag_overlap(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    src = capture_idea(
        conn,
        CaptureInput(content="src", actor="human:m", scope="global", tags=["a", "b"]),
    )
    two = capture_idea(
        conn,
        CaptureInput(content="two", actor="human:m", scope="global", tags=["a", "b"]),
    )
    one = capture_idea(
        conn, CaptureInput(content="one", actor="human:m", scope="global", tags=["a"])
    )
    zero = capture_idea(
        conn, CaptureInput(content="zero", actor="human:m", scope="global", tags=["z"])
    )
    out = related_ideas(conn, RelatedInput(id=src.id))
    ids = [i.id for i in out.items]
    assert ids[0] == two.id
    assert ids[1] == one.id
    assert zero.id in ids


def test_related_cross_scope_flag(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    src = capture_idea(
        conn,
        CaptureInput(content="src", actor="human:m", scope="global", tags=["a"]),
    )
    other = capture_idea(
        conn,
        CaptureInput(content="other", actor="human:m", scope="repo:x", tags=["a"]),
    )
    out_same = related_ideas(conn, RelatedInput(id=src.id))
    assert other.id not in [i.id for i in out_same.items]
    out_cross = related_ideas(conn, RelatedInput(id=src.id, cross_scope=True))
    assert other.id in [i.id for i in out_cross.items]


def test_related_empty_returns_empty(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)
    src = capture_idea(
        conn, CaptureInput(content="only", actor="human:m", scope="global")
    )
    out = related_ideas(conn, RelatedInput(id=src.id))
    assert out.items == []
