"""Deterministic splits: 15% calibration/test hold-out, then stratified CV."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from typing import Any

import numpy as np
from sklearn.model_selection import KFold, StratifiedKFold, train_test_split

SEED = 42
HOLDOUT = 0.15


def holdout_split(y: list[Any], classification: bool) -> tuple[np.ndarray, np.ndarray]:
    idx = np.arange(len(y))
    strat = None
    if classification:
        counts = Counter(y)
        if min(counts.values()) >= 2 and len(idx) * HOLDOUT >= len(counts):
            strat = y
    tr, ca = train_test_split(idx, test_size=HOLDOUT, random_state=SEED, stratify=strat)
    return np.sort(tr), np.sort(ca)


def n_folds(n_rows: int) -> int:
    return 3 if n_rows < 2000 else 5


def cv_splits(
    y: list[Any], classification: bool, n_rows: int
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    k = n_folds(n_rows)
    X = np.zeros(len(y))
    if classification:
        min_count = min(Counter(y).values())
        if min_count >= 2:
            k = max(2, min(k, min_count))
            yield from StratifiedKFold(k, shuffle=True, random_state=SEED).split(X, y)
            return
    yield from KFold(k, shuffle=True, random_state=SEED).split(X)
