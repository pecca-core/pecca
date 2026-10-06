# Langfuse

Langfuse accepts OpenTelemetry traces. Authenticate with HTTP Basic auth built from your public and secret keys, passed as a ready-made header value.

```yaml
workspace:
  telemetry:
    exporter: otlp
    endpoint: https://cloud.langfuse.com/api/public/otel/v1/traces
    headers: {Authorization: ${LANGFUSE_BASIC_AUTH}}
```
Export `LANGFUSE_BASIC_AUTH` as `Basic <base64(public_key:secret_key)>` (US region: `https://us.cloud.langfuse.com/...`; self-hosted: your own host).

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
In the Traces view, filter on span metadata:
```text
metadata.pecca.served_by = fallback
```

Your wrapped LLM spans (with `gen_ai.*` attributes) nest under the `pecca.call` span, so Langfuse shows which calls the model absorbed and which still reached the LLM.

!!! note "Screenshot"
    Placeholder: `docs/assets/monitoring/langfuse.png` (the maintainer adds a screenshot of the query above).

Pecca has **no vendor-specific code**: it speaks OTLP over HTTP. Endpoint paths and header names are the vendor's and can change, so check their current documentation. To read traces back as training data, see the [`otel-traces` datasource](../connectors/datasource.md).
