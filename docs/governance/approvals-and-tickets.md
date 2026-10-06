# Approvals and tickets

`approvals.via` selects where approvals come from:

* `manual`: `pecca approve PATH --version v3 --approver a@bank.com --group model-risk`. Approvals are stored per version in the call state.
* `jira:PROJ`: Pecca opens a ticket from `templates/approval_ticket.md.j2` when a promotion needs approval. An approval is a transition into `approved_when.status` (the Jira changelog author).
* `github:owner/repo`: Pecca opens an issue; a user comment `/approve` counts, with groups mapped through `group_members`.
* Any [`Ticketer`](../connectors/ticketer.md), including the MCP adapter.

A promotion proceeds when `require` (`all`, `any` or a number) of the listed groups/users are satisfied. Group membership comes from the approval itself (`--group`), `group_members` in the config, or the ticketer. Approvals never carry over to a new version.

```yaml
integrations:
  ticketer: {type: jira, url: https://x.atlassian.net, project: MRM, email: ${JIRA_EMAIL}, token: ${JIRA_TOKEN},
             approved_when: {status: Approved}, group_members: {model-risk: [mrm@bank.com]}}
```
