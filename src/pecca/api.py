"""Public API. Every function is re-exported from ``pecca``."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from typing import Any

import pandas as pd

from pecca import audit as _audit
from pecca import connectors
from pecca import governance as _gov
from pecca.candidates import register as register  # noqa: PLC0414
from pecca.core import context
from pecca.core.call import Call, check_transition
from pecca.core.errors import GovernanceError, PeccaError
from pecca.core.models import CallProfile, Decision, EvalReport, Prediction, TrainResult
from pecca.core.project import Project
from pecca.core.timeutil import iso
from pecca.core.workspace import Workspace
from pecca.data.dataset import Dataset, canonicalize
from pecca.data.labels import join_labels
from pecca.evaluation import evaluate_call
from pecca.profiler import ProfileReport, profile_dataset
from pecca.runtime.decorator import replace as replace  # noqa: PLC0414
from pecca.runtime.predictor import Bundle, get_predictor
from pecca.templates_util import render
from pecca.trainer.tournament import run_tournament

WS = str | Workspace | None
PR = str | Project | None


def _call(call: str, workspace: WS, project: PR) -> Call:
    return context.get_call(call, workspace, project)


# ---- data ---------------------------------------------------------------------------------
def connect(
    source: str | dict[str, Any],
    *,
    table: str | None = None,
    path: str | None = None,
    columns: dict[str, Any],
    input_template: str | None = None,
    **kwargs: Any,
) -> Dataset:
    """Read a data source into the canonical schema (spec §5.1)."""
    cfg: dict[str, Any] = dict(source) if isinstance(source, dict) else {"type": source}
    cfg.setdefault("columns", columns)
    if input_template:
        cfg["input_template"] = input_template
    if table:
        cfg["table"] = table
    if path:
        cfg["path"] = path
    cfg.update(kwargs)
    ds = connectors.create("datasource", cfg)
    df = ds.read()
    return Dataset(df, cfg["columns"], cfg.get("input_template"), source=str(cfg["type"]))


def _log_dataset(call: Call, include_fallbacks: bool) -> pd.DataFrame:
    logs = call.registry.read_logs(call.key, "3650d")
    if logs.empty or "llm_output" not in logs:
        return pd.DataFrame()
    logs = logs[logs["llm_output"].notna()]
    if not include_fallbacks and "served_by" in logs:
        logs = logs[logs["served_by"] != "fallback"]
    if logs.empty:
        return pd.DataFrame()
    raw = pd.DataFrame(
        {
            "input": logs["input"],
            "llm_output": logs["llm_output"],
            "ts": logs["ts"],
            "name": call.name,
        }
    )
    return canonicalize(
        raw, {"input": "input", "llm_output": "llm_output", "call_name": "name", "timestamp": "ts"}
    )


def load_dataset(
    call: Call, *, include_fallbacks: bool = True, include_human_labels: bool = True
) -> Dataset:
    """Configured datasource rows (+ label join) plus recorded logs for this call."""
    frames: list[pd.DataFrame] = []
    template = None
    mapping: dict[str, Any] = {}
    cfg = call.project.config
    ds = call.project.datasource()
    if ds is not None:
        df = ds.read(call=call.name)
        template = getattr(ds, "input_template", None)
        mapping = getattr(ds, "columns", {})
        lab = cfg.get("labels")
        if lab and include_human_labels:
            lconn = connectors.create(
                "datasource",
                {
                    **lab,
                    "columns": {
                        "input": lab["join_on"],
                        "llm_output": lab["column"],
                        "call_name": {"literal": call.name},
                    },
                },
            )
            ldf = lconn._read_raw(None, None)  # noqa: SLF001
            df = join_labels(df, ldf, lab["join_on"], lab["column"])
        if not include_human_labels:
            df["human_label"] = None
        if not df.empty:
            frames.append(df)
    logged = _log_dataset(call, include_fallbacks)
    if not logged.empty:
        frames.append(logged)
    if not frames:
        raise PeccaError(
            f"no data for {call.path}",
            "check the call name against `pecca connect`, pass dataset=..., or record calls with @pecca.replace",
        )
    df = pd.concat(frames, ignore_index=True)
    return Dataset(df, mapping, template, source="project")


def profile(
    dataset: Dataset | None = None,
    call: str | None = None,
    *,
    min_rows: int = 500,
    workspace: WS = None,
    project: PR = None,
) -> ProfileReport:
    """Profile each call in ``dataset`` (default: the project's configured datasource)."""
    if dataset is None:
        if call is None:
            raise PeccaError(
                "profile() needs a dataset or a call", "profile(dataset) or profile(call=...)"
            )
        dataset = load_dataset(_call(call, workspace, project))
        call = _call(call, workspace, project).name
    return profile_dataset(dataset, call, min_rows)


# ---- training -----------------------------------------------------------------------------
def train(
    call: str,
    dataset: Dataset | None = None,
    *,
    metric: str | None = None,
    latency_budget_ms: float | None = None,
    target_precision: float | None = None,
    candidates: list[str] | None = None,
    min_rows: int | None = None,
    workspace: WS = None,
    project: PR = None,
    progress: Callable[[str], None] | None = None,
    include_fallbacks: bool = True,
    include_human_labels: bool = True,
) -> TrainResult:
    c = _call(call, workspace, project)
    pol = c.project.policy(c.name)
    if dataset is None:
        dataset = load_dataset(
            c, include_fallbacks=include_fallbacks, include_human_labels=include_human_labels
        )
    mr = min_rows if min_rows is not None else int(pol.get("min_rows", 500))
    prof: CallProfile = profile_dataset(dataset, c.name, mr).profiles[c.name]
    if not prof.replaceable:
        raise PeccaError(f"{c.path} is not replaceable: {prof.reason}", "see `pecca profile`")
    version = c.next_version()
    with tempfile.TemporaryDirectory() as work:
        out = run_tournament(
            c.name,
            dataset,
            prof,
            version=version,
            workdir=work,
            metric=metric or pol.get("metric"),
            latency_budget_ms=latency_budget_ms
            if latency_budget_ms is not None
            else pol.get("latency_budget_ms"),
            target_precision=target_precision
            if target_precision is not None
            else float(pol.get("target_precision", 0.95)),
            candidates=candidates if candidates is not None else pol.get("candidates"),
            progress=progress,
        )
        mv = out.version
        path = c.registry.save_model(c.key, version, out.artefacts_dir, mv.to_dict())
    st = c.state()
    st.policy = pol
    st.last_trained = iso()
    if st.mode == "live":  # a new model must re-earn live status
        st.mode, st.shadow_since = "shadow", iso()
        c.log_event(st, "retrained_demoted_to_shadow", version=version)
    if st.mode in ("off", "record") or st.current_version is None or st.mode in ("shadow", "live"):
        st.current_version = version
    if not c.has_state():
        st.since = iso()
    c.save_state(st)
    c.notify(
        "trained",
        {"version": version, "message": f"{mv.candidate} {mv.metric_name} {mv.metric:.3f}"},
    )
    return TrainResult(
        version,
        mv.candidate,
        mv.metric_name,
        mv.metric,
        mv.metric_std,
        mv.llm_metric,
        mv.threshold,
        mv.expected_fallback_rate,
        mv.latency_ms,
        mv.leaderboard,
        path,
        mv.lineage,
    )


def retrain(
    call: str,
    *,
    include_fallbacks: bool = True,
    include_human_labels: bool = True,
    workspace: WS = None,
    project: PR = None,
    **kw: Any,
) -> TrainResult:
    return train(
        call,
        None,
        include_fallbacks=include_fallbacks,
        include_human_labels=include_human_labels,
        workspace=workspace,
        project=project,
        **kw,
    )


def predict(
    call: str, inputs: list[Any], *, workspace: WS = None, project: PR = None
) -> list[Prediction]:
    return get_predictor(_call(call, workspace, project)).predict(list(inputs))


def evaluate(
    call: str, since: str = "14d", *, workspace: WS = None, project: PR = None
) -> EvalReport:
    return evaluate_call(_call(call, workspace, project), since)


# ---- promotion & governance ---------------------------------------------------------------
def promote(
    call: str, mode: str, *, force: bool = False, workspace: WS = None, project: PR = None
) -> Decision:
    c = _call(call, workspace, project)
    st = c.state()
    src = st.mode if c.has_state() else "record"
    check_transition(src, mode)
    transition = f"{src}->{mode}"
    if src == mode:
        return Decision(True, transition=transition)
    if mode in ("shadow", "live") and not c.versions():
        raise PeccaError(f"{c.path} has no trained model", f"run `pecca train {c.path}` first")
    dec = Decision(True, transition=transition)
    if transition in _gov.engine.GATED:
        cfg = (c.project.governance.get("transitions") or {}).get(transition) or {}
        if cfg.get("evidence"):
            _audit.generate(c)
        dec = _gov.evaluate(c, transition)
        _ensure_ticket(c, transition, cfg, dec)
    if not dec.allowed:
        if not force:
            return dec
        if os.environ.get("PECCA_ALLOW_FORCE") != "1":
            raise GovernanceError(
                "--force requires PECCA_ALLOW_FORCE=1", "set it explicitly to override gates"
            )
        dec.forced = True
        st = c.state()
        c.log_event(
            st,
            "forced_promotion",
            transition=transition,
            failing_gates=dec.failing_gates,
            pending_approvals=dec.pending_approvals,
            evidence_missing=dec.evidence_missing,
        )
        c.save_state(st)
    st = c.state()
    st.mode, st.since = mode, iso()
    if mode == "shadow" and src in ("record", "off"):
        st.shadow_since = iso()
    if st.current_version is None:
        st.current_version = c.version().version
    c.log_event(st, "mode_change", frm=src, to=mode, forced=dec.forced)
    c.save_state(st)
    c.notify(mode, {"version": st.current_version})
    return dec


def _ensure_ticket(c: Call, transition: str, cfg: dict[str, Any], dec: Decision) -> None:
    ap = cfg.get("approvals") or {}
    via = str(ap.get("via", "manual"))
    st = c.state()
    mv = c.version()
    if not dec.pending_approvals or via == "manual" or mv.version in st.tickets:
        return
    ticketer = c.project.ticketer()
    if ticketer is None:
        return
    from pecca.audit.pack import build_context

    ctx = build_context(c, mv.version)
    ctx["transition"] = transition
    ctx["policy"] = {**ctx["policy"], "approvals": ap}
    body = render("approval_ticket.md.j2", **ctx)
    tid = ticketer.create(
        f"Pecca: approve {c.path} {mv.version} ({transition})",
        body,
        {"call": str(c.path), "version": mv.version},
    )
    st.tickets[mv.version] = tid
    c.save_state(st)
    c.notify("ready_for_approval", {"version": mv.version, "message": f"ticket {tid}"})


def approve(
    call: str,
    version: str,
    *,
    approver: str,
    ticket: str | None = None,
    note: str | None = None,
    groups: list[str] | None = None,
    workspace: WS = None,
    project: PR = None,
) -> dict[str, Any]:
    c = _call(call, workspace, project)
    c.version(version)  # raises if unknown
    if groups is None:
        try:
            ident = connectors.get("identity", "oidc")().current_principal()
            groups = ident["groups"] if ident.get("user") == approver else []
        except Exception:  # noqa: BLE001
            groups = []
    rec = {
        "version": version,
        "approver": approver,
        "groups": groups,
        "ticket": ticket,
        "note": note,
        "ts": iso(),
    }
    st = c.state()
    st.approvals.append(rec)
    c.log_event(st, "approval", approver=approver, version=version)
    c.save_state(st)
    return rec


def audit_pack(
    call: str,
    version: str | None = None,
    *,
    out: str = "markdown",
    path: str | None = None,
    workspace: WS = None,
    project: PR = None,
) -> str:
    return _audit.export(_call(call, workspace, project), version, out, path)


def load(path: str) -> Bundle:
    """Load a saved model directory (e.g. downloaded from Hugging Face) for local prediction."""
    return Bundle(path, "local")


# ---- agent tools --------------------------------------------------------------------------
def as_tool(
    call: str, *, project: PR = None, workspace: WS = None, description: str | None = None
) -> Callable[[str], dict[str, Any]]:
    """A plain typed callable ``f(text) -> {label, confidence, fallback, version}`` for agent frameworks."""

    def tool(text: str) -> dict[str, Any]:
        p = predict(call, [text], workspace=workspace, project=project)[0]
        return {
            "label": p.label,
            "confidence": p.confidence,
            "fallback": p.fallback,
            "version": p.version,
        }

    tool.__name__ = call.rsplit("/", 1)[-1]
    tool.__doc__ = description or (
        f"Classify text with the Pecca model for `{call}`. Returns the label, calibrated confidence, "
        "and `fallback=True` when confidence is below the threshold (ask the LLM instead)."
    )
    return tool
