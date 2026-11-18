"""What each operator command actually does, as functions over one connection.

Every function here takes an open :class:`~sqlalchemy.engine.Connection` and,
where it needs one, a Cognito client (``user reissue`` touches Cognito only, so
takes no connection). It writes rows and returns a small record
describing what it did; it never opens a transaction, never prints, and never
exits. :mod:`policy_atlas.ops.cli` supplies the transaction and renders the
record. That shape is what lets the phase-6 SSE suite drive a *real*
de-enrolment against the test database with a stubbed identity provider, rather
than re-implementing the write it believes the CLI performs.

**Three rules run through the whole module.**

*The identity provider is asked first, and only about identity.* ``sub`` is the
key (contract § 3b) and only Cognito can turn an address into one, so
``user create``, ``user enrol`` and ``user resync`` call ``ListUsers`` /
``AdminCreateUser``, and ``user reissue`` calls ``ListUsers`` /
``AdminSetUserPassword``. ``user offboard`` is the one command that changes an
account's state in Cognito: ``ListUsers``, then ``AdminDisableUser`` and
``AdminUserGlobalSignOut`` (task 064a, ADR 0045 decision 5). ``admin grant``,
``admin revoke``, ``user de-enrol`` and ``rows assign`` resolve entirely in the
database and make no AWS call at all — which is also why operator IAM needs
nothing beyond ``ListUsers``, ``AdminCreateUser``, ``AdminSetUserPassword``,
``AdminDisableUser`` and ``AdminUserGlobalSignOut`` (contract § 9).

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
:sub`` in one statement per table. Colleague assignment (owner ruling
2026-08-27) means a project's members are no longer always owned by its
owner, so a move first **severs** every membership pairing the mover's rows
with someone else's (:func:`_sever_cross_owner_memberships`) — after which one
person's rows are again a closed set, and stamping the set leaves every
task matching its projects on both ``org_id`` and ``visibility``. Walking
row by row through the cascade path would transiently violate it.

**Nothing here logs.** A privilege change is recorded by
:mod:`policy_atlas.ops.cli` *after* the transaction commits, from the
:class:`AdminTrace` values a record carries. A ``log.info`` emitted inside the
transaction is a durable claim about a write a failed commit then discarded,
which is worse than no trace at all: contract § 3a wants the line to be
evidence.
"""

from __future__ import annotations

import secrets
import string
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError
from sqlalchemy import and_, case, delete, insert, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection, RowMapping
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    app_user,
    ops_action,
    organisation,
    organisation_domain,
    project,
    project_membership,
    task,
    waitlist_entry,
)
from policy_atlas.ops.errors import EnrolledElsewhere, NotFound, OpsError, ResendTooSoon

if TYPE_CHECKING:
    from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient
    from mypy_boto3_cognito_idp.type_defs import AttributeTypeTypeDef, UserTypeTypeDef

#: The visibility every moved row arrives at. Owner call (j): **no operator
#: action can expose a row.** Enrolment and ``rows assign`` stamp the
#: organisation *and* privatise, so the person opts each row into their
#: organisation deliberately, and neither a re-enrolment nor an operator
#: assignment can carry work shared with the previous organisation into the
#: next one.
_PRIVATE = "private"


