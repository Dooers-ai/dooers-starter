"""Soft (non-turn-failing) OpenTelemetry signals for swallowed errors.

Emits a span *event* on the current span without setting StatusCode.ERROR or
calling tracker.fail(). Safe to call when OTEL is disabled or unavailable.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

SOFT_FAILURE_EVENT = "agent.soft_failure"

# Keep attribute values small for exporters / UI.
_MAX_ATTR_LEN = 500
_MAX_CTX_KEYS = 12


def _attr_str(value: Any, *, max_len: int = _MAX_ATTR_LEN) -> str:
    text = str(value).strip() if value is not None else ""
    if len(text) <= max_len:
        return text
    return f"{text[: max_len - 1]}…"


def record_soft_failure(
    system: str,
    operation: str,
    exc: BaseException | None = None,
    **ctx: Any,
) -> None:
    """Attach a soft-failure event to the active span (no turn ERROR).

    ``system`` examples: ``senior``, ``modelo_semantico``, ``ocr``, ``workflow``.
    """
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        if span is None or not span.is_recording():
            return

        attributes: dict[str, str] = {
            "failure.system": _attr_str(system, max_len=64),
            "failure.operation": _attr_str(operation, max_len=128),
        }
        if exc is not None:
            attributes["exception.type"] = type(exc).__name__
            attributes["exception.message"] = _attr_str(exc)

        for i, (key, value) in enumerate(sorted(ctx.items())):
            if i >= _MAX_CTX_KEYS or value is None:
                continue
            attributes[f"failure.ctx.{key}"] = _attr_str(value)

        span.add_event(SOFT_FAILURE_EVENT, attributes=attributes)
    except Exception:
        # Observability must never break the agent path.
        logger.debug("OTEL soft failure event skipped", exc_info=True)


def log_ocr_failure(
    operation: str,
    exc: BaseException,
    *,
    warning_message: str | None = None,
    **ctx: Any,
) -> None:
    """Log an OCR/vision soft failure and emit the matching OTEL span event."""
    if warning_message:
        logger.warning("%s: %s", warning_message, exc)
    else:
        extras = " ".join(f"{key}={value!r}" for key, value in sorted(ctx.items()) if value is not None)
        logger.warning("OCR_FAILURE operation=%s %s error=%s", operation, extras, exc)
    record_soft_failure("ocr", operation, exc, **ctx)
