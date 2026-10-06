"""Load, validate and resolve ``pecca.yaml``."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import jsonschema
import yaml

from pecca.config.resolve import find_vars, resolve_extends
from pecca.connectors.base import Secrets
from pecca.core.errors import ConfigError, PeccaError

_HERE = Path(__file__).parent


def governance_schema() -> dict[str, Any]:
    return json.loads((_HERE.parent / "governance" / "schema.json").read_text())  # type: ignore[no-any-return]


def config_schema() -> dict[str, Any]:
    schema = json.loads((_HERE / "schema.json").read_text())
    schema.setdefault("$defs", {})["governance"] = governance_schema()
    return schema  # type: ignore[no-any-return]


def load_yaml(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise ConfigError(f"{p} not found", "run `pecca init` to create one")
    data = yaml.safe_load(p.read_text()) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{p} must contain a YAML mapping")
    return data


def validate(cfg: dict[str, Any], schema: dict[str, Any] | None = None) -> None:
    validator = jsonschema.Draft202012Validator(schema or config_schema())
    errors = sorted(validator.iter_errors(cfg), key=lambda e: list(e.absolute_path))
    if errors:
        lines = [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in errors]
        raise ConfigError("invalid pecca.yaml:\n  " + "\n  ".join(lines), "see docs/config")


def validate_governance(gov: dict[str, Any]) -> None:
    validate(gov, governance_schema())


def resolve(cfg: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any]:
    """Validate and resolve ``extends``. ``${VAR}`` placeholders are kept (never written resolved)."""
    validate(cfg)
    out: dict[str, Any] = {
        "version": cfg.get("version", 1),
        "workspace": cfg.get("workspace", {"name": "default"}),
        "projects": {},
    }
    out["workspace"].setdefault("name", "default")
    for pname, proj in (cfg.get("projects") or {}).items():
        proj = dict(proj)
        gov = resolve_extends(proj.get("governance") or {"extends": "none"}, base_dir)
        validate_governance(gov)
        proj["governance"] = gov
        out["projects"][pname] = proj
    return out


def unresolved_vars(cfg: dict[str, Any], secrets: Secrets) -> list[str]:
    missing = []
    for name in sorted(find_vars(cfg)):
        try:
            secrets.get(name)
        except PeccaError:
            missing.append(name)
    return missing


def dump(cfg: dict[str, Any]) -> str:
    return yaml.safe_dump(cfg, sort_keys=False)


def diff(old: dict[str, Any] | None, new: dict[str, Any]) -> str:
    a = dump(old).splitlines() if old else []
    b = dump(new).splitlines()
    return "\n".join(difflib.unified_diff(a, b, "stored", "new", lineterm="", n=2))
