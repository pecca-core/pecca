# Modes

| Mode | What `@pecca.replace` does |
| --- | --- |
| `off` | Calls your function only. Nothing is logged. |
| `record` | Calls your function and logs `(input, llm_output, ts)`. Returns the LLM output. |
| `shadow` | Calls your function **and** the model, logs both with confidence and agreement. Returns the LLM output. |
| `live` | Calls the model. If `confidence >= threshold` it returns the model's answer (`served_by=model`), otherwise it calls your function (`served_by=fallback`). |

Allowed transitions: `off ↔ record`, `record → shadow`, `shadow → live`, `live → shadow`, anything → `off`. **`record → live` is forbidden.**
Governance gates run on `record → shadow` and `shadow → live` (`pecca promote`). Retraining a `live` call puts it back in `shadow`: the new model must earn live status again.

Mode resolution: explicit `mode=` argument, then the stored call state, then `record`.

Pecca never raises into your code. If anything inside Pecca fails (registry, model load, logging) the error is logged and your function's result is returned. Exceptions from *your* function propagate normally. Async functions are supported.
Each call emits one OpenTelemetry span `pecca.call` (see [OpenTelemetry](../integrations/opentelemetry.md)).
