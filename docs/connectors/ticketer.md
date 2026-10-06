# Ticketer

`create(title, body, meta) → id`, `get_status`, `get_approvers → [{principal, group}]`, `comment`, `close`.

| `type` | Config |
| --- | --- |
| `jira` | `url, project, email, token, issue_type, approved_when: {status}, group_members, approvals_field` (REST v3) |
| `github` | `repo, token, group_members` (approval = `/approve` comment) |
| `manual` | writes a pending record under `.pecca/tickets`; fulfil with `pecca approve` |
| `mcp` | `url, tool_map: {create, get, comment[, close, approvers]}, args` |

`transport: mcp` on any ticketer config switches it to the MCP adapter. See [Approvals and tickets](../governance/approvals-and-tickets.md).
