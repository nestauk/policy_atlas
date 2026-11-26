"""The ops routes for announcement email.

Every case drives the real ops-mode application against the test database. The
mailer is the in-memory one, put on the application's state the way the
lifespan puts the real one; the picture store is a temporary folder.
"""

from __future__ import annotations

import base64
import os
import time
import uuid
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.api.app import create_app
from policy_atlas.api.deps import get_announcement_image_store
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings
from policy_atlas.core.schema import (
    announcement,
    announcement_recipient,
    app_user,
    cohort,
    cohort_member,
    ops_action,
)
from policy_atlas.core.uploads import LocalUploadStore
from policy_atlas.ops import announcements
from policy_atlas.ops.mail import MailSettings, MemoryMailer, Message, Suppressed
from tests.api.org_support import Principal, ops_enrol, seeded, unique_email
from tests.api.test_api_conformance import _flatten_api_routes
from tests.ops.support import add_person, announcement_example

SITE = "https://site.example.test"
MAIL = MailSettings(
    from_address="Policy Atlas <updates@example.test>",
    reply_to="team@example.test",
    site_url=SITE,
    api_url="https://api.example.test",
)
SAMPLE_TOKEN = "00000000-0000-0000-0000-000000000000"
SUBJECT = "Maps are here for everyone"
BODY = "Draw a theory of change.\n\n- Draw a map\n- Share it"
MESSAGE: dict[str, Any] = {
    "subject": SUBJECT,
    "body": BODY,
    "button_label": "Open Policy Atlas",
    "button_url": f"{SITE}/",
}
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WAIT = 15.0

_ANNOUNCEMENT_ROUTES = {
    ("POST", "/api/v1/ops/announcements/recipients"),
    ("POST", "/api/v1/ops/announcements/test"),
    ("POST", "/api/v1/ops/announcement-images"),
    ("POST", "/api/v1/ops/announcements"),
    ("GET", "/api/v1/ops/announcements"),
    ("GET", "/api/v1/ops/announcements/{announcement_id}"),
    ("POST", "/api/v1/ops/announcements/{announcement_id}/retry"),
}


class Harness(NamedTuple):
    """One ops client, its ops-role caller, the mailer, the picture folder and the database."""

    client: TestClient
    settings: Settings
    actor: Principal
    mailer: MemoryMailer
    pictures: Path
    engine: Engine


def _settings(tmp_path: Path) -> Settings:
    """Ops-mode settings with the public site address but no sender (no mailer at start)."""
    return Settings(
        "http://dev-issuer.local",
        "ops-announcements-test",
        None,
        init(tmp_path / "issuer"),
        "http://ops.example.test",
        os.environ["DATABASE_URL"],
        service_role="ops",
        ops_ui_dir=None,
        public_site_url=SITE,
    )


def _principal(settings: Settings, tmp_path: Path, label: str) -> Principal:
    user_id = f"{label}-{uuid.uuid4()}"
    token = mint_token(
        user_id, settings.oidc_issuer, settings.oidc_client_id, 600, tmp_path / "issuer"
    )
    return Principal(user_id, {"Authorization": f"Bearer {token}"})


@pytest.fixture
def ops(engine: Engine, tmp_path: Path) -> Iterator[Harness]:
    """An ops client with a mailer, signed in as an operator who has an address."""
    settings = _settings(tmp_path)
    app = create_app(settings=settings)
    pictures = tmp_path / "pictures"
    app.dependency_overrides[get_announcement_image_store] = lambda: LocalUploadStore(pictures)
    mailer = MemoryMailer(MAIL)
    with TestClient(app, raise_server_exceptions=False) as client:
        app.state.mailer = mailer
        app.state.mail_settings = MAIL
        actor = _principal(settings, tmp_path, "ops-actor")
        with seeded(engine) as conn:
            ops_enrol(conn, user_id=actor.user_id, email=unique_email("operator"))
            conn.execute(
                update(app_user).where(app_user.c.user_id == actor.user_id).values(is_ops=True)
            )
        yield Harness(client, settings, actor, mailer, pictures, engine)


def _post(h: Harness, path: str, body: dict[str, Any] | None = None) -> Any:
    return h.client.post(path, json=body, headers=h.actor.headers)


def _get(h: Harness, path: str) -> Any:
    return h.client.get(path, headers=h.actor.headers)


def _actions(h: Harness, action: str) -> list[Any]:
    with h.engine.connect() as conn:
        return list(
            conn.execute(
                select(ops_action).where(
                    ops_action.c.actor_user_id == h.actor.user_id, ops_action.c.action == action
                )
            ).mappings()
        )


