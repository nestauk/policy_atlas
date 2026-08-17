"""User-feedback contract: the source relevance flag and the issue report.

Both are human-authored and LLM-free (spec § Feedback). The source flag is
feedback only: it never moves a source on the evidence status ladder and never
changes what the pipeline selects, reads or cites.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

#: Issue-report body length bound (spec § Feedback: `POST .../issue-reports`).
ISSUE_REPORT_BODY_MAX = 4000


class SourceFeedbackUpdate(BaseModel):
    """Inbound body for `PATCH /api/v1/projects/{id}/sources/{source_id}`.

    Args:
        not_relevant: Whether the caller marks this source as not relevant.
            Idempotent in both directions.
    """

    model_config = ConfigDict(extra="forbid")

    not_relevant: bool


class SourceFeedbackOut(BaseModel):
    """The caller's feedback state for one source.

    Args:
        source_id: The source the flag applies to.
        not_relevant: The flag's state after the write.
    """

    source_id: uuid.UUID
    not_relevant: bool


class IssueReportCreate(BaseModel):
    """Inbound body for `POST /api/v1/projects/{id}/issue-reports`.

    Args:
        body: What the user noticed, 1-4000 characters. Outer whitespace is
            stripped before the length constraint is applied
            (`str_strip_whitespace`), so a whitespace-only report is rejected.
        page_path: The in-app path the report was raised from, when known.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    body: str = Field(min_length=1, max_length=ISSUE_REPORT_BODY_MAX)
    page_path: str | None = Field(default=None, max_length=2000)


class IssueReportOut(BaseModel):
    """A recorded issue report's receipt.

    Args:
        feedback_id: The stored feedback row's identity.
        created_at: When the report was recorded.
    """

    feedback_id: uuid.UUID
    created_at: datetime
