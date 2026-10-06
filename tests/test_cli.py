import json
import re

import pytest
import yaml
from typer.testing import CliRunner

import pecca
from pecca.cli.main import app
from pecca.core import context

runner = CliRunner()


def run(*args, ok=True):
    res = runner.invoke(app, list(args))
    if ok:
        assert res.exit_code == 0, res.output
    return res


@pytest.fixture()
def project(tmp_path):
    run("datasets", "demo", "--out", "data/demo")
    run("init", "--profile", "none")
    cfg = yaml.safe_load(open("pecca.yaml"))
    cfg["projects"]["default"]["datasource"] = {
        "type": "csv",
        "path": "data/demo/train.csv",
        "columns": {
            "input": {"subject": "email_subject", "body": "email_body"},
            "llm_output": "llm_rfi",
            "human_label": "human_rfi",
            "call_name": {"literal": "route_rfi"},
        },
    }
    cfg["projects"]["default"]["calls"] = {
        "route_rfi": {"policy": {"train_every": "7d", "target_precision": 0.9}}
    }
    cfg["projects"]["default"]["governance"]["extends"] = "none"
    open("pecca.yaml", "w").write(yaml.safe_dump(cfg))
    run("apply")
    context.reset()
    return tmp_path


def test_version_and_help():
    assert run("version").output.strip() == pecca.__version__
    assert "init" in run("--help").output


def test_init_creates_files_and_refuses_overwrite(tmp_path):
    out = run("init", "--profile", "sr11-7", "--project", "ar")
    assert "created pecca.yaml, templates/" in out.output
    assert (tmp_path / "templates" / "approval_ticket.md.j2").exists() and (
        tmp_path / "templates" / "audit_pack" / "summary.md.j2"
    ).exists()
    assert (
        ".pecca/" in (tmp_path / ".gitignore").read_text() and (tmp_path / ".env.example").exists()
    )
    res = run("init", ok=False)
    assert (
        res.exit_code == 1
        and "error: pecca.yaml already exists" in res.output
        and "hint:" in res.output
    )
    run("init", "--force", "--profile", "none")
    res = run("init", "--profile", "bogus", "--force", ok=False)
    assert res.exit_code == 1 and "unknown governance profile" in res.output


def test_full_flow_and_status_format(project, monkeypatch):
    assert "6,000 rows" in run("connect").output
    prof = run("profile").output
    assert "route_rfi" in prof and "60 labels" in prof and "✔" in prof
    tr = run("train", "default/default/route_rfi").output
    assert "winner" in tr and "threshold" in tr and "★" in tr
    assert (
        "shadow since now" in run("promote", "default/default/route_rfi", "--mode", "shadow").output
    )
    st = run("status", "default/default/route_rfi").output.splitlines()
    keys = [l.split()[0] for l in st]
    assert keys == ["call", "mode", "version", "model", "threshold", "agreement", "policy", "next"]
    assert st[0] == "call       default/default/route_rfi"
    assert re.fullmatch(r"mode       shadow          since \d{4}-\d\d-\d\d", st[1])
    assert re.fullmatch(r"version    v1              trained \d{4}-\d\d-\d\d on 6,000 rows", st[2])
    assert re.fullmatch(r"model      \w+\s+macro_f1 0\.\d\d  \(llm 0\.\d\d\)", st[3])
    assert re.fullmatch(r"threshold  0\.\d\d\s+expected fallback \d+%", st[4])
    assert st[5].startswith("agreement  - (14d)") and "fallback -   drift -" in st[5]
    assert st[6] == "policy     shadow_at cv_metric>=0.80  live_at agreement>=0.85 & shadow_days>=7"
    assert re.fullmatch(r"next       retrain \d{4}-\d\d-\d\d", st[7])
    tbl = run("status").output
    assert (
        all(
            h in tbl for h in ("call", "rows", "metric", "mode", "agreement", "fallback", "version")
        )
        and "route_rfi" in tbl
    )
    assert "route_rfi" in run("status", "default").output
    blocked = run("promote", "default/default/route_rfi", "--mode", "live", ok=False)
    assert blocked.exit_code == 1 and "gate failing: shadow_days" in blocked.output
    run("train", "default/default/route_rfi")
    d = run("diff", "default/default/route_rfi", "v1", "v2").output
    assert "per-class F1 deltas" in d and "v1" in d and "v2" in d
    assert run("eval", "default/default/route_rfi").exit_code == 0
    assert "no logs" in run("logs", "default/default/route_rfi").output
    out = run("audit", "default/default/route_rfi", "--out", "json").output
    assert json.loads(out)["model"]["version"] == "v2"
    monkeypatch.setenv("PECCA_ALLOW_FORCE", "1")
    forced = run("promote", "default/default/route_rfi", "--mode", "live", "--force")
    assert "live since now  (forced)" in forced.output and "blocked" not in forced.output
    assert (
        run(
            "approve",
            "default/default/route_rfi",
            "--version",
            "v1",
            "--approver",
            "a@b.c",
            "--group",
            "ml-leads",
        ).exit_code
        == 0
    )
    assert run("doctor").exit_code == 0


