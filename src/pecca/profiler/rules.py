"""Deterministic profiling rules (spec §3.4)."""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

from pecca.data.dataset import normalise_output

JSON_SHARE = 0.95
FLOAT_SHARE = 0.98
MAX_UNIQUE_RATIO = 0.05
MIN_UNIQUE_CAP = 50
LANG_SAMPLE = 500
LANG_MIN_SHARE = 0.05
BELOW = 20


def is_float(s: str) -> bool:
    try:
        v = float(s)
    except (TypeError, ValueError):
        return False
    return not math.isnan(v)


def json_keys(s: str) -> tuple[str, ...] | None:
    try:
        v = json.loads(s)
    except (TypeError, ValueError):
        return None
    return tuple(sorted(v)) if isinstance(v, dict) else None


def infer_task_type(raw_outputs: list[Any], n_rows: int) -> tuple[str, str | None, list[str]]:
    """Return (task_type, reason_if_not_replaceable, sorted_labels)."""
    norm = [normalise_output(o) for o in raw_outputs]
    if n_rows == 0:
        return "free_text", "no rows", []
    # JSON detection uses the raw (stripped) string: normalisation would lowercase keys.
    keysets = [json_keys(str(o).strip()) for o in raw_outputs]
    parsed = [k for k in keysets if k is not None]
    if len(parsed) / n_rows >= JSON_SHARE:
        most_common, count = Counter(parsed).most_common(1)[0]
        if count / n_rows >= JSON_SHARE:
            return "extraction", "extraction not supported in v1", []
    if sum(is_float(o) for o in norm) / n_rows >= FLOAT_SHARE:
        return "regression", None, []
    uniq = sorted(set(norm))
    ratio = len(uniq) / n_rows
    if len(uniq) <= max(MIN_UNIQUE_CAP, 0.05 * n_rows) and ratio <= MAX_UNIQUE_RATIO:
        return "classification", None, uniq
    return "free_text", "outputs are not a closed set", []


def infer_input_type(inputs: list[Any]) -> str:
    if inputs and all(isinstance(x, str) for x in inputs):
        return "text"
    dicts = [x for x in inputs if isinstance(x, dict)]
    if dicts and len(dicts) == len(inputs):
        numeric = all(
            all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in d.values())
            for d in dicts
        )
        return "tabular" if numeric else "multi_text"
    return "text"


def detect_languages(texts: list[str]) -> list[str]:
    """Languages with share >= 5% on a deterministic sample, most frequent first."""
    try:
        from langdetect import DetectorFactory, detect
    except ImportError:  # pragma: no cover
        return []
    DetectorFactory.seed = 0
    step = max(1, len(texts) // LANG_SAMPLE)
    sample = [t for t in texts[::step][:LANG_SAMPLE] if t and t.strip()]
    counts: Counter[str] = Counter()
    for t in sample:
        try:
            counts[detect(t)] += 1
        except Exception:  # noqa: BLE001
            continue
    total = sum(counts.values())
    if not total:
        return []
    return [lang for lang, c in counts.most_common() if c / total >= LANG_MIN_SHARE]
