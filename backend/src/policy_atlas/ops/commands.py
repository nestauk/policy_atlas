"""What each operator command actually does, as functions over one connection.

Every function here takes an open :class:`~sqlalchemy.engine.Connection` and,
where it needs one, a Cognito client (``user reissue`` changes Cognito only; it
reads the database to refuse a deactivated person). It writes rows and returns a small record
describing what it did; it never opens a transaction, never prints, and never
exits. :mod:`policy_atlas.ops.cli` supplies the transaction and renders the
record. That shape is what lets the phase-6 SSE suite drive a *real*
de-enrolment against the test database with a stubbed identity provider, rather
than re-implementing the write it believes the CLI performs.

**Three rules run through the whole module.**

*The identity provider is asked first, and only about identity.* ``sub`` is the
key and only Cognito can turn an address into one, so
``user create``, ``user enrol`` and ``user resync`` call ``ListUsers`` /
``AdminCreateUser``, and ``user reissue`` calls ``ListUsers``, ``AdminGetUser``
and ``AdminSetUserPassword``. ``user deactivate`` and ``user reactivate`` are the
commands that change an account's state in Cognito: ``ListUsers``, then
``AdminDisableUser`` and ``AdminUserGlobalSignOut``, or ``AdminEnableUser``
(ADR 0045 decision 5). ``user reset-app`` calls ``ListUsers``, ``AdminGetUser``,
``AdminUserGlobalSignOut`` and ``AdminDeleteSoftwareToken``. ``admin grant``,
``admin revoke``, ``user de-enrol`` and ``rows assign`` resolve entirely in the
database and make no AWS call at all — which is also why operator IAM needs
nothing beyond ``ListUsers``, ``AdminCreateUser``, ``AdminSetUserPassword``,
``AdminDisableUser``, ``AdminUserGlobalSignOut``, ``AdminEnableUser`` and
``AdminDeleteSoftwareToken``.

*Compare and refuse under the row lock.* Every write to ``app_user`` reads the
row ``FOR UPDATE`` first and refuses when the state is not what the operator was
acting on. The interlock the contract names — "operator B can resurrect admin on
a row operator A just de-enrolled" — is the organisation check on
:func:`set_admin`: a grant refuses a subject in no organisation. De-enrolment
keeps the stored address, so the person stays findable, and clears ``is_admin``.
A grant that races a de-enrolment finds the row and refuses; in the other order
the grant lands and the de-enrolment clears the role. Neither order leaves an
administrator behind.

*Row moves are set operations, never walks.* ``UPDATE ... WHERE owner_user_id =
:sub`` in one statement per table. Colleague assignment
means a project's members are no longer always owned by its
owner, so a move first **severs** every membership pairing the mover's rows
with someone else's (:func:`_sever_cross_owner_memberships`) — after which one
person's rows are again a closed set, and stamping the set leaves every
task matching its projects on both ``org_id`` and ``visibility``. Walking
row by row through the cascade path would transiently violate it.

**Nothing here logs.** A privilege change is recorded by
:mod:`policy_atlas.ops.cli` *after* the transaction commits, from the
:class:`AdminTrace` values a record carries. A ``log.info`` emitted inside the
transaction is a durable claim about a write a failed commit then discarded,
which is worse than no trace at all: the line must be evidence.
"""

from __future__ import annotations

import secrets
import string
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Literal, NoReturn

from botocore.exceptions import ClientError
from sqlalchemy import and_, case, delete, func, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import invite_code
from policy_atlas.core.schema import (
    app_user,
    cohort,
    cohort_member,
    invite_link,
    invite_link_cohort,
    ops_action,
    organisation,
    organisation_domain,
    project,
    project_membership,
    task,
    waitlist_entry,
)
from policy_atlas.ops.errors import (
    Deactivated,
    EnrolledElsewhere,
    NotFound,
    OpsError,
    ResendTooSoon,
)

if TYPE_CHECKING:
    from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
    from mypy_boto3_cognito_idp.type_defs import AttributeTypeTypeDef, UserTypeTypeDef

#: The visibility every moved row arrives at. **No operator
#: action can expose a row.** Enrolment and ``rows assign`` stamp the
#: organisation *and* privatise, so the person opts each row into their
#: organisation deliberately, and neither a re-enrolment nor an operator
#: assignment can carry work shared with the previous organisation into the
#: next one.
_PRIVATE = "private"


# --------------------------------------------------------------------------
# Records. Each carries its own operator-facing sentence: the CLI's safety UX
# is these strings, and keeping them beside the counts they
# describe is what stops a caller inventing a second wording for the same
# outcome. Code words throughout ("task", "project") — they match the
# flags the operator just typed, and the rename slice that follows 033 covers
# this module.
#
# A record also carries the audit lines its command owes, for the CLI to emit
# once the transaction has committed. `Record.admin_changes` returning `()` is
# the default because most commands owe none, and the two that do owe theirs
# for the same reason — `is_admin` moved.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class AdminTrace:
    """One privilege change, to be recorded after the transaction commits.

    Carries only what the command knows. The operator identity and the
    environment are the CLI's to add (:func:`policy_atlas.ops.cli._trace`) —
    they come from the verified ``GetCallerIdentity`` ARN, not from anything a
    command function is handed.

    Attributes:
        subject: The Cognito subject whose ``is_admin`` moved.
        direction: ``grant`` or ``revoke``.
    """

    subject: str
    direction: str
    flag: str = "is_admin"


class Record:
    """Base for every command record: what to print, and what to trace.

    Not an ABC and deliberately not carrying ``summary``: every subclass
    defines its own line, and :class:`policy_atlas.ops.cli.Outcome` is the
    structural protocol both halves are checked against.
    """

    def admin_changes(self) -> Sequence[AdminTrace]:
        """The privilege changes this command made, if any."""
        return ()


@dataclass(frozen=True)
class Organisation(Record):
    """One organisation, created or resolved."""

    org_id: uuid.UUID
    name: str

    def summary(self) -> str:
        """Render the created-organisation line."""
        return f"created organisation {self.name!r} ({self.org_id})"


@dataclass(frozen=True)
class OrganisationDeletion(Record):
    """One empty organisation deleted."""

    org_id: uuid.UUID
    name: str

    def summary(self) -> str:
        """Render the deleted-organisation line."""
        return f"deleted organisation {self.name!r} ({self.org_id})"


@dataclass(frozen=True)
class Enrolment(Record):
    """One person placed in an organisation, with the rows that moved.

    Attributes:
        user_id: The Cognito subject.
        email: The address the subject resolved from.
        org: The organisation they now belong to.
        created: Whether the ``app_user`` row was inserted rather than updated.
        tasks_moved: Tasks stamped and privatised.
        projects_moved: Projects stamped and privatised.
    """

    user_id: str
    email: str
    org: Organisation
    created: bool
    tasks_moved: int
    projects_moved: int
    #: Set only by `user create --invite manual`.
    #: Rendered ONCE in the summary for out-of-band handover; never logged —
    #: `summary()` output goes to the operator's stdout, not through structlog.
    temporary_password: str | None = None
    #: Cross-owner membership links cut because the rows moved organisation
    #: (colleague assignment).
    memberships_severed: int = 0
    invitation_sent: bool = False
    #: The account was deactivated and this enrolment turned it back on (task 066).
    reactivated: bool = False

    def summary(self) -> str:
        """Render the enrolment line, including what moved."""
        verb = "enrolled" if self.created else "re-enrolled"
        if self.reactivated:
            verb = f"reactivated and {verb}"
        line = (
            f"{verb} {self.email} ({self.user_id}) in {self.org.name!r}; "
            f"moved {self.tasks_moved} task(s), {self.projects_moved} "
            "project(s), all private"
        )
        if self.memberships_severed:
            line += (
                f"; cut {self.memberships_severed} membership(s) linking their "
                "rows to colleagues' rows left behind"
            )
        if self.temporary_password is not None:
            line += _temporary_password_line(self.temporary_password)
        return line


@dataclass(frozen=True)
class CreatedAccount(Record):
    """A Cognito account recorded with no organisation.

    Attributes:
        user_id: The Cognito subject.
        email: The address stored on ``app_user``. An organisation is not
            required for the address to be stored.
        created: Whether this call created the Cognito account. False when the
            account already existed and this call only wrote the identity row.
        temporary_password: Set only by ``user create --invite manual``.
    """

    user_id: str
    email: str
    created: bool
    temporary_password: str | None = None

    def summary(self) -> str:
        """Render the unenrolled-account line."""
        verb = "created" if self.created else "recorded"
        line = f"{verb} {self.email} ({self.user_id}); not in an organisation"
        if self.temporary_password is not None:
            line += _temporary_password_line(self.temporary_password)
        return line


def _temporary_password_line(password: str) -> str:
    """The one-time credential sentence shared by the create summaries."""
    return (
        "\ntemporary password (single-use, 30-day expiry, they set their "
        f"own at first sign-in): {password}"
    )


@dataclass(frozen=True)
class DeEnrolment(Record):
    """One person removed from their organisation, with the rows released."""

    user_id: str
    email: str | None
    tasks_cleared: int
    projects_cleared: int
    admin_revoked: bool
    ops_revoked: bool = False
    #: Cross-owner membership links cut because the rows left the organisation
    #: (colleague assignment).
    memberships_severed: int = 0

    def summary(self) -> str:
        """Render the de-enrolment line, including what was cleared."""
        who = self.email or self.user_id
        admin = "; support role revoked" if self.admin_revoked else ""
        ops = "; ops role revoked" if self.ops_revoked else ""
        severed = (
            f"; cut {self.memberships_severed} membership(s) linking their rows to colleagues' rows"
            if self.memberships_severed
            else ""
        )
        return (
            f"de-enrolled {who}; cleared the organisation on {self.tasks_cleared} "
            f"task(s) and {self.projects_cleared} project(s){severed}{admin}{ops}"
        )

    def admin_changes(self) -> Sequence[AdminTrace]:
        """A de-enrolment that cleared ``is_admin`` is a revoke, and traces as one.

        Every privilege change needs a record, not only every
        ``admin revoke`` invocation. De-enrolment is the *other* way the support
        role is taken away — and the one an investigation is most likely to be
        asking about.
        """
        return tuple(
            AdminTrace(subject=self.user_id, direction="revoke", flag=flag)
            for flag, revoked in (("is_admin", self.admin_revoked), ("is_ops", self.ops_revoked))
            if revoked
        )


@dataclass(frozen=True)
class Resync(Record):
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
class Reissue(Record):
    """A fresh temporary password for an account.

    Attributes:
        user_id: The Cognito subject.
        email: The address the subject resolved from.
        temporary_password: The minted credential. Rendered once in the summary
            for out-of-band handover, never logged.
    """

    user_id: str
    email: str
    temporary_password: str

    def summary(self) -> str:
        """Render the reissue line, carrying the password once."""
        return (
            f"reissued {self.email} ({self.user_id})\ntemporary password "
            f"(single-use, 30-day expiry, they set their own at the next sign-in): "
            f"{self.temporary_password}"
        )


