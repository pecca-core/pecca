"""Candidate registry and deterministic selection rules (spec §3.5)."""

from __future__ import annotations

import os
import warnings
from collections.abc import Callable
from typing import Any

from pecca.candidates.base import Candidate
from pecca.core.errors import PeccaError
from pecca.core.models import CallProfile

_REGISTRY: dict[str, type[Candidate]] = {}
_BUILTIN: set[str] = set()


def register(
    name: str,
    *,
    task_types: list[str],
    min_rows: int = 0,
    requires_gpu: bool = False,
    estimated_latency_ms: float | None = None,
    input_types: tuple[str, ...] | None = None,
    _builtin: bool = False,
) -> Callable[[type[Candidate]], type[Candidate]]:
    """Class decorator: ``@pecca.register("my_model", task_types=["classification"])``."""

    def deco(cls: type[Candidate]) -> type[Candidate]:
        cls.name = name
        cls.task_types = list(task_types)
        cls.min_rows = min_rows
        cls.requires_gpu = requires_gpu
        cls.estimated_latency_ms = estimated_latency_ms
        if input_types is not None:
            cls.input_types = input_types
        _REGISTRY[name] = cls
        if _builtin:
            _BUILTIN.add(name)
        return cls

    return deco


def get_candidate(name: str) -> type[Candidate]:
    if name not in _REGISTRY:
        raise PeccaError(f"unknown candidate {name!r}", f"registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def all_candidates() -> dict[str, type[Candidate]]:
    return dict(_REGISTRY)


def has_accelerator() -> bool:
    try:
        import torch

        return bool(
            torch.cuda.is_available()
            or (getattr(torch.backends, "mps", None) and torch.backends.mps.is_available())
        )
    except Exception:  # noqa: BLE001
        return False


def select_candidates(
    profile: CallProfile,
    latency_budget_ms: float | None = None,
    has_gpu: bool | None = None,
) -> list[str]:
    n, task = profile.n_rows, profile.task_type
    text = profile.input_type in {"text", "multi_text"}
    if task == "classification":
        names = (
            ["tfidf_linear", "e5_logreg"] + (["xlmr_finetune"] if n >= 2000 else [])
            if text
            else ["logreg", "lightgbm"]
        )
    elif task == "regression":
        names = ["tfidf_ridge", "e5_ridge"] if text else ["ridge", "lightgbm_reg"]
    else:
        names = []
    gpu = has_accelerator() if has_gpu is None else has_gpu
    out: list[str] = []
    for nm in names:
        cls = _REGISTRY[nm]
        if (
            latency_budget_ms is not None
            and latency_budget_ms < 10
            and (cls.estimated_latency_ms or 0) > 10
        ):
            continue
        if nm == "xlmr_finetune" and os.environ.get("PECCA_TEST_SMALL") == "1":
            continue  # small mode: no model downloads / fine-tuning
        if cls.requires_gpu and not gpu and n > 20000:
            warnings.warn(f"skipping {nm}: no GPU/MPS and n_rows={n} > 20000", stacklevel=2)
            continue
        out.append(nm)
    for nm, cls in _REGISTRY.items():
        if nm in _BUILTIN or nm in out:
            continue
        if task in cls.task_types and n >= cls.min_rows:
            if latency_budget_ms is not None and latency_budget_ms < 10 and (cls.estimated_latency_ms or 0) > 10:
                continue
            out.append(nm)
    return out


def build(name: str, **kwargs: Any) -> Candidate:
    return get_candidate(name)(**kwargs)  # type: ignore[call-arg]
