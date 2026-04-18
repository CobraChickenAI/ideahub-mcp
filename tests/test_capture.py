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


def test_capture_persists_task_ref(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(
            content="mid-task observation",
            scope="global",
            actor="human:michael",
            task_ref="writeback-phase-1",
        ),
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"


def test_capture_task_ref_is_optional(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(content="anything", scope="global", actor="human:michael"),
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] is None
    assert out.task_ref is None


def test_capture_dedup_preserves_first_task_ref_and_echoes_caller(
    conn: sqlite3.Connection,
) -> None:
    # Pins the dedup semantics the scorer (Task 6) depends on:
    # storage keeps the first writer's task_ref; the response echoes the caller's.
    _seed_actor(conn)
    first = capture_idea(
        conn,
        CaptureInput(
            content="shared observation",
            scope="global",
            actor="human:michael",
            task_ref="A",
        ),
    )
    second = capture_idea(
        conn,
        CaptureInput(
            content="shared observation",
            scope="global",
            actor="human:michael",
            task_ref="B",
        ),
    )
    assert first.id == second.id
    row = conn.execute(
        "SELECT task_ref FROM idea WHERE id = ?", (first.id,)
    ).fetchone()
    assert row[0] == "A"
    assert second.task_ref == "B"


def test_capture_returns_candidates_and_task_context(
    conn: sqlite3.Connection
) -> None:
    _seed_actor(conn)
    # seed a prior idea and a prior checkpoint under the same task
    from ideahub_mcp.tools.checkpoint import CheckpointInput, checkpoint_idea
    prior = capture_idea(
        conn,
        CaptureInput(content="scorer ladder phase-1", scope="global",
                     actor="human:michael", task_ref="t1"),
    )
    checkpoint_idea(
        conn,
        CheckpointInput(content="sibling observation", scope="global",
                        actor="human:michael", task_ref="t1"),
    )

    out = capture_idea(
        conn,
        CaptureInput(
            content="scorer ladder final write",
            scope="global",
            actor="human:michael",
            task_ref="t1",
        ),
    )
    # annotate_candidates include the prior idea but not the checkpoint
    ids = [c.id for c in out.annotate_candidates]
    assert prior.id in ids
    kinds = {c.kind for c in out.annotate_candidates}
    assert kinds.issubset({"idea"})
    # task_context carries the task_ref and some recent siblings
    assert out.task_context.task_ref == "t1"
    assert isinstance(out.task_context.recent_ids, list)
    # related_candidates can include the sibling checkpoint
    r_ids = {c.id for c in out.related_candidates}
    # At minimum, the new write should see at least one prior in-scope row
    assert len(r_ids) >= 1


def test_capture_empty_task_ref_becomes_none(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(
            content="with empty task_ref",
            scope="global",
            actor="human:michael",
            task_ref="",
        ),
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] is None
    assert out.task_ref is None


def test_capture_does_not_surface_itself_as_candidate(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(content="unique sentinel content zebra", scope="global",
                     actor="human:michael"),
    )
    all_candidate_ids = (
        {c.id for c in out.annotate_candidates}
        | {c.id for c in out.related_candidates}
    )
    assert out.id not in all_candidate_ids
