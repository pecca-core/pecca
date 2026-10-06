"""Strands Agents tool (``strands.tool``)."""

from __future__ import annotations

from typing import Any

from pecca.integrations._common import base_tool, import_framework


def tool(call: str, *, project: Any = None, workspace: Any = None, description: str | None = None) -> Any:
    fn = base_tool(call, project, workspace, description)
    strands = import_framework("strands", "strands-agents")
    return strands.tool(fn, name=fn.__name__, description=fn.__doc__)
