"""Graded row access for tenancy-aware routes (task 033).

One helper per entity, replacing the owner-only ``owned_project`` /
``owned_portfolio`` pair in ``_common``. Two grades:

- **read** = the owner leg (``owner_user_id`` matches the caller) *or* the
  same-org leg. The admin read leg (contract § 3a) is deliberately absent —
  it lands in phase 8, at the single seam marked below. Nothing here reads
  ``app_user.is_admin``.
- **write** = the owner leg only. A caller who passes the read grade but is
  not the owner gets **403 ``forbidden``**; a caller who fails the read grade
  gets the contract's indistinguishable **404**, byte-identical to an absent
  row (the BOLA rule, ``web-api.md`` § Auth boundary).

**The NULL rule** (contract § 3, the highest-blast-radius mistake available
here). A row with ``org_id IS NULL`` is reachable by its owner only; a caller
whose ``app_user.org_id`` is NULL — or who has no ``app_user`` row at all —
matches no org leg. This holds because the org leg is expressed **as a single
SQL predicate**, never as a Python comparison of two loaded values: ``None ==
None`` is ``True`` in Python and would expose every unenrolled user's work to
every other unenrolled user on day one. In SQL the equality is against the
row's non-NULL ``org_id``, so a NULL-org caller matches nothing. Pinned by
``test_two_unenrolled_callers_cannot_see_each_others_null_org_rows``.

Comparing the *loaded* ``owner_user_id`` to the caller in Python is a
different thing and is fine: it happens only after SQL has already decided
visibility, and ``owner_user_id`` NULL never equals a subject string.
"""

from __future__ import annotations

import uuid
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import Select, Table, and_, exists, literal_column, or_, select
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.sql.elements import ColumnElement

from policy_atlas.core.schema import app_user, portfolio, project

# The 404 body every failed read grade produces. Byte-identical to the string
# ``_common``'s owner-only helpers raise, so the cutover in phase 4 cannot
# change what a probing caller observes.
NOT_FOUND_DETAIL = "resource not found"

# The 403 body. 403 was pre-reserved by ``web-api.md`` § Auth boundary for
# "role failures within an owned scope"; contract § 8 spends the reservation
# on ``forbidden``.
FORBIDDEN_DETAIL = "action is not permitted"


class Access(NamedTuple):
    """A row the caller may reach, plus the grade that reached it.

    Attributes:
        row: The resolved entity row.
        is_owner: Whether the owner leg matched. Callers project this
            straight onto ``ProjectOut.is_owner`` / ``PortfolioOut.is_owner``
            and use it to decide read-only affordances.
    """

    row: RowMapping
    is_owner: bool


def _same_org_leg(table: Table, user_id: str) -> ColumnElement[bool]:
    """Build the same-org read leg as one correlated SQL predicate.

    The three conjuncts are the whole tenancy rule: the row is *in* an
    organisation, the row is shared *with* that organisation, and the caller
    is enrolled in *that same* organisation. The last is an ``EXISTS`` against
    ``app_user`` rather than a loaded value, which is what makes the NULL rule
    hold — see the module docstring.

    Args:
        table: ``project`` or ``portfolio`` — both carry ``org_id`` and
            ``visibility``.
        user_id: The caller's token subject.

    Returns:
        A boolean predicate correlated to ``table``.
    """
    return and_(
        table.c.org_id.is_not(None),
        table.c.visibility == "org",
        exists(
            select(literal_column("1"))
            .select_from(app_user)
            .where(app_user.c.user_id == user_id)
            .where(app_user.c.org_id == table.c.org_id)
            .correlate(table)
        ),
    )


def _read_legs(table: Table, user_id: str) -> ColumnElement[bool]:
    """Disjoin every read leg this phase has.

    Phase 8's admin leg (``EXISTS(app_user WHERE user_id = :me AND
    is_admin)``, unconditional on ``org_id`` and ``visibility``) is the third
    disjunct and attaches **here** and nowhere else. It is not present yet:
    contract § 3a names the closed list of legitimate ``is_admin`` readers,
    and nothing in this phase is on it.
    """
    return or_(table.c.owner_user_id == user_id, _same_org_leg(table, user_id))


