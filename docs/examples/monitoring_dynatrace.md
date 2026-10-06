# Dynatrace

Dynatrace ingests OTLP at an environment-specific endpoint. Use an API token with the `openTelemetryTrace.ingest` scope in the `Authorization` header.

```yaml
workspace:
  telemetry:
    exporter: otlp
    endpoint: https://<environment-id>.live.dynatrace.com/api/v2/otlp/v1/traces
    headers: {Authorization: ${DYNATRACE_API_TOKEN_HEADER}}
```
Export `DYNATRACE_API_TOKEN_HEADER` as `Api-Token <token>`.

Pecca resolves `${VAR}` through its [secrets connector](../config/secrets.md); the value never appears in `.pecca/config.resolved.yaml`.

## Span attributes
Every `@pecca.replace` invocation emits one span named `pecca.call`:

| Attribute | Meaning |
| --- | --- |
| `pecca.path` | `workspace/project/call` |
| `pecca.mode` | `record`, `shadow` or `live` |
| `pecca.version` | model version used |
| `pecca.served_by` | `llm`, `model` or `fallback` |
| `pecca.confidence` | calibrated confidence |
| `pecca.agreement` | model agreed with the LLM (shadow only) |
| `pecca.latency_ms` | wall time of the call |

## Finding where the LLM is still used
In Notebooks / Grail (DQL):
```text
fetch spans
| filter pecca.served_by == "fallback"
| summarize count(), by:{pecca.path}
```

!!! note "Screenshot"
    Placeholder: `docs/assets/monitoring/dynatrace.png` (the maintainer adds a screenshot of the query above).

Pecca has **no vendor-specific code**: it speaks OTLP over HTTP. Endpoint paths and header names are the vendor's and can change, so check their current documentation. To read traces back as training data, see the [`otel-traces` datasource](../connectors/datasource.md).
