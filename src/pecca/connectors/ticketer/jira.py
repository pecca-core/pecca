from __future__ import annotations

from typing import Any

import httpx

from pecca.connectors.base import Ticketer, register
from pecca.core.errors import ConnectorError


def _adf(text: str) -> dict[str, Any]:
    paras = [
        {"type": "paragraph", "content": [{"type": "text", "text": p}]}
        for p in text.split("\n\n")
        if p.strip()
    ]
    return {"type": "doc", "version": 1, "content": paras or [{"type": "paragraph", "content": []}]}


@register("ticketer", "jira")
class JiraTicketer(Ticketer):
    """Jira Cloud REST v3. Approval = changelog transition to ``approved_when.status`` (author)."""

    def __init__(
        self,
        url: str,
        project: str,
        email: str,
        token: str,
        issue_type: str = "Task",
        approved_when: dict[str, str] | None = None,
        approvals_field: str | None = None,
        group_members: dict[str, list[str]] | None = None,
        template: str | None = None,
        **_: Any,
    ) -> None:
        self.url, self.project, self.issue_type = url.rstrip("/"), project, issue_type
        self.auth = (email, token)
        self.approved = (approved_when or {}).get("status", "Approved")
        self.field = approvals_field
        self.members = group_members or {}

    def _req(self, method: str, path: str, **kw: Any) -> Any:
        r = httpx.request(
            method,
            f"{self.url}/rest/api/3{path}",
            auth=self.auth,
            timeout=15,
            headers={"Accept": "application/json"},
            **kw,
        )
        if r.status_code >= 300:
            raise ConnectorError(f"Jira {method} {path} → {r.status_code}", r.text[:200])
        return r.json() if r.content else {}

    def create(self, title: str, body: str, meta: dict[str, Any]) -> str:
        res = self._req(
            "POST",
            "/issue",
            json={
                "fields": {
                    "project": {"key": self.project},
                    "summary": title[:250],
                    "issuetype": {"name": self.issue_type},
                    "description": _adf(body),
                }
            },
        )
        return str(res["key"])

    def get_status(self, ticket_id: str) -> str:
        return str(
            self._req("GET", f"/issue/{ticket_id}?fields=status")["fields"]["status"]["name"]
        )

    def get_approvers(self, ticket_id: str) -> list[dict[str, Any]]:
        issue = self._req(
            "GET", f"/issue/{ticket_id}?expand=changelog&fields=" + (self.field or "status")
        )
        out: list[dict[str, Any]] = []
        for h in issue.get("changelog", {}).get("histories", []):
            for it in h.get("items", []):
                if it.get("field") == "status" and it.get("toString") == self.approved:
                    who = h.get("author", {})
                    name = who.get("emailAddress") or who.get("displayName") or who.get("accountId")
                    groups = [g for g, us in self.members.items() if name in us]
                    out.append(
                        {
                            "principal": name,
                            "group": groups[0] if groups else None,
                            "groups": groups,
                            "ts": h.get("created"),
                        }
                    )
        if self.field:
            for u in issue.get("fields", {}).get(self.field) or []:
                name = u.get("emailAddress") or u.get("displayName")
                out.append(
                    {
                        "principal": name,
                        "group": None,
                        "groups": [g for g, us in self.members.items() if name in us],
                    }
                )
        return out

    def comment(self, ticket_id: str, body: str) -> None:
        self._req("POST", f"/issue/{ticket_id}/comment", json={"body": _adf(body)})

    def close(self, ticket_id: str) -> None:
        for t in self._req("GET", f"/issue/{ticket_id}/transitions")["transitions"]:
            if t["name"].lower() in ("done", "closed", "close", "resolve"):
                self._req(
                    "POST", f"/issue/{ticket_id}/transitions", json={"transition": {"id": t["id"]}}
                )
                return
        raise ConnectorError(f"no close transition available for {ticket_id}")
