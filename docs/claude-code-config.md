# Claude Code Configuration

Add to `~/.claude/settings.json` under `mcpServers`:

```json
{
  "mcpServers": {
    "ideahub": {
      "command": "uv",
      "args": ["--directory", "/Users/you/Cowork/ideahub-mcp", "run", "ideahub-mcp"],
      "env": {
        "IDEAHUB_MCP_HOME": "/Users/you/.ideahub-mcp",
        "IDEAHUB_ACTOR": "human:you"
      }
    }
  }
}
```
