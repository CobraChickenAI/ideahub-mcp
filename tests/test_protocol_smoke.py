from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent, TextResourceContents
from pydantic import AnyUrl

from ideahub_mcp import __version__

EXPECTED_TOOLS = {
    "capture",
    "dump",
    "search",
    "list",
    "get",
    "related",
    "annotate",
    "archive",
    "link",
    "recognize",
    "ping",
}


@pytest.mark.asyncio
async def test_stdio_health_contract(tmp_home: Path) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ideahub_mcp"],
        env={**os.environ, "IDEAHUB_MCP_HOME": str(tmp_home)},
    )

    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        init = await session.initialize()
        assert init.serverInfo.name == "ideahub-mcp"
        assert init.serverInfo.version == __version__

        tools_result = await session.list_tools()
        tool_names = {tool.name for tool in tools_result.tools}
        assert tool_names == EXPECTED_TOOLS

        ping_result = await session.call_tool("ping", {})
        ping_text = ping_result.content[0]
        assert isinstance(ping_text, TextContent)
        ping_payload = json.loads(ping_text.text)
        assert ping_payload["ok"] is True
        assert ping_payload["name"] == "ideahub-mcp"
        assert ping_payload["version"] == __version__

        resources_result = await session.list_resources()
        resource_uris = {str(resource.uri) for resource in resources_result.resources}
        assert "ideahub://status" in resource_uris

        status_result = await session.read_resource(AnyUrl("ideahub://status"))
        status_contents = status_result.contents[0]
        assert isinstance(status_contents, TextResourceContents)
        status_payload = json.loads(status_contents.text)
        assert status_payload["name"] == "ideahub-mcp"
        assert status_payload["version"] == __version__
        assert set(status_payload["tools"]) == EXPECTED_TOOLS
