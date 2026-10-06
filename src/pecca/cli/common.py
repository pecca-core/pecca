"""Shared CLI helpers."""

from __future__ import annotations

import functools
import sys
from collections.abc import Callable
from typing import Any

import typer
from rich.console import Console

from pecca.core.errors import PeccaError

console = Console()
err_console = Console(stderr=True)


def handle(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Print ``error: <msg>`` / ``hint: <hint>`` and exit 1 on ``PeccaError``."""

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except PeccaError as e:
            err_console.print(f"error: {e.message}", highlight=False, markup=False)
            if e.hint:
                err_console.print(f"hint: {e.hint}", highlight=False, markup=False)
            raise typer.Exit(1) from None

    return wrapper


def die(msg: str, hint: str = "") -> None:
    err_console.print(f"error: {msg}", markup=False)
    if hint:
        err_console.print(f"hint: {hint}", markup=False)
    sys.exit(1)
