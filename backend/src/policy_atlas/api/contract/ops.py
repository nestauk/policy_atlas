"""The ops-host contract: what the ops pages send and receive (task 065, B4, B7).

Served only by the ops service (``POLICY_ATLAS_SERVICE_ROLE=ops``) under
``/api/v1/ops``, and exported to its own OpenAPI document
(``frontend/openapi-ops.json``). Nothing here is reachable on the public API,
so this is the one package module that may carry another person's email
address: the ops pages are the ops-facing use ``app_user.email`` was stored
for, and they are reachable only by ops-role holders on the address-gated
host (contract B4).

Shapes follow the command functions in :mod:`policy_atlas.ops.commands`,
which every write goes through. A bulk action is a list of subjects; the
route runs the command once per subject and answers with one
:class:`ActionResult` each, so one failure leaves the others recorded.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .tenancy import OrganisationRef
from .waitlist import WaitlistSignup

#: Upper bounds on free text the ops pages send; the command functions
#: validate meaning, these only bound size.
OPS_NAME_MAX = 200
OPS_EMAIL_MAX = 320
#: The most cohorts one Add person or Approve may name.
OPS_COHORTS_MAX = 10
#: The most subjects one bulk action takes. The people list is the whole
#: user base (under a hundred people), so this is a sanity bound, not paging.
OPS_BULK_MAX = 200


class LimitSourceOut(BaseModel):
    """Where one limit came from (contract B12).

    Args:
        kind: A fixed word the pages branch on; never an operator-typed name.
        name: The cohort's or organisation's name for those two kinds, else ``None``.
    """

    kind: Literal["person", "cohort", "organisation", "default", "administrator"]
    name: str | None = None


class LimitsOut(BaseModel):
    """The limits that apply to one person after resolution (contract B12).

    Args:
        task_quota_per_year: Tasks the person may create in 365 days, or
            ``None`` for no limit (an administrator, or an override of 0).
        runs_per_user: Walks the person's tasks may hold at once, or ``None``
            for no limit (an override of 0).
        task_quota_from: Where the task quota came from.
        runs_from: The same for the run cap.
    """

    task_quota_per_year: int | None
    runs_per_user: int | None
    task_quota_from: LimitSourceOut
    runs_from: LimitSourceOut


class QuotaSet(BaseModel):
    """The two override fields of a quota form (contract B12).

    ``None`` clears the override so the next level applies; ``0`` means no
    limit. Both fields are always sent: the form shows both.
    """

    model_config = ConfigDict(extra="forbid")

    # Required, nullable: a body that leaves one out must not clear it by
    # accident.
    task_quota_per_year: int | None = Field(ge=0)
    runs_per_user: int | None = Field(ge=0)


class OrganisationOut(BaseModel):
    """One organisation as the ops pages list it.

    Args:
        org_id: The organisation's identity.
        name: Its display name.
        created_at: When it was created.
        people: How many ``app_user`` rows belong to it.
        task_quota_per_year: Its task-quota override, or ``None`` (inherit).
        runs_per_user: Its run-cap override, or ``None`` (inherit).
        domains: Email domains that join it by self-signup (contract C1).
            Read-only on the ops pages; the CLI edits the table.
    """

    org_id: uuid.UUID
    name: str
    created_at: datetime
    people: int
    task_quota_per_year: int | None = None
    runs_per_user: int | None = None
    domains: list[str]


class CohortRef(BaseModel):
    """A cohort as a person's row names it."""

    cohort_id: uuid.UUID
    name: str


class CohortOut(BaseModel):
    """One cohort as the Cohorts page lists it (owner, 2026-11-18).

    Args:
        cohort_id: The cohort's identity.
        name: Its unique display name.
        description: What the group is for, or ``None``.
        starts_on: When it starts, or ``None``.
        ends_on: When it ends, or ``None``.
        links: Web addresses about it (a plan, a sheet, a channel), in order.
        created_at: When it was created.
        people: How many people are in it.
        task_quota_per_year: Its task-quota override, or ``None`` (inherit).
        runs_per_user: Its run-cap override, or ``None`` (inherit).
    """

    cohort_id: uuid.UUID
    name: str
    description: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    links: list[str]
    created_at: datetime
    people: int
    task_quota_per_year: int | None = None
    runs_per_user: int | None = None


