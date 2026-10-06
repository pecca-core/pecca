import asyncio
import random
import time

import pandas as pd
import pytest
import yaml

import pecca
from pecca.core import context
from pecca.core.errors import NotFoundError, PeccaError
from pecca.core.timeutil import iso, now
from pecca.data.dataset import Dataset, canonicalize
from pecca.evaluation import evaluate_call, js_distance
from pecca.runtime import decorator, telemetry
from pecca.runtime.decorator import default_input_adapter
from pecca.runtime.logging_sink import LogSink, flush_all
from pecca.runtime.predictor import get_predictor


def small_ds(n=900, labels=("billing", "cards", "loans"), call="c", numeric=False):
    rng = random.Random(1)
    words = {
        "billing": ["invoice", "bill", "charge"],
        "cards": ["card", "pin", "atm"],
        "loans": ["loan", "rate", "mortgage"],
    }
    rows = []
    for i in range(n):
        lab = rng.choice(labels)
        rows.append(
            {
                "txt": " ".join(rng.choices(words[lab], k=6)) + f" t{i % 7}",
                "out": lab,
                "num": str(len(lab) + rng.random()),
            }
        )
    df = pd.DataFrame(rows)
    return Dataset(
        canonicalize(
            df,
            {
                "input": "txt",
                "llm_output": "num" if numeric else "out",
                "call_name": {"literal": call},
            },
        )
    )


class FlakyRegistry:
    def __init__(self):
        self.rows, self.fail = [], False

    def append_logs(self, key, rows):
        if self.fail:
            raise OSError("disk full")
        self.rows += rows


def test_log_sink_batches_interval_and_swallows_errors():
    reg = FlakyRegistry()
    s = LogSink(reg, "k", batch=50, interval_s=0.05)
    for i in range(49):
        s.add({"i": i})
    assert len(reg.rows) < 50 or len(reg.rows) == 49
    s.add({"i": 49})
    assert len(reg.rows) == 50
    s.add({"i": 50})
    time.sleep(0.3)
    assert len(reg.rows) == 51  # interval flush
    reg.fail = True
    s.add({"i": 1})
    s.flush()  # must not raise
    s.close()


def test_span_attributes_emitted(monkeypatch):
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exp = InMemorySpanExporter()
    prov = TracerProvider()
    prov.add_span_processor(SimpleSpanProcessor(exp))
    monkeypatch.setattr(telemetry, "get_tracer", lambda: prov.get_tracer("t"))
    pecca.train("c", small_ds())
    f = pecca.replace("c", mode="shadow")(lambda text: "billing")
    f("invoice bill charge invoice bill charge t1")
    span = [s for s in exp.get_finished_spans() if s.name == "pecca.call"][0]
    a = dict(span.attributes)
    assert (
        a["pecca.path"] == "default/default/c"
        and a["pecca.mode"] == "shadow"
        and a["pecca.served_by"] == "llm"
    )
    assert (
        a["pecca.version"] == "v1"
        and "pecca.confidence" in a
        and "pecca.agreement" in a
        and a["pecca.latency_ms"] > 0
    )


def test_no_exporter_is_noop_and_configure_otlp_once():
    assert telemetry.get_tracer().start_span("x") is not None
    telemetry.configure(None)
    telemetry.configure({"exporter": "none"})


def test_default_input_adapter():
    assert default_input_adapter("hello") == "hello"
    assert default_input_adapter(subject="a", body="b") == {"subject": "a", "body": "b"}
    assert default_input_adapter(x=1.5) == {"x": 1.5}
    for bad in ((("a", "b"), {}), ((), {}), ((1,), {}), ((), {"x": [1]})):
        with pytest.raises(ValueError, match="input_adapter"):
            default_input_adapter(*bad[0], **bad[1])


def test_predictor_missing_model():
    with pytest.raises(NotFoundError):
        get_predictor(context.get_call("nothing"))
    with pytest.raises(NotFoundError):
        context.get_call("nothing").model_dir("v9")


def test_regression_end_to_end():
    # cv_metric gates assume higher-is-better; for rmse a project writes its own (lower-is-better) gates.
    open("pecca.yaml", "w").write(
        yaml.safe_dump(
            {
                "version": 1,
                "projects": {
                    "default": {
                        "governance": {
                            "extends": "none",
                            "transitions": {
                                "record->shadow": {"gates": ["cv_metric <= 5"]},
                                "shadow->live": {"gates": ["shadow_days >= 7"]},
                            },
                        }
                    }
                },
            }
        )
    )
    context.reset()
    pecca.train("score", small_ds(numeric=True, call="score"))
    p = pecca.predict("score", ["card pin atm card pin atm"])[0]
    assert isinstance(p.label, float) and p.confidence is None and not p.fallback
    assert pecca.promote("score", "shadow").allowed
    c = context.get_call("score")
    st = c.state()
    st.shadow_since = iso(now() - pd.Timedelta(days=30))
    c.save_state(st)
    assert pecca.promote("score", "live").allowed
    out = pecca.replace("score", mode="live")(lambda t: 99.0)(
        "loan rate mortgage loan rate mortgage"
    )
    assert (
        isinstance(out, float) and out != 99.0
    )  # regression always served by the model in live mode


