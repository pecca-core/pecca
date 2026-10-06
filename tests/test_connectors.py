import base64
import json
import sqlite3
import sys
import types

import httpx
import pandas as pd
import pytest
import respx

from pecca import connectors
from pecca.connectors.base import INTERFACES, create, register
from pecca.core.errors import ConnectorError, PeccaError


def test_registry_lists_all_interfaces_with_two_plus_implementations():
    rows = connectors.available()
    by = {i: {r["type"] for r in rows if r["interface"] == i} for i in INTERFACES}
    assert all(len(v) >= 2 for v in by.values()), by
    assert len(by["datasource"]) >= 9 and len(by["ticketer"]) >= 3 and len(by["notifier"]) >= 3
    for i, ts in by.items():  # every builtin imports without optional extras installed
        for t in ts:
            connectors.get(i, t)


def test_third_party_register_and_unknown_type():
    @register(interface="ticketer", type="servicenow")
    class SN:
        def __init__(self, **kw):
            self.kw = kw

    assert create("ticketer", {"type": "servicenow", "x": 1}).kw == {"x": 1}
    with pytest.raises(ConnectorError) as e:
        connectors.get("ticketer", "nope")
    assert "servicenow" in e.value.hint
    with pytest.raises(ConnectorError):
        register(interface="bogus", type="x")


@respx.mock
def test_notifiers():
    s = respx.post("https://hooks.slack.test/x").mock(return_value=httpx.Response(200))
    create(
        "notifier", {"type": "slack", "webhook": "https://hooks.slack.test/x", "channel": "#ai"}
    ).send("trained", {}, "hello")
    assert json.loads(s.calls[0].request.content) == {"text": "hello", "channel": "#ai"}
    t = respx.post("https://teams.test/x").mock(return_value=httpx.Response(200))
    create("notifier", {"type": "teams", "webhook": "https://teams.test/x"}).send("live", {}, "hi")
    body = json.loads(t.calls[0].request.content)
    assert body["attachments"][0]["content"]["type"] == "AdaptiveCard"
    w = respx.post("https://wh.test/x").mock(return_value=httpx.Response(500, text="boom"))
    with pytest.raises(ConnectorError):
        create("notifier", {"type": "webhook", "url": "https://wh.test/x"}).send("e", {"a": 1}, "r")
    assert json.loads(w.calls[0].request.content)["payload"] == {"a": 1}


@respx.mock
def test_jira():
    j = create(
        "ticketer",
        {
            "type": "jira",
            "url": "https://x.atlassian.net",
            "project": "MRM",
            "email": "a@b.c",
            "token": "t",
            "group_members": {"model-risk": ["mrm@bank.test"]},
        },
    )
    respx.post("https://x.atlassian.net/rest/api/3/issue").mock(
        return_value=httpx.Response(201, json={"key": "MRM-7"})
    )
    assert j.create("title", "body", {}) == "MRM-7"
    respx.get(url__regex=r".*/issue/MRM-7\?fields=status").mock(
        return_value=httpx.Response(200, json={"fields": {"status": {"name": "In Review"}}})
    )
    assert j.get_status("MRM-7") == "In Review"
    hist = {
        "changelog": {
            "histories": [
                {
                    "author": {"emailAddress": "dev@bank.test"},
                    "items": [{"field": "status", "toString": "In Review"}],
                },
                {
                    "author": {"emailAddress": "mrm@bank.test"},
                    "created": "2026-10-01",
                    "items": [{"field": "status", "toString": "Approved"}],
                },
            ]
        }
    }
    respx.get(url__regex=r".*/issue/MRM-7\?expand=changelog.*").mock(
        return_value=httpx.Response(200, json=hist)
    )
    ap = j.get_approvers("MRM-7")
    assert [a["principal"] for a in ap] == ["mrm@bank.test"] and ap[0]["groups"] == ["model-risk"]
    c = respx.post("https://x.atlassian.net/rest/api/3/issue/MRM-7/comment").mock(
        return_value=httpx.Response(201, json={})
    )
    j.comment("MRM-7", "hi")
    assert json.loads(c.calls[0].request.content)["body"]["type"] == "doc"
    respx.get(url__regex=r".*/transitions$").mock(
        return_value=httpx.Response(200, json={"transitions": [{"id": "31", "name": "Done"}]})
    )
    respx.post(url__regex=r".*/transitions$").mock(return_value=httpx.Response(204))
    j.close("MRM-7")
    respx.get(url__regex=r".*/issue/NOPE.*").mock(return_value=httpx.Response(404, text="x"))
    with pytest.raises(ConnectorError):
        j.get_status("NOPE")


