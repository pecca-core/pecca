from __future__ import annotations

from typing import Any

from pecca.connectors.base import register
from pecca.connectors.notifier.webhook import WebhookNotifier


@register("notifier", "slack")
class SlackNotifier(WebhookNotifier):
    """Slack incoming webhook."""

    def __init__(self, webhook: str, channel: str | None = None, **kw: Any) -> None:
        super().__init__(url=webhook, **{k: v for k, v in kw.items() if k in ("headers", "timeout")})
        self.channel = channel

    def _body(self, event: str, payload: dict[str, Any], rendered: str) -> dict[str, Any]:
        body: dict[str, Any] = {"text": rendered}
        channel = payload.get("channel") or self.channel
        if channel:
            body["channel"] = channel
        return body
