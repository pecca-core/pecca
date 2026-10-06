"""Confidence calibration: temperature scaling (default) or isotonic."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import minimize_scalar
from sklearn.isotonic import IsotonicRegression

from pecca.trainer.metrics import ece

ISO_MAX_CLASSES = 10
ISO_MIN_CAL = 500


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return np.asarray(e / e.sum(axis=1, keepdims=True))


def _logits(proba: np.ndarray) -> np.ndarray:
    return np.log(np.clip(proba, 1e-12, 1.0))


class Calibrator:
    def __init__(self, kind: str = "temperature", T: float = 1.0,
                 x: list[float] | None = None, y: list[float] | None = None) -> None:
        self.kind, self.T, self.x, self.y = kind, T, x or [], y or []

    def apply(self, proba: np.ndarray) -> np.ndarray:
        """Return calibrated per-class probabilities; confidence is derived via ``confidence``."""
        if self.kind == "temperature":
            return _softmax(_logits(proba) / self.T)
        return proba

    def confidence(self, proba: np.ndarray) -> np.ndarray:
        cal = self.apply(proba)
        top = cal.max(axis=1)
        if self.kind == "isotonic":
            return np.interp(top, self.x, self.y)
        return np.asarray(top)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "T": self.T, "x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Calibrator:
        return cls(d.get("kind", "temperature"), d.get("T", 1.0), d.get("x"), d.get("y"))


def fit_calibrator(proba: np.ndarray, y_idx: np.ndarray) -> Calibrator:
    """Temperature scaling on the calibration split. Isotonic is used instead only when the
    spec's conditions hold (n_classes <= 10 and n_cal >= 500) and it lowers calibration ECE."""
    n, k = proba.shape
    lg = _logits(proba)

    def nll(t: float) -> float:
        p = _softmax(lg / t)
        return float(-np.mean(np.log(np.clip(p[np.arange(n), y_idx], 1e-12, 1.0))))

    res = minimize_scalar(nll, bounds=(0.05, 20.0), method="bounded")
    temp = Calibrator("temperature", T=float(res.x))
    if k <= ISO_MAX_CLASSES and n >= ISO_MIN_CAL:
        correct = (proba.argmax(axis=1) == y_idx).astype(float)
        iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip").fit(
            proba.max(axis=1), correct
        )
        iso_cal = Calibrator("isotonic", x=[float(v) for v in iso.X_thresholds_],
                             y=[float(v) for v in iso.y_thresholds_])
        t_ece = ece(temp.confidence(proba), correct)
        i_ece = ece(iso_cal.confidence(proba), correct)
        if i_ece < t_ece:
            return iso_cal
    return temp
