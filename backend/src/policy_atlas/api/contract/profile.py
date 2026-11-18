"""Onboarding profile contract: the answers a user gives at first access.

The profile lets user research cut feedback by department and by the main use
of Policy Atlas. It is a profile, not a feedback event.

The team types and the uses are stable codes. Their labels live in one
frontend file (``frontend/src/lib/onboardingOptions.ts``) and are not stored,
so a revised label does not change stored data. The department is also a code
from that file; the API does not hold the list of departments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

#: Upper bounds keep a POST from accepting arbitrarily large strings.
DEPARTMENT_CODE_MAX = 64
DEPARTMENT_OTHER_MAX = 200

TeamType = Literal["policy", "analysis_evidence", "strategy_finance", "private_office", "other"]
#: The main uses of Policy Atlas. ``j1`` to ``j7`` are the brief's J1 to J7.
ProfileJob = Literal["j1", "j2", "j3", "j4", "j5", "j6", "j7", "other"]
ProfileSource = Literal["signup", "migration", "waitlist"]


class UserProfileIn(BaseModel):
    """Inbound body for ``PUT /api/v1/me/profile``.

    The first two questions (department with team type, and the main use) are
    required. All other fields are optional.
    """

    model_config = ConfigDict(extra="forbid")

    department: str = Field(
        min_length=1,
        max_length=DEPARTMENT_CODE_MAX,
        pattern=r"^[a-z0-9_]+$",
        description="A department code, or 'other'. A code, never free text.",
    )
    department_other: str | None = Field(
        default=None,
        max_length=DEPARTMENT_OTHER_MAX,
        description="The department name that the user typed, when the code is 'other'.",
    )
    team_type: TeamType
    primary_job: ProfileJob
    secondary_job: ProfileJob | None = None
    panel_opt_in: bool | None = None


class UserProfileOut(BaseModel):
    """The caller's onboarding profile. Every field is null before the first answer."""

    department: str | None = None
    department_other: str | None = None
    team_type: TeamType | None = None
    primary_job: ProfileJob | None = None
    secondary_job: ProfileJob | None = None
    panel_opt_in: bool | None = None
    source: ProfileSource | None = None
    completed_at: datetime | None = None
    skipped_once_at: datetime | None = None
