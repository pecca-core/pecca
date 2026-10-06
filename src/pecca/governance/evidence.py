"""Evidence = audit-pack sections that must exist for a version."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def audit_dir(call: Any, version: str) -> Path:
    try:
        return Path(call.registry.audit_dir(call.key, version))
    except Exception:  # noqa: BLE001
        d = (
            call.workspace.home
            / call.path.workspace
            / call.path.project
            / call.path.call
            / "audit"
            / version
        )
        d.mkdir(parents=True, exist_ok=True)
        return Path(d)


def missing_evidence(call: Any, version: str, required: list[str]) -> list[str]:
    d = audit_dir(call, version)
    return [s for s in required if not (d / f"{s}.md").exists()]
