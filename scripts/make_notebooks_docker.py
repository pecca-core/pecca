"""Generate the connector (8) and monitoring (3) notebooks. Run: uv run python scripts/make_notebooks_docker.py

Cells that need Docker are guarded by ``USE_DOCKER`` (false when ``PECCA_SKIP_DOCKER=1``, as in CI) and every notebook
still executes end to end without Docker, using a documented fallback.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_notebooks import badge, build  # noqa: E402

SETUP = '''
import json, os, re, shutil, subprocess, tempfile, time
from pathlib import Path

import pandas as pd
import pecca
from pecca.core import context
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.synthetic import generate

HERE = Path.cwd()                                   # the notebook's folder (examples/notebooks in the repo)
work = tempfile.mkdtemp()
os.chdir(work)
os.environ["PECCA_HOME"] = os.path.join(work, ".pecca")
os.environ["TQDM_DISABLE"] = "1"
os.environ["MLFLOW_SUPPRESS_PRINTING_URL_TO_STDOUT"] = "1"
import logging
try:
    import mlflow  # MLflow resets its logger level on import, so quiet it afterwards
    logging.getLogger("mlflow").setLevel(logging.ERROR)
except ImportError:
    pass

# Docker-backed cells run only when Docker is reachable and PECCA_SKIP_DOCKER != 1 (CI sets it).
USE_DOCKER = (os.environ.get("PECCA_SKIP_DOCKER") != "1" and shutil.which("docker") is not None
              and subprocess.run(["docker", "info"], capture_output=True).returncode == 0)
print("docker:", "available" if USE_DOCKER else "skipped (PECCA_SKIP_DOCKER=1 or Docker not reachable)")

def sh(*args, check=True):
    return subprocess.run([str(a) for a in args], capture_output=True, text=True, check=check)

import atexit
def cleanup_later(*cmd):
    """Run `cmd` when the kernel exits, so containers are removed even if a cell fails."""
    atexit.register(lambda: subprocess.run([str(c) for c in cmd], capture_output=True))

def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def wait_for(check, what, seconds=90):
    end = time.time() + seconds
    while time.time() < end:
        try:
            if check():
                return
        except Exception:
            pass
        time.sleep(1)
    raise TimeoutError(f"{what} did not become ready in {seconds}s")

def train_demo(call="route_rfi", rows=3000, candidates=("tfidf_linear",), **kw):
    """Train a small model on the synthetic demo data (LLM answers + human corrections)."""
    df = generate(rows)
    df["text"] = df.email_subject + "\\n\\n" + df.email_body
    cols = {"input": "text", "llm_output": "llm_rfi", "human_label": "human_rfi", "call_name": {"literal": call.split("/")[-1]}}
    return pecca.train(call, Dataset(canonicalize(df, cols), cols), candidates=list(candidates), **kw)
'''

LLM_REPLAY = """
# The "LLM": replay the simulated LLM's answers for a few new emails (no API needed).
new = generate(30, seed=11)
texts = (new.email_subject + "\\n\\n" + new.email_body).tolist()
said = dict(zip(texts, new.llm_rfi))

@pecca.replace("route_rfi", mode="shadow")
def route_rfi(text: str) -> str:
    return said[text]                      # stand-in for my_llm.classify(text), unchanged
"""


def nb(
    name: str,
    title: str,
    intro: str,
    needs_docker: bool,
    cells: list[tuple[str, str]],
    pkgs: str = "",
) -> None:
    path = f"examples/notebooks/{name}.ipynb"
    docker_note = (
        "\n> Needs **Docker** for the container cells; without it (`PECCA_SKIP_DOCKER=1`) those cells are skipped and a fallback runs."
        if needs_docker
        else ""
    )
    build(
        path,
        [
            ("md", f"# {title}\n\n{badge(path)}\n\n{intro}{docker_note}"),
            ("code", f"%pip install -q pecca {pkgs}".strip()),
            ("code", SETUP),
            *cells,
        ],
    )


# ---- monitoring ---------------------------------------------------------------------------------
def monitoring_notebooks() -> None:
    telemetry_yaml = """
telemetry = "  telemetry: {exporter: otlp, endpoint: http://127.0.0.1:4318/v1/traces, service: pecca-demo}\\n" if USE_DOCKER else ""
Path("pecca.yaml").write_text("version: 1\\nworkspace:\\n  name: default\\n" + telemetry + "projects:\\n  default: {governance: {extends: none}}\\n")
context.reset()
print(Path("pecca.yaml").read_text())
"""
    flush = """
from opentelemetry import trace
trace.get_tracer_provider().force_flush() if hasattr(trace.get_tracer_provider(), "force_flush") else None
from pecca.runtime.logging_sink import flush_all
flush_all()
"""
    nb(
        "monitoring_jaeger",
        "Monitoring with Jaeger",
        "Pecca emits one OpenTelemetry span per call (`pecca.call`). Here a local **Jaeger** collects them and we read them back through Jaeger's API.",
        True,
        [
            (
                "md",
                "## 1. Start Jaeger\n`examples/monitoring/jaeger/docker-compose.yml` (UI on http://localhost:16686; OTLP/HTTP on 4318).",
            ),
            (
                "code",
                """
