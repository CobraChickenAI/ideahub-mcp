"""Single chokepoint for building FTS5 MATCH queries.

Every caller that wants to run an FTS5 MATCH must come through here. The
lint test in tests/test_lint.py enforces this — any other module containing
`idea_fts MATCH` will fail the build.

Two modes:

- ``sanitize_fts_query`` — extracts alphanumeric tokens, quotes each, joins
  with OR. Hyphens and other FTS5 operators become inert. This is the right
  default for a "search" verb where the query is content, not syntax.
- ``raw_fts_query`` — passes the query through, but validates syntax against
  a throwaway in-memory FTS5 table first so a malformed query fails loud
  with ``IdeaHubError`` instead of silently returning empty.
"""

from __future__ import annotations

import re
import sqlite3

from ideahub_mcp.errors import IdeaHubError

# FTS5's default unicode61 tokenizer indexes Unicode letters/digits, so the
# sanitizer must too — otherwise non-ASCII content captured into FTS becomes
# unreachable through search. \w under re.UNICODE (Python 3 default) covers
# letters/digits/underscore across scripts.
_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_MAX_TOKENS = 20
_MIN_TOKEN_LEN = 3


def fts_match_clause() -> str:
    """Return the canonical FTS5 MATCH SQL fragment.

    Callers must use this helper rather than inlining the literal so that
    the lint guard (tests/test_lint.py) catches any module that builds an
    FTS5 query without routing through this file.
    """
    return "idea_fts MATCH ?"


def sanitize_fts_query(text: str) -> str:
    """Build an OR-of-quoted-tokens FTS5 query from arbitrary content.

    Tokens shorter than ``_MIN_TOKEN_LEN`` are dropped. Tokens are
    deduplicated case-insensitively. The result is bounded at
    ``_MAX_TOKENS`` to keep queries cheap on long content. Returns ``""``
    when the input contains no usable tokens — callers should treat that
    as "no possible matches" rather than passing an empty MATCH.
    """
    tokens = [t for t in _FTS_TOKEN_RE.findall(text) if len(t) >= _MIN_TOKEN_LEN]
    if not tokens:
        return ""
    seen: set[str] = set()
    unique: list[str] = []
    for t in tokens:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        unique.append(low)
        if len(unique) >= _MAX_TOKENS:
            break
    return " OR ".join(f'"{t}"' for t in unique)


def raw_fts_query(text: str) -> str:
    """Validate ``text`` as an FTS5 MATCH expression; raise on syntax error.

    Uses a throwaway in-memory FTS5 table so syntax errors surface as
    ``IdeaHubError`` rather than the silent empty-result that FTS5
    otherwise returns for some edge cases.
    """
    if not text or not text.strip():
        raise IdeaHubError(
            code="invalid_query",
            message="Empty query in raw mode.",
            fix="Pass a non-empty FTS5 expression, or use query_mode='auto'.",
        )
    probe = sqlite3.connect(":memory:")
    try:
        probe.execute("CREATE VIRTUAL TABLE t USING fts5(c)")
        try:
            probe.execute("SELECT 1 FROM t WHERE t MATCH ?", (text,)).fetchall()
        except sqlite3.OperationalError as exc:
            raise IdeaHubError(
                code="invalid_query",
                message=f"FTS5 syntax error: {exc}",
                fix=(
                    "Fix the FTS5 expression, or use query_mode='auto' to let "
                    "the server tokenize and quote the query for you."
                ),
            ) from exc
    finally:
        probe.close()
    return text
