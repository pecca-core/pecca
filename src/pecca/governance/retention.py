"""Retention policy: stored and written into the audit pack (v1: no automatic deletion)."""

from __future__ import annotations

from typing import Any

from pecca.core.timeutil import parse_duration


def describe(cfg: dict[str, Any] | None) -> dict[str, Any]:
    cfg = cfg or {}
    out: dict[str, Any] = {"signed": bool(cfg.get("signed", False))}
    for k in ("evidence", "logs"):
        if cfg.get(k):
            out[k] = {"policy": cfg[k], "days": parse_duration(cfg[k]).days}
    if cfg.get("gpg_key"):
        out["gpg_key"] = cfg["gpg_key"]
    return out
