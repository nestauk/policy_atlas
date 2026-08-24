"""Private ownership and contract-projection helpers shared by API routers."""

from __future__ import annotations

import uuid
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.contract import LatestRun, ProjectOut, RunOut
from policy_atlas.api.identity import owner_display_for
from policy_atlas.core.schema import (
    app_user,
    capability_run,
    project,
    project_source_snapshot,
)

#: Sentinel for "resolve the owner's display name yourself". Distinct from
#: ``None``, which is a legitimate resolved value (an ownerless row).
_RESOLVE = object()


def resolve_owner_display(conn: Connection, owner_user_id: str | None) -> str | None:
    """Look up one row owner's display name.

    The single-row path. Listings must **not** call this per row — they join
    ``app_user`` once and hand the joined value to :func:`project_out` — but
    for a route that has already loaded exactly one row, one more indexed
    primary-key lookup is cheaper than reshaping the query.

    Args:
        conn: Open database connection.
        owner_user_id: The row's owner, or ``None`` for an ownerless row.

    Returns:
        The owner's display name, the sub rendering when they have no
        ``app_user`` row, or ``None`` when the row has no owner. Never an
        email (contract § 3b).
    """
    if owner_user_id is None:
        return None
    display_name = conn.execute(
        select(app_user.c.display_name).where(app_user.c.user_id == owner_user_id)
    ).scalar_one_or_none()
    return owner_display_for(owner_user_id, display_name)


def owned_project(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    user_id: str,
    include_archived: bool = False,
    for_update: bool = False,
) -> RowMapping:
    """Return an owned project or the contract's indistinguishable 404.

    Args:
        conn: Open database connection.
        project_id: Requested project identity.
        user_id: Authenticated owner's subject.
        include_archived: Whether an archived project can be observed.
        for_update: Whether the caller needs a row lock for a mutation.

    Returns:
        The owned project row.

    Raises:
        HTTPException: Always 404 for missing, archived, or cross-owner rows.
    """
    statement = select(project).where(project.c.project_id == project_id).where(
        project.c.owner_user_id == user_id
    )
    if not include_archived:
        statement = statement.where(project.c.status == "active")
    if for_update:
        statement = statement.with_for_update()
    row = conn.execute(statement).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="resource not found")
    return row


def run_out(row: RowMapping | dict[str, Any]) -> RunOut:
    """Project one capability-run row into its public contract shape."""
    return RunOut(
        capability_run_id=row["capability_run_id"],
        project_id=row["project_id"],
        plan_id=row["plan_id"],
        plan_version=row["plan_version"],
        status=row["status"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
    )


def project_out(
    conn: Connection,
    row: RowMapping | dict[str, Any],
    *,
    user_id: str,
    owner_display: str | None | object = _RESOLVE,
) -> ProjectOut:
    """Project a project row with its derived read models, for one caller.

    Two of the three task-033 fields are **caller-relative**, not properties
    of the row: ``is_owner`` answers "does *this* caller own it", and
    ``owner_display`` is what *this* caller is shown about the owner. That is
    why the caller's subject is a required argument rather than something the
    row carries.

    Args:
        conn: Open database connection.
        row: The project row.
        user_id: The calling subject, for ``is_owner``.
        owner_display: The owner's display name when the caller already
            joined ``app_user`` (listings do, to avoid one query per row).
            Left unset, this resolves it with one lookup — correct for
            single-row routes, an N+1 in a listing.

    Returns:
        The public project shape.
    """
    latest = conn.execute(
        select(capability_run)
        .where(capability_run.c.project_id == row["project_id"])
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).mappings().one_or_none()
    latest_out = None
    source_count = None
    if latest is not None:
        latest_out = LatestRun(
            capability_run_id=latest["capability_run_id"],
            status=latest["status"],
            started_at=latest["started_at"],
            ended_at=latest["ended_at"],
        )
        # Same population the funnel's ``found`` counts. Derived per read and
        # only once a run exists: before that, ``None`` says the question has
        # not been asked, which is not the same as a run that found nothing.
        source_count = int(
            conn.execute(
                select(func.count())
                .select_from(project_source_snapshot)
                .where(project_source_snapshot.c.project_id == row["project_id"])
            ).scalar_one()
        )
    display = (
        resolve_owner_display(conn, row["owner_user_id"])
        if owner_display is _RESOLVE
        else cast(str | None, owner_display)
    )
    return ProjectOut(
        project_id=row["project_id"],
        name=row["name"],
        question=row["question"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
        latest_run=latest_out,
        portfolio_id=row["portfolio_id"],
        source_count=source_count,
        visibility=row["visibility"],
        # Safe in Python: SQL has already decided visibility, and a NULL
        # ``owner_user_id`` never equals a subject string.
        is_owner=row["owner_user_id"] == user_id,
        owner_display=display,
    )
