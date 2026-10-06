"""Section extras that depend on runtime state (shadow results, approvals, controls)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pecca.governance.retention import describe


def shadow_results(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    return {}


def approvals(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    return {}


def controls_mapping(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    return {}


def environment(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    return {"retention": describe(ctx["governance"].get("retention"))}
