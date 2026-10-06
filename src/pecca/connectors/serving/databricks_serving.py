from __future__ import annotations

from typing import Any

from pecca.connectors.base import ServingTarget, register
from pecca.core.errors import PeccaError


@register("serving", "databricks_serving")
class DatabricksServing(ServingTarget):
    """Create a Databricks Model Serving endpoint for a UC-registered Pecca model (needs the mlflow registry)."""

    def __init__(self, model_name_prefix: str = "", workload_size: str = "Small", **_: Any) -> None:
        self.prefix, self.size = model_name_prefix, workload_size
        self._endpoints: dict[str, str] = {}

    def _client(self) -> Any:
        try:
            from databricks.sdk import WorkspaceClient
        except ImportError as e:
            raise PeccaError("databricks-sdk is not installed", "pip install 'pecca[databricks]'") from e
        return WorkspaceClient()

    def deploy(self, path_key: str, version: str) -> str:
        from databricks.sdk.service.serving import EndpointCoreConfigInput, ServedEntityInput

        name = path_key.replace("pecca/", "").replace("/", "-")
        entity = f"{self.prefix}{path_key.replace('pecca/', '').replace('/', '_')}"
        self._client().serving_endpoints.create(
            name=name,
            config=EndpointCoreConfigInput(served_entities=[ServedEntityInput(
                entity_name=entity, entity_version=version.lstrip("v"),
                workload_size=self.size, scale_to_zero_enabled=True)]))
        self._endpoints[path_key] = name
        return name

    def endpoint(self, path_key: str) -> str | None:
        return self._endpoints.get(path_key)
