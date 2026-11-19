"""Product analytics events for PostHog (in-app feedback, the brief's last step).

The events feed abandonment analysis: where in the funnel users stop. The list
is closed (:data:`ANALYTICS_EVENTS`); do not add an event without a reason.

Design: the server sends every event. The browser has no PostHog script. A
page event (for example "report opened") comes from the frontend to a relay
route, and the server forwards it. The effect is that PostHog receives only a
user id, an event name and a few closed fields: no browser details, no IP
address of the user, and no free text. Free text (a note, a description, the
research question) goes to Postgres and to Langfuse only.

Data destination: the PostHog capture API (``POST {host}/i/v0/e/``) of the
project named by ``POSTHOG_API_KEY``. Analytics is off unless the key and
``POSTHOG_HOST`` are set and ``POLICY_ATLAS_FEEDBACK`` names ``analytics``.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.api.settings import feedback_elements_from_env
from policy_atlas.core.schema import task

log = structlog.get_logger()

#: Every event that goes to PostHog. The first group comes from the frontend
#: through the relay route; the server emits the second group itself.
RELAYED_EVENTS = frozenset(
    {"planner_opened", "report_opened", "report_exported", "sources_tab_opened"}
)
ANALYTICS_EVENTS = RELAYED_EVENTS | frozenset(
    {
        "taskplan_approved",
        "run_started",
        "run_completed",
        "run_failed",
        "feedback_submitted",
        "onboarding_completed",
        "onboarding_skipped",
    }
)
#: PostHog's own event for an update of person properties with no other event.
PERSON_PROPERTIES_EVENT = "$set"
#: The run statuses that end a run, and the event for each. An aborted or
#: interrupted run is neither completed nor failed and has no event.
RUN_FINISHED_EVENTS = {
    "succeeded": "run_completed",
    "degraded": "run_completed",
    "failed": "run_failed",
}
POSTHOG_CAPTURE_PATH = "/i/v0/e/"
POSTHOG_TIMEOUT_S = 5.0
#: One worker thread sends the events, so a slow PostHog never holds a request.
_SEND_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analytics")

#: Takes one PostHog event body (without the project key) and sends it.
Sender = Callable[[dict[str, Any]], None]


def _post_to_posthog(url: str, api_key: str, body: dict[str, Any]) -> None:
    """Send one event to PostHog. A failure is logged, never raised."""
    try:
        response = httpx.post(url, json={"api_key": api_key, **body}, timeout=POSTHOG_TIMEOUT_S)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        log.warning(
            "analytics.send_failed", event_name=body.get("event"), error=type(exc).__name__
        )


def posthog_sender_from_env() -> Sender | None:
    """Build the function that sends events to PostHog, when analytics is on.

    Returns:
        The sender, or ``None`` when analytics is off: the ``analytics``
        element is not in ``POLICY_ATLAS_FEEDBACK``, or ``POSTHOG_API_KEY`` or
        ``POSTHOG_HOST`` is unset. The sender queues the HTTP call on a worker
        thread and returns at once.

    Raises:
        RuntimeError: ``POSTHOG_HOST`` is not an ``https://`` address. User
            ids must not travel over plain HTTP.
    """
    api_key = os.environ.get("POSTHOG_API_KEY", "").strip()
    host = os.environ.get("POSTHOG_HOST", "").strip().rstrip("/")
    if not api_key or not host or "analytics" not in feedback_elements_from_env():
        return None
    if not host.startswith("https://"):
        raise RuntimeError(f"POSTHOG_HOST must be an https:// address: got {host!r}")
    url = f"{host}{POSTHOG_CAPTURE_PATH}"

    def send(body: dict[str, Any]) -> None:
        """Queue one event for the worker thread."""
        _SEND_POOL.submit(_post_to_posthog, url, api_key, body)

    return send


def capture(
    sender: Sender | None,
    *,
    event: str,
    user_id: str | None,
    properties: dict[str, Any] | None = None,
    person_properties: dict[str, Any] | None = None,
) -> None:
    """Send one analytics event for one user. Never raises.

    Args:
        sender: The sender from :func:`posthog_sender_from_env`, or ``None``
            when analytics is off (then nothing happens).
        event: A name from :data:`ANALYTICS_EVENTS`, or
            :data:`PERSON_PROPERTIES_EVENT`.
        user_id: The user's token subject, which identifies the person in
            PostHog. ``None`` (a task with no owner): nothing is sent.
        properties: Closed fields of the event. Never free text.
        person_properties: Properties to set on the person (``$set``).
    """
    if sender is None or user_id is None:
        return
    if event not in ANALYTICS_EVENTS and event != PERSON_PROPERTIES_EVENT:
        log.warning("analytics.unknown_event", event_name=event)
        return
    body_properties: dict[str, Any] = {
        **(properties or {}),
        # The request comes from the server: its address is not the user's.
        "$geoip_disable": True,
    }
    if person_properties:
        body_properties["$set"] = person_properties
    try:
        sender(
            {
                "event": event,
                "distinct_id": user_id,
                "properties": body_properties,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
    except Exception as exc:  # noqa: BLE001 - analytics must not fail a request or a run
        log.warning("analytics.capture_failed", event_name=event, error=type(exc).__name__)


def capture_run_started(sender: Sender | None, *, user_id: str, task_id: uuid.UUID) -> None:
    """Send ``taskplan_approved`` and ``run_started`` for a run that a user started.

    The app has no separate approval step: "Start the search" approves the
    plan and starts the run, so the two events are sent together.

    Args:
        sender: The sender, or ``None`` when analytics is off.
        user_id: The user who started the run.
        task_id: The task.
    """
    for event in ("taskplan_approved", "run_started"):
        capture(sender, event=event, user_id=user_id, properties={"task_id": str(task_id)})


def capture_run_finished(
    engine: Engine, sender: Sender | None, *, task_id: uuid.UUID, status: str
) -> None:
    """Send ``run_completed`` or ``run_failed`` for the owner of a task. Never raises.

    Args:
        engine: The process engine, to read the task's owner.
        sender: The sender, or ``None`` when analytics is off (no read is made).
        task_id: The task whose run ended.
        status: The run's terminal status. A status with no event in
            :data:`RUN_FINISHED_EVENTS` sends nothing.
    """
    event = RUN_FINISHED_EVENTS.get(status)
    if sender is None or event is None:
        return
    try:
        with engine.connect() as conn:
            owner = conn.execute(
                select(task.c.owner_user_id).where(task.c.task_id == task_id)
            ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001 - analytics must not fail a run
        log.warning("analytics.owner_read_failed", error=type(exc).__name__)
        return
    capture(
        sender,
        event=event,
        user_id=owner,
        properties={"task_id": str(task_id), "status": status},
    )
