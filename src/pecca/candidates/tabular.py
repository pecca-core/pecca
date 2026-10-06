"""Tabular candidates (dict-of-numbers inputs)."""

from __future__ import annotations

from typing import Any

from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from pecca.candidates.base import SklearnCandidate
from pecca.candidates.registry import register

_TAB = ("tabular",)


@register("logreg", task_types=["classification"], estimated_latency_ms=1.0, input_types=_TAB, _builtin=True)
class LogReg(SklearnCandidate):
    kind = "classification"
    onnx_input = "float"

    def _build(self) -> Any:
        return Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=2000))])


@register("ridge", task_types=["regression"], estimated_latency_ms=1.0, input_types=_TAB, _builtin=True)
class RidgeTab(SklearnCandidate):
    kind = "regression"
    onnx_input = "float"

    def _build(self) -> Any:
        return Pipeline([("scale", StandardScaler()), ("reg", Ridge())])


@register("lightgbm", task_types=["classification"], estimated_latency_ms=2.0, input_types=_TAB, _builtin=True)
class LightGBMClf(SklearnCandidate):
    kind = "classification"
    onnx_input = "float"

    def _build(self) -> Any:
        from lightgbm import LGBMClassifier

        return LGBMClassifier(class_weight="balanced", verbose=-1, random_state=42, n_jobs=1)


@register("lightgbm_reg", task_types=["regression"], estimated_latency_ms=2.0, input_types=_TAB, _builtin=True)
class LightGBMReg(SklearnCandidate):
    kind = "regression"
    onnx_input = "float"

    def _build(self) -> Any:
        from lightgbm import LGBMRegressor

        return LGBMRegressor(verbose=-1, random_state=42, n_jobs=1)