def _table_counts(engine: Engine) -> list[int]:
    with engine.connect() as conn:
        return [
            conn.execute(select(func.count()).select_from(table)).scalar_one()
            for table in (announcement, announcement_recipient, ops_action)
        ]


def _people(engine: Engine, count: int) -> list[str]:
    with seeded(engine) as conn:
        return [add_person(conn, name=f"Reader {n}") for n in range(count)]


def _email(engine: Engine, user_id: str) -> str:
    with engine.connect() as conn:
        return str(
            conn.execute(select(app_user.c.email).where(app_user.c.user_id == user_id)).scalar_one()
        )


def _rows(engine: Engine, announcement_id: uuid.UUID | str) -> dict[str, tuple[str, Any]]:
    with engine.connect() as conn:
        return {
            user_id: (status, updated_at)
            for user_id, status, updated_at in conn.execute(
                select(
                    announcement_recipient.c.user_id,
                    announcement_recipient.c.status,
                    announcement_recipient.c.updated_at,
                ).where(announcement_recipient.c.announcement_id == announcement_id)
            )
        }


def _wait_until(done: Callable[[], bool]) -> None:
    """Poll until ``done`` holds, failing after a deadline (the sender runs on a thread)."""
    deadline = time.monotonic() + WAIT
    while not done():
        assert time.monotonic() < deadline, "the sender did not finish in time"
        time.sleep(0.05)


def _settled(engine: Engine, announcement_id: uuid.UUID | str) -> Callable[[], bool]:
    def done() -> bool:
        return not {"pending", "sending"} & {s for s, _ in _rows(engine, announcement_id).values()}

    return done


def _preview(h: Harness, kind: str, audience: dict[str, Any]) -> Any:
    return _post(h, "/api/v1/ops/announcements/recipients", {"kind": kind, "audience": audience})


def _send(h: Harness, audience: dict[str, Any], kind: str = "product_update") -> Any:
    fingerprint = _preview(h, kind, audience).json()["fingerprint"]
    return _post(
        h, "/api/v1/ops/announcements",
        {**MESSAGE, "kind": kind, "audience": audience, "fingerprint": fingerprint},
    )


def _recorded(engine: Engine, people: list[str]) -> uuid.UUID:
    """Record an announcement to ``people`` directly, with no sender started."""
    audience = announcements.Audience(user_ids=tuple(people))
    with seeded(engine) as conn:
        built = announcements.build_recipients(
            conn, kind="service_notice", audience=audience, suppressed={}
        )
        return announcements.create_announcement(
            conn, actor="recorder", message=Message(subject=SUBJECT, body=BODY),
            kind="service_notice", audience=audience, fingerprint=built.fingerprint,
            suppressed={}, settings=MAIL,
        )


def _set_status(engine: Engine, announcement_id: uuid.UUID, user_id: str, status: str) -> None:
    with seeded(engine) as conn:
        conn.execute(
            update(announcement_recipient)
            .where(
                announcement_recipient.c.announcement_id == announcement_id,
                announcement_recipient.c.user_id == user_id,
            )
            .values(status=status)
        )


# --- the role gate and the missing mailer ------------------------------------------------------


@pytest.mark.parametrize(("method", "path"), sorted(_ANNOUNCEMENT_ROUTES))
def test_every_announcement_route_refuses_a_user_without_the_ops_role(
    ops: Harness, engine: Engine, tmp_path: Path, method: str, path: str
) -> None:
    routes = {
        (m, route.path)
        for route in _flatten_api_routes(ops.client.app.routes)  # type: ignore[attr-defined]
        for m in route.methods or ()
        if route.path.startswith("/api/v1/ops/announcement")
    }
    assert routes == _ANNOUNCEMENT_ROUTES
    plain = _principal(ops.settings, tmp_path, "plain")
    with seeded(engine) as conn:
        ops_enrol(conn, user_id=plain.user_id, email=unique_email("plain"))
    filled = path.format(announcement_id=uuid.uuid4())
    assert ops.client.request(method, filled).status_code == 401
    assert ops.client.request(method, filled, headers=plain.headers).status_code == 403


