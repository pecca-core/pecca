from __future__ import annotations

import os

from pecca.connectors.base import Secrets, register
from pecca.core.errors import ConnectorError


@register("secrets", "env")
class EnvSecrets(Secrets):
    def __init__(self) -> None:
        pass

    def get(self, name: str) -> str:
        try:
            return os.environ[name]
        except KeyError as e:
            raise ConnectorError(
                f"secret {name!r} is not set", f"export {name}=... or add it to .env"
            ) from e
