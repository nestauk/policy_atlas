"""What each operator command actually does, as functions over one connection.

Every function here takes an open :class:`~sqlalchemy.engine.Connection` and,
where it needs one, a Cognito client. It writes rows and returns a small record
describing what it did; it never opens a transaction, never prints, and never
exits. :mod:`policy_atlas.ops.cli` supplies the transaction and renders the
record. That shape is what lets the phase-6 SSE suite drive a *real*
de-enrolment against the test database with a stubbed identity provider, rather
than re-implementing the write it believes the CLI performs.

**Three rules run through the whole module.**

*The identity provider is asked first, and only about identity.* ``sub`` is the
key (contract § 3b) and only Cognito can turn an address into one, so
``user create``, ``user enrol`` and ``user resync`` call ``ListUsers`` /
``AdminCreateUser``. ``admin grant``, ``admin revoke``, ``user de-enrol`` and
``rows assign`` resolve entirely in the database and make no AWS call at all —
which is also why operator IAM needs nothing beyond ``ListUsers`` and
``AdminCreateUser`` (contract § 9).

*Compare and refuse under the row lock.* Every write to ``app_user`` reads the
row ``FOR UPDATE`` first and refuses when the state is not what the operator was
acting on. The interlock the contract names — "operator B can resurrect admin on
a row operator A just de-enrolled" — falls out of one fact: **de-enrolment
clears ``email``**, and ``admin grant`` resolves its subject *by* address. So an
admin grant that raced a de-enrolment finds no row to grant and refuses, in
either commit order. See :func:`set_admin`.

*Row moves are set operations, never walks.* ``UPDATE ... WHERE owner_user_id =
:sub`` in one statement per table. The invariant (contract § 6) survives because
a portfolio's members are always owned by the portfolio's owner, so one person's
rows are a closed set: stamping the set leaves every project matching its
portfolio on both ``org_id`` and ``visibility``. Walking row by row through the
cascade path would transiently violate it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
from mypy_boto3_cognito_idp.type_defs import AttributeTypeTypeDef
from sqlalchemy import insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import app_user, organisation, portfolio, project
from policy_atlas.ops.errors import OpsError

log = structlog.get_logger()

#: The visibility every moved row arrives at. Owner call (j): **no operator
#: action can expose a row.** Enrolment stamps the organisation *and*
#: privatises, so the person opts each row into their organisation
#: deliberately, and a re-enrolment cannot carry work shared with the previous
#: organisation into the next one.
_PRIVATE = "private"


# --------------------------------------------------------------------------
# Records. Each carries its own operator-facing sentence: the CLI's safety UX
# is these strings (plan phase 9b), and keeping them beside the counts they
# describe is what stops a caller inventing a second wording for the same
# outcome. Code words throughout ("project", "portfolio") — they match the
# flags the operator just typed, and the rename slice that follows 033 covers
# this module.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Organisation:
    """One organisation, created or resolved."""

    org_id: uuid.UUID
    name: str

    def summary(self) -> str:
        """Render the created-organisation line."""
        return f"created organisation {self.name!r} ({self.org_id})"


@dataclass(frozen=True)
class Enrolment:
    """One person placed in an organisation, with the rows that moved.

    Attributes:
        user_id: The Cognito subject.
        email: The address the subject resolved from.
        org: The organisation they now belong to.
        created: Whether the ``app_user`` row was inserted rather than updated.
        projects_moved: Projects stamped and privatised.
        portfolios_moved: Portfolios stamped and privatised.
    """

    user_id: str
    email: str
    org: Organisation
    created: bool
    projects_moved: int
    portfolios_moved: int

    def summary(self) -> str:
        """Render the enrolment line, including what moved."""
        verb = "enrolled" if self.created else "re-enrolled"
        return (
            f"{verb} {self.email} ({self.user_id}) in {self.org.name!r}; "
            f"moved {self.projects_moved} project(s), {self.portfolios_moved} "
            "portfolio(s), all private"
        )


@dataclass(frozen=True)
class DeEnrolment:
    """One person removed from their organisation, with the rows released."""

    user_id: str
    email: str | None
    projects_cleared: int
    portfolios_cleared: int
    admin_revoked: bool

    def summary(self) -> str:
        """Render the de-enrolment line, including what was cleared."""
        who = self.email or self.user_id
        admin = "; support role revoked" if self.admin_revoked else ""
        return (
            f"de-enrolled {who}; cleared the organisation on {self.projects_cleared} "
            f"project(s) and {self.portfolios_cleared} portfolio(s){admin}"
        )


@dataclass(frozen=True)
class Resync:
    """One stored address re-resolved from the identity provider."""

    user_id: str
    previous_email: str | None
    email: str
    changed: bool

    def summary(self) -> str:
        """Render the resync line."""
        if not self.changed:
            return f"{self.email} ({self.user_id}) was already current; nothing changed"
        return (
            f"updated the stored address for {self.user_id}: "
            f"{self.previous_email or '(none)'} -> {self.email}"
        )


@dataclass(frozen=True)
class Assignment:
    """Rows moved into an organisation by a single-row assignment."""

    org: Organisation
    portfolio_id: uuid.UUID | None
    projects_moved: int
    portfolios_moved: int
    followed_membership: bool

    def summary(self) -> str:
        """Render the assignment line, saying so when membership widened it."""
        moved = (
            f"moved {self.portfolios_moved} portfolio(s) and {self.projects_moved} "
            f"project(s) into {self.org.name!r}"
        )
        if self.followed_membership:
            return (
                f"{moved} — the project is a member of portfolio {self.portfolio_id}, "
                "so the portfolio and every member moved together"
            )
        return moved


@dataclass(frozen=True)
class AdminChange:
    """A grant or revoke of the support role."""

    user_id: str
    email: str
    direction: str

    def summary(self) -> str:
        """Render the admin-change line."""
        return f"{self.direction}: {self.email} ({self.user_id})"


# --------------------------------------------------------------------------
# Organisations
# --------------------------------------------------------------------------


def create_organisation(conn: Connection, *, name: str) -> Organisation:
    """Create one organisation, refusing a duplicate name.

    Args:
        conn: Open connection inside the command's transaction.
        name: The organisation's name; unique by schema constraint.

    Returns:
        The created organisation.

    Raises:
        OpsError: If an organisation of that name already exists.
    """
    existing = conn.execute(
        select(organisation.c.org_id).where(organisation.c.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        raise OpsError(f"an organisation named {name!r} already exists ({existing})")
    org_id = uuid.uuid4()
    try:
        conn.execute(
            insert(organisation).values(org_id=org_id, name=name, created_at=_now())
        )
    except IntegrityError as error:  # a second operator won the race to the name
        raise OpsError(f"an organisation named {name!r} already exists") from error
    return Organisation(org_id=org_id, name=name)


def resolve_organisation(conn: Connection, token: str) -> Organisation:
    """Resolve ``--org`` given either an organisation id or its exact name.

    Args:
        conn: Open connection.
        token: A UUID or a name.

    Returns:
        The resolved organisation.

    Raises:
        OpsError: If nothing matches.
    """
    try:
        org_id = uuid.UUID(token)
    except ValueError:
        row = conn.execute(
            select(organisation.c.org_id, organisation.c.name).where(
                organisation.c.name == token
            )
        ).one_or_none()
        if row is None:
            raise OpsError(
                f"no organisation named {token!r} — run `org create --name {token!r}` first"
            ) from None
        return Organisation(org_id=row.org_id, name=row.name)
    name = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == org_id)
    ).scalar_one_or_none()
    if name is None:
        raise OpsError(f"no organisation with id {token}")
    return Organisation(org_id=org_id, name=name)


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------


def create_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str,
    display_name: str,
    org: Organisation,
) -> Enrolment:
    """Create a Cognito account, then enrol it.

    **Cognito first, because its ``sub`` is the key** (contract § 9) — there is
    nothing to write in the database until the account exists. That ordering
    creates the one failure this command has to handle explicitly: an account
    created and a database write that then fails. The account is **kept** and
    the ``user enrol`` remediation printed. Deleting it is Out (owner call (h),
    coupled to ownership transfer), and no path in this package calls
    ``AdminDeleteUser``.

    ``DesiredDeliveryMediums=["EMAIL"]`` is passed explicitly because **AWS
    defaults it to SMS** and the pool holds no phone numbers. The invitation is
    *not* suppressed — that, and the password the deleted ``cognito-user`` make
    target took on the command line, are the two things this command exists to
    stop doing.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The new account's address; also its sign-in identifier.
        display_name: Required, and never the email (contract § 3b).
        org: Where to enrol them.

    Returns:
        The enrolment (zero rows moved — a new account owns nothing yet).

    Raises:
        OpsError: If the address already exists in the pool, or if the database
            write fails after the account was created.
    """
    _require_filter_safe(email)
    if _find_sub_by_email(cognito, pool_id=pool_id, email=email) is not None:
        raise OpsError(
            f"{email} already exists in the pool — use "
            f"`user enrol --email {email} --org {org.name!r} "
            f"--display-name {display_name!r}`"
        )
    response = cognito.admin_create_user(
        UserPoolId=pool_id,
        Username=email,
        UserAttributes=[
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
        DesiredDeliveryMediums=["EMAIL"],
    )
    sub = _sub_of(response["User"].get("Attributes", []))
    if not sub:
        raise OpsError(
            f"Cognito created {email} but returned no `sub` attribute. The account "
            f"exists; enrol it with `user enrol --email {email} "
            f"--org {org.name!r} --display-name {display_name!r}`."
        )
    try:
        return _enrol(
            conn,
            sub=sub,
            email=email,
            display_name=display_name,
            org=org,
        )
    except Exception as error:
        raise OpsError(
            f"the Cognito account for {email} was created and has been KEPT, but the "
            f"database write failed ({error}). Nothing was enrolled. Re-run just the "
            f"enrolment: `user enrol --email {email} --org {org.name!r} "
            f"--display-name {display_name!r}`"
        ) from error


def enrol_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str,
    display_name: str,
    org: Organisation,
) -> Enrolment:
    """Enrol an existing Cognito account, carrying its owner's work across.

    Owner call (j): the ``app_user`` upsert **and** the row moves are one
    transaction, so an interrupted enrolment leaves a person neither
    half-enrolled nor with half their work in a new organisation.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The address to resolve the subject from.
        display_name: Required, and never the email.
        org: Where to enrol them.

    Returns:
        The enrolment, including the rows moved.

    Raises:
        OpsError: If the pool holds no such address, or the stored address for
            that subject is a different one (which means the operator is acting
            on a stale view — contract § 3b's staleness rule; ``user resync``
            is the way forward).
    """
    _require_filter_safe(email)
    sub = _find_sub_by_email(cognito, pool_id=pool_id, email=email)
    if sub is None:
        raise OpsError(
            f"no account in the pool for {email} — use "
            f"`user create --email {email} --org {org.name!r} "
            f"--display-name {display_name!r}`"
        )
    return _enrol(
        conn, sub=sub, email=email, display_name=display_name, org=org
    )


def _enrol(
    conn: Connection,
    *,
    sub: str,
    email: str,
    display_name: str,
    org: Organisation,
) -> Enrolment:
    """Upsert the ``app_user`` row and move the person's rows, in one transaction."""
    existing = _lock_user(conn, sub)
    if existing is not None and existing["email"] not in (None, email):
        raise OpsError(
            f"{sub} is stored against {existing['email']}, not {email}. The address "
            f"changed in Cognito, or this is the wrong person. Run "
            f"`user resync --email {email}` first if the address changed."
        )
    # ON CONFLICT DO UPDATE: ops enrolment clobbers deliberately (contract § 2),
    # unlike `/me`'s DO NOTHING. `is_admin` is deliberately NOT in the SET list —
    # enrolment is not a place to grant or drop the support role, and leaving it
    # out is also what keeps `user enrol` off the admin-resurrection path.
    statement = pg_insert(app_user).values(
        user_id=sub,
        org_id=org.org_id,
        display_name=display_name,
        email=email,
        created_at=_now(),
    )
    conn.execute(
        statement.on_conflict_do_update(
            index_elements=[app_user.c.user_id],
            set_={
                "org_id": statement.excluded.org_id,
                "display_name": statement.excluded.display_name,
                "email": statement.excluded.email,
            },
        )
    )
    projects_moved, portfolios_moved = _stamp_owned_rows(
        conn, sub=sub, org_id=org.org_id, visibility=_PRIVATE
    )
    return Enrolment(
        user_id=sub,
        email=email,
        org=org,
        created=existing is None,
        projects_moved=projects_moved,
        portfolios_moved=portfolios_moved,
    )


