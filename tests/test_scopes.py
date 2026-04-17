import subprocess
from pathlib import Path

import pytest

from ideahub_mcp.domain.scopes import resolve_scope


def test_explicit_scope_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IDEAHUB_SCOPE", "global")
    r = resolve_scope(explicit="repo:foo", cwd=Path("/tmp"))
    assert r.scope == "repo:foo"
    assert r.fallback_to_global is False


def test_env_var_second(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IDEAHUB_SCOPE", "repo:envrepo")
    r = resolve_scope(explicit=None, cwd=tmp_path)
    assert r.scope == "repo:envrepo"


def test_git_toplevel_derives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("IDEAHUB_SCOPE", raising=False)
    repo = tmp_path / "myrepo"
    repo.mkdir()
    subprocess.check_call(["git", "init", "-q"], cwd=repo)
    r = resolve_scope(explicit=None, cwd=repo)
    assert r.scope == "repo:myrepo"


def test_worktree_path_strips_to_parent_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IDEAHUB_SCOPE", raising=False)
    repo = tmp_path / "parentrepo"
    worktree = repo / ".claude" / "worktrees" / "fun-name"
    worktree.mkdir(parents=True)
    subprocess.check_call(["git", "init", "-q"], cwd=repo)
    r = resolve_scope(explicit=None, cwd=worktree)
    assert r.scope == "repo:parentrepo"


def test_fallback_to_global_flagged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IDEAHUB_SCOPE", raising=False)
    # Avoid ancestor git discovery by using /tmp (unlikely to be in a repo)
    import tempfile

    with tempfile.TemporaryDirectory(dir="/tmp") as td:
        r = resolve_scope(explicit=None, cwd=Path(td))
    assert r.scope == "global"
    assert r.fallback_to_global is True
