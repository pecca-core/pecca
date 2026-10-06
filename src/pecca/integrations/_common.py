"""Shared helpers for agent-framework shims."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

from pecca.api import as_tool
from pecca.core.errors import PeccaError


def import_framework(module: str, pip_name: str) -> Any:
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise PeccaError(f"install {pip_name}", f"pip install {pip_name}") from e


def base_tool(
    call: str, project: Any, workspace: Any, description: str | None
) -> Callable[[str], dict[str, Any]]:
    return as_tool(call, project=project, workspace=workspace, description=description)
