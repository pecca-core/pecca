"""Jinja2 rendering of shipped and user-overridden templates."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import jinja2


def _fmt(x: Any, digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}" if isinstance(x, (int, float)) else str(x)


def _pct(x: Any, digits: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{digits}f}%"


def _env() -> jinja2.Environment:
    loaders: list[jinja2.BaseLoader] = []
    user = Path(os.environ.get("PECCA_TEMPLATES", "templates"))
    if user.is_dir():
        loaders.append(jinja2.FileSystemLoader(str(user)))
    loaders.append(jinja2.FileSystemLoader(str(Path(__file__).parent / "templates")))
    env = jinja2.Environment(
        loader=jinja2.ChoiceLoader(loaders),
        autoescape=False,
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["fmt"] = _fmt
    env.filters["pct"] = _pct
    return env


def render(name: str, **ctx: Any) -> str:
    from pecca.core.timeutil import iso

    ctx.setdefault("now", iso())
    return _env().get_template(name).render(**ctx)
