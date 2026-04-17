import sqlite3

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.tools.capture import CaptureInput, capture_idea


def _seed_actor(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:michael", client_info_name=None)


def test_capture_minimal(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(content="the model is the user", actor="human:michael", scope="global"),
    )
    assert len(out.id) == 26
    assert out.actor == "human:michael"
    assert out.scope == "global"


def test_capture_idempotent_within_window(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    a = capture_idea(
        conn, CaptureInput(content="same", actor="human:michael", scope="global")
    )
    b = capture_idea(
        conn, CaptureInput(content="same", actor="human:michael", scope="global")
    )
    assert a.id == b.id


def test_capture_accepts_json_stringified_tags(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    # Simulates Raycast's local-agent-mode bridge which stringifies list params.
    out = capture_idea(
        conn,
        CaptureInput.model_validate(
            {
                "content": "stringified-tags",
                "actor": "human:michael",
                "scope": "global",
                "tags": '["mcp", "raycast"]',
            }
        ),
    )
    assert out.id
    # Re-capture with real list form — tags should be suggested back.
    out2 = capture_idea(
        conn,
        CaptureInput(
            content="another mcp note", actor="human:michael", scope="global"
        ),
    )
    assert "mcp" in out2.suggested_tags


def test_capture_echoes_actor_created(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(
            content="novel",
            actor="human:michael",
            scope="global",
            actor_created=True,
        ),
    )
    assert out.actor_created is True


def test_capture_suggests_existing_tags(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    capture_idea(
        conn,
        CaptureInput(
            content="about mcp",
            actor="human:michael",
            scope="global",
            tags=["mcp", "design"],
        ),
    )
    out = capture_idea(
        conn,
        CaptureInput(
            content="another mcp note", actor="human:michael", scope="global"
        ),
    )
    assert "mcp" in out.suggested_tags
