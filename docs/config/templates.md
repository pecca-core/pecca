# Templates

`pecca init` copies the shipped Jinja2 templates into `./templates/`. Files there override the built-ins.

| Template | Used for |
| --- | --- |
| `approval_ticket.md.j2` | the ticket body when approvals are required |
| `slack_event.md.j2` | notifier messages |
| `model_card.md.j2` | the model card (also an audit-pack section) |
| `confluence_page.html.j2` | the Confluence page wrapper |
| `audit_pack/*.md.j2` | one template per audit-pack section |

## Context variables
| Variable | Content |
| --- | --- |
| `call` | `{path, name, mode, version}` |
| `model` | the `ModelVersion`: `candidate`, `metric_name`, `metric`, `metric_std`, `llm_metric`, `threshold`, `expected_fallback_rate`, `latency_ms`, `lineage`, `leaderboard`, `per_class`, `confusion_matrix`, `calibration_curve`, `environment`, … |
| `shadow` | the `EvalReport` for the last 30 days: `agreement_rate`, `fallback_rate`, `n_rows`, `disagreements`, `drift_score`, `window` |
| `audit` | section data: `approvals`, `ticket`, `controls`, `history`, `retention`, plus per-section extras |
| `policy` | the `shadow->live` governance config plus `policy.call` |
| `workspace`, `project` | names |
| `now` | ISO timestamp |

Filters: `fmt(digits=3)` (numbers, `n/a` for null) and `pct`. Undefined variables are errors, so typos fail loudly.
