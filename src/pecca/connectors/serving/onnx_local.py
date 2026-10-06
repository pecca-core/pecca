from __future__ import annotations

import os
from typing import Any

from pecca.connectors.base import ServingTarget, register
from pecca.connectors.registry.local import LocalRegistry


@register("serving", "onnx_local")
class OnnxLocalServing(ServingTarget):
    """In-process serving (default): verifies the version loads and returns a local reference."""

    def __init__(self, home: str | None = None, **_: Any) -> None:
        self.registry = LocalRegistry(home or os.environ.get("PECCA_HOME") or ".pecca")

    def deploy(self, path_key: str, version: str) -> str:
        return self.registry.load_model(path_key, version)

    def endpoint(self, path_key: str) -> str | None:
        return None
