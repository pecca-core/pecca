"""``pecca apply``: validate, resolve, store and diff the config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from pecca.config import loader
from pecca.connectors.base import Secrets
from pecca.core import context
from pecca.core.errors import ConfigError
from pecca.governance import validate_gates


def apply(
    path: str | Path = "pecca.yaml", secrets: Secrets | None = None
) -> tuple[str, dict[str, Any]]:
    p = Path(path)
    cfg = loader.load_yaml(p)
    resolved = loader.resolve(cfg, p.resolve().parent)
    for proj in resolved["projects"].values():
        validate_gates(proj["governance"])
    if secrets is None:
        from pecca.core.workspace import Workspace

        secrets = Workspace(resolved["workspace"]["name"], resolved).secrets
    missing = loader.unresolved_vars(resolved, secrets)
    if missing:
        raise ConfigError(
            f"unresolved variables: {', '.join(missing)}",
            "set them in the environment or .env (see .env.example)",
        )
    home = context.home()
    home.mkdir(parents=True, exist_ok=True)
    target = home / "config.resolved.yaml"
    old = yaml.safe_load(target.read_text()) if target.exists() else None
    text = loader.diff(old, resolved)
    target.write_text(loader.dump(resolved))
    context.reset()
    return text, resolved
