"""Waitlist signup route tests — public POST /api/v1/waitlist."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import event, insert, select, update
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.core.invite_code import new_code
from policy_atlas.core.schema import invite_link, organisation_domain, waitlist_entry
from tests.api.org_support import make_org, seeded
from tests.api.resource_support import api_client


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


def test_waitlist_signup_creates_entry_without_auth(tmp_path: Path, engine: Engine) -> None:
    """Unauthenticated POST creates a row and returns the acknowledgement."""
    del engine
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.post(
            "/api/v1/waitlist",
            json={
                "email": _email("ada"),
                "name": "Ada Lovelace",
                "organisation": "Analytical Engine Office",
                "role_or_reason": "Policy analyst exploring evidence synthesis",
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert set(body) == {"entry_id", "email", "created_at"}
        assert body["email"].startswith("ada-")
        assert "organisation" not in body
        assert "role_or_reason" not in body


def test_waitlist_response_is_identical_for_listed_and_unlisted_domains(
    tmp_path: Path, engine: Engine
) -> None:
    """The public acknowledgement reveals no self-signup domain decision."""
    with seeded(engine) as conn:
        existing = conn.execute(
            select(organisation_domain.c.domain).where(
                organisation_domain.c.domain == "nesta.org.uk"
            )
        ).scalar_one_or_none()
        if existing is None:
            org_id = make_org(conn, name="Listed domain")
            conn.execute(
                organisation_domain.insert().values(
                    domain="nesta.org.uk", org_id=org_id, created_at=datetime.now(UTC)
                )
            )
    listed_email = f"listed-{uuid.uuid4().hex[:12]}@nesta.org.uk"
    unlisted_email = f"unlisted-{uuid.uuid4().hex[:12]}@example.test"
    payload = {"name": "Public Person", "role_or_reason": "Testing acknowledgement"}
    with api_client(tmp_path) as (client, _owner, _other):
        listed = client.post("/api/v1/waitlist", json={**payload, "email": listed_email})
        unlisted = client.post("/api/v1/waitlist", json={**payload, "email": unlisted_email})
    assert listed.status_code == unlisted.status_code == 201
    assert set(listed.json()) == set(unlisted.json()) == {"entry_id", "email", "created_at"}
    assert listed.json()["email"] == listed_email
    assert unlisted.json()["email"] == unlisted_email
    assert {key: value for key, value in listed.headers.items() if key != "content-length"} == {
        key: value for key, value in unlisted.headers.items() if key != "content-length"
    }


def test_waitlist_duplicate_email_gets_same_201_and_one_row(tmp_path: Path, engine: Engine) -> None:
    """A repeat signup is a 201 too and writes nothing (no registration oracle).

    The second 201 also shows the request transaction was not aborted. Row
    count is read through a fresh connection.
    """
    email = _email("dup")
    payload = {
        "email": email,
        "name": "First",
        "role_or_reason": "Curious about Policy Atlas",
    }
    with api_client(tmp_path) as (client, _owner, _other):
        first = client.post("/api/v1/waitlist", json=payload)
        second = client.post(
            "/api/v1/waitlist",
            json={**payload, "name": "Second", "organisation": "Somewhere"},
        )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    with engine.connect() as check:
        rows = check.execute(
            select(waitlist_entry.c.name).where(waitlist_entry.c.email == email)
        ).all()
    assert [r.name for r in rows] == ["First"]


def test_waitlist_rejects_invalid_email(tmp_path: Path, engine: Engine) -> None:
    """Malformed email is a 422 validation_error."""
    del engine
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.post(
            "/api/v1/waitlist",
            json={
                "email": "not-an-email",
                "name": "No At Sign",
                "role_or_reason": "Testing",
            },
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"


def test_waitlist_honeypot_fakes_success_and_stores_nothing(tmp_path: Path, engine: Engine) -> None:
    """A filled `website` honeypot gets a 201 but no row is created."""
    email = _email("bot")
    with api_client(tmp_path) as (client, _owner, _other):
        trapped = client.post(
            "/api/v1/waitlist",
            json={
                "email": email,
                "name": "Definitely Human",
                "role_or_reason": "Spam",
                "website": "https://spam.example",
            },
        )
        assert trapped.status_code == 201, trapped.text
        # A duplicate is a 201 too since task 064a (Q2), so the follow-up
        # signup no longer proves anything on its own: the row's name does.
        real = client.post(
            "/api/v1/waitlist",
            json={"email": email, "name": "Real Person", "role_or_reason": "Research"},
        )
        assert real.status_code == 201, real.text
    with engine.connect() as check:
        rows = check.execute(
            select(waitlist_entry.c.name).where(waitlist_entry.c.email == email)
        ).all()
    assert [r.name for r in rows] == ["Real Person"]


def test_waitlist_organisation_optional(tmp_path: Path, engine: Engine) -> None:
    """Organisation may be omitted; blank string becomes null."""
    del engine
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.post(
            "/api/v1/waitlist",
            json={
                "email": _email("orgless"),
                "name": "Solo Researcher",
                "organisation": "  ",
                "role_or_reason": "Independent research",
            },
        )
        assert response.status_code == 201, response.text


# --- invite codes ---------------------------------------------------------------


def _live_link_code(engine: Engine) -> str:
    """Commit one active invite link and return its code in the stored form."""
    code = new_code()
    with seeded(engine) as conn:
        conn.execute(insert(invite_link).values(
            invite_link_id=uuid.uuid4(), code=code, label="Pilot", org_id=make_org(conn),
            allowed_domains=["example.com"], max_uses=5,
            expires_at=datetime.now(UTC) + timedelta(days=7), created_at=datetime.now(UTC),
            created_by="operator",
        ))
    return code


def _stored_code(engine: Engine, email: str) -> str | None:
    with engine.connect() as check:
        code: str | None = check.execute(
            select(waitlist_entry.c.invite_code).where(waitlist_entry.c.email == email)
        ).scalar_one()
    return code


def test_waitlist_answer_is_the_same_for_every_invite_code(
    tmp_path: Path, engine: Engine
) -> None:
    """Good, malformed, unknown and no code: same status, fields and headers; no log line."""
    good = _live_link_code(engine)
    codes = {"good": f"{good[:4]}-{good[4:8]}-{good[8:]}", "malformed": "not a code",
             "unknown": new_code(), "none": None}
    answers = {}
    with api_client(tmp_path) as (client, _owner, _other), capture_logs() as captured:
        for kind, code in codes.items():
            answers[kind] = client.post("/api/v1/waitlist", json={
                "email": _email(kind[:4]), "name": "Coded Person",
                "role_or_reason": "Pilot", "invite_code": code})
        too_long = client.post("/api/v1/waitlist", json={
            "email": _email("long"), "name": "Long", "role_or_reason": "Pilot",
            "invite_code": "A" * 65})
    assert {kind: response.status_code for kind, response in answers.items()} == dict.fromkeys(
        codes, 201)
    assert {kind: tuple(response.json()) for kind, response in answers.items()} == dict.fromkeys(
        codes, ("entry_id", "email", "created_at"))
    headers = [
        {key: value for key, value in response.headers.items() if key != "content-length"}
        for response in answers.values()
    ]
    assert all(other == headers[0] for other in headers)
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "validation_error"
    assert good not in str(list(captured)) and good[:4] + "-" not in str(list(captured))


def test_a_waiting_request_takes_a_new_code_and_a_decided_one_does_not(
    tmp_path: Path, engine: Engine
) -> None:
    first, second = new_code(), new_code()
    waiting, stamped, rejected = _email("wait"), _email("stamp"), _email("reject")
    payload = {"name": "Coded Person", "role_or_reason": "Pilot"}
    with api_client(tmp_path) as (client, _owner, _other):
        for email in (waiting, stamped, rejected):
            client.post("/api/v1/waitlist", json={**payload, "email": email,
                                                   "invite_code": first})
        with seeded(engine) as conn:
            conn.execute(update(waitlist_entry).where(waitlist_entry.c.email == stamped)
                         .values(account_user_id="someone", account_created_at=datetime.now(UTC)))
            conn.execute(update(waitlist_entry).where(waitlist_entry.c.email == rejected)
                         .values(rejected_at=datetime.now(UTC)))
        for email in (waiting, stamped, rejected):
            client.post("/api/v1/waitlist", json={**payload, "email": email,
                                                   "invite_code": second.lower()})
        assert _stored_code(engine, waiting) == second
        for code in (None, "not a code"):
            client.post("/api/v1/waitlist", json={**payload, "email": waiting,
                                                   "invite_code": code})
    assert _stored_code(engine, waiting) == second
    assert _stored_code(engine, stamped) == _stored_code(engine, rejected) == first


def test_the_public_route_never_reads_invite_links(tmp_path: Path, engine: Engine) -> None:
    """No statement the request runs names the invite-link table."""
    good = _live_link_code(engine)
    statements: list[str] = []

    def record(_conn: Any, _cursor: Any, statement: str, *_args: Any) -> None:
        statements.append(statement)

    event.listen(Engine, "before_cursor_execute", record)
    try:
        with api_client(tmp_path) as (client, _owner, _other):
            response = client.post("/api/v1/waitlist", json={
                "email": _email("read"), "name": "Reader", "role_or_reason": "Pilot",
                "invite_code": good})
    finally:
        event.remove(Engine, "before_cursor_execute", record)
    assert response.status_code == 201, response.text
    assert any("waitlist_entry" in statement for statement in statements)
    assert not any("invite_link" in statement for statement in statements)
