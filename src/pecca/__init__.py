"""Pecca: replace repetitive LLM calls with small, auditable models."""

__version__ = "0.1.1"

from pecca import connectors  # noqa: E402
from pecca.api import (  # noqa: E402
    approve,
    as_tool,
    audit_pack,
    connect,
    evaluate,
    load,
    predict,
    profile,
    promote,
    register,
    replace,
    retrain,
    train,
)

__all__ = [
    "__version__",
    "approve",
    "as_tool",
    "audit_pack",
    "connect",
    "connectors",
    "evaluate",
    "load",
    "predict",
    "profile",
    "promote",
    "register",
    "replace",
    "retrain",
    "train",
]
