"""Onboarding profile contract: the answers a user gives at first access.

The profile lets user research cut feedback by where the user works, by role
and by the uses of Policy Atlas. It is a profile, not a feedback event.

The workplace and the role are free text, stored as the user typed them. The
uses are stable codes. Their labels live in one frontend file
(``frontend/src/lib/onboardingOptions.ts``) and are not stored, so a revised
label does not change stored data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Upper bound keeps a PUT from accepting arbitrarily large strings.
PROFILE_TEXT_MAX = 200

#: The uses of Policy Atlas. ``j1`` to ``j7`` are the brief's J1 to J7.
ProfileJob = Literal["j1", "j2", "j3", "j4", "j5", "j6", "j7", "other"]
ProfileSource = Literal["signup", "migration", "waitlist"]


class UserProfileIn(BaseModel):
    """Inbound body for ``PUT /api/v1/me/profile``.

    The first three questions (the workplace, the role and the uses) are
    required. ``panel_opt_in`` is optional.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    department: str = Field(
        min_length=1,
        max_length=PROFILE_TEXT_MAX,
        description="Where the user works, as typed. Free text.",
    )
    role: str = Field(
        min_length=1,
        max_length=PROFILE_TEXT_MAX,
        description="The user's role, as typed. Free text.",
    )
    jobs: list[ProfileJob] = Field(
        min_length=1,
        max_length=len(get_args(ProfileJob)),
        description="The uses that the user picked. One or more.",
    )
    panel_opt_in: bool | None = None

    @field_validator("jobs")
    @classmethod
    def _drop_repeats(cls, jobs: list[ProfileJob]) -> list[ProfileJob]:
        """Keep the first of each use, in the order given.

        Args:
            jobs: The validated uses.

        Returns:
            The uses with no repeats.
        """
        return list(dict.fromkeys(jobs))


class UserProfileOut(BaseModel):
    """The caller's onboarding profile. Every field is null before the first answer."""

    department: str | None = None
    role: str | None = None
    jobs: list[ProfileJob] | None = None
    panel_opt_in: bool | None = None
    source: ProfileSource | None = None
    completed_at: datetime | None = None
    skipped_once_at: datetime | None = None