@respx.mock
def test_github_issues_approvals_by_comment_and_group():
    g = create(
        "ticketer",
        {"type": "github", "repo": "o/r", "token": "t", "group_members": {"model-risk": ["alice"]}},
    )
    respx.post("https://api.github.com/repos/o/r/issues").mock(
        return_value=httpx.Response(201, json={"number": 12})
    )
    assert g.create("t", "b", {}) == "12"
    respx.get("https://api.github.com/repos/o/r/issues/12/comments").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"body": "looks fine", "user": {"login": "bob"}},
                {"body": "/approve", "user": {"login": "alice"}, "created_at": "x"},
            ],
        )
    )
    ap = g.get_approvers("12")
    assert len(ap) == 1 and ap[0]["principal"] == "alice" and ap[0]["group"] == "model-risk"
    respx.get("https://api.github.com/repos/o/r/issues/12").mock(
        return_value=httpx.Response(200, json={"state": "open"})
    )
    assert g.get_status("12") == "open"


def test_manual_ticketer(tmp_path):
    m = create("ticketer", {"type": "manual", "dir": str(tmp_path)})
    t = m.create("title", "body", {})
    assert t == "MAN-1" and m.get_status(t) == "pending"
    m.comment(t, "c")
    m.close(t)
    assert m.get_status(t) == "closed"
    with pytest.raises(PeccaError):
        m.get_status("MAN-99")


@respx.mock
def test_confluence_create_then_update():
    c = create(
        "docs_publisher",
        {
            "type": "confluence",
            "url": "https://wiki.test",
            "space": "AI",
            "token": "t",
            "email": "a@b.c",
            "parent_page_id": "5",
        },
    )
    respx.get("https://wiki.test/rest/api/content").mock(
        side_effect=[
            httpx.Response(200, json={"results": []}),
            httpx.Response(200, json={"results": [{"id": "9", "version": {"number": 3}}]}),
        ]
    )
    post = respx.post("https://wiki.test/rest/api/content").mock(
        return_value=httpx.Response(200, json={"id": "9", "_links": {"webui": "/pages/9"}})
    )
    put = respx.put("https://wiki.test/rest/api/content/9").mock(
        return_value=httpx.Response(200, json={"id": "9", "_links": {"webui": "/pages/9"}})
    )
    assert c.publish("T", "<p>x</p>", {}) == "https://wiki.test/pages/9"
    assert json.loads(post.calls[0].request.content)["ancestors"] == [{"id": "5"}]
    c.publish("T", "<p>y</p>", {})
    assert json.loads(put.calls[0].request.content)["version"]["number"] == 4


def test_markdown_publisher(tmp_path):
    p = create("docs_publisher", {"type": "markdown", "dir": str(tmp_path)}).publish(
        "My Page/1", "# x", {}
    )
    assert open(p).read() == "# x"


