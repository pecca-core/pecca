# Connectors

Pecca has **nine interfaces** (eight connector families plus identity) with a few reference implementations each. The community adds the rest.

| Interface | Purpose | Reference implementations |
| --- | --- | --- |
| [DataSource](datasource.md) | read historical rows | `csv`, `parquet`, `postgres`, `databricks`, `snowflake`, `bigquery`, `otel-traces`, `litellm`, `databricks-ai-gateway`, `mcp` |
| [Registry](registry.md) | models, versions, state, logs | `local`, `mlflow`, `wandb` |
| [Notifier](notifier.md) | events to chat | `slack`, `teams`, `webhook`, `mcp` |
| [Ticketer](ticketer.md) | approvals | `jira`, `github`, `manual`, `mcp` |
| [Scheduler](scheduler.md) | periodic jobs | `cron`, `airflow`, `databricks_workflows` |
| [ServingTarget](serving.md) | deploy a version | `onnx_local`, `docker_export`, `databricks_serving` |
| [Secrets](../config/secrets.md) | `${VAR}` values | `env`, `vault`, `aws-secrets-manager` |
| [DocsPublisher](docs-publisher.md) | audit pages | `markdown`, `confluence` |
| [Identity](identity.md) | who is approving | `oidc` (and local default) |

A config block selects an implementation with `type:`. `pecca plugins list` shows everything registered. Optional dependencies are imported only when used (`pip install 'pecca[databricks]'`, `[snowflake]`, `[bigquery]`, `[mlflow]`, `[wandb]`, `[vault]`, `[aws]`, `[pdf]`, `[all]`).
Connectors that talk to the network are tested with mocked HTTP; CI makes no network calls.
