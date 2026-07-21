"""SSE frame-vocabulary contract (discriminated union on `type`).

Frame `type` names and the nine pinned `stage` keys are contract (spec §
SSE) — Hyrum hygiene means nothing else internal (module names, model ids,
raw payload keys) is ever observable through a frame. Every frame except
`tick` carries a `sequence` (the `event_log` sequence, doubling as the
client's reconnect cursor); `tick` is the ephemeral channel and carries
neither `sequence` nor an `id:` line.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from .check_ins import CheckInOut
from .planning import PlanDraft
from .projects import ProjectStatus
from .runs import RunStatus

#: The pinned stable component-vocabulary stage keys (spec § SSE).
StageKey = Literal[
    "acquire",
    "screen",
    "classify",
    "appraise",
    "characterise",
    "select",
    "extract",
    "group",
    "synthesise",
]

#: `StageKey`'s members as a plain tuple, for runtime membership checks.
STAGE_KEYS: tuple[StageKey, ...] = (
    "acquire",
    "screen",
    "classify",
    "appraise",
    "characterise",
    "select",
    "extract",
    "group",
    "synthesise",
)

#: Who decided a resolved check-in. Mirrors `steering_events.DecidedBy`.
DecidedBy = Literal["user", "orchestrator", "standing_default"]


class _PersistedFrameBase(BaseModel):
    """Common fields for every persisted (non-`tick`) frame.

    Args:
        sequence: The `event_log` sequence — the client's reconnect cursor.
        occurred_at: When the underlying event was recorded.
    """

    sequence: int
    occurred_at: datetime


class RunStatusFrame(_PersistedFrameBase):
    """Walk open/park/finish/interrupt."""

    type: Literal["run.status"]
    capability_run_id: uuid.UUID
    status: RunStatus


class StageStartedFrame(_PersistedFrameBase):
    """A component run started."""

    type: Literal["stage.started"]
    stage: StageKey
    label: str
    blurb: str


class StageCompletedFrame(_PersistedFrameBase):
    """A component reached its terminal (successful) outcome."""

    type: Literal["stage.completed"]
    stage: StageKey
    label: str
    summary: dict[str, int | float | str] = Field(default_factory=dict)
    seconds: float | None = None


class StageFailedFrame(_PersistedFrameBase):
    """A component failed or was skipped."""

    type: Literal["stage.failed"]
    stage: StageKey
    label: str
    reason: str
    skipped: bool


class CheckinPendingFrame(_PersistedFrameBase):
    """A `steering.pause` — the full check-in resource."""

    type: Literal["checkin.pending"]
    check_in: CheckInOut


class CheckinResolvedFrame(_PersistedFrameBase):
    """A `steering.decision` resolving a prior pending check-in."""

    type: Literal["checkin.resolved"]
    check_in_id: uuid.UUID
    response: dict[str, Any]
    decided_by: DecidedBy | None = None


class PlanUpdatedFrame(_PersistedFrameBase):
    """A plan row supersession (new draft turn, or approval)."""

    type: Literal["plan.updated"]
    plan: PlanDraft
    version: int


class ProjectUpdatedFrame(_PersistedFrameBase):
    """A lifecycle audit event (rename, archive)."""

    type: Literal["project.updated"]
    name: str | None = None
    question: str | None = None
    status: ProjectStatus | None = None


class TickFrame(BaseModel):
    """Ephemeral heartbeat/progress-note frame.

    Never persisted, never state-bearing, carries no `id:` line — so it has
    no `sequence` field at all (unlike every other frame type).
    """

    type: Literal["tick"]
    ephemeral: Literal[True] = True
    stage: StageKey | None = None
    note: str
    occurred_at: datetime


#: Discriminated union of every SSE frame type, keyed on `type`.
SseFrame = Annotated[
    RunStatusFrame
    | StageStartedFrame
    | StageCompletedFrame
    | StageFailedFrame
    | CheckinPendingFrame
    | CheckinResolvedFrame
    | PlanUpdatedFrame
    | ProjectUpdatedFrame
    | TickFrame,
    Field(discriminator="type"),
]
