from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pecca.connectors.base import Scheduler, register
from pecca.core.errors import PeccaError


def cron_expr(every: str) -> str:
    m = re.match(r"^(\d+)(d|w|m|y)$", every)
    if not m:
        raise PeccaError(f"invalid duration {every!r}", "use e.g. 7d, 2w, 1m, 1y")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return f"0 6 */{n} * *" if n > 1 else "0 6 * * *"
    if unit == "w":
        return f"0 6 */{7 * n} * *"
    if unit == "m":
        return f"0 6 1 */{n} *" if n > 1 else "0 6 1 * *"
    return "0 6 1 1 *"  # yearly (every n years is not expressible in cron)


@register("scheduler", "cron")
class CronScheduler(Scheduler):
    """Prints a crontab line per job; ``pecca scheduler run`` is the tick the cron entry calls."""

    def __init__(self, path: str | None = None, **_: Any) -> None:
        self.path = Path(path or Path(os.environ.get("PECCA_HOME") or ".pecca") / "scheduler.json")

    def _load(self) -> list[dict[str, Any]]:
        return json.loads(self.path.read_text()) if self.path.exists() else []  # type: ignore[no-any-return]

    def register_job(self, name: str, every: str, command: list[str]) -> None:
        jobs = [j for j in self._load() if j["name"] != name]
        line = f"{cron_expr(every)} {' '.join(command)}"
        jobs.append({"name": name, "every": every, "command": command, "crontab": line})
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(jobs, indent=2))
        print(f"# pecca job {name}\n{line}")

    def list_jobs(self) -> list[dict[str, Any]]:
        return self._load()
