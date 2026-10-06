from datetime import timedelta

import pytest

import pecca
from pecca.core import context
from pecca.core.errors import ModeError, PeccaError
from pecca.core.timeutil import iso, now
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import generate
from pecca.runtime.logging_sink import flush_all
from pecca.runtime.predictor import clear_cache

COLS = {"input": {"subject": "email_subject", "body": "email_body"}, "llm_output": "llm_rfi",
        "human_label": "human_rfi", "call_name": {"literal": "route_rfi"}}


@pytest.fixture()
def df():
    return generate(1200)


@pytest.fixture()
def ds(df):
    return Dataset(canonicalize(df, COLS), COLS, "{subject}\n\n{body}")


@pytest.fixture()
def trained(ds):
    clear_cache()
    res = pecca.train("route_rfi", ds, target_precision=0.9)
    return res


def llm_for(df):
    table = {f"{r.email_subject}\n\n{r.email_body}": r.llm_rfi for r in df.itertuples()}
    calls = []

    def fn(text):
        calls.append(text)
        return table[text]

    return fn, calls, table


def test_train_result_and_state(trained):
    assert trained.version == "v1" and trained.winner in {"tfidf_linear", "e5_logreg"}
    c = context.get_call("route_rfi")
    assert c.state().current_version == "v1" and c.version().threshold is not None


def test_predict(trained, df):
    r = df.iloc[0]
    p = pecca.predict("route_rfi", [{"subject": r.email_subject, "body": r.email_body}])[0]
    assert isinstance(p.label, str) and 0 <= p.confidence <= 1 and p.version == "v1"


def test_modes_off_record_shadow_live(trained, df):
    fn, calls, table = llm_for(df)
    texts = list(table)[:40]

    off = pecca.replace("route_rfi", mode="off")(fn)
    assert off(texts[0]) == table[texts[0]]
    flush_all()
    assert context.get_call("route_rfi").registry.read_logs("pecca/default/default/route_rfi", "1d").empty

    rec = pecca.replace("route_rfi", mode="record")(fn)
    for t in texts[:5]:
        assert rec(t) == table[t]
    sh = pecca.replace("route_rfi", mode="shadow", input_adapter=lambda t: {"subject": t.split("\n\n")[0], "body": t.split("\n\n", 1)[1]})(fn)
    for t in texts[5:15]:
        assert sh(t) == table[t]  # shadow always returns the LLM answer
    flush_all()
    logs = context.get_call("route_rfi").registry.read_logs("pecca/default/default/route_rfi", "1d")
    assert set(logs["mode"]) == {"record", "shadow"} and logs[logs["mode"] == "shadow"]["agreement"].notna().all()

    before = len(calls)
    live = pecca.replace("route_rfi", mode="live", input_adapter=lambda t: {"subject": t.split("\n\n")[0], "body": t.split("\n\n", 1)[1]})(fn)
    outs = [live(t) for t in texts[15:40]]
    served_by_model = 25 - (len(calls) - before)
    assert served_by_model > 0 and all(isinstance(o, str) for o in outs)
    flush_all()
    logs = context.get_call("route_rfi").registry.read_logs("pecca/default/default/route_rfi", "1d")
    assert set(logs[logs["mode"] == "live"]["served_by"]) <= {"model", "fallback"}


def test_exception_isolation(trained, df, monkeypatch):
    fn, _, table = llm_for(df)
    t = list(table)[0]
    from pecca.runtime import decorator

    def boom(*a, **k):
        raise RuntimeError("pecca internal failure")

    monkeypatch.setattr(decorator, "get_predictor", boom)
    monkeypatch.setattr(decorator, "get_sink", boom)
    for mode in ("record", "shadow", "live"):
        wrapped = pecca.replace("route_rfi", mode=mode, input_adapter=lambda x: x)(fn)
        assert wrapped(t) == table[t]  # LLM answer returned despite Pecca failing


def test_user_exceptions_propagate():
    @pecca.replace("x", mode="record")
    def f(text):
        raise ValueError("llm down")

    with pytest.raises(ValueError):
        f("hi")


