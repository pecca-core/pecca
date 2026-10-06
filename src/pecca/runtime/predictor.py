"""Load a trained version from the registry and serve predictions (thread-safe, lazy)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import numpy as np

from pecca.candidates import get_candidate
from pecca.core.call import Call
from pecca.core.errors import NotFoundError
from pecca.core.models import Prediction
from pecca.data.dataset import render_input
from pecca.trainer.calibration import Calibrator


class Bundle:
    """A trained model directory (config, labels, calibration, candidate) with no registry dependency."""

    def __init__(self, directory: str, version: str = "v?") -> None:
        self.dir, self.version = directory, version
        self._lock = threading.Lock()
        self._loaded = False
        self._cand: Any = None
        self._cfg: dict[str, Any] = {}
        self._forms: dict[str, str] = {}
        self._cal = Calibrator("temperature")

    def _load(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            d = Path(self.dir)
            self._cfg = json.loads((d / "config.json").read_text())
            labels = json.loads((d / "labels.json").read_text())
            self._forms = labels.get("forms", {})
            cal_file = d / "calibration.json"
            if cal_file.exists():
                self._cal = Calibrator.from_dict(json.loads(cal_file.read_text()))
            self._cand = get_candidate(self._cfg["candidate"]).load(str(d))
            self._loaded = True

    @property
    def threshold(self) -> float | None:
        self._load()
        t = self._cfg.get("threshold")
        return None if t is None else float(t)

    @property
    def format(self) -> str:
        self._load()
        return str(self._cfg.get("format", "pickle"))

    def _prep(self, x: Any) -> Any:
        if self._cfg.get("input_type") == "tabular" and isinstance(x, dict):
            return x
        return render_input(x, self._cfg.get("input_template"))

    def predict(self, inputs: list[Any]) -> list[Prediction]:
        if not inputs:
            return []
        self._load()
        X = [self._prep(x) for x in inputs]
        if self._cfg.get("task_type") == "regression":
            vals = self._cand.predict(X)
            return [Prediction(float(v), None, False, self.version) for v in vals]
        proba = np.asarray(self._cand.predict_proba(X))
        conf = self._cal.confidence(proba)
        classes = self._cand.classes_
        thr = self.threshold
        out = []
        for row, c in zip(proba, conf, strict=True):
            norm = classes[int(row.argmax())]
            label = self._forms.get(norm, norm)
            out.append(Prediction(label, float(c), bool(thr is not None and c < thr), self.version))
        return out


class Predictor(Bundle):
    """A ``Bundle`` resolved lazily from a call's registry."""

    def __init__(self, call: Call, version: str) -> None:
        super().__init__("", version)
        self.call = call

    def _load(self) -> None:
        if not self._loaded:
            self.dir = self.call.model_dir(self.version)
        super()._load()


_cache: dict[tuple[int, str, str], Predictor] = {}
_cache_lock = threading.Lock()


def get_predictor(call: Call, version: str | None = None) -> Predictor:
    v = version or call.state().current_version
    if v is None:
        vs = call.versions()
        if not vs:
            raise NotFoundError(f"no trained model for {call.path}", f"run `pecca train {call.path}`")
        v = vs[-1].version
    key = (id(call.workspace), call.key, v)
    with _cache_lock:
        if key not in _cache:
            _cache[key] = Predictor(call, v)
        return _cache[key]


def clear_cache() -> None:
    with _cache_lock:
        _cache.clear()
