"""Small tracing helpers for non-HTTP spans."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from loguru import logger

try:
    from opentelemetry import trace
    from opentelemetry.trace import StatusCode

    HAS_OTEL = True
except Exception:  # pragma: no cover - optional runtime dependency failures.
    trace = None  # type: ignore[assignment]
    StatusCode = None  # type: ignore[assignment]
    HAS_OTEL = False


@contextmanager
def start_span(name: str, attrs: dict[str, Any] | None = None) -> Iterator[None]:
    if not HAS_OTEL or trace is None:
        yield
        return

    tracer = trace.get_tracer("contract-agent.internal")
    with tracer.start_as_current_span(name) as span:
        for key, value in (attrs or {}).items():
            try:
                span.set_attribute(key, value)
            except Exception as exc:
                logger.debug(f"span attribute ignored name={name} key={key}: {exc}")
        try:
            yield
            if StatusCode is not None:
                span.set_status(StatusCode.OK)
        except Exception as exc:
            if StatusCode is not None:
                span.set_status(StatusCode.ERROR, str(exc))
            span.record_exception(exc)
            logger.debug(f"span {name} failed: {exc}")
            raise