def test_scheduler_cron_airflow_databricks(tmp_path, capsys):
    from pecca.connectors.scheduler.cron import cron_expr

    assert (
        cron_expr("1d") == "0 6 * * *"
        and cron_expr("7d") == "0 6 */7 * *"
        and cron_expr("2w") == "0 6 */14 * *"
    )
    assert cron_expr("1m") == "0 6 1 * *" and cron_expr("1y") == "0 6 1 1 *"
    with pytest.raises(PeccaError):
        cron_expr("often")
    cron = create("scheduler", {"type": "cron", "path": str(tmp_path / "j.json")})
    cron.register_job("train", "7d", ["pecca", "scheduler", "run", "--once"])
    assert "0 6 */7 * * pecca scheduler run --once" in capsys.readouterr().out
    assert cron.list_jobs()[0]["name"] == "train"
    af = create("scheduler", {"type": "airflow", "dags_dir": str(tmp_path / "dags")})
    af.register_job("a/b", "1d", ["pecca", "scheduler", "run"])
    assert "BashOperator" in (tmp_path / "dags" / "pecca_a_b.py").read_text()
    db = create(
        "scheduler",
        {"type": "databricks_workflows", "out_dir": str(tmp_path / "dbx"), "cluster_id": "c1"},
    )
    db.register_job("train", "7d", ["pecca", "train", "x"])
    job = db.list_jobs()[0]
    assert job["name"] == "pecca-train" and job["tasks"][0]["existing_cluster_id"] == "c1"


def test_serving_docker_export(tmp_path):
    from pecca.connectors.registry.local import LocalRegistry

    reg = LocalRegistry(tmp_path / "h")
    art = tmp_path / "art"
    art.mkdir()
    (art / "config.json").write_text("{}")
    key = "pecca/default/default/route_rfi"
    reg.save_model(key, "v1", str(art), {"version": "v1"})
    s = create(
        "serving",
        {"type": "docker_export", "out_dir": str(tmp_path / "out"), "home": str(tmp_path / "h")},
    )
    d = s.deploy(key, "v1")
    for f in ("Dockerfile", "app.py", "requirements.txt", "model/config.json"):
        assert (tmp_path / "out" / "route_rfi-v1" / f).exists()
    compile(open(f"{d}/app.py").read(), "app.py", "exec")
    local = create("serving", {"type": "onnx_local", "home": str(tmp_path / "h")})
    assert local.deploy(key, "v1").endswith("v1") and local.endpoint(key) is None


def test_identity(monkeypatch):
    monkeypatch.delenv("PECCA_ID_TOKEN", raising=False)
    assert create("identity", {"type": "oidc"}).current_principal()["groups"] == ["local"]
    claims = (
        base64.urlsafe_b64encode(json.dumps({"email": "a@b.c", "groups": ["model-risk"]}).encode())
        .decode()
        .rstrip("=")
    )
    monkeypatch.setenv("PECCA_ID_TOKEN", f"h.{claims}.s")
    assert create("identity", {"type": "oidc"}).current_principal() == {
        "user": "a@b.c",
        "groups": ["model-risk"],
    }
    monkeypatch.setenv("PECCA_ID_TOKEN", "garbage")
    assert create("identity", {"type": "oidc"}).current_principal()["groups"] == []


def test_secrets_env_vault_aws(monkeypatch):
    monkeypatch.setenv("S1", "v1")
    assert create("secrets", {"type": "env"}).get("S1") == "v1"
    with pytest.raises(ConnectorError, match="S_NOPE"):
        create("secrets", {"type": "env"}).get("S_NOPE")

    class KV:
        def read_secret_version(self, path, mount_point):
            return {"data": {"data": {"JIRA_TOKEN": "tok"}}}

    hv = types.ModuleType("hvac")
    hv.Client = lambda **kw: types.SimpleNamespace(
        secrets=types.SimpleNamespace(kv=types.SimpleNamespace(v2=KV()))
    )
    monkeypatch.setitem(sys.modules, "hvac", hv)
    v = create("secrets", {"type": "vault", "url": "http://v", "token": "t"})
    assert v.get("JIRA_TOKEN") == "tok"
    with pytest.raises(ConnectorError):
        v.get("MISSING")
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    with moto.mock_aws():
        sm = boto3.client("secretsmanager")
        sm.create_secret(Name="PLAIN", SecretString="p")
        sm.create_secret(Name="J", SecretString=json.dumps({"J": "jv"}))
        a = create("secrets", {"type": "aws-secrets-manager", "region": "us-east-1"})
        assert a.get("PLAIN") == "p" and a.get("J") == "jv"
        with pytest.raises(ConnectorError):
            a.get("NOPE")


