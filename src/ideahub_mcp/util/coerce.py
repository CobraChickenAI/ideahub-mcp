"""Defensive coercion for tool inputs from MCP clients that stringify lists."""

from __future__ import annotations

import json
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
