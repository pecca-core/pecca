# pecca.yaml reference

*Generated from the JSON Schema by `scripts/gen_docs.py`.*

`pecca apply` validates the file, resolves `extends`, checks that every `${VAR}` resolves, stores the result in `.pecca/config.resolved.yaml` (placeholders kept) and prints a diff against what was stored before.

```yaml
version: 1
workspace:
  name: default
  registry: local://./.pecca
projects:
  autoresponse:
    datasource:                       # historical LLM answers + human agent tags
      type: csv
      path: ../../data/demo/train.csv   # created by `pecca datasets demo`
      columns:
        input: {subject: email_subject, body: email_body}
        llm_output: llm_rfi
        human_label: human_rfi
        call_name: {literal: route_rfi}
        timestamp: timestamp
        language: language
    governance:
      extends: default
      transitions:
        shadow->live:
          gates: ["agreement >= 0.90", "shadow_days >= 14"]
    calls:
      route_rfi: {policy: {train_every: 7d, min_rows: 2000, target_precision: 0.95, latency_budget_ms: 50}}
```

| key | type | notes |
| --- | --- | --- |
| `version` |  |  |
| `workspace` | object |  |
| `workspace.name` | string | Pattern `^[A-Za-z0-9_.-]+$`. |
| `workspace.registry` | string | local://./.pecca or mlflow://databricks-uc/<catalog>.<schema> |
| `workspace.telemetry` | object |  |
| `workspace.secrets` | object |  |
| `workspace.secrets.provider` | string |  |
| `workspace.scheduler` | object |  |
| `projects` | object |  |
| `projects.<name>.datasource` | object |  |
| `projects.<name>.datasource.type` | string |  |
| `projects.<name>.datasource.columns` | object |  |
| `projects.<name>.labels` | object |  |
| `projects.<name>.labels.type` | string |  |
| `projects.<name>.labels.join_on` | string |  |
| `projects.<name>.labels.column` | string |  |
| `projects.<name>.governance` | object |  |
| `projects.<name>.governance.extends` | string |  |
| `projects.<name>.governance.transitions` | object |  |
| `projects.<name>.governance.transitions.<name>.gates` | array |  |
| `projects.<name>.governance.transitions.<name>.approvals` | object |  |
| `projects.<name>.governance.transitions.<name>.approvals.groups` | array |  |
| `projects.<name>.governance.transitions.<name>.approvals.users` | array |  |
| `projects.<name>.governance.transitions.<name>.approvals.require` |  |  |
| `projects.<name>.governance.transitions.<name>.approvals.via` | string | Pattern `^(manual|jira:.+|github:.+/.+)$`. |
| `projects.<name>.governance.transitions.<name>.approvals.group_members` | object |  |
| `projects.<name>.governance.transitions.<name>.evidence` | array |  |
| `projects.<name>.governance.transitions.<name>.controls` | array |  |
| `projects.<name>.governance.retention` | object |  |
| `projects.<name>.governance.retention.evidence` | string | Pattern `^\d+(d|w|m|y)$`. |
| `projects.<name>.governance.retention.logs` | string | Pattern `^\d+(d|w|m|y)$`. |
| `projects.<name>.governance.retention.signed` | boolean |  |
| `projects.<name>.governance.retention.gpg_key` | string |  |
| `projects.<name>.governance.schedule` | object |  |
| `projects.<name>.governance.schedule.revalidate` | object |  |
| `projects.<name>.governance.schedule.revalidate.every` | string | Pattern `^\d+(d|w|m|y)$`. |
| `projects.<name>.governance.schedule.revalidate.approvals` | object |  |
| `projects.<name>.governance.schedule.drift_review` | object |  |
| `projects.<name>.governance.schedule.drift_review.every` | string | Pattern `^\d+(d|w|m|y)$`. |
| `projects.<name>.governance.schedule.drift_review.notify` | string |  |
| `projects.<name>.integrations` | object |  |
| `projects.<name>.integrations.notifier` | object |  |
| `projects.<name>.integrations.ticketer` | object |  |
| `projects.<name>.integrations.docs` | object |  |
| `projects.<name>.calls` | object |  |
| `projects.<name>.calls.<name>.policy` | object |  |
| `projects.<name>.calls.<name>.policy.train_every` | string | Pattern `^\d+(d|w|m|y)$`. |
| `projects.<name>.calls.<name>.policy.min_rows` | integer |  |
| `projects.<name>.calls.<name>.policy.target_precision` | number |  |
| `projects.<name>.calls.<name>.policy.latency_budget_ms` | number |  |
| `projects.<name>.calls.<name>.policy.metric` | string |  |

Connector blocks (`datasource`, `labels`, `integrations.*`) take `type:` plus the options listed on the [connector pages](../connectors/overview.md).
Durations use `<n>d`, `<n>w`, `<n>m` or `<n>y`. Gate expressions are described in [Governance](../governance/overview.md).