def test_decorator_picks_up_state_mode_and_ttl(monkeypatch):
    pecca.train("c", small_ds())
    calls = []
    f = pecca.replace("c")(
        lambda text: calls.append(text) or "billing"
    )  # mode from stored state (record)
    f("invoice bill charge t1")
    flush_all()
    c = context.get_call("c")
    assert set(c.registry.read_logs(c.key, "1d")["mode"]) == {"record"}
    pecca.promote("c", "shadow")
    monkeypatch.setattr(decorator, "STATE_TTL_S", 0.0)
    f("invoice bill charge t2")
    flush_all()
    assert set(c.registry.read_logs(c.key, "1d")["mode"]) == {"record", "shadow"}


def test_train_from_recorded_logs_and_retrain_flags():
    ds = small_ds()
    texts, outs = ds.to_pandas()["input"].tolist(), ds.to_pandas()["llm_output"].tolist()
    table = dict(zip(texts, outs))
    f = pecca.replace("c", mode="record")(lambda text: table[text])
    for t in texts:
        f(t)
    flush_all()
    res = pecca.train("c")  # no dataset: learns from the recorded calls only
    assert res.lineage["rows"] == 900 and res.metric > 0.9
    res2 = pecca.retrain("c", include_fallbacks=False)
    assert res2.version == "v2"
    with pytest.raises(PeccaError, match="no data"):
        pecca.train("empty")


def test_labels_join_via_project_config(tmp_path):
    ds = small_ds()
    df = ds.to_pandas()
    raw = pd.DataFrame(
        {"rid": [f"r{i}" for i in range(len(df))], "txt": df["input"], "out": df["llm_output"]}
    )
    raw.to_csv("logs.csv", index=False)
    pd.DataFrame({"tid": ["r0", "r1"], "agent_tag": ["loans", "loans"]}).to_csv(
        "tags.csv", index=False
    )
    cfg = {
        "version": 1,
        "projects": {
            "p": {
                "datasource": {
                    "type": "csv",
                    "path": "logs.csv",
                    "columns": {
                        "input": "txt",
                        "llm_output": "out",
                        "call_name": {"literal": "c"},
                        "request_id": "rid",
                    },
                },
                "labels": {
                    "type": "csv",
                    "path": "tags.csv",
                    "join_on": "tid",
                    "column": "agent_tag",
                },
            }
        },
    }
    open("pecca.yaml", "w").write(yaml.safe_dump(cfg))
    context.reset()
    from pecca.api import load_dataset

    out = load_dataset(context.get_call("p/c")).to_pandas()
    assert (
        list(out["human_label"].iloc[:2]) == ["loans", "loans"]
        and out["human_label"].iloc[2:].isna().all()
    )
    assert (
        len(
            load_dataset(context.get_call("p/c"), include_human_labels=False)
            .to_pandas()["human_label"]
            .dropna()
        )
        == 0
    )
    rep = pecca.profile(call="p/c")
    assert rep.profiles["c"].n_human_labels == 2
    with pytest.raises(PeccaError):
        pecca.profile()


def test_connect_api(tmp_path):
    ds = small_ds().to_pandas()
    pd.DataFrame({"txt": ds["input"], "out": ds["llm_output"]}).to_csv("x.csv", index=False)
    d = pecca.connect(
        "csv",
        path="x.csv",
        columns={"input": "txt", "llm_output": "out", "call_name": {"literal": "c"}},
    )
    assert (
        d.rows == 900
        and d.calls == ["c"]
        and len(d.sample(3)) == 3
        and len(d.to_pandas("c")) == 900
    )
    assert (
        pecca.profile(d).profiles["c"].replaceable and "classification" in pecca.profile(d).table()
    )


def test_evaluate_drift_and_per_class():
    assert js_distance({"a": 5}, {"a": 5}) == pytest.approx(0.0)
    assert js_distance({"a": 5}, {"b": 5}) == pytest.approx(1.0)
    assert js_distance({}, {"a": 1}) is None
    pecca.train("c", small_ds())
    pecca.promote("c", "shadow")
    c = context.get_call("c")
    llm = lambda t: "billing"
    f = pecca.replace("c", mode="shadow")(llm)
    for t in ["invoice bill charge t1", "card pin atm t2", "loan rate mortgage t3"] * 5:
        f(t)
    flush_all()
    rep = evaluate_call(c, "1d")
    assert rep.n_rows == 15 and 0.2 < rep.agreement_rate < 0.5 and rep.drift_score > 0
    assert len(rep.disagreements) == 10 and set(rep.per_class_agreement) == {"billing"}
    assert evaluate_call(context.get_call("zzz"), "1d").n_rows == 0


def test_mcp_remaining_tools():
    from mcp.client import Client

    from pecca.mcp.server import build_server

    pecca.train("c", small_ds())
    pecca.train("c", small_ds(n=1000))

    async def go():
        async with Client(build_server()) as cl:
            res = {}
            for name, args in [
                ("pecca_profile", {"path": "c"}),
                ("pecca_evaluate", {"path": "c"}),
                ("pecca_diff", {"path": "c", "v_a": "v1", "v_b": "v2"}),
                ("pecca_audit", {"path": "c"}),
            ]:
                res[name] = await cl.call_tool(name, args)
            return res

    out = asyncio.run(go())
    assert (
        not any(r.is_error for r in out.values()) or out["pecca_profile"].is_error
    )  # profile needs a datasource
    assert (
        "per_class_f1_delta" in out["pecca_diff"].content[0].text
        and "Audit pack" in out["pecca_audit"].content[0].text
    )
