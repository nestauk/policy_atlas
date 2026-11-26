"""Announcements: who gets one, how it is recorded, and the background sender.

Four steps, in the order an announcement goes through them:

- :func:`build_recipients` turns the operator's choice (the audience) into a list
  of people. Each person is either ``pending`` (will get the email) or
  ``left_out`` with a reason. The list has a fingerprint, a SHA-256 hash, so the
  send can check that the list has not changed since the operator saw it.
- :func:`create_announcement` records the announcement, one row per person and
  one audit row, in the caller's transaction. It sends nothing.
- :func:`send_pending` sends to each ``pending`` row, one at a time. It marks a
  row ``sending`` before it calls the mailer and never touches a ``sending`` row
  again: if the server stops between the two, the person may or may not have the
  email, and the operator decides (at most one copy, never two).
- :func:`retry_failed` puts the ``failed`` rows back to ``pending``.

Logs and audit rows carry ids and counts only, never an address, a token or
the message text.
"""

from __future__ import annotations

import hashlib
import threading
import time
import uuid
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import UTC, datetime
from typing import Literal

import structlog
from sqlalchemy import Column, insert, or_, select, update
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.core.background import in_background
from policy_atlas.core.schema import (
    announcement,
    announcement_recipient,
    app_user,
    cohort,
    cohort_member,
    organisation,
)
from policy_atlas.ops import commands
from policy_atlas.ops.errors import NotFound, OpsError
from policy_atlas.ops.mail import (
    Kind,
    Mailer,
    MailSettings,
    Message,
    Suppressed,
    failure_code,
    render_announcement,
)

log = structlog.get_logger()

Status = Literal["pending", "left_out"]


@dataclass(frozen=True)
class Audience:
    """The operator's choice of people.

    Attributes:
        everyone: Every account. The three id lists must then be empty.
        cohort_ids: Cohorts whose members are chosen.
        org_ids: Organisations whose people are chosen.
        user_ids: People chosen one by one.
    """

    everyone: bool = False
    cohort_ids: tuple[uuid.UUID, ...] = ()
    org_ids: tuple[uuid.UUID, ...] = ()
    user_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.everyone and (self.cohort_ids or self.org_ids or self.user_ids):
            raise ValueError("an audience of everyone takes no cohort, organisation or person")


@dataclass(frozen=True)
class Recipient:
    """One person on the list.

    Attributes:
        user_id: The person's account id.
        name: Their display name.
        email: Their address, or ``None`` when the account has none.
        organisation: Their organisation's name, or ``None``.
        status: ``pending`` (gets the email) or ``left_out``.
        reason: Why they are left out, or ``None``.
    """

    user_id: str
    name: str
    email: str | None
    organisation: str | None
    status: Status
    reason: str | None


@dataclass(frozen=True)
class RecipientList:
    """The people an audience gives, with counts and a fingerprint.

    Attributes:
        recipients: Each person once, sorted by ``user_id``.
        chosen: How many people the audience gives.
        will_get: How many of them get the email.
        left_out: How many are left out, by reason.
        fingerprint: SHA-256 hex over every person's id, address, status and reason.
        summary: The audience in words: "Everyone", or the cohort and
            organisation names and how many people were chosen one by one.
    """

    recipients: tuple[Recipient, ...]
    chosen: int
    will_get: int
    left_out: dict[str, int]
    fingerprint: str
    summary: str


@dataclass(frozen=True)
class Created:
    """What :func:`create_announcement` recorded.

    Attributes:
        announcement_id: The new announcement's id.
        action_id: The id of its audit row.
        chosen: How many people the audience gave.
        will_get: How many of them get the email.
    """

    announcement_id: uuid.UUID
    action_id: uuid.UUID
    chosen: int
    will_get: int


@dataclass(frozen=True)
class Retried:
    """What :func:`retry_failed` did.

    Attributes:
        moved: How many rows went back to ``pending``.
        action_id: The id of its audit row.
    """

    moved: int
    action_id: uuid.UUID


class RecipientsChanged(OpsError):
    """Refusal raised when the list differs from the one the operator confirmed.

    Attributes:
        recipients: The list as it is now, for the operator to check again.
    """

    def __init__(self, recipients: RecipientList) -> None:
        self.recipients = recipients
        super().__init__("the list of people changed. Nothing was written. Check the list again.")


