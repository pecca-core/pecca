from __future__ import annotations

from typing import Any

from pecca.connectors._mcp import McpRemote
from pecca.connectors.base import Ticketer, register


def _id(res: Any) -> str:
    if isinstance(res, dict):
        for k in ("id", "key", "ticket_id", "number", "url"):
            if k in res:
                return str(res[k])
    return str(res)


@register("ticketer", "mcp")
class McpTicketer(Ticketer):
    """Ticketing through a remote MCP server.

    ``tool_map`` keys: ``create``, ``get``, ``comment``, optional ``close`` and ``approvers``.
    Conventions: create(title, body) → {id|key}; get(id) → {status, approvers?}; comment(id, body).
    Extra static arguments (e.g. the Jira project) go in ``args: {create: {project: MRM}}``.
    """

    def __init__(
        self,
        url: Any = None,
        tool_map: dict[str, str] | None = None,
        args: dict[str, dict[str, Any]] | None = None,
        **_: Any,
    ) -> None:
        self.remote = McpRemote(url, tool_map, args)

    def create(self, title: str, body: str, meta: dict[str, Any]) -> str:
        return _id(self.remote.call("create", {"title": title, "body": body}))

    def get_status(self, ticket_id: str) -> str:
        res = self.remote.call("get", {"id": ticket_id})
        return str(res.get("status", "unknown")) if isinstance(res, dict) else str(res)

    def get_approvers(self, ticket_id: str) -> list[dict[str, Any]]:
        if "approvers" in self.remote.tool_map:
            res = self.remote.call("approvers", {"id": ticket_id})
        else:
            res = self.remote.call("get", {"id": ticket_id})
            res = res.get("approvers", []) if isinstance(res, dict) else []
        return [a if isinstance(a, dict) else {"principal": str(a)} for a in (res or [])]

    def comment(self, ticket_id: str, body: str) -> None:
        self.remote.call("comment", {"id": ticket_id, "body": body})

    def close(self, ticket_id: str) -> None:
        self.remote.call("close", {"id": ticket_id})
