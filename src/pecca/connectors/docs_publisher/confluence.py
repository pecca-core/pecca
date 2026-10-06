from __future__ import annotations

from typing import Any

import httpx

from pecca.connectors.base import DocsPublisher, register
from pecca.core.errors import ConnectorError


@register("docs_publisher", "confluence")
class ConfluencePublisher(DocsPublisher):
    """Create or update (by title, under ``parent_page_id``) a Confluence page (storage format)."""

    def __init__(
        self,
        url: str,
        space: str,
        token: str,
        email: str | None = None,
        parent_page_id: str | None = None,
        **_: Any,
    ) -> None:
        self.url, self.space, self.parent = url.rstrip("/"), space, parent_page_id
        self.auth = (email, token) if email else None
        self.h = {} if email else {"Authorization": f"Bearer {token}"}

    def _req(self, method: str, path: str, **kw: Any) -> Any:
        r = httpx.request(
            method, f"{self.url}/rest/api{path}", auth=self.auth, headers=self.h, timeout=20, **kw
        )
        if r.status_code >= 300:
            raise ConnectorError(f"Confluence {method} {path} → {r.status_code}", r.text[:200])
        return r.json()

    def publish(self, title: str, markdown: str, meta: dict[str, Any]) -> str:
        body = {"storage": {"value": markdown, "representation": "storage"}}
        found = self._req(
            "GET", "/content", params={"title": title, "spaceKey": self.space, "expand": "version"}
        )
        if found.get("results"):
            page = found["results"][0]
            res = self._req(
                "PUT",
                f"/content/{page['id']}",
                json={
                    "id": page["id"],
                    "type": "page",
                    "title": title,
                    "space": {"key": self.space},
                    "version": {"number": page["version"]["number"] + 1},
                    "body": body,
                },
            )
        else:
            payload: dict[str, Any] = {
                "type": "page",
                "title": title,
                "space": {"key": self.space},
                "body": body,
            }
            if self.parent:
                payload["ancestors"] = [{"id": self.parent}]
            res = self._req("POST", "/content", json=payload)
        return f"{self.url}{res.get('_links', {}).get('webui', '/pages/' + str(res['id']))}"
