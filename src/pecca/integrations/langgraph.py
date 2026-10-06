"""LangGraph / LangChain tool (``langchain_core.tools.tool``)."""

from __future__ import annotations

from typing import Any

from pecca.integrations._common import base_tool, import_framework


def tool(call: str, *, project: Any = None, workspace: Any = None, description: str | None = None) -> Any:
    fn = base_tool(call, project, workspace, description)
    lc = import_framework("langchain_core.tools", "langchain-core")
    return lc.tool(fn.__name__, description=fn.__doc__)(fn)