# --------------------------------------------------------------------------
# Records. Each carries its own operator-facing sentence: the CLI's safety UX
# is these strings (plan phase 9b), and keeping them beside the counts they
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
    #: Set only by `user create --invite manual` (owner amendment 2026-08-26).
    #: Rendered ONCE in the summary for out-of-band handover; never logged —
    #: `summary()` output goes to the operator's stdout, not through structlog.
    temporary_password: str | None = None
    #: Cross-owner membership links cut because the rows moved organisation
    #: (colleague assignment, owner ruling 2026-08-27).
    memberships_severed: int = 0
    invitation_sent: bool = False

    def summary(self) -> str:
        """Render the enrolment line, including what moved."""
        verb = "enrolled" if self.created else "re-enrolled"
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
    #: (colleague assignment, owner ruling 2026-08-27).
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

        Contract § 3a asks for a record of every privilege change, not of every
        ``admin revoke`` invocation. De-enrolment is the *other* way the support
        role is taken away — and the one an investigation is most likely to be
        asking about, because it is what offboarding runs.
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
    """A fresh temporary password for an account that never completed first sign-in.

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
            f"(single-use, 30-day expiry, they set their own at first sign-in): "
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
        def show(value: int | None) -> str:
            return "inherit" if value is None else str(value)

        return (
            f"quota for {self.who}: tasks per year {show(self.task_quota_before)} → "
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
class Offboarding(Record):
    """One person locked out: Cognito account disabled, then the database cleaned.

    Attributes:
        user_id: The Cognito subject.
        email: The address they were found by or stored under, if any.
        steps: One plain sentence per step taken or skipped, in order.
        links_made_private: Tasks whose public link was switched off.
        de_enrolment: The de-enrolment, when the person was still enrolled or
            held the support role; ``None`` when it was skipped.
    """

    user_id: str
    email: str | None
    steps: tuple[str, ...]
    links_made_private: int
    de_enrolment: DeEnrolment | None

    def summary(self) -> str:
        """Render the offboarding as one header line and one line per step."""
        who = f"{self.email} ({self.user_id})" if self.email else self.user_id
        return f"offboarded {who}:\n" + "\n".join(f"  - {step}" for step in self.steps)

    def admin_changes(self) -> Sequence[AdminTrace]:
        """The support-role revoke the de-enrolment made, traced like ``admin revoke``."""
        return self.de_enrolment.admin_changes() if self.de_enrolment else ()


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

    Generated, never accepted: rubric 30's "no command accepts a password"
    holds because this value originates here, not from an operator. 20
    characters with every Cognito-default class guaranteed (upper, lower,
    digit, symbol); the symbol set avoids quotes, backslashes and ``$`` so the
    printed value copies cleanly through a shell.
    """
    symbols = "!@#%^*-_+="
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

    **Cognito first, because its ``sub`` is the key** (contract § 9) — there is
    nothing to write in the database until the account exists. That ordering
    creates the one failure this command has to handle explicitly: an account
    created and a database write that then fails. The account is **kept** and
    the ``user enrol`` remediation printed. Deleting it is Out (owner call (h),
    coupled to ownership transfer), and no path in this package calls
    ``AdminDeleteUser``.

    Two invitation modes (owner amendment 2026-08-26 — the ``COGNITO_DEFAULT``
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
        display_name: Required, and never the email (contract § 3b).
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
) -> Enrolment:
    """Ensure an account exists and belongs to ``org``, sending only a new invitation.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified Cognito user pool.
        email: The account address.
        display_name: The name stored on enrolment.
        org: The destination organisation.

    Returns:
        The idempotent enrolment result.

    Raises:
        EnrolledElsewhere: If the account already belongs to another organisation.
        OpsError: If Cognito cannot create the account or does not return a subject.
    """
    _require_filter_safe(email)
    _require_mailable(email)
    sub = _find_sub_by_email(cognito, pool_id=pool_id, email=email)
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
    if existing is None:
        return _enrol(conn, sub=sub, email=email, display_name=display_name, org=org)
    if existing["org_id"] is None:
        # An account that exists keeps its stored name: the name offered here
        # may come from the public form (the sweep), and a stranger must not be
        # able to rename a colleague (review stack, 2026-11-17).
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
    other = conn.execute(
        select(organisation.c.name).where(organisation.c.org_id == existing["org_id"])
    ).scalar_one()
    raise EnrolledElsewhere(sub=sub, org_name=other, org_id=existing["org_id"], email=email)


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
    cognito: CognitoIdentityProviderClient, *, pool_id: str, email: str
) -> Reissue:
    """Replace the expired or lost temporary password of a never-signed-in account.

    **Only ``FORCE_CHANGE_PASSWORD`` accounts.** Anyone who has set their own
    password recovers it themselves with "Forgot password"; an operator setting
    one for them would lock them out of a password they know and hand the
    operator a working credential for their account. The new password is set
    non-permanent, so the person still chooses their own at first sign-in.

    Touches Cognito only: the account's enrolment, if any, is unchanged, and an
    account kept after a failed ``user create`` database write is reissuable.

    Args:
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The account's address.

    Returns:
        The reissue, carrying the minted temporary password.

    Raises:
        OpsError: If the pool holds no such address, the account is not
            awaiting first sign-in, or Cognito refuses the change.
    """
    _require_filter_safe(email)
    user = _find_user_by_email(cognito, pool_id=pool_id, email=email)
    if user is None:
        raise OpsError(f"no account in the pool for {email}")
    status = user.get("UserStatus")
    if status != "FORCE_CHANGE_PASSWORD":
        raise OpsError(
            f"{email} is {status}, not FORCE_CHANGE_PASSWORD: only an account that has "
            "never signed in can be reissued. Nothing was changed. If they have "
            "forgotten their own password, they reset it from the sign-in page."
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
    sight of their work (contract § 7; flagged there as an owner decision,
    because the alternative needs ownership transfer, which is Out). The stored
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


def offboard_user(
    conn: Connection,
    cognito: CognitoIdentityProviderClient,
    *,
    pool_id: str,
    email: str | None = None,
    sub: str | None = None,
) -> Offboarding:
    """Lock a person out: disable their login, then clean up the database.

    This is what to run when someone leaves. ``user de-enrol`` alone only
    changes the database: the person can still sign in and their public task
    links still work (finding M-02).

    **The order, and why.**

    1. Find the person (see below).
    2. Cognito: ``AdminDisableUser`` (no new sign-in), then
       ``AdminUserGlobalSignOut`` (their refresh tokens stop working, so no
       session can be renewed). If either call fails, this stops and raises
       before any database write, so the database is untouched.
    3. Database, inside the caller's one transaction: de-enrol them if they
       are still in an organisation or hold the support role (the plain
       :func:`de_enrol_user`, unchanged), then switch off every public link on
       the tasks they own (``task.is_public = false``). Project ``visibility``
       is about who in the organisation can see a project, not a public link,
       so it is left alone (ADR 0045 decision 5).

    Cognito goes first so the dangerous half — a working login — is closed
    before anything else. If the database step then fails, the account stays
    disabled and the transaction rolls back; running the same command again
    completes it (disabling an already-disabled account succeeds).

    An access token issued before this runs stays valid until it expires (up to
    60 minutes), and an open progress stream can outlive it. That window is
    accepted and documented in the deployment guide.

    **Finding the person.** Exactly one of ``email`` or ``sub``:

    - ``sub``: the ``app_user`` row with that id, if any.
    - ``email``: the ``app_user`` row storing that address; if none does (they
      only ever signed in, so no address was stored), Cognito is asked which
      account has that address, and that account's row is used if one exists.

    Three cases follow, each reported in :attr:`Offboarding.steps`:

    - **Enrolled** (in an organisation, or holding the support role):
      Cognito, de-enrol, public links off.
    - **Already de-enrolled** (row exists, no organisation, no support role —
      M-02's main case: removed earlier, login still working): Cognito, public
      links off; de-enrol is skipped because it would refuse.
    - **No** ``app_user`` **row** (a Cognito account that never reached the
      app): Cognito only.
    - **No Cognito account** but a row (the account was deleted from the pool
      earlier): the database half only, reported as such. Neither a row nor
      an account is a refusal.

    Args:
        conn: Open connection inside the command's transaction.
        cognito: Client bound to the verified pool.
        pool_id: The verified user pool.
        email: The address to find them by; mutually exclusive with ``sub``.
        sub: The Cognito subject to find them by.

    Returns:
        The offboarding, listing the steps taken and the counts.

    Raises:
        OpsError: If neither or both selectors are given, the address is
            stored on more than one row, neither the pool nor the database
            knows the person, or Cognito refuses either call (the database
            is then untouched).
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
    who = email or (row["email"] if row is not None else None) or user_id

    if user is None:
        # The account was deleted from the pool earlier (by hand, or the pool
        # was replaced) but the row remains: nothing to disable, and the
        # database half must still run or their public links stay live
        # (review stack, 2026-11-16).
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
                f"`user offboard --sub {user_id}` to finish."
            ) from error
        steps = ["disabled the Cognito account", "signed out everywhere (refresh tokens revoked)"]

    if row is None:
        steps.append("no app_user row: Cognito only, the database was not touched")
        return Offboarding(
            user_id=user_id,
            email=email,
            steps=tuple(steps),
            links_made_private=0,
            de_enrolment=None,
        )

    de_enrolment: DeEnrolment | None = None
    if row["org_id"] is not None or row["is_admin"] or row["is_ops"]:
        de_enrolment = de_enrol_user(conn, sub=user_id)
        steps.append(de_enrolment.summary())
    else:
        steps.append("de-enrol skipped: not enrolled")
    links = int(
        conn.execute(
            update(task)
            .where(task.c.owner_user_id == user_id, task.c.is_public)
            .values(is_public=False)
        ).rowcount
    )
    steps.append(f"made {links} public task link(s) private")
    return Offboarding(
        user_id=user_id,
        email=row["email"] or email,
        steps=tuple(steps),
        links_made_private=links,
        de_enrolment=de_enrolment,
    )


def set_admin(
    conn: Connection, *, grant: bool, email: str | None = None, sub: str | None = None
) -> AdminChange:
    """Grant or revoke the support role.

    Contract § 3a: "a privileged grant with no record of who made it is not
    auditable". The record is :meth:`AdminChange.admin_changes`, emitted by the
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
    task_quota_per_year: int | None,
    runs_per_user: int | None,
) -> QuotaChange:
    """Set or clear both quota overrides on exactly one user or organisation.

    Args:
        conn: Open connection inside the command transaction.
        user_id: User subject, mutually exclusive with ``org_id``.
        org_id: Organisation identifier, mutually exclusive with ``user_id``.
        task_quota_per_year: Task quota override; ``None`` inherits.
        runs_per_user: Simultaneous run override; ``None`` inherits.

    Returns:
        The previous and requested quota values.

    Raises:
        OpsError: If selection is invalid, absent, or a quota is negative.
    """
    if (user_id is None) == (org_id is None):
        raise OpsError("give exactly one of user_id or org_id")
    if any(value is not None and value < 0 for value in (task_quota_per_year, runs_per_user)):
        raise OpsError("quota values cannot be negative")
    table = app_user if user_id is not None else organisation
    key = app_user.c.user_id if user_id is not None else organisation.c.org_id
    identifier = user_id if user_id is not None else org_id
    row = (
        conn.execute(select(table).where(key == identifier).with_for_update())
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise NotFound(f"no {'user' if user_id is not None else 'organisation'} {identifier}")
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
        OpsError: If the row is missing or was already approved.
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
        raise OpsError(f"no waitlist request {entry_id}")
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
        .values(account_user_id=enrolment.user_id, account_created_at=now)
    )
    return Approval(entry_id=entry_id, enrolment=enrolment, created_at=now)


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

    Contract § 9 sends this through § 6's invariant: a task carries its
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
    owner call (j), ADR 0033 decision 7). Stamping ``org_id`` while preserving
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
    derived value: org-visible iff *any* project it is in is org-visible
    (owner ruling 2026-08-27). That recompute is the ``i.4`` self-heal for a
    member that ever slipped out of step.

    ``updated_at`` is bumped on moved members, exactly as the API cascade bumps
    it: unlike enrolment — where contract § 7 requires the person to see no
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
            # Two literal `.values()` calls rather than a built dict: rubric 24
            # bars the blind splat on the API's patch, and the same discipline
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
    # A cross-organisation move privatises everything it carries (owner call
    # (j)). A same-organisation assignment moves nobody's audience, so the
    # projects keep their visibility and each member is **recomputed** to
    # the derived value — org-visible iff any project it is in is
    # org-visible (owner ruling 2026-08-27) — which is the i.4 self-heal for
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
    Rubric 24 bars the blind ``.values(**changes)`` splat on the API's project
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

    Colleague assignment (owner ruling 2026-08-27) means a project's members
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
    ``&``. Such an address is not deliverable anyway, so refusing costs nothing
    (review stack, 2026-11-17).
    """
    if any(character in email for character in "<>&") or any(c.isspace() for c in email):
        raise OpsError(f"refusing an address containing markup or whitespace: {email!r}")


def _now() -> datetime:
    return datetime.now(UTC)
