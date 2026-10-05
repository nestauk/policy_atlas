"""Public waitlist signup route — splash-page Request access."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.contract.waitlist import WaitlistSignup, WaitlistSignupOut
from policy_atlas.api.deps import get_conn
from policy_atlas.core.schema import waitlist_entry

router = APIRouter(
    prefix="/api/v1/waitlist",
    tags=["waitlist"],
)


@router.post("", response_model=WaitlistSignupOut, status_code=status.HTTP_201_CREATED)
def signup(
    payload: WaitlistSignup,
    conn: Annotated[Connection, Depends(get_conn)],
) -> WaitlistSignupOut:
    """Record a Request-access signup on the waitlist.

    Args:
        payload: Validated signup body.
        conn: Open database connection.

    Returns:
        Minimal acknowledgement of the new row.

    Raises:
        ApiConflict: When the email is already on the waitlist.
    """
    entry_id = uuid.uuid4()
    created_at = datetime.now(UTC)

    # Honeypot tripped (the hidden `website` field is filled): acknowledge
    # with a fake 201 and store nothing, so the bot learns nothing.
    if payload.website:
        return WaitlistSignupOut(entry_id=entry_id, email=payload.email, created_at=created_at)

    # No pre-check SELECT: the unique constraint is the arbiter, so two
    # concurrent submits with the same email cannot race past a lookup.
    try:
        conn.execute(
            waitlist_entry.insert().values(
                entry_id=entry_id,
                email=payload.email,
                name=payload.name,
                organisation=payload.organisation,
                role_or_reason=payload.role_or_reason,
                created_at=created_at,
            )
        )
    except IntegrityError as exc:
        raise ApiConflict(
            "already_registered",
            "This email is already on the waitlist.",
        ) from exc
    return WaitlistSignupOut(entry_id=entry_id, email=payload.email, created_at=created_at)
