"""Announcements: the recipient rules, the record of a send, the sender and retry.

The list rules run on the rolled-back ``conn`` fixture. Everything the sender
touches must be committed, because the sender opens its own connections: those
tests seed through ``seeded`` and run the sender on an engine that acts as the
ops server's restricted database login (``pa_ops``), so a missing grant fails here.
"""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Callable, Generator, Mapping
from datetime import UTC, datetime
from typing import Any

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.engine import Connection, Engine
from structlog.testing import capture_logs

from policy_atlas.core.schema import announcement, announcement_recipient, app_user, ops_action
from policy_atlas.ops.announcements import (
    Audience,
    RecipientList,
    RecipientsChanged,
    build_recipients,
    create_announcement,
    resume_all,
    retry_failed,
    send_pending,
)
from policy_atlas.ops.errors import NotFound
from policy_atlas.ops.mail import Kind, MailSettings, MemoryMailer, Message, Suppressed
from tests.api.org_support import seeded
from tests.ops.support import add_person, announcement_example, fresh_sub

SETTINGS = MailSettings(
    from_address="Policy Atlas <updates@example.org>",
    reply_to="team@example.org",
    site_url="https://site.example.org",
    api_url="https://api.example.org",
)
MESSAGE = Message(
    subject="What's new: theory of change maps",
    body="Maps are here.\n\n- Draw a map\n- Share it",
    button_label="Open Policy Atlas",
    button_url="https://site.example.org/",
)
WAIT = 10.0


@pytest.fixture(scope="module")
def pa_ops(engine: Engine) -> Generator[Engine, None, None]:
    """Yield an engine whose every connection acts as the ``pa_ops`` login.

    ``SET ROLE`` on each new connection gives the login's exact grants without
    switching the role's own login on and off, which other test modules do.
    """
    role_engine = create_engine(engine.url)

    @event.listens_for(role_engine, "connect")
    def _as_pa_ops(dbapi_connection: Any, _record: Any) -> None:
        with dbapi_connection.cursor() as cursor:
            cursor.execute("SET ROLE pa_ops")
        dbapi_connection.commit()

    yield role_engine
    role_engine.dispose()


def _list(
    conn: Connection,
    audience: Audience,
    kind: Kind = "product_update",
    suppressed: Mapping[str, Suppressed] | None = None,
) -> RecipientList:
    return build_recipients(conn, kind=kind, audience=audience, suppressed=suppressed or {})


def _announce(
    db: Engine, audience: Audience, kind: Kind = "product_update", actor: str = "ops-actor"
) -> uuid.UUID:
    """Build the list and record the announcement, committed."""
    with db.begin() as conn:
        listed = _list(conn, audience, kind)
        return create_announcement(
            conn, actor=actor, message=MESSAGE, kind=kind, audience=audience,
            fingerprint=listed.fingerprint, suppressed={}, settings=SETTINGS,
        ).announcement_id


def _rows(db: Engine, announcement_id: uuid.UUID) -> dict[str, tuple[str, str | None]]:
    with db.connect() as conn:
        rows = conn.execute(
            select(
                announcement_recipient.c.user_id,
                announcement_recipient.c.status,
                announcement_recipient.c.reason,
            ).where(announcement_recipient.c.announcement_id == announcement_id)
        ).all()
    return {user_id: (status, reason) for user_id, status, reason in rows}


def _people(engine: Engine, count: int, **fields: Any) -> list[str]:
    with seeded(engine) as conn:
        return [add_person(conn, **fields) for _ in range(count)]


def _email_of(engine: Engine, user_id: str) -> str:
    with engine.connect() as conn:
        email = conn.execute(select(app_user.c.email).where(app_user.c.user_id == user_id)).scalar()
    assert isinstance(email, str)
    return email


def _sent_to(mailer: MemoryMailer) -> list[str]:
    return [email.to for email in mailer.sent]


# --- the recipient rules ----------------------------------------------------------------------


