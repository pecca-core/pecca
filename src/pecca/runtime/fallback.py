"""Helpers for confidence-gated serving and agreement."""

from __future__ import annotations

from typing import Any

from pecca.core.models import Prediction
from pecca.data.dataset import normalise_output


def serve_from_model(pred: Prediction | None) -> bool:
    return pred is not None and not pred.fallback


def agrees(model_output: Any, llm_output: Any) -> bool:
    if isinstance(model_output, float) and not isinstance(llm_output, str):
        try:
            return abs(model_output - float(llm_output)) < 1e-9
        except (TypeError, ValueError):
            return False
    return normalise_output(model_output) == normalise_output(llm_output)
