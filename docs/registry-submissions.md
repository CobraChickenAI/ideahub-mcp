# <span data-proof="authored" data-by="ai:claude">Registry submission drafts</span>

<span data-proof="authored" data-by="ai:claude">These are drafted but NOT submitted. Submit after polishing is done.</span>

## <span data-proof="authored" data-by="ai:claude">1. modelcontextprotocol/servers</span>

<span data-proof="authored" data-by="ai:claude">Submit as a PR to</span> [<span data-proof="authored" data-by="ai:claude">https://github.com/modelcontextprotocol/servers</span>](https://github.com/modelcontextprotocol/servers) <span data-proof="authored" data-by="ai:claude">— adds one line to the "Community Servers" section of</span> <span data-proof="authored" data-by="ai:claude">`README.md`, alphabetically.</span>

**<span data-proof="authored" data-by="ai:claude">Line to add:</span>**

```markdown proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTY1LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
- [ideahub-mcp](https://github.com/CobraChickenAI/ideahub-mcp) - Agent-first idea capture and recall with FTS5 search, scope/actor resolution, and idempotent writes.
```

**<span data-proof="authored" data-by="ai:claude">PR title:</span>**<span data-proof="authored" data-by="ai:claude"></span> <span data-proof="authored" data-by="ai:claude">`Add ideahub-mcp to community servers`</span>

**<span data-proof="authored" data-by="ai:claude">PR body:</span>**

```
Adds ideahub-mcp, an agent-first MCP server for capturing and recalling ideas.

Ten tools over a single SQLite store: capture, dump, search, list, get, related, annotate, archive, link, recognize. Built for the model as primary user — tool descriptions are prompts, errors carry a repair path, scope and actor resolve from MCP clientInfo + cwd without asking.

- Repo: https://github.com/CobraChickenAI/ideahub-mcp
- PyPI: https://pypi.org/project/ideahub-mcp/
- Install: `uvx ideahub-mcp`
- License: MIT
```

## <span data-proof="authored" data-by="ai:claude">2. Smithery</span>

<span data-proof="authored" data-by="ai:claude">Submit via the web UI at</span> [<span data-proof="authored" data-by="ai:claude">https://smithery.ai/new</span>](https://smithery.ai/new) <span data-proof="authored" data-by="ai:claude">(requires GitHub sign-in as a CobraChickenAI member).</span>

**<span data-proof="authored" data-by="ai:claude">Fields:</span>**

* **<span data-proof="authored" data-by="ai:claude">Repository</span>**<span data-proof="authored" data-by="ai:claude">:</span> <span data-proof="authored" data-by="ai:claude">`CobraChickenAI/ideahub-mcp`</span>

* **<span data-proof="authored" data-by="ai:claude">Display name</span>**<span data-proof="authored" data-by="ai:claude">:</span> <span data-proof="authored" data-by="ai:claude">`ideahub-mcp`</span>

* **<span data-proof="authored" data-by="ai:claude">Tagline</span>**<span data-proof="authored" data-by="ai:claude">:</span> <span data-proof="authored" data-by="ai:claude">`Agent-first idea capture and recall.`</span>

* **<span data-proof="authored" data-by="ai:claude">Category</span>**<span data-proof="authored" data-by="ai:claude">:</span> <span data-proof="authored" data-by="ai:claude">`Productivity`</span> <span data-proof="authored" data-by="ai:claude">(or</span> <span data-proof="authored" data-by="ai:claude">`Memory`, if they have it)</span>

* **<span data-proof="authored" data-by="ai:claude">Install command</span>**<span data-proof="authored" data-by="ai:claude">:</span> <span data-proof="authored" data-by="ai:claude">`uvx ideahub-mcp`</span>

* **<span data-proof="authored" data-by="ai:claude">Config schema</span>**<span data-proof="authored" data-by="ai:claude">: point at the env vars (`IDEAHUB_MCP_HOME`,</span> <span data-proof="authored" data-by="ai:claude">`IDEAHUB_ACTOR`,</span> <span data-proof="authored" data-by="ai:claude">`IDEAHUB_SCOPE`) — Smithery may auto-detect from a</span> <span data-proof="authored" data-by="ai:claude">`smithery.yaml`</span> <span data-proof="authored" data-by="ai:claude">if present.</span>

<span data-proof="authored" data-by="ai:claude">If Smithery requires a</span> <span data-proof="authored" data-by="ai:claude">`smithery.yaml`, drop this at repo root:</span>

```yaml proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MTg1LCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
startCommand:
  type: stdio
  command: uvx
  args: [ideahub-mcp]
  env:
    IDEAHUB_MCP_HOME: ${IDEAHUB_MCP_HOME}
    IDEAHUB_ACTOR: ${IDEAHUB_ACTOR}
    IDEAHUB_SCOPE: ${IDEAHUB_SCOPE}
```

## <span data-proof="authored" data-by="ai:claude">3. mcp-get (optional)</span>

<span data-proof="authored" data-by="ai:claude">`mcp-get`</span> <span data-proof="authored" data-by="ai:claude">is a community CLI registry:</span> [<span data-proof="authored" data-by="ai:claude">https://github.com/michaellatman/mcp-get</span>](https://github.com/michaellatman/mcp-get)<span data-proof="authored" data-by="ai:claude">. Submission is also a PR adding one entry to</span> <span data-proof="authored" data-by="ai:claude">`packages/package-list.json`:</span>

```json proof:W3sidHlwZSI6InByb29mQXV0aG9yZWQiLCJmcm9tIjowLCJ0byI6MzAxLCJhdHRycyI6eyJieSI6ImFpOmNsYXVkZSJ9fV0=
{
  "name": "ideahub-mcp",
  "description": "Agent-first idea capture and recall with FTS5 search.",
  "vendor": "CobraChickenAI",
  "sourceUrl": "https://github.com/CobraChickenAI/ideahub-mcp",
  "homepage": "https://github.com/CobraChickenAI/ideahub-mcp",
  "license": "MIT",
  "runtime": "python"
}
```

## <span data-proof="authored" data-by="ai:claude">Order</span>

1. <span data-proof="authored" data-by="ai:claude">Finish polishing/refinement.</span>
2. <span data-proof="authored" data-by="ai:claude">Consider cutting v0.1.1 with polish fixes.</span>
3. <span data-proof="authored" data-by="ai:claude">Submit modelcontextprotocol/servers PR first — highest-signal surface.</span>
4. <span data-proof="authored" data-by="ai:claude">Smithery next — lowest friction, good for humans discovering via web.</span>
5. <span data-proof="authored" data-by="ai:claude">mcp-get last — nice-to-have.</span>