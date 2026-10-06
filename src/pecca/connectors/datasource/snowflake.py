from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource._sql import SqlDataSource
from pecca.core.errors import ConnectorError


@register("datasource", "snowflake")
class SnowflakeDataSource(SqlDataSource):
    """Snowflake via ``snowflake-connector-python`` (extra: ``pecca[snowflake]``). Extra kwargs go to ``connect``."""

    def __init__(self, account: str | None = None, user: str | None = None, password: str | None = None,
                 warehouse: str | None = None, database: str | None = None, schema: str | None = None,
                 role: str | None = None, **kw: Any) -> None:
        own = {k: kw.pop(k) for k in list(kw) if k not in ("table", "query", "columns", "input_template")}
        super().__init__(**kw)
        self.conn = {k: v for k, v in dict(account=account, user=user, password=password, warehouse=warehouse,
                                           database=database, schema=schema, role=role).items() if v is not None} | own

    def _execute(self, sql: str) -> pd.DataFrame:
        try:
            import snowflake.connector as sf
        except ImportError as e:
            raise ConnectorError("snowflake-connector-python is not installed", "pip install 'pecca[snowflake]'") from e
        with sf.connect(**self.conn) as conn, conn.cursor() as cur:
            cur.execute(sql)
            df: pd.DataFrame = cur.fetch_pandas_all()
            df.columns = [c.lower() if c.isupper() else c for c in df.columns]
            return df
