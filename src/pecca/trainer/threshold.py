"""Choose the smallest confidence threshold meeting a precision target."""

from __future__ import annotations

import numpy as np

MIN_SUPPORT = 20  # rows needed above a threshold before its precision is trusted


def search_threshold(
    conf: np.ndarray, correct: np.ndarray, target_precision: float = 0.95
) -> tuple[float, float, bool, float]:
    """Return (threshold, expected_fallback_rate, target_met, precision_at_threshold).

    Rows with ``confidence >= t`` are served by the model. If no threshold reaches the target,
    the threshold is set just above the maximum confidence (everything falls back).
    """
    n = len(conf)
    if n == 0:
        return 1.0, 1.0, False, 0.0
    order = np.argsort(-conf, kind="stable")
    c_sorted = conf[order]
    hit = correct[order].astype(float)
    cum_prec = np.cumsum(hit) / np.arange(1, n + 1)
    best_t: float | None = None
    best_prec = 0.0
    # Walk down from the highest confidence; keep the lowest t that still meets the target.
    for i in range(n):
        if i + 1 < n and c_sorted[i] == c_sorted[i + 1]:
            continue  # evaluate only at the end of a tie group
        if cum_prec[i] >= target_precision and (i + 1) >= min(MIN_SUPPORT, n):
            best_t, best_prec = float(c_sorted[i]), float(cum_prec[i])
    if best_t is None:
        t = float(min(1.0, c_sorted[0] + 1e-6))
        return t, 1.0, False, 0.0
    fallback = float(np.mean(conf < best_t))
    return best_t, fallback, True, best_prec
