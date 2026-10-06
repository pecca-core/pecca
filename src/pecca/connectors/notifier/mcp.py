from __future__ import annotations

from typing import Any

from pecca.connectors._mcp import McpRemote
from pecca.connectors.base import Notifier, register


@register("notifier", "mcp")
class McpNotifier(Notifier):
    """Send via a remote MCP tool. ``tool_map: {send: <tool>}``; args: ``event``, ``text`` (+ ``args``)."""

    def __init__(
        self,
        url: Any = None,
        tool_map: dict[str, str] | None = None,
        args: dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        self.remote = McpRemote(url, tool_map, {"send": args or {}})

    def send(self, event: str, payload: dict[str, Any], rendered: str) -> None:
        self.remote.call("send", {"event": event, "text": rendered})
