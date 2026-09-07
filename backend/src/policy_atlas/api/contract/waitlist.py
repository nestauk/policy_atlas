"""Waitlist signup contract: public Request-access intake from the splash page.

Intake only — ops enrolment (task 033) remains the deliberate Cognito
on-ramp. No admin list/export in v1.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: Upper bounds keep a public POST from accepting arbitrarily large strings.
WAITLIST_NAME_MAX = 200
WAITLIST_ORG_MAX = 200
WAITLIST_ROLE_MAX = 1000
WAITLIST_EMAIL_MAX = 320

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class WaitlistSignup(BaseModel):
    """Inbound body for `POST /api/v1/waitlist`.

    Args:
        email: Contact address. Unique on the waitlist table.
        name: Display name of the requester.
        organisation: Optional organisation or employer.
        role_or_reason: Free-text role and/or why they want access.
        website: Leave this field empty.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=WAITLIST_EMAIL_MAX)
    name: str = Field(min_length=1, max_length=WAITLIST_NAME_MAX)
    organisation: str | None = Field(default=None, max_length=WAITLIST_ORG_MAX)
    role_or_reason: str = Field(min_length=1, max_length=WAITLIST_ROLE_MAX)
    # Honeypot: hidden on the form, so humans leave it empty and bots fill
    # it. A non-empty value gets a fake 201 and no row. Kept innocuous in
    # the public schema description on purpose.
    website: str | None = Field(
        default=None, max_length=WAITLIST_ORG_MAX, description="Leave this field empty."
    )

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Normalise and lightly validate the email shape.

        Args:
            value: Stripped inbound email.

        Returns:
            Lower-cased email.

        Raises:
            ValueError: If the string is not a plausible email.
        """
        normalised = value.lower()
        if not _EMAIL_RE.match(normalised):
            raise ValueError("must be a valid email address")
        return normalised

    @field_validator("organisation")
    @classmethod
    def empty_org_to_none(cls, value: str | None) -> str | None:
        """Treat blank organisation as omitted.

        Args:
            value: Optional organisation string.

        Returns:
            `None` when blank, otherwise the stripped value.
        """
        if value is None or value == "":
            return None
        return value


class WaitlistSignupOut(BaseModel):
    """Minimal acknowledgement of a waitlist signup.

    Omits organisation and role/reason so response logs do not amplify PII.

    Args:
        entry_id: New waitlist row id.
        email: Echo of the accepted email.
        created_at: Insert timestamp (UTC).
    """

    entry_id: uuid.UUID
    email: str
    created_at: datetime