def _resolve(
    conn: Connection,
    *,
    table: Table,
    base: Select[tuple[object, ...]],
    user_id: str,
    write: bool,
    for_update: bool,
) -> Access:
    """Apply the grades to an already identity- and status-filtered select.

    Args:
        conn: Open database connection.
        table: The entity table the select reads.
        base: ``select(table)`` narrowed to one row by primary key, plus any
            status filter — everything except the access legs.
        user_id: The caller's token subject.
        write: Whether the caller needs the write grade.
        for_update: Whether to lock the row. Write paths only; see the public
            helpers' docstrings.

    Returns:
        The row and the grade that reached it.

    Raises:
        ValueError: ``for_update`` without ``write`` — a programming error,
            not a caller error.
        HTTPException: 404 when no read leg matches, 403 when a read leg
            matches but the write grade is refused.
    """
    if for_update and not write:
        raise ValueError(
            "for_update is a write-path lock: a read-grade caller must never take "
            "FOR UPDATE on the owner's row (contract § 4)"
        )
    if for_update:
        # Lock through the owner leg alone: `FOR UPDATE` is bounded by
        # `owner_user_id = :caller`, so the statement can only ever lock a row
        # the caller owns and a colleague can never block the owner's own
        # rename, archive or run-start (contract § 4). A miss here — not the
        # owner, or no such row — locks nothing and costs one round trip on
        # the refusal path; the unlocked read below tells 404 from 403.
        owned = conn.execute(
            base.where(table.c.owner_user_id == user_id).with_for_update()
        ).mappings().one_or_none()
        if owned is not None:
            return Access(row=owned, is_owner=True)
    row = conn.execute(base.where(_read_legs(table, user_id))).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    # Safe in Python: SQL has already decided visibility, and a NULL
    # ``owner_user_id`` (the ``orchestrate.py`` rows) never equals a subject.
    is_owner = row["owner_user_id"] == user_id
    if write and not is_owner:
        raise HTTPException(status_code=403, detail=FORBIDDEN_DETAIL)
    return Access(row=row, is_owner=is_owner)


def accessible_project(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    user_id: str,
    write: bool = False,
    include_archived: bool = False,
    for_update: bool = False,
) -> Access:
    """Resolve one project under the caller's grade, or raise 404/403.

    Args:
        conn: Open database connection.
        project_id: Requested project identity.
        user_id: The caller's token subject.
        write: Ask for the write grade (owner only). A caller who can read the
            row but does not own it gets 403 ``forbidden``.
        include_archived: Whether an archived project can be observed.
            Unchanged from ``owned_project``.
        for_update: Take ``SELECT … FOR UPDATE`` on the row. **Write paths
            only** — passing it without ``write=True`` raises ``ValueError``,
            because a read-grade caller (a colleague holding their own chat)
            locking the owner's project row would block the owner's own
            mutations for the length of their transaction (contract § 4).
            Phase 4 fixes this per call site from an explicit table; a call
            site does not inherit it.

    Returns:
        The project row and whether the owner leg matched.

    Raises:
        HTTPException: 404 for missing, archived or unreadable rows
            (indistinguishable); 403 when the row is readable but not
            writable.
    """
    base = select(project).where(project.c.project_id == project_id)
    if not include_archived:
        base = base.where(project.c.status == "active")
    return _resolve(
        conn, table=project, base=base, user_id=user_id, write=write, for_update=for_update
    )


def accessible_portfolio(
    conn: Connection,
    *,
    portfolio_id: uuid.UUID,
    user_id: str,
    write: bool = False,
    for_update: bool = False,
) -> Access:
    """Resolve one portfolio under the caller's grade, or raise 404/403.

    Mirrors :func:`accessible_project` minus the archived leg: ``portfolio``
    has no ``status`` column, so there is nothing to widen.

    Args:
        conn: Open database connection.
        portfolio_id: Requested portfolio identity.
        user_id: The caller's token subject.
        write: Ask for the write grade (owner only).
        for_update: Take ``SELECT … FOR UPDATE`` on the row. Write paths only,
            on the same terms as :func:`accessible_project`.

    Returns:
        The portfolio row and whether the owner leg matched.

    Raises:
        HTTPException: 404 for missing or unreadable rows
            (indistinguishable); 403 when the row is readable but not
            writable.
    """
    base = select(portfolio).where(portfolio.c.portfolio_id == portfolio_id)
    return _resolve(
        conn, table=portfolio, base=base, user_id=user_id, write=write, for_update=for_update
    )
