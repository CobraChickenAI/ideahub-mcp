# ideahub_mcp evaluation suite

Ten read-only QA pairs that exercise the ideahub_mcp tool surface end-to-end. Built per the [mcp-builder evaluation guide](https://docs.anthropic.com/) — each question is independent, complex (multi-tool composition), realistic, verifiable by string comparison, and stable across reseeds.

## Build the seed store

```bash
uv run python evals/seed_corpus.py /tmp/ideahub_eval/store.db
```

The seed builder is deterministic: hand-picked ULIDs, frozen ISO timestamps, and identical content on every run. It applies the live migrations from `src/ideahub_mcp/storage/migrations/`, so the schema always matches production.

What gets seeded:

- 4 actors (`human:alice`, `human:bob`, `agent:claude`, `agent:codex`)
- 14 live + archived ideas across `repo:demo` and `repo:other`
- 5 checkpoints (3 under `task_ref='writeback-phase-1'`, 2 under other task_refs)
- 7 notes (idea `00000000000000000000000007` carries 4 of them)
- 5 links across all four kinds (`related`, `supersedes`, `evolved_from`, `duplicate`)

## Point a model at the seed corpus

The eval expects the agent to talk to ideahub_mcp via stdio. Set `IDEAHUB_MCP_HOME` to the directory containing the seed store (NOT the store path itself — ideahub_mcp expects a directory and creates `store.db` inside it):

```bash
export IDEAHUB_MCP_HOME=/tmp/ideahub_eval
export IDEAHUB_ACTOR=human:eval
uv run python -m ideahub_mcp
```

In MCP host config (Claude Code, Codex, etc.):

```json
{
  "mcpServers": {
    "ideahub_eval": {
      "command": "uv",
      "args": ["--directory", "/abs/path/to/ideahub_mcp", "run", "ideahub_mcp"],
      "env": {
        "IDEAHUB_MCP_HOME": "/tmp/ideahub_eval",
        "IDEAHUB_ACTOR": "human:eval"
      }
    }
  }
}
```

## Run the eval

This repo doesn't ship its own LLM harness. The mcp-builder skill provides a runner that consumes `ideahub_mcp_eval.xml` and reports pass/fail per question. To run by hand: paste each `<question>` into a fresh chat with the configured ideahub_mcp server attached, compare the model's response to the `<answer>`.

## Re-seeding for stability

```bash
rm -rf /tmp/ideahub_eval && uv run python evals/seed_corpus.py /tmp/ideahub_eval/store.db
```

Daily snapshot backups run on every server start, so successive eval runs against the same `IDEAHUB_MCP_HOME` will accumulate `backups/store-*.db` files. These don't affect query results but can be pruned anytime.