def resync_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str,
) -> Resync:
    """Re-resolve a stored address after it changed in Cognito.

    **The semantics implemented here, stated because the flag alone is
    ambiguous:** ``--email`` is the address as it stands in Cognito **now** —
    the new one. The command looks that address up in the pool, takes the
    ``sub`` it belongs to, and writes it onto that subject's ``app_user`` row.
    ``sub`` is what the application keys on and what never changes (contract
    § 3b), so it is the only fixed point available; the old address is not an
    input, and does not need to be known.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The current address in Cognito.

    Returns:
        The resync, saying whether anything changed.

    Raises:
        OpsError: If the pool holds no such address, or the subject behind it
            has never been enrolled.
    """
    _require_filter_safe(email)
    sub = _find_sub_by_email(cognito, pool_id=pool_id, email=email)
    if sub is None:
        raise OpsError(f"no account in the pool for {email}")
    row = _lock_user(conn, sub)
    if row is None:
        raise OpsError(
            f"{email} ({sub}) has a Cognito account but is not enrolled — "
            "use `user enrol`"
        )
    previous = row["email"]
    if previous == email:
        return Resync(user_id=sub, previous_email=previous, email=email, changed=False)
    conn.execute(update(app_user).where(app_user.c.user_id == sub).values(email=email))
    return Resync(user_id=sub, previous_email=previous, email=email, changed=True)


