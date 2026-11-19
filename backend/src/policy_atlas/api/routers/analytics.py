"""The analytics relay: page events from the frontend, forwarded to PostHog.

The browser has no PostHog script. It names an event from a closed list and,
at most, a task id; the server adds the user id and forwards the event (see
``policy_atlas.api.analytics``). The route is a 404 when the ``analytics``
element is off.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, ConfigDict

from policy_atlas.api.analytics import Sender, capture
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.deps import get_analytics_sender, get_current_user, require_feedback

router = APIRouter(
    prefix="/api/v1/analytics",
    tags=["analytics"],
    dependencies=[Depends(get_current_user), Depends(require_feedback("analytics"))],
)


class AnalyticsEventIn(BaseModel):
    """One page event. No free text: an event name and an optional task id."""

    model_config = ConfigDict(extra="forbid")

    event: Literal["planner_opened", "report_opened", "report_exported", "sources_tab_opened"]
    task_id: uuid.UUID | None = None


@router.post("/events", status_code=status.HTTP_204_NO_CONTENT)
def relay_event(
    body: AnalyticsEventIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    sender: Annotated[Sender | None, Depends(get_analytics_sender)],
) -> Response:
    """Forward one page event to PostHog for the caller.

    Args:
        body: The event name and the task that was open, if any.
        user: The authenticated caller, who is the person in PostHog.
        sender: The PostHog sender, or ``None`` when no project key is set.

    Returns:
        An empty 204 response. The event is sent on a worker thread.
    """
    properties = {"task_id": str(body.task_id)} if body.task_id is not None else {}
    capture(sender, event=body.event, user_id=user.user_id, properties=properties)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
