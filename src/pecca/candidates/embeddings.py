"""Embedding-based text candidates (multilingual-e5 + linear head)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from sklearn.linear_model import LogisticRegression, Ridge

from pecca.candidates.base import SklearnCandidate
from pecca.candidates.registry import register

E5_MODEL = "intfloat/multilingual-e5-base"
HASH_DIM = 384


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> np.ndarray: ...


def cache_dir() -> Path:
    home = Path(os.environ.get("PECCA_HOME") or ".pecca")
    d = home / "cache" / "embeddings"
    d.mkdir(parents=True, exist_ok=True)
    return d


class HashingEmbedder:
    """Tiny local embedder used when ``PECCA_TEST_SMALL=1`` (no downloads)."""

    def __init__(self, dim: int = HASH_DIM) -> None:
        from sklearn.feature_extraction.text import HashingVectorizer

        self.dim = dim
        self.name = f"hashing-{dim}"
        self._vec = HashingVectorizer(
            n_features=dim, ngram_range=(1, 2), alternate_sign=False, norm="l2"
        )

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._vec.transform(texts).todense(), dtype=np.float32)


class SentenceEmbedder:
    """sentence-transformers wrapper with an on-disk cache keyed by sha256(text)."""

    def __init__(self, model_name: str = E5_MODEL, prefix: str = "query: ") -> None:
        self.name = model_name
        self.prefix = prefix
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.name)
        return self._model

    def _key(self, text: str) -> str:
        return hashlib.sha256(f"{self.name}\x00{self.prefix}{text}".encode()).hexdigest()

    def embed(self, texts: list[str]) -> np.ndarray:
        cdir = cache_dir()
        out: list[np.ndarray | None] = [None] * len(texts)
        missing: list[int] = []
        for i, t in enumerate(texts):
            f = cdir / f"{self._key(t)}.npy"
            if f.exists():
                out[i] = np.load(f)
            else:
                missing.append(i)
        if missing:
            model = self._load()
            vecs = model.encode(
                [self.prefix + texts[i] for i in missing],
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            for i, v in zip(missing, vecs, strict=True):
                v = np.asarray(v, dtype=np.float32)
                np.save(cdir / f"{self._key(texts[i])}.npy", v)
                out[i] = v
        if not out:
            return np.zeros((0, 1), dtype=np.float32)
        return np.vstack([v for v in out if v is not None])


_EMBEDDERS: dict[str, Embedder] = {}


def get_embedder(name: str | None = None) -> Embedder:
    """Pick the embedder: explicit ``name`` (stored in a saved model) or by environment."""
    if name is None:
        name = f"hashing-{HASH_DIM}" if os.environ.get("PECCA_TEST_SMALL") == "1" else E5_MODEL
    if name not in _EMBEDDERS:
        _EMBEDDERS[name] = (
            HashingEmbedder(int(name.split("-")[1]))
            if name.startswith("hashing-")
            else SentenceEmbedder(name)
        )
    return _EMBEDDERS[name]


class _EmbeddingCandidate(SklearnCandidate):
    onnx_input = "float"

    def __init__(self, embedder: str | None = None) -> None:
        super().__init__()
        self.embedder = get_embedder(embedder)

    def _prep(self, X: list[Any]) -> Any:
        return self.embedder.embed([str(x) for x in X])

    def _onnx_feed(self, X: list[Any]) -> np.ndarray:
        return np.asarray(self._prep(X), dtype=np.float32)

    def _n_float_features(self) -> int:
        return int(self.model.n_features_in_)

    def _extra_meta(self) -> dict[str, Any]:
        return {"embedder": self.embedder.name}

    @classmethod
    def _from_meta(cls, meta: dict[str, Any]) -> SklearnCandidate:
        obj = cls(embedder=meta.get("embedder"))
        obj._classes = list(meta.get("classes", []))
        obj._features = []
        return obj


@register(
    "e5_logreg",
    task_types=["classification"],
    estimated_latency_ms=40.0,
    input_types=("text", "multi_text"),
    _builtin=True,
)
class E5LogReg(_EmbeddingCandidate):
    kind = "classification"

    def _build(self) -> Any:
        return LogisticRegression(class_weight="balanced", max_iter=2000)


@register(
    "e5_ridge",
    task_types=["regression"],
    estimated_latency_ms=40.0,
    input_types=("text", "multi_text"),
    _builtin=True,
)
class E5Ridge(_EmbeddingCandidate):
    kind = "regression"

    def _build(self) -> Any:
        return Ridge()
