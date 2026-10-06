"""Candidate models. Importing this package registers the built-ins."""

from pecca.candidates import classical, embeddings, tabular, transformers_ft  # noqa: F401
from pecca.candidates.base import Candidate, SklearnCandidate
from pecca.candidates.registry import (
    all_candidates,
    get_candidate,
    register,
    select_candidates,
)

__all__ = [
    "Candidate",
    "SklearnCandidate",
    "all_candidates",
    "get_candidate",
    "register",
    "select_candidates",
]
