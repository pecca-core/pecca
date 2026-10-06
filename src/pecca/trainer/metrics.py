"""Metrics, per-class reports and confusion matrices."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import confusion_matrix as _cm
from sklearn.metrics import f1_score, precision_recall_fscore_support

HIGHER_IS_BETTER = {"macro_f1": True, "accuracy": True, "rmse": False}


def primary_metric(task_type: str, metric: str | None) -> str:
    return metric or ("macro_f1" if task_type == "classification" else "rmse")


def score(metric: str, y_true: list | np.ndarray, y_pred: list | np.ndarray) -> float:
    if metric == "macro_f1":
        return float(f1_score(y_true, y_pred, average="macro", zero_division=0))
    if metric == "accuracy":
        return float(np.mean(np.asarray(y_true) == np.asarray(y_pred)))
    if metric == "rmse":
        return float(np.sqrt(np.mean((np.asarray(y_true, float) - np.asarray(y_pred, float)) ** 2)))
    raise ValueError(f"unknown metric {metric!r}")


def better(metric: str, a: float, b: float) -> bool:
    return a > b if HIGHER_IS_BETTER[metric] else a < b


def confusion(y_true: list, y_pred: list, labels: list[str], top: int = 50) -> dict[str, Any]:
    counts = {l: int(sum(1 for t in y_true if t == l)) for l in labels}
    keep = sorted(labels, key=lambda l: (-counts[l], l))[:top]
    m = _cm(y_true, y_pred, labels=keep)
    return {"labels": keep, "matrix": m.tolist(), "truncated": len(labels) > top}


def per_class_report(y_true: list, y_pred: list, labels: list[str]) -> dict[str, Any]:
    p, r, f, s = precision_recall_fscore_support(y_true, y_pred, labels=labels, zero_division=0)
    return {
        l: {"precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
        for i, l in enumerate(labels)
    }


def ece(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> float:
    if len(conf) == 0:
        return 0.0
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(total)


def calibration_curve(conf: np.ndarray, correct: np.ndarray, bins: int = 10) -> list[list[float]]:
    edges = np.linspace(0, 1, bins + 1)
    pts = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            pts.append([float(conf[m].mean()), float(correct[m].mean()), float(m.sum())])
    return pts
