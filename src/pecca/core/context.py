"""Process-wide workspace cache: ``pecca.replace(...)`` works with implicit defaults."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from pecca.config import loader
from pecca.core.call import Call
from pecca.core.paths import DEFAULT, CallPath
from pecca.core.project import Project
from pecca.core.workspace import Workspace

_cache: dict[tuple[str, str], Workspace] = {}


def reset() -> None:
    _cache.clear()


def home() -> Path:
    return Path(os.environ.get("PECCA_HOME") or ".pecca").resolve()


def _load_config() -> dict[str, Any]:
    resolved = home() / "config.resolved.yaml"
    if resolved.is_file():
        return yaml.safe_load(resolved.read_text()) or {}
    local = Path("pecca.yaml")
    if local.is_file():
        return loader.resolve(loader.load_yaml(local), local.resolve().parent)
    return {}


def get_workspace(ws: str | Workspace | None = None) -> Workspace:
    if isinstance(ws, Workspace):
        return ws
    name = ws or os.environ.get("PECCA_WORKSPACE") or DEFAULT
    key = (name, str(home()))
    if key not in _cache:
        cfg = _load_config()
        _cache[key] = Workspace(name, cfg, home())
    return _cache[key]


def get_project(ws: str | Workspace | None = None, project: str | Project | None = None) -> Project:
    if isinstance(project, Project):
        return project
    return get_workspace(ws).project(project or DEFAULT)


def get_call(
    call: str, workspace: str | Workspace | None = None, project: str | Project | None = None
) -> Call:
    ws_name = workspace.name if isinstance(workspace, Workspace) else workspace
    pr_name = project.name if isinstance(project, Project) else project
    path = CallPath.parse(call, ws_name, pr_name)
    ws = get_workspace(workspace if isinstance(workspace, Workspace) else path.workspace)
    return Call(path, ws, ws.project(path.project))
