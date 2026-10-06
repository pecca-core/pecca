"""Section extras for confusion matrix, per-class report and calibration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def _plt() -> Any:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def confusion_matrix(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    cm = ctx["model"]["confusion_matrix"]
    if not cm:
        return {"confusion_text": "", "confusion_png": ""}
    labels, m = cm["labels"], np.array(cm["matrix"])
    top = min(12, len(labels))
    w = max(len(l) for l in labels[:top]) + 1
    lines = [" " * w + " ".join(f"{i:>4}" for i in range(top))]
    for i in range(top):
        lines.append(f"{i:>2} {labels[i][: w - 3]:<{w - 3}}" + " ".join(f"{int(v):>4}" for v in m[i, :top]))
    lines.append("(rows=true, cols=predicted; first 12 classes by support, column index = row index)")
    plt = _plt()
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(m, cmap="Blues")
    ax.set_xlabel("predicted")
    ax.set_ylabel("true")
    ax.set_title(f"Confusion matrix ({len(labels)} classes)")
    fig.tight_layout()
    fig.savefig(out / "confusion_matrix.png", dpi=110)
    plt.close(fig)
    return {"confusion_text": "\n".join(lines), "confusion_png": "confusion_matrix.png"}


def per_class(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    rows = sorted(ctx["model"]["per_class"].items(), key=lambda kv: (-kv[1]["support"], kv[0]))
    return {"per_class_rows": rows}


def calibration(ctx: dict[str, Any], out: Path) -> dict[str, Any]:
    pts = ctx["model"]["calibration_curve"]
    if not pts:
        return {"calibration_png": ""}
    plt = _plt()
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    ax.plot([0, 1], [0, 1], "--", color="grey")
    ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-")
    ax.set_xlabel("mean confidence")
    ax.set_ylabel("accuracy")
    ax.set_title("Calibration (hold-out)")
    fig.tight_layout()
    fig.savefig(out / "calibration.png", dpi=110)
    plt.close(fig)
    return {"calibration_png": "calibration.png"}
