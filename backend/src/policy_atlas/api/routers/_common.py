"""Private ownership and contract-projection helpers shared by API routers."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.contract import LatestRun, ProjectOut, RunOut
from policy_atlas.core.schema import (
    capability_run,
    portfolio,
    portfolio_membership,
    project,
)
from policy_atlas.evidence_base.assess.screen import effective_screen_rows


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


def owned_portfolio(
    conn: Connection,
    *,
    portfolio_id: uuid.UUID,
    user_id: str,
) -> RowMapping:
    """Return an owned portfolio or the contract's indistinguishable 404.

    Args:
        conn: Open database connection.
        portfolio_id: Requested portfolio identity.
        user_id: Authenticated owner's subject.

    Returns:
        The owned portfolio row.

    Raises:
        HTTPException: Always 404 for missing or cross-owner rows, so an
            unknown portfolio and someone else's are indistinguishable.
    """
    row = conn.execute(
        select(portfolio)
        .where(portfolio.c.portfolio_id == portfolio_id)
        .where(portfolio.c.owner_user_id == user_id)
    ).mappings().one_or_none()
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
    portfolio_ids: list[uuid.UUID] | None = None,
) -> ProjectOut:
    """Project a project row with its derived latest capability-run read model."""
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
    if portfolio_ids is None:
        portfolio_ids = memberships_for_projects(conn, [row["project_id"]])[row["project_id"]]
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
    )
