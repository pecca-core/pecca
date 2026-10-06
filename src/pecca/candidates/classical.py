"""TF-IDF based text candidates."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline

from pecca.candidates.base import SklearnCandidate
from pecca.candidates.registry import register


def _tfidf() -> TfidfVectorizer:
    return TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)


@register(
    "tfidf_linear",
    task_types=["classification"],
    estimated_latency_ms=1.0,
    input_types=("text", "multi_text"),
    _builtin=True,
)
class TfidfLinear(SklearnCandidate):
    kind = "classification"

    def _build(self) -> Any:
        return Pipeline(
            [
                ("tfidf", _tfidf()),
                ("clf", LogisticRegression(C=4, max_iter=2000, class_weight="balanced")),
            ]
        )


@register(
    "tfidf_ridge",
    task_types=["regression"],
    estimated_latency_ms=1.0,
    input_types=("text", "multi_text"),
    _builtin=True,
)
class TfidfRidge(SklearnCandidate):
    kind = "regression"

    def _build(self) -> Any:
        return Pipeline([("tfidf", _tfidf()), ("reg", Ridge())])
