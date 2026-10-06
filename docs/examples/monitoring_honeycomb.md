# Honeycomb

Honeycomb accepts OTLP over HTTP. Use an ingest API key in the `x-honeycomb-team` header (EU: `api.eu1.honeycomb.io`). For classic environments also send `x-honeycomb-dataset`.

```yaml
workspace:
  telemetry:
    exporter: otlp
    endpoint: https://api.honeycomb.io/v1/traces
    headers: {x-honeycomb-team: ${HONEYCOMB_API_KEY}}
```
Export `HONEYCOMB_API_KEY`.

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
In Query Builder:
```text
WHERE pecca.served_by = fallback
GROUP BY pecca.path
VISUALIZE COUNT, P95(pecca.latency_ms)
```

!!! note "Screenshot"
    Placeholder: `docs/assets/monitoring/honeycomb.png` (the maintainer adds a screenshot of the query above).

Pecca has **no vendor-specific code**: it speaks OTLP over HTTP. Endpoint paths and header names are the vendor's and can change, so check their current documentation. To read traces back as training data, see the [`otel-traces` datasource](../connectors/datasource.md).
