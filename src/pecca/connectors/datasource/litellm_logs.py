from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource import _chat
from pecca.connectors.datasource.postgres import PostgresDataSource

DEFAULT_COLUMNS = {"input": "input", "llm_output": "output", "call_name": "call_name",
                   "timestamp": "timestamp", "request_id": "request_id", "llm_model": "model"}


@register("datasource", "litellm")
class LiteLLMDataSource(PostgresDataSource):
    """LiteLLM proxy ``LiteLLM_SpendLogs`` (Postgres). Required columns: ``request_id``, ``model``,
    ``startTime``, ``messages`` (JSON), ``response`` (JSON). ``call_name`` = ``metadata.<call_name_key>``
    if ``call_name_key`` is set, otherwise the ``model``."""

    def __init__(self, table: str = '"LiteLLM_SpendLogs"', call_name_key: str | None = None,
                 columns: dict[str, Any] | None = None, **kw: Any) -> None:
        super().__init__(table=table, columns={**DEFAULT_COLUMNS, **(columns or {})}, **kw)
        self.call_name_key = call_name_key

    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame:
        raw = self._execute(self.build_sql(None, limit))
        meta = raw["metadata"].map(_chat.loads) if "metadata" in raw else pd.Series([None] * len(raw))
        out = pd.DataFrame({
            "request_id": raw["request_id"],
            "timestamp": raw["startTime"],
            "input": raw["messages"].map(_chat.extract_input),
            "output": raw["response"].map(_chat.extract_output),
            "model": raw["model"],
        })
        if self.call_name_key:
            out["call_name"] = [(m or {}).get(self.call_name_key) if isinstance(m, dict) else None for m in meta]
        else:
            out["call_name"] = raw["model"]
        return out.dropna(subset=["input", "output"])
