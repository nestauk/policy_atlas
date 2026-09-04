"""Graded row access for tenancy-aware routes (task 033).

One helper per entity, replacing the owner-only ``owned_project`` /
``owned_portfolio`` pair in ``_common``. Two grades:

- **read** = the owner leg (``owner_user_id`` matches the caller) *or* the
  same-org leg *or* the **admin leg** (contract § 3a: ``app_user.is_admin``,
  any row, any organisation, any visibility). All three disjoin at the single
  seam :func:`_read_legs`, so row reads and the SSE tail widened together when
  phase 8 attached the third. The listings hold the same grade but assemble it
  from one Python read of the flag rather than from that predicate, because
  they owe an audit line and the two must not be able to disagree — see
  :func:`listing_scope`.
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

**The admin trace lives here too** (contract § 3a). The privileged read has
no user-facing disclosure — the privacy notice was deliberately not edited
(contract § 12) — so the log line *is* the control, and it is emitted from
the same functions that grant the access rather than from each route, which
is what makes "nothing is emitted for a read the caller was already entitled
to" a property of the grade rather than of a caller's diligence. The three
shapes are :func:`trace_admin_read`, :func:`trace_admin_listing` and
:func:`trace_admin_stream_read`.
"""

from __future__ import annotations

import uuid
from typing import NamedTuple

import structlog
from fastapi import HTTPException
from sqlalchemy import (
    Select,
    Table,
    and_,
    exists,
    false,
    func,
    literal_column,
    or_,
    select,
    true,
)
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.sql.elements import ColumnElement

from policy_atlas.core.schema import app_user, conversation, portfolio, project

log = structlog.get_logger()

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

# The 422 body for a value that is not an address at all. Same status and same
# code as the refusal above, deliberately: both are "your parameter is wrong",
# and the filter has no third semantic to spend.
OWNER_EMAIL_MALFORMED_DETAIL = "owner_email must be an email address"

#: Longest ``owner_email`` the listings accept, and the reason there is a bound
#: at all: the value is logged **verbatim** by :func:`trace_admin_listing`, so
#: unbounded input on the query string is unbounded input in the audit trail —
#: the one control the admin leg has. 254 is the maximum length of an address
#: that can be delivered (RFC 5321's 256-octet path minus the angle brackets),
#: so it refuses nothing anyone could actually be looking for.
OWNER_EMAIL_MAX = 254

#: Label the graded read query carries **alongside** the row: did the owner or
#: same-org leg match on its own?
#:
#: This is the one-query leg detection the admin trace needs. The alternative —
#: resolve the row, then ask a second question ("was this caller entitled
#: anyway?") — is a second round trip on every graded read in the API, and a
#: second copy of the tenancy predicate free to drift from the one that
#: actually granted the row. Selecting :func:`own_estate` as a boolean column
#: beside the row means SQL answers both questions in the statement that
#: already ran: the row came back, so *some* leg matched; this column says
#: whether it was one the caller held without ``is_admin``.
#:
#: The extra key rides along in the returned ``RowMapping``. Every consumer
#: reads the row by column name, so it is inert — and it is named distinctly
#: enough that no present or future column can collide with it.
_OWN_LEG = "own_leg_matched"


class Access(NamedTuple):
    """A row the caller may reach, plus the grade that reached it.

    Attributes:
        row: The resolved entity row.
        is_owner: Whether the owner leg matched. Callers project this
            straight onto ``ProjectOut.is_owner`` / ``PortfolioOut.is_owner``
            and use it to decide read-only affordances.
        via_admin: Whether the **admin** leg is what reached this row — i.e.
            the caller would have been refused without ``is_admin``. Defaults
            ``False`` so the admin-free helpers (:func:`chat_mutable_project`)
            construct unchanged. :func:`_resolve` has already emitted the
            trace line when this is true; the field exists so a caller can
            reason about the grade, not so each route can remember to log.
        via_public: Whether the public leg reached this project. Public-leg
            responses are redacted and never emit an admin-read trace.
    """

    row: RowMapping
    is_owner: bool
    via_admin: bool = False
    via_public: bool = False


class ReadCheck(NamedTuple):
    """The boolean re-check's answer, plus which leg carried it.

    :func:`may_read_project` returns this rather than a bare ``bool`` because
    the SSE tail owes a trace line per re-authorisation the admin leg carried
    (contract § 3a) and must not ask a second question to find out.

    Attributes:
        allowed: Whether the caller may still read the project.
        via_admin: Whether the admin leg is what allowed it.
    """

    allowed: bool
    via_admin: bool


