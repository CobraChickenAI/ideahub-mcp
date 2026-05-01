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
    # Dedup returns the stored task_ref (first writer's), not the caller's.
    # Both the response field and task_context must reflect the stored value.
    # task_ref is normalized at the boundary, so the stored form is lowercased.
    _seed_actor(conn)
    first = capture_idea(
        conn,
        CaptureInput(
            content="shared observation",
            scope="global",
            actor="human:michael",
            task_ref="alpha-task",
        ),
    )
    second = capture_idea(
        conn,
        CaptureInput(
            content="shared observation",
            scope="global",
            actor="human:michael",
            task_ref="beta-task",
        ),
    )
    assert first.id == second.id
    row = conn.execute(
        "SELECT task_ref FROM idea WHERE id = ?", (first.id,)
    ).fetchone()
    assert row[0] == "alpha-task"
    assert second.task_ref == "alpha-task"
    assert second.task_context.task_ref == "alpha-task"


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


def test_capture_task_ref_normalized_at_boundary(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(
            content="boundary normalization",
            scope="global",
            actor="human:michael",
            task_ref="Writeback Phase 1",
        ),
    )
    row = conn.execute("SELECT task_ref FROM idea WHERE id = ?", (out.id,)).fetchone()
    assert row[0] == "writeback-phase-1"
    assert out.task_ref == "writeback-phase-1"


def test_capture_task_ref_underscore_and_kebab_collide(conn: sqlite3.Connection) -> None:
    # Two captures under "writeback_phase_1" and "writeback-phase-1" must
    # land on the same task_ref so the graph is not silently partitioned.
    _seed_actor(conn)
    a = capture_idea(
        conn,
        CaptureInput(
            content="content one",
            scope="global",
            actor="human:michael",
            task_ref="writeback_phase_1",
        ),
    )
    b = capture_idea(
        conn,
        CaptureInput(
            content="content two",
            scope="global",
            actor="human:michael",
            task_ref="writeback-phase-1",
        ),
    )
    assert a.task_ref == b.task_ref == "writeback-phase-1"


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


def test_capture_candidates_zero_returns_empty_lists(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    capture_idea(
        conn,
        CaptureInput(content="seed idea", actor="human:michael", scope="global"),
    )
    out = capture_idea(
        conn,
        CaptureInput(
            content="another idea",
            actor="human:michael",
            scope="global",
            candidates=0,
        ),
    )
    assert out.annotate_candidates == []
    assert out.related_candidates == []


def test_capture_candidates_param_caps_response(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    for i in range(8):
        capture_idea(
            conn,
            CaptureInput(
                content=f"seed idea about scoring number {i}",
                actor="human:michael",
                scope="global",
            ),
        )
    out = capture_idea(
        conn,
        CaptureInput(
            content="another idea about scoring",
            actor="human:michael",
            scope="global",
            candidates=3,
        ),
    )
    assert len(out.annotate_candidates) <= 3
    assert len(out.related_candidates) <= 3


def test_capture_candidates_default_unchanged(conn: sqlite3.Connection) -> None:
    # v0.2.1 baseline: default candidates=5 with no param.
    _seed_actor(conn)
    for i in range(8):
        capture_idea(
            conn,
            CaptureInput(
                content=f"seed scorer phase number {i}",
                actor="human:michael",
                scope="global",
            ),
        )
    out = capture_idea(
        conn,
        CaptureInput(
            content="another scorer phase write",
            actor="human:michael",
            scope="global",
        ),
    )
    assert len(out.annotate_candidates) <= 5
    assert len(out.related_candidates) <= 5


def test_capture_candidates_out_of_range(conn: sqlite3.Connection) -> None:
    import pytest
    from pydantic import ValidationError

    _seed_actor(conn)
    with pytest.raises(ValidationError):
        CaptureInput(
            content="x", actor="human:michael", scope="global", candidates=11
        )
    with pytest.raises(ValidationError):
        CaptureInput(
            content="x", actor="human:michael", scope="global", candidates=-1
        )


def test_capture_dedup_byte_identical_across_actors(
    conn: sqlite3.Connection,
) -> None:
    from ideahub_mcp.domain.actors import resolve_actor

    resolve_actor(conn, explicit="human:michael", client_info_name=None)
    resolve_actor(conn, explicit="agent:claude", client_info_name=None)
    a = capture_idea(
        conn,
        CaptureInput(
            content="cross-actor duplicate",
            scope="global",
            actor="human:michael",
        ),
    )
    b = capture_idea(
        conn,
        CaptureInput(
            content="cross-actor duplicate",
            scope="global",
            actor="agent:claude",
        ),
    )
    assert a.id == b.id
    notes = conn.execute(
        "SELECT kind, content FROM idea_note WHERE idea_id = ?", (a.id,)
    ).fetchall()
    assert any(k == "dup_attempt" for k, _ in notes)


def test_capture_dedup_whitespace_normalized(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    a = capture_idea(
        conn,
        CaptureInput(
            content="hello world",
            scope="global",
            actor="human:michael",
        ),
    )
    # Different whitespace, would miss the 5s exact-match path on its own.
    b = capture_idea(
        conn,
        CaptureInput(
            content="  Hello   world  ",
            scope="global",
            actor="human:michael",
        ),
    )
    assert a.id == b.id


def test_capture_dedup_does_not_cross_scope(conn: sqlite3.Connection) -> None:
    _seed_actor(conn)
    a = capture_idea(
        conn,
        CaptureInput(content="scoped content", scope="alpha", actor="human:michael"),
    )
    b = capture_idea(
        conn,
        CaptureInput(content="scoped content", scope="beta", actor="human:michael"),
    )
    assert a.id != b.id


def test_capture_dedup_archived_does_not_block_recapture(
    conn: sqlite3.Connection,
) -> None:
    _seed_actor(conn)
    a = capture_idea(
        conn,
        CaptureInput(content="reusable thought", scope="global", actor="human:michael"),
    )
    conn.execute(
        "UPDATE idea SET archived_at = ? WHERE id = ?",
        ("2026-01-01T00:00:00Z", a.id),
    )
    b = capture_idea(
        conn,
        CaptureInput(content="reusable thought", scope="global", actor="human:michael"),
    )
    assert a.id != b.id


def test_capture_dup_attempt_merges_tags(conn: sqlite3.Connection) -> None:
    from ideahub_mcp.domain.actors import resolve_actor

    resolve_actor(conn, explicit="human:michael", client_info_name=None)
    resolve_actor(conn, explicit="agent:claude", client_info_name=None)
    a = capture_idea(
        conn,
        CaptureInput(
            content="tagged content",
            scope="global",
            actor="human:michael",
            tags=["alpha"],
        ),
    )
    capture_idea(
        conn,
        CaptureInput(
            content="tagged content",
            scope="global",
            actor="agent:claude",
            tags=["beta"],
        ),
    )
    import json as _json
    row = conn.execute("SELECT tags FROM idea WHERE id = ?", (a.id,)).fetchone()
    stored = set(_json.loads(row[0]))
    assert stored == {"alpha", "beta"}


def test_capture_writes_content_hash_on_insert(conn: sqlite3.Connection) -> None:
    from ideahub_mcp.util.hashing import compute_content_hash

    _seed_actor(conn)
    out = capture_idea(
        conn,
        CaptureInput(
            content="Hashable Content",
            scope="global",
            actor="human:michael",
        ),
    )
    row = conn.execute(
        "SELECT content_hash FROM idea WHERE id = ?", (out.id,)
    ).fetchone()
    assert row[0] == compute_content_hash("Hashable Content")


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
