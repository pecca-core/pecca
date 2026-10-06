from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource._base import MappedDataSource
from pecca.core.errors import ConnectorError

DEFAULT_COLUMNS = {
    "input": "input",
    "llm_output": "output",
    "call_name": "call_name",
    "timestamp": "timestamp",
    "request_id": "request_id",
    "llm_model": "model",
}
IN_KEYS = ("gen_ai.prompt", "input.value", "llm.input_messages", "gen_ai.request.prompt")
OUT_KEYS = (
    "gen_ai.completion",
    "output.value",
    "llm.output_messages",
    "gen_ai.response.completion",
)
MODEL_KEYS = ("gen_ai.request.model", "llm.model_name", "gen_ai.response.model")


def _attr_value(v: dict[str, Any]) -> Any:
    for k in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if k in v:
            return v[k]
    return None


def _first(attrs: dict[str, Any], keys: tuple[str, ...]) -> Any:
    return next((attrs[k] for k in keys if k in attrs), None)


@register("datasource", "otel-traces")
class OtelTracesDataSource(MappedDataSource):
    """OTLP JSON/JSONL exports (``resourceSpans``) or OpenInference parquet.

    Input/output come from ``gen_ai.prompt``/``gen_ai.completion`` or ``input.value``/``output.value``;
    ``call_name`` is the span's ``pecca.call`` attribute, else the span name."""

    def __init__(
        self, path: str | None = None, columns: dict[str, Any] | None = None, **kw: Any
    ) -> None:
        super().__init__(columns={**DEFAULT_COLUMNS, **(columns or {})}, **kw)
        if not path:
            raise ConnectorError("otel-traces datasource needs path=...")
        self.path = Path(path)

    def _spans(self) -> list[dict[str, Any]]:
        if self.path.suffix == ".parquet":
            df = pd.read_parquet(self.path)
            return [
                {
                    "attrs": r,
                    "name": r.get("name"),
                    "id": r.get("context.span_id") or str(i),
                    "ts": r.get("start_time"),
                }
                for i, r in enumerate(df.to_dict("records"))
            ]
        spans = []
        text = self.path.read_text()
        docs = (
            [json.loads(line) for line in text.splitlines() if line.strip()]
            if self.path.suffix == ".jsonl"
            else [json.loads(text)]
        )
        for doc in docs:
            for rs in doc.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    for sp in ss.get("spans", []):
                        attrs = {
                            a["key"]: _attr_value(a.get("value", {}))
                            for a in sp.get("attributes", [])
                        }
                        ns = int(sp.get("startTimeUnixNano", 0))
                        spans.append(
                            {
                                "attrs": attrs,
                                "name": sp.get("name"),
                                "id": f"{sp.get('traceId')}-{sp.get('spanId')}",
                                "ts": datetime.fromtimestamp(ns / 1e9, UTC).isoformat()
                                if ns
                                else None,
                            }
                        )
        return spans

    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame:
        rows = []
        for sp in self._spans():
            a = sp["attrs"]
            inp, out = _first(a, IN_KEYS), _first(a, OUT_KEYS)
            if inp is None or out is None:
                continue
            rows.append(
                {
                    "request_id": sp["id"],
                    "timestamp": sp["ts"],
                    "input": str(inp),
                    "output": str(out),
                    "model": _first(a, MODEL_KEYS),
                    "call_name": a.get("pecca.call") or sp["name"],
                }
            )
        return pd.DataFrame(
            rows, columns=["request_id", "timestamp", "input", "output", "model", "call_name"]
        )