class CohortSave(BaseModel):
    """Body of ``POST /api/v1/ops/cohorts`` (create) and ``/cohorts/{id}`` (replace).

    Every field is sent: the form shows them all, and an empty optional field
    clears it.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=OPS_NAME_MAX)
    description: str | None = Field(default=None, max_length=2000)
    starts_on: date | None = None
    ends_on: date | None = None
    links: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("links")
    @classmethod
    def bound_links(cls, links: list[str]) -> list[str]:
        """Bound each link's size; the command checks that it is a web address."""
        if any(len(link) > 2000 for link in links):
            raise ValueError("a link is at most 2000 characters")
        return links


class OrganisationCreate(BaseModel):
    """Body of ``POST /api/v1/ops/organisations``."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=OPS_NAME_MAX)


class PersonOut(BaseModel):
    """One person as the ops pages list them (contract B4 "list people").

    Args:
        user_id: The Cognito subject.
        display_name: The stored name (never derived from the email here).
        email: The stored address, or ``None`` for a person who only ever
            signed in. Ops-facing: this shape never leaves the ops host.
        organisation: Their organisation, or ``None`` when unenrolled.
        is_admin: Whether they hold the administrator flag.
        is_ops: Whether they hold the ops role.
        created_at: When the row was created.
        invited_at: When Cognito last sent them an invitation through this
            service, or ``None``. The resend cooldown reads it.
        first_signed_in_at: When they first opened the app, or ``None``.
        deactivated_at: When an operator deactivated them, or ``None`` (task 066).
        task_quota_per_year: Their own override, or ``None``.
        runs_per_user: Their own override, or ``None``.
        tasks_this_year: Tasks they created in the last 365 days.
        last_task_at: When they created their latest task, or ``None``.
        limits: The limits that apply after resolution.
        cohorts: The cohorts they are in, by name.
    """

    user_id: str
    display_name: str
    email: str | None = None
    organisation: OrganisationRef | None = None
    is_admin: bool
    is_ops: bool
    created_at: datetime
    invited_at: datetime | None = None
    first_signed_in_at: datetime | None = None
    deactivated_at: datetime | None = None
    task_quota_per_year: int | None = None
    runs_per_user: int | None = None
    tasks_this_year: int
    last_task_at: datetime | None = None
    limits: LimitsOut
    cohorts: list[CohortRef]


class CohortChoice(BaseModel):
    """The optional cohorts an Add person or an Approve puts the person in.

    Args:
        cohort_ids: Up to :data:`OPS_COHORTS_MAX` cohorts, each named once.
    """

    model_config = ConfigDict(extra="forbid")

    cohort_ids: list[uuid.UUID] = Field(default_factory=list, max_length=OPS_COHORTS_MAX)

    @field_validator("cohort_ids")
    @classmethod
    def refuse_repeats(cls, cohort_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        """Refuse a cohort named twice."""
        if len(set(cohort_ids)) != len(cohort_ids):
            raise ValueError("a cohort is named more than once")
        return cohort_ids


def validate_person_fields(email: str, display_name: str) -> tuple[str, str]:
    """Apply the Add person rules to one address and name.

    Add person and the file check both use this, so a file line passes exactly
    when the same person typed into Add person would. The address is
    lower-cased and shape-checked as the waitlist form and the CLI do:
    Cognito's lookup is an exact, case-sensitive match, so one spelling per
    mailbox is what keeps a second identity from being minted.

    Args:
        email: The address as given.
        display_name: The name as given.

    Returns:
        The lower-cased address and the name, both stripped.

    Raises:
        ValueError: With a sentence for the operator, when either fails.
    """
    email, display_name = email.strip(), display_name.strip()
    try:
        if len(email) > OPS_EMAIL_MAX:
            raise ValueError
        email = WaitlistSignup.validate_email(email)
    except ValueError:
        raise ValueError("this is not an email address.") from None
    if not display_name:
        raise ValueError("the name is empty.")
    if len(display_name) > OPS_NAME_MAX:
        raise ValueError(f"the name is longer than {OPS_NAME_MAX} characters.")
    return email, display_name


class PersonCreate(CohortChoice):
    """Body of ``POST /api/v1/ops/people``: create a person in an organisation.

    The organisation is required (contract B4): a browser-created account is
    never unenrolled. The route calls the ensure-account command, so an
    address that already has an unenrolled account is enrolled without a
    second invitation. The person joins each cohort in ``cohort_ids``. The
    address and name follow :func:`validate_person_fields`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str
    display_name: str
    org_id: uuid.UUID

    @model_validator(mode="after")
    def validate_person(self) -> PersonCreate:
        """Apply the shared address and name rules."""
        self.email, self.display_name = validate_person_fields(self.email, self.display_name)
        return self


