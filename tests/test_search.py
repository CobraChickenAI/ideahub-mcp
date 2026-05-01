import sqlite3

import pytest

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.errors import IdeaHubError
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.search import SearchInput, search_ideas


def _seed(conn: sqlite3.Connection) -> None:
    resolve_actor(conn, explicit="human:m", client_info_name=None)


def test_search_finds_matches(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(conn, CaptureInput(content="coherence layer", actor="human:m", scope="global"))
    capture_idea(conn, CaptureInput(content="unrelated", actor="human:m", scope="global"))
    out = search_ideas(conn, SearchInput(query="coherence"))
    assert out.count == 1
    assert "coherence" in out.hits[0].snippet.lower() or "[coherence]" in out.hits[0].snippet


def test_search_empty_result(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(conn, CaptureInput(content="apples", actor="human:m", scope="global"))
    out = search_ideas(conn, SearchInput(query="zebras"))
    assert out.count == 0


def test_search_excludes_archived_by_default(conn: sqlite3.Connection) -> None:
    _seed(conn)
    cap = capture_idea(
        conn, CaptureInput(content="findme", actor="human:m", scope="global")
    )
    conn.execute("UPDATE idea SET archived_at = ? WHERE id = ?", ("2026-01-01T00:00:00Z", cap.id))
    out = search_ideas(conn, SearchInput(query="findme"))
    assert out.count == 0
    out_all = search_ideas(conn, SearchInput(query="findme", include_archived=True))
    assert out_all.count == 1


def test_search_case_insensitive(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(conn, CaptureInput(content="Capitalized", actor="human:m", scope="global"))
    out = search_ideas(conn, SearchInput(query="capitalized"))
    assert out.count == 1


def test_search_default_excludes_checkpoints(conn: sqlite3.Connection) -> None:
    _seed(conn)
    actor_id = resolve_actor(conn, explicit="human:m", client_info_name=None).id
    conn.execute(
        "INSERT INTO idea (id, content, scope, actor_id, tags, created_at, kind) VALUES "
        "('i1','writeback phase','s1',?, '[]', datetime('now'), 'idea'),"
        "('c1','writeback phase','s1',?, '[]', datetime('now'), 'checkpoint')",
        (actor_id, actor_id),
    )
    out = search_ideas(conn, SearchInput(query="writeback", scope="s1"))
    ids = {h.id for h in out.hits}
    assert "i1" in ids
    assert "c1" not in ids

    out2 = search_ideas(
        conn, SearchInput(query="writeback", scope="s1", include_checkpoints=True)
    )
    ids2 = {h.id for h in out2.hits}
    assert {"i1", "c1"}.issubset(ids2)


def test_search_hyphenated_query_finds_kebab_content(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(
        conn,
        CaptureInput(
            content="writeback-phase-1 design notes",
            actor="human:m",
            scope="global",
        ),
    )
    out = search_ideas(conn, SearchInput(query="writeback-phase-1"))
    assert out.count == 1


def test_search_special_chars_inert_in_auto_mode(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(
        conn,
        CaptureInput(content="hello world", actor="human:m", scope="global"),
    )
    # None of these should raise; all should return results or empty cleanly.
    for q in (":", "*", "^foo", '"unbalanced', "-leading", "foo:bar*"):
        out = search_ideas(conn, SearchInput(query=q))
        assert isinstance(out.count, int)


def test_search_auto_mode_empty_when_no_tokens(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(
        conn,
        CaptureInput(content="hello world", actor="human:m", scope="global"),
    )
    # All-symbol query has no extractable tokens — treated as no possible match.
    out = search_ideas(conn, SearchInput(query="!!!"))
    assert out.count == 0


def test_search_raw_mode_passthrough(conn: sqlite3.Connection) -> None:
    _seed(conn)
    capture_idea(
        conn,
        CaptureInput(content="alpha beta gamma", actor="human:m", scope="global"),
    )
    capture_idea(
        conn,
        CaptureInput(content="beta alpha gamma", actor="human:m", scope="global"),
    )
    # Phrase query in raw mode matches contiguous tokens only.
    out = search_ideas(
        conn, SearchInput(query='"alpha beta"', query_mode="raw")
    )
    contents = {h.snippet for h in out.hits}
    # The "alpha beta gamma" idea matches; "beta alpha gamma" does not.
    assert any("alpha" in s and "beta" in s for s in contents)
    assert out.count == 1


def test_search_raw_mode_syntax_error_is_loud(conn: sqlite3.Connection) -> None:
    _seed(conn)
    with pytest.raises(IdeaHubError) as excinfo:
        search_ideas(conn, SearchInput(query="foo:::", query_mode="raw"))
    assert excinfo.value.code == "invalid_query"


def test_search_raw_mode_empty_query_loud(conn: sqlite3.Connection) -> None:
    _seed(conn)
    with pytest.raises(IdeaHubError):
        search_ideas(conn, SearchInput(query="", query_mode="raw"))
