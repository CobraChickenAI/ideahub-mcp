import asyncio
from pathlib import Path

from ideahub_mcp import __version__
from ideahub_mcp.server import build_server


def test_build_server_registers_tools(tmp_home: Path) -> None:
    s = build_server()
    tools = asyncio.run(s.list_tools())
    names = {t.name for t in tools}
    assert names == {
        "capture", "dump", "search", "list", "get",
        "related", "annotate", "archive", "link", "recognize", "ping",
        "checkpoint", "promote",
    }


def test_build_server_reports_package_version(tmp_home: Path) -> None:
    s = build_server()
    assert s.version == __version__


def test_status_resource_registered(tmp_home: Path) -> None:
    s = build_server()
    resources = asyncio.run(s.list_resources())
    uris = {str(r.uri) for r in resources}
    assert "ideahub://status" in uris
