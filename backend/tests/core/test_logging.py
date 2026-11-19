"""configure_logging must not leak frame locals; Settings must not print the DB URL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import structlog
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from policy_atlas.api.settings import Settings
from policy_atlas.core.db import get_engine
from policy_atlas.core.logging import configure_logging

PLANTED = "planted-secret-value-ab12"


def _fail_with_local() -> None:
    secret = PLANTED
    raise ValueError(f"boom {len(secret)}")


def test_json_traceback_has_no_frame_locals(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Frames are logged without their local variables (review finding H-06)."""
    monkeypatch.setenv("LOG_FORMAT", "json")
    try:
        configure_logging()
        try:
            _fail_with_local()
        except ValueError:
            structlog.get_logger().error("boom", exc_info=True)
        raw = capsys.readouterr().out.strip()
    finally:
        structlog.reset_defaults()
    record = json.loads(raw)
    frames = [f for exc in record["exception"] for f in exc["frames"]]
    assert frames
    assert all("locals" not in f for f in frames)
    assert PLANTED not in raw


def test_settings_repr_hides_database_url() -> None:
    """The database URL (it holds the password) stays out of repr(Settings)."""
    url = "postgresql://user:planted-db-password@host/db"
    settings = Settings("iss", "client", None, Path("jwks.json"), "http://app", url)
    assert url not in repr(settings)
    assert "planted-db-password" not in repr(settings)


def test_db_error_log_hides_bound_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed query's bound values (user text) stay out of the error log."""
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("LOG_FORMAT", "json")
    try:
        configure_logging()
        try:
            with get_engine().connect() as conn:
                conn.execute(text("select * from no_such_table where q = :q"), {"q": PLANTED})
        except DBAPIError:
            structlog.get_logger().error("boom", exc_info=True)
        raw = capsys.readouterr().out.strip()
    finally:
        structlog.reset_defaults()
    assert "no_such_table" in raw
    assert PLANTED not in raw
