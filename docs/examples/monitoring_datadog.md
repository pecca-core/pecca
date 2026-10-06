# Datadog

Send Pecca spans to Datadog through the Datadog Agent's OTLP receiver (enable `otlp_config.receiver.protocols.http` in the Agent). The Agent holds your API key, so Pecca needs no auth header. To skip the Agent, Datadog also offers a direct OTLP intake; it needs a `dd-api-key` header, so add `headers: {dd-api-key: ${DD_API_KEY}}` and use the endpoint from Datadog's current docs.

```yaml
workspace:
  telemetry:
    exporter: otlp
    endpoint: http://localhost:4318/v1/traces
```
Set nothing else; for the direct intake export `DD_API_KEY`.

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
In Trace Explorer / APM search:
```text
service:pecca @pecca.served_by:fallback
```

!!! note "Screenshot"
    Placeholder: `docs/assets/monitoring/datadog.png` (the maintainer adds a screenshot of the query above).

Pecca has **no vendor-specific code**: it speaks OTLP over HTTP. Endpoint paths and header names are the vendor's and can change, so check their current documentation. To read traces back as training data, see the [`otel-traces` datasource](../connectors/datasource.md).
