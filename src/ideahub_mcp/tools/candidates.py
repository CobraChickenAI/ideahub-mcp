from __future__ import annotations

import re
import sqlite3

from pydantic import BaseModel


class CandidateItem(BaseModel):
    id: str
    kind: str
    preview: str
    score: float
    why: str
    created_at: str


class WriteCandidates(BaseModel):
    annotate_candidates: list[CandidateItem]
    related_candidates: list[CandidateItem]


def _preview(content: str) -> str:
    first = content.splitlines()[0] if content else ""
    return first[:120]


_FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _fts_query(content: str) -> str:
    """Build an OR-of-tokens fts5 query from content.

    Quote each token to defuse fts5 syntax characters in user content. Cap the
    number of tokens to keep queries bounded on very long content.
    """
    tokens = [t for t in _FTS_TOKEN_RE.findall(content) if len(t) >= 3]
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
        if len(unique) >= 20:
            break
    return " OR ".join(f'"{t}"' for t in unique)


def _invert_ts(ts: str) -> str:
    # Invert an ISO-8601 timestamp lexically: newer strings -> smaller inverted
    # strings. This lets ascending sort put newer first on the recency rung.
    return "".join(
        chr(0x7E - (ord(c) - 0x20)) if 0x20 <= ord(c) <= 0x7E else c for c in ts
    )


class _Row(BaseModel):
    id: str
    content: str
    kind: str
    task_ref: str | None
    originator: str | None
    created_at: str
    fts_score: float | None
    fts_hit: bool


def _display_score(row: _Row, *, task_ref_match: bool, originator_match: bool) -> float:
    """A small human-legible float. Higher is better. Not used for sorting."""
    score = 0.0
    if row.fts_hit:
        fts = row.fts_score
        if fts is not None:
            score += 10.0 + 1.0 / (1.0 + abs(fts))
        else:
            score += 10.0
    if task_ref_match:
        score += 3.0
    if originator_match:
        score += 1.0
    return round(score, 3)


def score_candidates_for_write(
    conn: sqlite3.Connection,
    *,
    content: str,
    scope: str,
    originator: str | None,
    task_ref: str | None,
    max_candidates: int = 5,
) -> WriteCandidates:
    """Produce annotate_candidates and related_candidates for a new write.

    Ladder, ascending preference: FTS bm25 match -> shared task_ref -> shared
    originator -> recency. Lower bm25 is better; we invert where needed.
    """
    query = _fts_query(content)

    merged: dict[str, _Row] = {}

    if query:
        sql = (
            "SELECT i.id, i.content, i.kind, i.task_ref, i.originator_id, "
            "       i.created_at, bm25(idea_fts) AS score "
            "FROM idea_fts JOIN idea i ON i.rowid = idea_fts.rowid "
            "WHERE idea_fts MATCH ? AND i.scope = ? AND i.archived_at IS NULL "
            "ORDER BY score ASC LIMIT 50"
        )
        for r in conn.execute(sql, (query, scope)).fetchall():
            rid = str(r[0])
            merged[rid] = _Row(
                id=rid,
                content=str(r[1]),
                kind=str(r[2]),
                task_ref=(str(r[3]) if r[3] is not None else None),
                originator=(str(r[4]) if r[4] is not None else None),
                created_at=str(r[5]),
                fts_score=float(r[6]),
                fts_hit=True,
            )

    # Non-FTS side: every in-scope idea for the task_ref/originator/recency rungs
    # when FTS misses. Bounded to keep this cheap on large corpora.
    nonfts_rows = conn.execute(
        "SELECT id, content, kind, task_ref, originator_id, created_at "
        "FROM idea WHERE scope = ? AND archived_at IS NULL "
        "ORDER BY created_at DESC LIMIT 100",
        (scope,),
    ).fetchall()
    for r in nonfts_rows:
        rid = str(r[0])
        if rid in merged:
            continue
        merged[rid] = _Row(
            id=rid,
            content=str(r[1]),
            kind=str(r[2]),
            task_ref=(str(r[3]) if r[3] is not None else None),
            originator=(str(r[4]) if r[4] is not None else None),
            created_at=str(r[5]),
            fts_score=None,
            fts_hit=False,
        )

    def composite_key(row: _Row) -> tuple[float, int, int, str]:
        # Lower is better in every slot. Python's default ascending sort puts the
        # best candidate first.
        fts_rank = row.fts_score if row.fts_score is not None else 1e9
        shared_task = 0 if (task_ref and row.task_ref == task_ref) else 1
        shared_orig = 0 if (originator and row.originator == originator) else 1
        return (fts_rank, shared_task, shared_orig, _invert_ts(row.created_at))

    def build_why(row: _Row) -> str:
        parts: list[str] = []
        if row.fts_hit:
            parts.append("lexical match")
        if task_ref and row.task_ref == task_ref:
            parts.append("same task")
        if originator and row.originator == originator:
            parts.append("shared originator")
        if not parts:
            parts.append("recent in scope")
        return " + ".join(parts)

    ranked = sorted(merged.values(), key=composite_key)

    related: list[CandidateItem] = []
    annotate: list[CandidateItem] = []
    for row in ranked:
        task_match = bool(task_ref) and row.task_ref == task_ref
        orig_match = bool(originator) and row.originator == originator
        item = CandidateItem(
            id=row.id,
            kind=row.kind,
            preview=_preview(row.content),
            score=_display_score(row, task_ref_match=task_match, originator_match=orig_match),
            why=build_why(row),
            created_at=row.created_at,
        )
        if len(related) < max_candidates:
            related.append(item)
        if row.kind == "idea" and len(annotate) < max_candidates:
            annotate.append(item)
        if len(related) >= max_candidates and len(annotate) >= max_candidates:
            break

    return WriteCandidates(annotate_candidates=annotate, related_candidates=related)