def de_enrol_user(
    conn: Connection, *, email: str | None = None, sub: str | None = None
) -> DeEnrolment:
    """Remove a person from their organisation and take their rows out with them.

    Clears ``org_id``, ``email`` and ``is_admin`` on ``app_user``, and ``org_id``
    on every project and portfolio the person owns — so the organisation they
    left loses sight of their work (contract § 7; flagged there as an owner
    decision, because the alternative needs ownership transfer, which is Out).

    **``visibility`` is deliberately untouched.** The rows return to
    ``org_id IS NULL``, where the NULL rule already makes them reachable by
    their owner alone, so re-privatising would change nothing a caller can
    observe while destroying the choices the person made. The invariant holds
    because both tables are cleared in the same set operation: a member and its
    portfolio arrive at NULL together, and neither one's visibility moved.

    Args:
        conn: Open connection inside the command's transaction.
        email: The stored address to resolve by; mutually exclusive with ``sub``.
        sub: The Cognito subject to resolve by.

    Returns:
        The de-enrolment, including the counts cleared.

    Raises:
        OpsError: If the person cannot be resolved, resolves ambiguously, or is
            already de-enrolled.
    """
    row = _resolve_and_lock(conn, email=email, sub=sub)
    user_id = str(row["user_id"])
    if row["org_id"] is None and row["email"] is None and not row["is_admin"]:
        raise OpsError(f"{user_id} is already de-enrolled; nothing to do")
    conn.execute(
        update(app_user)
        .where(app_user.c.user_id == user_id)
        .values(org_id=None, email=None, is_admin=False)
    )
    projects_cleared, portfolios_cleared = _clear_owned_rows(conn, sub=user_id)
    return DeEnrolment(
        user_id=user_id,
        email=row["email"],
        projects_cleared=projects_cleared,
        portfolios_cleared=portfolios_cleared,
        admin_revoked=bool(row["is_admin"]),
    )