def test_example_audience_gives_82_chosen_79_for_an_update_and_81_for_a_notice(
    conn: Connection,
) -> None:
    example = announcement_example(conn)

    update_list = _list(conn, example.audience, "product_update")
    notice_list = _list(conn, example.audience, "service_notice")

    assert update_list.chosen == 82
    assert update_list.will_get == 79
    assert update_list.left_out == {"unsubscribed": 2, "deactivated": 1}
    assert notice_list.chosen == 82
    assert notice_list.will_get == 81
    assert notice_list.left_out == {"deactivated": 1}
    ids = [person.user_id for person in update_list.recipients]
    assert ids == sorted(set(example.people))
    assert ids.count(example.in_both) == 1


def test_a_person_is_left_out_for_the_first_reason_that_applies(conn: Connection) -> None:
    deactivated = add_person(conn, deactivated=True, unsubscribed=True)
    no_email = add_person(conn, email=None, signed_in=False)
    bounced = add_person(conn, signed_in=False)
    complained = add_person(conn, unsubscribed=True)
    not_signed_in = add_person(conn, signed_in=False, unsubscribed=True)
    unsubscribed = add_person(conn, unsubscribed=True)
    suppressed = {
        _address(conn, bounced): Suppressed(reason="bounce", at=datetime.now(UTC)),
        _address(conn, complained): Suppressed(reason="complaint", at=datetime.now(UTC)),
    }
    audience = Audience(
        user_ids=(deactivated, no_email, bounced, complained, not_signed_in, unsubscribed)
    )

    listed = _list(conn, audience, "product_update", suppressed)

    reasons = {person.user_id: (person.status, person.reason) for person in listed.recipients}
    assert reasons == {
        deactivated: ("left_out", "deactivated"),
        no_email: ("left_out", "no_email"),
        bounced: ("left_out", "suppressed_bounce"),
        complained: ("left_out", "suppressed_complaint"),
        not_signed_in: ("left_out", "not_signed_in"),
        unsubscribed: ("left_out", "unsubscribed"),
    }


def test_a_service_notice_reaches_people_who_unsubscribed_or_have_not_signed_in(
    conn: Connection,
) -> None:
    unsubscribed = add_person(conn, unsubscribed=True)
    not_signed_in = add_person(conn, signed_in=False)

    listed = _list(conn, Audience(user_ids=(unsubscribed, not_signed_in)), "service_notice")

    assert listed.will_get == 2
    assert {person.status for person in listed.recipients} == {"pending"}


def test_everyone_is_every_account(conn: Connection) -> None:
    example = announcement_example(conn)

    listed = _list(conn, Audience(everyone=True), "service_notice")

    total = conn.execute(select(func.count()).select_from(app_user)).scalar_one()
    assert listed.chosen == total
    assert set(example.people) <= {person.user_id for person in listed.recipients}


@pytest.mark.parametrize("field", ["cohort_ids", "org_ids", "user_ids"])
def test_an_unknown_cohort_organisation_or_person_is_not_found(
    conn: Connection, field: str
) -> None:
    unknown: Any = (uuid.uuid4(),) if field != "user_ids" else (fresh_sub(),)

    with pytest.raises(NotFound):
        _list(conn, Audience(**{field: unknown}))


def test_the_fingerprint_changes_on_a_same_count_swap_and_on_an_address_change(
    conn: Connection,
) -> None:
    leaving, staying, joining = (add_person(conn) for _ in range(3))
    before = _list(conn, Audience(user_ids=(leaving, staying)))

    swapped = _list(conn, Audience(user_ids=(staying, joining)))
    conn.execute(
        update(app_user).where(app_user.c.user_id == leaving).values(email="new@example.org")
    )
    readdressed = _list(conn, Audience(user_ids=(leaving, staying)))

    assert swapped.chosen == before.chosen
    assert swapped.fingerprint != before.fingerprint
    assert readdressed.fingerprint != before.fingerprint


# --- create ----------------------------------------------------------------------------------


