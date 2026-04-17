from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from hypothesis import HealthCheck, given, settings, strategies as st

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.storage.migrations import apply_pending_migrations
from ideahub_mcp.tools.capture import CaptureInput, capture_idea
from ideahub_mcp.tools.search import SearchInput, search_ideas

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "ideahub_mcp" / "storage" / "migrations"
)


def _fresh_conn(tmp: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp / "t.db", isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    apply_pending_migrations(c, MIGRATIONS_DIR)
    resolve_actor(c, explicit="human:m", client_info_name=None)
    return c


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{2,}")


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(content=st.text(alphabet=st.characters(whitelist_categories=("L", "N", "Zs")), min_size=8, max_size=200))
def test_fts_roundtrip(tmp_path_factory, content):
    tmp = tmp_path_factory.mktemp("fts")
    conn = _fresh_conn(tmp)
    tokens = TOKEN_RE.findall(content)
    if not tokens:
        return
    cap = capture_idea(
        conn, CaptureInput(content=content, actor="human:m", scope="global")
    )
    hits = search_ideas(conn, SearchInput(query=tokens[0]))
    assert any(h.id == cap.id for h in hits.hits)
    conn.close()
