"""profile, train, promote, approve, audit, eval, diff, logs, status."""

from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

import pecca
from pecca.cli.common import console, handle
from pecca.core import context
from pecca.core.errors import PeccaError
from pecca.core.models import ModelVersion


def _fmt(x: float | None, d: int = 2) -> str:
    return "-" if x is None else f"{x:.{d}f}"


def _call_exists(path: str) -> bool:
    try:
        c = context.get_call(path)
        return c.has_state() or bool(c.versions())
    except PeccaError:
        return False


@handle
def profile(
    path: str = typer.Argument(
        None, help="workspace/project/call (default: every call in the project datasource)"
    ),
    project: str = typer.Option("default", "--project"),
    min_rows: int = typer.Option(500, "--min-rows"),
) -> None:
    """Table of CallProfiles."""
    from pecca.api import load_dataset
    from pecca.profiler import profile_dataset

    if path:
        call = context.get_call(path)
        rep = profile_dataset(load_dataset(call), call.name, min_rows)
    else:
        proj = context.get_project(None, project)
        ds = proj.datasource()
        if ds is None:
            raise PeccaError(
                "no datasource configured", "add projects.<name>.datasource to pecca.yaml"
            )
        from pecca.data.dataset import Dataset

        rep = profile_dataset(
            Dataset(ds.read(), getattr(ds, "columns", {}), getattr(ds, "input_template", None)),
            None,
            min_rows,
        )
    t = Table(show_header=True, header_style="bold")
    for col in ("call", "task", "classes", "rows", "languages", "replaceable"):
        t.add_column(col)
    for p in rep.profiles.values():
        t.add_row(
            p.call,
            p.task_type,
            f"{len(p.labels)} labels" if p.labels else "—",
            f"{p.n_rows:,} rows",
            ",".join(p.languages) or "—",
            "✔" if p.replaceable else f"✘ {p.reason or ''}",
        )
    console.print(t)


@handle
def train(
    path: str = typer.Argument(...),
    metric: str = typer.Option(None, "--metric"),
    latency_budget_ms: float = typer.Option(None, "--latency-budget-ms"),
    candidates: str = typer.Option(
        None,
        "--candidates",
        help="Comma-separated override, e.g. tfidf_linear,e5_logreg (skips slow xlmr_finetune on CPU)",
    ),
) -> None:
    """Run the tournament and print the leaderboard."""
    c = context.get_call(path)
    console.print(f"training {c.path} ...", markup=False)
    res = pecca.train(
        path,
        metric=metric,
        latency_budget_ms=latency_budget_ms,
        candidates=[c.strip() for c in candidates.split(",")] if candidates else None,
        progress=lambda m: console.print(m, markup=False),
    )
    t = Table(show_header=True, header_style="bold")
    for col in ("candidate", res.metric_name, "std", "fit s", "latency ms"):
        t.add_column(col)
    for e in res.leaderboard:
        if e["status"] != "ok":
            t.add_row(e["candidate"], "failed", "", "", e.get("error", "")[:40])
            continue
        win = e.get("winner")
        name = f"★ {e['candidate']}" if win else e["candidate"]
        t.add_row(
            name,
            f"{e['metric']:.3f}",
            f"{e['metric_std']:.3f}",
            f"{e['fit_time_s']:.1f}",
            f"{e['predict_latency_ms']:.1f}",
            style="bold green" if win else None,
        )
    console.print(t)
    llm = (
        f"vs llm {res.llm_metric:.2f}"
        if res.llm_metric is not None
        else "(no human labels: matches the LLM, not compared)"
    )
    console.print(f"winner {res.winner}  {res.metric_name} {res.metric:.2f} {llm}", markup=False)
    if res.threshold is not None:
        console.print(
            f"threshold {res.threshold:.2f}  expected fallback {100 * (res.expected_fallback_rate or 0):.0f}%",
            markup=False,
        )
    console.print(f"saved {res.version} → {res.model_path}", markup=False)


@handle
def promote(
    path: str = typer.Argument(...),
    mode: str = typer.Option(..., "--mode", help="off | record | shadow | live"),
    force: bool = typer.Option(
        False, "--force", help="Override gates (requires PECCA_ALLOW_FORCE=1)"
    ),
) -> None:
    """Governance-gated mode change. Prints the Decision."""
    dec = pecca.promote(path, mode, force=force)
    if dec.allowed or dec.forced:
        since = "now" if mode in ("shadow", "live") else ""
        console.print(
            f"{mode} since {since}".strip() + ("  (forced)" if dec.forced else ""), markup=False
        )
        return
    console.print(f"blocked: {dec.transition}", markup=False)
    for g in dec.failing_gates:
        console.print(f"  gate failing: {g}", markup=False)
    for a in dec.pending_approvals:
        console.print(f"  approval pending: {a}", markup=False)
    for e in dec.evidence_missing:
        console.print(f"  evidence missing: {e}", markup=False)
    raise typer.Exit(1)