class ListingScope(NamedTuple):
    """A listing's tenancy predicate, plus whether the admin leg widened it.

    Attributes:
        predicate: The boolean to AND into the listing's filters.
        via_admin: Whether this listing runs on the admin leg — i.e. it spans
            organisations. ``scope=mine`` is never on the admin leg (it is the
            owner column and nothing else), so this is ``False`` there without
            a query.
    """

    predicate: ColumnElement[bool]
    via_admin: bool


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


def admin_read_leg(user_id: str) -> ColumnElement[bool]:
    """Build the admin read leg as one uncorrelated SQL predicate.

    **Code-level reader of ``app_user.is_admin`` #1**, and the whole of
    contract § 3a's semantic reader **(i)**, the row-access helper's admin leg
    — every graded row read and the SSE tail's re-check reach the flag through
    here, because all of them resolve through :func:`_read_legs`. Reader
    **(ii)**, the listing scope resolver, reaches it through :func:`_is_admin`
    instead and for a stated reason: a listing owes an audit line, and a
    predicate holding its own copy of the flag can disagree with the line. The
    closed list is asserted structurally by
    ``test_only_the_named_code_sites_read_the_is_admin_flag``.

    Unlike :func:`_same_org_leg` this predicate says **nothing** about the
    row: not its ``org_id``, not its ``visibility``, not its owner. That is
    the contract's "any row, any org, any visibility" written as SQL, and it
    is why the leg also reaches ``org_id IS NULL`` rows — including the
    ``runtime/orchestrate.py`` rows that carry no owner at all (contract § 11
    names this; the deferred "unreachable" posture is amended by it).

    What it does **not** do is bypass the archived/status filters. Those live
    in the ``base`` select the caller built, before any leg is applied, so
    ``include_archived`` stays exactly as caller-controlled for an admin as
    for anyone else.

    Args:
        user_id: The caller's token subject.

    Returns:
        A boolean predicate, correlated to nothing.
    """
    return exists(
        select(literal_column("1"))
        .select_from(app_user)
        .where(app_user.c.user_id == user_id)
        .where(app_user.c.is_admin.is_(True))
    )


def _is_admin(conn: Connection, user_id: str) -> bool:
    """Ask whether one caller holds the support role, as a Python boolean.

    **Code-level reader of ``app_user.is_admin`` #2**, serving contract
    § 3a's semantic readers **(iii)** the ``owner_email`` filter gate and
    **(ii)** the listing scope resolver *in full* — its predicate as well as
    its trace decision. Both need the answer in Python — one to raise 422, one
    to decide whether the request owes an audit line — and neither can get it
    from a SQL leg.

    Kept as *one* function rather than two inline queries so the structural
    assertion has a closed list to name. An unenrolled caller, or one with no
    ``app_user`` row at all, is not an administrator.

    Args:
        conn: Open database connection.
        user_id: The caller's token subject.

    Returns:
        Whether the caller holds ``is_admin``.
    """
    return bool(
        conn.execute(
            select(app_user.c.is_admin).where(app_user.c.user_id == user_id)
        ).scalar_one_or_none()
    )


def _row_identity(table: Table, row: RowMapping) -> str:
    """Render a resolved row's primary key for the trace line."""
    (key,) = table.primary_key.columns.keys()
    return str(row[key])


def trace_admin_read(*, kind: str, row_id: str, user_id: str) -> None:
    """Record one direct row read served by the admin leg (contract § 3a).

    **One line per row**, and only for a row the caller would *not* have
    reached without ``is_admin`` — a reader-entitled read emits nothing, which
    is what keeps the log an audit trail of the privilege rather than of the
    traffic.

    Emitted for a row the admin leg disclosed on a **write**-graded route too,
    where the outcome is 403. The line records what the leg revealed, and the
    leg revealed the row's existence: a 403 tells the admin the row is there,
    a 404 would not. Recording it also puts an administrator's *attempted*
    mutations in the trail, which is the more useful audit property. The event
    name stays ``admin_read`` because a read grade is all that was ever
    granted.

    Args:
        kind: ``"project"``, ``"portfolio"`` or ``"conversation"``.
        row_id: The row's primary key, rendered.
        user_id: The administrator's token subject.
    """
    log.info("admin_read", user_id=user_id, kind=kind, row_id=row_id)