COMPOSE = ["docker", "compose", "-p", "pecca-jaeger", "-f", str(HERE.parent / "monitoring" / "jaeger" / "docker-compose.yml")]
if USE_DOCKER:
    import requests
    cleanup_later(*COMPOSE, "down", "-v")
    sh(*COMPOSE, "up", "-d")
    wait_for(lambda: requests.get("http://127.0.0.1:16686/", timeout=2).status_code == 200, "Jaeger UI")
    print("Jaeger is up")
""",
            ),
            (
                "md",
                "## 2. Point Pecca at it and run some shadow calls\nThe only Pecca config is `workspace.telemetry`; there is no vendor-specific code.",
            ),
            ("code", telemetry_yaml),
            (
                "code",
                'result = train_demo()\nprint(f"trained {result.winner}: macro_f1 {result.metric:.2f}, threshold {result.threshold:.2f}")',
            ),
            (
                "code",
                LLM_REPLAY
                + """
pecca.promote("route_rfi", "shadow")
for t in texts:
    route_rfi(t)
"""
                + flush
                + '\nprint(f"ran {len(texts)} shadow calls")',
            ),
            ("md", "## 3. Read the spans back from Jaeger"),
            (
                "code",
                """
if USE_DOCKER:
    def fetch():
        r = requests.get("http://127.0.0.1:16686/api/traces", params={"service": "pecca-demo", "limit": 100}, timeout=10).json()
        return r["data"]
    wait_for(lambda: len(fetch()) >= len(texts), "spans in Jaeger", 60)
    rows = []
    for tr in fetch():
        for sp in tr["spans"]:
            if sp["operationName"] == "pecca.call":
                tags = {t["key"]: t["value"] for t in sp["tags"]}
                rows.append({"mode": tags.get("pecca.mode"), "served_by": tags.get("pecca.served_by"), "version": tags.get("pecca.version"),
                             "confidence": round(tags.get("pecca.confidence", float("nan")), 2), "agreement": tags.get("pecca.agreement"),
                             "latency_ms": round(tags.get("pecca.latency_ms", float("nan")), 2)})
    spans = pd.DataFrame(rows)
    print(f"{len(spans)} pecca.call spans received by Jaeger")
    display(spans.head(8))
    print(spans.groupby(["mode", "served_by"]).size().rename("spans").to_frame())
    print(f"agreement with the LLM: {spans['agreement'].mean():.0%}")
else:
    print("skipped: needs Docker. With Docker, this cell lists the pecca.call spans Jaeger received.")
""",
            ),
            ("md", "## 4. Clean up"),
            ("code", 'if USE_DOCKER:\n    sh(*COMPOSE, "down", "-v")\n    print("Jaeger stopped")'),
        ],
        "requests",
    )

    nb(
        "monitoring_grafana_tempo",
        "Monitoring with Grafana Tempo",
        "Spans go to **Tempo**; **Grafana** shows them in a dashboard that is provisioned from `examples/monitoring/grafana/`. We query Tempo with TraceQL and check the dashboard through Grafana's API.",
        True,
        [
            (
                "md",
                "## 1. Start Tempo + Grafana\nGrafana: http://localhost:3000 (anonymous admin, local demo only).",
            ),
            (
                "code",
                """
COMPOSE = ["docker", "compose", "-p", "pecca-tempo", "-f", str(HERE.parent / "monitoring" / "tempo" / "docker-compose.yml")]
if USE_DOCKER:
    import requests
    cleanup_later(*COMPOSE, "down", "-v")
    sh(*COMPOSE, "up", "-d")
    wait_for(lambda: requests.get("http://127.0.0.1:3200/ready", timeout=2).text.strip() == "ready", "Tempo", 120)
    wait_for(lambda: requests.get("http://127.0.0.1:3000/api/health", timeout=2).json().get("database") == "ok", "Grafana", 120)
    print("Tempo and Grafana are up")
""",
            ),
            ("md", "## 2. Run shadow calls with telemetry on"),
            ("code", telemetry_yaml),
            (
                "code",
                'result = train_demo()\nprint(f"trained {result.winner}: macro_f1 {result.metric:.2f}")',
            ),
            (
                "code",
                LLM_REPLAY
                + """
pecca.promote("route_rfi", "shadow")
for t in texts:
    route_rfi(t)
"""
                + flush
                + '\nprint(f"ran {len(texts)} shadow calls")',
            ),
            (
                "md",
                "## 3. Query Tempo with TraceQL\nThe same queries back the provisioned dashboard panels.",
            ),
            (
                "code",
                """
def traceql(q):
    r = requests.get("http://127.0.0.1:3200/api/search", params={"q": q, "limit": 100}, timeout=10).json()
    return r.get("traces", [])

if USE_DOCKER:
    wait_for(lambda: len(traceql('{ name = "pecca.call" }')) >= len(texts), "spans in Tempo", 90)
    queries = {
        "all pecca.call spans": '{ name = "pecca.call" }',
        "served by the LLM (shadow)": '{ span.pecca.served_by = "llm" }',
        "model disagreed with the LLM": '{ span.pecca.agreement = false }',
        "served by fallback": '{ span.pecca.served_by = "fallback" }',
        "confidence < 0.6": '{ name = "pecca.call" && span.pecca.confidence < 0.6 }',
    }
    print(pd.Series({k: len(traceql(q)) for k, q in queries.items()}, name="traces").to_frame())
