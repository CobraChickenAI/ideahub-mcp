# ideahub-mcp

An agent-first MCP server for capturing and recalling ideas — the agent's and their human's.

The primary user is a model. See `docs/design.md` for principles.

## Usage

```bash
uv run ideahub-mcp
```

Configured via environment:

- `IDEAHUB_MCP_HOME` — data directory (default `~/.ideahub-mcp/`)
- `IDEAHUB_ACTOR` — actor fallback (e.g. `human:michael`)
- `IDEAHUB_SCOPE` — scope fallback (e.g. `global`)
