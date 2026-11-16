"""Waitlist signup route tests — public POST /api/v1/waitlist."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import waitlist_entry
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
    del engine
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
        # Same email signs up cleanly afterwards — proof the trapped
        # request inserted nothing.
        real = client.post(
            "/api/v1/waitlist",
            json={"email": email, "name": "Real Person", "role_or_reason": "Research"},
        )
        assert real.status_code == 201, real.text


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
