"""Structured logging setup — mandatory from first scaffold slice.

Call configure_logging() at every entrypoint before any log call.
Never use stdlib logging or print statements; all calls go through structlog.
"""

import os

import structlog


def configure_logging() -> None:
    """JSON in deployed environments (LOG_FORMAT=json); console-pretty locally."""
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if os.getenv("LOG_FORMAT") == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
