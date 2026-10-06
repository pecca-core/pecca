# DataSource

`read(call=None, since=None, limit=None) -> DataFrame` in the [canonical schema](../concepts/canonical-schema.md). All implementations map your columns with `columns:` (+ optional `input_template`).

```yaml
datasource:
  type: databricks
  table: ai_gateway.inference_logs
  columns: {input: email_body, llm_output: output, human_label: pega_tag, call_name: endpoint}
```
| `type` | Config | Notes |
| --- | --- | --- |
| `csv`, `parquet` | `path` | pandas |
| `postgres` | `dsn` or `host, port, dbname, user, password`; `table` or `query` | `psycopg` |
| `databricks` | `server_hostname, http_path, access_token` (or `DATABRICKS_*` env); `table`/`query` | `pecca[databricks]` |
| `snowflake` | `account, user, password, warehouse, database, schema, role`; `table`/`query` | `pecca[snowflake]` |
| `bigquery` | `project`; `table`/`query` | `pecca[bigquery]` |
| `otel-traces` | `path` to OTLP JSON/JSONL or OpenInference parquet | `gen_ai.prompt`/`gen_ai.completion` or `input.value`/`output.value` become input/output; call = `pecca.call` attribute or span name |
| `litellm` | Postgres connection; `call_name_key` | LiteLLM `LiteLLM_SpendLogs`: needs `request_id, model, startTime, messages, response` (+ `metadata`) |
| `databricks-ai-gateway` | `table`, `endpoint_name` | payload-logging inference table: needs `databricks_request_id, request_time, request, response, status_code` |
| `mcp` | `url`, `tool_map: {read: <tool>}` | see [MCP](mcp.md) |

Table names are validated; `query:` is wrapped as a subquery so `since`/`limit` can be pushed down.