@dataclass(frozen=True)
class Assignment(Record):
    """Rows moved into an organisation by a single-row assignment.

    Attributes:
        org: The destination organisation.
        project_id: The project the move went through, if any.
        tasks_moved: Tasks stamped.
        projects_moved: Projects stamped.
        followed_membership: Whether a named task widened the move to its
            project and siblings.
        privatised: Whether the move changed the rows' organisation and
            therefore forced them ``private``. ``False`` only when the rows
            were already in the destination organisation, where there is no
            new audience to privatise against.
    """

    org: Organisation
    project_id: uuid.UUID | None
    tasks_moved: int
    projects_moved: int
    followed_membership: bool
    privatised: bool

    def summary(self) -> str:
        """Render the assignment line, naming the destination and the privatisation."""
        moved = (
            f"moved {self.projects_moved} project(s) and {self.tasks_moved} "
            f"task(s) into {self.org.name!r}"
        )
        if self.privatised:
            moved += ", all private"  # same words `Enrolment` uses, for the same rule
        if self.followed_membership:
            return (
                f"{moved} — the task is a member of project {self.project_id}, "
                "so the project and every member moved together"
            )
        return moved


@dataclass(frozen=True)
class AdminChange(Record):
    """A grant or revoke of the support role."""

    user_id: str
    email: str | None
    direction: str

    def summary(self) -> str:
        """Render the admin-change line."""
        if self.email is None:  # resolved by --sub, on a row carrying no address
            return f"{self.direction}: {self.user_id}"
        return f"{self.direction}: {self.email} ({self.user_id})"

    def admin_changes(self) -> Sequence[AdminTrace]:
        """The change itself, for the CLI to trace after the commit."""
        return (AdminTrace(subject=self.user_id, direction=self.direction),)


@dataclass(frozen=True)
class Resend(Record):
    """An invitation re-sent to a person awaiting their first sign-in."""

    user_id: str
    email: str
    sent_at: datetime

    def summary(self) -> str:
        """Render the invitation resend line."""
        return f"resent the invitation to {self.email} ({self.user_id})"


@dataclass(frozen=True)
class Approval(Record):
    """A waitlist request enrolled and stamped with its resulting account."""

    entry_id: uuid.UUID
    enrolment: Enrolment
    created_at: datetime

    def summary(self) -> str:
        """Render the approval without exposing the request address."""
        return f"approved request {self.entry_id} for {self.enrolment.user_id}"


@dataclass(frozen=True)
class OpsChange(AdminChange):
    """A grant or revoke of the ops role."""

    def admin_changes(self) -> Sequence[AdminTrace]:
        """Return the post-commit ops-role audit trace."""
        return (AdminTrace(subject=self.user_id, direction=self.direction, flag="is_ops"),)


@dataclass(frozen=True)
class QuotaChange(Record):
    """The before and after quota overrides for one user or organisation."""

    who: str
    task_quota_before: int | None
    runs_before: int | None
    task_quota_after: int | None
    runs_after: int | None

    def summary(self) -> str:
        """Render quota override changes, using inherit for a cleared value."""
        return f"quota for {self.audit_target()}"

    def audit_target(self) -> str:
        """The audit row's target: who, then each value before and after."""
        def show(value: int | None) -> str:
            return "inherit" if value is None else str(value)

        return (
            f"{self.who}: tasks per year {show(self.task_quota_before)} → "
            f"{show(self.task_quota_after)}, simultaneous tasks {show(self.runs_before)} → "
            f"{show(self.runs_after)}"
        )


@dataclass(frozen=True)
class DomainChange(Record):
    """One organisation-domain mapping added or removed."""

    domain: str
    org: Organisation | None
    added: bool

    def summary(self) -> str:
        """Render the domain mapping change."""
        if self.added:
            assert self.org is not None
            return f"added domain {self.domain} to {self.org.name!r}"
        return f"removed domain {self.domain}"


@dataclass(frozen=True)
class Deactivation(Record):
    """One person locked out: Cognito account disabled, then marked in the database.

    Attributes:
        user_id: The Cognito subject.
        email: The address they were found by or stored under, if any.
        steps: One plain sentence per step taken or skipped, in order.
        links_made_private: Tasks whose public link was switched off.
        already: Whether they were already marked deactivated.
        admin_revoked: Whether this cleared ``is_admin``.
        ops_revoked: Whether this cleared ``is_ops``.
    """

    user_id: str
    email: str | None
    steps: tuple[str, ...]
    links_made_private: int
    already: bool
    admin_revoked: bool = False
    ops_revoked: bool = False

    def admin_changes(self) -> Sequence[AdminTrace]:
        """Clearing a role is a revoke, and traces as one (contract § 3a)."""
        return tuple(
            AdminTrace(subject=self.user_id, direction="revoke", flag=flag)
            for flag, revoked in (("is_admin", self.admin_revoked), ("is_ops", self.ops_revoked))
            if revoked
        )

    def summary(self) -> str:
        """Render the deactivation as one header line and one line per step."""
        who = f"{self.email} ({self.user_id})" if self.email else self.user_id
        return f"deactivated {who}:\n" + "\n".join(f"  - {step}" for step in self.steps)


@dataclass(frozen=True)
class Reactivation(Record):
    """One person's login turned back on.

    Attributes:
        user_id: The Cognito subject.
        email: The stored address, if any.
        changed: False when they were neither deactivated nor disabled.
    """

    user_id: str
    email: str | None
    changed: bool

    def summary(self) -> str:
        """Render the reactivation as one line."""
        who = f"{self.email} ({self.user_id})" if self.email else self.user_id
        return f"reactivated {who}" if self.changed else f"{who} is not deactivated; nothing to do"


@dataclass(frozen=True)
class AppReset(Record):
    """One person's authenticator app unlinked, after signing them out everywhere.

    Attributes:
        user_id: The Cognito subject; the audit row's target.
        email: The address they were found by or stored under, if any.
    """

    user_id: str
    email: str | None

    def summary(self) -> str:
        """Render the reset as one line, with what the person sees next."""
        who = f"{self.email} ({self.user_id})" if self.email else self.user_id
        return (
            f"reset the authenticator app of {who}: signed out everywhere; their next "
            "sign-in shows the QR code to set up an app again"
        )


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
        conn.execute(insert(organisation).values(org_id=org_id, name=name, created_at=_now()))
    except IntegrityError as error:  # a second operator won the race to the name
        raise OpsError(f"an organisation named {name!r} already exists") from error
    return Organisation(org_id=org_id, name=name)


def delete_organisation(conn: Connection, *, org_id: uuid.UUID) -> OrganisationDeletion:
    """Delete an organisation nothing points at any more.

    The foreign keys would refuse too; this check comes first so the refusal
    says what is still there (contract 066 B7).

    Args:
        conn: Open connection inside the command's transaction.
        org_id: The organisation to delete.

    Returns:
        The deleted organisation.

    Raises:
        NotFound: If no organisation has that id.
        OpsError: If any person, task, project, domain or invite link still points at it.
    """
    name = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == org_id).with_for_update()
    ).scalar_one_or_none()
    if name is None:
        raise NotFound(f"no organisation {org_id}")
    counts = {
        label: int(conn.execute(
            select(func.count()).select_from(table).where(table.c.org_id == org_id)
        ).scalar_one())
        for label, table in (("people", app_user), ("tasks", task), ("projects", project),
                             ("domains", organisation_domain), ("invite links", invite_link))
    }
    left = [f"{count} {label}" for label, count in counts.items() if count]
    if left:
        raise OpsError(f"{name} still has {', '.join(left)}. Nothing was deleted.")
    conn.execute(delete(organisation).where(organisation.c.org_id == org_id))
    return OrganisationDeletion(org_id=org_id, name=str(name))


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
            select(organisation.c.org_id, organisation.c.name).where(organisation.c.name == token)
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
        raise NotFound(f"no organisation with id {token}")
    return Organisation(org_id=org_id, name=name)


# --------------------------------------------------------------------------
# People
# --------------------------------------------------------------------------


def _mint_temporary_password() -> str:
    """Mint a policy-compliant single-use temporary password.

    Generated, never accepted: no command accepts a password, because
    this value originates here, not from an operator. 20
    characters with every Cognito-default class guaranteed (upper, lower,
    digit, symbol). The symbol set holds only characters that survive a copy
    through a shell and a chat or email app: no quotes, backslashes or ``$``;
    no ``!`` or ``^`` (shell history); no ``*`` or ``_`` (chat apps read pairs
    of them as bold and italic and remove them); no ``#`` (comment, tag).
    """
    symbols = "@%+=-"
    pools = (string.ascii_lowercase, string.ascii_uppercase, string.digits, symbols)
    everything = "".join(pools)
    chars = [secrets.choice(pool) for pool in pools]
    chars += [secrets.choice(everything) for _ in range(16)]
    # secrets-driven order, so the guaranteed classes are not positionally fixed.
    return "".join(chars.pop(secrets.randbelow(len(chars))) for _ in range(len(chars)))


def create_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str,
    display_name: str,
    org: Organisation | None = None,
    invite: str = "email",
) -> Enrolment | CreatedAccount:
    """Create a Cognito account, and enrol it when an organisation is named.

    **Cognito first, because its ``sub`` is the key** — there is
    nothing to write in the database until the account exists. That ordering
    creates the one failure this command has to handle explicitly: an account
    created and a database write that then fails. The account is **kept** and
    the ``user enrol`` remediation printed. Deleting it is out of scope (it is
    coupled to ownership transfer), and no path in this package calls
    ``AdminDeleteUser``.

    Two invitation modes (the ``COGNITO_DEFAULT``
    sender lands in spam; SES integration is the deferred fix):

    - ``email`` (default): ``DesiredDeliveryMediums=["EMAIL"]``, passed
      explicitly because **AWS defaults it to SMS** and the pool holds no
      phone numbers.
    - ``manual``: the invitation is suppressed and this command **mints** a
      single-use temporary password (printed once in the summary for
      out-of-band handover; the person sets their own at first sign-in —
      ``FORCE_CHANGE_PASSWORD``). Distinct from the deleted ``cognito-user``
      make target on every axis that killed it: nothing is accepted from the
      operator, nothing rides argv, and the credential is single-use and
      force-rotated rather than permanent. Uses no IAM beyond
      ``AdminCreateUser``.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The new account's address; also its sign-in identifier.
        display_name: Required, and never the email.
        org: Where to enrol them. Omit it to leave them in no organisation.
        invite: ``email`` or ``manual`` (validated by the parser).

    Returns:
        The enrolment when ``org`` is given (zero rows moved — a new account
        owns nothing yet), or a :class:`CreatedAccount` when it is not. Either
        carries the minted temporary password in ``manual`` mode.

    Raises:
        OpsError: If the address already exists and an organisation was named,
            if an existing account is already enrolled when none was named, if
            Cognito refuses the creation, or if the database write fails after
            the account was created — in ``manual`` mode that message carries
            the minted password, because the kept account has it and no email
            was sent.
    """
    _require_filter_safe(email)
    existing_sub = _find_sub_by_email(cognito, pool_id=pool_id, email=email)
    if existing_sub is not None and org is not None:
        raise OpsError(
            f"{email} already exists in the pool — use "
            f"`user enrol --email {email} --org {org.name!r} "
            f"--display-name {display_name!r}`"
        )
    minted: str | None = None
    if existing_sub is not None:
        return _finish_unenrolled(
            conn,
            sub=existing_sub,
            email=email,
            display_name=display_name,
            temporary_password=None,
            created_in_cognito=False,
        )
    request: dict[str, object] = {
        "UserPoolId": pool_id,
        "Username": email,
        "UserAttributes": [
            {"Name": "email", "Value": email},
            {"Name": "email_verified", "Value": "true"},
        ],
    }
    if invite == "manual":
        minted = _mint_temporary_password()
        request["TemporaryPassword"] = minted
        request["MessageAction"] = "SUPPRESS"
    else:
        request["DesiredDeliveryMediums"] = ["EMAIL"]
    try:
        response = cognito.admin_create_user(**request)  # type: ignore[arg-type]
    except ClientError as error:
        # The lookup above is Cognito's own exact-match filter, so it can lose
        # a race, and it cannot see an account whose alias — not its `email`
        # attribute — carries this address. Either way the answer is
        # `UsernameExistsException`, and an operator is owed a refusal naming
        # the remediation rather than a botocore traceback.
        code = error.response.get("Error", {}).get("Code", "") or "ClientError"
        if org is None:
            raise OpsError(
                f"Cognito refused to create {email} ({code}). Nothing was written. If the "
                f"account already exists, re-run `user create --email {email} "
                f"--display-name {display_name!r}` with no `--org`."
            ) from error
        raise OpsError(
            f"Cognito refused to create {email} ({code}). Nothing was written. If the "
            f"account already exists, enrol it: `user enrol --email {email} "
            f"--org {org.name!r} --display-name {display_name!r}`"
        ) from error
    sub = _sub_of(response["User"].get("Attributes", []))
    if not sub:
        if org is None:
            raise OpsError(
                f"Cognito created {email} but returned no `sub` attribute. The account "
                f"exists; re-run `user create --email {email} --display-name "
                f"{display_name!r}` with no `--org`."
            )
        raise OpsError(
            f"Cognito created {email} but returned no `sub` attribute. The account "
            f"exists; enrol it with `user enrol --email {email} "
            f"--org {org.name!r} --display-name {display_name!r}`."
        )
    if org is None:
        return _finish_unenrolled(
            conn,
            sub=sub,
            email=email,
            display_name=display_name,
            temporary_password=minted,
            created_in_cognito=True,
        )
    try:
        enrolment = _enrol(
            conn,
            sub=sub,
            email=email,
            display_name=display_name,
            org=org,
        )
    except Exception as error:
        # In manual mode the minted password must ride the refusal: the kept
        # account carries it, no email was ever sent, and `user create` refuses
        # existing addresses — losing it here would strand the account.
        kept_password = (
            f" Its single-use temporary password is: {minted} (printed once, 30-day expiry)."
            if minted is not None
            else ""
        )
        raise OpsError(
            f"the Cognito account for {email} was created and has been KEPT, but the "
            f"database write failed ({error}).{kept_password} Nothing was enrolled. "
            f"Re-run just the enrolment: `user enrol --email {email} "
            f"--org {org.name!r} --display-name {display_name!r}`"
        ) from error
    return replace(enrolment, temporary_password=minted)


