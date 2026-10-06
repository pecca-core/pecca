from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pecca.connectors.base import DocsPublisher, register


@register("docs_publisher", "markdown")
class MarkdownPublisher(DocsPublisher):
    def __init__(self, dir: str = "docs_out", **_: Any) -> None:  # noqa: A002
        self.dir = Path(dir)

    def publish(self, title: str, markdown: str, meta: dict[str, Any]) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / (re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-") + ".md")
        p.write_text(markdown)
        return str(p)
