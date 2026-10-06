from __future__ import annotations

import os
from typing import Any

from pecca.connectors.base import Secrets, register
from pecca.core.errors import ConnectorError


@register("secrets", "vault")
class VaultSecrets(Secrets):
    """HashiCorp Vault KV v2: ``get(NAME)`` reads key ``NAME`` from the secret at ``path``."""

    def __init__(self, url: str | None = None, token: str | None = None, path: str = "pecca",
                 mount: str = "secret", **_: Any) -> None:
        self.url = url or os.environ.get("VAULT_ADDR", "http://127.0.0.1:8200")
        self.token = token or os.environ.get("VAULT_TOKEN")
        self.path, self.mount = path, mount
        self._data: dict[str, Any] | None = None

    def _client(self) -> Any:
        try:
            import hvac
        except ImportError as e:
            raise ConnectorError("hvac is not installed", "pip install 'pecca[vault]'") from e
        return hvac.Client(url=self.url, token=self.token)

    def get(self, name: str) -> str:
        if self._data is None:
            res = self._client().secrets.kv.v2.read_secret_version(path=self.path, mount_point=self.mount)
            self._data = res["data"]["data"]
        assert self._data is not None
        if name not in self._data:
            raise ConnectorError(f"secret {name!r} not found in vault path {self.path!r}")
        return str(self._data[name])