def test_error_format_and_unknown_call(project):
    res = run("train", "default/default/nope", ok=False)
    assert (
        res.exit_code == 1
        and "error: no data for default/default/nope" in res.output
        and "hint:" in res.output
    )


def test_plugins_and_scheduler(project):
    out = run("plugins", "list").output
    assert "tfidf_linear" in out and "jira" in out
    run("train", "default/default/route_rfi")
    from pecca.cli.commands import ops

    st = context.get_call("default/default/route_rfi").state()
    st.last_trained = "2020-01-01T00:00:00+00:00"
    context.get_call("default/default/route_rfi").save_state(st)
    assert any("retrained" in x for x in ops.tick())
    assert "nothing due" in run("scheduler", "run", "--once").output


def test_doctor_fails_on_unresolved_secret(project, monkeypatch):
    cfg = yaml.safe_load(open("pecca.yaml"))
    cfg["projects"]["default"]["integrations"] = {
        "notifier": {"type": "slack", "webhook": "${NOPE_HOOK}"}
    }
    monkeypatch.setenv("NOPE_HOOK", "x")
    open("pecca.yaml", "w").write(yaml.safe_dump(cfg))
    run("apply")
    monkeypatch.delenv("NOPE_HOOK")
    context.reset()
    res = run("doctor", ok=False)
    assert res.exit_code == 1 and "NOPE_HOOK" in res.output


def test_ops_branches(project, monkeypatch):
    from pecca.cli.commands import ops

    run("train", "default/default/route_rfi")
    c = context.get_call("default/default/route_rfi")
    st = c.state()
    st.mode, st.shadow_since = "shadow", "2020-01-01T00:00:00+00:00"
    st.last_revalidated = st.last_drift_review = "2000-01-01T00:00:00+00:00"
    c.save_state(st)
    out = ops.tick()
    assert (
        any("revalidate" in x for x in out) and any("drift_review" in x for x in out) or out == []
    )
    cfg = yaml.safe_load(open("pecca.yaml"))
    cfg["workspace"] = {
        "name": "default",
        "telemetry": {"exporter": "otlp", "endpoint": "http://127.0.0.1:9"},
    }
    cfg["projects"]["default"]["governance"]["extends"] = "default"
    open("pecca.yaml", "w").write(yaml.safe_dump(cfg))
    run("apply")
    context.reset()
    d = run("doctor").output
    assert "shadow > 30 days" in d and "otel endpoint not reachable" in d
    started = {}

    class FakeServer:
        def run(self, transport, **kw):
            started.update(transport=transport, **kw)

    monkeypatch.setattr("pecca.mcp.server.build_server", lambda **kw: FakeServer())
    run("mcp", "serve")
    assert started["transport"] == "stdio"
    run("mcp", "serve", "--transport", "http", "--port", "9123", "--allow-promote")
    assert started["transport"] == "streamable-http" and started["port"] == 9123


def test_logs_filters(project):
    run("train", "default/default/route_rfi")
    run("promote", "default/default/route_rfi", "--mode", "shadow")
    f = pecca.replace("default/default/route_rfi", mode="shadow")(lambda text: "card_lost_stolen")
    for t in ("a card was lost", "need a loan top up please"):
        f(t)
    from pecca.runtime.logging_sink import flush_all

    flush_all()
    assert "shadow" in run("logs", "default/default/route_rfi").output
    assert (
        "shadow"
        in run("logs", "default/default/route_rfi", "--disagreements", "--limit", "5").output
    )
    assert "shadow" not in run("logs", "default/default/route_rfi", "--fallbacks").output.replace(
        "served_by", ""
    )
    assert run("eval", "default/default/route_rfi", "--since", "1d").exit_code == 0
