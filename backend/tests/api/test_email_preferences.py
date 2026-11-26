"""Public unsubscribe and resubscribe routes, and the token kept out of the logs."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from uvicorn.logging import AccessFormatter

from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init
from policy_atlas.api.settings import Settings
from policy_atlas.core.logging import drop_token_from_access_log
from policy_atlas.core.schema import app_user
from tests.api.org_support import make_user, seeded
from tests.api.resource_support import api_client
from tests.helpers import now

_ACCESS_FORMAT = '%s - "%s %s HTTP/%s" %d'


@pytest.fixture
def person(engine: Engine) -> tuple[str, str]:
    """Commit one account and return its user id and unsubscribe token."""
    with seeded(engine) as conn:
        user_id = make_user(conn)
        token = conn.execute(
            select(app_user.c.unsubscribe_token).where(app_user.c.user_id == user_id)
        ).scalar_one()
    return user_id, str(token)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        "http://dev-issuer.local",
        "email-preferences-test",
        None,
        init(tmp_path / "issuer"),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )


def _mark(engine: Engine, user_id: str) -> datetime | None:
    with engine.connect() as conn:
        mark: datetime | None = conn.execute(
            select(app_user.c.updates_unsubscribed_at).where(app_user.c.user_id == user_id)
        ).scalar_one()
    return mark


def test_unsubscribe_sets_the_mark_and_a_repeat_keeps_the_first_time(
    tmp_path: Path, engine: Engine, person: tuple[str, str]
) -> None:
    user_id, token = person
    with api_client(tmp_path) as (client, _owner, _other):
        first = client.post(f"/api/v1/unsubscribe?token={token}")
        marked = _mark(engine, user_id)
        second = client.post(f"/api/v1/unsubscribe?token={token}")
    assert first.status_code == second.status_code == 204
    assert first.content == second.content == b""
    assert marked is not None
    assert _mark(engine, user_id) == marked


def test_resubscribe_clears_the_mark_and_a_repeat_answers_204(
    tmp_path: Path, engine: Engine, person: tuple[str, str]
) -> None:
    user_id, token = person
    with api_client(tmp_path) as (client, _owner, _other):
        assert client.post(f"/api/v1/unsubscribe?token={token}").status_code == 204
        first = client.post(f"/api/v1/resubscribe?token={token}")
        second = client.post(f"/api/v1/resubscribe?token={token}")
    assert first.status_code == second.status_code == 204
    assert _mark(engine, user_id) is None


def test_a_deactivated_accounts_token_still_works(
    tmp_path: Path, engine: Engine, person: tuple[str, str]
) -> None:
    user_id, token = person
    with seeded(engine) as conn:
        conn.execute(
            update(app_user).where(app_user.c.user_id == user_id).values(deactivated_at=now())
        )
    with api_client(tmp_path) as (client, _owner, _other):
        assert client.post(f"/api/v1/unsubscribe?token={token}").status_code == 204
    assert _mark(engine, user_id) is not None


_UNKNOWN = "00000000-0000-4000-8000-000000000000"


@pytest.mark.parametrize("query", [f"?token={_UNKNOWN}", "", "?token=not-a-uuid"])
@pytest.mark.parametrize("path", ["/api/v1/unsubscribe", "/api/v1/resubscribe"])
def test_unknown_missing_or_badly_formed_token_answers_404_and_changes_nothing(
    tmp_path: Path, engine: Engine, person: tuple[str, str], path: str, query: str
) -> None:
    user_id, _token = person
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.post(f"{path}{query}")
    assert response.status_code == 404
    assert _mark(engine, user_id) is None


@pytest.mark.parametrize("path", ["/api/v1/unsubscribe", "/api/v1/resubscribe"])
def test_a_get_changes_nothing(
    tmp_path: Path, engine: Engine, person: tuple[str, str], path: str
) -> None:
    user_id, token = person
    with seeded(engine) as conn:
        conn.execute(
            update(app_user)
            .where(app_user.c.user_id == user_id)
            .values(updates_unsubscribed_at=now())
        )
    before = _mark(engine, user_id)
    with api_client(tmp_path) as (client, _owner, _other):
        response = client.get(f"{path}?token={token}", follow_redirects=False)
    assert not 200 <= response.status_code < 400
    assert _mark(engine, user_id) == before


@pytest.mark.parametrize(
    "body",
    [
        {
            "content": b"List-Unsubscribe=One-Click",
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        },
        {"content": b""},
        {"json": {"anything": ["at", "all"]}},
    ],
    ids=["mail-provider-form", "empty", "json"],
)
def test_a_post_with_no_cookie_origin_or_sign_in_answers_204_without_redirect(
    tmp_path: Path, engine: Engine, person: tuple[str, str], body: dict[str, Any]
) -> None:
    user_id, token = person
    with api_client(tmp_path) as (client, _owner, _other):
        client.cookies.clear()
        response = client.post(f"/api/v1/unsubscribe?token={token}", follow_redirects=False, **body)
    assert response.status_code == 204
    assert _mark(engine, user_id) is not None


def _access_line(path_with_query: str) -> str:
    """Format a uvicorn access record the way the server does, filters applied."""
    logger = logging.getLogger("uvicorn.access")
    record = logger.makeRecord(
        logger.name,
        logging.INFO,
        __file__,
        0,
        _ACCESS_FORMAT,
        ("203.0.113.9:5000", "POST", path_with_query, "1.1", 204),
        None,
    )
    assert logger.filter(record)
    return AccessFormatter("%(message)s", use_colors=False).format(record)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/unsubscribe",
        "/api/v1/resubscribe",
        "/api/v1//unsubscribe",
        "/API/V1/Unsubscribe",
        "/api/v1/resubscribe//",
        "/api/v1/%75nsubscribe",
    ],
)
def test_access_log_line_holds_no_token(tmp_path: Path, path: str) -> None:
    create_app(settings=_settings(tmp_path))
    token = str(uuid.uuid4())
    line = _access_line(f"{path}?token={token}")
    assert token not in line
    assert path in line


def test_access_log_leaves_other_lines_unchanged(tmp_path: Path) -> None:
    create_app(settings=_settings(tmp_path))
    line = _access_line("/api/v1/tasks?page=2&page_size=5")
    assert line == '203.0.113.9:5000 - "POST /api/v1/tasks?page=2&page_size=5 HTTP/1.1" 204'


def test_building_the_app_twice_installs_one_access_log_filter(tmp_path: Path) -> None:
    create_app(settings=_settings(tmp_path))
    create_app(settings=_settings(tmp_path))
    filters = logging.getLogger("uvicorn.access").filters
    assert filters.count(drop_token_from_access_log) == 1


def test_request_log_line_holds_no_token(
    tmp_path: Path, person: tuple[str, str], capsys: pytest.CaptureFixture[str]
) -> None:
    user_id, token = person
    with api_client(tmp_path) as (client, _owner, _other):
        capsys.readouterr()
        assert client.post(f"/api/v1/unsubscribe?token={token}").status_code == 204
    out = capsys.readouterr().out
    assert "email_preferences.changed" in out
    assert "unsubscribed" in out
    assert user_id in out
    assert token not in out
