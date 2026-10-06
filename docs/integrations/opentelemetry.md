# OpenTelemetry

Every invocation emits one span `pecca.call` with attributes:

| Attribute | Meaning |
| --- | --- |
| `pecca.path` | `workspace/project/call` |
| `pecca.mode` | `record`, `shadow` or `live` |
| `pecca.version` | model version used |
| `pecca.served_by` | `llm`, `model` or `fallback` |
| `pecca.confidence` | calibrated confidence |
| `pecca.agreement` | model agreed with the LLM (shadow) |
| `pecca.latency_ms` | wall time of the call |

Your wrapped LLM span nests under it, so GenAI semantic-convention (`gen_ai.*`) spans stay intact. Without a configured exporter the tracer is a no-op.
```yaml
workspace:
  telemetry: {exporter: otlp, endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}}
```
Filter `pecca.served_by = fallback` to see where the LLM is still used. Pecca has **no** anonymous usage telemetry. Traces can be read back as training data with the `otel-traces` datasource.
