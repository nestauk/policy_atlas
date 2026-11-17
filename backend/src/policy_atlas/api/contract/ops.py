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
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .tenancy import OrganisationRef

#: Upper bounds on free text the ops pages send; the command functions
#: validate meaning, these only bound size.
OPS_NAME_MAX = 200
OPS_EMAIL_MAX = 320
#: The most subjects one bulk action takes. The people list is the whole
#: user base (under a hundred people), so this is a sanity bound, not paging.
OPS_BULK_MAX = 200


class LimitsOut(BaseModel):
    """The limits that apply to one person after resolution (contract B12).

    Args:
        task_quota_per_year: Tasks the person may create in 365 days, or
            ``None`` for no limit (an administrator, or an override of 0).
        runs_per_user: Walks the person's tasks may hold at once, or ``None``
            for no limit (an override of 0).
    """

    task_quota_per_year: int | None
    runs_per_user: int | None


class QuotaSet(BaseModel):
    """The two override fields of a quota form (contract B12).

    ``None`` clears the override so the next level applies; ``0`` means no
    limit. Both fields are always sent: the form shows both.
    """

    model_config = ConfigDict(extra="forbid")

    task_quota_per_year: int | None = Field(default=None, ge=0)
    runs_per_user: int | None = Field(default=None, ge=0)


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
        task_quota_per_year: Their own override, or ``None``.
        runs_per_user: Their own override, or ``None``.
        tasks_this_year: Tasks they created in the last 365 days.
        limits: The limits that apply after resolution.
    """

    user_id: str
    display_name: str
    email: str | None = None
    organisation: OrganisationRef | None = None
    is_admin: bool
    is_ops: bool
    created_at: datetime
    invited_at: datetime | None = None
    task_quota_per_year: int | None = None
    runs_per_user: int | None = None
    tasks_this_year: int
    limits: LimitsOut


class PersonCreate(BaseModel):
    """Body of ``POST /api/v1/ops/people``: create a person in an organisation.

    The organisation is required (contract B4): a browser-created account is
    never unenrolled. The route calls the ensure-account command, so an
    address that already has an unenrolled account is enrolled without a
    second invitation.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=OPS_EMAIL_MAX)
    display_name: str = Field(min_length=1, max_length=OPS_NAME_MAX)
    org_id: uuid.UUID


class PersonCreatedOut(BaseModel):
    """Answer to ``POST /api/v1/ops/people``.

    Args:
        person: The person as the list now shows them.
        invitation_sent: Whether Cognito sent an invitation on this call.
            ``False`` when the address already had an account.
    """

    person: PersonOut
    invitation_sent: bool


#: How one subject of a bulk action ended. ``ok`` means the command ran and
#: its audit row is written; ``failed`` means this subject's savepoint was
#: rolled back and a ``failed`` audit row written; ``too_soon`` is the resend
#: cooldown (contract B4).
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


class BulkEnrol(BulkSubjects):
    """Body of ``POST /api/v1/ops/people/enrol``: enrol or move into ``org_id``."""

    org_id: uuid.UUID


class BulkQuota(BulkSubjects, QuotaSet):
    """Body of ``POST /api/v1/ops/people/quota``: the same two fields for every subject."""


#: A waitlist row's state on the Requests page (contract C5). ``waiting``: no
#: account yet and no listed domain, so an operator approves it; ``invited``:
#: stamped by the sweep or an approval; ``check``: the address already belongs
#: to another organisation, left for a person to decide.
RequestStatus = Literal["waiting", "invited", "check"]


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
    note: str | None = None


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


class ApproveRequest(BaseModel):
    """Body of ``POST /api/v1/ops/requests/{entry_id}/approve``."""

    model_config = ConfigDict(extra="forbid")

    org_id: uuid.UUID


class RowAssign(BaseModel):
    """Body of ``POST /api/v1/ops/rows/assign``: exactly one of the two ids."""

    model_config = ConfigDict(extra="forbid")

    task_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    org_id: uuid.UUID


class AssignmentOut(BaseModel):
    """What ``rows assign`` moved (see :class:`policy_atlas.ops.commands.Assignment`)."""

    org: OrganisationRef
    project_id: uuid.UUID | None = None
    tasks_moved: int
    projects_moved: int
    followed_membership: bool
    privatised: bool
    message: str
    action_id: uuid.UUID
