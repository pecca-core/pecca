"""The eight connector interfaces plus the connector registry."""

from __future__ import annotations

import importlib
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import pandas as pd

from pecca.core.errors import ConnectorError

INTERFACES = (
    "datasource",
    "registry",
    "notifier",
    "ticketer",
    "scheduler",
    "serving",
    "secrets",
    "docs_publisher",
    "identity",
)


class DataSource(ABC):
    """Read historical rows into the canonical schema."""

    @abstractmethod
    def read(
        self, call: str | None = None, since: str | None = None, limit: int | None = None
    ) -> pd.DataFrame: ...

    def describe(self) -> dict[str, Any]:
        return {"type": type(self).__name__}


class Registry(ABC):
    """Persist models, versions, call state and logs."""

    @abstractmethod
    def save_model(
        self, path_key: str, version: str, artefacts_dir: str, metadata: dict[str, Any]
    ) -> str: ...
    @abstractmethod
    def load_model(self, path_key: str, version: str) -> str: ...
    @abstractmethod
    def list_versions(self, path_key: str) -> list[dict[str, Any]]: ...
    @abstractmethod
    def get_state(self, path_key: str) -> dict[str, Any]: ...
    @abstractmethod
    def set_state(self, path_key: str, state: dict[str, Any]) -> None: ...
    @abstractmethod
    def append_logs(self, path_key: str, rows: list[dict[str, Any]]) -> None: ...
    @abstractmethod
    def read_logs(self, path_key: str, since: str) -> pd.DataFrame: ...

    # Optional helpers with sensible defaults.
    def list_calls(self, prefix: str) -> list[str]:
        """Call names stored under ``pecca/<workspace>/<project>`` (best effort)."""
        return []

    def audit_dir(self, path_key: str, version: str) -> str:
        raise ConnectorError(f"{type(self).__name__} has no local audit directory")

    def root_dir(self) -> str | None:
        return None


class Notifier(ABC):
    @abstractmethod
    def send(self, event: str, payload: dict[str, Any], rendered: str) -> None: ...


class Ticketer(ABC):
    @abstractmethod
    def create(self, title: str, body: str, meta: dict[str, Any]) -> str: ...
    @abstractmethod
    def get_status(self, ticket_id: str) -> str: ...
    @abstractmethod
    def get_approvers(self, ticket_id: str) -> list[dict[str, Any]]: ...
    @abstractmethod
    def comment(self, ticket_id: str, body: str) -> None: ...
    @abstractmethod
    def close(self, ticket_id: str) -> None: ...


class Scheduler(ABC):
    @abstractmethod
    def register_job(self, name: str, every: str, command: list[str]) -> None: ...
    @abstractmethod
    def list_jobs(self) -> list[dict[str, Any]]: ...


class ServingTarget(ABC):
    @abstractmethod
    def deploy(self, path_key: str, version: str) -> str: ...
    @abstractmethod
    def endpoint(self, path_key: str) -> str | None: ...


class Secrets(ABC):
    @abstractmethod
    def get(self, name: str) -> str: ...


class DocsPublisher(ABC):
    @abstractmethod
    def publish(self, title: str, markdown: str, meta: dict[str, Any]) -> str: ...


class Identity(ABC):
    @abstractmethod
    def current_principal(self) -> dict[str, Any]: ...


# --- registry of implementations -------------------------------------------------------------

CONNECTORS: dict[tuple[str, str], Any] = {}

