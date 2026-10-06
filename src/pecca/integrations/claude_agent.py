"""Claude Agent SDK tool (``claude_agent_sdk.tool``).

The SDK exposes tools through an in-process MCP server::

    server = claude_agent_sdk.create_sdk_mcp_server("pecca", tools=[pecca.integrations.claude_agent.tool("route_rfi")])
"""

from __future__ import annotations

import json
from typing import Any

from pecca.integrations._common import base_tool, import_framework


def tool(
    call: str, *, project: Any = None, workspace: Any = None, description: str | None = None
) -> Any:
    fn = base_tool(call, project, workspace, description)
    sdk = import_framework("claude_agent_sdk", "claude-agent-sdk")

    @sdk.tool(fn.__name__, fn.__doc__ or "", {"text": str})  # type: ignore[untyped-decorator]
    async def handler(args: dict[str, Any]) -> dict[str, Any]:
        return {"content": [{"type": "text", "text": json.dumps(fn(args["text"]))}]}

    return handler
