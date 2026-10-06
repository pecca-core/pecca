from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource import _chat
from pecca.connectors.datasource.databricks import DatabricksDataSource

DEFAULT_COLUMNS = {
    "input": "input",
    "llm_output": "output",
    "call_name": "call_name",
    "timestamp": "timestamp",
    "request_id": "request_id",
}


@register("datasource", "databricks-ai-gateway")
class DatabricksAiGatewayDataSource(DatabricksDataSource):
    """Mosaic AI Gateway payload-logging inference table. Required columns: ``databricks_request_id``,
    ``request_time``, ``request`` (JSON), ``response`` (JSON), ``status_code``. ``call_name`` is
    ``endpoint_name`` if given, else the table's ``endpoint_name`` column, else the table name."""

    def __init__(
        self,
        table: str,
        endpoint_name: str | None = None,
        columns: dict[str, Any] | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(table=table, columns={**DEFAULT_COLUMNS, **(columns or {})}, **kw)
        self.endpoint_name = endpoint_name

    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame:
        raw = self._execute(self.build_sql(None, limit))
        if "status_code" in raw:
            raw = raw[raw["status_code"].astype(str) == "200"]
        name = self.endpoint_name or (raw.get("endpoint_name", self.table))
        out = pd.DataFrame(
            {
                "request_id": raw["databricks_request_id"],
                "timestamp": raw["request_time"],
                "input": raw["request"].map(_chat.extract_input),
                "output": raw["response"].map(_chat.extract_output),
            }
        )
        out["call_name"] = name
        return out.dropna(subset=["input", "output"])
