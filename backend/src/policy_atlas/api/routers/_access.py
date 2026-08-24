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
- **colleague-mutation** (:func:`chat_mutable_project`) — the one documented
  exception to "write = owner only": the three chat mutations owner call (b)
  grants a same-org colleague. Read-shaped but deliberately admin-free, and
  it never takes a lock. See its docstring.

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
from sqlalchemy import (
    Select,
    Table,
    and_,
    exists,
    func,
    literal_column,
    or_,
    select,
    true,
)
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.sql.elements import ColumnElement

from policy_atlas.core.schema import app_user, conversation, portfolio, project

# The 404 body every failed read grade produces. Byte-identical to the string
# ``_common``'s owner-only helpers raise, so the cutover in phase 4 cannot
# change what a probing caller observes.
NOT_FOUND_DETAIL = "resource not found"

# The 403 body. 403 was pre-reserved by ``web-api.md`` § Auth boundary for
# "role failures within an owned scope"; contract § 8 spends the reservation
# on ``forbidden``.
FORBIDDEN_DETAIL = "action is not permitted"

# The 422 body a non-admin gets for passing ``owner_email``. Contract § 8 is
# explicit that this is **422 ``validation_error``**, the code the existing
# envelope map already assigns to "your parameter is wrong" — not 403, and
# not a third semantic invented for one filter.
OWNER_EMAIL_DETAIL = "owner_email is available to administrators only"


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


def own_estate(table: Table, user_id: str) -> ColumnElement[bool]:
    """The caller's own estate: the owner leg or the same-org leg, never admin.

    Deliberately **excludes** the admin leg, and will keep excluding it after
    phase 8 attaches that leg to :func:`_read_legs`. Two callers want this
    narrower predicate rather than the full read grade:

    - **``scope=mine`` is narrower still** (owner only) but shares this
      definition of the org leg, so there is one org leg in the codebase.
    - **Derived counts** (contract § 8, last line: portfolio task counts
      include only rows the caller may read *and* rows in the caller's own
      org). Today read-and-own-org is exactly this predicate; once the admin
      leg exists, an admin's portfolio count must stay their **own
      organisation's** count rather than silently summing every organisation's
      members into one number on the card.

    Args:
        table: ``project`` or ``portfolio``.
        user_id: The caller's token subject.

    Returns:
        A boolean predicate correlated to ``table``.
    """
    return or_(table.c.owner_user_id == user_id, _same_org_leg(table, user_id))


def own_conversation_leg(user_id: str) -> ColumnElement[bool]:
    """Contract § 4's own-chats filter, written out once and reused everywhere.

    The contract specifies this predicate **exactly**, because the obvious
    shorthand is wrong in a way that leaks: a bare ``created_by IS NULL``
    disjunct would hand every colleague the owner's legacy pre-033 rows. The
    NULL disjunct is therefore conjoined with the project's ownership::

        created_by = :me OR (created_by IS NULL AND project.owner_user_id = :me)

    Six call sites resolve through this (the library listing, the
    conversation-id router's grade, the turn POST, the turn cancel, the
    pending cap and its sweeper), so it has one definition and a drifted copy
    is not a thing that can exist.

    Correlated to **both** ``conversation`` and ``project``: every caller must
    have joined the two, which they all do.

    Args:
        user_id: The caller's token subject.

    Returns:
        A boolean predicate over the joined ``conversation``/``project`` pair.
    """
    return or_(
        conversation.c.created_by == user_id,
        and_(
            conversation.c.created_by.is_(None),
            project.c.owner_user_id == user_id,
        ),
    )


def own_chat_leg(user_id: str) -> ColumnElement[bool]:
    """:func:`own_conversation_leg` narrowed to chats.

    The grade the two turn mutations, the pending cap and the sweeper carry.
    Planning conversations are excluded outright: they are owner steering, and
    a planning turn resolves through ``planning.py``'s own owner-graded path,
    never through here.

    The library listing deliberately uses the *un*-narrowed
    :func:`own_conversation_leg` instead — it lists both kinds, and the owner
    must keep seeing their project's planning conversation there.

    Args:
        user_id: The caller's token subject.

    Returns:
        A boolean predicate over the joined ``conversation``/``project`` pair.
    """
    return and_(conversation.c.kind == "chat", own_conversation_leg(user_id))