# Built-in implementations, imported lazily so optional dependencies are not required up front.
_BUILTIN: dict[tuple[str, str], str] = {
    ("datasource", "csv"): "pecca.connectors.datasource.csv",
    ("datasource", "parquet"): "pecca.connectors.datasource.parquet",
    ("datasource", "postgres"): "pecca.connectors.datasource.postgres",
    ("datasource", "databricks"): "pecca.connectors.datasource.databricks",
    ("datasource", "snowflake"): "pecca.connectors.datasource.snowflake",
    ("datasource", "bigquery"): "pecca.connectors.datasource.bigquery",
    ("datasource", "otel-traces"): "pecca.connectors.datasource.otel_traces",
    ("datasource", "litellm"): "pecca.connectors.datasource.litellm_logs",
    ("datasource", "databricks-ai-gateway"): "pecca.connectors.datasource.databricks_ai_gateway",
    ("datasource", "mcp"): "pecca.connectors.datasource.mcp",
    ("registry", "local"): "pecca.connectors.registry.local",
    ("registry", "mlflow"): "pecca.connectors.registry.mlflow",
    ("registry", "wandb"): "pecca.connectors.registry.wandb",
    ("notifier", "slack"): "pecca.connectors.notifier.slack",
    ("notifier", "teams"): "pecca.connectors.notifier.teams",
    ("notifier", "webhook"): "pecca.connectors.notifier.webhook",
    ("notifier", "mcp"): "pecca.connectors.notifier.mcp",
    ("ticketer", "jira"): "pecca.connectors.ticketer.jira",
    ("ticketer", "github"): "pecca.connectors.ticketer.github_issues",
    ("ticketer", "github_issues"): "pecca.connectors.ticketer.github_issues",
    ("ticketer", "manual"): "pecca.connectors.ticketer.manual",
    ("ticketer", "mcp"): "pecca.connectors.ticketer.mcp",
    ("scheduler", "cron"): "pecca.connectors.scheduler.cron",
    ("scheduler", "airflow"): "pecca.connectors.scheduler.airflow",
    ("scheduler", "databricks_workflows"): "pecca.connectors.scheduler.databricks_workflows",
    ("serving", "onnx_local"): "pecca.connectors.serving.onnx_local",
    ("serving", "docker_export"): "pecca.connectors.serving.docker_export",
    ("serving", "databricks_serving"): "pecca.connectors.serving.databricks_serving",
    ("secrets", "env"): "pecca.connectors.secrets.env",
    ("secrets", "vault"): "pecca.connectors.secrets.vault",
    ("secrets", "aws-secrets-manager"): "pecca.connectors.secrets.aws_secrets_manager",
    ("docs_publisher", "markdown"): "pecca.connectors.docs_publisher.markdown",
    ("docs_publisher", "confluence"): "pecca.connectors.docs_publisher.confluence",
    ("identity", "oidc"): "pecca.connectors.identity.oidc",
    ("identity", "local"): "pecca.connectors.identity.oidc",
}


def register(interface: str, type: str) -> Callable[[Any], Any]:  # noqa: A002
    """Class decorator: ``@pecca.connectors.register(interface="ticketer", type="servicenow")``."""
    if interface not in INTERFACES:
        raise ConnectorError(f"unknown interface {interface!r}", f"use one of {INTERFACES}")

    def deco(cls: Any) -> Any:
        CONNECTORS[(interface, type)] = cls
        return cls

    return deco


def get(interface: str, type: str) -> Any:  # noqa: A002
    key = (interface, type)
    if key not in CONNECTORS and key in _BUILTIN:
        importlib.import_module(_BUILTIN[key])
    if key not in CONNECTORS:
        known = sorted(t for (i, t) in {*CONNECTORS, *_BUILTIN} if i == interface)
        raise ConnectorError(
            f"no {interface} connector of type {type!r}", f"available: {', '.join(known)}"
        )
    return CONNECTORS[key]


def create(interface: str, config: dict[str, Any]) -> Any:
    cfg = dict(config)
    type_name = cfg.pop("type", None)
    if cfg.get("transport") == "mcp":  # e.g. ticketer: {type: jira, transport: mcp}
        cfg.pop("transport")
        type_name = "mcp"
    cfg.pop("transport", None)
    if not type_name:
        raise ConnectorError(f"{interface} config is missing 'type'")
    return get(interface, type_name)(**cfg)


def available() -> list[dict[str, str]]:
    keys = sorted({*CONNECTORS, *_BUILTIN})
    return [
        {
            "interface": i,
            "type": t,
            "module": (CONNECTORS[(i, t)].__module__ if (i, t) in CONNECTORS else _BUILTIN[(i, t)]),
        }
        for i, t in keys
    ]