@handle
def approve(
    path: str = typer.Argument(...),
    version: str = typer.Option(..., "--version"),
    approver: str = typer.Option(..., "--approver", help="Approver email"),
    ticket: str = typer.Option(None, "--ticket"),
    note: str = typer.Option(None, "--note"),
    group: list[str] = typer.Option(
        None, "--group", help="Group(s) the approver represents (repeatable)"
    ),
) -> None:
    """Record a manual approval."""
    pecca.approve(
        path,
        version,
        approver=approver,
        ticket=ticket,
        note=note,
        groups=list(group) if group else None,
    )
    console.print(f"approved {version} by {approver}", markup=False)


@handle
def audit(
    path: str = typer.Argument(...),
    version: str = typer.Option(None, "--version"),
    out: str = typer.Option(
        "markdown", "--out", help="markdown | json | confluence | pdf (pdf is untested)"
    ),
    dest: str = typer.Option(None, "--path"),
) -> None:
    """Generate the audit pack."""
    console.print(
        pecca.audit_pack(path, version, out=out, path=dest), markup=False, highlight=False
    )


@handle
def eval_(path: str = typer.Argument(...), since: str = typer.Option("14d", "--since")) -> None:
    """Agreement, fallback rate and drift over a window."""
    r = pecca.evaluate(path, since)
    t = Table(show_header=True, header_style="bold")
    t.add_column("metric")
    t.add_column("value")
    t.add_row("window", r.window)
    t.add_row("calls", f"{r.n_rows:,}")
    t.add_row("agreement", _fmt(r.agreement_rate))
    t.add_row("fallback", _fmt(r.fallback_rate))
    t.add_row("drift", _fmt(r.drift_score, 3))
    t.add_row("disagreements", str(len(r.disagreements)))
    console.print(t)


def _f1(mv: ModelVersion) -> dict[str, float]:
    return {k: v["f1"] for k, v in mv.per_class.items()}


@handle
def diff(
    path: str = typer.Argument(...), a: str = typer.Argument(...), b: str = typer.Argument(...)
) -> None:
    """Side-by-side comparison of two versions."""
    c = context.get_call(path)
    va, vb = c.version(a), c.version(b)
    t = Table(show_header=True, header_style="bold")
    for col in ("", va.version, vb.version):
        t.add_column(col)
    rows: list[tuple[str, Any, Any]] = [
        ("model", va.candidate, vb.candidate),
        (va.metric_name, _fmt(va.metric, 3), _fmt(vb.metric, 3)),
        ("llm metric", _fmt(va.llm_metric, 3), _fmt(vb.llm_metric, 3)),
        ("threshold", _fmt(va.threshold), _fmt(vb.threshold)),
        ("expected fallback", _fmt(va.expected_fallback_rate), _fmt(vb.expected_fallback_rate)),
        ("rows", f"{va.lineage.get('rows', 0):,}", f"{vb.lineage.get('rows', 0):,}"),
        (
            "date range",
            " → ".join(str(x)[:10] for x in va.lineage.get("date_range", ["-", "-"])),
            " → ".join(str(x)[:10] for x in vb.lineage.get("date_range", ["-", "-"])),
        ),
    ]
    for r in rows:
        t.add_row(*[str(x) for x in r])
    console.print(t)
    fa, fb = _f1(va), _f1(vb)
    deltas = sorted(
        ((k, fb.get(k, 0.0) - fa.get(k, 0.0)) for k in set(fa) | set(fb)),
        key=lambda kv: -abs(kv[1]),
    )[:20]
    d = Table(title="per-class F1 deltas (top 20)", show_header=True, header_style="bold")
    for col in ("class", va.version, vb.version, "delta"):
        d.add_column(col)
    for k, dv in deltas:
        d.add_row(k, _fmt(fa.get(k), 2), _fmt(fb.get(k), 2), f"{dv:+.2f}")
    console.print(d)


