"""OpenAI Agents SDK tool (``agents.function_tool``)."""

from __future__ import annotations

from typing import Any

from pecca.integrations._common import base_tool, import_framework


def tool(call: str, *, project: Any = None, workspace: Any = None, description: str | None = None) -> Any:
    fn = base_tool(call, project, workspace, description)
    agents = import_framework("agents", "openai-agents")
    return agents.function_tool(fn, name_override=fn.__name__, description_override=fn.__doc__)
