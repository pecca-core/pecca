"""Data lineage and environment capture."""

from __future__ import annotations

import platform
import subprocess
from collections import Counter
from importlib import metadata
from typing import Any

import pandas as pd

from pecca import __version__
from pecca.data.dataset import dataset_hash


def environment() -> dict[str, Any]:
    env: dict[str, Any] = {
        "python": platform.python_version(),
        "pecca": __version__,
        "platform": platform.platform(),
    }
    for pkg in (
        "numpy",
        "pandas",
        "scikit-learn",
        "onnxruntime",
        "skl2onnx",
        "torch",
        "transformers",
        "sentence-transformers",
        "lightgbm",
    ):
        try:
            env[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            continue
    return env


def git_sha() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, check=False
        )
        return out.stdout.strip() or None if out.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def build_lineage(
    df: pd.DataFrame,
    texts: list[str],
    sources: list[str],
    call: str,
    source: str,
    input_template: str | None,
) -> dict[str, Any]:
    date_range: list[str | None] = [None, None]
    if "timestamp" in df and df["timestamp"].notna().any():
        ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce").dropna()
        if len(ts):
            date_range = [ts.min().isoformat(), ts.max().isoformat()]
    return {
        "call": call,
        "source": source,
        "rows": len(df),
        "date_range": date_range,
        "label_source_counts": dict(Counter(sources)),
        "dataset_sha256": dataset_hash(texts),
        "input_template": input_template,
    }
