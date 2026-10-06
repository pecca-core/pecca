"""Build a ``CallProfile`` per call."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pecca.core.models import CallProfile, Serializable
from pecca.data.dataset import Dataset, normalise_output, render_input, resolve_labels
from pecca.profiler import rules

DEFAULT_MIN_ROWS = 500


def profile_call(dataset: Dataset, call: str, min_rows: int = DEFAULT_MIN_ROWS) -> CallProfile:
    df = dataset.to_pandas(call)
    n = len(df)
    outputs = list(df["llm_output"])
    norm_unique = {normalise_output(o) for o in outputs}
    task, reason, labels = rules.infer_task_type(outputs, n)
    inputs = list(df["input"])
    input_type = rules.infer_input_type(inputs)
    replaceable = task in {"classification", "regression"}
    if replaceable and n < min_rows:
        replaceable, reason = False, f"insufficient rows (n<{min_rows})"
    languages: list[str] = []
    if input_type in {"text", "multi_text"}:
        languages = rules.detect_languages(
            [render_input(x, dataset.input_template) for x in inputs]
        )
    resolved, sources = resolve_labels(df) if n else ([], [])
    min_count: int | None = None
    below: int | None = None
    if task == "classification" and resolved:
        counts = Counter(resolved)
        min_count = min(counts.values())
        below = sum(1 for c in counts.values() if c < rules.BELOW)
    return CallProfile(
        call=call,
        n_rows=n,
        n_unique_outputs=len(norm_unique),
        unique_ratio=(len(norm_unique) / n) if n else 0.0,
        task_type=task,
        input_type=input_type,
        replaceable=replaceable,
        reason=reason,
        labels=labels,
        languages=languages,
        min_class_count=min_count,
        n_classes_below_20=below,
        n_human_labels=sum(1 for s in sources if s == "human"),
    )


class ProfileReport(Serializable):
    def __init__(self, profiles: dict[str, CallProfile]) -> None:
        self.profiles = profiles

    def to_dict(self) -> dict[str, Any]:
        return {"profiles": {k: v.to_dict() for k, v in self.profiles.items()}}

    def table(self) -> str:
        """Plain-text table (the CLI renders the same data with rich)."""
        lines = []
        for p in self.profiles.values():
            detail = f"{len(p.labels)} labels" if p.task_type == "classification" else "—"
            mark = "✔" if p.replaceable else "✘"
            lines.append(
                f"{p.call:<20}{p.task_type:<16}{detail:<12}{p.n_rows:>8,} rows  replaceable {mark}"
            )
        return "\n".join(lines)


def profile_dataset(
    dataset: Dataset, call: str | None = None, min_rows: int = DEFAULT_MIN_ROWS
) -> ProfileReport:
    calls = [call] if call else dataset.calls
    return ProfileReport({c: profile_call(dataset, c, min_rows) for c in calls})