@handle
def logs(
    path: str = typer.Argument(...),
    since: str = typer.Option("1d", "--since"),
    disagreements: bool = typer.Option(False, "--disagreements"),
    fallbacks: bool = typer.Option(False, "--fallbacks"),
    limit: int = typer.Option(20, "--limit"),
) -> None:
    """Tail decision logs."""
    c = context.get_call(path)
    df = c.registry.read_logs(c.key, since)
    if df.empty:
        console.print("no logs", markup=False)
        return
    if disagreements and "agreement" in df:
        df = df[df["agreement"] == False]  # noqa: E712
    if fallbacks and "served_by" in df:
        df = df[df["served_by"] == "fallback"]
    t = Table(show_header=True, header_style="bold")
    for col in ("ts", "mode", "served_by", "llm_output", "model_output", "conf", "agree"):
        t.add_column(col)
    for _, r in df.tail(limit).iterrows():
        conf = r.get("confidence")
        t.add_row(
            str(r.get("ts", ""))[:19],
            str(r.get("mode", "")),
            str(r.get("served_by", "")),
            str(r.get("llm_output", "")),
            str(r.get("model_output", "")),
            "-" if conf is None or conf != conf else f"{conf:.2f}",
            str(r.get("agreement", "")),
        )
    console.print(t)


def _d(s: str | None) -> str:
    return (s or "-")[:10]


def render_status(call: Any) -> str:
    from pecca.governance import schedule

    st = call.state()
    lines: list[tuple[str, str, str]] = []
    mv = call.version() if call.versions() else None
    lines.append(("call", str(call.path), ""))
    lines.append(("mode", st.mode, f"since {_d(st.since)}"))
    if mv:
        lines.append(
            (
                "version",
                mv.version,
                f"trained {_d(mv.trained_at)} on {mv.lineage.get('rows', 0):,} rows",
            )
        )
        lines.append(
            (
                "model",
                mv.candidate,
                f"{mv.metric_name} {mv.metric:.2f}  (llm {_fmt(mv.llm_metric)})",
            )
        )
        fb = "-" if mv.expected_fallback_rate is None else f"{100 * mv.expected_fallback_rate:.0f}%"
        lines.append(("threshold", _fmt(mv.threshold), f"expected fallback {fb}"))
    from pecca.evaluation import evaluate_call

    rep = evaluate_call(call, "14d")
    fbr = "-" if rep.fallback_rate is None else f"{100 * rep.fallback_rate:.0f}%"
    lines.append(
        (
            "agreement",
            f"{_fmt(rep.agreement_rate)} (14d)",
            f"fallback {fbr}   drift {_fmt(rep.drift_score)}",
        )
    )
    tr = call.project.governance.get("transitions") or {}

    def gates(t: str) -> str:
        g = (tr.get(t) or {}).get("gates", [])
        return " & ".join(x.replace(" ", "") for x in g) or "-"

    lines.append(
        ("policy", f"shadow_at {gates('record->shadow')}", f"live_at {gates('shadow->live')}")
    )
    nxt = schedule.next_dates(call)
    lines.append(
        (
            "next",
            "   ".join(f"{k.replace('drift_review', 'drift')} {v.date()}" for k, v in nxt.items())
            or "-",
            "",
        )
    )
    out = []
    for key, a, b in lines:
        if key == "policy":
            out.append(f"{key:<11}{a}  {b}")
        elif key in ("call", "next"):
            out.append(f"{key:<11}{a}")
        else:
            out.append(f"{key:<11}{a:<16}{b}".rstrip())
    return "\n".join(out)


@handle
def status(path: str = typer.Argument(None)) -> None:
    """Workspace, project or call view."""
    ws = context.get_workspace()
    if path and path.count("/") == 2 or (path and _call_exists(path)):
        console.print(render_status(context.get_call(path)), markup=False, highlight=False)
        return
    projects = [path.split("/")[-1]] if path else (list(ws.projects) or ["default"])
    t = Table(show_header=True, header_style="bold")
    for col in ("call", "rows", "metric", "mode", "agreement", "fallback", "version"):
        t.add_column(col)
    from pecca.evaluation import evaluate_call

    for pname in projects:
        names = set(ws.registry.list_calls(f"pecca/{ws.name}/{pname}")) | set(
            ws.project(pname).config.get("calls") or {}
        )
        for cname in sorted(names):
            c = context.get_call(f"{ws.name}/{pname}/{cname}", ws)
            st = c.state()
            mv = c.version() if c.versions() else None
            rep = evaluate_call(c, "14d")
            t.add_row(
                f"{pname}/{cname}",
                f"{mv.lineage.get('rows', 0):,}" if mv else "-",
                f"{mv.metric:.2f}" if mv else "-",
                st.mode,
                _fmt(rep.agreement_rate),
                "-" if rep.fallback_rate is None else f"{100 * rep.fallback_rate:.0f}%",
                mv.version if mv else "-",
            )
    console.print(t)