def test_bad_adapter_does_not_raise():
    @pecca.replace("x", mode="record")
    def f(a, b):
        return "ok"

    assert f(1, 2) == "ok"


def test_async_function(trained, df):
    import asyncio

    _, _, table = llm_for(df)
    t = list(table)[0]

    @pecca.replace("route_rfi", mode="record", input_adapter=lambda x: x)
    async def f(x):
        return table[x]

    assert asyncio.run(f(t)) == table[t]


def test_promote_gates_and_transitions(trained, df):
    with pytest.raises(ModeError):
        pecca.promote("route_rfi", "live")  # record->live forbidden
    dec = pecca.promote("route_rfi", "shadow")
    assert dec.allowed
    dec = pecca.promote("route_rfi", "live")
    assert not dec.allowed and any("shadow_days" in g for g in dec.failing_gates)
    c = context.get_call("route_rfi")
    assert c.state().mode == "shadow"
    with pytest.raises(PeccaError):
        pecca.promote("route_rfi", "live", force=True)  # needs PECCA_ALLOW_FORCE=1


def test_force_is_logged(trained, monkeypatch):
    monkeypatch.setenv("PECCA_ALLOW_FORCE", "1")
    pecca.promote("route_rfi", "shadow")
    dec = pecca.promote("route_rfi", "live", force=True)
    assert dec.forced
    st = context.get_call("route_rfi").state()
    assert st.mode == "live" and any(h["kind"] == "forced_promotion" for h in st.history)


def test_shadow_to_live_after_enough_data(trained, df):
    fn, _, table = llm_for(df)
    pecca.promote("route_rfi", "shadow")
    c = context.get_call("route_rfi")
    st = c.state()
    st.shadow_since = iso(now() - timedelta(days=10))
    c.save_state(st)
    sh = pecca.replace("route_rfi", mode="shadow", input_adapter=lambda t: {"subject": t.split("\n\n")[0], "body": t.split("\n\n", 1)[1]})(fn)
    for t in list(table)[:60]:
        sh(t)
    flush_all()
    rep = pecca.evaluate("route_rfi", "14d")
    assert rep.n_rows == 60 and rep.agreement_rate is not None
    dec = pecca.promote("route_rfi", "live")
    assert dec.allowed == (rep.agreement_rate >= 0.85)


def test_retrain_in_live_demotes_to_shadow(trained, ds, monkeypatch):
    monkeypatch.setenv("PECCA_ALLOW_FORCE", "1")
    pecca.promote("route_rfi", "shadow")
    pecca.promote("route_rfi", "live", force=True)
    res = pecca.train("route_rfi", ds)
    assert res.version == "v2"
    assert context.get_call("route_rfi").state().mode == "shadow"


def test_approve_and_audit_pack(trained, tmp_path):
    rec = pecca.approve("route_rfi", "v1", approver="lead@example.com", groups=["ml-leads"], note="ok")
    assert rec["approver"] == "lead@example.com"
    p = pecca.audit_pack("route_rfi", out="markdown", path=str(tmp_path / "pack"))
    text = open(p).read()
    assert "Benchmark leaderboard" in text and "lead@example.com" in text
    d = tmp_path / "pack"
    assert (d / "manifest.sha256").exists() and (d / "confusion_matrix.png").exists()
    import json

    assert json.loads(pecca.audit_pack("route_rfi", out="json"))["model"]["version"] == "v1"


def test_unreplaceable_call_raises():
    import pandas as pd

    raw = pd.DataFrame({"i": [f"t{i}" for i in range(600)], "o": [f"unique answer {i} " * 4 for i in range(600)]})
    ds = Dataset(canonicalize(raw, {"input": "i", "llm_output": "o", "call_name": {"literal": "gen"}}))
    with pytest.raises(PeccaError, match="not replaceable"):
        pecca.train("gen", ds)


def test_as_tool(trained, df):
    r = df.iloc[0]
    tool = pecca.as_tool("route_rfi")
    out = tool(f"{r.email_subject}\n\n{r.email_body}")
    assert set(out) == {"label", "confidence", "fallback", "version"} and tool.__doc__