#: Bounds on a people file (CSV text) for the file check.
IMPORT_PEOPLE_MAX = 500
IMPORT_CHARACTERS_MAX = 200_000


class ImportCheck(BaseModel):
    """Body of ``POST /api/v1/ops/people/import-check``: the text of a people file.

    The size rule (:data:`IMPORT_CHARACTERS_MAX`) answers as a file error; the
    field bound here only stops a body far beyond it.
    """

    model_config = ConfigDict(extra="forbid")

    csv: str = Field(max_length=4 * IMPORT_CHARACTERS_MAX)


class ImportRow(BaseModel):
    """One good line of a people file.

    Args:
        line: The file line where the record starts; the header is line 1.
        email: The address, lower-cased.
        display_name: The name.
    """

    line: int
    email: str
    display_name: str


class ImportProblem(BaseModel):
    """One fault in a people file.

    Args:
        line: The file line where the faulty record starts, or ``None`` for a
            fault of the whole file.
        message: A sentence for the operator.
    """

    line: int | None = None
    message: str


class ImportCheckOut(BaseModel):
    """Answer to the file check: the good lines and the faults, in file order."""

    rows: list[ImportRow]
    errors: list[ImportProblem]


class PersonCreatedOut(BaseModel):
    """Answer to ``POST /api/v1/ops/people``.

    Args:
        person: The person as the list now shows them.
        invitation_sent: Whether Cognito sent an invitation on this call.
            ``False`` when the address already had an account.
        reactivated: Whether the address belonged to a deactivated account
            that this call turned back on.
    """

    person: PersonOut
    invitation_sent: bool
    reactivated: bool = False


#: How one subject of a bulk action ended. ``ok`` means the command ran and
#: its audit row is written; ``failed`` means this subject's savepoint was
#: rolled back and a ``failed`` audit row written; ``too_soon`` is the resend
#: cooldown.
ActionOutcome = Literal["ok", "failed", "too_soon"]


class ActionResult(BaseModel):
    """One subject's result inside a bulk action.

    Args:
        user_id: The subject.
        outcome: How it ended.
        message: The command's one-line summary, or the refusal's reason.
        action_id: The ``ops_action`` row's id, or ``None`` for ``too_soon``
            (nothing happened, so nothing was recorded).
    """

    user_id: str
    outcome: ActionOutcome
    message: str
    action_id: uuid.UUID | None = None


class BulkOut(BaseModel):
    """Answer to every bulk action: one result per subject, in request order."""

    results: list[ActionResult]


class BulkSubjects(BaseModel):
    """Body of the bulk actions that need only the subjects (de-enrol, offboard, resend)."""

    model_config = ConfigDict(extra="forbid")

    user_ids: list[str] = Field(min_length=1, max_length=OPS_BULK_MAX)


class BulkCohort(BulkSubjects):
    """Body of ``POST /api/v1/ops/people/cohort-add`` and ``cohort-remove``."""

    cohort_id: uuid.UUID


class BulkEnrol(BulkSubjects):
    """Body of ``POST /api/v1/ops/people/enrol``: enrol or move into ``org_id``."""

    org_id: uuid.UUID


class BulkQuota(BulkSubjects, QuotaSet):
    """Body of ``POST /api/v1/ops/people/quota``: the same two fields for every subject."""


#: A waitlist row's state on the Requests page. ``waiting``: no
#: account yet and no listed domain, so an operator approves it; ``invited``:
#: stamped by the sweep or an approval; ``check``: the address already belongs
#: to another organisation, left for a person to decide.
RequestStatus = Literal["waiting", "invited", "check", "rejected"]


