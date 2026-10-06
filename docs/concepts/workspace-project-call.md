# Workspace, project, call

| Term | Meaning |
| --- | --- |
| **Call** | One LLM-backed function being replaced, e.g. `route_rfi`. Has its own versions, threshold, mode and metrics. |
| **Project** | Named group of calls sharing a pipeline and data source, e.g. `autoresponse`. |
| **Workspace** | Top-level container: registry location, secrets, telemetry, scheduler. Usually one per team or environment (`dev`, `prod`). |
| **Path** | `workspace/project/call`, e.g. `prod/autoresponse/route_rfi`. Used in storage keys, the CLI and audit packs. |

`pecca.replace("route_rfi")` with no project uses the implicit workspace `default` and project `default`, like `logging.getLogger()`.
Set `PECCA_WORKSPACE` to change the default workspace; then `project/call` is enough on the CLI.

Pecca keeps only its own metadata. Models and call state live in the workspace **registry** (`local://./.pecca` by default, or MLflow / Unity Catalog / W&B).

```
.pecca/<workspace>/<project>/<call>/
  state.json   versions/vN/   logs/YYYY-MM-DD.jsonl   audit/vN/
```
