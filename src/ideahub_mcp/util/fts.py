"""FTS5 query helpers.

Two modes:

- ``sanitize_fts_query`` — extracts alphanumeric tokens, quotes each, joins
  with OR. Hyphens and other FTS5 operators become inert. This is the right
  default for a "search" verb where the query is content, not syntax.
- ``raw_fts_query`` — passes the query through, validating only that it is
  non-empty. Syntax errors from FTS5 surface at the actual query site;
  callers wrap that exception into ``IdeaHubError`` for loud failure.
"""

from __future__ import annotations

import re

from ideahub_mcp.errors import IdeaHubError

# FTS5's default unicode61 tokenizer indexes Unicode letters/digits, so the
# sanitizer must too — otherwise non-ASCII content captured into FTS becomes
# unreachable through search. \w under re.UNICODE (Python 3 default) covers
# letters/digits/underscore across scripts.
_FTS_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_MAX_TOKENS = 20
_MIN_TOKEN_LEN = 3


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
    """Validate that ``text`` is a non-empty raw FTS5 MATCH expression.

    Syntax errors are caught at the call site by wrapping the actual query
    in a try/except — that's loud failure without a probing round-trip.
    """
    if not text or not text.strip():
        raise IdeaHubError(
            code="invalid_query",
            message="Empty query in raw mode.",
            fix="Pass a non-empty FTS5 expression, or use query_mode='auto'.",
        )
    return text
