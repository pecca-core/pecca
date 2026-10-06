"""``@pecca.replace``: record / shadow / live wrapper that never raises Pecca errors into user code."""

from __future__ import annotations

import functools
import inspect
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pecca.core import context
from pecca.core.call import Call
from pecca.core.models import Prediction
from pecca.core.project import Project
from pecca.core.timeutil import iso
from pecca.core.workspace import Workspace
from pecca.runtime import telemetry
from pecca.runtime.fallback import agrees, serve_from_model
from pecca.runtime.logging_sink import get_sink
from pecca.runtime.predictor import get_predictor

log = logging.getLogger("pecca")
STATE_TTL_S = 5.0
_warned: set[str] = set()


def default_input_adapter(*args: Any, **kwargs: Any) -> Any:
    if len(args) == 1 and not kwargs and isinstance(args[0], str):
        return args[0]
    if not args and kwargs and all(isinstance(v, (str, int, float)) for v in kwargs.values()):
        return dict(kwargs)
    raise ValueError(
        "cannot derive the Pecca input from this call's arguments; "
        "pass input_adapter=lambda *a, **k: <str or dict> to @pecca.replace"
    )


def _jsonable(v: Any) -> Any:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    try:
        json.dumps(v)
        return v
    except TypeError:
        return str(v)


@dataclass
class _Plan:
    mode: str
    inp: Any = None
    pred: Prediction | None = None
    call: Call | None = None
    error: str | None = None


class _Runtime:
    """Per-decorated-function state: cached call handle and call state."""

    def __init__(
        self,
        name: str,
        mode: str | None,
        project: Any,
        workspace: Any,
        adapter: Callable[..., Any] | None,
    ) -> None:
        self.name, self.mode, self.project, self.workspace = name, mode, project, workspace
        self.adapter = adapter or default_input_adapter
        self._lock = threading.Lock()
        self._call: Call | None = None
        self._ws_id = 0
        self._state_mode: str | None = None
        self._state_at = 0.0

    def call(self) -> Call:
        ws = context.get_workspace(self.workspace)
        if self._call is None or id(ws) != self._ws_id:
            self._call = context.get_call(self.name, ws, self.project)
            self._ws_id = id(ws)
            self._state_at = 0.0
            telemetry.configure(ws.telemetry)
        return self._call

    def resolve_mode(self, call: Call) -> str:
        if self.mode:
            return self.mode
        now = time.monotonic()
        with self._lock:
            if now - self._state_at > STATE_TTL_S:
                st = call.registry.get_state(call.key)
                self._state_mode = st.get("mode") if st else None
                self._state_at = now
            return self._state_mode or "record"


def _prepare(rt: _Runtime, args: tuple[Any, ...], kwargs: dict[str, Any]) -> _Plan:
    try:
        call = rt.call()
        mode = rt.resolve_mode(call)
        if mode == "off":
            return _Plan("off", call=call)
        inp = rt.adapter(*args, **kwargs)
        pred: Prediction | None = None
        if mode in ("shadow", "live"):
            try:
                pred = get_predictor(call).predict([inp])[0]
            except Exception as e:  # noqa: BLE001
                _warn_once(
                    f"{rt.name}-predict",
                    f"pecca: model unavailable for {call.path} ({e}); using LLM only",
                )
        return _Plan(mode, inp, pred, call)
    except Exception as e:  # noqa: BLE001
        _warn_once(f"{rt.name}-prep-{type(e).__name__}", f"pecca: {e}")
        return _Plan("off", error=str(e))


def _warn_once(key: str, msg: str) -> None:
    if key not in _warned:
        _warned.add(key)
        log.error(msg)


def _record(plan: _Plan, llm_out: Any, served_by: str, started: float, span: Any) -> None:
    try:
        call = plan.call
        if call is None:
            return
        pred = plan.pred
        latency_ms = (time.perf_counter() - started) * 1000
        agreement = None
        if plan.mode == "shadow" and pred is not None and llm_out is not None:
            agreement = agrees(pred.label, llm_out)
        row = {
            "ts": iso(),
            "path": str(call.path),
            "mode": plan.mode,
            "version": pred.version if pred else None,
            "served_by": served_by,
            "input": _jsonable(plan.inp),
            "llm_output": _jsonable(llm_out),
            "model_output": pred.label if pred else None,
            "confidence": pred.confidence if pred else None,
            "agreement": agreement,
            "latency_ms": round(latency_ms, 3),
        }
        get_sink(call.registry, call.key).add(row)
        span.set_attribute("pecca.path", str(call.path))
        span.set_attribute("pecca.mode", plan.mode)
        span.set_attribute("pecca.served_by", served_by)
        span.set_attribute("pecca.latency_ms", latency_ms)
        if pred:
            span.set_attribute("pecca.version", pred.version)
            if pred.confidence is not None:
                span.set_attribute("pecca.confidence", pred.confidence)
        if agreement is not None:
            span.set_attribute("pecca.agreement", agreement)
    except Exception as e:  # noqa: BLE001
        _warn_once("record", f"pecca: failed to record decision: {e}")


def replace(
    call: str,
    mode: str | None = None,
    *,
    project: str | Project | None = None,
    workspace: str | Workspace | None = None,
    input_adapter: Callable[..., Any] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Wrap an LLM-backed function. Modes: off | record | shadow | live (see docs/concepts/modes)."""
    rt = _Runtime(call, mode, project, workspace, input_adapter)

    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def awrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                plan = _prepare(rt, args, kwargs)
                with telemetry.get_tracer().start_as_current_span("pecca.call") as span:
                    if plan.mode == "off":
                        return await fn(*args, **kwargs)
                    if plan.mode == "live" and serve_from_model(plan.pred):
                        assert plan.pred is not None
                        _record(plan, None, "model", started, span)
                        return plan.pred.label
                    out = await fn(*args, **kwargs)
                    _record(plan, out, "fallback" if plan.mode == "live" else "llm", started, span)
                    return out

            awrapper.pecca_call = call  # type: ignore[attr-defined]
            return awrapper

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            plan = _prepare(rt, args, kwargs)
            with telemetry.get_tracer().start_as_current_span("pecca.call") as span:
                if plan.mode == "off":
                    return fn(*args, **kwargs)
                if plan.mode == "live" and serve_from_model(plan.pred):
                    assert plan.pred is not None
                    _record(plan, None, "model", started, span)
                    return plan.pred.label
                out = fn(*args, **kwargs)
                _record(plan, out, "fallback" if plan.mode == "live" else "llm", started, span)
                return out

        wrapper.pecca_call = call  # type: ignore[attr-defined]
        return wrapper

    return deco
