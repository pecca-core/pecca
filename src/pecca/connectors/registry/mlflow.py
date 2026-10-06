"""MLflow / Unity Catalog registry.

URIs: ``mlflow://databricks-uc/<catalog>.<schema>`` (Databricks tracking + UC registry),
``mlflow://sqlite/<path to .db>`` (local SQLite backend, artefacts beside it),
``mlflow://http(s)/<host[:port]>`` (tracking server).
Each trained version is an MLflow run (params, metrics, artefacts) plus a ``pyfunc`` model; call state is
the ``state.json`` artefact of one dedicated "state" run per call; decision logs are small JSONL artefacts.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from pecca.connectors.base import Registry, register
from pecca.core.errors import ConnectorError, NotFoundError
from pecca.core.timeutil import parse_since

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")


def _mlflow() -> Any:
    try:
        import mlflow
    except ImportError as e:
        raise ConnectorError("mlflow is not installed", "pip install 'pecca[mlflow]' (or 'pecca[databricks]')") from e
    return mlflow


def parse_uri(uri: str) -> dict[str, str]:
    rest = uri.removeprefix("mlflow://")
    if rest.startswith("databricks-uc/"):
        return {"tracking": "databricks", "registry": "databricks-uc", "uc": rest.split("/", 1)[1]}
    if rest.startswith("sqlite/"):
        db = Path(rest.split("/", 1)[1]).resolve()
        return {"tracking": f"sqlite:///{db}", "registry": "", "uc": "", "artifacts": str(db.parent / "artifacts")}
    if rest.startswith(("http/", "https/")):
        scheme, host = rest.split("/", 1)
        return {"tracking": f"{scheme}://{host}", "registry": "", "uc": ""}
    raise ConnectorError(f"unsupported mlflow uri {uri!r}", "use mlflow://databricks-uc/<catalog>.<schema>, mlflow://sqlite/<path>.db or mlflow://http(s)/<host>")


@register("registry", "mlflow")
class MlflowRegistry(Registry):
    def __init__(self, uri: str = "mlflow://sqlite/./mlflow.db", home: str | os.PathLike[str] | None = None, **_: Any) -> None:
        self.cfg = parse_uri(uri)
        self.home = Path(home or os.environ.get("PECCA_HOME") or ".pecca").resolve()
        self._client: Any = None
        self._exp: dict[str, str] = {}

    # -- plumbing ---------------------------------------------------------------------------
    @property
    def client(self) -> Any:
        if self._client is None:
            mlflow = _mlflow()
            mlflow.set_tracking_uri(self.cfg["tracking"])
            if self.cfg["registry"]:
                mlflow.set_registry_uri(self.cfg["registry"])
            self._client = mlflow.MlflowClient()
        return self._client

    def _exp_name(self, path_key: str) -> str:
        rel = path_key.removeprefix("pecca/")
        return f"/Shared/pecca/{rel}" if self.cfg["tracking"] == "databricks" else f"pecca/{rel}"

    def _exp_id(self, path_key: str) -> str:
        name = self._exp_name(path_key)
        if name not in self._exp:
            exp = self.client.get_experiment_by_name(name)
            art = self.cfg.get("artifacts")
            self._exp[name] = exp.experiment_id if exp else self.client.create_experiment(
                name, artifact_location=f"{art}/{name.replace('/', '_')}" if art else None)
        return self._exp[name]

    def _runs(self, path_key: str, kind: str) -> list[Any]:
        return list(self.client.search_runs([self._exp_id(path_key)], filter_string=f"tags.`pecca.kind` = '{kind}'",
                                            order_by=["attributes.start_time ASC"], max_results=5000))

    def _uc_model_name(self, path_key: str) -> str:
        return f"{self.cfg['uc']}.{path_key.removeprefix('pecca/').replace('/', '_')}"

    # -- models -----------------------------------------------------------------------------
    def save_model(self, path_key: str, version: str, artefacts_dir: str, metadata: dict[str, Any]) -> str:
        mlflow = _mlflow()
        c = self.client
        run = c.create_run(self._exp_id(path_key), run_name=version,
                           tags={"pecca.kind": "version", "pecca.version": version, "pecca.path": path_key})
        rid = run.info.run_id
        for k in ("candidate", "format", "task_type", "metric_name", "calibration_kind", "calibration_basis"):
            if metadata.get(k) is not None:
                c.log_param(rid, k, metadata[k])
        for k in ("metric", "metric_std", "llm_metric", "threshold", "expected_fallback_rate", "latency_ms", "ece"):
            if isinstance(metadata.get(k), (int, float)):
                c.log_metric(rid, k, float(metadata[k]))
        c.log_artifacts(rid, artefacts_dir, "model_artefacts")
        c.log_dict(rid, metadata, "metadata.json")
        try:  # a pyfunc wrapper so the version can be served by MLflow / Databricks Model Serving
            from pecca.connectors.registry._pyfunc import PeccaPyfunc

            kwargs: dict[str, Any] = {"registered_model_name": self._uc_model_name(path_key)} if self.cfg["uc"] else {}
            with mlflow.start_run(run_id=rid):
                mlflow.pyfunc.log_model(name="pyfunc", python_model=PeccaPyfunc(),
                                        artifacts={"pecca_model": artefacts_dir}, pip_requirements=["pecca"], **kwargs)
        except Exception as e:  # noqa: BLE001 - registry persistence must not depend on pyfunc packaging
            c.set_tag(rid, "pecca.pyfunc_error", str(e)[:250])
        c.set_terminated(rid)
        return f"runs:/{rid}/model_artefacts"

    def _version_run(self, path_key: str, version: str) -> Any:
        for r in self._runs(path_key, "version"):
            if r.data.tags.get("pecca.version") == version:
                return r
        raise NotFoundError(f"model {path_key}@{version} not found", "run `pecca train`")

    def load_model(self, path_key: str, version: str) -> str:
        run = self._version_run(path_key, version)
        dst = self.home / "cache" / "models" / path_key.removeprefix("pecca/") / version
        if (dst / "config.json").exists():
            return str(dst)
        dst.mkdir(parents=True, exist_ok=True)
        local = _mlflow().artifacts.download_artifacts(run_id=run.info.run_id, artifact_path="model_artefacts", dst_path=str(dst.parent / f".{version}.dl"))
        import shutil

        shutil.copytree(local, dst, dirs_exist_ok=True)
        return str(dst)

    def list_versions(self, path_key: str) -> list[dict[str, Any]]:
        out = [self.client.download_artifacts(r.info.run_id, "metadata.json") for r in self._runs(path_key, "version")]
        metas = [json.loads(Path(p).read_text()) for p in out]
        return sorted(metas, key=lambda m: int(str(m["version"]).lstrip("v")))

    # -- state & logs -----------------------------------------------------------------------
    def _state_run(self, path_key: str, create: bool) -> str | None:
        runs = self._runs(path_key, "state")
        if runs:
            return str(runs[-1].info.run_id)
        if not create:
            return None
        return str(self.client.create_run(self._exp_id(path_key), run_name="state", tags={"pecca.kind": "state"}).info.run_id)

    def get_state(self, path_key: str) -> dict[str, Any]:
        rid = self._state_run(path_key, create=False)
        if rid is None:
            return {}
        try:
            return json.loads(Path(self.client.download_artifacts(rid, "state.json")).read_text())  # type: ignore[no-any-return]
        except Exception:  # noqa: BLE001
            return {}

    def set_state(self, path_key: str, state: dict[str, Any]) -> None:
        rid = self._state_run(path_key, create=True)
        assert rid is not None
        self.client.log_dict(rid, state, "state.json")

    def append_logs(self, path_key: str, rows: list[dict[str, Any]]) -> None:
        rid = self._state_run(path_key, create=True)
        assert rid is not None
        by_day: dict[str, list[str]] = {}
        for r in rows:
            ts = str(r.get("ts") or datetime.now(UTC).isoformat())
            by_day.setdefault(ts[:10], []).append(json.dumps(r, default=str))
        for day, lines in by_day.items():
            self.client.log_text(rid, "\n".join(lines) + "\n", f"logs/{day}/{uuid.uuid4().hex}.jsonl")

    def read_logs(self, path_key: str, since: str) -> pd.DataFrame:
        rid = self._state_run(path_key, create=False)
        cutoff = parse_since(since)
        rows: list[dict[str, Any]] = []
        if rid is not None:
            for day in self.client.list_artifacts(rid, "logs"):
                if cutoff and day.path.split("/")[-1] < cutoff.date().isoformat():
                    continue
                for f in self.client.list_artifacts(rid, day.path):
                    text = Path(self.client.download_artifacts(rid, f.path)).read_text()
                    rows += [json.loads(line) for line in text.splitlines() if line.strip()]
        df = pd.DataFrame(rows)
        if cutoff is not None and not df.empty and "ts" in df:
            df = df[pd.to_datetime(df["ts"], utc=True, format="ISO8601") >= pd.Timestamp(cutoff)].reset_index(drop=True)
        return df

    def list_calls(self, prefix: str) -> list[str]:
        base = self._exp_name(prefix) + "/"
        exps = self.client.search_experiments(filter_string=f"name LIKE '{base}%'")
        return sorted(e.name.removeprefix(base) for e in exps if "/" not in e.name.removeprefix(base))
