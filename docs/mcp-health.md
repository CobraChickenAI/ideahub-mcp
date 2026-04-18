# MCP Health And Host Compatibility

This server is designed to be healthy across MCP hosts that surface different parts
of the protocol.

That distinction matters because "healthy in Codex" and "healthy in Claude Code" are
overlapping but not identical goals. A host may prioritize tools, resources, prompts,
or its own lazy-loading path. A server should not assume that every client discovers
capabilities the same way.

## Health Model

Treat MCP health as four layers.

### 1. Protocol Health

The server is protocol-healthy if:

- it starts cleanly over the intended transport
- `initialize` succeeds
- `serverInfo.name` identifies the real server
- `serverInfo.version` identifies the package version, not the framework version
- `list_tools`, `list_resources`, `list_resource_templates`, and `list_prompts`
  return valid MCP responses, even when a catalog is empty
- at least one representative safe call succeeds

If this layer fails, the bug is in the server or transport.

### 2. Semantic Health

The server is semantically healthy if:

- advertised surfaces match real intent
- empty catalogs are intentional, not accidental
- names and descriptions explain what the server is for
- errors are structured and actionable

A server can be protocol-correct and still be confusing.

### 3. Discoverability Health

The server is discoverability-healthy if a generic client can answer:

- is the server connected?
- what does it do?
- what is the cheapest no-side-effect probe?

For `ideahub-mcp`, the canonical low-cost probes are:

- `ping`
- `ideahub://status`

### 4. Host Compatibility Health

The server is host-compatible if it remains legible in clients with different
discovery behavior.

Examples:

- Codex may expose generic resource listing separately from tool namespaces.
- Claude Code may foreground tools first and make resources less central.

The server should not require one specific host behavior to feel healthy.

## ideahub-mcp Contract

`ideahub-mcp` is intentionally tool-first. Non-empty resources are not required for
correctness, but the server still exposes a status resource so a generic client does
not mistake "no business resources" for "no server."

Current expectations:

- `list_tools()` returns the idea operations plus `ping`
- `list_resources()` includes `ideahub://status`
- `list_resource_templates()` may be empty
- `list_prompts()` may be empty
- `ping` is safe and side-effect free
- `ideahub://status` is safe and side-effect free

## Recommended Client Smoke Checks

For generic MCP clients, the minimum compatibility smoke test is:

1. initialize the server
2. assert `serverInfo.name == "ideahub-mcp"`
3. assert `serverInfo.version` matches the package version
4. call `list_tools()`
5. assert `ping` is present
6. call `ping`
7. call `list_resources()`
8. assert `ideahub://status` is present
9. read `ideahub://status`

This test avoids assuming that resources, templates, or prompts must be populated to
prove server health.
