from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors.base import register
from pecca.connectors.datasource._sql import SqlDataSource


@register("datasource", "postgres")
class PostgresDataSource(SqlDataSource):
    """``dsn`` (libpq connection string / URL) or ``host, port, dbname, user, password``."""

    def __init__(
        self,
        dsn: str | None = None,
        host: str | None = None,
        port: int = 5432,
        dbname: str | None = None,
        user: str | None = None,
        password: str | None = None,
        **kw: Any,
    ) -> None:
        super().__init__(**kw)
        self.conn_kwargs = (
            {}
            if dsn
            else {
                k: v
                for k, v in dict(
                    host=host, port=port, dbname=dbname, user=user, password=password
                ).items()
                if v is not None
            }
        )
        self.dsn = dsn or ""

    def _execute(self, sql: str) -> pd.DataFrame:
        import psycopg

        with psycopg.connect(self.dsn, **self.conn_kwargs) as conn:  # type: ignore[arg-type]
            cur = conn.execute(sql)
            cols = [d.name for d in cur.description or []]
            return pd.DataFrame(cur.fetchall(), columns=cols)
