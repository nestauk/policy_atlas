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

from policy_atlas.api.app import ApiConflict
from policy_atlas.api.auth import AuthenticatedUser
from policy_atlas.api.contract import (
    PAGE_SIZE_DEFAULT,
    PAGE_SIZE_MAX,
    Page,
    PageMeta,
    PortfolioCreate,
    PortfolioOut,
    PortfolioUpdate,
    Visibility,
)
from policy_atlas.api.deps import get_conn, get_current_user
from policy_atlas.api.identity import owner_display_for
from policy_atlas.api.routers._access import (
    OWNER_EMAIL_MAX,
    accessible_portfolio,
    accessible_project,
    creator_org_id,
    listing_scope,
    own_estate,
    owner_email_filter,
    trace_admin_listing,
)
from policy_atlas.api.routers._common import resolve_owner_display
from policy_atlas.core.schema import app_user, portfolio, portfolio_membership, project

router = APIRouter(
    prefix="/api/v1/portfolios",
    tags=["portfolios"],
    dependencies=[Depends(get_current_user)],
)


#: The only columns `PATCH /api/v1/portfolios/{id}` may write **by splat**.
#: Explicitly **not** `visibility`: contract § 6, i.4 makes
#: :func:`_cascade_visibility` its sole writer. `PortfolioUpdate` now carries
#: the field — the route routes it to the cascade by name — and this list is
#: what guarantees the generic path can never carry it to the column instead.
#: Asserted structurally by
#: `test_portfolio_visibility_never_reaches_the_column_through_the_splat`.
_PATCHABLE_COLUMNS = ("name", "description")


