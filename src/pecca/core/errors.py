"""Pecca exceptions. Every error carries a human-readable ``hint``."""

from __future__ import annotations


class PeccaError(Exception):
    def __init__(self, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class SchemaError(PeccaError):
    pass


class ConfigError(PeccaError):
    pass


class GovernanceError(PeccaError):
    pass


class ModeError(PeccaError):
    pass


class ConnectorError(PeccaError):
    pass


class NotFoundError(PeccaError):
    pass