def set_admin(
    conn: Connection, *, email: str, grant: bool, operator: str, env: str
) -> AdminChange:
    """Grant or revoke the support role, and trace who did it.

    Contract § 3a: "a privileged grant with no record of who made it is not
    auditable", so this emits ``ops.admin_change`` naming **the operator, the
    subject and the direction**. The operator identity is the CLI's
    ``--operator`` value, defaulting to the ARN that ``GetCallerIdentity``
    returned during the environment check — the AWS principal that actually held
    the permission, not a shell variable anyone can set.

    **The subject is resolved by address in the database, not in Cognito**, and
    that is the concurrency guard. De-enrolment clears ``email``; so if operator
    A de-enrols while operator B grants, the ``FOR UPDATE`` read serialises them
    and B finds no row carrying that address — the grant refuses instead of
    resurrecting the role. In the other commit order B's grant lands first and
    A's de-enrolment clears it. Neither order leaves an administrator behind.

    Args:
        conn: Open connection inside the command's transaction.
        email: The stored address of the subject.
        grant: ``True`` to grant, ``False`` to revoke.
        operator: Who is making the change; recorded on the trace line.
        env: The environment, recorded on the trace line.

    Returns:
        The change that was made.

    Raises:
        OpsError: If no enrolled subject carries that address, more than one
            does, or the flag already holds the requested value.
    """
    row = _resolve_and_lock(conn, email=email, sub=None)
    user_id = str(row["user_id"])
    direction = "grant" if grant else "revoke"
    if bool(row["is_admin"]) == grant:
        state = "already an administrator" if grant else "not an administrator"
        raise OpsError(f"{email} ({user_id}) is {state}; nothing to {direction}")
    conn.execute(
        update(app_user).where(app_user.c.user_id == user_id).values(is_admin=grant)
    )
    log.info(
        "ops.admin_change",
        operator=operator,
        subject=user_id,
        direction=direction,
        env=env,
    )
    return AdminChange(user_id=user_id, email=email, direction=direction)


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------


