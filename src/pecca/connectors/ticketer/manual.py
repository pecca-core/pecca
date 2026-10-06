from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pecca.connectors.base import Ticketer, register
from pecca.core.errors import NotFoundError
from pecca.core.timeutil import iso


@register("ticketer", "manual")
class ManualTicketer(Ticketer):
    """Writes a pending-approval record; ``pecca approve`` fulfils it (approvals live in call state)."""

    def __init__(self, dir: str | None = None, **_: Any) -> None:  # noqa: A002
        self.dir = Path(dir or Path(os.environ.get("PECCA_HOME") or ".pecca") / "tickets")

    def _f(self, tid: str) -> Path:
        return self.dir / f"{tid}.json"

    def _read(self, tid: str) -> dict[str, Any]:
        if not self._f(tid).exists():
            raise NotFoundError(f"ticket {tid} not found")
        return json.loads(self._f(tid).read_text())  # type: ignore[no-any-return]

    def create(self, title: str, body: str, meta: dict[str, Any]) -> str:
        self.dir.mkdir(parents=True, exist_ok=True)
        tid = f"MAN-{len(list(self.dir.glob('MAN-*.json'))) + 1}"
        self._f(tid).write_text(json.dumps({"id": tid, "title": title, "body": body, "meta": meta,
                                            "status": "pending", "comments": [], "created": iso()}, indent=2))
        return tid

    def get_status(self, ticket_id: str) -> str:
        return str(self._read(ticket_id)["status"])

    def get_approvers(self, ticket_id: str) -> list[dict[str, Any]]:
        return []  # approvals are recorded in call state by `pecca approve`

    def comment(self, ticket_id: str, body: str) -> None:
        t = self._read(ticket_id)
        t["comments"].append({"ts": iso(), "body": body})
        self._f(ticket_id).write_text(json.dumps(t, indent=2))

    def close(self, ticket_id: str) -> None:
        t = self._read(ticket_id)
        t["status"] = "closed"
        self._f(ticket_id).write_text(json.dumps(t, indent=2))
