"""The caller's onboarding profile: read, complete or edit, and skip once.

Behind the ``onboarding`` feedback flag: with the flag off, each route is a 404.

The profile row has a foreign key to ``app_user``, and that row is created only
by ``GET /api/v1/me``. The two write routes therefore provision the row first
(:func:`policy_atlas.api.identity.provision_user`), so they do not depend on
the order of the frontend's calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.api.analytics import PERSON_PROPERTIES_EVENT, Sender, capture
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract.profile import UserProfileIn, UserProfileOut
from policy_atlas.api.deps import (
    get_analytics_sender,
    get_conn,
    get_current_user,
    require_feedback,
)
from policy_atlas.api.identity import provision_user
from policy_atlas.core.schema import user_profile

router = APIRouter(
    prefix="/api/v1/me/profile",
    tags=["profile"],
    dependencies=[Depends(get_current_user), Depends(require_feedback("onboarding"))],
)


def _read_profile(conn: Connection, user_id: str) -> UserProfileOut:
    """Read one user's profile.

    Args:
        conn: Open database connection.
        user_id: The caller's token subject.

    Returns:
        The profile, with every field null when the user has no row yet.
    """
    row = conn.execute(
        select(user_profile).where(user_profile.c.user_id == user_id)
    ).mappings().first()
    return UserProfileOut.model_validate(dict(row)) if row is not None else UserProfileOut()


@router.get("", response_model=UserProfileOut)
def get_profile(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> UserProfileOut:
    """Return the caller's onboarding profile.

    Args:
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The profile. ``completed_at`` is null until the form is completed.
    """
    return _read_profile(conn, user.user_id)


@router.put("", response_model=UserProfileOut)
def save_profile(
    payload: UserProfileIn,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    analytics: Annotated[Sender | None, Depends(get_analytics_sender)],
) -> UserProfileOut:
    """Complete the caller's profile, or edit a completed one.

    ``completed_at`` keeps the time of the first completion. A later edit
    replaces the answers and leaves that time unchanged.

    The profile is mirrored to PostHog person properties: ``jobs`` and
    ``source``. Each holds codes. The workplace (``department``) and the
    ``role`` are free text and are not sent.

    Args:
        payload: The validated answers.
        user: The authenticated caller.
        conn: Open database connection.
        analytics: The PostHog sender, or ``None`` when analytics is off.

    Returns:
        The stored profile.
    """
    provision_user(conn, user.user_id)
    first_completion = _read_profile(conn, user.user_id).completed_at is None
    answers = payload.model_dump()
    conn.execute(
        pg_insert(user_profile)
        .values(user_id=user.user_id, completed_at=datetime.now(UTC), **answers)
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                **answers,
                "completed_at": func.coalesce(user_profile.c.completed_at, datetime.now(UTC)),
            },
        )
    )
    profile = _read_profile(conn, user.user_id)
    capture(
        analytics,
        # An edit of a completed profile only updates the person properties.
        event="onboarding_completed" if first_completion else PERSON_PROPERTIES_EVENT,
        user_id=user.user_id,
        properties={"source": profile.source} if first_completion else None,
        person_properties=profile.model_dump(include={"jobs", "source"}),
    )
    return profile


@router.post("/skip", response_model=UserProfileOut)
def skip_profile(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    analytics: Annotated[Sender | None, Depends(get_analytics_sender)],
) -> UserProfileOut:
    """Record the caller's one "Skip for now".

    Only the first skip is recorded: a second call changes nothing, so
    ``skipped_once_at`` always holds the time of the first skip. The frontend
    offers no skip when this time is set (``frontend/src/lib/profileGate.ts``).

    Args:
        user: The authenticated caller.
        conn: Open database connection.
        analytics: The PostHog sender, or ``None`` when analytics is off.

    Returns:
        The stored profile.
    """
    provision_user(conn, user.user_id)
    skipped = conn.execute(
        pg_insert(user_profile)
        .values(user_id=user.user_id, skipped_once_at=datetime.now(UTC))
        .on_conflict_do_nothing(index_elements=["user_id"])
        .returning(user_profile.c.user_id)
    ).first()
    if skipped is not None:
        # Only the one recorded skip is an event.
        capture(analytics, event="onboarding_skipped", user_id=user.user_id)
    return _read_profile(conn, user.user_id)
