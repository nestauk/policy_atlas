"""Waitlist signup route tests — public POST /api/v1/waitlist."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.engine import Engine

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


def test_waitlist_duplicate_email_is_already_registered(tmp_path: Path, engine: Engine) -> None:
    """A second signup with the same email is a 409 already_registered."""
    del engine
    email = _email("dup")
    payload = {
        "email": email,
        "name": "First",
        "role_or_reason": "Curious about Policy Atlas",
    }
    with api_client(tmp_path) as (client, _owner, _other):
        first = client.post("/api/v1/waitlist", json=payload)
        assert first.status_code == 201
        second = client.post(
            "/api/v1/waitlist",
            json={**payload, "name": "Second", "organisation": "Somewhere"},
        )
        assert second.status_code == 409
        assert second.json()["error"]["code"] == "already_registered"


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


def test_waitlist_honeypot_fakes_success_and_stores_nothing(
    tmp_path: Path, engine: Engine
) -> None:
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
        # request inserted nothing (a real row would make this a 409).
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
