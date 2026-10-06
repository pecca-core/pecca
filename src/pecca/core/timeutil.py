"""Time helpers: durations (``7d``, ``2w``, ``3m``, ``1y``) and ``since`` parsing."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from pecca.core.errors import PeccaError

_DUR = re.compile(r"^(\d+)(d|w|m|y)$")
_UNIT_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


def now() -> datetime:
    return datetime.now(UTC)


def parse_duration(text: str) -> timedelta:
    m = _DUR.match(str(text).strip())
    if not m:
        raise PeccaError(f"invalid duration {text!r}", "use <n>d, <n>w, <n>m or <n>y, e.g. 14d")
    return timedelta(days=int(m.group(1)) * _UNIT_DAYS[m.group(2)])


def parse_since(since: str | datetime | None) -> datetime | None:
    if since is None:
        return None
    if isinstance(since, datetime):
        return since if since.tzinfo else since.replace(tzinfo=UTC)
    if _DUR.match(since.strip()):
        return now() - parse_duration(since)
    try:
        dt = datetime.fromisoformat(since)
    except ValueError as e:
        raise PeccaError(f"invalid since {since!r}", "use e.g. 14d or 2026-09-01") from e
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def iso(dt: datetime | None = None) -> str:
    return (dt or now()).isoformat()


def from_iso(text: str) -> datetime:
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
