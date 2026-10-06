"""Plain dataclasses persisted as JSON via ``to_dict`` / ``from_dict``."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any, Self


class Serializable:
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)  # type: ignore[call-overload, no-any-return]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Self:
        names = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        return cls(**{k: v for k, v in d.items() if k in names})


@dataclass
class CallProfile(Serializable):
    call: str
    n_rows: int
    n_unique_outputs: int
    unique_ratio: float
    task_type: str  # classification | regression | extraction | free_text
    input_type: str  # text | tabular | multi_text
    replaceable: bool
    reason: str | None = None
    labels: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    min_class_count: int | None = None
    n_classes_below_20: int | None = None
    n_human_labels: int = 0


@dataclass
class ModelVersion(Serializable):
    version: str
    candidate: str
    format: str
    task_type: str
    metric_name: str
    metric: float
    metric_std: float
    llm_metric: float | None
    threshold: float | None
    expected_fallback_rate: float | None
    latency_ms: float
    trained_at: str
    target_precision: float = 0.95
    target_met: bool = True
    calibration_kind: str = "none"
    calibration_basis: str = "all_labels"
    holdout_metric: float | None = None
    labels: list[str] = field(default_factory=list)
    leaderboard: list[dict[str, Any]] = field(default_factory=list)
    lineage: dict[str, Any] = field(default_factory=dict)
    confusion_matrix: dict[str, Any] = field(default_factory=dict)
    per_class: dict[str, Any] = field(default_factory=dict)
    calibration_curve: list[list[float]] = field(default_factory=list)
    ece: float | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    git_sha: str | None = None
    input_template: str | None = None
    min_class_count: int | None = None


@dataclass
class CallState(Serializable):
    mode: str = "record"
    current_version: str | None = None
    since: str | None = None
    policy: dict[str, Any] = field(default_factory=dict)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    tickets: dict[str, str] = field(default_factory=dict)
    last_trained: str | None = None
    last_revalidated: str | None = None
    last_drift_review: str | None = None
    shadow_since: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class Prediction(Serializable):
    label: str | float
    confidence: float | None
    fallback: bool
    version: str


@dataclass
class TrainResult(Serializable):
    version: str
    winner: str
    metric_name: str
    metric: float
    metric_std: float
    llm_metric: float | None
    threshold: float | None
    expected_fallback_rate: float | None
    latency_ms: float
    leaderboard: list[dict[str, Any]]
    model_path: str
    lineage: dict[str, Any]


@dataclass
class EvalReport(Serializable):
    agreement_rate: float | None
    fallback_rate: float | None
    n_rows: int
    disagreements: list[dict[str, Any]]
    drift_score: float | None
    per_class_agreement: dict[str, float]
    window: str


@dataclass
class Decision(Serializable):
    allowed: bool
    failing_gates: list[str] = field(default_factory=list)
    pending_approvals: list[str] = field(default_factory=list)
    evidence_missing: list[str] = field(default_factory=list)
    transition: str = ""
    forced: bool = False