else:
    print("skipped: needs Docker.")
""",
            ),
            ("md", "## 4. The provisioned Grafana dashboard"),
            (
                "code",
                """
if USE_DOCKER:
    dash = requests.get("http://127.0.0.1:3000/api/dashboards/uid/pecca-llm-replacement", timeout=10).json()["dashboard"]
    via_grafana = requests.get("http://127.0.0.1:3000/api/datasources/proxy/uid/pecca-tempo/api/search",
                               params={"q": '{ name = "pecca.call" }', "limit": 100}, timeout=10).json()["traces"]
    print("dashboard:", dash["title"], f"| Grafana -> Tempo datasource returns {len(via_grafana)} traces")
    for p in dash["panels"]:
        print(f" - {p['title']:<28} {p['targets'][0]['query']}")
    print("Open http://localhost:3000/d/pecca-llm-replacement to see it.")
else:
    d = json.loads((HERE.parent / "monitoring" / "grafana" / "dashboards" / "pecca-llm-replacement.json").read_text())
    print("dashboard JSON (not started):", d["title"], [p["title"] for p in d["panels"]])
""",
            ),
            ("md", "## 5. Clean up"),
            (
                "code",
                'if USE_DOCKER:\n    sh(*COMPOSE, "down", "-v")\n    print("Tempo and Grafana stopped")',
            ),
        ],
        "requests",
    )

    nb(
        "monitoring_mlflow",
        "Monitoring with MLflow",
        "Pecca stores each model version in your registry. With `workspace.registry: mlflow://...` every version becomes an MLflow run (params, metrics, artefacts) plus a `pyfunc` model, "
        "and call state and decision logs live next to them. Here a local MLflow server plays the role of your tracking server.",
        False,
        [
            ("md", "## 1. Start a local MLflow server"),
            (
                "code",
                """
