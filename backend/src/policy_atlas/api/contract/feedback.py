"""In-app feedback contract: one inbound model per feedback kind.

``POST /api/v1/feedback`` takes a body whose ``kind`` field selects the model
(a discriminated union). Each model holds the kind-specific fields. The server
adds the envelope: the user, the run, the trace and the application version.

Free text (a note, a description, the research question) goes to Postgres and
to the Langfuse score comment only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

#: Upper bounds keep a POST from accepting arbitrarily large strings.
FEEDBACK_NOTE_MAX = 2000
FEEDBACK_DESCRIPTION_MAX = 5000
FEEDBACK_SHORT_TEXT_MAX = 500

FeedbackKind = Literal[
    "citation_flag",
    "missing_paper",
    "screening_override",
    "use_intent",
    "claim_flag",
    "problem_report",
]

MissingPaperFailureStage = Literal[
    "unresolved",
    "cited",
    "not_cited",
    "not_selected",
    "screened_out_s2",
    "screened_out_s1",
    "acquired_only",
    "not_retrieved",
]
UseIntent = Literal["as_is", "with_edits", "no", "dismissed"]
UseIntentChangeReason = Literal[
    "missing_evidence",
    "wrong_emphasis",
    "accuracy_concern",
    "length",
    "tone_or_format",
    "other",
]
CitationFlagReason = Literal["off_topic", "wrong_population", "not_evidence", "duplicate", "other"]


class CitationFlagIn(BaseModel):
    """Element A: "Useful" or "Not relevant" on one cited or screened-in document.

    A toggle: a second submit for the same document replaces the first. The
    reason and the note refine a "Not relevant" flag and are optional.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["citation_flag"]
    surface: Literal["report_references", "sources_all"]
    task_id: uuid.UUID
    artefact_id: uuid.UUID | None = Field(
        default=None,
        description="The report that the flag was given on. It names the run. "
        "Absent on the Sources tab: the task's latest run is used.",
    )
    source_id: uuid.UUID = Field(description="The document: its task source identity.")
    action: Literal["useful", "not_relevant"]
    reason: CitationFlagReason | None = None
    note: str | None = Field(default=None, max_length=FEEDBACK_NOTE_MAX)


class ProblemClientInfo(BaseModel):
    """What the browser attaches to a problem report."""

    model_config = ConfigDict(extra="forbid")

    browser: str = Field(max_length=FEEDBACK_SHORT_TEXT_MAX, description="The user agent.")
    time: datetime = Field(description="The browser's clock when the report was sent.")


class ProblemReportIn(BaseModel):
    """Element E: "Report a problem", from the app header on any page."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["problem_report"]
    surface: Literal["app_header"]
    task_id: uuid.UUID | None = Field(
        default=None,
        description="The task that was open. Absent on a page with no task: the "
        "report is then stored with no run.",
    )
    problem_kind: Literal["error", "stalled", "unusable", "other"]
    description: str = Field(default="", max_length=FEEDBACK_DESCRIPTION_MAX)
    page: str = Field(max_length=FEEDBACK_SHORT_TEXT_MAX, description="The page path.")
    step_reached: str | None = Field(default=None, max_length=FEEDBACK_SHORT_TEXT_MAX)
    step_status: str | None = Field(default=None, max_length=FEEDBACK_SHORT_TEXT_MAX)
    query_text: str | None = Field(
        default=None,
        max_length=FEEDBACK_DESCRIPTION_MAX,
        description="The research question, when the user left its checkbox on.",
    )
    client: ProblemClientInfo


class MissingPaperIn(BaseModel):
    """Element B: "A paper I expected is missing".

    The user gives a DOI, a URL or a title. The server resolves the paper and
    names the pipeline stage at which it was lost; the user never chooses one.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["missing_paper"]
    surface: Literal["report_foot", "sources_tab"]
    task_id: uuid.UUID
    artefact_id: uuid.UUID | None = Field(
        default=None,
        description="The report that the form is under. It names the run. "
        "Absent on the Sources tab: the task's latest run is used.",
    )
    raw_input: str = Field(
        min_length=1, max_length=FEEDBACK_SHORT_TEXT_MAX, description="A DOI, a URL or a title."
    )
    why: str | None = Field(default=None, max_length=FEEDBACK_NOTE_MAX)


class ScreeningOverrideIn(BaseModel):
    """Element B: "Should have been kept" on one screened-out document.

    A toggle with no free text. The server reads the screening stage.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["screening_override"]
    surface: Literal["screened_out_row"]
    task_id: uuid.UUID
    source_id: uuid.UUID = Field(description="The document: its task source identity.")


class UseIntentIn(BaseModel):
    """Element C: "Would you use this report in your work?", under Key findings.

    A toggle: one answer per user and report, which the user can change.
    ``dismissed`` is "Not now": it is recorded so that the question is never
    asked again for that report.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["use_intent"]
    surface: Literal["report_key_findings"]
    task_id: uuid.UUID
    artefact_id: uuid.UUID = Field(description="The report that the answer is about.")
    use_intent: UseIntent
    change_reasons: list[UseIntentChangeReason] = Field(
        default_factory=list, description="What would need to change. Optional."
    )
    note: str | None = Field(default=None, max_length=FEEDBACK_NOTE_MAX)
    shown_at: datetime = Field(description="When the browser first showed the question.")


class ClaimFlagIn(BaseModel):
    """Element D: a flag on one claim, from the foot of the claim's evidence sheet.

    A toggle: one flag per user and claim, which the user can change or
    retract. The reason is required. ``unsupported`` ("Citation doesn't
    support it") needs at least one failing citation.
    """

    model_config = ConfigDict(extra="forbid")

    kind: Literal["claim_flag"]
    surface: Literal["report_claim_sidebar"]
    task_id: uuid.UUID
    artefact_id: uuid.UUID = Field(description="The report that holds the claim.")
    claim_id: uuid.UUID
    reason: Literal["wrong", "overstated", "unsupported"]
    failing_citation_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="The claim's citations that the user ticked as not supporting it.",
    )
    provenance_viewed: list[uuid.UUID] = Field(
        default_factory=list,
        description="The claim's citations whose source the user had in view before the submit.",
    )
    note: str | None = Field(default=None, max_length=FEEDBACK_NOTE_MAX)


FeedbackIn = Annotated[
    CitationFlagIn
    | ProblemReportIn
    | MissingPaperIn
    | ScreeningOverrideIn
    | UseIntentIn
    | ClaimFlagIn,
    Field(discriminator="kind"),
]


class MissingPaperResolutionOut(BaseModel):
    """The resolver's answer for one missing-paper record.

    ``failure_stage`` is null while the resolver is still at work (pending).
    ``resolved_id`` is the document's task source identity when the task holds
    the paper, else the paper's own id (an OpenAlex address or a DOI).
    """

    failure_stage: MissingPaperFailureStage | None = None
    resolved_id: str | None = None
    resolver_confidence: float | None = None
    resolved_at: datetime | None = None


class FeedbackOut(BaseModel):
    """One stored feedback record of the caller."""

    feedback_event_id: uuid.UUID
    kind: FeedbackKind
    surface: str
    target_type: str
    target_id: str | None = None
    capability_run_id: uuid.UUID | None = None
    payload: dict[str, Any]
    created_at: datetime
    resolution: MissingPaperResolutionOut | None = Field(
        default=None, description="For a missing-paper record only."
    )


class FeedbackListOut(BaseModel):
    """The caller's active feedback records on one task."""

    data: list[FeedbackOut]
