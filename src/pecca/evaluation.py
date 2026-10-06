"""Evaluate shadow/live logs: agreement, fallback rate, disagreements and drift."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from scipy.spatial.distance import jensenshannon

from pecca.core.call import Call
from pecca.core.models import EvalReport
from pecca.core.timeutil import from_iso, now
from pecca.data.dataset import normalise_output

MAX_DISAGREEMENTS = 200


def _window_logs(call: Call, since: str) -> pd.DataFrame:
    df = call.registry.read_logs(call.key, since)
    return df if not df.empty else pd.DataFrame()


def js_distance(window: dict[str, int], train: dict[str, int]) -> float | None:
    keys = sorted(set(window) | set(train))
    if not keys or not window or not train:
        return None
    p = np.array([window.get(k, 0) for k in keys], float)
    q = np.array([train.get(k, 0) for k in keys], float)
    if p.sum() == 0 or q.sum() == 0:
        return None
    return float(jensenshannon(p / p.sum(), q / q.sum(), base=2))


def evaluate_call(call: Call, since: str = "14d") -> EvalReport:
    df = _window_logs(call, since)
    if df.empty or "mode" not in df:
        return EvalReport(None, None, 0, [], None, {}, since)
    df = df[df["mode"].isin(["shadow", "live"])]
    n = len(df)
    if n == 0:
        return EvalReport(None, None, 0, [], None, {}, since)
    sh = df[df["mode"] == "shadow"]
    shadow_ag = sh["agreement"].dropna() if "agreement" in sh else pd.Series(dtype=float)
    agreement = float(shadow_ag.astype(float).mean()) if len(shadow_ag) else None

    thr = None
    try:
        thr = call.version().threshold
    except Exception:  # noqa: BLE001
        pass
    live = df[df["mode"] == "live"]
    fb: float | None = None
    if len(live):
        fb = float((live["served_by"] == "fallback").mean())
    elif thr is not None and "confidence" in sh and sh["confidence"].notna().any():
        fb = float((sh["confidence"].dropna() < thr).mean())

    dis = []
    if "agreement" in sh:
        for _, r in sh[sh["agreement"] == False].head(MAX_DISAGREEMENTS).iterrows():  # noqa: E712
            dis.append({k: (None if pd.isna(r.get(k)) else r.get(k))
                        for k in ("ts", "input", "llm_output", "model_output", "confidence")})
    per_class: dict[str, float] = {}
    if "agreement" in sh and len(shadow_ag):
        tmp = sh.dropna(subset=["agreement"]).copy()
        tmp["cls"] = tmp["llm_output"].map(normalise_output)
        per_class = {str(k): float(v) for k, v in tmp.groupby("cls")["agreement"].apply(lambda s: s.astype(float).mean()).items()}

    drift = None
    try:
        counts = call.version().lineage.get("label_counts") or {}
        resolved = [normalise_output(a if a is not None and a == a else b)
                    for a, b in zip(df.get("llm_output", [None] * n), df.get("model_output", [None] * n), strict=True)]
        drift = js_distance(dict(Counter(resolved)), counts)
    except Exception:  # noqa: BLE001
        pass
    return EvalReport(agreement, fb, n, dis, drift, per_class, since)


def shadow_days(call: Call) -> float | None:
    st = call.state()
    if st.shadow_since:
        return (now() - from_iso(st.shadow_since)).total_seconds() / 86400
    df = call.registry.read_logs(call.key, "3650d")
    if df.empty or "mode" not in df:
        return None
    sh = df[df["mode"] == "shadow"]
    if sh.empty:
        return None
    first = pd.to_datetime(sh["ts"], utc=True, format="ISO8601").min()
    return float((pd.Timestamp(now()) - first).total_seconds() / 86400)


def variables(call: Call, since: str = "14d") -> dict[str, Any]:
    """Values available to governance gates (``None`` = no data yet)."""
    v: dict[str, Any] = dict.fromkeys(
        ["cv_metric", "cv_f1", "rows", "agreement", "shadow_days", "fallback_rate", "drift",
         "llm_metric", "min_class_count"])
    try:
        mv = call.version()
        v.update(cv_metric=mv.metric, rows=mv.lineage.get("rows"), llm_metric=mv.llm_metric,
                 min_class_count=mv.min_class_count)
        v["cv_f1"] = mv.metric if mv.metric_name == "macro_f1" else None
    except Exception:  # noqa: BLE001
        pass
    rep = evaluate_call(call, since)
    v.update(agreement=rep.agreement_rate, fallback_rate=rep.fallback_rate, drift=rep.drift_score,
             shadow_days=shadow_days(call))
    return v
