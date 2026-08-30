"""Tests for OpenTelemetry integration (Issue #4)."""

import os
from unittest.mock import patch

from srf.telemetry.provider import (
    NoOpSpan,
    NoOpTracer,
    get_tracer,
    init_telemetry,
    inject_trace_id_to_structlog,
    span,
)


def test_no_otel_returns_noop():
    tracer = init_telemetry()
    assert isinstance(tracer, NoOpTracer)


def test_noop_span_attributes():
    s = NoOpSpan()
    s.set_attribute("key", "value")
    s.set_status(None)
    s.record_exception(Exception("test"))


def test_noop_span_context_manager():
    s = NoOpSpan()
    with s as inner:
        assert inner is s


def test_noop_tracer_start_span():
    tracer = NoOpTracer()
    s = tracer.start_as_current_span("test")
    assert isinstance(s, NoOpSpan)


def test_get_tracer_returns_noop_when_not_initialized():
    import srf.telemetry.provider as tp
    old = tp._tracer
    tp._tracer = None
    try:
        tracer = get_tracer()
        assert isinstance(tracer, NoOpTracer)
    finally:
        tp._tracer = old


def test_span_context_manager_noop():
    init_telemetry()
    with span("test-span", {"run_id": "abc"}) as s:
        assert isinstance(s, NoOpSpan)


def test_no_endpoint_returns_noop():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("SRF_OTLP_ENDPOINT", None)
        tracer = init_telemetry()
        assert isinstance(tracer, NoOpTracer)


def test_inject_trace_id_without_otel():
    result = inject_trace_id_to_structlog()
    # Without OTel installed and active, returns None
    assert result is None or isinstance(result, str)


def test_span_noop_no_crash():
    init_telemetry(service_name="test", run_id="r1", mode="gepa", task="circle_packing")
    with span("package.execute", {"mode": "gepa", "iteration": 0}):
        pass
    with span("fn.execute", {"name": "select_parent"}):
        pass
    with span("llm.call", {"model": "sonnet"}):
        pass
