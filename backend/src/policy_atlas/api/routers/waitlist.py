"""Public waitlist signup route — splash-page Request access."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

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
    """
    entry_id = uuid.uuid4()
    created_at = datetime.now(UTC)

    # Honeypot tripped (the hidden `website` field is filled): acknowledge
    # with a fake 201 and store nothing, so the bot learns nothing.
    if payload.website:
        return WaitlistSignupOut(entry_id=entry_id, email=payload.email, created_at=created_at)

    # A duplicate gets the same 201 and writes nothing, so the endpoint cannot
    # be used to test whether an address is registered.
    conn.execute(
        pg_insert(waitlist_entry)
        .values(
            entry_id=entry_id,
            email=payload.email,
            name=payload.name,
            organisation=payload.organisation,
            role_or_reason=payload.role_or_reason,
            created_at=created_at,
        )
        .on_conflict_do_nothing(index_elements=["email"])
    )
    return WaitlistSignupOut(entry_id=entry_id, email=payload.email, created_at=created_at)