def ensure_account_enrolled(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str,
    display_name: str,
    org: Organisation,
    reactivate: bool = False,
) -> Enrolment:
    """Ensure an account exists and belongs to ``org``, sending only a new invitation.

    A deactivated account (marked, or disabled in Cognito) is turned back on
    only when ``reactivate`` is true: an operator adding the person. Every
    other caller — waitlist approval, the self-signup sweep — is refused with
    :class:`Deactivated`, so the public form is never a way back in.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified Cognito user pool.
        email: The account address.
        display_name: The name stored on enrolment.
        org: The destination organisation.
        reactivate: Whether a deactivated account may be turned back on.

    Returns:
        The idempotent enrolment result.

    Raises:
        Deactivated: If the account is deactivated and ``reactivate`` is false.
        EnrolledElsewhere: If the account already belongs to another organisation.
        OpsError: If Cognito cannot create the account or does not return a subject.
    """
    _require_filter_safe(email)
    _require_mailable(email)
    found = _find_user_by_email(cognito, pool_id=pool_id, email=email)
    sub = (_sub_of(found.get("Attributes", [])) or None) if found is not None else None
    if sub is None:
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
                f"Cognito created {email} but returned no `sub` attribute. The account exists; "
                "nothing was enrolled."
            )
        enrolment = _enrol(conn, sub=sub, email=email, display_name=display_name, org=org)
        conn.execute(
            update(app_user).where(app_user.c.user_id == sub).values(invited_at=_now())
        )
        return replace(enrolment, invitation_sent=True)
    existing = _lock_user(conn, sub)
    assert found is not None  # sub came from it
    if (existing is not None and existing["deactivated_at"] is not None) or not _is_enabled(
        cognito, pool_id=pool_id, username=found["Username"]
    ):
        if not reactivate:
            raise Deactivated(email=email)
        # Refuse a different organisation before anything is turned back on: a
        # refused add must not restore a login (contract review, 2026-11-19).
        if existing is not None and existing["org_id"] not in (None, org.org_id):
            _raise_enrolled_elsewhere(conn, sub=sub, org_id=existing["org_id"], email=email)
        reactivate_user(conn, cognito, pool_id=pool_id, sub=sub)
        enrolment = _enrol_existing(conn, sub=sub, email=email, display_name=display_name,
                                    org=org, existing=existing)
        return replace(enrolment, reactivated=True)
    return _enrol_existing(conn, sub=sub, email=email, display_name=display_name,
                           org=org, existing=existing)


def _is_enabled(cognito: CognitoIdentityProviderClient, *, pool_id: str, username: str) -> bool:
    """Whether Cognito lets this account sign in, read from ``AdminGetUser``.

    ``ListUsers`` is eventually consistent, so it finds the account but does not
    decide this. A failed read raises: the caller fails closed.
    """
    return bool(cognito.admin_get_user(UserPoolId=pool_id, Username=username)["Enabled"])


def _raise_enrolled_elsewhere(
    conn: Connection, *, sub: str, org_id: uuid.UUID, email: str
) -> NoReturn:
    """Raise the "already in another organisation" refusal, naming it."""
    other = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == org_id)
    ).scalar_one()
    raise EnrolledElsewhere(sub=sub, org_name=other, org_id=org_id, email=email)


def _enrol_existing(
    conn: Connection,
    *,
    sub: str,
    email: str,
    display_name: str,
    org: Organisation,
    existing: RowMapping | None,
) -> Enrolment:
    """Enrol an account Cognito already has, under today's rules.

    Raises:
        EnrolledElsewhere: If the account already belongs to another organisation.
    """
    if existing is None:
        return _enrol(conn, sub=sub, email=email, display_name=display_name, org=org)
    if existing["org_id"] is None:
        # An account that exists keeps its stored name: the name offered here
        # may come from the public form (the sweep), and a stranger must not be
        # able to rename a colleague.
        return _enrol(
            conn, sub=sub, email=email, display_name=existing["display_name"], org=org
        )
    if existing["org_id"] == org.org_id:
        return Enrolment(
            user_id=sub,
            email=email,
            org=org,
            created=False,
            tasks_moved=0,
            projects_moved=0,
        )
    _raise_enrolled_elsewhere(conn, sub=sub, org_id=existing["org_id"], email=email)


def _finish_unenrolled(
    conn: Connection,
    *,
    sub: str,
    email: str,
    display_name: str,
    temporary_password: str | None,
    created_in_cognito: bool,
) -> CreatedAccount:
    """Record an account with no organisation, keeping Cognito on a write failure.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The Cognito subject.
        email: The address, for the operator line only. Not stored.
        display_name: Written onto the unenrolled row.
        temporary_password: Minted this call, if any. A failure message
            includes it when this call created the Cognito account.
        created_in_cognito: Whether this call called ``AdminCreateUser``.

    Returns:
        The unenrolled account.

    Raises:
        OpsError: If the subject is already enrolled, or the database write fails.
    """
    try:
        _record_unenrolled(conn, sub=sub, email=email, display_name=display_name)
    except OpsError:
        raise
    except Exception as error:
        if not created_in_cognito:
            raise OpsError(
                f"the database write for {email} failed ({error}). Nothing was written."
            ) from error
        kept_password = (
            f" Its single-use temporary password is: {temporary_password} (printed once, "
            f"30-day expiry)."
            if temporary_password is not None
            else ""
        )
        raise OpsError(
            f"the Cognito account for {email} was created and has been KEPT, but the "
            f"database write failed ({error}).{kept_password} Nothing was written in "
            f"the database. Re-run `user create --email {email} --display-name "
            f"{display_name!r}` with no `--org`."
        ) from error
    return CreatedAccount(
        user_id=sub,
        email=email,
        created=created_in_cognito,
        temporary_password=temporary_password,
    )


def _record_unenrolled(conn: Connection, *, sub: str, email: str, display_name: str) -> None:
    """Insert or refresh an ``app_user`` row with no organisation.

    The address is stored so an operator can find the person later. It does not
    place them in an organisation, and :func:`set_admin` still refuses the
    support role until an enrolment does.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The Cognito subject.
        email: The address to store.
        display_name: The name to store. Updated when the row is already
            unenrolled, so a retry after a failed write lands the name.

    Raises:
        OpsError: If the subject is already in an organisation.
    """
    existing = _lock_user(conn, sub)
    if existing is not None and existing["org_id"] is not None:
        raise OpsError(
            f"{email} ({sub}) is already in an organisation. Nothing was written. "
            f"Move them with `user enrol --email {email} --display-name {display_name!r} "
            f"--org '<organisation>'`."
        )
    if existing is None:
        conn.execute(
            insert(app_user).values(
                user_id=sub, display_name=display_name, email=email, created_at=_now()
            )
        )
        return
    changes: dict[str, str] = {}
    if existing["display_name"] != display_name:
        changes["display_name"] = display_name
    if existing["email"] != email:
        changes["email"] = email
    if changes:
        conn.execute(update(app_user).where(app_user.c.user_id == sub).values(**changes))


