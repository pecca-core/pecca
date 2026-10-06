"""Project: datasource, labels, governance, integrations and per-call policy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pecca import connectors
from pecca.config.resolve import resolve_extends, substitute
from pecca.connectors.base import DataSource, DocsPublisher, Notifier, Ticketer

if TYPE_CHECKING:
    from pecca.core.workspace import Workspace


class Project:
    def __init__(self, name: str, workspace: Workspace, config: dict[str, Any] | None = None):
        self.name = name
        self.workspace = workspace
        self.config: dict[str, Any] = config or {}

    @property
    def governance(self) -> dict[str, Any]:
        gov = self.config.get("governance")
        return gov if gov is not None else resolve_extends({"extends": "none"})

    def policy(self, call: str) -> dict[str, Any]:
        return dict(((self.config.get("calls") or {}).get(call) or {}).get("policy") or {})

    def _build(self, interface: str, cfg: dict[str, Any] | None) -> Any:
        if not cfg:
            return None
        return connectors.create(interface, substitute(cfg, self.workspace.secrets))

    def datasource(self) -> DataSource | None:
        return self._build("datasource", self.config.get("datasource"))  # type: ignore[no-any-return]

    def notifier(self) -> Notifier | None:
        return self._build("notifier", (self.config.get("integrations") or {}).get("notifier"))  # type: ignore[no-any-return]

    def ticketer(self) -> Ticketer | None:
        return self._build("ticketer", (self.config.get("integrations") or {}).get("ticketer"))  # type: ignore[no-any-return]

    def docs_publisher(self) -> DocsPublisher | None:
        return self._build("docs_publisher", (self.config.get("integrations") or {}).get("docs"))  # type: ignore[no-any-return]