def build_recipients(
    conn: Connection, *, kind: Kind, audience: Audience, suppressed: Mapping[str, Suppressed]
) -> RecipientList:
    """Turn an audience into the list of people, each pending or left out.

    A person is left out for the first reason that applies: ``deactivated``,
    ``no_email``, ``suppressed_bounce`` or ``suppressed_complaint`` (the address
    is on the suppression list), then for a product update only
    ``not_signed_in`` and ``unsubscribed``.

    Args:
        conn: Open database connection.
        kind: ``product_update`` or ``service_notice``.
        audience: The operator's choice.
        suppressed: The suppression list, keyed by lower-cased address.

    Returns:
        The list, its counts, its fingerprint and the audience in words.

    Raises:
        NotFound: A cohort, organisation or person in the audience does not exist.
    """
    query = select(
        app_user.c.user_id,
        app_user.c.display_name,
        app_user.c.email,
        app_user.c.deactivated_at,
        app_user.c.first_signed_in_at,
        app_user.c.updates_unsubscribed_at,
        organisation.c.name.label("org_name"),
    ).select_from(app_user.outerjoin(organisation, app_user.c.org_id == organisation.c.org_id))
    people: list[str] = []
    if audience.everyone:
        summary = "Everyone"
    else:
        cohort_names = _names(
            conn, cohort.c.cohort_id, cohort.c.name, audience.cohort_ids, "cohort"
        )
        org_names = _names(
            conn, organisation.c.org_id, organisation.c.name, audience.org_ids, "organisation"
        )
        people = sorted(set(audience.user_ids))
        parts = cohort_names + org_names
        if people:
            parts.append(f"{len(people)} {'person' if len(people) == 1 else 'people'}")
        summary = ", ".join(parts)
        query = query.where(
            or_(
                app_user.c.user_id.in_(
                    select(cohort_member.c.user_id).where(
                        cohort_member.c.cohort_id.in_(audience.cohort_ids)
                    )
                ),
                app_user.c.org_id.in_(audience.org_ids),
                app_user.c.user_id.in_(people),
            )
        )
    rows = conn.execute(query).mappings().all()
    found = {row["user_id"] for row in rows}
    if missing := [user_id for user_id in people if user_id not in found]:
        raise NotFound(f"no user {missing[0]}")
    recipients = []
    for row in rows:
        reason = _left_out_reason(row, kind, suppressed)
        recipients.append(
            Recipient(
                user_id=row["user_id"],
                name=row["display_name"],
                email=row["email"],
                organisation=row["org_name"],
                status="pending" if reason is None else "left_out",
                reason=reason,
            )
        )
    recipients.sort(key=lambda person: person.user_id)
    left_out = Counter(person.reason for person in recipients if person.reason is not None)
    return RecipientList(
        recipients=tuple(recipients),
        chosen=len(recipients),
        will_get=len(recipients) - sum(left_out.values()),
        left_out=dict(left_out),
        fingerprint=_fingerprint(recipients),
        summary=summary,
    )


def create_announcement(
    conn: Connection,
    *,
    actor: str,
    message: Message,
    kind: Kind,
    audience: Audience,
    fingerprint: str,
    suppressed: Mapping[str, Suppressed],
    settings: MailSettings,
) -> Created:
    """Record an announcement, one row per person and one audit row.

    Everything runs on the caller's connection, in the caller's transaction;
    the caller commits and then starts the sender.

    Args:
        conn: Open database connection.
        actor: The operator's user id.
        message: The operator's fields.
        kind: ``product_update`` or ``service_notice``.
        audience: The operator's choice.
        fingerprint: The fingerprint of the list the operator confirmed.
        suppressed: The suppression list, keyed by lower-cased address.
        settings: Used to check the message the way the email will be built.

    Returns:
        The new announcement's id, its audit row's id and the list's counts.

    Raises:
        InvalidMessage: A field breaks a rule; nothing is written.
        NotFound: A cohort, organisation or person does not exist.
        RecipientsChanged: The list differs from the confirmed one; nothing is written.
    """
    # A sample token: only the field rules matter here.
    render_announcement(message, kind=kind, unsubscribe_token=str(uuid.uuid4()), settings=settings)
    recipients = build_recipients(conn, kind=kind, audience=audience, suppressed=suppressed)
    if recipients.fingerprint != fingerprint:
        raise RecipientsChanged(recipients)

    announcement_id = uuid.uuid4()
    now = _now()
    conn.execute(
        insert(announcement).values(
            announcement_id=announcement_id,
            kind=kind,
            **asdict(message),
            audience={
                "everyone": audience.everyone,
                "cohort_ids": [str(i) for i in audience.cohort_ids],
                "org_ids": [str(i) for i in audience.org_ids],
                "user_ids": list(audience.user_ids),
            },
            audience_summary=recipients.summary,
            sent_by=actor,
            created_at=now,
        )
    )
    if recipients.recipients:
        conn.execute(
            insert(announcement_recipient),
            [
                {
                    "announcement_id": announcement_id,
                    "user_id": person.user_id,
                    "email": person.email,
                    "status": person.status,
                    "reason": person.reason,
                    "updated_at": now,
                }
                for person in recipients.recipients
            ],
        )
    action_id = commands.record_action(
        conn, actor=actor, action="announcement.send", target=str(announcement_id), outcome="ok"
    )
    return Created(
        announcement_id=announcement_id,
        action_id=action_id,
        chosen=recipients.chosen,
        will_get=recipients.will_get,
    )


