# MLflow and Unity Catalog

```yaml
workspace:
  registry: mlflow://databricks-uc/ml.pecca
```
Each trained version is an MLflow run (params, metrics, artefacts) plus a `pyfunc` model registered in Unity Catalog as `<catalog>.<schema>.<workspace>_<project>_<call>`. Call state is the `state.json` artefact of one "state" run per call; decision logs are small JSONL artefacts (a Delta-table sink is planned). Experiments are named `/Shared/pecca/<workspace>/<project>/<call>` on Databricks.

Install `pip install 'pecca[databricks]'` and authenticate the usual way (`DATABRICKS_HOST`, `DATABRICKS_TOKEN`). For a local trial use `mlflow://sqlite/./mlflow.db`.
Pecca keeps only its own metadata; everything else lives in your registry.
