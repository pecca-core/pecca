import json
import os

import numpy as np
import pytest

os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
mlflow = pytest.importorskip("mlflow")

import pecca
from pecca.connectors.registry.local import LocalRegistry
from pecca.connectors.registry.mlflow import MlflowRegistry, parse_uri
from pecca.core import context
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import generate
from pecca.runtime.predictor import Bundle

KEY = "pecca/default/default/route_rfi"


def _fake_artefacts(tmp_path):
    d = tmp_path / f"art{len(list(tmp_path.glob('art*')))}"
    d.mkdir()
    (d / "config.json").write_text("{}")
    (d / "x.bin").write_bytes(b"1")
    return str(d)


@pytest.mark.parametrize("make", ["local", "mlflow"])
def test_registry_contract(make, tmp_path):
    reg = LocalRegistry(tmp_path / "loc") if make == "local" else MlflowRegistry(f"mlflow://sqlite/{tmp_path}/mlflow.db", home=tmp_path)
    assert reg.get_state(KEY) == {} and reg.list_versions(KEY) == []
    reg.set_state(KEY, {"mode": "shadow"})
    assert reg.get_state(KEY) == {"mode": "shadow"}
    reg.set_state(KEY, {"mode": "live"})
    assert reg.get_state(KEY)["mode"] == "live"
    for v in ("v1", "v2", "v10"):
        reg.save_model(KEY, v, _fake_artefacts(tmp_path), {"version": v, "metric": 0.5})
    assert [m["version"] for m in reg.list_versions(KEY)] == ["v1", "v2", "v10"]
    d = reg.load_model(KEY, "v2")
    assert os.path.exists(os.path.join(d, "x.bin"))
    reg.append_logs(KEY, [{"ts": "2026-10-01T00:00:00+00:00", "a": 1}, {"ts": "2026-10-02T00:00:00+00:00", "a": 2}])
    reg.append_logs(KEY, [{"ts": "2099-01-01T00:00:00+00:00", "a": 3}])
    assert sorted(reg.read_logs(KEY, "2000-01-01")["a"]) == [1, 2, 3]
    assert list(reg.read_logs(KEY, "2026-10-02")["a"]) == [2, 3]
    assert "route_rfi" in reg.list_calls("pecca/default/default")
    with pytest.raises(Exception):
        reg.load_model(KEY, "v99")


def test_parse_uri():
    assert parse_uri("mlflow://databricks-uc/ml.pecca")["uc"] == "ml.pecca"
    assert parse_uri("mlflow://sqlite/x/y.db")["tracking"].startswith("sqlite:///")
    assert parse_uri("mlflow://https/mlflow.example.com")["tracking"] == "https://mlflow.example.com"
    with pytest.raises(Exception):
        parse_uri("mlflow://nonsense")


def test_train_with_mlflow_registry_and_pyfunc(tmp_path, monkeypatch):
    from pecca.core.workspace import Workspace

    ws = Workspace("default", {"workspace": {"registry": f"mlflow://sqlite/{tmp_path}/mlflow.db"}}, tmp_path / ".pecca")
    cols = {"input": {"s": "email_subject", "b": "email_body"}, "llm_output": "llm_rfi",
            "human_label": "human_rfi", "call_name": {"literal": "route_rfi"}}
    ds = Dataset(canonicalize(generate(1500), cols), cols, "{s}\n\n{b}")
    res = pecca.train("route_rfi", ds, workspace=ws)
    assert res.version == "v1"
    p = pecca.predict("route_rfi", [{"s": "lost card", "b": "my card was stolen yesterday"}], workspace=ws)[0]
    assert isinstance(p.label, str)
    c = context.get_call("route_rfi", ws)
    assert c.registry.get_state(c.key)["current_version"] == "v1"
    rid = c.registry._version_run(c.key, "v1").info.run_id  # noqa: SLF001
    assert not c.registry._version_run(c.key, "v1").data.tags.get("pecca.pyfunc_error")  # noqa: SLF001
    model = mlflow.pyfunc.load_model(f"runs:/{rid}/pyfunc")
    import pandas as pd

    out = model.predict(pd.DataFrame({"text": ["lost card\n\nmy card was stolen yesterday"]}))
    assert list(out.columns) == ["label", "confidence", "fallback"]