def trace_admin_listing(
    scoped: ListingScope,
    *,
    kind: str,
    user_id: str,
    scope: str,
    owner_email: str | None,
    page: int,
    page_size: int,
    row_count: int,
    total_items: int,
) -> None:
    """Record one listing or search request served across organisations.

    **One line per request**, not per row — "one line per read" is meaningless
    for a listing, and a per-row grain would make a 200-row page unreadable in
    the log and a zero-row page invisible in it.

    **A zero-result request still emits its line** (rubric 17). That is the
    whole point of the request grain: ``owner_email`` returns an empty page
    rather than a 404 precisely so the status code is not an oracle for "does
    this address own anything", and an unlogged empty page would restore the
    oracle in a form nobody can see.

    **The address is logged verbatim.** ``owner_email`` is the filter, and an
    audit line that cannot say what was searched for is not an audit line.
    Contract § 3b already makes the address ops- and admin-facing; this log is
    read by the same people. It is never rendered to another user.

    Args:
        scoped: The resolver's answer — the line is emitted only when the
            admin leg is what widened this listing.
        kind: ``"project"`` or ``"portfolio"``.
        user_id: The administrator's token subject.
        scope: The requested scope, as the route received it.
        owner_email: The requested owner filter, or ``None``.
        page: The 1-indexed page requested.
        page_size: The page size requested.
        row_count: How many rows this page actually returned — ``0`` for the
            zero-result search, which still emits.
        total_items: How many rows matched in total.
    """
    if not scoped.via_admin:
        return
    log.info(
        "admin_listing",
        user_id=user_id,
        kind=kind,
        scope=scope,
        owner_email=owner_email,
        page=page,
        page_size=page_size,
        row_count=row_count,
        total_items=total_items,
    )


def trace_admin_stream_read(*, user_id: str, project_id: uuid.UUID) -> None:
    """Record one SSE re-authorisation batch carried by the admin leg.

    **One line per batch, never one per frame** (contract § 3a). A stream is
    unbounded; a per-frame line would drown the trail it is meant to be. The
    *subscribe* is already covered — ``_snapshot`` resolves through
    :func:`accessible_project`, so opening an admin-carried stream emits an
    ordinary ``admin_read`` line for the project row, and this event covers
    only the tail's repeated re-checks.

    Args:
        user_id: The administrator's token subject.
        project_id: The project being streamed.
    """
    log.info(
        "admin_stream_read", user_id=user_id, kind="project", row_id=str(project_id)
    )


def own_estate(table: Table, user_id: str) -> ColumnElement[bool]:
    """The caller's own estate: the owner leg or the same-org leg, never admin.

    Deliberately **excludes** the admin leg, which is now attached to
    :func:`_read_legs` alongside it. Three callers want this narrower
    predicate rather than the full read grade:

    - **``scope=mine`` is narrower still** (owner only) but shares this
      definition of the org leg, so there is one org leg in the codebase.
    - **Derived counts** (contract § 8, last line: portfolio task counts
      include only rows the caller may read *and* rows in the caller's own
      org). An admin's portfolio card keeps showing their **own
      organisation's** count rather than silently summing every
      organisation's members into one number.
    - **The chat mutations** (:func:`chat_mutable_project`, and
      ``own_chat_leg``'s call sites): an admin is not a colleague and receives
      none of the three.

    It is also the boolean the graded read selects alongside the row (see
    :data:`_OWN_LEG`): "would this caller have reached the row without
    ``is_admin``" is exactly this predicate, which is why the trace can be
    decided in the statement that already resolved the row.

    Args:
        table: ``project`` or ``portfolio``.
        user_id: The caller's token subject.

    Returns:
        A boolean predicate correlated to ``table``.
    """
    return or_(table.c.owner_user_id == user_id, _same_org_leg(table, user_id))


