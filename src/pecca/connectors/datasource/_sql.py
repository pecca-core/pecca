"""SQL-backed datasources share query construction; subclasses only implement ``_execute``."""

from __future__ import annotations

import re
from abc import abstractmethod
from typing import Any

import pandas as pd

from pecca.connectors.datasource._base import MappedDataSource
from pecca.core.errors import ConnectorError
from pecca.core.timeutil import parse_since

_IDENT = re.compile(r'^[\w$."`-]+$')


class SqlDataSource(MappedDataSource):
    def __init__(self, table: str | None = None, query: str | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        if not table and not query:
            raise ConnectorError("SQL datasource needs table=... or query=...")
        if table and not _IDENT.match(table):
            raise ConnectorError(f"unsafe table name {table!r}", "use [catalog.][schema.]table")
        self.table, self.query = table, query

    @abstractmethod
    def _execute(self, sql: str) -> pd.DataFrame: ...

    def build_sql(self, since: str | None, limit: int | None) -> str:
        base = f"SELECT * FROM ({self.query}) AS _pecca_q" if self.query else f"SELECT * FROM {self.table}"
        ts = self.columns.get("timestamp")
        if since and isinstance(ts, str) and _IDENT.match(ts):
            cutoff = parse_since(since)
            assert cutoff is not None
            base += f" WHERE {ts} >= '{cutoff.strftime('%Y-%m-%d %H:%M:%S')}'"
        if limit:
            base += f" LIMIT {int(limit)}"
        return base

    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame:
        return self._execute(self.build_sql(since, limit))

    def describe(self) -> dict[str, Any]:
        return {"type": type(self).__name__, "table": self.table, "query": bool(self.query)}
