"""Structured JSON logging configuration using loguru."""

from __future__ import annotations

import sys
from contextvars import ContextVar
from typing import Any

from loguru import logger as _base_logger

trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def _inject_trace_id(record: dict[str, Any]) -> None:
    record["extra"]["trace_id"] = trace_id_var.get()


logger = _base_logger.patch(_inject_trace_id)


def setup_logging(
    *,
    level: str = "INFO",
    json: bool = True,
    sink: Any = sys.stderr,
) -> None:
    """Configure loguru with structured JSON output and trace ID support.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
        json: If True, output structured JSON logs; otherwise plain text.
        sink: Where to emit logs (default sys.stderr).
    """
    logger.remove()

    if json:
        logger.add(
            sink,
            level=level.upper(),
            serialize=True,
            format="{message}",
            enqueue=True,
        )
    else:
        def _fmt(record: dict[str, Any]) -> str:
            trace = record.get("extra", {}).get("trace_id", "")
            exc = record.get("exception", "")
            exc_str = "" if exc is None else f"\n{exc}"
            return (
                f"<green>{record['time']:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                f"<level>{record['level'].name: <8}</level> | "
                f"<cyan>{trace}</cyan> | "
                f"<level>{record['message']}</level>{exc_str}\n"
            )

        logger.add(
            sink,
            level=level.upper(),
            format=_fmt,
            colorize=True,
            enqueue=True,
        )


def set_trace_id(trace_id: str) -> None:
    """Set the current async context's trace ID."""
    trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """Get the current async context's trace ID."""
    return trace_id_var.get()
