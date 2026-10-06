"""OpenTelemetry helpers. With no exporter configured the API returns a no-op tracer."""

from __future__ import annotations

import threading
from typing import Any

from opentelemetry import trace

_configured = False
_lock = threading.Lock()


def configure(cfg: dict[str, Any] | None) -> None:
    """Install an OTLP exporter once if the workspace config asks for it."""
    global _configured
    if not cfg or _configured or cfg.get("exporter") != "otlp":
        return
    with _lock:
        if _configured:
            return
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": cfg.get("service", "pecca")}))
        kwargs: dict[str, Any] = {}
        if cfg.get("endpoint"):
            kwargs["endpoint"] = cfg["endpoint"]
        if cfg.get("headers"):
            kwargs["headers"] = cfg["headers"]
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(**kwargs)))
        trace.set_tracer_provider(provider)
        _configured = True


def get_tracer() -> trace.Tracer:
    return trace.get_tracer("pecca")
