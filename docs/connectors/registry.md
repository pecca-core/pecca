# Registry

Stores model versions, call state and decision logs. `workspace.registry` selects it:

| URI | Backend |
| --- | --- |
| `local://./.pecca` (default) | files, see [workspace/project/call](../concepts/workspace-project-call.md) |
| `mlflow://databricks-uc/<catalog>.<schema>` | Databricks tracking + Unity Catalog models |
| `mlflow://sqlite/<path>.db`, `mlflow://http(s)/<host>` | local SQLite or an MLflow server |
| `wandb://<entity>/<project>` | Weights & Biases artefacts |

See [MLflow / Unity Catalog](../integrations/mlflow-unity-catalog.md). Interface: `save_model, load_model, list_versions, get_state, set_state, append_logs, read_logs`.
