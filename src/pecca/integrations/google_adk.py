"""Google ADK tool (``google.adk.tools.FunctionTool``). ADK reads name and description from the function."""

from __future__ import annotations

from typing import Any

from pecca.integrations._common import base_tool, import_framework


def tool(call: str, *, project: Any = None, workspace: Any = None, description: str | None = None) -> Any:
    fn = base_tool(call, project, workspace, description)
    adk = import_framework("google.adk.tools", "google-adk")
    return adk.FunctionTool(func=fn)
