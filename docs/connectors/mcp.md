# MCP adapters

`McpTicketer`, `McpNotifier` and `McpDataSource` talk to a remote MCP server (streamable HTTP URL) and map interface methods to its tools through `tool_map`.

```yaml
ticketer:
  type: jira
  transport: mcp          # switches to the MCP adapter
  url: https://mcp.example.com/mcp
  tool_map: {create: create_issue, get: get_issue, comment: add_comment}
  args: {create: {project: MRM}}      # static arguments per method
```
Conventions: `create(title, body)` → `{id|key}`; `get(id)` → `{status, approvers?}`; `comment(id, body)`. Pecca lists the server's tools and raises a clear error (suggesting `transport: rest`) when a mapped tool does not exist.
Limitation in v0.1: no auth headers for remote MCP servers; use the REST transport for authenticated systems.

## Pecca as an MCP server
`pecca mcp serve [--transport stdio|http] [--port 8765] [--allow-promote]`

| Tool | Purpose |
| --- | --- |
| `pecca_status(path)` | mode, version, metrics, threshold, agreement |
| `pecca_profile(path)` | profile of the call's data |
| `pecca_evaluate(path, since)` | agreement / fallback / drift / disagreements |
| `pecca_diff(path, v_a, v_b)` | compare versions |
| `pecca_audit(path)` | the audit pack as Markdown |
| `pecca_predict(path, inputs[])` | predictions with confidence and `fallback` |
| `pecca_promote(path, mode)` | governance-gated promotion; **only registered with `--allow-promote`** (never forces) |
