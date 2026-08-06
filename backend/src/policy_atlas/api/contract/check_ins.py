"""Steering check-in resource and response contract.

A check-in is the API projection of a `steering.pause` event (runtime
`policy_atlas.runtime.steering`); the response to one is a tagged union on
`kind` (spec § Check-ins). UI renders only server-supplied options —
vetting/judge steering never surfaces as a check-in.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

#: Boundary side a check-in pauses at. Mirrors the runtime pause boundary
#: vocabulary (`steering.PauseBoundary`) — a check-in is always a component
#: boundary pause, never the walk-level `"walk"` boundary some other
#: steering events use.
CheckInBoundary = Literal["after_component", "before_component"]

#: Check-in resolution status.
CheckInStatus = Literal["pending", "decided"]


class CheckInOption(BaseModel):
    """One server-supplied option offered at a check-in.

    Args:
        id: Canonical or authored option id.
        label: Short user-visible option label.
        description: Longer user-visible option description.
        requires_user_input: Whether picking this option requires an
            additional `params` fill-in on the response.
        suggested: Whether the server highlights this as the suggested pick.
        why: Visible reason for a run-specific suggestion.
        endorsement: Visible reason when the run endorses this canonical option.
    """

    id: str
    label: str
    description: str
    requires_user_input: bool
    suggested: bool = False
    why: str | None = None
    endorsement: str | None = None


class CheckInTrigger(BaseModel):
    """One fired floor trigger reported alongside a check-in.

    Args:
        trigger: Trigger name (e.g. `excluded_large_stratum`).
        detail: Trigger-specific detail payload.
    """

    trigger: str
    detail: Any = None


class CheckInOut(BaseModel):
    """A pending or decided steering check-in.

    Args:
        check_in_id: The pause event id.
        kind: Check-in kind.
        boundary: Which side of the component boundary the pause sits at.
        component: Composed-chain component the pause concerns, or `None`.
        stage: Presentation stage key for the pause, or `None`.
        render: The deterministic render — content of record; there is no
            LLM prose wrap.
        options: Server-supplied options. The client must never invent
            options.
        triggers: Fired floor triggers, if any.
        bundle: Scrubbed per-point display data, or ``None`` for legacy pauses.
        segment_reentry_allowed: Whether an additive segment re-entry is
            available at this boundary.
        rerun_component: Component a replacement re-run would target, or
            `None` if unavailable.
        status: Whether the check-in is still pending or already decided.
        created_at: When the pause was recorded.
        sequence: The pause event's `event_log` sequence.
    """

    check_in_id: uuid.UUID
    kind: str
    boundary: CheckInBoundary
    component: str | None = None
    stage: str | None = None
    render: str
    options: list[CheckInOption] = Field(default_factory=list)
    triggers: list[CheckInTrigger] = Field(default_factory=list)
    bundle: dict[str, Any] | None = None
    segment_reentry_allowed: bool
    rerun_component: str | None = None
    status: CheckInStatus
    created_at: datetime
    sequence: int


class OptionResponse(BaseModel):
    """Response picking a canonical or authored option.

    Args:
        kind: Discriminator.
        option_id: The picked option's id.
        params: Fill-in for `requires_user_input` options. The spec does
            not name per-option param shapes, so this stays a constrained
            free-form mapping rather than a per-option union.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["option"]
    option_id: str
    params: dict[str, Any] | None = None


class FreeTextResponse(BaseModel):
    """Response supplying free text for the router to compile.

    Args:
        kind: Discriminator.
        text: The user's free-text steer.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["free_text"]
    text: str = Field(min_length=1)


class FreeTextConfirmResponse(BaseModel):
    """Response confirming or discarding a compiled free-text fan-out.

    Args:
        kind: Discriminator.
        confirm_token: Token threading this confirm back to its compile
            (`FreeTextCompileOut.confirm_token`).
        apply: `True` to apply the compiled deltas, `False` to discard them.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["free_text_confirm"]
    confirm_token: str
    apply: bool


class AbortResponse(BaseModel):
    """Response aborting the run at this check-in.

    Args:
        kind: Discriminator.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["abort"]


#: Tagged union on `kind` for `POST .../check-ins/{check_in_id}/response`.
CheckInResponse = Annotated[
    OptionResponse | FreeTextResponse | FreeTextConfirmResponse | AbortResponse,
    Field(discriminator="kind"),
]


class FreeTextCompileOut(BaseModel):
    """The 202 body returned for a `free_text` check-in response.

    Args:
        render: The compiled fan-out render — the confirm-gate content of
            record. Nothing applies until confirmed.
        confirm_token: Opaque token the client echoes back in a
            `free_text_confirm` response.
    """

    render: str
    confirm_token: str