def test_without_a_mailer_the_sending_routes_answer_503(ops: Harness) -> None:
    ops.client.app.state.mailer = None  # type: ignore[attr-defined]
    ops.client.app.state.mail_settings = None  # type: ignore[attr-defined]
    audience = {"user_ids": _people(ops.engine, 1)}
    announcement_id = _recorded(ops.engine, audience["user_ids"])
    answers = [
        _preview(ops, "product_update", audience),
        _post(ops, "/api/v1/ops/announcements/test", {**MESSAGE, "kind": "product_update"}),
        _post(ops, "/api/v1/ops/announcements",
              {**MESSAGE, "kind": "product_update", "audience": audience, "fingerprint": "x"}),
        _post(ops, f"/api/v1/ops/announcements/{announcement_id}/retry"),
    ]
    assert [answer.status_code for answer in answers] == [503] * 4
    assert _get(ops, "/api/v1/ops/announcements").status_code == 200
    detail = _get(ops, f"/api/v1/ops/announcements/{announcement_id}")
    assert detail.status_code == 200
    assert detail.json()["suppression_unreadable"] is True


# --- preview -----------------------------------------------------------------------------------


def test_preview_gives_the_example_counts_and_reasons_and_writes_nothing(ops: Harness) -> None:
    with seeded(ops.engine) as conn:
        example = announcement_example(conn)
    audience = {
        "cohort_ids": [str(example.cohort_id)],
        "org_ids": [str(example.org_id)],
        "user_ids": [example.tomas],
    }
    before = _table_counts(ops.engine)

    update_answer = _preview(ops, "product_update", audience)
    notice_answer = _preview(ops, "service_notice", audience)

    assert update_answer.status_code == 200
    update_body, notice_body = update_answer.json(), notice_answer.json()
    assert (update_body["chosen"], update_body["will_get"]) == (82, 79)
    assert update_body["left_out"] == {"deactivated": 1, "unsubscribed": 2}
    assert (notice_body["chosen"], notice_body["will_get"]) == (82, 81)
    assert notice_body["left_out"] == {"deactivated": 1}
    tomas = next(p for p in update_body["recipients"] if p["user_id"] == example.tomas)
    assert tomas["name"] == "Tomás Ferreira"
    assert tomas["status"] == "pending" and tomas["reason"] is None
    assert len(update_body["fingerprint"]) == 64
    assert _table_counts(ops.engine) == before


def test_an_audience_must_be_everyone_or_name_at_least_one_id(ops: Harness) -> None:
    person = _people(ops.engine, 1)
    assert _preview(ops, "product_update", {"everyone": False}).status_code == 422
    both = {"everyone": True, "user_ids": person}
    assert _preview(ops, "product_update", both).status_code == 422


def test_preview_of_an_unknown_cohort_is_not_found(ops: Harness) -> None:
    answer = _preview(ops, "service_notice", {"cohort_ids": [str(uuid.uuid4())]})
    assert answer.status_code == 404


# --- test send ---------------------------------------------------------------------------------


def test_a_test_goes_only_to_the_operators_own_address_with_the_sample_token(
    ops: Harness,
) -> None:
    answer = _post(ops, "/api/v1/ops/announcements/test", {**MESSAGE, "kind": "product_update"})

    assert answer.status_code == 204
    assert len(ops.mailer.sent) == 1
    email = ops.mailer.sent[0]
    assert email.to == _email(ops.engine, ops.actor.user_id)
    assert email.subject == f"[Test] {SUBJECT}"
    assert SAMPLE_TOKEN in email.headers["List-Unsubscribe"]
    with ops.engine.connect() as conn:
        holders = conn.execute(
            select(func.count()).where(app_user.c.unsubscribe_token == uuid.UUID(SAMPLE_TOKEN))
        ).scalar_one()
    assert holders == 0
    [row] = _actions(ops, "announcement.test")
    assert row["target"] == ops.actor.user_id


def test_a_test_that_the_mailer_refuses_answers_502_with_a_code_and_no_address(
    ops: Harness,
) -> None:
    def refuse(to: str) -> None:
        raise ConnectionError(to)

    ops.mailer.on_send = refuse
    answer = _post(ops, "/api/v1/ops/announcements/test", {**MESSAGE, "kind": "service_notice"})

    assert answer.status_code == 502
    assert answer.json()["error"]["code"] == "upstream_failed"
    assert "ConnectionError" in answer.json()["error"]["message"]
    assert "@" not in answer.text
    assert _actions(ops, "announcement.test") == []


