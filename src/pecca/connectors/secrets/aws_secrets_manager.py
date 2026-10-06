from __future__ import annotations

import json
from typing import Any

from pecca.connectors.base import Secrets, register
from pecca.core.errors import ConnectorError


@register("secrets", "aws-secrets-manager")
class AwsSecretsManager(Secrets):
    """``get(NAME)`` reads secret id ``<prefix>NAME`` (a plain string, or JSON with key ``NAME``)."""

    def __init__(self, region: str | None = None, prefix: str = "", **_: Any) -> None:
        self.region, self.prefix = region, prefix

    def get(self, name: str) -> str:
        try:
            import boto3
        except ImportError as e:
            raise ConnectorError("boto3 is not installed", "pip install 'pecca[aws]'") from e
        client = boto3.client("secretsmanager", region_name=self.region)
        try:
            value = client.get_secret_value(SecretId=f"{self.prefix}{name}")["SecretString"]
        except Exception as e:  # noqa: BLE001
            raise ConnectorError(f"secret {name!r} not available from AWS Secrets Manager: {e}") from e
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict) and name in parsed:
                return str(parsed[name])
        except ValueError:
            pass
        return str(value)
