"""Owner-scoped portfolio routes — the named grouping above the project row.

The screen calls a portfolio a **Project** and a `project` row a **Task**
(task 032 § Terms). A portfolio carries a name, a description and an owner;
its task count is derived per request rather than cached on the row.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

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
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.routers._access import (
    accessible_portfolio,
    accessible_project,
    creator_org_id,
    listing_scope,
    own_estate,
    owner_email_filter,
)
from policy_atlas.api.routers._common import resolve_owner_display
from policy_atlas.core.schema import app_user, portfolio, project

router = APIRouter(
    prefix="/api/v1/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


#: The only columns `PATCH /api/v1/portfolios/{id}` may write. Explicitly
#: **not** `visibility`: contract § 6, i.4 makes the cascade its sole writer,
#: so the field is absent from `PortfolioUpdate` and cannot reach the column
#: even if a later slice adds it to the model.
_PATCHABLE_COLUMNS = ("name", "description")


def _task_counts(
    conn: Connection, portfolio_ids: list[uuid.UUID], *, user_id: str
) -> dict[uuid.UUID, int]:
    """Count each portfolio's active, caller-visible members in one query.

    Counted unconditionally before task 033, which would have shown a
    colleague the true size of a Project whose private Tasks they cannot
    open. Contract § 8: the count includes only rows the caller may read
    **and** rows in the caller's own organisation — :func:`own_estate`, which
    is the read grade minus the admin leg, so an administrator's card keeps
    showing their own organisation's count rather than a cross-organisation
    sum.

    Args:
        conn: Open database connection.
        portfolio_ids: The portfolios to count for.
        user_id: The calling subject — the count is per-caller.

    Returns:
        Counts by portfolio id; portfolios with no visible member are absent.
    """
    if not portfolio_ids:
        return {}
    rows = conn.execute(
        select(project.c.portfolio_id, func.count())
        .where(project.c.portfolio_id.in_(portfolio_ids))
        .where(project.c.status == "active")
        .where(own_estate(project, user_id))
        .group_by(project.c.portfolio_id)
    ).all()
    return {row[0]: int(row[1]) for row in rows}


def _portfolio_out(
    row: RowMapping, task_count: int, *, user_id: str, owner_display: str | None
) -> PortfolioOut:
    """Project one portfolio row into its public contract shape for one caller.

    Args:
        row: The portfolio row.
        task_count: The caller-visible member count.
        user_id: The calling subject, for `is_owner`.
        owner_display: How to name the owner — never an email.

    Returns:
        The public portfolio shape.
    """
    return PortfolioOut(
        portfolio_id=row["portfolio_id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        task_count=task_count,
        visibility=row["visibility"],
        is_owner=row["owner_user_id"] == user_id,
        owner_display=owner_display,
    )


@router.get("", response_model=Page[PortfolioOut])
def list_portfolios(
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
    scope: Annotated[Literal["all", "mine"], Query()] = "all",
    owner_email: Annotated[str | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[PortfolioOut]:
    """List the portfolios the caller may see, with a derived task count.

    Args:
        user: The authenticated caller.
        conn: Open database connection.
        scope: `all` (default) — the caller's own rows plus their
            organisation's org-visible rows — or `mine` for owner-only.
        owner_email: Narrow to one owner's rows. **Administrators only**; any
            other caller gets 422 `validation_error`.
        page: 1-indexed page number.
        page_size: Rows per page, server-capped.

    Returns:
        One page of portfolios.

    Raises:
        HTTPException: 422 when a non-administrator passes `owner_email`.
    """
    where = [
        listing_scope(portfolio, user_id=user.user_id, scope=scope),
        owner_email_filter(conn, portfolio, user_id=user.user_id, owner_email=owner_email),
    ]
    total = conn.execute(select(func.count()).select_from(portfolio).where(*where)).scalar_one()
    rows = conn.execute(
        select(*portfolio.c, app_user.c.display_name.label("owner_display_name"))
        .select_from(
            portfolio.outerjoin(app_user, app_user.c.user_id == portfolio.c.owner_user_id)
        )
        .where(*where)
        .order_by(portfolio.c.created_at.desc(), portfolio.c.portfolio_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).mappings().all()
    counts = _task_counts(conn, [row["portfolio_id"] for row in rows], user_id=user.user_id)
    return Page(
        data=[
            _portfolio_out(
                row,
                counts.get(row["portfolio_id"], 0),
                user_id=user.user_id,
                owner_display=owner_display_for(
                    row["owner_user_id"], row["owner_display_name"]
                ),
            )
            for row in rows
        ],
        pagination=PageMeta(page=page, page_size=page_size, total_items=int(total)),
    )


@router.post("", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
def create_portfolio(
    payload: PortfolioCreate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> PortfolioOut:
    """Create one portfolio owned by the authenticated subject.

    With `from_project_id` (contract § 6, i.1) the new portfolio inherits that
    project's `visibility` **and** organisation and takes it as its first
    member, all in the request's single transaction — so the invariant "a
    project in a portfolio matches its portfolio on both" holds from the
    moment the row exists rather than being repaired afterwards.

    The source project resolves under the **write** grade, not a read grade.
    Under a read grade a same-org colleague — or, once the admin leg lands, an
    administrator — could pull a row they do not own into a portfolio and
    change its visibility, which is the concrete admin-write escape the
    contract names.

    Without `from_project_id`, the portfolio is empty and its organisation is
    stamped from the creator (contract § 7).

    Args:
        payload: The create body.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The created portfolio.

    Raises:
        HTTPException: 404 when `from_project_id` names a project the caller
            cannot read, 403 when they can read it but do not own it.
    """
    portfolio_id = uuid.uuid4()
    source = (
        accessible_project(
            conn,
            project_id=payload.from_project_id,
            user_id=user.user_id,
            write=True,
            for_update=True,
        )
        if payload.from_project_id is not None
        else None
    )
    org_id = source.row["org_id"] if source is not None else creator_org_id(conn, user.user_id)
    values: dict[str, object] = {
        "portfolio_id": portfolio_id,
        "owner_user_id": user.user_id,
        "name": payload.name,
        "description": payload.description,
        "created_at": datetime.now(UTC),
        "org_id": org_id,
    }
    if source is not None:
        values["visibility"] = source.row["visibility"]
    conn.execute(portfolio.insert().values(**values))
    if source is not None:
        conn.execute(
            update(project)
            .where(project.c.project_id == source.row["project_id"])
            .values(portfolio_id=portfolio_id, updated_at=datetime.now(UTC))
        )
    row = conn.execute(
        select(portfolio).where(portfolio.c.portfolio_id == portfolio_id)
    ).mappings().one()
    return _portfolio_out(
        row,
        1 if source is not None else 0,
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, user.user_id),
    )


@router.get("/{portfolio_id}", response_model=PortfolioOut)
def get_portfolio(
    portfolio_id: uuid.UUID,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> PortfolioOut:
    """Return one portfolio readable by the caller (owner or same-org colleague)."""
    access = accessible_portfolio(
        conn, portfolio_id=portfolio_id, user_id=user.user_id, write=False
    )
    counts = _task_counts(conn, [portfolio_id], user_id=user.user_id)
    return _portfolio_out(
        access.row,
        counts.get(portfolio_id, 0),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, access.row["owner_user_id"]),
    )


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
def update_portfolio(
    portfolio_id: uuid.UUID,
    payload: PortfolioUpdate,
    user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    conn: Annotated[Connection, Depends(get_conn)],
) -> PortfolioOut:
    """Apply the supplied portfolio fields without changing omitted fields.

    The columns this route may write are listed explicitly rather than
    splatted from the request model. Contract § 6, i.4 makes the visibility
    cascade the **only** writer of `portfolio.visibility`; a blind
    `.values(**changes)` hands the column to whatever field a later slice
    adds to `PortfolioUpdate`, and the failure it produces is silent — the
    owner sets a Project private, the UI agrees, and its Tasks stay readable
    by the whole organisation.

    Args:
        portfolio_id: The portfolio to update.
        payload: The partial update.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The updated portfolio.

    Raises:
        HTTPException: 404 when the portfolio is not the caller's.
    """
    accessible_portfolio(conn, portfolio_id=portfolio_id, user_id=user.user_id, write=True)
    supplied = payload.model_dump(exclude_unset=True)
    changes = {field: supplied[field] for field in _PATCHABLE_COLUMNS if field in supplied}
    if changes:
        conn.execute(
            update(portfolio)
            .where(portfolio.c.portfolio_id == portfolio_id)
            .values(**changes)
        )
    row = conn.execute(
        select(portfolio).where(portfolio.c.portfolio_id == portfolio_id)
    ).mappings().one()
    counts = _task_counts(conn, [portfolio_id], user_id=user.user_id)
    return _portfolio_out(
        row,
        counts.get(portfolio_id, 0),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, row["owner_user_id"]),
    )