def test_a_field_rule_answers_422_and_writes_nothing(ops: Harness) -> None:
    audience = {"user_ids": _people(ops.engine, 1)}
    before = _table_counts(ops.engine)
    bad = {**MESSAGE, "button_url": "http://site.example.test/"}
    fingerprint = _preview(ops, "service_notice", audience).json()["fingerprint"]

    sent = _post(ops, "/api/v1/ops/announcements",
                 {**bad, "kind": "service_notice", "audience": audience,
                  "fingerprint": fingerprint})
    tested = _post(ops, "/api/v1/ops/announcements/test", {**bad, "kind": "service_notice"})

    assert (sent.status_code, tested.status_code) == (422, 422)
    assert "https://" in sent.json()["error"]["message"]
    assert sent.json()["error"]["details"] == {"field": "button_url"}
    assert tested.json()["error"]["code"] == "invalid_message"
    assert _table_counts(ops.engine) == before
    assert ops.mailer.sent == []


# --- pictures ----------------------------------------------------------------------------------


def _picture(h: Harness, data: bytes, content_type: str) -> Any:
    return _post(h, "/api/v1/ops/announcement-images",
                 {"content_type": content_type, "data_base64": base64.b64encode(data).decode()})


def test_a_png_and_a_jpeg_are_stored_and_their_address_returned(ops: Harness) -> None:
    urls = [
        _picture(ops, PNG, "image/png").json()["url"],
        _picture(ops, JPEG, "image/jpeg").json()["url"],
    ]

    assert urls[0].startswith(f"{SITE}/email-images/") and urls[0].endswith(".png")
    assert urls[1].startswith(f"{SITE}/email-images/") and urls[1].endswith(".jpg")
    stored = {p.name: p.read_bytes() for p in (ops.pictures / "email-images").iterdir()}
    assert stored == {urls[0].rsplit("/", 1)[1]: PNG, urls[1].rsplit("/", 1)[1]: JPEG}
    assert sorted(row["target"] for row in _actions(ops, "announcement.image")) == sorted(
        url.rsplit("/", 1)[1] for url in urls
    )


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (PNG + b"\x00" * (1024 * 1024), "image/png"),
        (b'<svg xmlns="http://www.w3.org/2000/svg"/>', "image/svg+xml"),
        (b"just some text, named as a picture", "image/png"),
    ],
    ids=["over-1-mb", "svg", "text-declared-png"],
)
def test_a_picture_that_breaks_a_rule_is_refused_and_nothing_is_stored(
    ops: Harness, data: bytes, content_type: str
) -> None:
    answer = _picture(ops, data, content_type)

    assert answer.status_code == 422
    assert not ops.pictures.exists()
    assert _actions(ops, "announcement.image") == []


# --- send --------------------------------------------------------------------------------------


def test_a_send_records_everything_and_the_sender_runs_after_the_commit(ops: Harness) -> None:
    people = _people(ops.engine, 2)

    answer = _send(ops, {"user_ids": people})

    assert answer.status_code == 201
    announcement_id = answer.json()["announcement_id"]
    with ops.engine.connect() as conn:
        assert conn.execute(
            select(func.count()).where(announcement.c.announcement_id == announcement_id)
        ).scalar_one() == 1
    assert set(_rows(ops.engine, announcement_id)) == set(people)
    [audit] = _actions(ops, "announcement.send")
    assert audit["target"] == announcement_id
    _wait_until(_settled(ops.engine, announcement_id))
    assert {s for s, _ in _rows(ops.engine, announcement_id).values()} == {"sent"}
    assert sorted(email.to for email in ops.mailer.sent) == sorted(
        _email(ops.engine, person) for person in people
    )


def test_a_changed_list_with_the_same_count_answers_409_and_inserts_nothing(
    ops: Harness,
) -> None:
    stays, leaves, joins = _people(ops.engine, 3)
    cohort_id = uuid.uuid4()
    now = datetime.now(UTC)
    with seeded(ops.engine) as conn:
        conn.execute(insert(cohort).values(cohort_id=cohort_id, name=f"Pilot {cohort_id}",
                                           created_at=now))
        conn.execute(insert(cohort_member), [
            {"cohort_id": cohort_id, "user_id": user_id, "added_at": now}
            for user_id in (stays, leaves)
        ])
    audience = {"cohort_ids": [str(cohort_id)]}
    confirmed = _preview(ops, "service_notice", audience).json()["fingerprint"]
    with seeded(ops.engine) as conn:
        conn.execute(delete(cohort_member).where(cohort_member.c.user_id == leaves))
        conn.execute(insert(cohort_member).values(cohort_id=cohort_id, user_id=joins,
                                                  added_at=now))
    before = _table_counts(ops.engine)

    answer = _post(ops, "/api/v1/ops/announcements",
                   {**MESSAGE, "kind": "service_notice", "audience": audience,
                    "fingerprint": confirmed})

    assert answer.status_code == 409
    error = answer.json()["error"]
    assert error["code"] == "recipients_changed"
    details = error["details"]
    assert details["chosen"] == 2
    assert {p["user_id"] for p in details["recipients"]} == {stays, joins}
    assert details["fingerprint"] == _preview(ops, "service_notice", audience).json()["fingerprint"]
    assert details["fingerprint"] != confirmed
    assert _table_counts(ops.engine) == before


