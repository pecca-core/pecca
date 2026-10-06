"""Train every eligible candidate on the same splits and pick the winner (spec §3.6)."""

from __future__ import annotations

import json
import statistics
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pecca.candidates import get_candidate, select_candidates
from pecca.core.errors import PeccaError
from pecca.core.models import CallProfile, ModelVersion
from pecca.core.timeutil import iso
from pecca.data.dataset import Dataset, normalise_output, resolve_labels
from pecca.trainer import metrics as M
from pecca.trainer import splits
from pecca.trainer.calibration import Calibrator, fit_calibrator
from pecca.trainer.export_onnx import export_with_parity
from pecca.trainer.lineage import build_lineage, environment, git_sha
from pecca.trainer.threshold import search_threshold

LATENCY_ROWS = 200


@dataclass
class Outcome:
    version: ModelVersion
    artefacts_dir: str


def _label_forms(df: Any, resolved: list[str]) -> dict[str, str]:
    raw: dict[str, Counter[str]] = {}
    for human, llm, norm in zip(df["human_label"], df["llm_output"], resolved, strict=True):
        v = human if (human is not None and human == human and human != "") else llm
        raw.setdefault(norm, Counter())[str(v).strip()] += 1
    return {k: c.most_common(1)[0][0] for k, c in raw.items()}


def _median_latency_ms(cand: Any, X: list[Any]) -> float:
    xs = X[:LATENCY_ROWS] or X
    cand.predict_proba(xs[:1]) if cand.classes_ else cand.predict(xs[:1])  # warm-up
    times = []
    for x in xs:
        t0 = time.perf_counter()
        cand.predict_proba([x]) if cand.classes_ else cand.predict([x])
        times.append((time.perf_counter() - t0) * 1000)
    return float(statistics.median(times))


