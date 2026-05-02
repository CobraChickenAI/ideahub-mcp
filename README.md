# ideahub_mcp

An agent-first [MCP](https://modelcontextprotocol.io) server for capturing and recalling ideas — the agent's and their human's.

The primary user is a model. Tools are short, imperative, example-laden; errors carry a repair path; scope and actor resolve from context so the agent doesn't have to ask.

## Tools

| Tool         | Purpose                                                                                 |
| ------------ | --------------------------------------------------------------------------------------- |
| `capture`    | Durable idea. Use when work produces something worth preserving beyond the task.        |
| `checkpoint` | Lightweight working-memory trace. Use mid-task for observations, decisions, next steps. |
| `promote`    | Promote a checkpoint to a durable idea, preserving its id, links, and provenance.       |
| `dump`       | Text-blob summary of the scoped corpus under a token budget.                            |
| `search`     | FTS5 + bm25 ranked search with snippets. Auto-tokenizes by default.                     |
| `list`       | Filter ideas by scope, actor, tags, date range.                                         |
| `get`        | Full detail for one idea, with notes and outbound links.                                |
| `related`    | Nearest neighbors by tag overlap → shared originator → recency.                         |
| `annotate`   | Append a free-text note to an idea without mutating it.                                 |
| `archive`    | Hide an idea; write a typed `archive` note with reason.                                 |
| `link`       | Connect two ideas (`related`, `supersedes`, `evolved_from`, `duplicate`).               |
| `recognize`  | Inspect the actor table.                                                                |
| `ping`       | Cheap no-side-effect health probe for connection/debugging.                             |

## Writeback Loop

`ideahub_mcp` is designed to behave like working memory for an agent, not just searchable storage. Two write verbs close that loop:

- `capture` writes a durable idea that should survive the task.
- `checkpoint` writes a lightweight in-flight trace — observations, decisions, assumptions, open questions — without the semantic weight of a full idea.

When a checkpoint hardens into something load-bearing, `promote` flips its kind to `idea` while preserving the id, so existing links, annotations, and `task_ref` groupings carry forward unchanged. Promotion is one-way; an idea cannot be demoted.

All write-path verbs (`capture`, `checkpoint`, `annotate`, `link`) accept an optional `task_ref` — a free-form string that groups every write from the same task. It is normalized to lowercase kebab-case at the boundary, so `"Writeback Phase 1"`, `"writeback_phase_1"`, and `"writeback-phase-1"` collapse onto the same key.

`capture` and `checkpoint` return scored `annotate_candidates` and `related_candidates` in their response so the model sees where a fresh trace probably belongs (usually as an annotation on an existing idea) without having to search. The `candidates` parameter (default 5, max 10, 0 to skip) lets a caller cap or skip that envelope when fire-and-forget is the right move.

Checkpoints are default-excluded from `search`, `list`, and `dump` so cheap traces do not bleed into orientation surfaces — opt in with `include_checkpoints=True`.

## Deduplication

`capture` runs two dedup paths before inserting:

- **Fast path** — same actor, same content, same scope, within 5 seconds: silently returns the existing id. This catches accidental double-fires.
- **Content-hash path** — same scope, same SHA-256 over normalized content (whitespace-collapsed, lowercased), any actor, any time, against live (non-archived) `kind='idea'` rows: returns the existing id, merges incoming tags into the row, and appends a `kind='dup_attempt'` note recording the second actor and tag delta.

Hash dedup makes re-derivation of the same idea observable in the row's note stream rather than silently creating duplicates.

## Search

`search` defaults to `query_mode='auto'`, which tokenizes the query and quotes each token so FTS5 operators (`-`, `:`, `*`, etc.) are treated as content. This is the right mode for searching kebab-case identifiers — task_refs, branch names, ULIDs.

For phrase queries, `NEAR`, or column-qualified syntax, pass `query_mode='raw'`. Raw mode validates the query and raises a loud error on syntax failure rather than the silent empty-result FTS5 returns by default.

## Discovery And Health

`ideahub_mcp` is intentionally tool-first, not resource-first. A client may show a healthy connection even when `list_resources()` is sparse or empty.

To make discovery cheap and host-agnostic, the server exposes:

- `ping`: a no-side-effect tool for "is the server connected and responsive?"
- `ideahub://status`: a status resource that reports package version, storage paths, and the current tool surface.

That design supports hosts that favor different MCP surfaces. Some clients reason primarily over tools. Others probe resources first. A healthy server should be easy to verify in either style.

For the full compatibility rubric, see [docs/mcp-health.md](docs/mcp-health.md).

## Install

```bash
uvx ideahub_mcp        # try it
uv tool install ideahub_mcp   # keep it around
```

## Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "ideahub": {
      "command": "uvx",
      "args": ["ideahub_mcp"],
      "env": {
        "IDEAHUB_MCP_HOME": "/Users/you/.ideahub_mcp",
        "IDEAHUB_ACTOR": "human:you"
      }
    }
  }
}
```

## Configuration

| Var                | Default            | Purpose                                          |
| ------------------ | ------------------ | ------------------------------------------------ |
| `IDEAHUB_MCP_HOME` | `~/.ideahub_mcp/`  | Data directory (SQLite store, logs, backups).    |
| `IDEAHUB_ACTOR`    | —                  | Fallback actor id (`human:you` or `agent:name`). |
| `IDEAHUB_SCOPE`    | —                  | Fallback scope when cwd isn't a git repo.        |

Actor resolution: explicit arg → MCP `clientInfo.name` → `IDEAHUB_ACTOR` → error.
Scope resolution: explicit arg → `IDEAHUB_SCOPE` → `repo:<git-toplevel>` → `global`.

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
