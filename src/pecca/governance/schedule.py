"""Due-date computation for retrain / revalidate / drift review."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pecca.core.timeutil import from_iso, parse_duration


def _last(call: Any, key: str) -> datetime | None:
    st = call.state()
    val = getattr(st, key)
    if val:
        return from_iso(val)
    if key in ("last_trained", "last_revalidated"):
        try:
            return from_iso(call.version().trained_at)
        except Exception:  # noqa: BLE001
            return None
    return from_iso(st.since) if st.since else None


def next_dates(call: Any) -> dict[str, datetime]:
    sched = call.project.governance.get("schedule") or {}
    policy = call.project.policy(call.name)
    out: dict[str, datetime] = {}
    if policy.get("train_every") and (t := _last(call, "last_trained")):
        out["retrain"] = t + parse_duration(policy["train_every"])
    if (r := sched.get("revalidate")) and (t := _last(call, "last_revalidated")):
        out["revalidate"] = t + parse_duration(r["every"])
    if (d := sched.get("drift_review")) and (t := _last(call, "last_drift_review")):
        out["drift_review"] = t + parse_duration(d["every"])
    return out


def due_items(call: Any, at: datetime) -> list[str]:
    return [k for k, v in next_dates(call).items() if v <= at]
