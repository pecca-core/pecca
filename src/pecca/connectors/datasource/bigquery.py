from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource._sql import SqlDataSource
from pecca.core.errors import ConnectorError


@register("datasource", "bigquery")
class BigQueryDataSource(SqlDataSource):
    """BigQuery via ``google-cloud-bigquery`` (extra: ``pecca[bigquery]``); uses application default credentials."""

    def __init__(self, project: str | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.project = project

    def _execute(self, sql: str) -> pd.DataFrame:
        try:
            from google.cloud import bigquery
        except ImportError as e:
            raise ConnectorError("google-cloud-bigquery is not installed", "pip install 'pecca[bigquery]'") from e
        df: pd.DataFrame = bigquery.Client(project=self.project).query(sql).to_dataframe()
        return df
