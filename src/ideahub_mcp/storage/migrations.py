from __future__ import annotations

import sqlite3
from pathlib import Path


def apply_pending_migrations(conn: sqlite3.Connection, migrations_dir: Path) -> list[str]:
    """Apply every migration in migrations_dir not yet in schema_version, in lexical order.

    Returns the list of applied migration names.
    """
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        "  name TEXT PRIMARY KEY,"
        "  applied_at TEXT NOT NULL"
        ")"
    )
    applied = {
        row[0] for row in conn.execute("SELECT name FROM schema_version").fetchall()
    }

    if not migrations_dir.exists():
        return []

    pending = sorted(p for p in migrations_dir.glob("*.sql") if p.name not in applied)
    names_applied: list[str] = []
    for path in pending:
        sql = path.read_text()
        conn.executescript(sql)
        _run_python_step(conn, path.name)
        conn.execute(
            "INSERT INTO schema_version (name, applied_at) VALUES (?, datetime('now'))",
            (path.name,),
        )
        names_applied.append(path.name)
    return names_applied


def _run_python_step(conn: sqlite3.Connection, migration_name: str) -> None:
    """Run any Python computation a migration needs after its DDL.

    Some migrations (e.g. content_hash backfill) need values computed in
    Python — the same canonical function the runtime uses — rather than
    expressed in pure SQL. The schema_version row is written only after
    this step succeeds, so a failed Python step replays the migration on
    the next start.
    """
    if migration_name == "004_content_hash.sql":
        from ideahub_mcp.storage.backfill import backfill_content_hashes

        backfill_content_hashes(conn)
