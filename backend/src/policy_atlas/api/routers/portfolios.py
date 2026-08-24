"""Owner-scoped portfolio routes — the named grouping above the project row.

The screen calls a portfolio a **Project** and a `project` row a **Task**
(task 032 § Terms). A portfolio carries a name, a description and an owner;
its task count is derived per request rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection, RowMapping

from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    Page,
    PageMeta,
    PortfolioCreate,
    PortfolioOut,
    PortfolioUpdate,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.routers._common import owned_portfolio
from policy_atlas.core.schema import portfolio, project

router = APIRouter(
    prefix="/api/v1/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


def _task_counts(conn: Connection, portfolio_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    """Count each portfolio's active projects in one query."""
    if not portfolio_ids:
        return {}
    rows = conn.execute(
        select(project.c.portfolio_id, func.count())
        .where(project.c.portfolio_id.in_(portfolio_ids))
        .where(project.c.status == "active")
        .group_by(project.c.portfolio_id)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def _portfolio_out(row: RowMapping, task_count: int) -> PortfolioOut:
    """Project one portfolio row into its public contract shape."""
    return PortfolioOut(
        portfolio_id=row["portfolio_id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        task_count=task_count,
    )


@router.get("", response_model=Page[PortfolioOut])
def list_portfolios(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[PortfolioOut]:
    """List the authenticated user's portfolios with a derived task count."""
    where = portfolio.c.owner_user_id == user.user_id
    total = conn.execute(select(func.count()).select_from(portfolio).where(where)).scalar_one()
    rows = conn.execute(
        select(portfolio)
        .where(where)
        .order_by(portfolio.c.created_at.desc(), portfolio.c.portfolio_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    counts = _task_counts(conn, [row["portfolio_id"] for row in rows])
    return Page(
        data=[_portfolio_out(row, counts.get(row["portfolio_id"], 0)) for row in rows],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    payload: PortfolioCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> PortfolioOut:
    """Create one portfolio owned by the authenticated subject."""
    portfolio_id = uuid.uuid4()
    conn.execute(
        portfolio.insert().values(
            portfolio_id=portfolio_id,
            owner_user_id=user.user_id,
            name=payload.name,
            description=payload.description,
            created_at=datetime.now(UTC),
        )
    )
    row = conn.execute(
        select(portfolio).where(portfolio.c.portfolio_id == portfolio_id)
    ).mappings().one()
    return _portfolio_out(row, 0)


@router.get("/{portfolio_id}", response_model=PortfolioOut)
def get_portfolio(
    portfolio_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> PortfolioOut:
    """Return one portfolio when it belongs to the caller."""
    row = owned_portfolio(conn, portfolio_id=portfolio_id, user_id=user.user_id)
    counts = _task_counts(conn, [portfolio_id])
    return _portfolio_out(row, counts.get(portfolio_id, 0))


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
def update_portfolio(
    portfolio_id: uuid.UUID,
    payload: PortfolioUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> PortfolioOut:
    """Apply the supplied portfolio fields without changing omitted fields."""
    owned_portfolio(conn, portfolio_id=portfolio_id, user_id=user.user_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes:
        conn.execute(
            update(portfolio)
            .where(portfolio.c.portfolio_id == portfolio_id)
            .values(**changes)
        )
    row = conn.execute(
        select(portfolio).where(portfolio.c.portfolio_id == portfolio_id)
    ).mappings().one()
    counts = _task_counts(conn, [portfolio_id])
    return _portfolio_out(row, counts.get(portfolio_id, 0))