COLS = {
    "input": "txt",
    "llm_output": "out",
    "human_label": "hl",
    "call_name": {"literal": "c"},
    "timestamp": "ts",
}


def _sqlite(tmp_path, cls_name, **kw):
    db = tmp_path / "t.db"
    con = sqlite3.connect(db)
    con.execute("create table logs (txt text, out text, hl text, ts text)")
    con.executemany(
        "insert into logs values (?,?,?,?)",
        [
            ("a", "x", None, "2026-01-01 00:00:00"),
            ("b", "y", "z", "2026-10-01 00:00:00"),
            ("c", "x", None, "2099-01-01 00:00:00"),
        ],
    )
    con.commit()
    con.close()
    cls = connectors.get("datasource", cls_name)

    class Lite(cls):
        def _execute(self, sql):
            self.last_sql = sql
            c = sqlite3.connect(db)
            try:
                return pd.read_sql_query(sql, c)
            finally:
                c.close()

    return Lite(table="logs", columns=COLS, **kw)


@pytest.mark.parametrize("kind", ["postgres", "databricks", "snowflake", "bigquery"])
def test_sql_datasources_share_query_building(tmp_path, kind):
    ds = _sqlite(tmp_path, kind)
    df = ds.read()
    assert (
        len(df) == 3
        and list(df["human_label"].fillna("-")) == ["-", "z", "-"]
        and set(df["call_name"]) == {"c"}
    )
    assert len(ds.read(since="2026-06-01")) == 2 and "WHERE ts >=" in ds.last_sql
    assert len(ds.read(limit=1)) == 1 and ds.last_sql.endswith("LIMIT 1")


def test_sql_rejects_unsafe_table():
    with pytest.raises(ConnectorError, match="unsafe"):
        connectors.get("datasource", "postgres")(table="x; drop table y", columns=COLS)


def test_csv_parquet_and_schema_errors(tmp_path):
    from pecca.core.errors import SchemaError

    df = pd.DataFrame({"txt": ["a", "b"], "out": ["x", "y"]})
    df.to_csv(tmp_path / "a.csv", index=False)
    df.to_parquet(tmp_path / "a.parquet")
    cols = {"input": "txt", "llm_output": "out", "call_name": {"literal": "c"}}
    for t, f in (("csv", "a.csv"), ("parquet", "a.parquet")):
        out = create("datasource", {"type": t, "path": str(tmp_path / f), "columns": cols}).read()
        assert list(out["llm_output"]) == ["x", "y"] and out["human_label"].isna().all()
    with pytest.raises(SchemaError, match="not found in data"):
        create(
            "datasource",
            {
                "type": "csv",
                "path": str(tmp_path / "a.csv"),
                "columns": {**cols, "input": "missing"},
            },
        ).read()
    with pytest.raises(SchemaError, match="unknown canonical"):
        create(
            "datasource",
            {"type": "csv", "path": str(tmp_path / "a.csv"), "columns": {**cols, "bogus": "txt"}},
        ).read()


