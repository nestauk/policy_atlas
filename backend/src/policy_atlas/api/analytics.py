"""Safe PostHog capture helpers for request-scoped product events."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import Request

log = structlog.get_logger(__name__)


def capture_event(
    request: Request, event: str, *, properties: dict[str, Any] | None = None
) -> None:
    """Queue a request-context event without affecting the API response."""
    posthog_client = getattr(request.app.state, "posthog", None)
    if posthog_client is None:
        return
    try:
        posthog_client.capture(event, properties=properties)
    except Exception:
        log.warning("posthog.capture_failed", event=event)
