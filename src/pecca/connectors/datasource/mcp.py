from __future__ import annotations

from typing import Any

import pandas as pd

from pecca.connectors._mcp import McpRemote
from pecca.connectors.base import register
from pecca.connectors.datasource._base import MappedDataSource


@register("datasource", "mcp")
class McpDataSource(MappedDataSource):
    """Read rows from a remote MCP tool. ``tool_map: {read: <tool>}``; the tool returns a JSON list of
    row objects (or ``{rows: [...]}``). ``since``/``limit`` are passed as arguments when set."""

    def __init__(self, url: Any = None, tool_map: dict[str, str] | None = None,
                 args: dict[str, Any] | None = None, **kw: Any) -> None:
        super().__init__(**kw)
        self.remote = McpRemote(url, tool_map, {"read": args or {}})

    def _read_raw(self, since: str | None, limit: int | None) -> pd.DataFrame:
        a: dict[str, Any] = {}
        if since:
            a["since"] = since
        if limit:
            a["limit"] = limit
        res = self.remote.call("read", a)
        rows = res.get("rows", res) if isinstance(res, dict) else res
        return pd.DataFrame(rows)
