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


FeedbackIn = Annotated[CitationFlagIn | ProblemReportIn, Field(discriminator="kind")]


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


class FeedbackListOut(BaseModel):
    """The caller's active feedback records on one task."""

    data: list[FeedbackOut]
