"""Weights & Biases registry (artefacts). URI: ``wandb://<entity>/<project>``."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pecca.connectors.base import Registry, register
from pecca.core.errors import ConnectorError, NotFoundError
from pecca.core.timeutil import parse_since


def _wandb() -> Any:
    try:
        import wandb
    except ImportError as e:
        raise ConnectorError("wandb is not installed", "pip install 'pecca[wandb]'") from e
    return wandb


def _slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", s.removeprefix("pecca/"))


@register("registry", "wandb")
class WandbRegistry(Registry):
    """Models = artefact versions (type ``model``, alias = version id, metadata = ModelVersion).
    State = ``state.json`` in the latest ``state`` artefact. Logs = one ``logs`` artefact version per flush."""

    def __init__(
        self, uri: str = "wandb://", home: str | os.PathLike[str] | None = None, **_: Any
    ) -> None:
        parts = uri.removeprefix("wandb://").strip("/").split("/")
        if len(parts) != 2 or not all(parts):
            raise ConnectorError(f"bad wandb uri {uri!r}", "use wandb://<entity>/<project>")
        self.entity, self.project = parts
        self.home = Path(home or os.environ.get("PECCA_HOME") or ".pecca").resolve()

    def _api(self) -> Any:
        return _wandb().Api()

    def _write(self, job: str, art: Any, aliases: list[str] | None = None) -> None:
        wandb = _wandb()
        run = wandb.init(project=self.project, entity=self.entity, job_type=job, reinit=True)
        try:
            run.log_artifact(art, aliases=aliases or ["latest"])
        finally:
            run.finish()

    def _full(self, name: str, alias: str) -> str:
        return f"{self.entity}/{self.project}/{name}:{alias}"

    def save_model(
        self, path_key: str, version: str, artefacts_dir: str, metadata: dict[str, Any]
    ) -> str:
        wandb = _wandb()
        name = f"{_slug(path_key)}-model"
        art = wandb.Artifact(
            name, type="model", metadata=json.loads(json.dumps(metadata, default=str))
        )
        art.add_dir(artefacts_dir)
        self._write("pecca-train", art, [version, "latest"])
        return self._full(name, version)

    def load_model(self, path_key: str, version: str) -> str:
        dst = self.home / "cache" / "models" / _slug(path_key) / version
        if (dst / "config.json").exists():
            return str(dst)
        try:
            art = self._api().artifact(self._full(f"{_slug(path_key)}-model", version))
        except Exception as e:  # noqa: BLE001
            raise NotFoundError(
                f"model {path_key}@{version} not found in W&B", "run `pecca train`"
            ) from e
        art.download(root=str(dst))
        return str(dst)

    def list_versions(self, path_key: str) -> list[dict[str, Any]]:
        try:
            col = self._api().artifact_collection(
                "model", f"{self.entity}/{self.project}/{_slug(path_key)}-model"
            )
            metas = [dict(a.metadata) for a in col.artifacts()]
        except Exception:  # noqa: BLE001
            return []
        return sorted(
            (m for m in metas if "version" in m), key=lambda m: int(str(m["version"]).lstrip("v"))
        )

    def get_state(self, path_key: str) -> dict[str, Any]:
        try:
            art = self._api().artifact(self._full(f"{_slug(path_key)}-state", "latest"))
            d = art.download(root=tempfile.mkdtemp())
            return json.loads((Path(d) / "state.json").read_text())  # type: ignore[no-any-return]
        except Exception:  # noqa: BLE001
            return {}

    def _file_artifact(self, name: str, kind: str, filename: str, text: str) -> Any:
        art = _wandb().Artifact(name, type=kind)
        d = Path(tempfile.mkdtemp())
        (d / filename).write_text(text)
        art.add_file(str(d / filename), name=filename)
        return art

    def set_state(self, path_key: str, state: dict[str, Any]) -> None:
        self._write(
            "pecca-state",
            self._file_artifact(
                f"{_slug(path_key)}-state", "state", "state.json", json.dumps(state, default=str)
            ),
        )

    def append_logs(self, path_key: str, rows: list[dict[str, Any]]) -> None:
        by_day: dict[str, list[str]] = {}
        for r in rows:
            by_day.setdefault(str(r.get("ts") or datetime.now(UTC).isoformat())[:10], []).append(
                json.dumps(r, default=str)
            )
        for day, lines in by_day.items():
            art = self._file_artifact(
                f"{_slug(path_key)}-logs-{day}",
                "logs",
                f"{uuid.uuid4().hex}.jsonl",
                "\n".join(lines) + "\n",
            )
            self._write("pecca-logs", art)

    def read_logs(self, path_key: str, since: str) -> pd.DataFrame:
        cutoff = parse_since(since)
        rows: list[dict[str, Any]] = []
        try:
            api = self._api()
            for col in api.artifact_type("logs", f"{self.entity}/{self.project}").collections():
                if not col.name.startswith(f"{_slug(path_key)}-logs-"):
                    continue
                if cutoff and col.name.rsplit("-logs-", 1)[1] < cutoff.date().isoformat():
                    continue
                for art in col.artifacts():
                    d = Path(art.download(root=tempfile.mkdtemp()))
                    for f in d.glob("*.jsonl"):
                        rows += [
                            json.loads(line) for line in f.read_text().splitlines() if line.strip()
                        ]
        except Exception:  # noqa: BLE001
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        if cutoff is not None and not df.empty and "ts" in df:
            df = df[
                pd.to_datetime(df["ts"], utc=True, format="ISO8601") >= pd.Timestamp(cutoff)
            ].reset_index(drop=True)
        return df