def reissue_temporary_password(
    conn: Connection, cognito: CognitoIdentityProviderClient, *, pool_id: str, email: str
) -> Reissue:
    """Replace an account's password with a new single-use temporary one.

    Serves an account that never signed in (``FORCE_CHANGE_PASSWORD``) and one
    that has (``CONFIRMED``). A person with a working mailbox should use "Forgot
    password" instead: this call replaces a password they may still know and
    gives the operator a working credential for their account. It exists for a
    lost invitation and for an address with no mailbox. The new password is
    always set non-permanent, so the person chooses their own at the next
    sign-in.

    Changes Cognito only: the account's enrolment, if any, is unchanged, and an
    account kept after a failed ``user create`` database write (no row) is
    reissuable. The database is read to refuse a deactivated person.

    Args:
        conn: A database connection, to read the person's deactivated mark.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The account's address.

    Returns:
        The reissue, carrying the minted temporary password.

    Raises:
        OpsError: If the pool holds no such address, the account's status is
            neither of the two above, the person is deactivated (marked in the
            database or disabled in Cognito), or Cognito refuses the change.
    """
    _require_filter_safe(email)
    user = _find_user_by_email(cognito, pool_id=pool_id, email=email)
    if user is None:
        raise OpsError(f"no account in the pool for {email}")
    status = user.get("UserStatus")
    if status not in ("FORCE_CHANGE_PASSWORD", "CONFIRMED"):
        raise OpsError(
            f"{email} is {status}: only a FORCE_CHANGE_PASSWORD or CONFIRMED account "
            "can be reissued. Nothing was changed."
        )
    row = _lock_user(conn, _sub_of(user.get("Attributes", [])))
    if (row is not None and row["deactivated_at"] is not None) or not _is_enabled(
        cognito, pool_id=pool_id, username=user["Username"]
    ):
        # Either sign means locked out, as in `user reset-app`. A new password
        # could not sign in now, and would be a working credential the moment
        # the account is turned back on.
        raise OpsError(
            f"{email} is deactivated, so no password was reissued. Nothing was "
            "changed. Reactivate the account first if they should sign in again."
        )
    minted = _mint_temporary_password()
    try:
        cognito.admin_set_user_password(
            UserPoolId=pool_id, Username=user["Username"], Password=minted, Permanent=False
        )
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "") or "ClientError"
        raise OpsError(
            f"Cognito refused to reissue {email} ({code}). Nothing was changed."
        ) from error
    return Reissue(
        user_id=_sub_of(user.get("Attributes", [])),
        email=email,
        temporary_password=minted,
    )


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

    The ``app_user`` upsert **and** the row moves are one
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
            on a stale view; ``user resync``
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
    return _enrol(conn, sub=sub, email=email, display_name=display_name, org=org)


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
    # ON CONFLICT DO UPDATE: ops enrolment clobbers deliberately,
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
    severed = _sever_cross_owner_memberships(conn, sub=sub)
    tasks_moved, projects_moved = _stamp_owned_rows(
        conn, sub=sub, org_id=org.org_id, visibility=_PRIVATE
    )
    return Enrolment(
        user_id=sub,
        email=email,
        org=org,
        created=existing is None,
        tasks_moved=tasks_moved,
        projects_moved=projects_moved,
        memberships_severed=severed,
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

    **It refuses a row with no organisation.** The stored address of someone
    outside an organisation is written by ``user create`` and kept by
    de-enrolment, so an operator can still find them. Updating it is part of
    keeping an enrolled person's record current; placing them back is
    ``user enrol``, which is also what makes a support-role grant possible
    (see :func:`set_admin`).

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The current address in Cognito.

    Returns:
        The resync, saying whether anything changed.

    Raises:
        OpsError: If the pool holds no such address, or the subject behind it
            has never been enrolled, or has been de-enrolled since.
    """
    _require_filter_safe(email)
    sub = _find_sub_by_email(cognito, pool_id=pool_id, email=email)
    if sub is None:
        raise OpsError(f"no account in the pool for {email}")
    row = _lock_user(conn, sub)
    if row is None:
        raise OpsError(
            f"{email} ({sub}) has a Cognito account but is not enrolled — use `user enrol`"
        )
    if row["org_id"] is None:
        raise OpsError(
            f"{sub} is in no organisation — de-enrolled, or has only ever signed in. "
            f"Nothing was written. Place them with `user enrol --email {email}` "
            "before updating the stored address."
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

    Clears ``org_id`` and ``is_admin`` on ``app_user``, and ``org_id`` on every
    task and project the person owns — so the organisation they left loses
    sight of their work (the alternative needs ownership transfer, which is
    out of scope). The stored
    address stays, so the person remains findable. The support role does not:
    :func:`set_admin` refuses a grant while ``org_id`` is null.

    **``visibility`` is deliberately untouched.** The rows return to
    ``org_id IS NULL``, where the NULL rule already makes them reachable by
    their owner alone, so re-privatising would change nothing a caller can
    observe while destroying the choices the person made. The invariant holds
    because both tables are cleared in the same set operation: a member and its
    project arrive at NULL together, and neither one's visibility moved.

    Args:
        conn: Open connection inside the command's transaction.
        email: The stored address to resolve by; mutually exclusive with ``sub``.
        sub: The Cognito subject to resolve by.

    Returns:
        The de-enrolment, including the counts cleared.

    Raises:
        OpsError: If the person cannot be resolved, resolves ambiguously, or is
            already in no organisation and holds no support role.
    """
    row = _resolve_and_lock(conn, email=email, sub=sub)
    user_id = str(row["user_id"])
    if row["org_id"] is None and not row["is_admin"] and not row["is_ops"]:
        raise OpsError(f"{user_id} is in no organisation; nothing to do")
    conn.execute(
        update(app_user)
        .where(app_user.c.user_id == user_id)
        .values(org_id=None, is_admin=False, is_ops=False)
    )
    severed = _sever_cross_owner_memberships(conn, sub=user_id)
    tasks_cleared, projects_cleared = _clear_owned_rows(conn, sub=user_id)
    return DeEnrolment(
        user_id=user_id,
        email=row["email"],
        tasks_cleared=tasks_cleared,
        projects_cleared=projects_cleared,
        admin_revoked=bool(row["is_admin"]),
        ops_revoked=bool(row["is_ops"]),
        memberships_severed=severed,
    )


def deactivate_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str | None = None,
    sub: str | None = None,
) -> Deactivation:
    """Lock a person out: disable their login and mark them deactivated.

    This is what to run when someone leaves. They keep their organisation,
    tasks, projects, cohorts and quotas, so
    :func:`reactivate_user` is a clean undo.

    **The order, and why.**

    1. Find the person (see below).
    2. Cognito: ``AdminDisableUser`` (no new sign-in), then
       ``AdminUserGlobalSignOut`` (their refresh tokens stop working, so no
       session can be renewed). If either call fails, this stops and raises
       before any database write, so the database is untouched.
    3. Database, inside the caller's one transaction: set ``deactivated_at``,
       clear the support and ops roles, and switch off every public link on
       the tasks they own (``task.is_public = false``).

    Cognito goes first so the dangerous half — a working login — is closed
    before anything else. If the database step then fails, the account stays
    disabled and the transaction rolls back; running the same command again
    completes it (disabling an already-disabled account succeeds).

    An access token issued before this runs stays valid until it expires (up to
    60 minutes), and with the organisation kept it can still read the
    organisation's shared work in that window (accepted, contract 066).

    **Finding the person.** Exactly one of ``email`` or ``sub``:

    - ``sub``: the ``app_user`` row with that id, if any.
    - ``email``: the ``app_user`` row storing that address; if none does (they
      only ever signed in, so no address was stored), Cognito is asked which
      account has that address, and that account's row is used if one exists.

    A Cognito account with no row is disabled only; a row whose account was
    deleted from the pool gets the database half only. Neither is a refusal.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The address to find them by; mutually exclusive with ``sub``.
        sub: The Cognito subject to find them by.

    Returns:
        The deactivation, listing the steps taken.

    Raises:
        OpsError: If neither or both selectors are given, the address is
            stored on more than one row, neither the pool nor the database
            knows the person, or Cognito refuses either call (the database
            is then untouched).
    """
    row, user, user_id = _resolve_account(conn, cognito, pool_id=pool_id, email=email, sub=sub)
    who = email or (row["email"] if row is not None else None) or user_id

    if user is None:
        # The account was deleted from the pool earlier (by hand, or the pool
        # was replaced) but the row remains: nothing to disable, and the
        # database half must still run or their public links stay live.
        steps = ["no Cognito account in the pool (deleted earlier): nothing to disable"]
    else:
        username = user["Username"]
        # Cognito first. A failure here raises before any database write.
        try:
            cognito.admin_disable_user(UserPoolId=pool_id, Username=username)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "") or "ClientError"
            raise OpsError(
                f"Cognito refused to disable {who} ({code}). Nothing was changed."
            ) from error
        try:
            cognito.admin_user_global_sign_out(UserPoolId=pool_id, Username=username)
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "") or "ClientError"
            raise OpsError(
                f"the Cognito account for {who} is DISABLED, but signing it out everywhere "
                f"failed ({code}). Nothing in the database was changed. Re-run "
                f"`user deactivate --sub {user_id}` to finish."
            ) from error
        steps = ["disabled the Cognito account", "signed out everywhere (refresh tokens revoked)"]

    if row is None:
        steps.append("no app_user row: Cognito only, the database was not touched")
        return Deactivation(
            user_id=user_id,
            email=email,
            steps=tuple(steps),
            links_made_private=0,
            already=False,
        )

    already = row["deactivated_at"] is not None
    conn.execute(
        update(app_user)
        .where(app_user.c.user_id == user_id)
        .values(
            deactivated_at=row["deactivated_at"] if already else _now(),
            is_admin=False,
            is_ops=False,
        )
    )
    steps.append("already deactivated" if already else "marked deactivated")
    if row["is_admin"] or row["is_ops"]:
        steps.append("cleared the admin and ops roles")
    links = int(
        conn.execute(
            update(task)
            .where(task.c.owner_user_id == user_id, task.c.is_public)
            .values(is_public=False)
        ).rowcount
    )
    steps.append(f"made {links} public task link(s) private")
    return Deactivation(
        user_id=user_id,
        email=row["email"] or email,
        steps=tuple(steps),
        links_made_private=links,
        already=already,
        admin_revoked=bool(row["is_admin"]),
        ops_revoked=bool(row["is_ops"]),
    )


def reactivate_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    sub: str,
) -> Reactivation:
    """Turn a person's login back on and clear their deactivated mark.

    It does not give back the support or ops role, or any public link: those
    are separate, deliberate acts. It also enables an account disabled in
    Cognito with no mark (people offboarded before task 066).

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        sub: The Cognito subject.

    Returns:
        The reactivation; ``changed`` is false when there was nothing to undo.

    Raises:
        OpsError: If the pool does not know the person, or Cognito refuses.
    """
    _require_filter_safe(sub)
    row = _lock_user(conn, sub)
    user = _find_user_by_sub(cognito, pool_id=pool_id, sub=sub)
    if user is None:
        raise OpsError(f"no account in the pool for {sub}. Nothing was changed.")
    email = row["email"] if row is not None else None
    marked = row is not None and row["deactivated_at"] is not None
    disabled = not _is_enabled(cognito, pool_id=pool_id, username=user["Username"])
    if not marked and not disabled:
        return Reactivation(user_id=sub, email=email, changed=False)
    if disabled:
        try:
            cognito.admin_enable_user(UserPoolId=pool_id, Username=user["Username"])
        except ClientError as error:
            code = error.response.get("Error", {}).get("Code", "") or "ClientError"
            raise OpsError(
                f"Cognito refused to enable {sub} ({code}). Nothing was changed."
            ) from error
    if marked:
        conn.execute(
            update(app_user).where(app_user.c.user_id == sub).values(deactivated_at=None)
        )
    return Reactivation(user_id=sub, email=email, changed=True)


def reset_authenticator_app(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str | None = None,
    sub: str | None = None,
) -> AppReset:
    """Unlink a person's authenticator app, for a lost or replaced phone.

    Their next sign-in asks for their password and then shows the QR code to
    link an app again. The person is found the way :func:`deactivate_user`
    finds them.

    **The order, and why.** ``AdminUserGlobalSignOut`` first: it ends every
    session (refresh tokens stop working) and is harmless on its own and safe
    to repeat. Then ``AdminDeleteSoftwareToken`` removes the app link. If the
    second call fails, the person is signed out and the link may or may not
    remain; running the command again is safe. Cognito only: the database is
    read, not written. The audit row is written by the CLI.

    Found by ``--email``, the command refuses unless the pool's current address
    for that person is the one given: a stale database address must not reset
    someone else's app.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The address to find them by; mutually exclusive with ``sub``.
        sub: The Cognito subject to find them by.

    Returns:
        The reset.

    Raises:
        OpsError: If the person cannot be found as above, the pool holds no
            account for them, the pool's address differs from ``email``, they
            are deactivated (marked in the database or
            disabled in Cognito; nothing is called then), or Cognito refuses
            either call.
    """
    row, user, user_id = _resolve_account(conn, cognito, pool_id=pool_id, email=email, sub=sub)
    who = email or (row["email"] if row is not None else None) or user_id
    if user is None:
        raise OpsError(f"no account in the pool for {who}. Nothing was changed.")
    if email is not None:
        pool_email = next(
            (
                str(a.get("Value", ""))
                for a in user.get("Attributes", [])
                if a.get("Name") == "email"
            ),
            "",
        )
        if pool_email.strip().lower() != email.strip().lower():
            raise OpsError(
                f"the address on file for {email} no longer matches Cognito for that "
                f"person ({user_id}), so their authenticator app was not reset — run "
                f"`user resync` or pass `--sub`. Nothing was changed."
            )
    username = user["Username"]
    if (row is not None and row["deactivated_at"] is not None) or not _is_enabled(
        cognito, pool_id=pool_id, username=username
    ):
        raise OpsError(
            f"{who} is deactivated, so their authenticator app was not reset — "
            f"`user reactivate --sub {user_id}` first. Nothing was changed."
        )
    rerun = f"Running `user reset-app --sub {user_id}` again is safe."
    try:
        cognito.admin_user_global_sign_out(UserPoolId=pool_id, Username=username)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "") or "ClientError"
        raise OpsError(
            f"Cognito refused to sign {who} out everywhere ({code}), so their "
            f"authenticator app was not reset. Nothing was changed. {rerun}"
        ) from error
    try:
        cognito.admin_delete_software_token(UserPoolId=pool_id, Username=username)
    except ClientError as error:
        code = error.response.get("Error", {}).get("Code", "") or "ClientError"
        raise OpsError(
            f"{who} was signed out everywhere, but removing their authenticator app "
            f"link failed ({code}). If they never linked an app, or it was already "
            f"removed, there is nothing to reset; otherwise running "
            f"`user reset-app --sub {user_id}` again is safe. "
            f"No audit row was written."
        ) from error
    return AppReset(user_id=user_id, email=row["email"] if row is not None else email)


