# Governance

Governance is **six primitives**, not policies. Industry [profiles](profiles.md) are editable templates with no legal claim.

| Primitive | What it does |
| --- | --- |
| **Gates** | Expressions such as `agreement >= 0.90 and shadow_days >= 14` over `cv_metric`, `cv_f1`, `rows`, `agreement`, `shadow_days`, `fallback_rate`, `drift`, `llm_metric`, `min_class_count`. Parsed by a small safe parser: no `eval`. |
| **Approvals** | `{groups, users, require: all\|any\|<n>, via: manual \| jira:PROJ \| github:owner/repo}`. Satisfied when the ticketer (or `pecca approve`) reports the required principals. |
| **Evidence** | Audit-pack sections that must exist for the version (`model_card`, `confusion_matrix`, `data_lineage`, `threshold_rationale`, `calibration`, `per_class_report`, `drift_report`, `human_oversight_log`). |
| **Retention** | `{evidence: 7y, logs: 2y, signed: true}` is stored and written into the audit pack. v0.1 does not delete anything. `signed` writes a sha256 manifest (plus a detached GPG signature if `gpg_key` is set). |
| **Schedule** | `revalidate` and `drift_review` intervals; `train_every` per call. `pecca scheduler run` evaluates what is due. |
| **Controls mapping** | Free-form strings attached to transitions; rendered in the audit pack. No semantics. |

```yaml
governance:
  extends: default
  transitions:
    shadow->live:
      gates: ["agreement >= 0.90", "shadow_days >= 14"]
      approvals: {groups: [model-risk], require: all, via: jira:MRM}
      evidence: [model_card, confusion_matrix, data_lineage, threshold_rationale]
      controls: ["ISO42001-8.4"]
  retention: {evidence: 7y, logs: 2y, signed: true}
  schedule:
    revalidate: {every: 365d}
    drift_review: {every: 30d, notify: "slack:#ml-governance"}
```
`pecca promote` returns a `Decision(allowed, failing_gates, pending_approvals, evidence_missing)`. `--force` needs `PECCA_ALLOW_FORCE=1` and is recorded in the call's history and the audit pack.

!!! note
    Gates assume *higher is better* for `cv_metric`. For regression calls (`rmse`), write lower-is-better gates, e.g. `cv_metric <= 5`.