def assign_rows(
    conn: Connection,
    *,
    org: Organisation,
    project_id: uuid.UUID | None = None,
    portfolio_id: uuid.UUID | None = None,
) -> Assignment:
    """Assign one row to an organisation, moving both where one is in the other.

    Contract § 9 sends this through § 6's invariant: a project carries its
    portfolio's ``org_id`` *and* ``visibility``. So there is no such thing as
    assigning half of a membership, and the command never offers to:

    - a **portfolio** moves with every member project, which also takes the
      portfolio's visibility (the same two statements the API's ``i.4`` cascade
      runs, ``portfolios.py``);
    - a **project that is a member** of a portfolio moves the *portfolio* and
      therefore every sibling, and says so in the summary;
    - a **project with no portfolio** is unconstrained and moves alone, keeping
      its visibility.

    ``updated_at`` is bumped on moved members, exactly as the API cascade bumps
    it: unlike enrolment — where contract § 7 requires the person to see no
    change — an assignment genuinely reshapes which organisation owns the row.

    Args:
        conn: Open connection inside the command's transaction.
        org: The destination.
        project_id: The project to assign; mutually exclusive with
            ``portfolio_id``.
        portfolio_id: The portfolio to assign.

    Returns:
        What moved.

    Raises:
        OpsError: If neither or both ids are given, or the row does not exist.
    """
    if (project_id is None) == (portfolio_id is None):
        raise OpsError("give exactly one of --project or --portfolio")

    followed = False
    if project_id is not None:
        row = conn.execute(
            select(project.c.project_id, project.c.portfolio_id)
            .where(project.c.project_id == project_id)
            .with_for_update()
        ).one_or_none()
        if row is None:
            raise OpsError(f"no project {project_id}")
        if row.portfolio_id is None:
            conn.execute(
                update(project)
                .where(project.c.project_id == project_id)
                .values(org_id=org.org_id, updated_at=_now())
            )
            return Assignment(
                org=org,
                portfolio_id=None,
                projects_moved=1,
                portfolios_moved=0,
                followed_membership=False,
            )
        target = row.portfolio_id
        followed = True
    else:
        target = portfolio_id

    visibility = conn.execute(
        select(portfolio.c.visibility)
        .where(portfolio.c.portfolio_id == target)
        .with_for_update()
    ).scalar_one_or_none()
    if visibility is None:
        raise OpsError(f"no portfolio {target}")
    conn.execute(
        update(portfolio)
        .where(portfolio.c.portfolio_id == target)
        .values(org_id=org.org_id)
    )
    # No status filter: archived members follow too, for the reason the API
    # cascade documents — an archived project is still readable by whoever may
    # read it, so leaving it behind strands exactly the rows nobody watches.
    moved = conn.execute(
        update(project)
        .where(project.c.portfolio_id == target)
        .values(org_id=org.org_id, visibility=visibility, updated_at=_now())
    ).rowcount
    return Assignment(
        org=org,
        portfolio_id=target,
        projects_moved=moved,
        portfolios_moved=1,
        followed_membership=followed,
    )


# --------------------------------------------------------------------------
# Shared internals
# --------------------------------------------------------------------------


