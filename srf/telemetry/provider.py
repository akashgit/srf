"""OpenTelemetry tracer provider — OTLP export with graceful degradation.

Activates when SRF_OTLP_ENDPOINT is set and opentelemetry is installed.
Otherwise degrades to a no-op tracer that costs nothing.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Generator

import structlog

logger = structlog.get_logger()

_tracer: Any = None
_OTEL_AVAILABLE = False

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except ImportError:
    pass


class NoOpSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any) -> None:
        pass

    def record_exception(self, exc: Exception) -> None:
        pass

    def __enter__(self) -> "NoOpSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class NoOpTracer:
    def start_as_current_span(self, name: str, **kwargs: Any) -> NoOpSpan:
        return NoOpSpan()


def init_telemetry(service_name: str = "srf", run_id: str = "", mode: str = "", task: str = "") -> Any:
    global _tracer
    endpoint = os.environ.get("SRF_OTLP_ENDPOINT")

    if not _OTEL_AVAILABLE or not endpoint:
        _tracer = NoOpTracer()
        return _tracer

    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({
            "service.name": service_name,
            "srf.run_id": run_id,
            "srf.mode": mode,
            "srf.task": task,
        })
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
        logger.info("telemetry.initialized", endpoint=endpoint)
    except Exception as e:
        logger.warning("telemetry.init_failed", error=str(e))
        _tracer = NoOpTracer()

    return _tracer


def get_tracer() -> Any:
    global _tracer
    if _tracer is None:
        _tracer = NoOpTracer()
    return _tracer


@contextmanager
def span(name: str, attributes: dict[str, Any] | None = None) -> Generator[Any, None, None]:
    tracer = get_tracer()
    if isinstance(tracer, NoOpTracer):
        s = NoOpSpan()
        if attributes:
            for k, v in attributes.items():
                s.set_attribute(k, v)
        yield s
        return

    with tracer.start_as_current_span(name) as s:
        if attributes:
            for k, v in attributes.items():
                s.set_attribute(k, str(v))
        yield s


def inject_trace_id_to_structlog() -> str | None:
    if not _OTEL_AVAILABLE:
        return None
    try:
        from opentelemetry import trace as otel_trace

        ctx = otel_trace.get_current_span().get_span_context()
        if ctx and ctx.trace_id:
            trace_id = format(ctx.trace_id, "032x")
            structlog.contextvars.bind_contextvars(trace_id=trace_id)
            return trace_id
    except Exception:
        pass
    return None