def _cascade_visibility(
    conn: Connection,
    *,
    portfolio_id: uuid.UUID,
    org_id: uuid.UUID | None,
    visibility: Visibility,
) -> None:
    """Set a portfolio's visibility and carry every member project with it.

    Contract § 6, i.4 — **the only writer of `portfolio.visibility`**, and
    the reason `PATCH /api/v1/portfolios/{id}` may accept the field at all.
    Two statements in the request's single transaction (`deps.get_conn`), so
    no reader ever observes a portfolio and its members disagreeing.

    **Both invariant fields are written, not just `visibility`.** A visibility
    change does not move a row between organisations, and members already
    match their portfolio's `org_id` — i.1 inherits it, the assignment path
    syncs it, and enrolment moves a person's rows as one set. So the `org_id`
    write is a no-op on every row the API itself produced. It is written
    anyway, deliberately: if a member ever *does* mismatch — an operator
    assignment, a pre-invariant row, a future path that forgets — the choice
    is between self-healing it here and leaving an exposed row in place while
    the property test reports it after the fact. "Every member follows its
    portfolio" is the rule, so the cascade makes both fields true rather than
    half of them.

    **Archived members are included** (contract § 6, i.4). They are excluded
    from the derived task count, not from the row's visibility: an archived
    Task is still readable by whoever may read it, so leaving it behind would
    keep exactly the rows nobody is looking at readable by the organisation
    after the owner made the Project private.

    Args:
        conn: Open database connection, inside the request transaction.
        portfolio_id: The portfolio whose visibility is changing.
        org_id: That portfolio's organisation — what members are synced to.
        visibility: The new visibility for the portfolio and every member.

    Raises:
        ApiConflict: 409 `visibility_conflict` when a member also belongs to
            another portfolio whose visibility differs from the new value —
            membership is many-to-many (ADR 0032), and "every member matches
            every portfolio it is in" only stays true if the cascade refuses
            to make two containing portfolios disagree.
    """
    member_ids = select(portfolio_membership.c.project_id).where(
        portfolio_membership.c.portfolio_id == portfolio_id
    )
    # ponytail: merge-time generalisation of contract 033 § 6 to many-to-many
    # membership — all containing portfolios must agree; owner to ratify.
    disagreeing = conn.execute(
        select(func.count())
        .select_from(portfolio_membership.join(
            portfolio, portfolio.c.portfolio_id == portfolio_membership.c.portfolio_id
        ))
        .where(portfolio_membership.c.project_id.in_(member_ids))
        .where(portfolio_membership.c.portfolio_id != portfolio_id)
        .where(portfolio.c.visibility != visibility)
    ).scalar_one()
    if int(disagreeing) > 0:
        raise ApiConflict(
            "visibility_conflict",
            "a task in this project is also in another project with a different "
            "visibility — align or remove that membership first",
        )
    conn.execute(
        update(portfolio)
        .where(portfolio.c.portfolio_id == portfolio_id)
        .values(visibility=visibility)
    )
    # No status filter, on purpose: archived members follow too.
    conn.execute(
        update(project)
        .where(project.c.project_id.in_(member_ids))
        .values(visibility=visibility, org_id=org_id, updated_at=datetime.now(UTC))
    )


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
        select(portfolio_membership.c.portfolio_id, func.count())
        .select_from(
            portfolio_membership.join(
                project,
                project.c.project_id == portfolio_membership.c.project_id,
            )
        )
        .where(portfolio_membership.c.portfolio_id.in_(portfolio_ids))
        .where(project.c.status == "active")
        .where(own_estate(project, user_id))
        .group_by(portfolio_membership.c.portfolio_id)
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
    owner_email: Annotated[str | None, Query(max_length=OWNER_EMAIL_MAX)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=PAGE_SIZE_MAX)] = PAGE_SIZE_DEFAULT,
) -> Page[PortfolioOut]:
    """List the portfolios the caller may see, with a derived task count.

    Args:
        user: The authenticated caller.
        conn: Open database connection.
        scope: `all` (default) — the caller's own rows plus their
            organisation's org-visible rows, and for an administrator every
            row in every organisation — or `mine` for owner-only.
        owner_email: Narrow to one owner's rows. **Administrators only**; any
            other caller gets 422 `validation_error`, as does a value longer
            than `OWNER_EMAIL_MAX` or one carrying no `@` — see
            `projects.list_projects`.
        page: 1-indexed page number.
        page_size: Rows per page, server-capped.

    Returns:
        One page of portfolios.

    Raises:
        HTTPException: 422 when a non-administrator passes `owner_email`.
    """
    scoped = listing_scope(conn, portfolio, user_id=user.user_id, scope=scope)
    where = [
        scoped.predicate,
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
    # One line per cross-organisation request (contract § 3a), emitted after
    # the page is known so it can carry the row count — including the zero an
    # `owner_email` search matching nobody produces.
    trace_admin_listing(
        scoped,
        kind="portfolio",
        user_id=user.user_id,
        scope=scope,
        owner_email=owner_email,
        page=page,
        page_size=page_size,
        row_count=len(rows),
        total_items=int(total),
    )
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
            portfolio_membership.insert().values(
                portfolio_id=portfolio_id,
                project_id=source.row["project_id"],
                created_at=datetime.now(UTC),
            )
        )
        conn.execute(
            update(project)
            .where(project.c.project_id == source.row["project_id"])
            .values(updated_at=datetime.now(UTC))
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

    **Two code paths, not one.** `name` and `description` are written by an
    explicit allow-list splat (`_PATCHABLE_COLUMNS`); `visibility` is read off
    the model **by name** and routed to :func:`_cascade_visibility`, and never
    joins the splat. Contract § 6, i.4 makes the cascade the only writer of
    `portfolio.visibility`; a blind `.values(**changes)` hands the column to
    whatever field a later slice adds to `PortfolioUpdate`, and the failure it
    produces is silent — the owner sets a Project private, the UI agrees, and
    its Tasks stay readable by the whole organisation. The field now exists on
    the model, so the allow-list is the thing keeping that true.

    `payload.visibility is not None` **is** "the caller supplied it": the
    model refuses an explicit null, so the absent value and the None value are
    the same state.

    **Owner-only, like every other write** (contract § 3): the route resolves
    through the write grade, so a same-org colleague gets 403 and an
    administrator — whose leg is a *read* leg — never reaches the cascade
    however wide their read becomes.

    The row is locked (`for_update`) because the cascade and the assignment
    path in `projects.py` write overlapping rows: without it, an assignment
    that read this portfolio's visibility a moment before the cascade
    committed would write the stale value onto the project it is assigning and
    leave an org-visible row inside a private Project.

    Args:
        portfolio_id: The portfolio to update.
        payload: The partial update. Supplying `visibility` runs the cascade.
        user: The authenticated caller.
        conn: Open database connection.

    Returns:
        The updated portfolio. Its `task_count` is the caller-visible active
        member count — see the note below on what the outcome copy may claim.

    Raises:
        HTTPException: 404 when the portfolio is unreadable, 403 when it is
            readable but not owned.
    """
    access = accessible_portfolio(
        conn, portfolio_id=portfolio_id, user_id=user.user_id, write=True, for_update=True
    )
    supplied = payload.model_dump(exclude_unset=True)
    changes = {field: supplied[field] for field in _PATCHABLE_COLUMNS if field in supplied}
    if changes:
        conn.execute(
            update(portfolio)
            .where(portfolio.c.portfolio_id == portfolio_id)
            .values(**changes)
        )
    if payload.visibility is not None:
        _cascade_visibility(
            conn,
            portfolio_id=portfolio_id,
            org_id=access.row["org_id"],
            visibility=payload.visibility,
        )
    row = conn.execute(
        select(portfolio).where(portfolio.c.portfolio_id == portfolio_id)
    ).mappings().one()
    # The i.4 outcome number. Defined through the **caller's readable set**
    # (`_task_counts` is per-caller: read grade minus admin, active only), not
    # through "how many rows the cascade touched" — the outcome copy must
    # never name rows the reader cannot see. For this route the two coincide
    # bar archived members: the write grade means the caller is the owner, and
    # a portfolio's members are always owned by its owner (032: setting
    # `portfolio_id` requires ownership of both rows), so the owner reads every
    # member. It is still derived the honest way, because "the caller happens
    # to own everything" is a property of today's write grade, not a rule.
    counts = _task_counts(conn, [portfolio_id], user_id=user.user_id)
    return _portfolio_out(
        row,
        counts.get(portfolio_id, 0),
        user_id=user.user_id,
        owner_display=resolve_owner_display(conn, row["owner_user_id"]),
    )