def _stamp_owned_rows(
    conn: Connection, *, sub: str, org_id: uuid.UUID, visibility: str
) -> tuple[int, int]:
    """Stamp organisation and visibility onto every row one person owns.

    Two statements, one per table — the set operation the invariant argument in
    the module docstring depends on.

    ``.values()`` names its columns literally rather than splatting a dict.
    Rubric 24 bars the blind ``.values(**changes)`` splat on the API's portfolio
    patch; the same discipline belongs on the one other writer of these two
    columns, even though the values here are internal.

    ``updated_at`` is left alone. Contract § 7 requires that an enrolled person
    "sees no change", and bumping it would reorder their entire task list the
    moment an operator enrolled them.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The owner.
        org_id: The organisation to stamp.
        visibility: The visibility to force — always ``private`` today.

    Returns:
        ``(projects, portfolios)`` row counts.
    """
    projects = conn.execute(
        update(project)
        .where(project.c.owner_user_id == sub)
        .values(org_id=org_id, visibility=visibility)
    ).rowcount
    portfolios = conn.execute(
        update(portfolio)
        .where(portfolio.c.owner_user_id == sub)
        .values(org_id=org_id, visibility=visibility)
    ).rowcount
    return projects, portfolios


def _clear_owned_rows(conn: Connection, *, sub: str) -> tuple[int, int]:
    """Clear the organisation on every row one person owns, leaving visibility.

    The counterpart to :func:`_stamp_owned_rows`, and deliberately *not* the
    same function with a nullable argument: the two differ in which columns they
    write, which is exactly the thing that must stay legible.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The owner.

    Returns:
        ``(projects, portfolios)`` row counts.
    """
    projects = conn.execute(
        update(project).where(project.c.owner_user_id == sub).values(org_id=None)
    ).rowcount
    portfolios = conn.execute(
        update(portfolio).where(portfolio.c.owner_user_id == sub).values(org_id=None)
    ).rowcount
    return projects, portfolios


def _lock_user(conn: Connection, sub: str) -> RowMapping | None:
    """Read one ``app_user`` row ``FOR UPDATE``, or ``None`` if it does not exist."""
    return (
        conn.execute(
            select(app_user).where(app_user.c.user_id == sub).with_for_update()
        )
        .mappings()
        .one_or_none()
    )


def _resolve_and_lock(
    conn: Connection, *, email: str | None, sub: str | None
) -> RowMapping:
    """Resolve a subject in the database by address or id, and lock the row.

    Raises:
        OpsError: If neither or both selectors are given, nothing matches, or —
            for an address, which carries no unique constraint — more than one
            row does.
    """
    if (email is None) == (sub is None):
        raise OpsError("give exactly one of --email or --sub")
    if sub is not None:
        row = _lock_user(conn, sub)
        if row is None:
            raise OpsError(f"no user {sub}")
        return row
    rows = (
        conn.execute(
            select(app_user).where(app_user.c.email == email).with_for_update()
        )
        .mappings()
        .all()
    )
    if not rows:
        raise OpsError(
            f"no enrolled user with the address {email}. `user enrol` is what stores "
            "the address this resolves by, and de-enrolment clears it — if the person "
            "was just de-enrolled, that is why."
        )
    if len(rows) > 1:
        subjects = ", ".join(str(row["user_id"]) for row in rows)
        raise OpsError(
            f"{len(rows)} users share the address {email} ({subjects}); resolve with "
            "--sub instead"
        )
    return rows[0]


def _find_sub_by_email(
    cognito: CognitoIdentityProviderClient, *, pool_id: str, email: str
) -> str | None:
    """Return the Cognito subject behind an address, or ``None``."""
    response = cognito.list_users(
        UserPoolId=pool_id, Filter=f'email = "{email}"', Limit=1
    )
    users = response.get("Users") or []
    if not users:
        return None
    return _sub_of(users[0].get("Attributes", [])) or None


def _sub_of(attributes: Sequence[AttributeTypeTypeDef]) -> str:
    """Pull ``sub`` out of a Cognito attribute list."""
    for attribute in attributes:
        if attribute.get("Name") == "sub":
            return str(attribute.get("Value", ""))
    return ""


def _require_filter_safe(email: str) -> None:
    """Refuse an address that cannot be a Cognito ``ListUsers`` filter literal.

    The filter grammar is ``attribute = "value"`` with no escape sequence, so a
    quote or a backslash in the value would change the query rather than be
    matched by it. Refusing is right in both readings: as an injection guard,
    and because such an address cannot be looked up at all.
    """
    if '"' in email or "\\" in email:
        raise OpsError(f"refusing an address containing a quote or backslash: {email!r}")


def _now() -> datetime:
    return datetime.now(UTC)
