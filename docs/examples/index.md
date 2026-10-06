# Examples

Every notebook has committed outputs and an *Open in Colab* badge, and runs offline: mock LLM, scripted agent models, mocked HTTP. A few use local Docker containers (Postgres, Vault, Jaeger, Tempo + Grafana); with `PECCA_SKIP_DOCKER=1`, which CI sets, those cells are skipped and a fallback runs. CI executes every notebook with `PECCA_TEST_SMALL=1`. The Colab badges work for notebooks that don't need Docker.

| Notebook | What it shows | Runtime | Needs Docker? |
| --- | --- | --- | --- |
| [Quickstart](quickstart.md) | connect → profile → train → shadow → status → audit pack | ~3 min | no |
| [LangGraph](agent_langgraph.md) | Pecca as the agent's first tool | ~15 s | no |
| [Strands Agents](agent_strands.md) | same, with Strands | ~15 s | no |
| [Google ADK](agent_google_adk.md) | same, with ADK | ~15 s | no |
| [OpenAI Agents SDK](agent_openai_agents.md) | same, with the Agents SDK | ~15 s | no |
| [Claude Agent SDK](agent_claude_agent_sdk.md) | same, through the SDK's MCP server | ~30 s | no |
| [Connector: data sources](connector_datasource.md) | CSV, Parquet, Postgres (container) and OTel traces read into one schema | ~10 s | yes |
| [Connector: registry](connector_registry.md) | the same call on the `local` and `mlflow` registries | ~35 s | no |
| [Connector: notifiers](connector_notifier.md) | webhook, Slack and Teams payloads; events firing in a project | ~15 s | no |
| [Connector: ticketers and the approval loop](connector_ticketer.md) | full approval loop with manual, GitHub Issues and Jira | ~25 s | no |
| [Connector: schedulers](connector_scheduler.md) | cron, `pecca scheduler run --once`, Airflow DAG, Databricks job JSON | ~20 s | no |
| [Connector: serving targets](connector_serving.md) | serving latency (pickle vs ONNX) and the `docker_export` folder | ~15 s | no |
| [Connector: secrets](connector_secrets.md) | env, HashiCorp Vault (container) and AWS Secrets Manager (mocked) | ~10 s | yes |
| [Connector: docs publishers](connector_docs_publisher.md) | Markdown folder and Confluence (mocked) publishing | ~15 s | no |
| [Monitoring with Jaeger](monitoring_jaeger.md) | OTLP spans into a local Jaeger, read back via its API | ~20 s | yes |
| [Monitoring with Grafana Tempo](monitoring_grafana_tempo.md) | spans in Tempo, TraceQL queries, provisioned Grafana dashboard | ~90 s | yes |
| [Monitoring with MLflow](monitoring_mlflow.md) | what MLflow shows for Pecca versions, state and logs | ~40 s | no |

## Monitoring
The Jaeger, Grafana Tempo and MLflow notebooks above run real stacks from `examples/monitoring/` (Docker Compose). For other vendors Pecca has no vendor-specific code: these are config-only guides:
[Datadog](monitoring_datadog.md) · [New Relic](monitoring_new_relic.md) · [Honeycomb](monitoring_honeycomb.md) · [Langfuse](monitoring_langfuse.md) · [Dynatrace](monitoring_dynatrace.md).
See also [OpenTelemetry](../integrations/opentelemetry.md).
