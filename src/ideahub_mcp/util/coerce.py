"""Defensive coercion for tool inputs from MCP clients that stringify lists."""

from __future__ import annotations

import json
import re
from typing import Any


def coerce_str_list(value: Any) -> list[str]:
    """Accept a list[str], a JSON-encoded list string, or None; always return list[str].

    Some MCP client bridges JSON-stringify list-typed params before forwarding them to
    the server. Rather than failing Pydantic validation, parse defensively so captures
    and filters still work regardless of the transport's behavior.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            # Plain non-JSON string — treat as a single tag.
            stripped = value.strip()
            return [stripped] if stripped else []
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
        if isinstance(parsed, str):
            return [parsed]
        raise ValueError(
            f"Expected a list of strings or a JSON-encoded list; got {type(parsed).__name__}"
        )
    raise ValueError(f"Cannot coerce {type(value).__name__} to list[str]")


_TASK_REF_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9]+")


def normalize_task_ref(value: Any) -> str | None:
    """Normalize a free-form task_ref to a stable kebab-case key.

    Lowercases, strips non-alphanumeric runs to single hyphens, and trims
    leading/trailing hyphens. Empty input returns ``None``. This collapses
    the trivial sprawl ("Writeback Phase 1" vs "writeback-phase-1" vs
    "writeback_phase_1") at the input boundary so the corpus only ever
    sees one form per task.

    Note: this is a *lexical* normalizer. Semantic near-duplicates
    ("writeback-phase-1" vs "writeback-spec-phase-1") are out of scope —
    those need detection, not normalization. See FAILURE-MODE-AUDIT P2.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"task_ref must be a string, got {type(value).__name__}")
    s = _TASK_REF_NON_ALPHANUMERIC.sub("-", value.strip().lower()).strip("-")
    return s or None