def test_litellm_and_gateway_extraction():
    from pecca.connectors.datasource import _chat

    req = {"messages": [{"role": "system", "content": "s"}, {"role": "user", "content": "hello"}]}
    resp = {"choices": [{"message": {"content": "BILLING"}}]}
    assert (
        _chat.extract_input(json.dumps(req)) == "hello"
        and _chat.extract_output(json.dumps(resp)) == "BILLING"
    )
    assert (
        _chat.extract_output({"choices": [{"text": "t"}]}) == "t"
        and _chat.extract_input({"prompt": "p"}) == "p"
    )
    lit = connectors.get("datasource", "litellm")(dsn="x", call_name_key="pecca_call")
    lit._execute = lambda sql: pd.DataFrame(
        {
            "request_id": ["r1", "r2"],
            "model": ["m", "m"],
            "startTime": ["2026-10-01"] * 2,
            "messages": [json.dumps(req)] * 2,
            "response": [json.dumps(resp)] * 2,
            "metadata": [json.dumps({"pecca_call": "route"}), None],
        }
    )
    out = lit.read()
    assert list(out["call_name"]) == ["route"]  # rows without a call name are not routable
    gw = connectors.get("datasource", "databricks-ai-gateway")(
        table="cat.sch.t_payload", endpoint_name="ep"
    )
    gw._execute = lambda sql: pd.DataFrame(
        {
            "databricks_request_id": ["a", "b"],
            "request_time": ["2026-10-01"] * 2,
            "status_code": [200, 500],
            "request": [json.dumps(req)] * 2,
            "response": [json.dumps(resp)] * 2,
        }
    )
    out = gw.read()
    assert (
        len(out) == 1
        and out.iloc[0]["call_name"] == "ep"
        and out.iloc[0]["llm_output"] == "BILLING"
    )


