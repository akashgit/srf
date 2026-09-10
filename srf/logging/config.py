"""structlog configuration — JSON renderer, ISO timestamps, file output."""

from __future__ import annotations

import sys
from pathlib import Path

import structlog


class _CurrentStderr:
    """A stream that resolves ``sys.stderr`` on every write.

    ``structlog.WriteLoggerFactory`` captures the file object it is handed, so
    passing ``sys.stderr`` directly pins whatever stream existed at
    configuration time — a test capture buffer that is later closed, or a
    replaced stream. Resolving at write time keeps a configured logger usable
    for the life of the process.
    """

    def write(self, message: str) -> int:
        return sys.stderr.write(message)

    def flush(self) -> None:
        sys.stderr.flush()


def configure_logging(
    harness: str = "srf",
    task: str = "",
    run_id: str = "",
    log_dir: Path | None = None,
) -> None:
    """Configure structlog with JSON rendering and context binding."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ]
    min_level = 20  # INFO

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"{harness}_{task}_{run_id}.jsonl"
        factory = structlog.WriteLoggerFactory(file=open(log_file, "a"))
    else:
        factory = structlog.WriteLoggerFactory(file=_CurrentStderr())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(min_level),
        context_class=dict,
        logger_factory=factory,
        cache_logger_on_first_use=True,
    )

    structlog.contextvars.bind_contextvars(
        harness=harness, task=task, run_id=run_id
    )
