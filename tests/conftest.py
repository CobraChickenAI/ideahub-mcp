"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Isolated IDEAHUB_MCP_HOME per test."""
    monkeypatch.setenv("IDEAHUB_MCP_HOME", str(tmp_path))
    yield tmp_path