def _own_leg_column(table: Table, user_id: str) -> ColumnElement[bool]:
    """Select :func:`own_estate` as a **non-nullable** boolean, labelled :data:`_OWN_LEG`.

    The ``COALESCE`` is not decoration. :func:`own_estate`'s owner disjunct is
    ``owner_user_id = :caller``, and ``owner_user_id`` is nullable — the
    ``runtime/orchestrate.py`` CLI rows carry no owner at all (contract § 11).
    On such a row with ``org_id IS NULL`` the owner disjunct is SQL NULL and
    the org leg is ``FALSE``, so the whole predicate evaluates to **NULL**, not
    ``FALSE``. Three-valued logic then breaks the two readers of this column in
    different ways:

    - :func:`may_read_project` selects it as the *only* column, so
      ``scalar_one_or_none()`` read the NULL as "no row" and an
      administrator's open SSE stream closed as revoked on every
      re-authorisation — while their plain ``GET`` on the same project
      succeeded, because :func:`_resolve` selects the row beside it.
    - :func:`_resolve` reads ``not row[_OWN_LEG]``, and ``not None`` is
      ``True`` — right on this row (nothing but the admin leg reaches an
      ownerless row) and right only by accident.

    NULL and ``FALSE`` mean the same thing for this column either way: "no leg
    the caller held without ``is_admin`` matched". Saying so in SQL is what
    makes both readers correct by construction rather than by case analysis.

    Args:
        table: ``project`` or ``portfolio``.
        user_id: The caller's token subject.

    Returns:
        The labelled boolean column to select beside — or instead of — the row.
    """
    return func.coalesce(own_estate(table, user_id), false()).label(_OWN_LEG)


