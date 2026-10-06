"""Audit pack sections: name -> extras builder (``None`` = template needs no extras)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from pecca.audit.sections import operations, performance

Builder = Callable[[dict[str, Any], Path], dict[str, Any]]

SECTIONS: dict[str, Builder | None] = {
    "summary": None,
    "model_card": None,
    "data_lineage": None,
    "benchmark_leaderboard": None,
    "confusion_matrix": performance.confusion_matrix,
    "per_class_report": performance.per_class,
    "calibration": performance.calibration,
    "threshold_rationale": None,
    "shadow_results": operations.shadow_results,
    "approvals": operations.approvals,
    "drift_report": None,
    "controls_mapping": operations.controls_mapping,
    "environment": operations.environment,
}
EXTRA_SECTIONS = ("human_oversight_log",)  # rendered only when governance evidence asks for it
