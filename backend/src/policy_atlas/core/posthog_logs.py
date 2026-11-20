"""PostHog OTLP log export for lifecycle milestones added by this integration only."""

from __future__ import annotations

import logging
from typing import Protocol


class _FlushableLogProvider(Protocol):
    """The portion of the OTel logger provider used at shutdown."""

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        """Flush queued records."""


_LOGGER_NAME = "policy_atlas.posthog_export"
_logger = logging.getLogger(_LOGGER_NAME)
_logger.setLevel(logging.INFO)
_logger.propagate = False

_log_provider: _FlushableLogProvider | None = None


def configure_posthog_log_exporter(project_token: str, host: str) -> bool:
    """Attach an OTLP handler to the dedicated PostHog logger when available.

    This deliberately does not attach to the root logger or the application's
    structlog output: only lifecycle lines emitted by this module leave for
    PostHog Logs.
    """
    global _log_provider
    if _log_provider is not None:
        return True

    try:
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        provider = LoggerProvider()
        exporter = OTLPLogExporter(
            endpoint=f"{host.rstrip('/')}/i/v1/logs",
            headers={"Authorization": f"Bearer {project_token}"},
        )
        provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        _logger.addHandler(LoggingHandler(logger_provider=provider))
        _log_provider = provider
    except Exception:
        # Optional observability setup must not prevent the API from serving.
        return False

    _logger.info("posthog_log_exporter_configured", extra={"service_name": "policy-atlas"})
    return True


def log_api_ready(*, ingest_mode: str) -> None:
    """Record that the API has finished creating its process resources."""
    if _log_provider is not None:
        _logger.info("api_resources_ready", extra={"ingest_mode": ingest_mode})


def log_api_stopping() -> None:
    """Record the beginning of the API's orderly shutdown."""
    if _log_provider is not None:
        _logger.info("api_shutdown_started")


def flush_posthog_logs() -> None:
    """Flush the dedicated log exporter during application shutdown."""
    if _log_provider is None:
        return
    try:
        _log_provider.force_flush(timeout_millis=5_000)
    except Exception:
        # Log delivery must never interfere with process shutdown.
        pass
