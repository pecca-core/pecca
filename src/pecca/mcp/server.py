"""Pecca MCP server (``mcp`` 2.x ``MCPServer``)."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.mcpserver import MCPServer

import pecca
from pecca.api import load_dataset
from pecca.core import context
from pecca.profiler import profile_dataset


def build_server(workspace: str | None = None, allow_promote: bool = False) -> MCPServer:
    server = MCPServer("pecca", instructions=(
        "Inspect and query Pecca models that replace repetitive LLM calls. "
        "Paths look like workspace/project/call."))

    def _ws() -> Any:
        return context.get_workspace(workspace)

    @server.tool()
    def pecca_status(path: str) -> dict[str, Any]:
        """Mode, version, metrics, threshold and agreement for a call."""
        c = context.get_call(path, _ws())
        st = c.state()
        mv = c.version() if c.versions() else None
        rep = pecca.evaluate(path, "14d", workspace=_ws())
        return {"call": str(c.path), "mode": st.mode, "since": st.since, "version": mv.version if mv else None,
                "model": mv.candidate if mv else None, "metric": {mv.metric_name: mv.metric} if mv else None,
                "llm_metric": mv.llm_metric if mv else None, "threshold": mv.threshold if mv else None,
                "expected_fallback_rate": mv.expected_fallback_rate if mv else None,
                "agreement_14d": rep.agreement_rate, "fallback_rate_14d": rep.fallback_rate, "drift": rep.drift_score}

    @server.tool()
    def pecca_profile(path: str) -> dict[str, Any]:
        """Profile the call's configured data (task type, labels, languages, replaceable)."""
        c = context.get_call(path, _ws())
        return profile_dataset(load_dataset(c), c.name).to_dict()["profiles"][c.name]  # type: ignore[no-any-return]

    @server.tool()
    def pecca_evaluate(path: str, since: str = "14d") -> dict[str, Any]:
        """Agreement, fallback rate, drift and recent disagreements over a window."""
        return pecca.evaluate(path, since, workspace=_ws()).to_dict()

    @server.tool()
    def pecca_diff(path: str, v_a: str, v_b: str) -> dict[str, Any]:
        """Compare two trained versions (metrics, threshold, rows, per-class F1 deltas)."""
        c = context.get_call(path, _ws())
        a, b = c.version(v_a), c.version(v_b)
        fa = {k: v["f1"] for k, v in a.per_class.items()}
        fb = {k: v["f1"] for k, v in b.per_class.items()}
        deltas = sorted(((k, fb.get(k, 0.0) - fa.get(k, 0.0)) for k in set(fa) | set(fb)), key=lambda kv: -abs(kv[1]))[:20]
        return {"a": {"version": a.version, a.metric_name: a.metric, "threshold": a.threshold, "rows": a.lineage.get("rows")},
                "b": {"version": b.version, b.metric_name: b.metric, "threshold": b.threshold, "rows": b.lineage.get("rows")},
                "per_class_f1_delta": [{"class": k, "delta": round(d, 4)} for k, d in deltas]}

    @server.tool()
    def pecca_audit(path: str) -> str:
        """Generate the audit pack for the current version and return it as Markdown."""
        from pathlib import Path

        return Path(pecca.audit_pack(path, workspace=_ws())).read_text()

    @server.tool()
    def pecca_predict(path: str, inputs: list[Any]) -> list[dict[str, Any]]:
        """Predict labels with confidence; ``fallback`` means the LLM should answer instead."""
        return [p.to_dict() for p in pecca.predict(path, inputs, workspace=_ws())]

    if allow_promote:

        @server.tool()
        def pecca_promote(path: str, mode: str) -> dict[str, Any]:
            """Governance-gated mode change (never forces). Enabled only with --allow-promote."""
            return pecca.promote(path, mode, workspace=_ws()).to_dict()

    return server


def tool_names(server: MCPServer) -> list[str]:
    import asyncio

    return sorted(t.name for t in asyncio.run(server.list_tools()))


__all__ = ["build_server", "tool_names", "json"]