def set_admin(
    conn: Connection, *, grant: bool, email: str | None = None, sub: str | None = None
) -> AdminChange:
    """Grant or revoke the support role.

    A privileged grant with no record of who made it is not
    auditable. The record is :meth:`AdminChange.admin_changes`, emitted by the
    CLI **after** the commit — this function does not log, for the reason the
    module docstring gives.

    **The subject is resolved in the database, not in Cognito**, and by address
    by default. De-enrolment keeps that address and clears the organisation and
    the support role. If operator A de-enrols while operator B grants, the
    ``FOR UPDATE`` read serialises them and B finds a row in no organisation —
    the grant refuses instead of resurrecting the role. In the other commit
    order B's grant lands first and A's de-enrolment clears it. Neither order
    leaves an administrator behind.

    ``--sub`` exists because an address is not unique (``app_user.email`` carries
    no constraint) and the ambiguous case has to stay resolvable — revoking a
    compromised administrator is the least acceptable place for a dead end. It
    bypasses the address selector, not the interlock: a **grant** refuses a
    subject with no organisation, whichever selector found them.

    Args:
        conn: Open connection inside the command's transaction.
        grant: ``True`` to grant, ``False`` to revoke.
        email: The stored address of the subject; mutually exclusive with
            ``sub``.
        sub: The Cognito subject to resolve by.

    Returns:
        The change that was made.

    Raises:
        OpsError: If no enrolled subject matches, more than one does, the flag
            already holds the requested value, or a grant names a subject who is
            in no organisation.
    """
    row = _resolve_and_lock(conn, email=email, sub=sub)
    user_id = str(row["user_id"])
    stored_email: str | None = row["email"]
    who = stored_email or user_id
    direction = "grant" if grant else "revoke"
    if grant and row["org_id"] is None:
        # The address stays on an unenrolled row so an operator can find the
        # person. The organisation is what the support role requires. Revoke is
        # deliberately still allowed: taking the role away must never be the
        # blocked direction.
        raise OpsError(
            f"{who} is in no organisation, so the support role cannot be granted — "
            "`user enrol` first. Nothing was written."
        )
    if grant and row["deactivated_at"] is not None:
        # A role granted now would come back with the login (contract review,
        # 2026-11-19): reactivate first, then grant.
        raise OpsError(
            f"{who} is deactivated, so the support role cannot be granted — "
            "`user reactivate` first. Nothing was written."
        )
    if bool(row["is_admin"]) == grant:
        state = "already an administrator" if grant else "not an administrator"
        raise OpsError(f"{who} ({user_id}) is {state}; nothing to {direction}")
    conn.execute(update(app_user).where(app_user.c.user_id == user_id).values(is_admin=grant))
    return AdminChange(user_id=user_id, email=stored_email, direction=direction)


def set_ops(
    conn: Connection, *, grant: bool, email: str | None = None, sub: str | None = None
) -> OpsChange:
    """Grant or revoke the ops role using the administrator-role interlocks.

    Args:
        conn: Open connection inside the command transaction.
        grant: Whether to grant rather than revoke the role.
        email: Stored account address, mutually exclusive with ``sub``.
        sub: Cognito subject, mutually exclusive with ``email``.

    Returns:
        The completed role change.

    Raises:
        OpsError: If the subject cannot receive the requested role change.
    """
    row = _resolve_and_lock(conn, email=email, sub=sub)
    user_id = str(row["user_id"])
    stored_email: str | None = row["email"]
    who = stored_email or user_id
    direction = "grant" if grant else "revoke"
    if grant and row["org_id"] is None:
        raise OpsError(
            f"{who} is in no organisation, so the ops role cannot be granted — "
            "`user enrol` first. Nothing was written."
        )
    if grant and row["deactivated_at"] is not None:
        # A role granted now would come back with the login (contract review,
        # 2026-11-19): reactivate first, then grant.
        raise OpsError(
            f"{who} is deactivated, so the ops role cannot be granted — "
            "`user reactivate` first. Nothing was written."
        )
    if bool(row["is_ops"]) == grant:
        state = "already holds the ops role" if grant else "does not hold the ops role"
        raise OpsError(f"{who} ({user_id}) {state}; nothing to {direction}")
    conn.execute(update(app_user).where(app_user.c.user_id == user_id).values(is_ops=grant))
    return OpsChange(user_id=user_id, email=stored_email, direction=direction)


def move_user(conn: Connection, *, sub: str, org: Organisation) -> Enrolment:
    """Move an existing stored person to another organisation.

    Args:
        conn: Open connection inside the command transaction.
        sub: The Cognito subject of the stored person.
        org: The destination organisation.

    Returns:
        The completed enrolment move.

    Raises:
        OpsError: If no stored person exists for ``sub``.
    """
    row = _lock_user(conn, sub)
    if row is None:
        raise OpsError(f"no user {sub}")
    return _enrol(
        conn,
        sub=sub,
        email=row["email"],
        display_name=row["display_name"],
        org=org,
    )


def resend_invitation(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    sub: str,
    now: datetime,
) -> Resend:
    """Re-send a pending Cognito invitation after its one-hour cooldown.

    Args:
        conn: Open connection inside the command transaction.
        cognito: Client bound to the verified user pool.
        pool_id: The verified Cognito user pool.
        sub: Cognito subject receiving the invitation.
        now: The current time, supplied by callers for deterministic tests.

    Returns:
        The sent invitation record.

    Raises:
        ResendTooSoon: If the prior invitation is less than an hour old.
        OpsError: If the person is not eligible for an invitation resend.
    """
    row = _lock_user(conn, sub)
    if row is None or not row["email"]:
        raise OpsError(f"{sub} has no stored email; nothing was sent")
    invited_at = row["invited_at"]
    if invited_at is not None and now - invited_at < timedelta(hours=1):
        raise ResendTooSoon(retry_after=invited_at + timedelta(hours=1))
    user = _find_user_by_sub(cognito, pool_id=pool_id, sub=sub)
    if user is None:
        raise OpsError(f"no account in the pool for {sub}; nothing was sent")
    if user.get("UserStatus") != "FORCE_CHANGE_PASSWORD":
        raise OpsError(
            f"{row['email']} is {user.get('UserStatus')}, not FORCE_CHANGE_PASSWORD; Cognito "
            "cannot resend an invitation for a confirmed account. Nothing was sent."
        )
    cognito.admin_create_user(
        UserPoolId=pool_id,
        Username=user["Username"],
        MessageAction="RESEND",
        DesiredDeliveryMediums=["EMAIL"],
    )
    conn.execute(update(app_user).where(app_user.c.user_id == sub).values(invited_at=now))
    return Resend(user_id=sub, email=row["email"], sent_at=now)


