"""Private contract-projection helpers shared by API routers.

The owner-only row helpers this module used to carry (``owned_project``,
``owned_portfolio``, ``_owned_conversation``) are gone: every project-,
portfolio- and conversation-scoped route now resolves through the graded
helpers in ``_access`` (task 033). What is left is projection and display.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.contract import LatestRun, ProjectOut, RunOut
from policy_atlas.api.identity import owner_display_for
from policy_atlas.core.schema import app_user, capability_run, portfolio_membership
from policy_atlas.evidence_base.assess.screen import effective_screen_rows

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


def memberships_for_projects(
    conn: Connection, project_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Return each project's portfolio ids, ordered by membership age then id."""
    grouped: dict[uuid.UUID, list[uuid.UUID]] = {project_id: [] for project_id in project_ids}
    if not project_ids:
        return grouped
    rows = conn.execute(
        select(portfolio_membership.c.project_id, portfolio_membership.c.portfolio_id)
        .where(portfolio_membership.c.project_id.in_(project_ids))
        .order_by(portfolio_membership.c.created_at, portfolio_membership.c.portfolio_id)
    ).all()
    for project_id, portfolio_id in rows:
        grouped[project_id].append(portfolio_id)
    return grouped


def included_source_count(conn: Connection, project_id: uuid.UUID) -> int:
    """Count effective screens with status ``relevant`` for one project.

    Same population the funnel's Included / ``relevant`` count uses.
    """
    effective = effective_screen_rows()
    return int(
        conn.execute(
            select(func.count())
            .select_from(effective)
            .where(effective.c.project_id == project_id)
            .where(effective.c.status == "relevant")
        ).scalar_one()
    )


def project_out(
    conn: Connection,
    row: RowMapping | dict[str, Any],
    *,
    user_id: str,
    owner_display: str | None | object = _RESOLVE,
    portfolio_ids: list[uuid.UUID] | None = None,
    access: Literal["full", "public"] = "full",
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
        portfolio_ids: The project's portfolio memberships when the caller
            already batch-loaded them (listings do). Left unset, this
            resolves them with one lookup — correct for single-row routes,
            an N+1 in a listing.
        access: ``"public"`` when this read was served by the public leg
            (task 037) — the returned shape is then redacted
            (``is_owner=False``, ``owner_display=None``,
            ``portfolio_ids=[]``), skipping the membership lookup entirely.
            ``"full"`` (default) leaves behaviour unchanged.

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
        # Same population the funnel's ``relevant`` (Included) counts. Derived
        # per read and only once a run exists: before that, ``None`` says the
        # question has not been asked, which is not the same as a run that
        # found nothing Included.
        source_count = included_source_count(conn, row["project_id"])
    if access == "public":
        # Redacted shape (D5): no owner display, no portfolio membership —
        # skip the membership lookup entirely rather than compute and discard.
        portfolio_ids = []
        display = None
        is_owner = False
    else:
        if portfolio_ids is None:
            portfolio_ids = memberships_for_projects(conn, [row["project_id"]])[row["project_id"]]
        display = (
            resolve_owner_display(conn, row["owner_user_id"])
            if owner_display is _RESOLVE
            else cast(str | None, owner_display)
        )
        # Safe in Python: SQL has already decided visibility, and a NULL
        # ``owner_user_id`` never equals a subject string.
        is_owner = row["owner_user_id"] == user_id
    return ProjectOut(
        project_id=row["project_id"],
        name=row["name"],
        question=row["question"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
        latest_run=latest_out,
        portfolio_ids=portfolio_ids,
        source_count=source_count,
        visibility=row["visibility"],
        is_owner=is_owner,
        owner_display=display,
        is_public=row["is_public"],
        access=access,
    )