def own_conversation_leg(user_id: str) -> ColumnElement[bool]:
    """Contract § 4's own-chats filter, written out once and reused everywhere.

    The contract specifies this predicate **exactly**, because the obvious
    shorthand is wrong in a way that leaks: a bare ``created_by IS NULL``
    disjunct would hand every colleague every unattributed row. The NULL
    disjunct is therefore conjoined with the project's ownership::

        created_by = :me OR (created_by IS NULL AND project.owner_user_id = :me)

    **A NULL ``created_by`` is not only a legacy state.** The migration
    backfilled pre-033 rows from their project's owner, but
    ``runtime/conversation_lifecycle.ensure_active_planning_conversation``
    still inserts every planning conversation without the column — they are
    minted by the runtime rather than by a request, so there is no acting
    subject to record. So this disjunct is the live rule for planning
    conversations (which is exactly how the owner reaches their own project's
    planning lineage, and why no colleague ever can) and a legacy rule for
    chats, whose creator has been recorded since this slice.
    ``conversations.list_conversations`` states the same thing from the
    listing's side.

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
    """Disjoin every read leg: owner, same-org, and admin.

    **The one seam for a single row.** Row reads
    (:func:`accessible_project`, :func:`accessible_portfolio`) and the SSE
    tail's re-authorisation (:func:`may_read_project`) resolve through this
    function, so the admin leg attached to both by adding one disjunct here
    and nowhere else — and revoking ``is_admin`` withdraws it from both just
    as narrowly.

    :func:`listing_scope` deliberately does **not** resolve through here. A
    listing owes an audit line, so it must know *in Python* whether the admin
    leg widened it, and a predicate carrying a second, independent read of the
    flag can disagree with that answer across a concurrent grant or revoke.
    It reads the flag once and derives both from it; see its docstring.

    The admin leg is unconditional on the row (:func:`admin_read_leg`); the
    archived/status filters are applied by the caller's ``base`` select before
    any leg runs, so they stay caller-controlled.
    """
    return or_(own_estate(table, user_id), admin_read_leg(user_id))


def may_read_project(
    conn: Connection, *, project_id: uuid.UUID, user_id: str
) -> ReadCheck:
    """Re-check the read grade on one project as a cheap boolean (contract § 5).

    The SSE tail's re-authorisation. :func:`accessible_project` is the wrong
    shape for a loop that runs every poll interval — it selects the whole row,
    raises ``HTTPException`` to report a refusal, and applies the archived
    filter — so this is the same question asked as a boolean.

    **It resolves through :func:`_read_legs`, deliberately the same function
    :func:`_resolve` uses**, and that is the whole point: a second tenancy
    predicate written out in ``sse.py`` would be a copy free to drift from the
    one the snapshot enforced, which is exactly the failure the closed helper
    design exists to prevent. The admin leg attaches inside
    :func:`_read_legs`, so an admin's stream is governed by ``is_admin`` — and
    closes when the flag is revoked — with no leg written out here.

    **It reports which leg answered**, in the same statement: the read query
    selects :func:`own_estate` as a boolean column, so "may they still read"
    and "is this batch on the admin leg" cost one round trip between them.
    The tail owes a trace line per admin-carried batch (contract § 3a) and
    :func:`trace_admin_stream_read` is where that line is shaped; the tail
    calls it rather than this function emitting, because the batch — not the
    grade check — is the unit being recorded.

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
        Whether the caller may still read this project, and which leg said so.
    """
    own_leg = conn.execute(
        select(_own_leg_column(project, user_id))
        .select_from(project)
        .where(project.c.project_id == project_id)
        .where(_read_legs(project, user_id))
        .limit(1)
    ).scalar_one_or_none()
    if own_leg is None:
        return ReadCheck(allowed=False, via_admin=False)
    # `own_leg` is a real ``False`` when the admin leg is what matched, which
    # is why the miss is distinguished by ``is None`` and not by falsiness —
    # and why the column is COALESCEd (:func:`_own_leg_column`): an ownerless
    # row made the predicate NULL, which arrived here as ``is None`` and closed
    # every administrator's stream on a project the same leg let them GET.
    return ReadCheck(allowed=True, via_admin=not own_leg)


def readable_project_exists(project_id: uuid.UUID, user_id: str) -> ColumnElement[bool]:
    """The read grade on one project, as a predicate to AND into another select.

    :func:`may_read_project` answers "may they still read it" as a *value*, and
    a value is one statement behind whatever the caller does next. The SSE tail
    had exactly that gap: it authorised in one statement and read the event
    batch in a second, so a revocation committing between them still disclosed
    one batch of frames before the stream closed. Gating the batch select with
    this predicate closes the window inside a single statement — the rows
    cannot be read unless the grade holds at the moment they are read.

    Both are kept, and they are not redundant: this predicate makes a batch
    empty, while :func:`may_read_project` is what ends the response. Resolving
    both through :func:`_read_legs` is what keeps them one rule.

    Args:
        project_id: The project being streamed.
        user_id: The caller's token subject.

    Returns:
        A boolean predicate correlated to nothing, true only while the caller
        holds a read leg on that project.
    """
    return exists(
        select(literal_column("1"))
        .select_from(project)
        .where(project.c.project_id == project_id)
        .where(_read_legs(project, user_id))
    )


def listing_scope(
    conn: Connection, table: Table, *, user_id: str, scope: str
) -> ListingScope:
    """Build the tenancy predicate for a paginated listing, and say how wide it is.

    Reader **(ii)** of contract § 3a's closed list of ``is_admin`` readers, on
    both counts: the flag is what lets an administrator's listing span
    organisations (private rows and ``org_id IS NULL`` rows included, contract
    § 11), and the returned ``via_admin`` is what tells the route it owes an
    audit line.

    **The flag is read exactly once per listing, and both answers come from
    that read.** It would be natural to hand back :func:`_read_legs` as the
    predicate and ask :func:`_is_admin` separately for the trace — but those
    are two statements, and the route then runs its count and page queries in
    two more. A grant or revoke committing in any of those gaps decouples the
    page from the line about the page: rows served across organisations with
    no ``admin_listing`` entry, or an entry for a page the leg never widened.
    So the administrator's predicate is ``true()`` — which is what the admin
    leg already means, since it is unconditional on the row
    (:func:`admin_read_leg`) — and everyone else's is :func:`own_estate`, the
    read grade with no flag in it at all. Both are decided by the one boolean.

    **``scope=mine`` is never on the admin leg and costs no query.** It is the
    owner column and nothing else, so an administrator asking for their own
    rows is an ordinary caller asking for their own rows — no widening, no
    line. ``scope=all`` for an administrator *is* the widened listing, and
    emits one line whether or not the widening happened to change the page:
    deciding "did it actually cross an organisation" per row would cost a
    second scan and would make the trail depend on what the data happened to
    contain that day.

    Args:
        conn: Open database connection — used only to ask whether the caller
            holds the flag, and only when ``scope`` can be widened by it.
        table: ``project`` or ``portfolio``.
        user_id: The caller's token subject.
        scope: ``"all"`` (the default the route declares — owner ∪ the org's
            org-visible rows ∪, for an administrator, everything) or
            ``"mine"`` (owner only, the pre-033 behaviour). The route's
            ``Literal`` type is what rejects anything else; a value that
            reached here unvalidated would be treated as ``"all"``, which is
            why the route owns the validation.

    Returns:
        The predicate to AND with the listing's status/portfolio/owner
        filters, and whether the admin leg widened it.
    """
    if scope == "mine":
        return ListingScope(table.c.owner_user_id == user_id, False)
    # **One read of the flag, and the predicate derives from it.** The obvious
    # spelling — `_read_legs(...)` for the predicate, `_is_admin(conn, ...)`
    # for the trace — asks the same question twice in two statements, and the
    # page and count queries ask it a third and fourth time later still. A
    # grant or revoke committing between them serves a cross-organisation page
    # with **no** `admin_listing` line (or logs one for a page the leg did not
    # widen). Since the admin leg is unconditional on the row
    # (:func:`admin_read_leg`), an administrator's widened predicate is
    # `sa.true()` — so substituting it here loses nothing and makes the
    # predicate and the audit decision two readings of a single row read.
    via_admin = _is_admin(conn, user_id)
    if via_admin:
        return ListingScope(true(), True)
    return ListingScope(own_estate(table, user_id), False)


def owner_email_filter(
    conn: Connection,
    table: Table,
    *,
    user_id: str,
    owner_email: str | None,
) -> ColumnElement[bool]:
    """Gate and resolve the admin-only ``owner_email`` listing filter.

    Reader **(iii)** of contract § 3a's closed list — kept as one small named
    function precisely so the structural assertion can enumerate the readers
    rather than assert "nowhere else", which rev 2.0 got wrong. It reaches the
    flag through :func:`_is_admin`, the same one-line query the listing trace
    uses, so the column has two code-level readers in this module rather than
    three.

    Refusal is **422 ``validation_error``** (contract § 8), not 403: the
    caller passed a parameter they may not use, which is the semantic the
    envelope map already carries. An unenrolled caller has no ``app_user``
    row at all and is refused on the same branch.

    An address that matches no ``app_user`` row yields an empty page rather
    than an error, so an admin cannot use the status code to learn whether an
    address is known to the system. (:func:`trace_admin_listing` emits a line
    for that zero-row request for the same reason.)

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
            ``owner_email``, and 422 when the value is not an address at all.
    """
    if owner_email is None:
        return true()
    if not _is_admin(conn, user_id):
        raise HTTPException(status_code=422, detail=OWNER_EMAIL_DETAIL)
    # Addresses are case-insensitive in practice and ops type them by hand;
    # folding both sides keeps the filter usable without a schema change.
    candidate = owner_email.strip().lower()
    # The shallowest possible shape check, and not a validation exercise: the
    # value reaches the audit line verbatim, so "not an address" should be
    # refused at the boundary rather than written to the trail and matched
    # against nothing. Anything stricter would start refusing addresses that
    # exist — the column has no format constraint and ops fill it in by hand.
    # The **length** bound is not here: it belongs on the route's `Query`, so
    # the contract states it and FastAPI refuses the value before any handler
    # runs. `OWNER_EMAIL_MAX` is what both routes annotate.
    if "@" not in candidate:
        raise HTTPException(status_code=422, detail=OWNER_EMAIL_MALFORMED_DETAIL)
    return table.c.owner_user_id.in_(
        select(app_user.c.user_id).where(func.lower(app_user.c.email) == candidate)
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

    **Leg detection is one query, not two.** The read statement carries
    :func:`own_estate` as a boolean column beside the row (:data:`_OWN_LEG`),
    so the row and the answer to "would this caller have reached it without
    ``is_admin``" arrive together. Where that answer is ``False`` the admin
    leg is what reached the row, and :func:`trace_admin_read` records it — one
    line per row, emitted here rather than at each route so a route cannot
    forget it and so a read the caller was already entitled to cannot
    accidentally be logged.

    The ``for_update`` fast path skips the extra column: it is bounded by the
    owner leg, so a row it returns was reached by the owner, never the admin.

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
    row = (
        conn.execute(
            base.add_columns(_own_leg_column(table, user_id)).where(
                _read_legs(table, user_id)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    via_admin = not row[_OWN_LEG]
    if via_admin:
        trace_admin_read(
            kind=table.name, row_id=_row_identity(table, row), user_id=user_id
        )
    # Safe in Python: SQL has already decided visibility, and a NULL
    # ``owner_user_id`` (the ``orchestrate.py`` rows) never equals a subject.
    is_owner = row["owner_user_id"] == user_id
    if write and not is_owner:
        # An administrator lands here on every mutation they attempt: the
        # admin leg is a **read** leg, so it can reach the row and never write
        # it. 403 rather than 404 because the leg already disclosed the row.
        raise HTTPException(status_code=403, detail=FORBIDDEN_DETAIL)
    return Access(row=row, is_owner=is_owner, via_admin=via_admin)


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


def readable_or_public_project(
    conn: Connection, *, project_id: uuid.UUID, user_id: str | None
) -> Access:
    """Resolve an active project through its read grade or the public leg.

    This is the only public-leg helper. Its callers are exclusively task
    037's eleven conditionally-public read routes; listings, cascades and all
    other access grades deliberately do not consult ``is_public``.

    Args:
        conn: Open database connection.
        project_id: Requested project identity.
        user_id: The authenticated subject, or ``None`` for an anonymous
            request with no Authorization header.

    Returns:
        The active project row, its owner status and the leg that served it.

    Raises:
        HTTPException: 404 when the row is absent, archived or unreadable.
    """
    base = select(project).where(
        project.c.project_id == project_id, project.c.status == "active"
    )
    if user_id is None:
        row = (
            conn.execute(base.where(project.c.is_public.is_(true())))
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
        return Access(row=row, is_owner=False, via_public=True)

    row = (
        conn.execute(
            base.add_columns(_own_leg_column(project, user_id)).where(
                or_(
                    own_estate(project, user_id),
                    admin_read_leg(user_id),
                    project.c.is_public.is_(true()),
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND_DETAIL)
    if row[_OWN_LEG]:
        return Access(row=row, is_owner=row["owner_user_id"] == user_id)
    if row["is_public"]:
        return Access(row=row, is_owner=False, via_public=True)
    trace_admin_read(kind="project", row_id=str(project_id), user_id=user_id)
    return Access(row=row, is_owner=False, via_admin=True)


def chat_mutable_project(conn: Connection, *, project_id: uuid.UUID, user_id: str) -> Access:
    """Resolve one project under the **colleague-mutation** grade, or 404.

    The grade owner call (b) invented and contract § 4 spends on exactly three
    mutations — create a conversation, post a turn to your own conversation,
    cancel your own turn. It sits between the two grades
    :func:`accessible_project` offers, and it exists as its own function for
    one reason: it must **never** widen to the admin leg.

    - Wider than **write**, which is owner-only: a same-org colleague passes.
    - Narrower than **read**, which carries the ``is_admin`` leg: an admin is
      not a colleague and receives none of the three mutations (contract § 3,
      and the acceptance check "is refused every mutation including chat
      creation and turn POST"). Resolving through :func:`own_estate` rather
      than :func:`_read_legs` is what makes that structurally true — the admin
      leg attached to ``_read_legs`` and this helper did not change.
      An out-of-organisation administrator therefore gets the **404** this
      grade gives everyone it refuses, not a 403: there is no read grade here
      to disclose the row with.

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


def assignable_portfolio(
    conn: Connection, *, portfolio_id: uuid.UUID, user_id: str
) -> Access:
    """Resolve one portfolio as an assignment target, or 404.

    The **colleague-mutation** grade (:func:`own_estate` — owner ∪ same-org,
    **never** the admin leg), on a portfolio: a same-org colleague may add
    their own task to an org-visible portfolio they did not create (owner
    ruling 2026-08-27, from staging live testing). Like
    :func:`chat_mutable_project`, it exists as its own function so it can
    never widen to the admin leg — an administrator is not a colleague, and
    an assignment through the admin leg would be the admin-write escape the
    contract bars. An out-of-organisation administrator gets the same 404 as
    everyone this grade refuses: there is no read grade here to disclose the
    row with.

    **Locked** (``FOR UPDATE``), unlike the chat grade: the assignment path
    reads the portfolio's ``visibility``/``org_id`` and writes them onto the
    member, so a cascade committing between that read and the write would
    leave the member carrying a stale value. A portfolio row lock is brief
    (one PATCH transaction) and blocks only the cascade and other
    assignments, not the owner's project operations.

    Args:
        conn: Open database connection.
        portfolio_id: Requested portfolio identity.
        user_id: The caller's token subject.

    Returns:
        The portfolio row and whether the owner leg matched.

    Raises:
        HTTPException: 404 for a missing or unreachable row. There is no 403
            on this grade — a caller who fails it is not told the row exists.
    """
    row = conn.execute(
        select(portfolio)
        .where(portfolio.c.portfolio_id == portfolio_id)
        .where(own_estate(portfolio, user_id))
        .with_for_update()
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