def set_quota(
    conn: Connection,
    *,
    user_id: str | None = None,
    org_id: uuid.UUID | None = None,
    cohort_id: uuid.UUID | None = None,
    task_quota_per_year: int | None,
    runs_per_user: int | None,
) -> QuotaChange:
    """Set or clear both quota overrides on exactly one user, organisation or cohort.

    Args:
        conn: Open connection inside the command transaction.
        user_id: User subject, mutually exclusive with ``org_id``.
        org_id: Organisation identifier; exactly one of the three is given.
        cohort_id: Cohort identifier.
        task_quota_per_year: Task quota override; ``None`` inherits.
        runs_per_user: Simultaneous run override; ``None`` inherits.

    Returns:
        The previous and requested quota values.

    Raises:
        OpsError: If selection is invalid, absent, or a quota is negative.
    """
    choices = (("user", user_id), ("organisation", org_id), ("cohort", cohort_id))
    given = [(name, value) for name, value in choices if value is not None]
    if len(given) != 1:
        raise OpsError("give exactly one of user_id, org_id or cohort_id")
    if any(value is not None and value < 0 for value in (task_quota_per_year, runs_per_user)):
        raise OpsError("quota values cannot be negative")
    kind, identifier = given[0]
    table, key = {
        "user": (app_user, app_user.c.user_id),
        "organisation": (organisation, organisation.c.org_id),
        "cohort": (cohort, cohort.c.cohort_id),
    }[kind]
    row = (
        conn.execute(select(table).where(key == identifier).with_for_update())
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound(f"no {kind} {identifier}")
    conn.execute(
        update(table)
        .where(key == identifier)
        .values(task_quota_per_year=task_quota_per_year, runs_per_user=runs_per_user)
    )
    return QuotaChange(
        who=str(identifier),
        task_quota_before=row["task_quota_per_year"],
        runs_before=row["runs_per_user"],
        task_quota_after=task_quota_per_year,
        runs_after=runs_per_user,
    )


def _normalise_domain(domain: str) -> str:
    """Validate and lower-case a domain token."""
    value = domain.lower()
    if not value or any(character.isspace() for character in value) or "@" in value:
        raise OpsError("domain must be non-empty, contain no whitespace, and omit @")
    return value


def add_domain(conn: Connection, *, domain: str, org: Organisation) -> DomainChange:
    """Map a lower-case email domain to an organisation."""
    value = _normalise_domain(domain)
    existing = conn.execute(
        select(organisation_domain.c.domain).where(organisation_domain.c.domain == value)
    ).scalar_one_or_none()
    if existing is not None:
        raise OpsError(f"domain {value} already belongs to an organisation")
    conn.execute(
        insert(organisation_domain).values(domain=value, org_id=org.org_id, created_at=_now())
    )
    return DomainChange(domain=value, org=org, added=True)


def remove_domain(conn: Connection, *, domain: str) -> DomainChange:
    """Remove an organisation-domain mapping."""
    value = _normalise_domain(domain)
    removed = conn.execute(delete(organisation_domain).where(organisation_domain.c.domain == value))
    if removed.rowcount == 0:
        raise OpsError(f"no organisation domain {value}")
    return DomainChange(domain=value, org=None, added=False)


#: The most links one cohort carries; a sanity bound, not a design limit.
COHORT_LINKS_MAX = 10


@dataclass(frozen=True)
class Cohort(Record):
    """One cohort, saved, deleted or resolved."""

    cohort_id: uuid.UUID
    name: str

    def summary(self) -> str:
        """Render the cohort line."""
        return f"cohort {self.name!r} ({self.cohort_id})"


@dataclass(frozen=True)
class CohortMembership(Record):
    """One person added to or removed from a cohort."""

    cohort: Cohort
    user_id: str
    added: bool
    changed: bool

    def summary(self) -> str:
        """Render the membership change, or say nothing changed."""
        verb = "added to" if self.added else "removed from"
        if not self.changed:
            where = "in" if self.added else "not in"
            return f"already {where} {self.cohort.name!r}; nothing changed"
        return f"{verb} {self.cohort.name!r}"


def _require_links(links: Sequence[str]) -> list[str]:
    """Keep non-empty web addresses; refuse anything else."""
    kept = [link.strip() for link in links if link.strip()]
    if len(kept) > COHORT_LINKS_MAX:
        raise OpsError(f"a cohort holds at most {COHORT_LINKS_MAX} links")
    for link in kept:
        if not link.startswith(("https://", "http://")) or any(c.isspace() for c in link):
            raise OpsError(f"links must be web addresses starting with https:// ({link!r})")
    return kept


def resolve_cohort(conn: Connection, cohort_id: uuid.UUID) -> Cohort:
    """Return one cohort by id.

    Raises:
        NotFound: If no cohort has that id.
    """
    name = conn.execute(
        select(cohort.c.name).where(cohort.c.cohort_id == cohort_id)
    ).scalar_one_or_none()
    if name is None:
        raise NotFound(f"no cohort {cohort_id}")
    return Cohort(cohort_id=cohort_id, name=str(name))


def save_cohort(
    conn: Connection,
    *,
    cohort_id: uuid.UUID | None,
    name: str,
    description: str | None,
    starts_on: date | None,
    ends_on: date | None,
    links: Sequence[str],
) -> Cohort:
    """Create a cohort (``cohort_id`` None) or replace an existing one's details.

    Raises:
        NotFound: If ``cohort_id`` names no cohort.
        OpsError: On a taken name, an end before the start, or a bad link.
    """
    name = name.strip()
    if not name:
        raise OpsError("a cohort needs a name")
    if starts_on is not None and ends_on is not None and ends_on < starts_on:
        raise OpsError("the end date is before the start date")
    values = {
        "name": name,
        "description": (description or "").strip() or None,
        "starts_on": starts_on,
        "ends_on": ends_on,
        "links": _require_links(links),
    }
    taken = conn.execute(
        select(cohort.c.cohort_id).where(cohort.c.name == name)
    ).scalar_one_or_none()
    if taken is not None and taken != cohort_id:
        raise OpsError(f"a cohort named {name!r} already exists")
    try:
        if cohort_id is None:
            cohort_id = uuid.uuid4()
            conn.execute(insert(cohort).values(cohort_id=cohort_id, created_at=_now(), **values))
        else:
            resolve_cohort(conn, cohort_id)
            conn.execute(update(cohort).where(cohort.c.cohort_id == cohort_id).values(**values))
    except IntegrityError as error:  # a second operator won the race to the name
        raise OpsError(f"a cohort named {name!r} already exists") from error
    return Cohort(cohort_id=cohort_id, name=name)


def delete_cohort(conn: Connection, *, cohort_id: uuid.UUID) -> Cohort:
    """Delete a cohort and its memberships; the people are untouched."""
    found = resolve_cohort(conn, cohort_id)
    conn.execute(delete(cohort).where(cohort.c.cohort_id == cohort_id))
    return found


def add_to_cohort(conn: Connection, *, target: Cohort, user_id: str) -> CohortMembership:
    """Add one person to a cohort; adding a member again changes nothing.

    Raises:
        NotFound: If no person has that id.
    """
    if _lock_user(conn, user_id) is None:
        raise NotFound(f"no user {user_id}")
    # RETURNING, not rowcount: an INSERT's rowcount is -1 through SQLAlchemy here.
    added = conn.execute(
        pg_insert(cohort_member)
        .values(cohort_id=target.cohort_id, user_id=user_id, added_at=_now())
        .on_conflict_do_nothing()
        .returning(cohort_member.c.user_id)
    ).first()
    return CohortMembership(cohort=target, user_id=user_id, added=True, changed=added is not None)


def join_cohorts(
    conn: Connection, *, actor: str, user_id: str, cohorts: Sequence[Cohort]
) -> list[tuple[str, uuid.UUID]]:
    """Add a person to each cohort, writing a ``cohort.add`` audit row only for a new membership.

    Args:
        conn: Open connection inside the caller's transaction.
        actor: Who the audit rows name.
        user_id: The person.
        cohorts: The cohorts to join.

    Returns:
        The audit target and action id of each new membership, in order.

    Raises:
        NotFound: If no person has that id.
    """
    added: list[tuple[str, uuid.UUID]] = []
    for target in cohorts:
        if add_to_cohort(conn, target=target, user_id=user_id).changed:
            audit_target = f"{user_id}/cohort/{target.cohort_id}"
            added.append((audit_target, record_action(
                conn, actor=actor, action="cohort.add", target=audit_target, outcome="ok"
            )))
    return added


def remove_from_cohort(conn: Connection, *, target: Cohort, user_id: str) -> CohortMembership:
    """Remove one person from a cohort; removing a non-member changes nothing."""
    removed = conn.execute(
        delete(cohort_member).where(
            cohort_member.c.cohort_id == target.cohort_id, cohort_member.c.user_id == user_id
        )
    )
    return CohortMembership(
        cohort=target, user_id=user_id, added=False, changed=removed.rowcount == 1
    )


#: Limits on an invite link.
INVITE_DOMAINS_MAX = 10
INVITE_USES_MAX = 1000
#: How far ahead a link may end. One day more than ninety, because the page
#: sends the end of the chosen day in the operator's own time zone.
INVITE_AHEAD_MAX = timedelta(days=91)

#: The state of an invite link, worked out when it is read.
InviteLinkState = Literal["active", "expired", "full", "revoked"]


@dataclass(frozen=True)
class InviteLink(Record):
    """One invite link. ``code`` is kept out of ``repr`` so it never reaches a log line."""

    invite_link_id: uuid.UUID
    code: str = field(repr=False)
    label: str
    org_id: uuid.UUID
    allowed_domains: tuple[str, ...]
    max_uses: int
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime

    def summary(self) -> str:
        """Render the link by its label and id, never its code."""
        return f"invite link {self.label!r} ({self.invite_link_id})"


def invite_link_state(link: InviteLink, uses: int, now: datetime) -> InviteLinkState:
    """Return whether a link can still make accounts, and if not, why.

    Args:
        link: The link.
        uses: How many requests the link has redeemed.
        now: The time to judge at.

    Returns:
        ``revoked``, ``expired`` or ``full`` in that order of precedence, else ``active``.
    """
    if link.revoked_at is not None:
        return "revoked"
    if link.expires_at <= now:
        return "expired"
    if uses >= link.max_uses:
        return "full"
    return "active"


#: Why a waiting request that carries a code has no account yet.
InviteRequestReason = Literal[
    "unknown_code", "wrong_domain", "expired", "full", "revoked", "next_run"
]


def email_domain(email: str) -> str:
    """Return an address's domain, lower-cased, or ``""`` when it has no ``@``."""
    # Must match the sweep query's lower(split_part(email, '@', 2)).
    return email.split("@")[1].lower() if "@" in email else ""


def invite_request_reason(
    *,
    request_domain: str,
    link: InviteLink | None,
    uses: int,
    now: datetime,
) -> InviteRequestReason:
    """Say why a waiting request's code has not made an account yet.

    Args:
        request_domain: The request's email domain, lower-cased.
        link: The link with the request's code, or ``None`` when no link has it.
        uses: How many requests the link has redeemed.
        now: The time to judge the link at.

    Returns:
        ``unknown_code``; ``wrong_domain``; the link's state when it is not
        active; else ``next_run`` (the sweep redeems it at its next run).
    """
    if link is None:
        return "unknown_code"
    if request_domain not in link.allowed_domains:
        return "wrong_domain"
    state = invite_link_state(link, uses, now)
    return "next_run" if state == "active" else state


def invite_link_record(row: RowMapping) -> InviteLink:
    """Build the record from an ``invite_link`` row."""
    return InviteLink(
        invite_link_id=row["invite_link_id"], code=str(row["code"]), label=str(row["label"]),
        org_id=row["org_id"], allowed_domains=tuple(row["allowed_domains"]),
        max_uses=int(row["max_uses"]), expires_at=row["expires_at"],
        revoked_at=row["revoked_at"], created_at=row["created_at"],
    )


def invite_link_uses_by_id(
    conn: Connection, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, int]:
    """Count the requests each link has redeemed; a link with no use is left out."""
    if not ids:
        return {}
    return {link_id: int(count) for link_id, count in conn.execute(
        select(waitlist_entry.c.invite_link_id, func.count())
        .where(waitlist_entry.c.invite_link_id.in_(ids))
        .group_by(waitlist_entry.c.invite_link_id)
    )}


def invite_link_uses(conn: Connection, invite_link_id: uuid.UUID) -> int:
    """Count the requests a link has redeemed."""
    return invite_link_uses_by_id(conn, [invite_link_id]).get(invite_link_id, 0)


def _require_invite_limits(*, max_uses: int, expires_at: datetime, now: datetime) -> None:
    """Refuse a use limit or an end outside the link rules."""
    if not 1 <= max_uses <= INVITE_USES_MAX:
        raise OpsError(f"Maximum uses must be from 1 to {INVITE_USES_MAX:,}.")
    if not now < expires_at <= now + INVITE_AHEAD_MAX:
        raise OpsError("Choose a date in the next 90 days.")


def _invite_domains(domains: Sequence[str]) -> list[str]:
    """Lower-case each domain by the listed-domain rule; refuse none, too many or a repeat."""
    if not domains:
        raise OpsError("Enter at least one domain.")
    if len(domains) > INVITE_DOMAINS_MAX:
        raise OpsError(f"A link can have at most {INVITE_DOMAINS_MAX} domains.")
    kept: list[str] = []
    for line, domain in enumerate(domains, start=1):
        try:
            value = _normalise_domain(domain.strip())
        except OpsError:
            raise OpsError(
                f"Line {line}: enter a domain such as dhsc.gov.uk, with no @."
            ) from None
        if value in kept:
            raise OpsError("This domain is on the list twice.")
        kept.append(value)
    return kept


def create_invite_link(
    conn: Connection,
    *,
    label: str,
    org: Organisation,
    cohorts: Sequence[Cohort],
    allowed_domains: Sequence[str],
    max_uses: int,
    expires_at: datetime,
    created_by: str,
    now: datetime,
) -> InviteLink:
    """Make an invite link with a new server-made code.

    Args:
        conn: Open connection inside the command's transaction.
        label: The operator's name for the link.
        org: The organisation a redeemed request joins.
        cohorts: The cohorts a redeemed person joins, already resolved.
        allowed_domains: The email domains the link accepts.
        max_uses: How many requests the link may redeem.
        expires_at: When the link stops working.
        created_by: The operator's user id.
        now: The time to judge the end against and to stamp.

    Returns:
        The new link.

    Raises:
        OpsError: On a domain list, use limit or end outside the link rules.
    """
    domains = _invite_domains(allowed_domains)
    _require_invite_limits(max_uses=max_uses, expires_at=expires_at, now=now)
    invite_link_id = uuid.uuid4()
    conn.execute(insert(invite_link).values(
        invite_link_id=invite_link_id, code=invite_code.new_code(), label=label.strip(),
        org_id=org.org_id, allowed_domains=domains, max_uses=max_uses, expires_at=expires_at,
        created_at=now, created_by=created_by,
    ))
    for target in cohorts:
        conn.execute(insert(invite_link_cohort).values(
            invite_link_id=invite_link_id, cohort_id=target.cohort_id
        ))
    return _lock_invite_link(conn, invite_link_id)


def _lock_invite_link(conn: Connection, invite_link_id: uuid.UUID) -> InviteLink:
    """Read one link under its row lock.

    Raises:
        NotFound: If no link has that id.
    """
    row = conn.execute(
        select(invite_link).where(invite_link.c.invite_link_id == invite_link_id)
        .with_for_update()
    ).mappings().one_or_none()
    if row is None:
        raise NotFound(f"no invite link {invite_link_id}")
    return invite_link_record(row)


def update_invite_link(
    conn: Connection,
    *,
    invite_link_id: uuid.UUID,
    label: str,
    max_uses: int,
    expires_at: datetime,
    now: datetime,
) -> InviteLink:
    """Change a link's label, use limit and end; its organisation, cohorts and domains stay.

    The uses are counted under the link's row lock, so a redemption cannot slip
    between the count and the write.

    Raises:
        NotFound: If no link has that id.
        OpsError: If the link is revoked, the limit is below its uses, or a
            value is outside the link rules.
    """
    link = _lock_invite_link(conn, invite_link_id)
    if link.revoked_at is not None:
        raise OpsError("A revoked link cannot be changed.")
    _require_invite_limits(max_uses=max_uses, expires_at=expires_at, now=now)
    uses = invite_link_uses(conn, invite_link_id)
    if max_uses < uses:
        raise OpsError(f"This link already has {uses} uses. The maximum cannot be lower.")
    conn.execute(
        update(invite_link).where(invite_link.c.invite_link_id == invite_link_id)
        .values(label=label.strip(), max_uses=max_uses, expires_at=expires_at)
    )
    return replace(link, label=label.strip(), max_uses=max_uses, expires_at=expires_at)


def revoke_invite_link(conn: Connection, *, invite_link_id: uuid.UUID, now: datetime) -> InviteLink:
    """Stop a link for good; the accounts it already made stay.

    Raises:
        NotFound: If no link has that id.
        OpsError: If it is already revoked.
    """
    link = _lock_invite_link(conn, invite_link_id)
    if link.revoked_at is not None:
        raise OpsError("A revoked link cannot be changed.")
    conn.execute(
        update(invite_link).where(invite_link.c.invite_link_id == invite_link_id)
        .values(revoked_at=now)
    )
    return replace(link, revoked_at=now)


def record_action(
    conn: Connection, *, actor: str, action: str, target: str | None, outcome: str
) -> uuid.UUID:
    """Insert one durable operations action record and return its identifier."""
    action_id = uuid.uuid4()
    conn.execute(
        insert(ops_action).values(
            action_id=action_id,
            at=_now(),
            actor_user_id=actor,
            action=action,
            target=target,
            outcome=outcome,
        )
    )
    return action_id


def approve_request(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    entry_id: uuid.UUID,
    org: Organisation,
    now: datetime,
) -> Approval:
    """Enrol one waitlist row and stamp it as approved.

    Args:
        conn: Open connection inside the command transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified Cognito user pool.
        entry_id: Waitlist row to approve.
        org: Organisation receiving the account.
        now: Timestamp used for the durable request stamp.

    Returns:
        The stamped request and its enrolment.

    Raises:
        NotFound: If no request has that id.
        OpsError: If the request was already approved.
        EnrolledElsewhere: If the address belongs to another organisation.
    """
    row = (
        conn.execute(
            select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id).with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound(f"no waitlist request {entry_id}")
    if row["account_created_at"] is not None:
        raise OpsError("already invited")
    enrolment = ensure_account_enrolled(
        conn,
        cognito,
        pool_id=pool_id,
        email=str(row["email"]),
        display_name=str(row["name"]),
        org=org,
    )
    conn.execute(
        update(waitlist_entry)
        .where(waitlist_entry.c.entry_id == entry_id)
        # Approving a rejected request reverses the decision.
        .values(account_user_id=enrolment.user_id, account_created_at=now, rejected_at=None)
    )
    return Approval(entry_id=entry_id, enrolment=enrolment, created_at=now)


def redeem_request(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    entry_id: uuid.UUID,
    now: datetime,
) -> Approval | None:
    """Turn a waiting request into an account through the invite link its code names.

    Locks the link row first and the request row second, and checks again under
    both locks that the link still accepts the request, so two redemptions at
    once cannot pass the link's use limit. The person joins the link's cohorts
    (a ``cohort.add`` audit row for each new membership) and the request records
    the link, which counts the use.

    Args:
        conn: Open connection inside the sweep's per-request transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified Cognito user pool.
        entry_id: The waiting request.
        now: The time to judge the link at and to stamp the request with.

    Returns:
        The approval, or ``None`` when the request is not (or no longer)
        redeemable; then nothing was written and Cognito was not called.

    Raises:
        EnrolledElsewhere: If the address belongs to another organisation.
        Deactivated: If the account is deactivated.
    """
    code = conn.execute(
        select(waitlist_entry.c.invite_code).where(waitlist_entry.c.entry_id == entry_id)
    ).scalar_one_or_none()
    link_id = None if code is None else conn.execute(
        select(invite_link.c.invite_link_id).where(invite_link.c.code == code)
    ).scalar_one_or_none()
    if link_id is None:
        return None
    link = _lock_invite_link(conn, link_id)
    row = conn.execute(
        select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id).with_for_update()
    ).mappings().one()
    if (
        row["invite_code"] != link.code
        or row["account_created_at"] is not None
        or row["rejected_at"] is not None
        or invite_request_reason(
            request_domain=email_domain(str(row["email"])), link=link,
            uses=invite_link_uses(conn, link_id), now=now,
        ) != "next_run"
    ):
        return None
    name = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == link.org_id)
    ).scalar_one()
    approved = approve_request(
        conn, cognito, pool_id=pool_id, entry_id=entry_id,
        org=Organisation(org_id=link.org_id, name=str(name)), now=now,
    )
    join_cohorts(conn, actor="sweep", user_id=approved.enrolment.user_id, cohorts=[
        Cohort(cohort_id=cohort_id, name=str(cohort_name))
        for cohort_id, cohort_name in conn.execute(
            select(cohort.c.cohort_id, cohort.c.name)
            .join(invite_link_cohort, invite_link_cohort.c.cohort_id == cohort.c.cohort_id)
            .where(invite_link_cohort.c.invite_link_id == link_id)
            .order_by(cohort.c.name)
        )
    ])
    conn.execute(
        update(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id)
        .values(invite_link_id=link_id)
    )
    return approved


