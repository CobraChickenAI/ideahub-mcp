from __future__ import annotations

import sqlite3

from pydantic import BaseModel

from ideahub_mcp.util.fts import fts_match_clause, sanitize_fts_query


class CandidateItem(BaseModel):
    id: str
    kind: str
    preview: str
    score: float
    why: str
    reasons: list[str]
    created_at: str


class WriteCandidates(BaseModel):
    annotate_candidates: list[CandidateItem]
    related_candidates: list[CandidateItem]


def _preview(content: str) -> str:
    first = content.splitlines()[0] if content else ""
    return first[:120]


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
    exclude_id: str | None = None,
) -> WriteCandidates:
    """Produce annotate_candidates and related_candidates for a new write.

    Ladder, ascending preference: FTS bm25 match -> shared task_ref -> shared
    originator -> recency. Lower bm25 is better; we invert where needed.
    """
    query = sanitize_fts_query(content)

    merged: dict[str, _Row] = {}

    if query:
        fts_sql = (
            "SELECT i.id, i.content, i.kind, i.task_ref, i.originator_id, "
            "       i.created_at, bm25(idea_fts) AS score "
            "FROM idea_fts JOIN idea i ON i.rowid = idea_fts.rowid "
            f"WHERE {fts_match_clause()} AND i.scope = ? AND i.archived_at IS NULL"
        )
        fts_params: list[object] = [query, scope]
        if exclude_id:
            fts_sql += " AND i.id != ?"
            fts_params.append(exclude_id)
        fts_sql += " ORDER BY score ASC LIMIT 50"
        for r in conn.execute(fts_sql, fts_params).fetchall():
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
    nonfts_sql = (
        "SELECT id, content, kind, task_ref, originator_id, created_at "
        "FROM idea WHERE scope = ? AND archived_at IS NULL"
    )
    nonfts_params: list[object] = [scope]
    if exclude_id:
        nonfts_sql += " AND id != ?"
        nonfts_params.append(exclude_id)
    nonfts_sql += " ORDER BY created_at DESC LIMIT 100"
    nonfts_rows = conn.execute(nonfts_sql, nonfts_params).fetchall()
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

    def composite_key(row: _Row) -> tuple[float, int, int, str, str]:
        # Lower is better in every slot. Python's default ascending sort puts the
        # best candidate first. Final tiebreaker: row.id lexically ascending,
        # so fully-tied rows have deterministic ordering.
        fts_rank = row.fts_score if row.fts_score is not None else 1e9
        shared_task = 0 if (task_ref and row.task_ref == task_ref) else 1
        shared_orig = 0 if (originator and row.originator == originator) else 1
        return (fts_rank, shared_task, shared_orig, _invert_ts(row.created_at), row.id)

    def build_reasons(row: _Row) -> list[str]:
        reasons: list[str] = []
        if row.fts_hit:
            reasons.append("lexical_match")
        if task_ref and row.task_ref == task_ref:
            reasons.append("same_task")
        if originator and row.originator == originator:
            reasons.append("shared_originator")
        if not reasons:
            reasons.append("recent_in_scope")
        return reasons

    def build_why(reasons: list[str]) -> str:
        human = {
            "lexical_match": "lexical match",
            "same_task": "same task",
            "shared_originator": "shared originator",
            "recent_in_scope": "recent in scope",
        }
        return " + ".join(human[r] for r in reasons)

    ranked = sorted(merged.values(), key=composite_key)

    related: list[CandidateItem] = []
    annotate: list[CandidateItem] = []
    for row in ranked:
        task_match = bool(task_ref) and row.task_ref == task_ref
        orig_match = bool(originator) and row.originator == originator
        reasons = build_reasons(row)
        item = CandidateItem(
            id=row.id,
            kind=row.kind,
            preview=_preview(row.content),
            score=_display_score(row, task_ref_match=task_match, originator_match=orig_match),
            why=build_why(reasons),
            reasons=reasons,
            created_at=row.created_at,
        )
        if len(related) < max_candidates:
            related.append(item)
        if row.kind == "idea" and len(annotate) < max_candidates:
            annotate.append(item)
        if len(related) >= max_candidates and len(annotate) >= max_candidates:
            break

    return WriteCandidates(annotate_candidates=annotate, related_candidates=related)


def candidates_or_empty(
    conn: sqlite3.Connection,
    *,
    candidates: int,
    content: str,
    scope: str,
    originator: str | None,
    task_ref: str | None,
    exclude_id: str | None,
) -> WriteCandidates:
    """Run the scorer when ``candidates > 0``; otherwise return empty lists.

    The scorer is the largest contributor to writeback response size. The
    ``candidates=0`` short-circuit is the immediate lever for callers that
    want a fire-and-forget trace without paying the candidate-envelope cost.
    """
    if candidates <= 0:
        return WriteCandidates(annotate_candidates=[], related_candidates=[])
    return score_candidates_for_write(
        conn,
        content=content,
        scope=scope,
        originator=originator,
        task_ref=task_ref,
        max_candidates=candidates,
        exclude_id=exclude_id,
    )