def run_tournament(
    call: str,
    dataset: Dataset,
    profile: CallProfile,
    *,
    version: str,
    workdir: str,
    metric: str | None = None,
    latency_budget_ms: float | None = None,
    target_precision: float = 0.95,
    candidates: list[str] | None = None,
    progress: Callable[[str], None] | None = None,
) -> Outcome:
    say = progress or (lambda _m: None)
    if profile.task_type not in {"classification", "regression"}:
        raise PeccaError(
            f"{call}: {profile.task_type} calls cannot be replaced in v0.1",
            profile.reason or "",
        )
    clf = profile.task_type == "classification"
    ds = dataset.for_call(call)
    df = ds.to_pandas()
    X_all = ds.texts()
    resolved, sources = resolve_labels(df)
    keep = [i for i, l in enumerate(resolved) if l != ""]
    if clf:
        y_all: list[Any] = [resolved[i] for i in keep]
    else:
        y_all = []
        keep2 = []
        for i in keep:
            try:
                y_all.append(float(resolved[i]))
                keep2.append(i)
            except ValueError:
                continue
        keep = keep2
    X = [X_all[i] for i in keep]
    df = df.iloc[keep].reset_index(drop=True)
    sources = [sources[i] for i in keep]
    resolved = [resolved[i] for i in keep]
    metric_name = M.primary_metric(profile.task_type, metric)

    names = candidates or select_candidates(profile, latency_budget_ms)
    if not names:
        raise PeccaError(f"no eligible candidates for {call}", "check the profile with `pecca profile`")

    tr_idx, cal_idx = splits.holdout_split(y_all if clf else [0] * len(y_all), clf)
    Xtr, ytr = [X[i] for i in tr_idx], [y_all[i] for i in tr_idx]
    Xcal, ycal = [X[i] for i in cal_idx], [y_all[i] for i in cal_idx]
    folds = list(splits.cv_splits(ytr if clf else [0] * len(ytr), clf, len(ytr)))

    board: list[dict[str, Any]] = []
    for nm in names:
        cls = get_candidate(nm)
        scores, fit_t = [], []
        last = None
        entry: dict[str, Any] = {"candidate": nm, "status": "ok"}
        try:
            for tr, va in folds:
                c = cls()
                t0 = time.perf_counter()
                c.fit([Xtr[i] for i in tr], [ytr[i] for i in tr])
                fit_t.append(time.perf_counter() - t0)
                pred = c.predict([Xtr[i] for i in va])
                scores.append(M.score(metric_name, [ytr[i] for i in va], list(pred)))
                last = c
            entry.update(
                metric=float(np.mean(scores)),
                metric_std=float(np.std(scores)),
                fit_time_s=float(np.mean(fit_t)),
                predict_latency_ms=_median_latency_ms(last, Xtr[:LATENCY_ROWS]),
            )
        except Exception as e:  # noqa: BLE001
            entry.update(status="failed", error=f"{type(e).__name__}: {e}")
        board.append(entry)
        say(f"  {nm}: " + (f"{metric_name} {entry['metric']:.4f}" if entry["status"] == "ok" else entry["error"]))

    ok = [e for e in board if e["status"] == "ok"]
    if not ok:
        raise PeccaError("every candidate failed", "; ".join(e["error"] for e in board))
    sign = -1.0 if M.HIGHER_IS_BETTER[metric_name] else 1.0
    winner_entry = min(ok, key=lambda e: (sign * round(e["metric"], 6), e["predict_latency_ms"]))
    winner_entry["winner"] = True
    winner = winner_entry["candidate"]

    # Refit on all training rows (calibration rows stay unseen) and calibrate.
    cand = get_candidate(winner)()
    cand.fit(Xtr, ytr)
    art = Path(workdir) / "artefacts"
    art.mkdir(parents=True, exist_ok=True)

    threshold = fallback = None
    target_met = True
    cal_kind = "none"
    curve: list[list[float]] = []
    ece_val: float | None = None
    conf_cal = None
    confusion: dict[str, Any] = {}
    per_class: dict[str, Any] = {}
    calibrator = Calibrator("none")
    if clf:
        classes = cand.classes_
        cidx = {c: i for i, c in enumerate(classes)}
        known = [i for i, y in enumerate(ycal) if y in cidx]
        proba = cand.predict_proba([Xcal[i] for i in known])
        y_idx = np.array([cidx[ycal[i]] for i in known])
        calibrator = fit_calibrator(proba, y_idx)
        cal_kind = calibrator.kind
        conf_cal = calibrator.confidence(proba)
        pred_idx = proba.argmax(axis=1)
        correct = (pred_idx == y_idx).astype(float)
        threshold, fallback, target_met, _ = search_threshold(conf_cal, correct, target_precision)
        ece_val = M.ece(conf_cal, correct)
        curve = M.calibration_curve(conf_cal, correct)
        y_true_s = [classes[i] for i in y_idx]
        y_pred_s = [classes[i] for i in pred_idx]
        confusion = M.confusion(y_true_s, y_pred_s, classes)
        per_class = M.per_class_report(y_true_s, y_pred_s, classes)

    # LLM vs human labels on the same hold-out rows.
    llm_metric = holdout_metric = None
    hum = [i for i in range(len(df)) if sources[i] == "human"]
    hum_cal = [i for i in cal_idx if sources[i] == "human"]
    rows = hum_cal if len(hum_cal) >= 30 else hum
    if rows:
        truth = [y_all[i] for i in rows]
        llm_out = [
            normalise_output(df["llm_output"].iloc[i]) if clf else float(df["llm_output"].iloc[i])
            for i in rows
        ]
        llm_metric = M.score(metric_name, truth, llm_out)
        if set(rows) <= set(cal_idx):
            holdout_metric = M.score(metric_name, truth, list(cand.predict([X[i] for i in rows])))

    # Persist artefacts.
    cand.save(str(art))
    fmt = export_with_parity(cand, str(art), Xcal or Xtr)
    forms = _label_forms(df, resolved) if clf else {}
    (art / "calibration.json").write_text(json.dumps(calibrator.to_dict()))
    (art / "labels.json").write_text(json.dumps({"classes": cand.classes_, "forms": forms}))
    lineage = build_lineage(df, [str(x) for x in X], sources, call, ds.source, ds.input_template)
    lineage["label_counts"] = dict(Counter(resolved)) if clf else {}
    (art / "lineage.json").write_text(json.dumps(lineage, indent=2))
    (art / "config.json").write_text(json.dumps({
        "candidate": winner, "format": fmt, "task_type": profile.task_type,
        "input_type": profile.input_type, "input_template": ds.input_template,
        "metric": metric_name, "threshold": threshold}))

    mv = ModelVersion(
        version=version, candidate=winner, format=fmt, task_type=profile.task_type,
        metric_name=metric_name, metric=winner_entry["metric"], metric_std=winner_entry["metric_std"],
        llm_metric=llm_metric, threshold=threshold, expected_fallback_rate=fallback,
        latency_ms=winner_entry["predict_latency_ms"], trained_at=iso(),
        target_precision=target_precision, target_met=target_met, calibration_kind=cal_kind,
        holdout_metric=holdout_metric, labels=list(cand.classes_), leaderboard=board,
        lineage=lineage, confusion_matrix=confusion, per_class=per_class,
        calibration_curve=curve, ece=ece_val, environment=environment(), git_sha=git_sha(),
        input_template=ds.input_template, min_class_count=profile.min_class_count,
    )
    return Outcome(mv, str(art))
