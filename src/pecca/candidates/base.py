"""``Candidate`` interface (spec §5.12) and a scikit-learn based helper."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

import joblib
import numpy as np


class Candidate(ABC):
    name: ClassVar[str] = ""
    task_types: ClassVar[list[str]] = []
    input_types: ClassVar[tuple[str, ...]] = ("text", "multi_text", "tabular")
    min_rows: ClassVar[int] = 0
    requires_gpu: ClassVar[bool] = False
    estimated_latency_ms: ClassVar[float | None] = None
    format: str = "pickle"  # pickle | onnx | hf  (set after save/load)

    @abstractmethod
    def fit(self, X: list[Any], y: list[Any]) -> None: ...
    @abstractmethod
    def predict_proba(self, X: list[Any]) -> np.ndarray: ...
    @abstractmethod
    def predict(self, X: list[Any]) -> np.ndarray: ...
    @property
    @abstractmethod
    def classes_(self) -> list[str]: ...
    @abstractmethod
    def save(self, path: str) -> None: ...
    @classmethod
    @abstractmethod
    def load(cls, path: str) -> Candidate: ...

    def to_onnx(self, path: str) -> bool:
        """Export to ONNX at ``path``; return False if unsupported."""
        return False


def _onnx_enabled() -> bool:
    return os.environ.get("PECCA_DISABLE_ONNX") != "1"


class SklearnCandidate(Candidate):
    """Candidate backed by one scikit-learn estimator/pipeline."""

    kind: ClassVar[str] = "classification"  # or regression
    onnx_input: ClassVar[str] = "text"  # text | float

    def __init__(self) -> None:
        self.model: Any = None
        self._classes: list[str] = []
        self._features: list[str] = []
        self._sess: Any = None
        self.format = "pickle"

    # -- subclass hooks ---------------------------------------------------------------------
    @abstractmethod
    def _build(self) -> Any: ...

    def _prep(self, X: list[Any]) -> Any:
        if self._features:
            import pandas as pd

            return pd.DataFrame([{f: x[f] for f in self._features} for x in X])[self._features]
        return list(X)

    def _extra_meta(self) -> dict[str, Any]:
        return {}

    # -- fitting / predicting ---------------------------------------------------------------
    def fit(self, X: list[Any], y: list[Any]) -> None:
        if X and isinstance(X[0], dict):
            self._features = sorted(X[0])
        self.model = self._build()
        self.model.fit(self._prep(X), y)
        if self.kind == "classification":
            self._classes = [str(c) for c in self.model.classes_]
        self._sess = None

    @property
    def classes_(self) -> list[str]:
        return self._classes

    def predict_proba(self, X: list[Any]) -> np.ndarray:
        if self._sess is not None:
            return self._onnx_proba(X)
        return np.asarray(self.model.predict_proba(self._prep(X)), dtype=np.float64)

    def predict(self, X: list[Any]) -> np.ndarray:
        if self.kind == "regression":
            if self._sess is not None:
                return np.asarray(self._onnx_run(X)[0], dtype=np.float64).reshape(-1)
            return np.asarray(self.model.predict(self._prep(X)), dtype=np.float64).reshape(-1)
        proba = self.predict_proba(X)
        return np.asarray(np.asarray(self._classes, dtype=object)[proba.argmax(axis=1)])

    # -- onnx -------------------------------------------------------------------------------
    def _onnx_feed(self, X: list[Any]) -> np.ndarray:
        if self.onnx_input == "text":
            return np.array(list(X), dtype=object).reshape(-1, 1)
        return np.asarray(self._prep(X), dtype=np.float32)

    def _onnx_run(self, X: list[Any]) -> list[Any]:
        name = self._sess.get_inputs()[0].name
        return list(self._sess.run(None, {name: self._onnx_feed(X)}))

    def _onnx_proba(self, X: list[Any]) -> np.ndarray:
        outs = self._onnx_run(X)
        return np.asarray(outs[1], dtype=np.float64)

    def to_onnx(self, path: str) -> bool:
        try:
            from skl2onnx import convert_sklearn
            from skl2onnx.common.data_types import FloatTensorType, StringTensorType

            if self.onnx_input == "text":
                initial = [("input", StringTensorType([None, 1]))]
            else:
                n = len(self._features) or self._n_float_features()
                initial = [("input", FloatTensorType([None, n]))]
            options: Any = {"zipmap": False} if self.kind == "classification" else None
            if options is not None:
                options = {id(self._final_estimator()): options}
            onx = convert_sklearn(
                self.model, initial_types=initial, options=options, target_opset=15
            )
            Path(path).write_bytes(onx.SerializeToString())
            return True
        except Exception:  # noqa: BLE001
            Path(path).unlink(missing_ok=True)
            return False

    def _final_estimator(self) -> Any:
        m = self.model
        return m.steps[-1][1] if hasattr(m, "steps") else m

    def _n_float_features(self) -> int:
        return int(getattr(self._final_estimator(), "n_features_in_", 0)) or int(
            self.model.n_features_in_
        )

    # -- persistence ------------------------------------------------------------------------
    def save(self, path: str) -> None:
        d = Path(path)
        d.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.model, d / "model.pkl")
        meta = {
            "candidate": self.name,
            "classes": self._classes,
            "features": self._features,
            **self._extra_meta(),
        }
        (d / "candidate.json").write_text(json.dumps(meta))

    @classmethod
    def _from_meta(cls, meta: dict[str, Any]) -> SklearnCandidate:
        obj = cls()
        obj._classes = list(meta.get("classes", []))
        obj._features = list(meta.get("features", []))
        return obj

    @classmethod
    def load(cls, path: str) -> SklearnCandidate:
        d = Path(path)
        meta = json.loads((d / "candidate.json").read_text())
        obj = cls._from_meta(meta)
        onnx_path = d / "model.onnx"
        if onnx_path.exists() and _onnx_enabled():
            try:
                import onnxruntime as ort

                obj._sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
                obj.format = "onnx"
                return obj
            except Exception:  # noqa: BLE001
                obj._sess = None
        obj.model = joblib.load(d / "model.pkl")
        obj.format = "pickle"
        return obj
