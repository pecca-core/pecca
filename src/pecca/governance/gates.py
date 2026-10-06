"""Safe gate expression parser. Only ``VAR OP NUMBER`` joined by ``and`` / ``&`` / ``&&``; no eval."""

from __future__ import annotations

import operator
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pecca.core.errors import GovernanceError

VARIABLES = (
    "cv_metric",
    "cv_f1",
    "rows",
    "agreement",
    "shadow_days",
    "fallback_rate",
    "drift",
    "llm_metric",
    "min_class_count",
)
_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}
_COND = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(>=|<=|==|!=|>|<)\s*(-?\d+(?:\.\d+)?)\s*$")
_SPLIT = re.compile(r"\s*(?:&&|&|\band\b)\s*")


@dataclass(frozen=True)
class Condition:
    var: str
    op: str
    value: float

    def __str__(self) -> str:
        return f"{self.var} {self.op} {self.value:g}"


def parse_gate(expr: str) -> list[Condition]:
    if not isinstance(expr, str) or not expr.strip():
        raise GovernanceError("empty gate expression")
    out = []
    for part in _SPLIT.split(expr.strip()):
        m = _COND.match(part)
        if not m:
            raise GovernanceError(
                f"invalid gate {expr!r}",
                f"use '<variable> <op> <number>' joined by 'and'; variables: {', '.join(VARIABLES)}",
            )
        var, op, val = m.groups()
        if var not in VARIABLES:
            raise GovernanceError(
                f"unknown gate variable {var!r}", f"allowed: {', '.join(VARIABLES)}"
            )
        out.append(Condition(var, op, float(val)))
    return out


def check_gate(expr: str, values: dict[str, Any]) -> tuple[bool, str]:
    """Return (passed, human-readable detail)."""
    details, ok = [], True
    for c in parse_gate(expr):
        actual = values.get(c.var)
        if actual is None:
            ok = False
            details.append(f"{c} (no data)")
        elif _OPS[c.op](float(actual), c.value):
            details.append(f"{c} (actual {float(actual):.4g})")
        else:
            ok = False
            details.append(f"{c} (actual {float(actual):.4g})")
    return ok, " and ".join(details)
