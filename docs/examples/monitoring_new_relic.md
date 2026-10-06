# New Relic

New Relic ingests OTLP directly. Use your ingest licence key in the `api-key` header (EU accounts use `otlp.eu01.nr-data.net`).

```yaml
workspace:
  telemetry:
    exporter: otlp
    endpoint: https://otlp.nr-data.net/v1/traces
    headers: {api-key: ${NEW_RELIC_LICENSE_KEY}}
```
Export `NEW_RELIC_LICENSE_KEY` (an *ingest* licence key).

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
In the query builder (NRQL):
```text
SELECT count(*) FROM Span WHERE pecca.served_by = 'fallback' FACET pecca.path SINCE 1 day ago
```

!!! note "Screenshot"
    Placeholder: `docs/assets/monitoring/new_relic.png` (the maintainer adds a screenshot of the query above).

Pecca has **no vendor-specific code**: it speaks OTLP over HTTP. Endpoint paths and header names are the vendor's and can change, so check their current documentation. To read traces back as training data, see the [`otel-traces` datasource](../connectors/datasource.md).
