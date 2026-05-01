"""Build-time architectural guards.

These tests fail the build when a structural contract is bypassed.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "ideahub_mcp"


def test_only_fts_helper_uses_match() -> None:
    """No module outside util/fts.py may inline the FTS5 MATCH literal.

    Callers must obtain the SQL fragment via util.fts.fts_match_clause() and
    the parameter via sanitize_fts_query() or raw_fts_query(). This makes
    util/fts.py the singular path to FTS5 — adding a new tool that bypasses
    sanitization fails the build.
    """
    offenders: list[str] = []
    for p in SRC.rglob("*.py"):
        if p.name == "fts.py":
            continue
        if "idea_fts MATCH" in p.read_text():
            offenders.append(str(p.relative_to(SRC)))
    assert offenders == [], (
        f"Bypassing util/fts.py — these files inline 'idea_fts MATCH': {offenders}. "
        "Use fts_match_clause() instead."
    )


def _is_list_str_annotation(node: ast.expr) -> bool:
    """Match a bare ``list[str]`` annotation node, however parenthesized."""
    if not isinstance(node, ast.Subscript):
        return False
    value = node.value
    if not (isinstance(value, ast.Name) and value.id == "list"):
        return False
    slice_node = node.slice
    return isinstance(slice_node, ast.Name) and slice_node.id == "str"


def test_no_bare_list_str_in_input_models() -> None:
    """Input models must use ``StrList`` (not bare ``list[str]``).

    ``StrList`` (util/types.py) carries the ``coerce_str_list`` BeforeValidator
    so MCP host bridges that JSON-stringify list params don't silently fail
    Pydantic validation. The bare annotation re-introduces that fragility,
    which is why a developer adding a new list-typed input parameter must
    not be able to forget it.

    A class is treated as an "input model" when its name ends in ``Input``.
    """
    offenders: list[str] = []
    for p in SRC.rglob("*.py"):
        try:
            tree = ast.parse(p.read_text())
        except SyntaxError:
            continue
        for cls in ast.walk(tree):
            if not (isinstance(cls, ast.ClassDef) and cls.name.endswith("Input")):
                continue
            for stmt in cls.body:
                if not isinstance(stmt, ast.AnnAssign):
                    continue
                if _is_list_str_annotation(stmt.annotation):
                    target = stmt.target
                    field = target.id if isinstance(target, ast.Name) else "<expr>"
                    offenders.append(
                        f"{p.relative_to(SRC)}::{cls.name}.{field}"
                    )
    assert offenders == [], (
        "Bare list[str] in input model fields — use StrList from "
        f"util/types.py: {offenders}"
    )
