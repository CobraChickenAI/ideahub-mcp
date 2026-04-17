from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

WORKTREE_RE = re.compile(r"/\.claude/worktrees/[^/]+$")


@dataclass(frozen=True)
class ScopeResolution:
    scope: str
    fallback_to_global: bool


def _git_toplevel(cwd: Path) -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    toplevel = out.stdout.strip()
    return WORKTREE_RE.sub("", toplevel)


def resolve_scope(explicit: str | None, cwd: Path) -> ScopeResolution:
    if explicit:
        return ScopeResolution(scope=explicit, fallback_to_global=False)
    if env := os.getenv("IDEAHUB_SCOPE"):
        return ScopeResolution(scope=env, fallback_to_global=False)
    toplevel = _git_toplevel(cwd)
    if toplevel:
        name = Path(toplevel).name
        return ScopeResolution(scope=f"repo:{name}", fallback_to_global=False)
    return ScopeResolution(scope="global", fallback_to_global=True)
