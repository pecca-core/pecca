# Canonical schema

Pecca needs four fields. You map your columns to them in `connect()` or `datasource.columns`:

| Field | Type | Notes |
| --- | --- | --- |
| `input` | `str`, or `dict[str, str]` of fields | Multiple fields are joined by `input_template`, e.g. `"{subject}\n\n{body}"`. Numeric dicts make a *tabular* call. |
| `llm_output` | `str` | The raw LLM answer. |
| `human_label` | `str` or null | A correction, e.g. an agent's tag. |
| `call_name` | `str` | Column name or `{literal: route_rfi}`. |

Optional, passed through when present: `timestamp`, `llm_model`, `language`, `channel`, `segment`, `request_id`, `latency_ms`, `cost_usd`. Anything else is kept in `extra`.

**Label resolution:** `label = human_label if not null else llm_output` (outputs are normalised: stripped, lower-cased, surrounding quotes/punctuation removed). Each row records its `label_source` (`human` or `llm`).

Late-arriving human labels can be joined from another table with `labels: {type, table/path, join_on, column}`; the datasource must map `request_id`.
