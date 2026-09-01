"""The caller's own identity, and the one place a user row is provisioned.

`GET /api/v1/me` is both a read and — on a person's first call — a write, and
contract § 2 states the asymmetry rather than leaving a reviewer to guess it.
§ 3a rejects an `event_log` trace partly on the grounds that writing inside a
GET is wrong; the difference is arity. Just-in-time provisioning is a
**once-per-user** insert that no-ops on every subsequent call, whereas a trace
would be a write on **every** read. Both rules survive.

**`ON CONFLICT DO NOTHING`, never `DO UPDATE`.** Sign-in happens far more
often than enrolment, and `DO UPDATE` would let every sign-in overwrite the
`display_name`, `email` and `is_admin` that ops set out of band — silently, and
with a one-line spec a test would stay green forever. Ops enrolment is the
upsert that updates; this one only ever creates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import MeOut, OrganisationRef
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.identity import sub_display
from policy_atlas.core.schema import app_user, organisation

router = APIRouter(
    prefix="/api/v1/me",
    tags=["me"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=MeOut)
def get_me(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> MeOut:
    """Return the caller's identity row, provisioning it on first call.

    The insert carries only what the API can know: the subject, and a display
    name derived from it. `email`, `org_id` and `is_admin` are ops-owned and
    are never written here — not even as explicit NULLs on the conflict path,
    because `DO NOTHING` means the statement touches an existing row not at
    all.

    Args:
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The caller's identity, with their organisation resolved by name.
    """
    conn.execute(
        pg_insert(app_user)
        .values(
            user_id=user.user_id,
            display_name=sub_display(user.user_id),
            created_at=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    row = conn.execute(
        select(
            app_user.c.user_id,
            app_user.c.display_name,
            app_user.c.email,
            app_user.c.is_admin,
            app_user.c.org_id,
            organisation.c.name.label("org_name"),
        )
        .select_from(
            app_user.outerjoin(organisation, organisation.c.org_id == app_user.c.org_id)
        )
        .where(app_user.c.user_id == user.user_id)
    ).mappings().one()
    # Reader (iv) of contract § 3a's closed list of `is_admin` readers: the
    # caller's own row, projected back to the caller. Nothing here decides
    # access; the frontend uses it to say plainly that a wider list spans
    # organisations.
    org = (
        OrganisationRef(org_id=row["org_id"], name=row["org_name"])
        if row["org_id"] is not None
        else None
    )
    return MeOut(
        user_id=row["user_id"],
        display_name=row["display_name"],
        email=row["email"],
        organisation=org,
        is_admin=row["is_admin"],
    )
