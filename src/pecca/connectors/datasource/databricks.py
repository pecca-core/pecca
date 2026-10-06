from __future__ import annotations

import os
from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource._sql import SqlDataSource
from pecca.core.errors import ConnectorError


@register("datasource", "databricks")
class DatabricksDataSource(SqlDataSource):
    """Databricks SQL warehouse via ``databricks-sql-connector`` (extra: ``pecca[databricks]``)."""

    def __init__(
        self,
        server_hostname: str | None = None,
        http_path: str | None = None,
        access_token: str | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(**kw)
        self.host = server_hostname or os.environ.get("DATABRICKS_HOST", "").replace("https://", "")
        self.http_path = http_path or os.environ.get("DATABRICKS_HTTP_PATH", "")
        self.token = access_token or os.environ.get("DATABRICKS_TOKEN", "")

    def _execute(self, sql: str) -> pd.DataFrame:
        try:
            from databricks import sql as dbsql  # type: ignore[attr-defined]
        except ImportError as e:
            raise ConnectorError(
                "databricks-sql-connector is not installed", "pip install 'pecca[databricks]'"
            ) from e
        with (
            dbsql.connect(
                server_hostname=self.host, http_path=self.http_path, access_token=self.token
            ) as conn,
            conn.cursor() as cur,
        ):
            cur.execute(sql)
            cols = [d[0] for d in cur.description]
            return pd.DataFrame([list(r) for r in cur.fetchall()], columns=cols)
