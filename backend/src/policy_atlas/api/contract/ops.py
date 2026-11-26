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
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from policy_atlas.ops.mail import BODY_MAX, BUTTON_LABEL_MAX, IMAGE_ALT_MAX, SUBJECT_MAX, Kind

from .tenancy import OrganisationRef
from .waitlist import WaitlistSignup

#: Upper bounds on free text the ops pages send; the command functions
#: validate meaning, these only bound size.
OPS_NAME_MAX = 200
OPS_EMAIL_MAX = 320
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

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        """Lower-case and shape-check the address, as the waitlist form and the CLI do.

        Cognito's lookup is an exact, case-sensitive match, so one spelling per
        mailbox is what keeps a second identity from being minted.
        """
        return WaitlistSignup.validate_email(value)


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
    rejected_at: datetime | None = None
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


# --- announcements ---------------------------------------------------------------------------

#: ``product_update`` has an unsubscribe link and skips people who unsubscribed;
#: ``service_notice`` has neither.
AnnouncementKind = Kind
#: Why a person on the preview does not get the email, in order of precedence.
LeftOutReason = Literal[
    "deactivated", "no_email", "suppressed_bounce", "suppressed_complaint", "not_signed_in",
    "unsubscribed",
]
#: A link's size bound; whether a link is allowed is the email layout's rule.
ANNOUNCEMENT_URL_MAX = 2000
#: About 1 MB once decoded, with room for the route to answer with its own size message.
ANNOUNCEMENT_IMAGE_BASE64_MAX = 2_000_000


class AudienceIn(BaseModel):
    """Who an announcement goes to: everyone, or any mix of cohorts, organisations and people.

    With ``everyone`` true the three lists must be empty; with it false at least
    one id is needed.
    """

    model_config = ConfigDict(extra="forbid")

    everyone: bool = False
    cohort_ids: list[uuid.UUID] = Field(default_factory=list, max_length=OPS_BULK_MAX)
    org_ids: list[uuid.UUID] = Field(default_factory=list, max_length=OPS_BULK_MAX)
    user_ids: list[str] = Field(default_factory=list, max_length=OPS_BULK_MAX)

    @model_validator(mode="after")
    def _one_way(self) -> AudienceIn:
        chosen = bool(self.cohort_ids or self.org_ids or self.user_ids)
        if self.everyone and chosen:
            raise ValueError("an audience of everyone takes no cohort, organisation or person")
        if not self.everyone and not chosen:
            raise ValueError("choose everyone, or at least one cohort, organisation or person")
        return self


class AnnouncementMessageIn(BaseModel):
    """The fields the operator writes. The field rules live in the email layout (422)."""

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(max_length=SUBJECT_MAX)
    body: str = Field(max_length=BODY_MAX)
    button_label: str | None = Field(default=None, max_length=BUTTON_LABEL_MAX)
    button_url: str | None = Field(default=None, max_length=ANNOUNCEMENT_URL_MAX)
    image_url: str | None = Field(default=None, max_length=ANNOUNCEMENT_URL_MAX)
    image_alt: str | None = Field(default=None, max_length=IMAGE_ALT_MAX)


class AnnouncementRecipientsIn(BaseModel):
    """Body of ``POST /api/v1/ops/announcements/recipients``."""

    model_config = ConfigDict(extra="forbid")

    kind: AnnouncementKind
    audience: AudienceIn


class AnnouncementTestIn(AnnouncementMessageIn):
    """Body of ``POST /api/v1/ops/announcements/test``."""

    kind: AnnouncementKind


class AnnouncementSendIn(AnnouncementMessageIn):
    """Body of ``POST /api/v1/ops/announcements``.

    Args:
        fingerprint: The ``fingerprint`` of the preview the operator confirmed.
    """

    kind: AnnouncementKind
    audience: AudienceIn
    fingerprint: str = Field(min_length=1, max_length=128)


