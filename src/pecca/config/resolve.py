"""Config helpers: deep merge, ``extends`` resolution, ``${VAR}`` substitution."""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

import yaml

from pecca.connectors.base import Secrets
from pecca.core.errors import ConfigError

_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def profiles_dir() -> Path:
    here = Path(__file__).resolve()
    packaged = here.parents[1] / "profiles"
    if packaged.is_dir():
        return packaged
    return here.parents[3] / "profiles"  # repo checkout: <root>/profiles


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_profile(name_or_path: str, base_dir: Path | None = None) -> dict[str, Any]:
    candidates = [profiles_dir() / f"{name_or_path}.yaml"]
    p = Path(name_or_path)
    if base_dir and not p.is_absolute():
        p = base_dir / p
    candidates.append(p)
    for c in candidates:
        if c.is_file():
            data = yaml.safe_load(c.read_text()) or {}
            gov = data.get("governance", data)
            if not isinstance(gov, dict):
                raise ConfigError(f"profile {name_or_path!r} is not a mapping")
            return gov
    raise ConfigError(
        f"unknown governance profile {name_or_path!r}",
        f"built-ins: {', '.join(sorted(x.stem for x in profiles_dir().glob('*.yaml')))}",
    )


def resolve_extends(gov: dict[str, Any], base_dir: Path | None = None) -> dict[str, Any]:
    gov = copy.deepcopy(gov)
    ext = gov.pop("extends", None)
    if ext is None:
        return gov
    base = resolve_extends(load_profile(str(ext), base_dir), base_dir)
    return deep_merge(base, gov)


def find_vars(obj: Any) -> set[str]:
    if isinstance(obj, str):
        return set(_VAR.findall(obj))
    if isinstance(obj, dict):
        return set().union(*(find_vars(v) for v in obj.values())) if obj else set()
    if isinstance(obj, list):
        return set().union(*(find_vars(v) for v in obj)) if obj else set()
    return set()


def substitute(obj: Any, secrets: Secrets) -> Any:
    """Replace ``${VAR}`` with values from the Secrets connector (raises if unresolved)."""
    if isinstance(obj, str):
        return _VAR.sub(lambda m: secrets.get(m.group(1)), obj)
    if isinstance(obj, dict):
        return {k: substitute(v, secrets) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute(v, secrets) for v in obj]
    return obj