def reject_request(conn: Connection, *, entry_id: uuid.UUID, now: datetime) -> None:
    """Mark one waiting request rejected: it leaves the waitlist and no email is sent.

    Raises:
        NotFound: If no request has that id.
        OpsError: If it was already invited or rejected.
    """
    row = (
        conn.execute(
            select(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id).with_for_update()
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound(f"no waitlist request {entry_id}")
    if row["account_created_at"] is not None:
        raise OpsError("already invited")
    if row["rejected_at"] is not None:
        raise OpsError("already rejected")
    conn.execute(
        update(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id).values(rejected_at=now)
    )


def delete_request(conn: Connection, *, entry_id: uuid.UUID) -> None:
    """Delete a rejected request for good; the address may ask again later.

    Raises:
        NotFound: If no request has that id.
        OpsError: If it is not rejected (only a rejected request is deleted).
    """
    rejected_at = conn.execute(
        select(waitlist_entry.c.rejected_at)
        .where(waitlist_entry.c.entry_id == entry_id)
        .with_for_update()
    ).one_or_none()
    if rejected_at is None:
        raise NotFound(f"no waitlist request {entry_id}")
    if rejected_at[0] is None:
        raise OpsError("only a rejected request can be deleted")
    conn.execute(delete(waitlist_entry).where(waitlist_entry.c.entry_id == entry_id))


# --------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------


def assign_rows(
    conn: Connection,
    *,
    org: Organisation,
    task_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
) -> Assignment:
    """Assign one row to an organisation, privately, moving a membership whole.

    The membership invariant applies: a task carries its
    project's ``org_id`` *and* ``visibility``. So there is no such thing as
    assigning half of a membership, and the command never offers to:

    - a **project** moves with every member task — and, membership being
      many-to-many (ADR 0032), with every project reachable through shared
      members (the connected component), or a shared member would be left
      breaching its other project;
    - a **task that is a member** of projects moves those projects'
      component and therefore every sibling, and says so in the summary;
    - a **task with no project** is unconstrained and moves alone.

    **A move privatises, on exactly the enrolment rule** (:data:`_PRIVATE`,
    ADR 0033 decision 7). Stamping ``org_id`` while preserving
    ``visibility`` is the one way an operator command can expose a row: the
    default visibility is ``org``, and a row whose ``org_id`` is NULL is
    reachable by its owner alone however it is marked — the org leg reads
    ``org_id IS NOT NULL AND visibility = 'org'`` (``routers/access.py``). So
    an unenrolled owner's estate is full of rows carrying ``visibility = 'org'``
    that nobody can see, and an assignment that kept the column would hand every
    one of them to every member of the destination organisation, instantly and
    without the owner acting. The rows arrive private and the owner re-shares
    from inside the new organisation, which is the same bargain enrolment
    strikes.

    Privatising is skipped only when the rows are **already** in the destination
    organisation, because then the assignment moves nobody's audience and
    flipping their visibility would be a gratuitous edit to the owner's choices.
    In that case project visibility is left alone — a component may
    legitimately mix visibilities — and each member is recomputed to the
    derived value: org-visible iff *any* project it is in is org-visible.
    That recompute is the ``i.4`` self-heal for a
    member that ever slipped out of step.

    ``updated_at`` is bumped on moved members, exactly as the API cascade bumps
    it: unlike enrolment — where the person must see no
    change — an assignment genuinely reshapes which organisation owns the row.

    Args:
        conn: Open connection inside the command's transaction.
        org: The destination.
        task_id: The task to assign; mutually exclusive with
            ``project_id``.
        project_id: The project to assign.

    Returns:
        What moved, and whether it was privatised.

    Raises:
        OpsError: If neither or both ids are given, or the row does not exist.
    """
    if (task_id is None) == (project_id is None):
        raise OpsError("give exactly one of --task or --project")

    followed = False
    if task_id is not None:
        row = conn.execute(
            select(task.c.task_id, task.c.org_id).where(task.c.task_id == task_id).with_for_update()
        ).one_or_none()
        if row is None:
            raise OpsError(f"no task {task_id}")
        member_of = [
            membership_row[0]
            for membership_row in conn.execute(
                select(project_membership.c.project_id)
                .where(project_membership.c.task_id == task_id)
                .order_by(project_membership.c.created_at, project_membership.c.project_id)
            ).all()
        ]
        if not member_of:
            privatised = row.org_id != org.org_id
            moving = update(task).where(task.c.task_id == task_id)
            # Two literal `.values()` calls rather than a built dict: the API
            # bars the blind splat on its patch, and the same discipline
            # belongs on the operator writer of the same two columns.
            if privatised:
                conn.execute(
                    moving.values(org_id=org.org_id, visibility=_PRIVATE, updated_at=_now())
                )
            else:
                conn.execute(moving.values(org_id=org.org_id, updated_at=_now()))
            return Assignment(
                org=org,
                project_id=None,
                tasks_moved=1,
                projects_moved=0,
                followed_membership=False,
                privatised=privatised,
            )
        seeds = list(member_of)
        target = member_of[0]
        followed = True
    else:
        seeds = [project_id]
        target = project_id

    current = conn.execute(
        select(project.c.org_id, project.c.visibility)
        .where(project.c.project_id == target)
        .with_for_update()
    ).one_or_none()
    if current is None:
        raise OpsError(f"no project {target}")
    # Membership is many-to-many (ADR 0032), so "a membership moves whole"
    # means the **connected component**: every project reachable through
    # shared members moves too, or the shared member would be left matching
    # one project and breaching the other. Within a component every row
    # already agrees on both fields (each shared member matches all of its
    # projects), so the set moves coherently.
    component: set[uuid.UUID] = set(seeds)
    frontier: set[uuid.UUID] = set(seeds)
    while frontier:
        member_ids = select(project_membership.c.task_id).where(
            project_membership.c.project_id.in_(frontier)
        )
        linked = {
            linked_row[0]
            for linked_row in conn.execute(
                select(project_membership.c.project_id)
                .where(project_membership.c.task_id.in_(member_ids))
                .distinct()
            ).all()
        }
        frontier = linked - component
        component |= frontier
    privatised = current.org_id != org.org_id
    member_rows = task.c.task_id.in_(
        select(project_membership.c.task_id).where(project_membership.c.project_id.in_(component))
    )
    # A cross-organisation move privatises everything it carries.
    # A same-organisation assignment moves nobody's audience, so the
    # projects keep their visibility and each member is **recomputed** to
    # the derived value — org-visible iff any project it is in is
    # org-visible — which is the self-heal for
    # a member that ever slipped out of step.
    # No status filter on members: archived tasks follow too, for the
    # reason the API cascade documents — an archived task is still
    # readable by whoever may read it, so leaving it behind strands exactly
    # the rows nobody watches.
    if privatised:
        projects_moved = conn.execute(
            update(project)
            .where(project.c.project_id.in_(component))
            .values(org_id=org.org_id, visibility=_PRIVATE)
        ).rowcount
        moved = conn.execute(
            update(task)
            .where(member_rows)
            .values(org_id=org.org_id, visibility=_PRIVATE, updated_at=_now())
        ).rowcount
    else:
        projects_moved = conn.execute(
            update(project).where(project.c.project_id.in_(component)).values(org_id=org.org_id)
        ).rowcount
        in_any_org_project = (
            select(project_membership.c.task_id)
            .select_from(
                project_membership.join(
                    project,
                    project.c.project_id == project_membership.c.project_id,
                )
            )
            .where(project_membership.c.task_id == task.c.task_id)
            .where(project.c.visibility == "org")
            .exists()
        )
        moved = conn.execute(
            update(task)
            .where(member_rows)
            .values(
                org_id=org.org_id,
                visibility=case((in_any_org_project, "org"), else_=_PRIVATE),
                updated_at=_now(),
            )
        ).rowcount
    return Assignment(
        org=org,
        project_id=target,
        tasks_moved=moved,
        projects_moved=projects_moved,
        followed_membership=followed,
        privatised=privatised,
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
    The blind ``.values(**changes)`` splat is barred on the API's project
    patch; the same discipline belongs on the one other writer of these two
    columns, even though the values here are internal.

    ``updated_at`` is left alone. An enrolled person must
    see no change, and bumping it would reorder their entire task list the
    moment an operator enrolled them.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The owner.
        org_id: The organisation to stamp.
        visibility: The visibility to force — always ``private`` today.

    Returns:
        ``(tasks, projects)`` row counts.
    """
    tasks = conn.execute(
        update(task).where(task.c.owner_user_id == sub).values(org_id=org_id, visibility=visibility)
    ).rowcount
    projects = conn.execute(
        update(project)
        .where(project.c.owner_user_id == sub)
        .values(org_id=org_id, visibility=visibility)
    ).rowcount
    return tasks, projects


def _sever_cross_owner_memberships(conn: Connection, *, sub: str) -> int:
    """Delete every membership pairing one of `sub`'s rows with someone else's.

    Colleague assignment means a project's members
    are no longer always owned by the project's owner — so "one person's
    rows are a closed set" (the module docstring's invariant argument) is only
    true after the cross-owner links are cut. Called by every membership move
    (enrol, re-enrol, de-enrol): the moved rows change organisation and the
    other owner's rows do not, so any membership between them would leave a
    member and a project disagreeing on `org_id`. Severing keeps i.6's
    reading — the rows on both sides keep the visibility and organisation
    they had; only the link is removed.

    An ownerless row (NULL `owner_user_id`, the CLI-created ones) is "someone
    else's" for this question: it does not move with `sub`, so a link to it
    is cut on the same grounds.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The owner whose rows are moving.

    Returns:
        The number of membership rows deleted.
    """
    own_tasks = select(task.c.task_id).where(task.c.owner_user_id == sub)
    own_projects = select(project.c.project_id).where(project.c.owner_user_id == sub)
    return int(
        conn.execute(
            delete(project_membership).where(
                or_(
                    and_(
                        project_membership.c.task_id.in_(own_tasks),
                        project_membership.c.project_id.notin_(own_projects),
                    ),
                    and_(
                        project_membership.c.project_id.in_(own_projects),
                        project_membership.c.task_id.notin_(own_tasks),
                    ),
                )
            )
        ).rowcount
    )


def _clear_owned_rows(conn: Connection, *, sub: str) -> tuple[int, int]:
    """Clear the organisation on every row one person owns, leaving visibility.

    The counterpart to :func:`_stamp_owned_rows`, and deliberately *not* the
    same function with a nullable argument: the two differ in which columns they
    write, which is exactly the thing that must stay legible.

    Args:
        conn: Open connection inside the command's transaction.
        sub: The owner.

    Returns:
        ``(tasks, projects)`` row counts.
    """
    tasks = conn.execute(
        update(task).where(task.c.owner_user_id == sub).values(org_id=None)
    ).rowcount
    projects = conn.execute(
        update(project).where(project.c.owner_user_id == sub).values(org_id=None)
    ).rowcount
    return tasks, projects


def _lock_user(conn: Connection, sub: str) -> RowMapping | None:
    """Read one ``app_user`` row ``FOR UPDATE``, or ``None`` if it does not exist."""
    return (
        conn.execute(select(app_user).where(app_user.c.user_id == sub).with_for_update())
        .mappings()
        .one_or_none()
    )


def _resolve_and_lock(conn: Connection, *, email: str | None, sub: str | None) -> RowMapping:
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
        conn.execute(select(app_user).where(app_user.c.email == email).with_for_update())
        .mappings()
        .all()
    )
    if not rows:
        raise OpsError(
            f"no user with the address {email}. `user create` and `user enrol` store "
            "the address this resolves by; a person who has only signed in has none yet."
        )
    if len(rows) > 1:
        subjects = ", ".join(str(row["user_id"]) for row in rows)
        raise OpsError(
            f"{len(rows)} users share the address {email} ({subjects}); resolve with --sub instead"
        )
    return rows[0]


def _resolve_account(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str | None,
    sub: str | None,
) -> tuple[RowMapping | None, UserTypeTypeDef | None, str]:
    """Find a person by address or subject, in the database and in Cognito.

    The rule :func:`deactivate_user` documents under "Finding the person". The
    ``app_user`` row, when there is one, is read ``FOR UPDATE``.

    Returns:
        The locked row or ``None``, the Cognito user or ``None``, and the subject.

    Raises:
        OpsError: If neither or both selectors are given, the address is
            stored on more than one row, or neither the pool nor the database
            knows the person.
    """
    if (email is None) == (sub is None):
        raise OpsError("give exactly one of --email or --sub")
    row: RowMapping | None
    if sub is not None:
        _require_filter_safe(sub)
        row = _lock_user(conn, sub)
        user = _find_user_by_sub(cognito, pool_id=pool_id, sub=sub)
    else:
        assert email is not None  # narrowed by the check above
        _require_filter_safe(email)
        stored = (
            conn.execute(select(app_user).where(app_user.c.email == email).with_for_update())
            .mappings()
            .all()
        )
        if len(stored) > 1:
            subjects = ", ".join(str(r["user_id"]) for r in stored)
            raise OpsError(
                f"{len(stored)} users share the address {email} ({subjects}); "
                "resolve with --sub instead. Nothing was changed."
            )
        if stored:
            row = stored[0]
            user = _find_user_by_sub(cognito, pool_id=pool_id, sub=str(row["user_id"]))
        else:
            user = _find_user_by_email(cognito, pool_id=pool_id, email=email)
            found_sub = _sub_of(user.get("Attributes", [])) if user is not None else ""
            row = _lock_user(conn, found_sub) if found_sub else None
    if row is not None:
        user_id = str(row["user_id"])
    elif user is not None:
        user_id = _sub_of(user.get("Attributes", []))
    else:
        raise OpsError(f"no account in the pool for {email or sub}. Nothing was changed.")
    return row, user, user_id


def _find_sub_by_email(
    cognito: CognitoIdentityProviderClient, *, pool_id: str, email: str
) -> str | None:
    """Return the Cognito subject behind an address, or ``None``.

    ``ListUsers``'s ``=`` is an **exact, case-sensitive** match, so this asks
    about one spelling of the address and no other. That is why every address
    is lower-cased once at the CLI boundary
    (:func:`policy_atlas.ops.cli._email`): without it, ``--email Alice@x``
    against an account created as ``alice@x`` finds nothing, and ``user create``
    goes on to try to mint a second identity for the same person.
    """
    user = _find_user_by_email(cognito, pool_id=pool_id, email=email)
    if user is None:
        return None
    return _sub_of(user.get("Attributes", [])) or None


def _find_user_by_email(
    cognito: CognitoIdentityProviderClient, *, pool_id: str, email: str
) -> UserTypeTypeDef | None:
    """Return the Cognito user behind an address, or ``None``.

    The same exact-match lookup :func:`_find_sub_by_email` relies on; see there.
    """
    response = cognito.list_users(UserPoolId=pool_id, Filter=f'email = "{email}"', Limit=1)
    users = response.get("Users") or []
    return users[0] if users else None


def _find_user_by_sub(
    cognito: CognitoIdentityProviderClient, *, pool_id: str, sub: str
) -> UserTypeTypeDef | None:
    """Return the Cognito user with this subject, or ``None``.

    ``sub`` is unique in a pool, so the match is exact. The returned
    ``Username`` is what the admin calls address the account by.
    """
    response = cognito.list_users(UserPoolId=pool_id, Filter=f'sub = "{sub}"', Limit=1)
    users = response.get("Users") or []
    return users[0] if users else None


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
        raise OpsError(f"refusing a value containing a quote or backslash: {email!r}")


def _require_mailable(email: str) -> None:
    """Refuse an address that could carry markup into the invitation email.

    Cognito substitutes ``{username}`` (the address) into the HTML invitation
    without escaping, and the public form's pattern admits ``<``, ``>`` and
    ``&``. Such an address is not deliverable anyway, so refusing costs nothing.
    """
    if any(character in email for character in "<>&") or any(c.isspace() for c in email):
        raise OpsError(f"refusing an address containing markup or whitespace: {email!r}")


def _now() -> datetime:
    return datetime.now(UTC)
