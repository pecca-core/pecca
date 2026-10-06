"""Tiny synchronous helper over the ``mcp`` 2.x client used by the MCP transport adapters."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from pecca.core.errors import ConnectorError


class McpRemote:
    """``server`` is a streamable-HTTP URL, or an in-process ``MCPServer`` (tests)."""

    def __init__(
        self,
        server: Any,
        tool_map: dict[str, str] | None = None,
        static_args: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        if not server:
            raise ConnectorError("mcp transport needs url=...", "or use transport: rest")
        self.server = server
        self.tool_map = tool_map or {}
        self.static_args = static_args or {}
        self._tools: set[str] | None = None

    def _run(self, coro_fn: Any) -> Any:
        from mcp.client import Client

        async def go() -> Any:
            async with Client(self.server) as c:
                return await coro_fn(c)

        try:
            return asyncio.run(go())
        except ConnectorError:
            raise
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(
                f"MCP call failed: {e}", "check the server URL, or use transport: rest"
            ) from e

    def tool_names(self) -> set[str]:
        if self._tools is None:
            res = self._run(lambda c: c.list_tools())
            self._tools = {t.name for t in res.tools}
        return self._tools

    def resolve(self, method: str) -> str:
        name = self.tool_map.get(method)
        if not name or name not in self.tool_names():
            raise ConnectorError(
                f"no MCP tool mapped for {method!r} (tool_map={self.tool_map}, server offers {sorted(self.tool_names())})",
                "add it to tool_map in the config, or use transport: rest",
            )
        return name

    def call(self, method: str, args: dict[str, Any]) -> Any:
        name = self.resolve(method)
        merged = {**self.static_args.get(method, {}), **args}
        res = self._run(lambda c: c.call_tool(name, merged))
        if getattr(res, "is_error", False):
            raise ConnectorError(f"MCP tool {name} returned an error", _text(res)[:200])
        sc = getattr(res, "structured_content", None)
        if sc is not None:
            return sc.get("result", sc) if isinstance(sc, dict) and set(sc) == {"result"} else sc
        text = _text(res)
        try:
            return json.loads(text)
        except ValueError:
            return text


def _text(res: Any) -> str:
    return "".join(getattr(p, "text", "") for p in (res.content or []))
