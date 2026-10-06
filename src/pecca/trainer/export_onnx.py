"""Export the winner to ONNX when supported; validate parity; fall back to native artefacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from pecca.candidates.base import Candidate

PARITY_ROWS = 100
PARITY_TOL = 1e-3


def export_with_parity(cand: Candidate, artefacts_dir: str, X_sample: list[Any]) -> str:
    """Return the artefact ``format``: ``onnx`` (validated), ``pickle`` or ``hf``."""
    d = Path(artefacts_dir)
    native_fmt = "hf" if cand.name == "xlmr_finetune" else "pickle"
    onnx_path = d / "model.onnx"
    try:
        ok = cand.to_onnx(str(onnx_path))
    except Exception:  # noqa: BLE001
        ok = False
    if not ok:
        onnx_path.unlink(missing_ok=True)
        return native_fmt
    sample = X_sample[:PARITY_ROWS]
    try:
        loaded = type(cand).load(str(d))
        if loaded.format != "onnx":
            raise RuntimeError("onnx did not load")
        if cand.classes_:
            a, b = cand.predict_proba(sample), loaded.predict_proba(sample)
        else:
            a, b = cand.predict(sample), loaded.predict(sample)
        if not np.allclose(np.asarray(a, float), np.asarray(b, float), atol=PARITY_TOL):
            raise RuntimeError("onnx parity failed")
    except Exception:  # noqa: BLE001
        onnx_path.unlink(missing_ok=True)
        return native_fmt
    return "onnx"
