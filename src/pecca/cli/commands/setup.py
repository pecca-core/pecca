"""init, apply, connect, doctor, version, datasets demo."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer

from pecca import __version__
from pecca.cli.common import console, handle
from pecca.config import apply as apply_mod
from pecca.config.resolve import profiles_dir
from pecca.core import context
from pecca.core.errors import PeccaError

YAML = """\
version: 1
workspace:
  name: default
  registry: local://./.pecca
  secrets: {{provider: env}}
projects:
  {project}:
    # datasource:
    #   type: csv
    #   path: data/demo/train.csv
    #   columns: {{input: {{subject: email_subject, body: email_body}}, llm_output: llm_rfi, human_label: human_rfi, call_name: {{literal: route_rfi}}}}
    governance:
      extends: {profile}
    calls: {{}}
"""
GITIGNORE_LINES = [".pecca/", ".env"]


@handle
def init(
    profile: str = typer.Option("default", "--profile", help="Governance profile (none, default, sr11-7, ...)"),
    project: str = typer.Option("default", "--project", help="Project name"),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing pecca.yaml"),
) -> None:
    """Create pecca.yaml, templates/, .pecca/ and .env.example."""
    from pecca.config.resolve import load_profile

    load_profile(profile)  # validates the profile name
    target = Path("pecca.yaml")
    if target.exists() and not force:
        raise PeccaError("pecca.yaml already exists", "use --force to overwrite")
    target.write_text(YAML.format(project=project, profile=profile))
    tpl_src = Path(__file__).resolve().parents[2] / "templates"
    tpl_dst = Path("templates")
    tpl_dst.mkdir(exist_ok=True)
    for f in tpl_src.rglob("*.j2"):
        dest = tpl_dst / f.relative_to(tpl_src)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or force:
            shutil.copy(f, dest)
    context.home().mkdir(parents=True, exist_ok=True)
    env_example = Path(".env.example")
    if not env_example.exists():
        src = Path(__file__).resolve().parents[4] / ".env.example"
        env_example.write_text(src.read_text() if src.exists() else "# SLACK_WEBHOOK=\n# JIRA_TOKEN=\n")
    gi = Path(".gitignore")
    existing = gi.read_text().splitlines() if gi.exists() else []
    add = [l for l in GITIGNORE_LINES if l not in existing]
    if add:
        gi.write_text("\n".join([*existing, *add]) + "\n")
    apply_mod.apply(target)
    console.print("created pecca.yaml, templates/", markup=False)


@handle
def apply(path: str = typer.Argument("pecca.yaml")) -> None:
    """Validate, resolve and store the config; print the diff vs the stored one."""
    text, _ = apply_mod.apply(path)
    console.print(text or "no changes", markup=False, highlight=False)


@handle
def connect(project: str = typer.Option("default", "--project")) -> None:
    """Test datasource connectivity and print row counts per call."""
    proj = context.get_project(None, project)
    ds = proj.datasource()
    if ds is None:
        raise PeccaError(f"project {project!r} has no datasource", "add projects.<name>.datasource to pecca.yaml")
    df = ds.read()
    counts = df["call_name"].value_counts()
    for call, n in counts.items():
        console.print(f"{call}  {n:,} rows", markup=False)
    console.print(f"total {len(df):,} rows", markup=False)


@handle
def doctor() -> None:
    """Check python, registry, secrets, OTel, ONNX runtime, long shadows and due revalidations."""
    from pecca.config.resolve import find_vars
    from pecca.core.timeutil import now
    from pecca.governance import schedule

    failures = 0

    def ok(msg: str) -> None:
        console.print(f"✔ {msg}", markup=False)

    def bad(msg: str) -> None:
        nonlocal failures
        failures += 1
        console.print(f"✘ {msg}", markup=False)

    def warn(msg: str) -> None:
        console.print(f"! {msg}", markup=False)

    if sys.version_info >= (3, 11):
        ok(f"python {sys.version.split()[0]}")
    else:
        bad("python >= 3.11 required")
    ws = context.get_workspace()
    try:
        calls = []
        for pname in ws.projects:
            calls += [(pname, c) for c in ws.registry.list_calls(f"pecca/{ws.name}/{pname}")]
        ok(f"registry reachable ({ws._registry_uri}); {len(calls)} call(s)")  # noqa: SLF001
    except Exception as e:  # noqa: BLE001
        bad(f"registry: {e}")
        calls = []
    missing = []
    for name in sorted(find_vars(ws.config)):
        try:
            ws.secrets.get(name)
        except PeccaError:
            missing.append(name)
    (bad if missing else ok)(f"secrets: unresolved {missing}" if missing else "secrets resolvable")
    try:
        import onnxruntime as ort

        ok(f"onnxruntime {ort.__version__} loads")
    except Exception as e:  # noqa: BLE001
        bad(f"onnxruntime: {e}")
    ep = (ws.telemetry or {}).get("endpoint")
    if ep:
        try:
            import httpx

            httpx.get(str(ep), timeout=3)
            ok(f"otel endpoint reachable ({ep})")
        except Exception:  # noqa: BLE001
            warn(f"otel endpoint not reachable ({ep})")
    from pecca.core.timeutil import from_iso

    for pname, c in calls:
        call = context.get_call(f"{ws.name}/{pname}/{c}", ws)
        st = call.state()
        if st.mode == "shadow" and st.shadow_since and (now() - from_iso(st.shadow_since)).days > 30:
            warn(f"{call.path} has been in shadow > 30 days")
        for item in schedule.due_items(call, now()):
            warn(f"{call.path}: {item} is due")
    if failures:
        raise typer.Exit(1)


def version() -> None:
    """Print the Pecca version."""
    console.print(__version__, markup=False)


def datasets_demo(out: str = typer.Option("./data/demo", "--out", help="Output directory")) -> None:
    """Write the synthetic Northbridge Bank demo dataset."""
    from pecca.data.synthetic import write_dataset

    df = write_dataset(out)
    console.print(f"{len(df):,} rows → {out}", markup=False)