class AnnouncementRecipientOut(BaseModel):
    """One person on the preview.

    Args:
        user_id: The account.
        name: The display name.
        email: The address, or ``None`` when the account has none.
        organisation: The organisation's name, or ``None``.
        status: ``pending`` (gets the email) or ``left_out``.
        reason: Why they are left out, or ``None``.
    """

    user_id: str
    name: str
    email: str | None
    organisation: str | None
    status: Literal["pending", "left_out"]
    reason: LeftOutReason | None


class AnnouncementRecipientsOut(BaseModel):
    """The preview: counts, each person, and the list's fingerprint.

    Also the ``details`` of the 409 ``recipients_changed`` answer to a send.

    Args:
        chosen: How many people the audience gives.
        will_get: How many of them get the email.
        left_out: How many are left out, by reason (only reasons that occur).
        recipients: Each person once, sorted by ``user_id``.
        fingerprint: A hash of the list; the send must carry it back.
    """

    chosen: int
    will_get: int
    left_out: dict[LeftOutReason, int]
    recipients: list[AnnouncementRecipientOut]
    fingerprint: str


class AnnouncementImageIn(BaseModel):
    """Body of ``POST /api/v1/ops/announcement-images``: a PNG or JPEG, base64, at most 1 MB."""

    model_config = ConfigDict(extra="forbid")

    content_type: Literal["image/png", "image/jpeg"]
    data_base64: str = Field(min_length=1, max_length=ANNOUNCEMENT_IMAGE_BASE64_MAX)


class AnnouncementImageOut(BaseModel):
    """The stored picture's public address, for ``image_url``."""

    url: str


class AnnouncementCreatedOut(BaseModel):
    """Answer to a send: the new announcement's id."""

    announcement_id: uuid.UUID


class AnnouncementCounts(BaseModel):
    """How many recipient rows are in each status."""

    pending: int = 0
    sending: int = 0
    sent: int = 0
    failed: int = 0
    left_out: int = 0


class AnnouncementSummaryOut(BaseModel):
    """One announcement on the list.

    Args:
        announcement_id: The announcement.
        subject: Its subject line.
        kind: Product update or service notice.
        audience_summary: The audience in words ("Everyone", or the names).
        sent_by_name: The operator's display name, or ``None`` if unknown.
        created_at: When it was sent.
        counts: Recipient rows by status.
    """

    announcement_id: uuid.UUID
    subject: str
    kind: AnnouncementKind
    audience_summary: str
    sent_by_name: str | None
    created_at: datetime
    counts: AnnouncementCounts


class AnnouncementsOut(BaseModel):
    """Answer to ``GET /api/v1/ops/announcements``: newest first."""

    items: list[AnnouncementSummaryOut]


class AnnouncementResultOut(BaseModel):
    """One person's result on an announcement.

    Args:
        user_id: The account.
        name: The display name now.
        email: The address the email went to (as it was at the send).
        organisation: The organisation's name now, or ``None``.
        status: ``pending``, ``sending`` (the page says "Not confirmed" once
            the send has stopped), ``sent``, ``failed`` or ``left_out``.
        reason: The left-out reason, a short failure code, or ``None``.
        overlay: For a ``sent`` row whose address joined the suppression list
            after the send: ``bounced`` or ``marked_as_spam``. Not stored.
    """

    user_id: str
    name: str
    email: str | None
    organisation: str | None
    status: Literal["pending", "sending", "sent", "failed", "left_out"]
    reason: str | None
    overlay: Literal["bounced", "marked_as_spam"] | None


class AnnouncementDetailOut(AnnouncementSummaryOut):
    """Answer to ``GET /api/v1/ops/announcements/{announcement_id}``.

    Args:
        body: The message text.
        button_label: The button's words, or ``None``.
        button_url: The button's link, or ``None``.
        image_url: The picture's address, or ``None``.
        image_alt: The picture's description, or ``None``.
        recipients: Each person's result, by name.
        suppression_unreadable: True when the suppression list could not be
            read, so no row carries an overlay.
    """

    body: str
    button_label: str | None
    button_url: str | None
    image_url: str | None
    image_alt: str | None
    recipients: list[AnnouncementResultOut]
    suppression_unreadable: bool
