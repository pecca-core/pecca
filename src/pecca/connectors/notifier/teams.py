from __future__ import annotations

from typing import Any

from pecca.connectors.base import register
from pecca.connectors.notifier.webhook import WebhookNotifier


@register("notifier", "teams")
class TeamsNotifier(WebhookNotifier):
    """Microsoft Teams incoming webhook (Adaptive Card)."""

    def __init__(self, webhook: str, **kw: Any) -> None:
        super().__init__(url=webhook, **{k: v for k, v in kw.items() if k in ("headers", "timeout")})

    def _body(self, event: str, payload: dict[str, Any], rendered: str) -> dict[str, Any]:
        return {
            "type": "message",
            "attachments": [{
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard", "version": "1.4",
                    "body": [{"type": "TextBlock", "text": f"Pecca: {event}", "weight": "Bolder"},
                             {"type": "TextBlock", "text": rendered, "wrap": True}],
                },
            }],
        }
