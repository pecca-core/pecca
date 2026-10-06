"""Local filesystem registry (default). Layout: see docs/concepts and spec §7."""

from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pecca.connectors.base import Registry, register
from pecca.core.errors import NotFoundError
from pecca.core.timeutil import parse_since


@register("registry", "local")
class LocalRegistry(Registry):
    def __init__(self, root: str | os.PathLike[str] = ".pecca") -> None:
        self.root = Path(root).resolve()

    def root_dir(self) -> str:
        return str(self.root)

    def _dir(self, path_key: str) -> Path:
        key = path_key[len("pecca/") :] if path_key.startswith("pecca/") else path_key
        return self.root / key

    def save_model(
        self, path_key: str, version: str, artefacts_dir: str, metadata: dict[str, Any]
    ) -> str:
        dest = self._dir(path_key) / "versions" / version
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(artefacts_dir, dest)
        (dest / "metadata.json").write_text(json.dumps(metadata, indent=2, default=str))
        return str(dest)

    def load_model(self, path_key: str, version: str) -> str:
        d = self._dir(path_key) / "versions" / version
        if not d.exists():
            raise NotFoundError(f"model {path_key}@{version} not found", "run `pecca train`")
        return str(d)

    def list_versions(self, path_key: str) -> list[dict[str, Any]]:
        vdir = self._dir(path_key) / "versions"
        if not vdir.exists():
            return []
        out = []
        for d in vdir.iterdir():
            f = d / "metadata.json"
            if f.exists():
                out.append(json.loads(f.read_text()))
        return sorted(out, key=lambda m: int(str(m["version"]).lstrip("v")))

    def get_state(self, path_key: str) -> dict[str, Any]:
        f = self._dir(path_key) / "state.json"
        return json.loads(f.read_text()) if f.exists() else {}

    def set_state(self, path_key: str, state: dict[str, Any]) -> None:
        d = self._dir(path_key)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2, default=str))
        tmp.replace(d / "state.json")

    def append_logs(self, path_key: str, rows: list[dict[str, Any]]) -> None:
        ldir = self._dir(path_key) / "logs"
        ldir.mkdir(parents=True, exist_ok=True)
        by_day: dict[str, list[str]] = {}
        for r in rows:
            ts = str(r.get("ts") or datetime.now(UTC).isoformat())
            by_day.setdefault(ts[:10], []).append(json.dumps(r, default=str))
        for day, lines in by_day.items():
            with (ldir / f"{day}.jsonl").open("a") as fh:
                fh.write("\n".join(lines) + "\n")

    def read_logs(self, path_key: str, since: str) -> pd.DataFrame:
        ldir = self._dir(path_key) / "logs"
        cutoff = parse_since(since)
        rows: list[dict[str, Any]] = []
        if ldir.exists():
            for f in sorted(ldir.glob("*.jsonl")):
                if cutoff and f.stem < cutoff.date().isoformat():
                    continue
                for line in f.read_text().splitlines():
                    if line.strip():
                        rows.append(json.loads(line))
        df = pd.DataFrame(rows)
        if cutoff is not None and not df.empty and "ts" in df:
            ts = pd.to_datetime(df["ts"], utc=True, format="ISO8601")
            df = df[ts >= pd.Timestamp(cutoff)].reset_index(drop=True)
        return df

    def list_calls(self, prefix: str) -> list[str]:
        d = self._dir(prefix)
        if not d.exists():
            return []
        return sorted(
            p.name
            for p in d.iterdir()
            if p.is_dir() and ((p / "state.json").exists() or (p / "versions").exists())
        )

    def audit_dir(self, path_key: str, version: str) -> str:
        d = self._dir(path_key) / "audit" / version
        d.mkdir(parents=True, exist_ok=True)
        return str(d)
