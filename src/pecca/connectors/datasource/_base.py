"""Shared base for datasource connectors: raw read + canonical mapping."""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

import pandas as pd

from pecca.connectors.base import DataSource
from pecca.core.errors import SchemaError
from pecca.core.timeutil import parse_since
from pecca.data.dataset import canonicalize


class MappedDataSource(DataSource):
    """Subclasses implement ``_read_raw``; mapping to the canonical schema is shared."""

    def __init__(
        self,
        columns: dict[str, Any] | None = None,
        input_template: str | None = None,
        **_: Any,
    ) -> None:
        self.columns = columns or {}
        self.input_template = input_template

    @abstractmethod
    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame: ...

    def read(
        self, call: str | None = None, since: str | None = None, limit: int | None = None
    ) -> pd.DataFrame:
        raw = self._read_raw(since, limit)
        if not self.columns:
            raise SchemaError("no column mapping given", "pass columns={'input': ..., ...}")
        df = canonicalize(raw, self.columns, self.input_template)
        if since and "timestamp" in df and df["timestamp"].notna().any():
            cutoff = parse_since(since)
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            assert cutoff is not None
            df = df[ts >= pd.Timestamp(cutoff)]
        if call is not None:
            df = df[df["call_name"] == call]
        if limit is not None:
            df = df.head(limit)
        return df.reset_index(drop=True)
