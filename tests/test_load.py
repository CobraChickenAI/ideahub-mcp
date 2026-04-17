from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from ideahub_mcp.domain.actors import resolve_actor
from ideahub_mcp.storage.migrations import apply_pending_migrations
from ideahub_mcp.tools.dump import DumpInput, dump_ideas
from ideahub_mcp.tools.search import SearchInput, search_ideas
from ideahub_mcp.util.clock import utcnow_iso
from ideahub_mcp.util.ids import new_ulid

MIGRATIONS_DIR = (
    Path(__file__).resolve().parents[1] / "src" / "ideahub_mcp" / "storage" / "migrations"
)

WORDS = [
    "coherence", "scope", "actor", "archetype", "binding", "domain",
    "policy", "provenance", "capability", "view", "connector",
    "interface", "model", "declaration", "protocol", "registry",
]


def _bulk_conn(tmp: Path, n: int) -> sqlite3.Connection:
    c = sqlite3.connect(tmp / "load.db", isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    apply_pending_migrations(c, MIGRATIONS_DIR)
    resolve_actor(c, explicit="human:m", client_info_name=None)
    now = utcnow_iso()
    c.execute("BEGIN")
    for i in range(n):
        words = " ".join(WORDS[(i + j) % len(WORDS)] for j in range(6))
        c.execute(
            "INSERT INTO idea (id, content, scope, actor_id, tags, created_at) "
            "VALUES (?, ?, ?, ?, '[]', ?)",
            (new_ulid(), f"{i}: {words}", "global", "human:m", now),
        )
    c.execute("COMMIT")
    return c


def test_dump_10k_respects_token_budget(tmp_path: Path) -> None:
    conn = _bulk_conn(tmp_path, 10_000)
    out = dump_ideas(conn, DumpInput(limit_tokens=50_000))
    assert out.truncated is True
    assert 0 < out.count <= 10_000
    conn.close()


def test_search_10k_under_500ms_median(tmp_path: Path) -> None:
    conn = _bulk_conn(tmp_path, 10_000)
    latencies: list[float] = []
    for i in range(25):
        term = WORDS[i % len(WORDS)]
        t0 = time.perf_counter()
        search_ideas(conn, SearchInput(query=term, limit=25))
        latencies.append(time.perf_counter() - t0)
    latencies.sort()
    median = latencies[len(latencies) // 2]
    assert median < 0.5, f"median search latency {median:.3f}s exceeded 500ms"
    conn.close()