def send_pending(
    engine: Engine,
    mailer: Mailer,
    settings: MailSettings,
    announcement_id: uuid.UUID,
    *,
    pause: float = 0.2,
) -> None:
    """Send the announcement to each of its ``pending`` rows, until none is left.

    Each row is claimed in its own short transaction (so two senders never take
    the same row), the email goes out with no transaction open, and the result is
    written in a second transaction. A ``sending`` row is never touched.

    Args:
        engine: The database; each step takes its own connection.
        mailer: Sends the emails.
        settings: The addresses the email layout uses.
        announcement_id: The announcement to send.
        pause: Seconds to wait between emails.

    Raises:
        NotFound: No announcement has this id.
    """
    with engine.connect() as conn:
        row = (
            conn.execute(
                select(announcement).where(announcement.c.announcement_id == announcement_id)
            )
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise NotFound(f"no announcement {announcement_id}")
    kind: Kind = row["kind"]
    message = Message(**{f.name: row[f.name] for f in fields(Message)})
    counts: Counter[str] = Counter()
    # ponytail: one sender thread per announcement, a fixed pause for at most 5
    # emails a second; fine up to about 1,000 recipients. Beyond that, a queue
    # and a separate worker.
    while (claim := _claim(engine, announcement_id, kind)) is not None:
        user_id, status, email, token = claim
        if status == "left_out":
            counts["left_out"] += 1
            continue
        try:
            rendered = render_announcement(
                message,
                kind=kind,
                unsubscribe_token=str(token) if kind == "product_update" else None,
                settings=settings,
            )
            mailer.send(
                to=email, subject=rendered.subject, html=rendered.html, text=rendered.text,
                headers=rendered.headers,
            )
        except Exception as error:
            reason = failure_code(error)
            _finish(engine, announcement_id, user_id, "failed", reason)
            counts["failed"] += 1
            log.warning(
                "announcement.send_failed", announcement_id=str(announcement_id),
                user_id=user_id, reason=reason,
            )
        else:
            _finish(engine, announcement_id, user_id, "sent", None)
            counts["sent"] += 1
        if pause:
            time.sleep(pause)
    log.info(
        "announcement.sender_finished", announcement_id=str(announcement_id),
        sent=counts["sent"], failed=counts["failed"], left_out=counts["left_out"],
    )


def start_sender(
    engine: Engine, mailer: Mailer, settings: MailSettings, announcement_id: uuid.UUID
) -> threading.Thread:
    """Run :func:`send_pending` on a background thread and return the thread."""
    return in_background(
        lambda: send_pending(engine, mailer, settings, announcement_id),
        name=f"announcement-{announcement_id}",
        event="announcement.sender_crashed",
    )


def retry_failed(conn: Connection, *, actor: str, announcement_id: uuid.UUID) -> Retried:
    """Put the ``failed`` rows of one announcement back to ``pending``.

    ``sending`` and ``sent`` rows are never touched. The caller commits and then
    starts the sender, which also takes any row still ``pending``.

    Args:
        conn: Open database connection.
        actor: The operator's user id.
        announcement_id: The announcement.

    Returns:
        How many rows went back to ``pending``, and the audit row's id.

    Raises:
        NotFound: No announcement has this id.
    """
    exists = conn.execute(
        select(announcement.c.announcement_id).where(
            announcement.c.announcement_id == announcement_id
        )
    ).first()
    if exists is None:
        raise NotFound(f"no announcement {announcement_id}")
    moved = conn.execute(
        update(announcement_recipient)
        .where(
            announcement_recipient.c.announcement_id == announcement_id,
            announcement_recipient.c.status == "failed",
        )
        .values(status="pending", reason=None, updated_at=_now())
    ).rowcount
    action_id = commands.record_action(
        conn, actor=actor, action="announcement.retry", target=str(announcement_id), outcome="ok"
    )
    return Retried(moved=moved, action_id=action_id)


def resume_all(engine: Engine, mailer: Mailer, settings: MailSettings) -> list[threading.Thread]:
    """Start one sender for each announcement that has ``pending`` rows.

    Called when the ops server starts, so a send cut short by a stop finishes.

    Returns:
        The sender threads.
    """
    with engine.connect() as conn:
        ids = conn.execute(
            select(announcement_recipient.c.announcement_id)
            .where(announcement_recipient.c.status == "pending")
            .distinct()
        ).scalars().all()
    if ids:
        log.info("announcement.senders_resumed", count=len(ids))
    return [start_sender(engine, mailer, settings, announcement_id) for announcement_id in ids]


# --- helpers ------------------------------------------------------------------------------------


def _names(
    conn: Connection,
    id_column: Column[uuid.UUID],
    name_column: Column[str],
    ids: tuple[uuid.UUID, ...],
    what: str,
) -> list[str]:
    """Return the names of ``ids`` in the order given, or raise for the first unknown one."""
    by_id = dict(
        conn.execute(select(id_column, name_column).where(id_column.in_(ids))).tuples().all()
    )
    for wanted in ids:
        if wanted not in by_id:
            raise NotFound(f"no {what} {wanted}")
    return [by_id[wanted] for wanted in dict.fromkeys(ids)]


def _left_out_reason(
    row: RowMapping, kind: Kind, suppressed: Mapping[str, Suppressed]
) -> str | None:
    """Return the first reason that applies, or ``None`` when the person gets the email."""
    if row["deactivated_at"] is not None:
        return "deactivated"
    email = row["email"]
    if not isinstance(email, str) or not email:
        return "no_email"
    entry = suppressed.get(email.lower())
    if entry is not None:
        return f"suppressed_{entry.reason}"
    if kind == "product_update":
        if row["first_signed_in_at"] is None:
            return "not_signed_in"
        if row["updates_unsubscribed_at"] is not None:
            return "unsubscribed"
    return None


def _fingerprint(recipients: list[Recipient]) -> str:
    """SHA-256 hex over ``user_id|email|status|reason`` lines, sorted by ``user_id``."""
    lines = sorted(
        f"{p.user_id}|{p.email or ''}|{p.status}|{p.reason or ''}" for p in recipients
    )
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def _claim(
    engine: Engine, announcement_id: uuid.UUID, kind: Kind
) -> tuple[str, str, str, uuid.UUID] | None:
    """Take one ``pending`` row and decide it: ``sending``, or ``left_out`` with a reason.

    The person's account row is read ``FOR UPDATE``, so an unsubscribe or a
    deactivate running at the same moment waits; the commit of this transaction
    is the moment that decides.

    Returns:
        The user id, the new status, the address and the unsubscribe token, or
        ``None`` when no ``pending`` row is left that another sender has not taken.
    """
    with engine.begin() as conn:
        picked = conn.execute(
            select(announcement_recipient.c.user_id, announcement_recipient.c.email)
            .where(
                announcement_recipient.c.announcement_id == announcement_id,
                announcement_recipient.c.status == "pending",
            )
            .order_by(announcement_recipient.c.user_id)
            .limit(1)
            .with_for_update(skip_locked=True)
        ).first()
        if picked is None:
            return None
        user_id, email = picked
        person = conn.execute(
            select(
                app_user.c.deactivated_at,
                app_user.c.updates_unsubscribed_at,
                app_user.c.unsubscribe_token,
            )
            .where(app_user.c.user_id == user_id)
            .with_for_update()
        ).one()
        status, reason = "sending", None
        if person.deactivated_at is not None:
            status, reason = "left_out", "deactivated"
        elif kind == "product_update" and person.updates_unsubscribed_at is not None:
            status, reason = "left_out", "unsubscribed"
        conn.execute(
            update(announcement_recipient)
            .where(
                announcement_recipient.c.announcement_id == announcement_id,
                announcement_recipient.c.user_id == user_id,
            )
            .values(status=status, reason=reason, updated_at=_now())
        )
    return user_id, status, email, person.unsubscribe_token


def _finish(
    engine: Engine, announcement_id: uuid.UUID, user_id: str, status: str, reason: str | None
) -> None:
    """Write the result of one email to its ``sending`` row."""
    with engine.begin() as conn:
        conn.execute(
            update(announcement_recipient)
            .where(
                announcement_recipient.c.announcement_id == announcement_id,
                announcement_recipient.c.user_id == user_id,
                announcement_recipient.c.status == "sending",
            )
            .values(status=status, reason=reason, updated_at=_now())
        )


def _now() -> datetime:
    return datetime.now(UTC)
