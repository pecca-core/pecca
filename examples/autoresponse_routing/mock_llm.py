"""A deterministic stand-in for an LLM so the examples run offline.

It classifies an email by keyword overlap with each RFI topic and gets ~15% of answers wrong
(chosen by a hash of the text, so every run gives the same answers).
"""

from __future__ import annotations

import hashlib
import re

from pecca.data.synthetic import CATALOG, RFIS

_STOP = {
    "i",
    "my",
    "the",
    "a",
    "to",
    "me",
    "is",
    "and",
    "of",
    "on",
    "for",
    "in",
    "it",
    "do",
    "how",
    "can",
    "you",
    "please",
    "this",
    "that",
    "amt",
    "date",
    "last",
    "prod",
    "need",
    "want",
}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in _STOP]


def _grams(tokens: list[str]) -> set[str]:
    return set(tokens) | {f"{a} {b}" for a, b in zip(tokens, tokens[1:], strict=False)}


_TOPIC_GRAMS = {
    rfi: [_grams(_tokens(p.replace("{", " ").replace("}", " "))) for p in phrases]
    for rs in CATALOG.values()
    for rfi, phrases in rs.items()
}
CALLS = {"llm_calls": 0}


def _h(text: str) -> int:
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def llm_route_rfi(subject: str, body: str) -> str:
    """Pretend LLM call: returns one of the 60 RFI labels."""
    CALLS["llm_calls"] += 1
    text = f"{subject}\n\n{body}"
    grams = _grams(_tokens(text))
    # best phrase-variant recall (how much of a known phrasing appears in the email)
    best = max(
        _TOPIC_GRAMS, key=lambda r: (max(len(grams & g) / len(g) for g in _TOPIC_GRAMS[r]), r)
    )
    if _h(text) % 100 < 15:  # the "LLM" is wrong 15% of the time
        return RFIS[_h(text + "x") % len(RFIS)][1]
    return best