def test_preview_and_send_answer_503_when_the_suppression_list_cannot_be_read(
    ops: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    audience = {"user_ids": _people(ops.engine, 1)}
    fingerprint = _preview(ops, "service_notice", audience).json()["fingerprint"]

    def unreadable(since: datetime | None = None) -> dict[str, Suppressed]:
        raise ConnectionError("down")

    monkeypatch.setattr(ops.mailer, "suppressed", unreadable)
    before = _table_counts(ops.engine)

    assert _preview(ops, "service_notice", audience).status_code == 503
    sent = _post(ops, "/api/v1/ops/announcements",
                 {**MESSAGE, "kind": "service_notice", "audience": audience,
                  "fingerprint": fingerprint})
    assert sent.status_code == 503
    assert _table_counts(ops.engine) == before


# --- list and detail ---------------------------------------------------------------------------


def test_the_list_counts_each_announcement_by_status_newest_first(ops: Harness) -> None:
    people = _people(ops.engine, 3)
    older = _recorded(ops.engine, people[:1])
    newer = _recorded(ops.engine, people)
    _set_status(ops.engine, newer, people[0], "sent")
    _set_status(ops.engine, newer, people[1], "failed")

    items = _get(ops, "/api/v1/ops/announcements").json()["items"]

    ids = [item["announcement_id"] for item in items]
    assert ids.index(str(newer)) < ids.index(str(older))
    item = items[ids.index(str(newer))]
    assert item["counts"] == {"pending": 1, "sending": 0, "sent": 1, "failed": 1, "left_out": 0}
    assert item["subject"] == SUBJECT
    assert item["kind"] == "service_notice"
    assert item["audience_summary"] == "3 people"


def test_the_detail_shows_a_sent_row_bounced_after_the_send_and_stores_nothing(
    ops: Harness,
) -> None:
    bounced, fine = _people(ops.engine, 2)
    announcement_id = _recorded(ops.engine, [bounced, fine])
    for person in (bounced, fine):
        _set_status(ops.engine, announcement_id, person, "sent")
    ops.mailer.suppression[_email(ops.engine, bounced).lower()] = Suppressed(
        reason="bounce", at=datetime.now(UTC)
    )
    stored = _rows(ops.engine, announcement_id)

    detail = _get(ops, f"/api/v1/ops/announcements/{announcement_id}").json()

    overlays = {p["user_id"]: p["overlay"] for p in detail["recipients"]}
    assert overlays == {bounced: "bounced", fine: None}
    assert detail["suppression_unreadable"] is False
    assert detail["body"] == BODY
    assert _rows(ops.engine, announcement_id) == stored


def test_the_detail_answers_with_the_flag_when_the_suppression_list_cannot_be_read(
    ops: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    person = _people(ops.engine, 1)[0]
    announcement_id = _recorded(ops.engine, [person])
    _set_status(ops.engine, announcement_id, person, "sent")

    def unreadable(since: datetime | None = None) -> dict[str, Suppressed]:
        raise ConnectionError("down")

    monkeypatch.setattr(ops.mailer, "suppressed", unreadable)
    answer = _get(ops, f"/api/v1/ops/announcements/{announcement_id}")

    assert answer.status_code == 200
    assert answer.json()["suppression_unreadable"] is True
    assert answer.json()["recipients"][0]["overlay"] is None


def test_the_detail_returns_a_sending_row_as_sending(ops: Harness) -> None:
    person = _people(ops.engine, 1)[0]
    announcement_id = _recorded(ops.engine, [person])
    _set_status(ops.engine, announcement_id, person, "sending")

    detail = _get(ops, f"/api/v1/ops/announcements/{announcement_id}").json()

    assert detail["recipients"][0]["status"] == "sending"
    assert detail["counts"]["sending"] == 1
    assert _rows(ops.engine, announcement_id)[person][0] == "sending"


def test_the_detail_of_an_unknown_announcement_is_not_found(ops: Harness) -> None:
    assert _get(ops, f"/api/v1/ops/announcements/{uuid.uuid4()}").status_code == 404


# --- retry -------------------------------------------------------------------------------------


def test_retry_sends_the_failed_rows_and_leaves_sent_and_sending_alone(ops: Harness) -> None:
    failed, sent, sending = _people(ops.engine, 3)
    announcement_id = _recorded(ops.engine, [failed, sent, sending])
    _set_status(ops.engine, announcement_id, failed, "failed")
    _set_status(ops.engine, announcement_id, sent, "sent")
    _set_status(ops.engine, announcement_id, sending, "sending")
    before = _rows(ops.engine, announcement_id)

    answer = _post(ops, f"/api/v1/ops/announcements/{announcement_id}/retry")

    assert answer.status_code == 202
    _wait_until(lambda: _rows(ops.engine, announcement_id)[failed][0] == "sent")
    after = _rows(ops.engine, announcement_id)
    assert after[sent] == before[sent]
    assert after[sending] == before[sending]
    assert [email.to for email in ops.mailer.sent] == [_email(ops.engine, failed)]
    [audit] = _actions(ops, "announcement.retry")
    assert audit["target"] == str(announcement_id)


def test_retry_of_an_unknown_announcement_is_not_found(ops: Harness) -> None:
    assert _post(ops, f"/api/v1/ops/announcements/{uuid.uuid4()}/retry").status_code == 404


# --- privacy of logs and audit rows ------------------------------------------------------------


def test_no_log_line_or_audit_row_holds_an_address_the_subject_or_the_body(
    ops: Harness,
) -> None:
    people = _people(ops.engine, 2)
    addresses = [_email(ops.engine, person) for person in people]
    addresses.append(_email(ops.engine, ops.actor.user_id))
    audience = {"user_ids": people}

    def refuse_first(to: str) -> None:
        if to == addresses[0]:
            raise ConnectionError(to)

    ops.mailer.on_send = refuse_first
    with capture_logs() as logs:
        assert _post(ops, "/api/v1/ops/announcements/test",
                     {**MESSAGE, "kind": "product_update"}).status_code == 204
        answer = _send(ops, audience)
        announcement_id = answer.json()["announcement_id"]
        _wait_until(_settled(ops.engine, announcement_id))
        ops.mailer.on_send = None
        assert _post(ops, f"/api/v1/ops/announcements/{announcement_id}/retry").status_code == 202
        _wait_until(_settled(ops.engine, announcement_id))

    with ops.engine.connect() as conn:
        audit = conn.execute(
            select(ops_action.c.action, ops_action.c.target, ops_action.c.outcome).where(
                ops_action.c.actor_user_id == ops.actor.user_id
            )
        ).all()
    assert {row.action for row in audit} == {
        "announcement.test", "announcement.send", "announcement.retry",
    }
    send_line = next(line for line in logs if line.get("action") == "announcement.send")
    assert (send_line["chosen"], send_line["will_get"]) == (2, 2)
    written = repr(logs) + repr(audit)
    for secret in [*addresses, SUBJECT, "Draw a theory of change", "@"]:
        assert secret not in written


# --- start-up ----------------------------------------------------------------------------------


class _FakeSes:
    """Stands in for the SES client: records each recipient and accepts the email."""

    def __init__(self) -> None:
        self.to: list[str] = []

    def send_email(self, **request: Any) -> dict[str, str]:
        self.to.extend(request["Destination"]["ToAddresses"])
        return {"MessageId": "fake"}

    def list_suppressed_destinations(self, **request: Any) -> dict[str, Any]:
        return {"SuppressedDestinationSummaries": []}


def test_ops_start_up_with_a_mailer_finishes_pending_rows(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import boto3

    people = _people(engine, 2)
    announcement_id = _recorded(engine, people)
    ses = _FakeSes()
    built: list[str] = []

    def client(service: str, **kwargs: Any) -> Any:
        built.append(service)
        return ses

    monkeypatch.setattr(boto3, "client", client)
    settings = replace(
        _settings(tmp_path),
        announcement_from_address=MAIL.from_address,
        announcement_reply_to=MAIL.reply_to,
        public_api_url=MAIL.api_url,
    )
    app = create_app(settings=settings)

    with TestClient(app):
        assert app.state.mailer is not None
        _wait_until(_settled(engine, announcement_id))

    assert built == ["sesv2"]
    assert {s for s, _ in _rows(engine, announcement_id).values()} == {"sent"}
    assert {_email(engine, person) for person in people} <= set(ses.to)