def test_otel_traces_jsonl_and_parquet(tmp_path):
    def span(i, attrs, name="route"):
        return {
            "resourceSpans": [
                {
                    "scopeSpans": [
                        {
                            "spans": [
                                {
                                    "traceId": f"t{i}",
                                    "spanId": f"s{i}",
                                    "name": name,
                                    "startTimeUnixNano": str(1_760_000_000_000_000_000 + i),
                                    "attributes": [
                                        {"key": k, "value": {"stringValue": v}}
                                        for k, v in attrs.items()
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

    f = tmp_path / "t.jsonl"
    f.write_text(
        "\n".join(
            json.dumps(x)
            for x in [
                span(
                    1,
                    {"gen_ai.prompt": "hi", "gen_ai.completion": "A", "gen_ai.request.model": "m"},
                ),
                span(2, {"input.value": "yo", "output.value": "B", "pecca.call": "custom"}),
                span(3, {"other": "x"}),
            ]
        )
    )
    out = create("datasource", {"type": "otel-traces", "path": str(f)}).read()
    assert (
        list(out["llm_output"]) == ["A", "B"]
        and list(out["call_name"]) == ["route", "custom"]
        and out["timestamp"].notna().all()
    )
    pd.DataFrame(
        {"name": ["r"], "input.value": ["q"], "output.value": ["Z"], "context.span_id": ["1"]}
    ).to_parquet(tmp_path / "o.parquet")
    assert list(
        create("datasource", {"type": "otel-traces", "path": str(tmp_path / "o.parquet")}).read()[
            "llm_output"
        ]
    ) == ["Z"]


def test_mcp_transport_adapters_against_inprocess_server():
    from mcp.server.mcpserver import MCPServer

    srv = MCPServer("fake-tracker")
    store: dict = {}

    @srv.tool()
    def create_issue(title: str, body: str, project: str = "") -> dict:
        store["1"] = {
            "id": "ISS-1",
            "status": "Open",
            "approvers": [{"principal": "mrm@x"}],
            "title": title,
            "project": project,
        }
        return {"id": "ISS-1"}

    @srv.tool()
    def get_issue(id: str) -> dict:
        return store["1"]

    @srv.tool()
    def add_comment(id: str, body: str) -> str:
        store.setdefault("c", []).append(body)
        return "ok"

    @srv.tool()
    def notify(event: str, text: str) -> str:
        store["n"] = (event, text)
        return "sent"

    @srv.tool()
    def read_rows(limit: int = 10) -> list[dict]:
        return [{"i": "a", "o": "x"}, {"i": "b", "o": "y"}]

    tk = create(
        "ticketer",
        {
            "type": "jira",
            "transport": "mcp",
            "url": srv,
            "args": {"create": {"project": "MRM"}},
            "tool_map": {"create": "create_issue", "get": "get_issue", "comment": "add_comment"},
        },
    )
    assert tk.create("T", "B", {}) == "ISS-1" and store["1"]["project"] == "MRM"
    assert tk.get_status("ISS-1") == "Open" and tk.get_approvers("ISS-1") == [
        {"principal": "mrm@x"}
    ]
    tk.comment("ISS-1", "hello")
    assert store["c"] == ["hello"]
    create(
        "notifier",
        {"type": "slack", "transport": "mcp", "url": srv, "tool_map": {"send": "notify"}},
    ).send("trained", {}, "msg")
    assert store["n"] == ("trained", "msg")
    ds = create(
        "datasource",
        {
            "type": "mcp",
            "url": srv,
            "tool_map": {"read": "read_rows"},
            "columns": {"input": "i", "llm_output": "o", "call_name": {"literal": "c"}},
        },
    )
    assert list(ds.read()["llm_output"]) == ["x", "y"]
    for cfg in ({"tool_map": {"create": "does_not_exist"}}, {}):
        with pytest.raises(ConnectorError) as e:
            create("ticketer", {"type": "mcp", "url": srv, **cfg}).create("t", "b", {})
        assert "transport: rest" in e.value.hint


def test_wandb_registry_with_fake_module(tmp_path, monkeypatch):
    import pathlib

    class Art:
        def __init__(self, name, type=None, metadata=None):
            self.name, self.type, self.metadata, self.files = name, type, metadata or {}, {}

        def add_dir(self, d):
            self.files.update({p.name: p.read_bytes() for p in pathlib.Path(d).iterdir()})

        def add_file(self, path, name=None):
            self.files[name] = pathlib.Path(path).read_bytes()

        def download(self, root):
            r = pathlib.Path(root)
            r.mkdir(parents=True, exist_ok=True)
            for n, b in self.files.items():
                (r / n).write_bytes(b)
            return str(r)

    store: dict[str, list[tuple[list[str], Art]]] = {}

    class Run:
        def log_artifact(self, art, aliases):
            store.setdefault(art.name, []).append((aliases, art))

        def finish(self):
            pass

    class Api:
        def artifact(self, full):
            name, alias = full.split("/")[-1].rsplit(":", 1)
            for aliases, a in reversed(store.get(name, [])):
                if alias in aliases:
                    return a
            raise KeyError(full)

        def artifact_collection(self, kind, path):
            name = path.split("/")[-1]
            return types.SimpleNamespace(artifacts=lambda: [a for _, a in store.get(name, [])])

        def artifact_type(self, kind, path):
            return types.SimpleNamespace(
                collections=lambda: [
                    types.SimpleNamespace(name=n, artifacts=lambda n=n: [a for _, a in store[n]])
                    for n in store
                    if "-logs-" in n
                ]
            )

    wb = types.ModuleType("wandb")
    wb.Artifact, wb.Api, wb.init = Art, Api, lambda **kw: Run()
    monkeypatch.setitem(sys.modules, "wandb", wb)
    reg = create("registry", {"type": "wandb", "uri": "wandb://ent/proj", "home": str(tmp_path)})
    key = "pecca/default/default/route_rfi"
    art = tmp_path / "a"
    art.mkdir()
    (art / "config.json").write_text("{}")
    reg.save_model(key, "v1", str(art), {"version": "v1"})
    reg.save_model(key, "v2", str(art), {"version": "v2"})
    assert [m["version"] for m in reg.list_versions(key)] == ["v1", "v2"]
    assert (pathlib.Path(reg.load_model(key, "v2")) / "config.json").exists()
    reg.set_state(key, {"mode": "shadow"})
    reg.set_state(key, {"mode": "live"})
    assert reg.get_state(key) == {"mode": "live"}
    reg.append_logs(key, [{"ts": "2026-10-01T00:00:00+00:00", "a": 1}])
    assert list(reg.read_logs(key, "2000-01-01")["a"]) == [1]
    with pytest.raises(ConnectorError):
        create("registry", {"type": "wandb", "uri": "wandb://bad"})