import socket, sys
port = free_port()
mlflow_proc = subprocess.Popen([sys.executable, "-m", "mlflow", "server", "--host", "127.0.0.1", "--port", str(port),
                                "--backend-store-uri", f"sqlite:///{work}/mlflow.db", "--default-artifact-root", f"{work}/artifacts"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
import requests
wait_for(lambda: requests.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200, "MLflow server")
atexit.register(mlflow_proc.terminate)
print("MLflow server is up (UI on http://127.0.0.1:<port>)")
""",
            ),
            ("md", "## 2. Use it as Pecca's registry"),
            (
                "code",
                """
Path("pecca.yaml").write_text(f"version: 1\\nworkspace:\\n  name: default\\n  registry: mlflow://http/127.0.0.1:{port}\\nprojects:\\n  default: {{governance: {{extends: none}}}}\\n")
context.reset()
v1 = train_demo(rows=1500)
v2 = train_demo(rows=3000)
print("versions:", v1.version, v2.version)
""",
            ),
            (
                "code",
                LLM_REPLAY
                + """
pecca.promote("route_rfi", "shadow")
for t in texts:
    route_rfi(t)
from pecca.runtime.logging_sink import flush_all
flush_all()
print(f"logged {len(texts)} shadow calls")
""",
            ),
            ("md", "## 3. What MLflow now shows"),
            (
                "code",
                """
import mlflow
client = mlflow.MlflowClient(f"http://127.0.0.1:{port}")
exp = client.get_experiment_by_name("pecca/default/default/route_rfi")
runs = client.search_runs([exp.experiment_id], order_by=["attributes.start_time ASC"])
table = pd.DataFrame([{"run": r.data.tags.get("pecca.kind"), "version": r.data.tags.get("pecca.version", "-"),
                       "candidate": r.data.params.get("candidate", "-"), "macro_f1": r.data.metrics.get("metric"),
                       "threshold": r.data.metrics.get("threshold"), "artefacts": len(client.list_artifacts(r.info.run_id))} for r in runs])
print(f"experiment: {exp.name}")
table
""",
            ),
            (
                "code",
                """
version_run = [r for r in runs if r.data.tags.get("pecca.version") == "v2"][0]
print("v2 artefacts:", sorted(a.path for a in client.list_artifacts(version_run.info.run_id)))
state_run = [r for r in runs if r.data.tags.get("pecca.kind") == "state"][0]
print("state run artefacts:", sorted(a.path for a in client.list_artifacts(state_run.info.run_id)))
print("pyfunc model:", "ok" if not version_run.data.tags.get("pecca.pyfunc_error") else version_run.data.tags["pecca.pyfunc_error"])
state = context.get_call("route_rfi").state()
print("current state:", {"mode": state.mode, "current_version": state.current_version})
""",
            ),
            ("md", "## 4. Clean up"),
            (
                "code",
                'mlflow_proc.terminate(); mlflow_proc.wait(10)\nprint("MLflow server stopped")',
            ),
        ],
        "requests mlflow",
    )


# ---- connectors ---------------------------------------------------------------------------------
def connector_notebooks() -> None:
    nb(
        "connector_datasource",
        "Connector: data sources",
        "`DataSource` implementations read your historical LLM calls into Pecca's canonical schema. We read the same 2,000 rows from **CSV**, **Parquet**, **Postgres** and **OTel traces**.",
        True,
        [
            (
                "code",
                """
df = generate(2000)
df.to_csv("logs.csv", index=False)
df.to_parquet("logs.parquet", index=False)
COLUMNS = {"input": {"subject": "email_subject", "body": "email_body"}, "llm_output": "llm_rfi", "human_label": "human_rfi",
           "call_name": {"literal": "route_rfi"}, "timestamp": "timestamp", "request_id": "request_id"}
results = {}
for kind, path in (("csv", "logs.csv"), ("parquet", "logs.parquet")):
    ds = pecca.connect(kind, path=path, columns=COLUMNS, input_template="{subject}\\n\\n{body}")
    results[kind] = ds.rows
results
""",
            ),
            (
                "md",
                "## Postgres\nWith Docker we start a throwaway `postgres:16-alpine` container (random password, localhost only). Without Docker we use the same connector class on SQLite so the query building still runs.",
            ),
            (
                "code",
                """
import secrets as _secrets
pg = {"name": f"pecca-pg-{_secrets.token_hex(3)}", "password": _secrets.token_hex(8), "port": free_port()}
cols = ["request_id", "timestamp", "email_subject", "email_body", "llm_rfi", "human_rfi"]
rows = list(df[cols].astype(object).where(df[cols].notna(), None).itertuples(index=False, name=None))
if USE_DOCKER:
    import psycopg
    cleanup_later("docker", "rm", "-f", pg["name"])
    sh("docker", "run", "-d", "--rm", "--name", pg["name"], "-e", f"POSTGRES_PASSWORD={pg['password']}", "-p", f"127.0.0.1:{pg['port']}:5432", "postgres:16-alpine")
    dsn = f"postgresql://postgres:{pg['password']}@127.0.0.1:{pg['port']}/postgres"
    wait_for(lambda: psycopg.connect(dsn, connect_timeout=2).close() is None, "Postgres")
    with psycopg.connect(dsn) as conn:
        conn.execute("CREATE TABLE email_logs (request_id text, timestamp timestamptz, email_subject text, email_body text, llm_rfi text, human_rfi text)")
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO email_logs VALUES (%s,%s,%s,%s,%s,%s)", rows)
    ds_pg = pecca.connect("postgres", dsn=dsn, table="email_logs", columns=COLUMNS, input_template="{subject}\\n\\n{body}")
else:
    import sqlite3
    from pecca import connectors
    con = sqlite3.connect("logs.db")
    pd.DataFrame(rows, columns=cols).to_sql("email_logs", con, index=False)
    class SqlitePostgres(connectors.get("datasource", "postgres")):     # same query building, different driver
        def _execute(self, sql):
            return pd.read_sql_query(sql, con)
    ds_pg = Dataset(SqlitePostgres(table="email_logs", columns=COLUMNS).read(), COLUMNS)    # read() already returns the canonical schema
results["postgres" if USE_DOCKER else "postgres (sqlite fallback)"] = ds_pg.rows
print(results)
""",
            ),
            (
                "code",
                """
# `since` and `limit` are pushed down into SQL
from pecca import connectors
src = connectors.create("datasource", {"type": "postgres", "dsn": "unused", "table": "email_logs", "columns": COLUMNS})
print(src.build_sql(since="14d", limit=100))
if USE_DOCKER:
    sh("docker", "rm", "-f", pg["name"], check=False)
    print("Postgres container removed")
""",
            ),
            (
                "md",
                "## OTel traces\nOTLP JSON/JSONL exports (or OpenInference parquet): `gen_ai.prompt`/`gen_ai.completion` or `input.value`/`output.value` become input and output.",
            ),
            (
                "code",
                """
def span(i, attrs, name="route_rfi"):
    return {"resourceSpans": [{"scopeSpans": [{"spans": [{"traceId": f"t{i}", "spanId": f"s{i}", "name": name, "startTimeUnixNano": str(1_760_000_000_000_000_000 + i * 10**9),
        "attributes": [{"key": k, "value": {"stringValue": v}} for k, v in attrs.items()]}]}]}]}
lines = [span(i, {"gen_ai.prompt": f"email {i}", "gen_ai.completion": ["billing", "cards"][i % 2], "gen_ai.request.model": "demo-llm"}) for i in range(6)]
lines.append(span(99, {"unrelated": "x"}))         # spans without a prompt/completion are ignored
Path("traces.jsonl").write_text("\\n".join(json.dumps(x) for x in lines))
ds_otel = pecca.connect("otel-traces", path="traces.jsonl", columns={})
ds_otel.to_pandas()[["input", "llm_output", "call_name", "llm_model"]]
""",
            ),
        ],
        "psycopg[binary]",
    )

    nb(
        "connector_registry",
        "Connector: registry",
        "A registry stores model versions, call state and decision logs. The `local` registry writes files; `mlflow` writes runs to an MLflow server. The Pecca API is identical, only `workspace.registry` changes.",
        False,
        [
            (
                "code",
                """
import sys
import requests
from pecca.core.workspace import Workspace

port = free_port()
proc = subprocess.Popen([sys.executable, "-m", "mlflow", "server", "--host", "127.0.0.1", "--port", str(port),
                         "--backend-store-uri", f"sqlite:///{work}/mlflow.db", "--default-artifact-root", f"{work}/artifacts"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
wait_for(lambda: requests.get(f"http://127.0.0.1:{port}/health", timeout=2).status_code == 200, "MLflow server")
atexit.register(proc.terminate)
workspaces = {
    "local": Workspace("default", {"workspace": {"registry": "local://./.pecca"}}, Path(work) / ".pecca"),
    "mlflow": Workspace("default", {"workspace": {"registry": f"mlflow://http/127.0.0.1:{port}"}}, Path(work) / ".pecca-mlflow"),
}
for name, ws in workspaces.items():
    r = train_demo(workspace=ws)
    pecca.promote("route_rfi", "shadow", workspace=ws)
    print(f"{name:<7} trained {r.version}: {r.winner}, macro_f1 {r.metric:.2f}")
""",
            ),
            (
                "code",
                """
call = {name: context.get_call("route_rfi", ws) for name, ws in workspaces.items()}
pd.DataFrame({name: {"versions": [m.version for m in c.versions()], "mode": c.state().mode, "current_version": c.state().current_version,
                     "registry class": type(c.registry).__name__} for name, c in call.items()})
""",
            ),
            (
                "code",
                """
# The same prediction from either registry
x = {"route_rfi": "Card lost\\n\\nI lost my debit card ending ****1234, please block it."}
{name: pecca.predict("route_rfi", list(x.values()), workspace=ws)[0].label for name, ws in workspaces.items()}
""",
            ),
            ("code", 'proc.terminate(); proc.wait(10)\nprint("MLflow server stopped")'),
        ],
        "requests mlflow",
    )

    nb(
        "connector_notifier",
        "Connector: notifiers",
        "Notifiers push events (`trained`, `shadow`, `ready_for_approval`, `live`, `drift`) to chat. All HTTP here is **mocked** with `respx`, so we can show exactly what each notifier would send.",
        False,
        [
            (
                "code",
                """
import httpx, respx
from pecca import connectors
from pecca.templates_util import render

payload = {"call": "prod/autoresponse/route_rfi", "event": "ready_for_approval", "version": "v3", "message": "ticket MRM-7"}
text = render("slack_event.md.j2", **payload)
print(text)
""",
            ),
            (
                "code",
                """
sent = {}
with respx.mock:
    for name, cfg in {"webhook": {"type": "webhook", "url": "https://hooks.example/generic"},
                      "slack": {"type": "slack", "webhook": "https://hooks.example/slack", "channel": "#ai-platform"},
                      "teams": {"type": "teams", "webhook": "https://hooks.example/teams"}}.items():
        route = respx.post(cfg.get("url") or cfg["webhook"]).mock(return_value=httpx.Response(200))
        connectors.create("notifier", cfg).send(payload["event"], payload, text)
        sent[name] = json.loads(route.calls[0].request.content)
for name, body in sent.items():
    print(f"--- {name}")
    print(json.dumps(body, indent=2)[:700])
""",
            ),
            (
                "md",
                "In a project, configure one under `integrations.notifier`; `events:` filters which events are sent, and a failing notifier never affects the pipeline.",
            ),
            (
                "code",
                '''
Path("pecca.yaml").write_text("""version: 1
projects:
  default:
    governance: {extends: none}
    integrations:
      notifier: {type: slack, webhook: "https://hooks.example/slack", channel: "#ai-platform", events: [trained, shadow, live]}
""")
context.reset()
with respx.mock:
    route = respx.post("https://hooks.example/slack").mock(return_value=httpx.Response(200))
    train_demo()
    pecca.promote("route_rfi", "shadow")
print([json.loads(c.request.content)["text"].splitlines()[0] for c in route.calls])
''',
            ),
        ],
        "respx",
    )

    nb(
        "connector_ticketer",
        "Connector: ticketers and the approval loop",
        "A `Ticketer` opens an approval ticket when a promotion needs sign-off and reports who approved. We run the full loop (train → shadow → `live` blocked → ticket → approval → `live`) "
        "with **manual**, **GitHub Issues** and **Jira** approvals. GitHub and Jira HTTP is mocked.",
        False,
        [
            (
                "code",
                """
import httpx, respx, yaml

def project_cfg(name, ticketer, via):
    gov = {"extends": "none", "transitions": {"shadow->live": {"gates": ["shadow_days >= 0"],
           "approvals": {"groups": ["model-risk"], "require": "all", "via": via},
           "evidence": ["model_card", "threshold_rationale"]}}}
    proj = {"governance": gov}
    if ticketer:
        proj["integrations"] = {"ticketer": ticketer}
    return proj

def configure(**projects):
    Path("pecca.yaml").write_text(yaml.safe_dump({"version": 1, "projects": projects}))
    context.reset()

def show(dec):
    return {"allowed": dec.allowed, "pending": dec.pending_approvals, "evidence missing": dec.evidence_missing}
""",
            ),
            (
                "md",
                "## Manual approvals\n`via: manual`: someone runs `pecca approve` (or `pecca.approve`) and names the group they represent.",
            ),
            (
                "code",
                """
configure(manual=project_cfg("manual", {"type": "manual"}, "manual"))
train_demo("manual/route_rfi")
pecca.promote("manual/route_rfi", "shadow")
print("blocked :", show(pecca.promote("manual/route_rfi", "live")))
pecca.approve("manual/route_rfi", "v1", approver="mrm@bank.example", groups=["model-risk"], note="reviewed")
print("approved:", show(pecca.promote("manual/route_rfi", "live")))
print("mode now:", context.get_call("manual/route_rfi").state().mode)
""",
            ),
            (
                "md",
                "## GitHub Issues\nPecca opens an issue; an approval is a `/approve` comment by a member of the group (`group_members`).",
            ),
            (
                "code",
                """
configure(gh=project_cfg("gh", {"type": "github", "repo": "bank/model-risk", "token": "test-token", "group_members": {"model-risk": ["alice"]}}, "github:bank/model-risk"))
train_demo("gh/route_rfi")
pecca.promote("gh/route_rfi", "shadow")
with respx.mock:
    issue = respx.post("https://api.github.com/repos/bank/model-risk/issues").mock(return_value=httpx.Response(201, json={"number": 41}))
    thread = [{"body": "looks fine to me", "user": {"login": "bob"}}]          # bob is not in the model-risk group
    respx.get("https://api.github.com/repos/bank/model-risk/issues/41/comments").mock(side_effect=lambda request: httpx.Response(200, json=thread))
    print("1. blocked, ticket opened:", show(pecca.promote("gh/route_rfi", "live")))
    print("   ticket:", context.get_call("gh/route_rfi").state().tickets, "| issue title:", json.loads(issue.calls[0].request.content)["title"])
    print("2. bob commented only   :", show(pecca.promote("gh/route_rfi", "live")))
    thread.append({"body": "/approve", "user": {"login": "alice"}})              # alice is in model-risk
    print("3. alice: /approve      :", show(pecca.promote("gh/route_rfi", "live")))
print("mode now:", context.get_call("gh/route_rfi").state().mode)
""",
            ),
            (
                "md",
                "## Jira\nAn approval is a status transition to `approved_when.status` (the changelog author is the approver).",
            ),
            (
                "code",
                """
configure(jira=project_cfg("jira", {"type": "jira", "url": "https://bank.atlassian.example", "project": "MRM", "email": "pecca@bank.example", "token": "test-token",
                                    "approved_when": {"status": "Approved"}, "group_members": {"model-risk": ["mrm@bank.example"]}}, "jira:MRM"))
train_demo("jira/route_rfi")
pecca.promote("jira/route_rfi", "shadow")
histories = [{"author": {"emailAddress": "dev@bank.example"}, "created": "2026-10-05", "items": [{"field": "status", "toString": "In Review"}]}]
with respx.mock:
    respx.post("https://bank.atlassian.example/rest/api/3/issue").mock(return_value=httpx.Response(201, json={"key": "MRM-7"}))
    respx.get(url__regex=r".*/issue/MRM-7\\?expand=changelog.*").mock(side_effect=lambda request: httpx.Response(200, json={"changelog": {"histories": histories}}))
    print("1. blocked, ticket opened:", show(pecca.promote("jira/route_rfi", "live")))
    print("   ticket:", context.get_call("jira/route_rfi").state().tickets)
    print("2. moved to In Review   :", show(pecca.promote("jira/route_rfi", "live")))
    histories.append({"author": {"emailAddress": "mrm@bank.example"}, "created": "2026-10-06", "items": [{"field": "status", "toString": "Approved"}]})
    print("3. mrm@ set to Approved :", show(pecca.promote("jira/route_rfi", "live")))
print("mode now:", context.get_call("jira/route_rfi").state().mode)
""",
            ),
        ],
        "respx pyyaml",
    )

    nb(
        "connector_scheduler",
        "Connector: schedulers",
        "Policies such as `train_every: 7d` and `revalidate: {every: 365d}` are evaluated by `pecca scheduler run`. A `Scheduler` connector registers that command with cron, Airflow or Databricks Workflows.",
        False,
        [
            (
                "code",
                """
from pecca import connectors
cron = connectors.create("scheduler", {"type": "cron", "path": "jobs.json"})
cron.register_job("pecca-tick", "1d", ["pecca", "scheduler", "run", "--once"])
cron.register_job("pecca-weekly", "7d", ["pecca", "scheduler", "run", "--once"])
cron.list_jobs()
""",
            ),
            ("md", "## Make a call due and run one tick"),
            (
                "code",
                """
import yaml
logs = generate(3000)
logs.to_csv("logs.csv", index=False)                       # the call's history: a retrain reads it from the project's datasource
Path("pecca.yaml").write_text(yaml.safe_dump({"version": 1, "projects": {"default": {
    "datasource": {"type": "csv", "path": "logs.csv", "columns": {"input": {"subject": "email_subject", "body": "email_body"}, "llm_output": "llm_rfi",
                                                              "human_label": "human_rfi", "call_name": {"literal": "route_rfi"}},
                   "input_template": "{subject}\\n\\n{body}"},
    "governance": {"extends": "default"}, "calls": {"route_rfi": {"policy": {"train_every": "7d", "candidates": ["tfidf_linear"]}}}}}}))   # scheduled retrains skip the slow models (e.g. xlmr_finetune)
context.reset()
print(pecca.train("route_rfi", candidates=["tfidf_linear"]).version)
from pecca.governance import schedule
from pecca.core.timeutil import iso, now
from datetime import timedelta
call = context.get_call("route_rfi")
print("next dates:", {k: v.date().isoformat() for k, v in schedule.next_dates(call).items()})
st = call.state(); st.last_trained = iso(now() - timedelta(days=8)); call.save_state(st)     # pretend it was trained 8 days ago
print("due now:", schedule.due_items(call, now()))
""",
            ),
            ("code", "!pecca scheduler run --once"),
            (
                "code",
                'print("versions after the tick:", [m.version for m in context.get_call("route_rfi").versions()])',
            ),
            (
                "md",
                "## Airflow and Databricks Workflows\nThe Airflow connector writes a DAG file per job (and exposes a lazy `PeccaOperator`); Databricks Workflows writes job JSON.",
            ),
            (
                "code",
                """
af = connectors.create("scheduler", {"type": "airflow", "dags_dir": "dags"})
af.register_job("route_rfi", "7d", ["pecca", "scheduler", "run", "--once"])
print(Path("dags/pecca_route_rfi.py").read_text())
dbx = connectors.create("scheduler", {"type": "databricks_workflows", "out_dir": "dbx_jobs", "cluster_id": "0000-demo-cluster"})
dbx.register_job("route_rfi", "7d", ["pecca", "scheduler", "run", "--once"])
print(json.dumps(dbx.list_jobs()[0], indent=2))
""",
            ),
        ],
    )

    nb(
        "connector_serving",
        "Connector: serving targets",
        "`onnx_local` serves in-process (what `@pecca.replace` uses); `docker_export` writes a folder you can build into a container; `databricks_serving` creates a Model Serving endpoint. "
        "This notebook benchmarks local serving and shows the Docker export. It uses the tiny hashing embedder (`PECCA_TEST_SMALL=1`) so nothing is downloaded.",
        False,
        [
            (
                "code",
                """
os.environ["PECCA_TEST_SMALL"] = "1"
r1 = train_demo(candidates=("tfidf_linear",))
r2 = train_demo(candidates=("e5_logreg",))
call = context.get_call("route_rfi")
print({m.version: (m.candidate, m.format) for m in call.versions()})
""",
            ),
            ("md", "## Latency of in-process serving (single-row predictions on CPU)"),
            (
                "code",
                """
import numpy as np
texts = (generate(200, seed=3).email_subject + "\\n\\n" + generate(200, seed=3).email_body).tolist()
from pecca.runtime.predictor import get_predictor
bench = {}
for version in ("v1", "v2"):
    p = get_predictor(call, version)
    p.predict(texts[:1])                                   # warm-up / lazy load
    times = []
    for t in texts:
        t0 = time.perf_counter(); p.predict([t]); times.append((time.perf_counter() - t0) * 1000)
    m = call.version(version)
    bench[f"{version} {m.candidate} ({m.format})"] = {"median ms": round(float(np.median(times)), 2), "p95 ms": round(float(np.percentile(times, 95)), 2)}
pd.DataFrame(bench).T
""",
            ),
            (
                "md",
                "## docker_export\nWrites a Dockerfile, a FastAPI `/predict` app, `requirements.txt` and the model for one version.",
            ),
            (
                "code",
                """
from pecca import connectors
export = connectors.create("serving", {"type": "docker_export", "out_dir": "export", "home": os.environ["PECCA_HOME"]})
folder = Path(export.deploy(call.key, "v2"))
print(sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file()))
print((folder / "Dockerfile").read_text())
print((folder / "requirements.txt").read_text())
""",
            ),
            (
                "code",
                """
print((folder / "app.py").read_text())
print("# build and run it (skipped here: the image installs torch via pecca, which is large):")
print(f"docker build -t pecca-route-rfi {folder.name} && docker run -p 8000:8000 pecca-route-rfi")
print('curl -s localhost:8000/predict -H "content-type: application/json" -d \\'{"inputs": ["Card lost\\\\n\\\\nplease block my card"]}\\'')
""",
            ),
        ],
    )

    nb(
        "connector_secrets",
        "Connector: secrets",
        "Config values like `${JIRA_TOKEN}` are resolved at use time through a `Secrets` connector: environment variables, **HashiCorp Vault**, or **AWS Secrets Manager**. "
        "Resolved values are never written to `.pecca/config.resolved.yaml`. Secret values are masked in this notebook.",
        True,
        [
            (
                "code",
                """
import yaml
from pecca.config.apply import apply as apply_config

mask = lambda v: v[:2] + "*" * (len(v) - 2) if v else v
def write_config(secrets_cfg):
    Path("pecca.yaml").write_text(yaml.safe_dump({"version": 1, "workspace": {"name": "default", "secrets": secrets_cfg}, "projects": {"default": {
        "governance": {"extends": "none"},
        "integrations": {"notifier": {"type": "slack", "webhook": "${SLACK_WEBHOOK}"}}}}}))
    context.reset()
""",
            ),
            ("md", "## 1. Environment variables (default)"),
            (
                "code",
                """
os.environ["SLACK_WEBHOOK"] = "https://hooks.example/env-secret"
write_config({"provider": "env"})
diff, resolved = apply_config("pecca.yaml")
stored = Path(os.environ["PECCA_HOME"], "config.resolved.yaml").read_text()
print("placeholder kept on disk:", "${SLACK_WEBHOOK}" in stored, "| value on disk:", "env-secret" in stored)
del os.environ["SLACK_WEBHOOK"]
try:
    apply_config("pecca.yaml")
except pecca.core.errors.PeccaError as e:
    print("unresolved ->", e.message)
""",
            ),
            (
                "md",
                "## 2. HashiCorp Vault (dev server in Docker)\nA throwaway `hashicorp/vault` container in dev mode with a random root token, bound to localhost.",
            ),
            (
                "code",
                """
import secrets as _secrets
vault = {"name": f"pecca-vault-{_secrets.token_hex(3)}", "token": _secrets.token_hex(12), "port": free_port()}
if USE_DOCKER:
    import requests
    cleanup_later("docker", "rm", "-f", vault["name"])
    sh("docker", "run", "-d", "--rm", "--cap-add=IPC_LOCK", "--name", vault["name"], "-p", f"127.0.0.1:{vault['port']}:8200",
       "-e", f"VAULT_DEV_ROOT_TOKEN_ID={vault['token']}", "-e", "VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200", "hashicorp/vault:1.18")
    base = f"http://127.0.0.1:{vault['port']}"
    wait_for(lambda: requests.get(f"{base}/v1/sys/health", timeout=2).status_code == 200, "Vault")
    requests.post(f"{base}/v1/secret/data/pecca", headers={"X-Vault-Token": vault["token"]},
                  json={"data": {"SLACK_WEBHOOK": "https://hooks.example/vault-secret"}}).raise_for_status()
    write_config({"provider": "vault", "url": base, "token": vault["token"], "path": "pecca", "mount": "secret"})
    diff, resolved = apply_config("pecca.yaml")
    value = context.get_workspace().secrets.get("SLACK_WEBHOOK")
    print("resolved from Vault:", mask(value))
    print("value on disk:", "vault-secret" in Path(os.environ["PECCA_HOME"], "config.resolved.yaml").read_text())
    sh("docker", "rm", "-f", vault["name"], check=False)
    print("Vault container removed")
else:
    print("skipped: needs Docker (the connector call is `secrets: {provider: vault, url, token, path, mount}`).")
""",
            ),
            ("md", "## 3. AWS Secrets Manager (mocked with moto)"),
            (
                "code",
                """
import boto3
from moto import mock_aws

for k, v in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_DEFAULT_REGION": "eu-west-1"}.items():
    os.environ[k] = v
with mock_aws():
    boto3.client("secretsmanager").create_secret(Name="pecca/SLACK_WEBHOOK", SecretString="https://hooks.example/aws-secret")
    write_config({"provider": "aws-secrets-manager", "region": "eu-west-1", "prefix": "pecca/"})
    apply_config("pecca.yaml")
    print("resolved from AWS Secrets Manager (mock):", mask(context.get_workspace().secrets.get("SLACK_WEBHOOK")))
""",
            ),
        ],
        "hvac boto3 moto pyyaml requests",
    )

    nb(
        "connector_docs_publisher",
        "Connector: docs publishers",
        "A `DocsPublisher` ships the audit pack where your reviewers read: a Markdown folder, or a Confluence page. Confluence HTTP is **mocked** with `respx`.",
        False,
        [
            (
                "code",
                """
import httpx, respx, yaml

def configure(docs):
    Path("pecca.yaml").write_text(yaml.safe_dump({"version": 1, "projects": {"default": {"governance": {"extends": "none"}, "integrations": {"docs": docs}}}}))
    context.reset()
train_demo(); print("model trained")
""",
            ),
            ("md", "## Markdown folder"),
            (
                "code",
                """
configure({"type": "markdown", "dir": "published"})
location = pecca.audit_pack("route_rfi", out="confluence")      # `confluence` = "send to the configured docs publisher"
print(Path(location).name, "|", len(Path(location).read_text().splitlines()), "lines")
""",
            ),
            (
                "md",
                "## Confluence (mocked)\nThe publisher looks up the page by title under `parent_page_id`; it creates it the first time and updates (version + 1) afterwards.",
            ),
            (
                "code",
                """
configure({"type": "confluence", "url": "https://wiki.bank.example", "space": "AI", "parent_page_id": "123", "email": "pecca@bank.example", "token": "test-token"})
with respx.mock:
    respx.get("https://wiki.bank.example/rest/api/content").mock(side_effect=[
        httpx.Response(200, json={"results": []}),
        httpx.Response(200, json={"results": [{"id": "900", "version": {"number": 1}}]})])
    create = respx.post("https://wiki.bank.example/rest/api/content").mock(return_value=httpx.Response(200, json={"id": "900", "_links": {"webui": "/spaces/AI/pages/900"}}))
    update = respx.put("https://wiki.bank.example/rest/api/content/900").mock(return_value=httpx.Response(200, json={"id": "900", "_links": {"webui": "/spaces/AI/pages/900"}}))
    first = pecca.audit_pack("route_rfi", out="confluence")
    second = pecca.audit_pack("route_rfi", out="confluence")
body = json.loads(create.calls[0].request.content)
print("page:", first)
print("created:", body["title"], "| parent:", body["ancestors"], "| representation:", body["body"]["storage"]["representation"])
print("updated: version", json.loads(update.calls[0].request.content)["version"]["number"], "| same page:", first == second)
""",
            ),
        ],
        "respx pyyaml",
    )


def main() -> None:
    monitoring_notebooks()
    connector_notebooks()
    print("wrote 11 docker-era notebooks")


if __name__ == "__main__":
    main()