def test_create_records_the_announcement_every_person_and_one_audit_row(
    conn: Connection,
) -> None:
    example = announcement_example(conn)
    actor = fresh_sub("operator")
    listed = _list(conn, example.audience)

    announcement_id = create_announcement(
        conn, actor=actor, message=MESSAGE, kind="product_update", audience=example.audience,
        fingerprint=listed.fingerprint, suppressed={}, settings=SETTINGS,
    ).announcement_id

    stored = conn.execute(
        select(announcement).where(announcement.c.announcement_id == announcement_id)
    ).mappings().one()
    assert stored["sent_by"] == actor
    assert stored["audience_summary"] == f"{example.cohort_name}, {example.org_name}, 1 person"
    recipients = conn.execute(
        select(announcement_recipient.c.status, func.count())
        .where(announcement_recipient.c.announcement_id == announcement_id)
        .group_by(announcement_recipient.c.status)
    ).all()
    assert {status: count for status, count in recipients} == {"pending": 79, "left_out": 3}
    audit = conn.execute(
        select(ops_action.c.action, ops_action.c.target).where(ops_action.c.actor_user_id == actor)
    ).all()
    assert [tuple(row) for row in audit] == [("announcement.send", str(announcement_id))]


def test_create_refuses_a_changed_list_and_writes_nothing(conn: Connection) -> None:
    leaving, staying, joining = (add_person(conn) for _ in range(3))
    seen = _list(conn, Audience(user_ids=(leaving, staying)))
    actor = fresh_sub("operator")

    with pytest.raises(RecipientsChanged) as refused:
        create_announcement(
            conn, actor=actor, message=MESSAGE, kind="product_update",
            audience=Audience(user_ids=(staying, joining)), fingerprint=seen.fingerprint,
            suppressed={}, settings=SETTINGS,
        )

    assert refused.value.recipients.chosen == 2
    assert refused.value.recipients.fingerprint != seen.fingerprint
    written = conn.execute(
        select(func.count()).select_from(announcement).where(announcement.c.sent_by == actor)
    ).scalar_one()
    audited = conn.execute(
        select(func.count()).select_from(ops_action).where(ops_action.c.actor_user_id == actor)
    ).scalar_one()
    assert (written, audited) == (0, 0)


# --- the sender ------------------------------------------------------------------------------


def test_a_send_gives_each_person_one_email_with_their_own_token(
    engine: Engine, pa_ops: Engine
) -> None:
    with seeded(engine) as conn:
        example = announcement_example(conn)
    announcement_id = _announce(pa_ops, example.audience)
    mailer = MemoryMailer(SETTINGS)

    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    rows = _rows(engine, announcement_id)
    sent = {user_id for user_id, (status, _) in rows.items() if status == "sent"}
    assert len(sent) == 79
    assert "pending" not in {status for status, _ in rows.values()}
    with engine.connect() as conn:
        people = conn.execute(
            select(app_user.c.email, app_user.c.unsubscribe_token).where(
                app_user.c.user_id.in_(sent)
            )
        ).all()
    tokens = {email: str(token) for email, token in people}
    assert sorted(_sent_to(mailer)) == sorted(tokens)
    for email in mailer.sent:
        assert email.message.get_all("To") == [email.to]
        assert f"token={tokens[email.to]}>" in email.headers["List-Unsubscribe"]