class RequestInvite(BaseModel):
    """Why a waiting request that arrived through an invite link has no account yet.

    Args:
        label: The link's label; ``None`` when no link has the request's code.
        reason: ``unknown_code``, ``wrong_domain``, ``expired``, ``full``,
            ``revoked``, ``next_run`` (the sweep takes it at its next run) or
            ``retry_wait`` (the last try failed; the sweep tries again in a few
            minutes).
    """

    label: str | None = None
    reason: Literal[
        "unknown_code", "wrong_domain", "expired", "full", "revoked", "next_run", "retry_wait"
    ]


class RequestOut(BaseModel):
    """One waitlist row as the Requests page shows it.

    Args:
        entry_id: The row.
        email: The requested address.
        name: The name they gave.
        organisation: The organisation they typed, if any.
        role_or_reason: Why they asked.
        created_at: When they asked.
        status: See :data:`RequestStatus`.
        account_user_id: The subject once an account exists.
        account_created_at: When the row was stamped.
        note: For ``check``, which organisation the address already belongs
            to; otherwise ``None``.
        invite: For a waiting request that carries an invite code, the link's
            label and why it has no account yet; otherwise ``None``. The code
            itself is never in the answer.
    """

    entry_id: uuid.UUID
    email: str
    name: str
    organisation: str | None = None
    role_or_reason: str
    created_at: datetime
    status: RequestStatus
    account_user_id: str | None = None
    account_created_at: datetime | None = None
    rejected_at: datetime | None = None
    note: str | None = None
    invite: RequestInvite | None = None


class SelfSignupOut(BaseModel):
    """The self-signup sweep's state, shown above the Requests list (contract C3, C4).

    Args:
        enabled: Whether the sweep runs on this service.
        domains: The listed domains.
        sent_this_hour: Invitations the sweep sent in the last hour.
        max_per_hour: The hourly cap.
    """

    enabled: bool
    domains: list[str]
    sent_this_hour: int
    max_per_hour: int


class RequestsOut(BaseModel):
    """Answer to ``GET /api/v1/ops/requests``."""

    items: list[RequestOut]
    self_signup: SelfSignupOut


class ApproveRequest(CohortChoice):
    """Body of ``POST /api/v1/ops/requests/{entry_id}/approve``.

    The person joins each cohort in ``cohort_ids``.
    """

    org_id: uuid.UUID


#: The longest invite-link label.
INVITE_LABEL_MAX = 200


class InviteLinkUpdate(BaseModel):
    """Body of ``POST /api/v1/ops/invite-links/{invite_link_id}``: the fields that may change.

    The command checks the use limit and the end against the link rules, so a
    refusal reads as the pages word it.

    Args:
        label: The operator's name for the link.
        max_uses: How many requests the link may redeem.
        expires_at: When it stops working, with its time zone.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label: str = Field(min_length=1, max_length=INVITE_LABEL_MAX)
    max_uses: int
    expires_at: AwareDatetime


class InviteLinkCreate(InviteLinkUpdate, CohortChoice):
    """Body of ``POST /api/v1/ops/invite-links``.

    Args:
        org_id: The organisation a redeemed request joins.
        allowed_domains: The email domains the link accepts, one each; the
            command lower-cases them and refuses none, more than ten or a repeat.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    org_id: uuid.UUID
    allowed_domains: list[Annotated[str, Field(max_length=253)]] = Field(max_length=100)


#: An invite link's state, worked out when it is read.
InviteLinkStateOut = Literal["active", "expired", "full", "revoked"]


class InviteLinkOut(BaseModel):
    """One invite link as the Invite links page lists it.

    Args:
        invite_link_id: The link's identity.
        label: The operator's name for it.
        organisation: The organisation a redeemed request joins.
        cohorts: The cohorts a redeemed person joins.
        allowed_domains: The email domains it accepts.
        max_uses: How many requests it may redeem.
        uses: How many it has redeemed.
        expires_at: When it stops working.
        revoked_at: When an operator revoked it, or ``None``.
        created_at: When it was made.
        state: See :data:`InviteLinkStateOut`.
        url: The full web address with the code in its fragment. Ops pages only.
    """

    invite_link_id: uuid.UUID
    label: str
    organisation: OrganisationRef
    cohorts: list[CohortRef]
    allowed_domains: list[str]
    max_uses: int
    uses: int
    expires_at: datetime
    revoked_at: datetime | None = None
    created_at: datetime
    state: InviteLinkStateOut
    url: str
