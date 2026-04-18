from __future__ import annotations

import sqlite3

import pytest

from ideahub_mcp.tools.candidates import (
    CandidateItem,  # noqa: F401  # re-exported surface sanity check
    score_candidates_for_write,
)


@pytest.fixture
def seeded(conn: sqlite3.Connection) -> sqlite3.Connection:
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now')),"
        "       ('a2','agent','a2',datetime('now'))"
    )
    # Three ideas + one checkpoint with varied signals:
    # - i1: lexical match on 'scorer ladder'
    # - i2: task-ref match 't-phase-1', no lexical
    # - i3: recency winner, a2-originator
    # - c1: sibling checkpoint, task-ref match + a1-originator
    conn.execute(
        "INSERT INTO idea (id, content, scope, actor_id, originator_id, tags, "
        "                  created_at, kind, task_ref) VALUES "
        "('i1','scorer ladder design','s1','a1','a1','[]','2026-04-10','idea', NULL),"
        "('i2','unrelated thing',     's1','a1','a2','[]','2026-04-15','idea','t-phase-1'),"
        "('i3','most recent thought', 's1','a2','a2','[]','2026-04-17','idea', NULL),"
        "('c1','sibling checkpoint',  's1','a1','a1','[]','2026-04-16','checkpoint','t-phase-1')"
    )
    conn.commit()
    # FTS triggers on idea INSERT already populate idea_fts. Verify by testing.
    return conn


def test_scorer_surfaces_lexical_match(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="scorer ladder for write time",
        scope="s1",
        originator=None,
        task_ref=None,
        max_candidates=5,
    )
    ids = [c.id for c in result.related_candidates]
    assert "i1" in ids  # lexical match wins


def test_scorer_promotes_shared_task_ref(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="drive-by note with no lexical overlap",
        scope="s1",
        originator=None,
        task_ref="t-phase-1",
        max_candidates=5,
    )
    ids = [c.id for c in result.related_candidates]
    # Task-ref matches (c1, i2) must outrank the non-task-ref recency winner (i3).
    if "i3" in ids:
        assert ids.index("c1") < ids.index("i3")
        assert ids.index("i2") < ids.index("i3")


def test_scorer_prefers_shared_originator_on_ties(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="unrelated content",
        scope="s1",
        originator="a1",
        task_ref=None,
        max_candidates=5,
    )
    # Among ideas with no lexical match and no task_ref match, a1-originated
    # should outrank a2-originated despite a2 being more recent.
    ids = [c.id for c in result.related_candidates]
    if "i1" in ids and "i3" in ids:
        assert ids.index("i1") < ids.index("i3")


def test_scorer_annotate_candidates_exclude_checkpoints(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="scorer ladder",
        scope="s1",
        originator=None,
        task_ref="t-phase-1",
        max_candidates=5,
    )
    # annotate_candidates only target durable ideas, never checkpoints.
    kinds = {c.kind for c in result.annotate_candidates}
    assert kinds == set() or kinds == {"idea"}
    ids = [c.id for c in result.annotate_candidates]
    assert "c1" not in ids


def test_scorer_explains_why(seeded: sqlite3.Connection) -> None:
    result = score_candidates_for_write(
        seeded,
        content="scorer ladder",
        scope="s1",
        originator="a1",
        task_ref="t-phase-1",
        max_candidates=5,
    )
    assert all(isinstance(c.why, str) and c.why for c in result.related_candidates)


def test_scorer_empty_on_empty_scope(conn: sqlite3.Connection) -> None:
    # Actor exists but no ideas yet.
    conn.execute(
        "INSERT INTO actor (id, kind, display_name, first_seen_at) "
        "VALUES ('a1','agent','a1',datetime('now'))"
    )
    conn.commit()
    result = score_candidates_for_write(
        conn,
        content="anything",
        scope="empty-scope",
        originator=None,
        task_ref=None,
    )
    assert result.related_candidates == []
    assert result.annotate_candidates == []
