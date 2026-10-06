"""Evaluate a mode transition against the project's governance config."""

from __future__ import annotations

from typing import Any

from pecca import evaluation
from pecca.core.call import Call
from pecca.core.models import Decision
from pecca.governance import approvals, evidence, gates

GATED = ("record->shadow", "shadow->live")


def evaluate(call: Call, transition: str, version: str | None = None) -> Decision:
    """Return a ``Decision``; ``allowed`` is true only if gates, approvals and evidence all pass."""
    cfg: dict[str, Any] = (call.project.governance.get("transitions") or {}).get(transition) or {}
    dec = Decision(allowed=True, transition=transition)
    if transition not in GATED:
        return dec
    mv = call.version(version)
    values = evaluation.variables(call)
    for expr in cfg.get("gates", []):
        ok, detail = gates.check_gate(expr, values)
        if not ok:
            dec.failing_gates.append(detail)
    dec.pending_approvals = approvals.pending_approvals(call, mv.version, cfg.get("approvals"))
    dec.evidence_missing = evidence.missing_evidence(call, mv.version, cfg.get("evidence", []))
    dec.allowed = not (dec.failing_gates or dec.pending_approvals or dec.evidence_missing)
    return dec


def validate_gates(governance: dict[str, Any]) -> None:
    """Parse every gate in a governance block so bad expressions fail at ``pecca apply``."""
    for cfg in (governance.get("transitions") or {}).values():
        for expr in cfg.get("gates", []):
            gates.parse_gate(expr)
