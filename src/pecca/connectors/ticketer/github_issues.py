from __future__ import annotations

from typing import Any

import httpx

from pecca.connectors.base import Ticketer, register
from pecca.core.errors import ConnectorError


@register("ticketer", "github_issues")
class GithubIssuesTicketer(Ticketer):
    """Approval = a ``/approve`` comment by a user; groups come from ``group_members`` config."""

    def __init__(self, repo: str, token: str, group_members: dict[str, list[str]] | None = None,
                 api_url: str = "https://api.github.com", **_: Any) -> None:
        self.repo, self.api = repo, api_url.rstrip("/")
        self.members = group_members or {}
        self.h = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    def _req(self, method: str, path: str, **kw: Any) -> Any:
        r = httpx.request(method, f"{self.api}/repos/{self.repo}{path}", headers=self.h, timeout=15, **kw)
        if r.status_code >= 300:
            raise ConnectorError(f"GitHub {method} {path} → {r.status_code}", r.text[:200])
        return r.json()

    def create(self, title: str, body: str, meta: dict[str, Any]) -> str:
        return str(self._req("POST", "/issues", json={"title": title, "body": body})["number"])

    def get_status(self, ticket_id: str) -> str:
        return str(self._req("GET", f"/issues/{ticket_id}")["state"])

    def get_approvers(self, ticket_id: str) -> list[dict[str, Any]]:
        out = []
        for c in self._req("GET", f"/issues/{ticket_id}/comments"):
            if str(c.get("body", "")).strip().lower().startswith("/approve"):
                user = c["user"]["login"]
                groups = [g for g, us in self.members.items() if user in us]
                out.append({"principal": user, "group": groups[0] if groups else None,
                            "groups": groups, "ts": c.get("created_at")})
        return out

    def comment(self, ticket_id: str, body: str) -> None:
        self._req("POST", f"/issues/{ticket_id}/comments", json={"body": body})

    def close(self, ticket_id: str) -> None:
        self._req("PATCH", f"/issues/{ticket_id}", json={"state": "closed"})
