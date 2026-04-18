# <span data-proof="authored" data-by="ai:claude">ideahub-mcp</span>

An agent-first [MCP](https://modelcontextprotocol.io) server for capturing and recalling ideas — the agent's and their human's.

The primary user is a model. Tools are short, imperative, example-laden; errors carry a repair path; scope and actor resolve from context so the agent doesn't have to ask.

## Tools

| Tool        | Purpose                                                                   |
| ----------- | ------------------------------------------------------------------------- |
| `capture`   | Write a new idea. Idempotent within 5s on identical content.              |
| `dump`      | Text-blob summary of the scoped corpus under a token budget.              |
| `search`    | FTS5 + bm25 ranked search with snippets.                                  |
| `list`      | Filter ideas by scope, actor, tags, date range.                           |
| `get`       | Full detail for one idea, with notes and outbound links.                  |
| `related`   | Nearest neighbors by tag overlap → shared originator → recency.           |
| `annotate`  | Append a free-text note to an idea without mutating it.                   |
| `archive`   | Hide an idea; write a typed `archive` note with reason.                   |
| `link`      | Connect two ideas (`related`, `supersedes`, `evolved_from`, `duplicate`). |
| `recognize` | Inspect the actor table.                                                  |
| `ping`      | Cheap no-side-effect health probe for connection/debugging.               |

## Discovery And Health

`ideahub-mcp` is intentionally tool-first, not resource-first. A client may show a
healthy connection even when `list_resources()` is sparse or empty.

To make discovery cheap and host-agnostic, the server exposes:

- `ping`: a no-side-effect tool for "is the server connected and responsive?"
- `ideahub://status`: a status resource that reports package version, storage paths,
  and the current tool surface

That design supports hosts that favor different MCP surfaces. Some clients reason
primarily over tools. Others probe resources first. A healthy server should be easy
to verify in either style.

For the full compatibility rubric, see [docs/mcp-health.md](docs/mcp-health.md).

## Install

```bash
uvx ideahub-mcp        # try it
uv tool install ideahub-mcp   # keep it around
```

## Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "ideahub": {
      "command": "uvx",
      "args": ["ideahub-mcp"],
      "env": {
        "IDEAHUB_MCP_HOME": "/Users/you/.ideahub-mcp",
        "IDEAHUB_ACTOR": "human:you"
      }
    }
  }
}
```

## Configuration

| Var                                                                       | Default                                                                  | Purpose                                          |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ------------------------------------------------ |
| <span data-proof="authored" data-by="ai:claude">`IDEAHUB_MCP_HOME`</span> | <span data-proof="authored" data-by="ai:claude">`~/.ideahub-mcp/`</span> | Data directory (SQLite store, logs, backups).    |
| <span data-proof="authored" data-by="ai:claude">`IDEAHUB_ACTOR`</span>    | —                                                                        | Fallback actor id (`human:you` or `agent:name`). |
| <span data-proof="authored" data-by="ai:claude">`IDEAHUB_SCOPE`</span>    | —                                                                        | Fallback scope when cwd isn't a git repo.        |

Actor resolution: explicit arg → MCP `clientInfo.name` → `IDEAHUB_ACTOR` → error.
Scope resolution: explicit arg → `IDEAHUB_SCOPE` → `repo:<git-toplevel>` → <span data-proof="authored" data-by="ai:claude">`global`</span>.

## Storage

One SQLite file with WAL, FTS5, and hand-rolled migrations. No ORM. Daily snapshots to `$IDEAHUB_MCP_HOME/backups/` with 14-day retention.

## Develop

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run pyright
```

## License

MIT.