def _read_legs(table: Table, user_id: str) -> ColumnElement[bool]:
    """Disjoin every read leg this phase has.

    Phase 8's admin leg (``EXISTS(app_user WHERE user_id = :me AND
    is_admin)``, unconditional on ``org_id`` and ``visibility``) is the third
    disjunct and attaches **here** and nowhere else. It is not present yet:
    contract § 3a names the closed list of legitimate ``is_admin`` readers,
    and nothing in this phase is on it.

    Row reads (:func:`accessible_project`, :func:`accessible_portfolio`) and
    the listings (:func:`listing_scope`) both resolve through this function,
    so the org leg has exactly one definition and phase 8 widens both by
    editing one line.
    """
    return own_estate(table, user_id)


def may_read_project(conn: Connection, *, project_id: uuid.UUID, user_id: str) -> bool:
    """Re-check the read grade on one project as a cheap boolean (contract § 5).

    The SSE tail's re-authorisation. :func:`accessible_project` is the wrong
    shape for a loop that runs every poll interval — it selects the whole row,
    raises ``HTTPException`` to report a refusal, and applies the archived
    filter — so this is the same question asked as a boolean.

    **It resolves through :func:`_read_legs`, deliberately the same function
    :func:`_resolve` uses**, and that is the whole point: a second tenancy
    predicate written out in ``sse.py`` would be a copy free to drift from the
    one the snapshot enforced, which is exactly the failure the closed helper
    design exists to prevent. Phase 8's admin leg attaches inside
    :func:`_read_legs`, so an admin's stream starts being governed by
    ``is_admin`` — and closes when the flag is revoked — with no edit here.

    **No status filter, on purpose.** ``accessible_project`` excludes archived
    rows because *opening* something archived is not a thing the API offers;
    an already-open stream is different. The owner archiving their own project
    emits a ``project.updated`` frame and must not have their own stream shot
    out from under them by the same action. Only the tenancy legs revoke.

    One query, one round trip: the project is found by primary key and the org
    leg's ``EXISTS`` probes ``app_user``'s primary key, so both sides are index
    lookups and neither depends on the project's event volume.

    Args:
        conn: Open database connection.
        project_id: The project the open stream is bound to.
        user_id: The caller's token subject.

    Returns:
        Whether the caller may still read this project.
    """
    return (
        conn.execute(
            select(literal_column("1"))
            .select_from(project)
            .where(project.c.project_id == project_id)
            .where(_read_legs(project, user_id))
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def listing_scope(table: Table, *, user_id: str, scope: str) -> ColumnElement[bool]:
    """Build the tenancy predicate for a paginated listing.

    Reader **(ii)** of contract § 3a's closed list of ``is_admin`` readers —
    named there because phase 8's admin branch attaches to the legs this
    function disjoins. **In this phase it reads nothing**: ``all`` resolves
    through :func:`_read_legs`, which has no admin leg yet.

    Args:
        table: ``project`` or ``portfolio``.
        user_id: The caller's token subject.
        scope: ``"all"`` (the default the route declares — owner ∪ the org's
            org-visible rows) or ``"mine"`` (owner only, the pre-033
            behaviour). The route's ``Literal`` type is what rejects anything
            else; a value that reached here unvalidated would be treated as
            ``"all"``, which is why the route owns the validation.

    Returns:
        A boolean predicate correlated to ``table``, to be ANDed with the
        listing's status/portfolio/owner filters.
    """
    if scope == "mine":
        return table.c.owner_user_id == user_id
    return _read_legs(table, user_id)


def owner_email_filter(
    conn: Connection,
    table: Table,
    *,
    user_id: str,
    owner_email: str | None,
) -> ColumnElement[bool]:
    """Gate and resolve the admin-only ``owner_email`` listing filter.

    Reader **(iii)** of contract § 3a's closed list — kept as one small named
    function precisely so phase 8's structural assertion can enumerate the
    readers rather than assert "nowhere else", which rev 2.0 got wrong.

    Refusal is **422 ``validation_error``** (contract § 8), not 403: the
    caller passed a parameter they may not use, which is the semantic the
    envelope map already carries. An unenrolled caller has no ``app_user``
    row at all and is refused on the same branch.

    An address that matches no ``app_user`` row yields an empty page rather
    than an error, so an admin cannot use the status code to learn whether an
    address is known to the system. (Phase 8's trace emits a line for that
    zero-row request for the same reason.)

    Resolution is an ``IN`` over a subquery rather than "look up the one
    matching subject", because **``app_user.email`` carries no unique
    constraint**: the address is ops-resolved and can go stale (contract § 3b
    names staleness explicitly), so two rows sharing one address is a state
    the schema permits. Fetching it with ``scalar_one_or_none`` would turn
    that into a 500 on the admin's support path; the subquery filters to
    every matching owner instead, which is also the more useful answer.

    Args:
        conn: Open database connection.
        table: ``project`` or ``portfolio``.
        user_id: The caller's token subject.
        owner_email: The requested owner's address, or ``None`` when the
            caller did not pass the filter.

    Returns:
        ``true()`` when no filter was requested, otherwise a predicate
        narrowing ``table`` to that owner's rows.

    Raises:
        HTTPException: 422 when a non-admin (or unenrolled) caller passes
            ``owner_email``.
    """
    if owner_email is None:
        return true()
    is_admin = conn.execute(
        select(app_user.c.is_admin).where(app_user.c.user_id == user_id)
    ).scalar_one_or_none()
    if not is_admin:
        raise HTTPException(status_code=422, detail=OWNER_EMAIL_DETAIL)
    # Addresses are case-insensitive in practice and ops type them by hand;
    # folding both sides keeps the filter usable without a schema change.
    return table.c.owner_user_id.in_(
        select(app_user.c.user_id).where(
            func.lower(app_user.c.email) == owner_email.strip().lower()
        )
    )


def creator_org_id(conn: Connection, user_id: str) -> uuid.UUID | None:
    """Return the organisation a newly created row should be stamped with.

    Contract § 7: ``POST /projects`` and ``POST /portfolios`` stamp ``org_id``
    from the creator's ``app_user.org_id`` — **NULL when the creator is
    unenrolled**, which is also what a caller with no ``app_user`` row gets.
    A NULL-``org_id`` row is reachable by its owner (and, from phase 8, an
    admin) and by nobody else, so the unenrolled user's dark launch holds.

    Args:
        conn: Open database connection.
        user_id: The creator's token subject.

    Returns:
        The creator's organisation, or ``None``.
    """
    org_id = conn.execute(
        select(app_user.c.org_id).where(app_user.c.user_id == user_id)
    ).scalar_one_or_none()
    return org_id


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


def chat_mutable_project(conn: Connection, *, project_id: uuid.UUID, user_id: str) -> Access:
    """Resolve one project under the **colleague-mutation** grade, or 404.

    The grade owner call (b) invented and contract § 4 spends on exactly three
    mutations — create a conversation, post a turn to your own conversation,
    cancel your own turn. It sits between the two grades
    :func:`accessible_project` offers, and it exists as its own function for
    one reason: it must **never** widen to the admin leg.

    - Wider than **write**, which is owner-only: a same-org colleague passes.
    - Narrower than **read**, which phase 8 widens with ``is_admin``: an admin
      is not a colleague and receives none of the three mutations (contract
      § 3, and the acceptance check "is refused every mutation including chat
      creation and turn POST"). Resolving through :func:`own_estate` rather
      than :func:`_read_legs` is what makes that structurally true *now*,
      rather than true only until phase 8 attaches the third leg.

    **No lock, ever, and no ``for_update`` parameter to pass one.** Contract
    § 4: a colleague chat path that took ``FOR UPDATE`` on the owner's project
    row would block the owner's own rename, archive and run-start for the
    length of the colleague's transaction. The turn path locks the
    *conversation* row instead (``chat_turns._phase_one_turn``).

    Archived projects are excluded, exactly as the retired ``owned_project``
    excluded them: a chat is a live conversation about live work.

    Args:
        conn: Open database connection.
        project_id: Requested project identity.
        user_id: The caller's token subject.

    Returns:
        The project row and whether the owner leg matched.

    Raises:
        HTTPException: 404 for a missing, archived or unreachable row. There
            is no 403 on this grade — a caller who fails it is not told the
            row exists.
    """
    row = conn.execute(
        select(project)
        .where(project.c.project_id == project_id)
        .where(project.c.status == "active")
        .where(own_estate(project, user_id))
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    return Access(row=row, is_owner=row["owner_user_id"] == user_id)


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
