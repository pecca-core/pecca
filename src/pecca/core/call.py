"""Call: handle onto one replaced LLM function (state, versions, notifications)."""

from __future__ import annotations

from typing import Any

from pecca.core.errors import ModeError, NotFoundError
from pecca.core.models import CallState, ModelVersion
from pecca.core.paths import CallPath
from pecca.core.project import Project
from pecca.core.timeutil import iso
from pecca.core.workspace import Workspace

MODES = ("off", "record", "shadow", "live")
ALLOWED = {
    ("off", "record"),
    ("record", "off"),
    ("record", "shadow"),
    ("shadow", "live"),
    ("live", "shadow"),
    ("shadow", "off"),
    ("live", "off"),
    ("shadow", "record"),
}


def check_transition(src: str, dst: str) -> None:
    if dst not in MODES:
        raise ModeError(f"unknown mode {dst!r}", f"use one of {MODES}")
    if src == dst:
        return
    if src == "record" and dst == "live":
        raise ModeError("record->live is forbidden", "promote to shadow first, then live")
    if dst != "off" and (src, dst) not in ALLOWED:
        raise ModeError(f"transition {src}->{dst} is not allowed")


class Call:
    def __init__(self, path: CallPath, workspace: Workspace, project: Project) -> None:
        self.path = path
        self.workspace = workspace
        self.project = project

    @property
    def name(self) -> str:
        return self.path.call

    @property
    def key(self) -> str:
        return self.path.key

    @property
    def registry(self) -> Any:
        return self.workspace.registry

    # state ----------------------------------------------------------------------------------
    def state(self) -> CallState:
        return CallState.from_dict(self.registry.get_state(self.key))

    def save_state(self, state: CallState) -> None:
        self.registry.set_state(self.key, state.to_dict())

    def has_state(self) -> bool:
        return bool(self.registry.get_state(self.key))

    # versions -------------------------------------------------------------------------------
    def versions(self) -> list[ModelVersion]:
        return [ModelVersion.from_dict(m) for m in self.registry.list_versions(self.key)]

    def version(self, v: str | None = None) -> ModelVersion:
        vs = self.versions()
        if not vs:
            raise NotFoundError(f"no trained model for {self.path}", f"run `pecca train {self.path}`")
        if v is None:
            cur = self.state().current_version
            v = cur or vs[-1].version
        for m in vs:
            if m.version == v:
                return m
        raise NotFoundError(f"version {v} not found for {self.path}")

    def next_version(self) -> str:
        return f"v{len(self.versions()) + 1}"

    def model_dir(self, v: str) -> str:
        return str(self.registry.load_model(self.key, v))

    # notifications --------------------------------------------------------------------------
    def notify(self, event: str, payload: dict[str, Any] | None = None) -> None:
        """Best-effort notification; never raises."""
        try:
            notifier = self.project.notifier()
            if notifier is None:
                return
            ev_cfg = (self.project.config.get("integrations") or {}).get("notifier", {})
            if "events" in ev_cfg and event not in ev_cfg["events"]:
                return
            from pecca.templates_util import render

            body = {"call": str(self.path), "event": event, **(payload or {})}
            notifier.send(event, body, render("slack_event.md.j2", event=event, **body))
        except Exception:  # noqa: BLE001
            pass

    def log_event(self, state: CallState, kind: str, **data: Any) -> None:
        state.history.append({"ts": iso(), "kind": kind, **data})
