"""SSE frame-vocabulary contract (discriminated union on `type`).

Frame `type` names and the nineteen pinned `stage` keys are contract (spec §
SSE) — Hyrum hygiene means nothing else internal (module names, model ids,
raw payload keys) is ever observable through a frame. Every frame except the
six ephemeral ones (`tick`, `artefact.section_delta`,
`artefact.section_revising`, `artefact.section_sources`,
`artefact.section_claim`, `artefact.section_card`) carries a `sequence` (the `event_log` sequence,
doubling as the client's reconnect cursor); the ephemeral frames carry
neither `sequence` nor an `id:` line and are never replayed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from .check_ins import CheckInOut
from .common import StageKey
from .runs import RunStatus
from .task_agent import PlanDraft, ScopingPlanDraft
from .tasks import TaskStatus

#: Who decided a resolved check-in. Mirrors `steering_events.DecidedBy`.
DecidedBy = Literal["user", "agent", "standing_default"]


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


class _StageFrameBase(_PersistedFrameBase):
    """Common fields for the three stage frames.

    Args:
        capability_run_id: The walk the component run belongs to (task 045,
            A3), so a reader can keep an option search's stages off its
            parent's timeline; `null` when the event names no component run.
    """

    capability_run_id: uuid.UUID | None = None


class StageStartedFrame(_StageFrameBase):
    """A component run started."""

    type: Literal["stage.started"]
    stage: StageKey
    label: str
    blurb: str


class StageCount(BaseModel):
    """One count a done row shows, with its noun: `312 found` (task 058, N17)."""

    value: int
    noun: str


class StageCompletedFrame(_StageFrameBase):
    """A component reached its terminal (successful) outcome.

    Args:
        counts: The counts the done row shows, in order, each with the
            server's noun (task 058, N17: the client keeps no copy of which
            summary keys a stage shows). Empty when the stage names none.
    """

    type: Literal["stage.completed"]
    stage: StageKey
    label: str
    summary: dict[str, int | float | str] = Field(default_factory=dict)
    seconds: float | None = None
    counts: list[StageCount] = Field(default_factory=list)


class StageFailedFrame(_StageFrameBase):
    """A component failed or was skipped."""

    type: Literal["stage.failed"]
    stage: StageKey
    label: str
    reason: str
    skipped: bool


#: What a live-artefact section is, so the page orders live sections by the
#: same rule as the saved report (task 058, round 7).
LiveSectionRole = Literal["key_findings", "case_studies", "body"]


class ArtefactSectionSkeleton(BaseModel):
    """One planned live-artefact section.

    Args:
        index: The section's display identity (the key findings at 0 when the
            report has them, the body sections next, the case studies last).
        title: The section's title.
        focus: What the section covers.
        role: `key_findings`, `case_studies` or `body`; skeletons recorded
            before the field existed read as `body`.
    """

    index: int
    title: str
    focus: str
    role: LiveSectionRole = "body"


class ArtefactSkeletonFrame(_PersistedFrameBase):
    """Presentation-only outline for an artefact being synthesised."""

    type: Literal["artefact.skeleton"]
    sections: list[ArtefactSectionSkeleton]


class ArtefactSectionStartedFrame(_PersistedFrameBase):
    """A live-artefact section has started generation."""

    type: Literal["artefact.section_started"]
    index: int


class SectionCitation(BaseModel):
    """One checked citation on a completed live section (task 058, round 7).

    One entry per citation row of the section's judged claims, so a claim
    citing two sources gives two entries over the same span.

    Args:
        start: First code point of the cited claim's text in `prose`.
        end: One past its last code point.
        n: The report-wide reference number, numbered as the committed
            report numbers its references (by source, in order of first
            citation).
        source_id: The source's id in this task, or `null` when the cited
            text is not one of the task's sources.
        title: The source's title as the committed report's references name it.
        tier: The checker's verdict on the claim (`tier_1` ... `tier_4`,
            `unsupported_mis_cited`), or `null` when it was not checked.
    """

    start: int
    end: int
    n: int
    source_id: uuid.UUID | None
    title: str
    tier: str | None


class ArtefactSectionCompletedFrame(_PersistedFrameBase):
    """A live-artefact section's whole prose is available.

    Args:
        citations: The section's checked citations over `prose` (task 058,
            round 7); empty when it has none, and on frames recorded before
            the field existed.
    """

    type: Literal["artefact.section_completed"]
    index: int
    title: str
    prose: str
    citations: list[SectionCitation] = Field(default_factory=list)


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
    plan: PlanDraft | None = None
    scoping: ScopingPlanDraft | None = None
    version: int


class TaskUpdatedFrame(_PersistedFrameBase):
    """A lifecycle audit event (rename, archive)."""

    type: Literal["task.updated"]
    name: str | None = None
    question: str | None = None
    status: TaskStatus | None = None


class TickFrame(BaseModel):
    """Ephemeral activity frame (task 058, D2): what the model is doing now.

    Never persisted, never state-bearing, carries no `id:` line — so it has
    no `sequence` field at all (unlike every other frame type). One set of
    fields for every stage.

    Args:
        stage: The stage the activity belongs to.
        activity: The activity line, in the server's plain voice; the client
            shows it as it is.
        done: Items finished so far, or null when the stage has no honest
            count (no total known before its loop started).
        total: The total known before the loop started, or null.
        unit: What `done` and `total` count (`documents`, `batches`,
            `searches`, `sections`), or null with no count.
        section: The writer's section line ("Section 3 of 7 · Costs"), or
            null outside writing.
        heartbeat: True when the hub repeated the current tick because a
            model call is still in flight (every 10 s), not because anything
            changed.
        dropped: The hub's dropped-tick counter for this task (slow
            subscriber evictions), for the silent-gap measure (N25).
    """

    type: Literal["tick"]
    ephemeral: Literal[True] = True
    stage: StageKey | None = None
    activity: str
    done: int | None = None
    total: int | None = None
    unit: str | None = None
    section: str | None = None
    heartbeat: bool = False
    dropped: int = 0
    occurred_at: datetime


class ArtefactSectionDeltaFrame(BaseModel):
    """Ephemeral: prose appended to the section being written (task 058, N7).

    Display-only. `artefact.section_completed` stays the record; a replay
    carries no deltas. Never persisted, no `id:` line, no `sequence`.

    Args:
        index: The skeleton display index of the section.
        text: The prose delta.
        mode: `append` adds `text` to the client's draft; `replace` resets
            the draft to `text` (a reconnect mid-section, or the streamed
            turn's fallback resetting an abandoned draft with empty text).
    """

    type: Literal["artefact.section_delta"]
    ephemeral: Literal[True] = True
    index: int
    text: str
    mode: Literal["append", "replace"]
    occurred_at: datetime


class SectionSpan(BaseModel):
    """A code-point span `[start, end)` of the section draft."""

    start: int
    end: int


class ArtefactSectionRevisingFrame(BaseModel):
    """Ephemeral: the sentences the judge failed, sent before the repair (N7).

    Display-only: the client blurs these spans of its draft until
    `artefact.section_completed` brings the repaired prose. Never persisted,
    no `id:` line, no `sequence`.
    """

    type: Literal["artefact.section_revising"]
    ephemeral: Literal[True] = True
    index: int
    spans: list[SectionSpan]
    occurred_at: datetime


class SectionSourceRef(BaseModel):
    """One source as the page names it while a section is written.

    Args:
        source_id: The source's id in this task (display identity only).
        title: The source's short name: first author or publisher and year
            when both are known, else its title, else where it came from.
    """

    source_id: str
    title: str


class ArtefactSectionSourcesFrame(BaseModel):
    """Ephemeral: the sources the writer has read so far for a section (task 058).

    Each frame carries the whole set, in the order the sources were first
    read; it replaces the one before. Display-only: never persisted, no
    `id:` line, no `sequence`. A reconnect mid-section gets the current set.
    """

    type: Literal["artefact.section_sources"]
    ephemeral: Literal[True] = True
    index: int
    sources: list[SectionSourceRef]
    occurred_at: datetime


class ArtefactSectionClaimFrame(BaseModel):
    """Ephemeral: one of the writer's citations, bound to the draft (task 058).

    The span `[start, end)` counts code points of the section draft, as
    `artefact.section_revising` does. The citation is still to be checked;
    `artefact.section_completed` brings the checked section. Display-only:
    never persisted, no `id:` line, no `sequence`.
    """

    type: Literal["artefact.section_claim"]
    ephemeral: Literal[True] = True
    index: int
    start: int
    end: int
    sources: list[SectionSourceRef]
    occurred_at: datetime


class ArtefactSectionCardFrame(BaseModel):
    """Ephemeral: one case-study card as it closes in the streamed reply (task 058).

    Cards arrive in order and add to the ones before; a `replace`
    `artefact.section_delta` for the same section clears them (the reply is
    being written again). `artefact.section_completed` brings the checked
    section. Display-only: never persisted, no `id:` line, no `sequence`.
    """

    type: Literal["artefact.section_card"]
    ephemeral: Literal[True] = True
    index: int
    title: str
    prose: str
    occurred_at: datetime


#: Discriminated union of every SSE frame type, keyed on `type`.
SseFrame = Annotated[
    RunStatusFrame
    | StageStartedFrame
    | StageCompletedFrame
    | StageFailedFrame
    | ArtefactSkeletonFrame
    | ArtefactSectionStartedFrame
    | ArtefactSectionCompletedFrame
    | CheckinPendingFrame
    | CheckinResolvedFrame
    | PlanUpdatedFrame
    | TaskUpdatedFrame
    | TickFrame
    | ArtefactSectionDeltaFrame
    | ArtefactSectionRevisingFrame
    | ArtefactSectionSourcesFrame
    | ArtefactSectionClaimFrame
    | ArtefactSectionCardFrame,
    Field(discriminator="type"),
]