def test_two_senders_on_one_announcement_send_each_email_once(
    engine: Engine, pa_ops: Engine
) -> None:
    with seeded(engine) as conn:
        example = announcement_example(conn)
    announcement_id = _announce(pa_ops, example.audience)
    mailer = MemoryMailer(SETTINGS)
    start = threading.Barrier(2)

    def sender() -> None:
        start.wait()
        send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    threads = [threading.Thread(target=sender) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(WAIT)

    addresses = _sent_to(mailer)
    assert len(addresses) == 79
    assert len(set(addresses)) == 79


def test_a_row_is_sending_while_the_mailer_is_called(engine: Engine, pa_ops: Engine) -> None:
    (person,) = _people(engine, 1)
    announcement_id = _announce(pa_ops, Audience(user_ids=(person,)))
    mailer = MemoryMailer(SETTINGS)
    seen: list[tuple[str, str | None]] = []
    mailer.on_send = lambda _to: seen.append(_rows(engine, announcement_id)[person])

    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    assert seen == [("sending", None)]
    assert _rows(engine, announcement_id)[person] == ("sent", None)


def test_a_person_who_unsubscribes_or_is_deactivated_after_the_send_was_recorded_gets_nothing(
    engine: Engine, pa_ops: Engine
) -> None:
    stays, unsubscribes, deactivated = _people(engine, 3)
    announcement_id = _announce(pa_ops, Audience(user_ids=(stays, unsubscribes, deactivated)))
    with engine.begin() as conn:
        now = datetime.now(UTC)
        conn.execute(
            update(app_user).where(app_user.c.user_id == unsubscribes)
            .values(updates_unsubscribed_at=now)
        )
        conn.execute(
            update(app_user).where(app_user.c.user_id == deactivated).values(deactivated_at=now)
        )
    mailer = MemoryMailer(SETTINGS)

    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    assert _sent_to(mailer) == [_email_of(engine, stays)]
    assert _rows(engine, announcement_id) == {
        stays: ("sent", None),
        unsubscribes: ("left_out", "unsubscribed"),
        deactivated: ("left_out", "deactivated"),
    }


def test_the_claim_waits_for_a_locked_account_and_decides_on_the_committed_value(
    engine: Engine, pa_ops: Engine
) -> None:
    (person,) = _people(engine, 1)
    announcement_id = _announce(pa_ops, Audience(user_ids=(person,)))
    mailer = MemoryMailer(SETTINGS)

    with engine.connect() as unsubscribe:
        held = unsubscribe.begin()
        unsubscribe.execute(
            update(app_user).where(app_user.c.user_id == person)
            .values(updates_unsubscribed_at=datetime.now(UTC))
        )
        sender = threading.Thread(
            target=send_pending, args=(pa_ops, mailer, SETTINGS, announcement_id),
            kwargs={"pause": 0},
        )
        sender.start()
        _wait_for_a_lock_wait(engine)
        assert sender.is_alive()
        assert mailer.sent == []
        held.commit()
    sender.join(WAIT)

    assert not sender.is_alive()
    assert mailer.sent == []
    assert _rows(engine, announcement_id)[person] == ("left_out", "unsubscribed")


def test_a_mailer_error_marks_the_row_failed_and_the_sender_goes_on(
    engine: Engine, pa_ops: Engine
) -> None:
    rejected, other = _people(engine, 2)
    announcement_id = _announce(pa_ops, Audience(user_ids=(rejected, other)))
    mailer = MemoryMailer(SETTINGS)
    mailer.on_send = _reject(_email_of(engine, rejected))

    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    assert _rows(engine, announcement_id) == {
        rejected: ("failed", "MessageRejected"),
        other: ("sent", None),
    }
    assert _sent_to(mailer) == [_email_of(engine, other)]


def test_a_stop_after_the_mailer_accepted_leaves_sending_and_nothing_sends_again(
    engine: Engine, pa_ops: Engine
) -> None:
    (person,) = _people(engine, 1)
    announcement_id = _announce(pa_ops, Audience(user_ids=(person,)))
    mailer = MemoryMailer(SETTINGS)

    class Stopped(BaseException):
        """Stands for the server stopping between the mailer and the row write."""

    class StopsAfterSending:
        def send(
            self, *, to: str, subject: str, html: str, text: str, headers: Mapping[str, str]
        ) -> None:
            mailer.send(to=to, subject=subject, html=html, text=text, headers=headers)
            raise Stopped

        def suppressed(self, since: datetime | None = None) -> dict[str, Suppressed]:
            return {}

    with pytest.raises(Stopped):
        send_pending(pa_ops, StopsAfterSending(), SETTINGS, announcement_id, pause=0)
    assert _rows(engine, announcement_id)[person] == ("sending", None)

    with pa_ops.begin() as conn:
        assert retry_failed(conn, actor="ops-actor", announcement_id=announcement_id).moved == 0
    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)
    for thread in resume_all(pa_ops, mailer, SETTINGS):
        thread.join(WAIT)

    assert _sent_to(mailer).count(_email_of(engine, person)) == 1
    assert _rows(engine, announcement_id)[person] == ("sending", None)


