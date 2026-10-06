"""Workspace: registry, secrets, telemetry, scheduler and projects."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pecca import connectors
from pecca.connectors.base import Registry, Scheduler, Secrets
from pecca.core.errors import ConfigError
from pecca.core.project import Project


class Workspace:
    def __init__(
        self,
        name: str = "default",
        config: dict[str, Any] | None = None,
        home: str | os.PathLike[str] | None = None,
    ) -> None:
        self.name = name
        self.config: dict[str, Any] = config or {}
        self.home = Path(home or os.environ.get("PECCA_HOME") or ".pecca").resolve()
        ws_cfg = self.config.get("workspace", {}) if self.config else {}
        self.telemetry: dict[str, Any] = ws_cfg.get("telemetry") or {}
        self._secrets_cfg: dict[str, Any] = ws_cfg.get("secrets") or {"provider": "env"}
        self._registry_uri: str = ws_cfg.get("registry") or "local://"
        self._scheduler_cfg: dict[str, Any] = ws_cfg.get("scheduler") or {"type": "cron"}
        self._registry: Registry | None = None
        self._secrets: Secrets | None = None
        self._projects: dict[str, Project] = {}

    @property
    def secrets(self) -> Secrets:
        if self._secrets is None:
            cfg = dict(self._secrets_cfg)
            self._secrets = connectors.create(
                "secrets", {"type": cfg.pop("provider", "env"), **cfg}
            )
        return self._secrets

    @property
    def registry(self) -> Registry:
        if self._registry is None:
            uri = self._registry_uri
            if uri.startswith("local://"):
                rest = uri[len("local://") :]
                root = Path(rest) if rest and rest != "./.pecca" else self.home
                self._registry = connectors.get("registry", "local")(root=root)
            elif uri.startswith("mlflow://"):
                self._registry = connectors.get("registry", "mlflow")(uri=uri, home=self.home)
            elif uri.startswith("wandb://"):
                self._registry = connectors.get("registry", "wandb")(uri=uri, home=self.home)
            else:
                raise ConfigError(
                    f"unsupported registry {uri!r}", "use local://..., mlflow://... or wandb://..."
                )
        return self._registry

    @registry.setter
    def registry(self, value: Registry) -> None:
        self._registry = value

    @property
    def scheduler(self) -> Scheduler:
        return connectors.create("scheduler", dict(self._scheduler_cfg))  # type: ignore[no-any-return]

    def project(self, name: str = "default") -> Project:
        if name not in self._projects:
            cfg = (self.config.get("projects") or {}).get(name, {})
            self._projects[name] = Project(name, self, cfg)
        return self._projects[name]

    @property
    def projects(self) -> dict[str, Project]:
        names = set((self.config.get("projects") or {}).keys()) | set(self._projects)
        return {n: self.project(n) for n in sorted(names)}
