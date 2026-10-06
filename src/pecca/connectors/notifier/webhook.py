from __future__ import annotations

from typing import Any

import httpx

from pecca.connectors.base import Notifier, register
from pecca.core.errors import ConnectorError


@register("notifier", "webhook")
class WebhookNotifier(Notifier):
    """Generic JSON POST: ``{"event", "payload", "text"}``."""

    def __init__(
        self, url: str, headers: dict[str, str] | None = None, timeout: float = 10.0, **_: Any
    ) -> None:
        self.url, self.headers, self.timeout = url, headers or {}, timeout

    def _body(self, event: str, payload: dict[str, Any], rendered: str) -> dict[str, Any]:
        return {"event": event, "payload": payload, "text": rendered}

    def send(self, event: str, payload: dict[str, Any], rendered: str) -> None:
        r = httpx.post(
            self.url,
            json=self._body(event, payload, rendered),
            headers=self.headers,
            timeout=self.timeout,
        )
        if r.status_code >= 300:
            raise ConnectorError(f"webhook returned {r.status_code}", r.text[:200])