def test_retry_sends_the_failed_rows_and_leaves_sent_and_sending_alone(
    engine: Engine, pa_ops: Engine
) -> None:
    first, second, stuck, done = _people(engine, 4)
    announcement_id = _announce(pa_ops, Audience(user_ids=(first, second, stuck, done)))
    mailer = MemoryMailer(SETTINGS)
    mailer.on_send = _reject(_email_of(engine, first), _email_of(engine, second))
    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)
    with engine.begin() as conn:
        conn.execute(
            update(announcement_recipient)
            .where(
                announcement_recipient.c.announcement_id == announcement_id,
                announcement_recipient.c.user_id == stuck,
            )
            .values(status="sending")
        )
    actor = fresh_sub("operator")

    with pa_ops.begin() as conn:
        moved = retry_failed(conn, actor=actor, announcement_id=announcement_id).moved

    assert moved == 2
    assert _rows(engine, announcement_id) == {
        first: ("pending", None),
        second: ("pending", None),
        stuck: ("sending", None),
        done: ("sent", None),
    }
    with engine.connect() as conn:
        audit = conn.execute(
            select(ops_action.c.action, ops_action.c.target).where(
                ops_action.c.actor_user_id == actor
            )
        ).all()
    assert [tuple(row) for row in audit] == [("announcement.retry", str(announcement_id))]

    mailer.on_send = None
    before = len(mailer.sent)
    send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    assert sorted(_sent_to(mailer)[before:]) == sorted(
        [_email_of(engine, first), _email_of(engine, second)]
    )
    assert _rows(engine, announcement_id)[stuck] == ("sending", None)


def test_retry_of_an_unknown_announcement_is_not_found(pa_ops: Engine) -> None:
    with pa_ops.connect() as conn, pytest.raises(NotFound):
        retry_failed(conn, actor="ops-actor", announcement_id=uuid.uuid4())


def test_resume_all_finishes_pending_rows(engine: Engine, pa_ops: Engine) -> None:
    people = _people(engine, 3)
    announcement_id = _announce(pa_ops, Audience(user_ids=tuple(people)))
    mailer = MemoryMailer(SETTINGS)

    threads = resume_all(pa_ops, mailer, SETTINGS)
    for thread in threads:
        thread.join(WAIT)

    assert {status for status, _ in _rows(engine, announcement_id).values()} == {"sent"}
    assert set(_sent_to(mailer)) >= {_email_of(engine, person) for person in people}


def test_logs_and_audit_rows_of_a_send_hold_no_address_or_subject(
    engine: Engine, pa_ops: Engine
) -> None:
    rejected, other = _people(engine, 2)
    addresses = [_email_of(engine, rejected), _email_of(engine, other)]
    mailer = MemoryMailer(SETTINGS)
    mailer.on_send = _reject(addresses[0])
    actor = fresh_sub("operator")

    with capture_logs() as logs:
        announcement_id = _announce(pa_ops, Audience(user_ids=(rejected, other)), actor=actor)
        send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)
        with pa_ops.begin() as conn:
            retry_failed(conn, actor=actor, announcement_id=announcement_id)
        send_pending(pa_ops, mailer, SETTINGS, announcement_id, pause=0)

    with engine.connect() as conn:
        audit = conn.execute(
            select(ops_action.c.target, ops_action.c.outcome).where(
                ops_action.c.actor_user_id == actor
            )
        ).all()
    written = repr(logs) + repr(audit)
    assert logs and len(audit) == 2
    for secret in [*addresses, MESSAGE.subject, "@"]:
        assert secret not in written


# --- helpers ---------------------------------------------------------------------------------


def _address(conn: Connection, user_id: str) -> str:
    email = conn.execute(select(app_user.c.email).where(app_user.c.user_id == user_id)).scalar()
    assert isinstance(email, str)
    return email


def _reject(*addresses: str) -> Callable[[str], None]:
    """An ``on_send`` hook that fails like SES does for the given addresses.

    The error message holds the address, so a test sees whether it leaks.
    """

    def hook(to: str) -> None:
        if to in addresses:
            raise ClientError(
                {"Error": {"Code": "MessageRejected", "Message": f"rejected {to}"}}, "SendEmail"
            )

    return hook


def _wait_for_a_lock_wait(engine: Engine) -> None:
    """Return once a connection to this database waits on a row lock."""
    deadline = time.monotonic() + WAIT
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            waiting = conn.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock'"
                )
            ).scalar_one()
            if waiting:
                return
            time.sleep(0.01)
    raise AssertionError("the sender never waited on the locked account")
