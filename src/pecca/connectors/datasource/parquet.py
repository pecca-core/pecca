from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource._base import MappedDataSource
from pecca.core.errors import ConnectorError


@register("datasource", "parquet")
class ParquetDataSource(MappedDataSource):
    def __init__(self, path: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        if not path:
            raise ConnectorError("parquet datasource needs path=...")
        self.path = path

    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame:
        return pd.read_parquet(self.path)

    def describe(self) -> dict[str, Any]:
        return {"type": "parquet", "path": self.path}
