"""``workspace/project/call`` paths."""

from __future__ import annotations

import os
from dataclasses import dataclass

from pecca.core.errors import PeccaError

DEFAULT = "default"


@dataclass(frozen=True)
class CallPath:
    workspace: str
    project: str
    call: str

    @classmethod
    def parse(
        cls, text: str, workspace: str | None = None, project: str | None = None
    ) -> CallPath:
        parts = [p for p in text.split("/") if p]
        env_ws = os.environ.get("PECCA_WORKSPACE") or DEFAULT
        if len(parts) == 3:
            return cls(*parts)
        if len(parts) == 2:
            return cls(workspace or env_ws, parts[0], parts[1])
        if len(parts) == 1:
            return cls(workspace or env_ws, project or DEFAULT, parts[0])
        raise PeccaError(f"invalid call path {text!r}", "use workspace/project/call")

    @property
    def key(self) -> str:
        return f"pecca/{self.workspace}/{self.project}/{self.call}"

    def __str__(self) -> str:
        return f"{self.workspace}/{self.project}/{self.call}"
