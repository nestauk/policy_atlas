"""SSE frame-vocabulary contract (discriminated union on `type`).

Frame `type` names and the nineteen pinned `stage` keys are contract (spec §
SSE) — Hyrum hygiene means nothing else internal (module names, model ids,
raw payload keys) is ever observable through a frame. Every frame except the
ten ephemeral ones (`tick`, `artefact.section_delta`,
`artefact.section_revising`, `artefact.section_sources`,
`artefact.section_claim`, `artefact.section_card`, `artefact.source_note`,
`search.query`, `characterise.themes`, `toc.sketch`)
carries a `sequence` (the `event_log` sequence,
doubling as the client's reconnect cursor); the ephemeral frames carry
neither `sequence` nor an `id:` line and are never replayed.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from policy_atlas.theory_of_change.graph import Layer

from .check_ins import CheckInOut
from .common import StageKey
from .runs import RunStatus, StageCount
from .task_agent import PlanDraft, ScopingPlanDraft, TocPlanDraft
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
#: same rule as the saved report (task 058, round 7). ``intro`` is the short
#: paragraph the saved report shows under "Full report", before the body
#: sections (round 8).
LiveSectionRole = Literal["key_findings", "case_studies", "body", "intro"]


class ArtefactSectionSkeleton(BaseModel):
    """One planned live-artefact section.

    Args:
        index: The section's display identity (the key findings at 0 when the
            report has them, the body sections next, then the case studies,
            then the introduction). The index is identity, not reading
            order: the page orders by `role`.
        title: The section's title.
        focus: What the section covers.
        role: `key_findings`, `case_studies`, `body` or `intro`; skeletons
            recorded before the field existed read as `body`.
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
        citation_id: The saved citation's id, the one the committed report's
            citation carries, so the page can ask for its chunk context while
            the run is live (round 8); `null` on frames recorded before the
            field existed.
        claim_id: The saved claim's id, the one the committed report's claim
            carries; `null` on older frames.
        chunk_id: The cited chunk. The citation rows commit with the whole
            report, so `citation_id` cannot be read until then; the chunks
            are committed long before, so the page reads the passage by chunk
            and quote (`GET .../chunks/{chunk_id}/context?quote=`) while the
            report is still being written (owner, 2026-11-09). `null` on
            frames recorded before the field existed.
        quote: The checked quote the citation rests on; empty on older frames.
    """

    start: int
    end: int
    n: int
    source_id: uuid.UUID | None
    title: str
    citation_id: uuid.UUID | None = None
    claim_id: uuid.UUID | None = None
    chunk_id: uuid.UUID | None = None
    quote: str = ""


class SectionClaim(BaseModel):
    """One checked claim on a completed live section (task 058, round 13).

    The checker's verdict belongs to the claim, not to each of its citations.

    Args:
        claim_id: The saved claim's id, the one the committed report's claim
            carries; `null` without a saved row to match.
        start: First code point of the claim's text in `prose`.
        end: One past its last code point.
        tier: The checker's verdict (`tier_1` ... `tier_4`,
            `unsupported_mis_cited`), or `null` when it was not checked.
        rationale: The checker's reason for the verdict, when recorded.
    """

    claim_id: uuid.UUID | None = None
    start: int
    end: int
    tier: str | None = None
    rationale: str | None = None


class ArtefactSectionCompletedFrame(_PersistedFrameBase):
    """A live-artefact section's whole prose is available.

    Args:
        citations: The section's checked citations over `prose` (task 058,
            round 7); empty when it has none, and on frames recorded before
            the field existed.
        claims: The section's checked claims with their verdicts (task 058,
            round 13); empty on frames recorded before the field existed.
    """

    type: Literal["artefact.section_completed"]
    index: int
    title: str
    prose: str
    citations: list[SectionCitation] = Field(default_factory=list)
    claims: list[SectionClaim] = Field(default_factory=list)


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
    toc: TocPlanDraft | None = None
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
        capability_run_id: The walk the line belongs to (round 11): a
            longlist walk's option searches are walks of their own and run
            the same stages, so the page keeps the tracked walk's lines only.
            Null when the server could not tell.
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
    capability_run_id: uuid.UUID | None = None
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


class ArtefactSourceNoteFrame(BaseModel):
    """Ephemeral: one most-relevant-source note as it is written (task 058, round 8).

    The notes arrive one at a time, in the order the saved report lists
    them; each adds to the ones before. A reconnect gets the run's notes so
    far. Display-only: never persisted, no `id:` line, no `sequence`.

    Args:
        source_id: The source's id in this task.
        title: The source's title as the committed report's references name it.
        note: The note's text.
    """

    type: Literal["artefact.source_note"]
    ephemeral: Literal[True] = True
    source_id: str
    title: str
    note: str
    occurred_at: datetime


#: What a search query is (task 058, round 9): a written topic query, a
#: meaning-based (semantic) query, a pass following citations, or a pass
#: looking up cited works by id.
SearchQueryKind = Literal["topic", "semantic", "citations", "lookup"]


class SearchQueryFrame(BaseModel):
    """Ephemeral: one search query as it goes out, and again when it comes back (round 9).

    A query is identified by `(backend, query, kind)`: the frame sent when it
    comes back (with `results`) replaces the one sent when it went out
    (`results` null). A reconnect gets the run's queries so far, each in its
    latest state. Display-only: never persisted, no `id:` line, no
    `sequence`; the saved search record lists the queries after the stage.

    Args:
        backend: The database searched, `openalex` or `overton`.
        query: The query text for a `topic` or `semantic` query; for a
            `citations` or `lookup` pass a short description ("Following
            citations from 50 sources"), never the ids.
        kind: `topic`, `semantic`, `citations` or `lookup`.
        results: Null while the query is out; the number of records it
            returned once it is back.
    """

    type: Literal["search.query"]
    ephemeral: Literal[True] = True
    backend: str
    query: str
    kind: SearchQueryKind
    results: int | None
    occurred_at: datetime


class LiveTheme(BaseModel):
    """One theme as the characterise stage found it (task 058, round 9).

    Args:
        label: The theme's name.
        description: Its one-line description, or null.
    """

    label: str
    description: str | None


class CharacteriseThemesFrame(BaseModel):
    """Ephemeral: the names a clustering found, before units are assigned (rounds 9, 11).

    Sent once a clustering stage has found its names, in the order found:
    `characterise` its themes (sources into themes), `longlist` its options
    (sources into options; the residual pass sends the whole list again) and
    `theme` its themes (options into themes). The saved result brings them
    with their counts when the stage ends. A reconnect gets each stage's
    latest again. Display-only: never persisted, no `id:` line, no
    `sequence`.
    """

    type: Literal["characterise.themes"]
    ephemeral: Literal[True] = True
    stage: Literal["characterise", "longlist", "theme"]
    themes: list[LiveTheme]
    occurred_at: datetime


class SketchBox(BaseModel):
    """One box of the theory of change draft as the model wrote it (task 054, S12).

    Args:
        key: The model's key for the box in this draft ("b1", "b2", ...), not a
            stored id; connections name their ends by it.
        layer: The box's column on the canvas.
        text: The box's words.
    """

    key: str
    layer: Layer
    text: str


class SketchLink(BaseModel):
    """One connection of the draft as the model wrote it (task 054, S12).

    Args:
        key: The model's key for the connection ("l1", ...).
        source: The draft key of the box it starts from.
        target: The draft key of the box it leads to.
    """

    key: str
    source: str
    target: str


class TocSketchFrame(BaseModel):
    """Ephemeral: the theory of change's first draft while it is written (task 054, S12).

    Sent whole each time a box or connection closes in the model's answer:
    each frame replaces the one before. The boxes come first, then the
    connections; a connection names its ends by the boxes' draft keys, and
    only after both boxes were sent. An empty frame (no boxes, no
    connections) means the draft is being written again: the page drops
    its sketch. The stored graph (`GET /toc`, read when the `toc_draft`
    stage completes) replaces the sketch; its ids are not the draft keys. A
    reconnect gets the sketch so far. Display-only: never persisted, no
    `id:` line, no `sequence`.
    """

    type: Literal["toc.sketch"]
    ephemeral: Literal[True] = True
    boxes: list[SketchBox]
    links: list[SketchLink]
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
    | ArtefactSectionCardFrame
    | ArtefactSourceNoteFrame
    | SearchQueryFrame
    | CharacteriseThemesFrame
    | TocSketchFrame,
    Field(discriminator="type"),
]
