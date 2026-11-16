"""configure_logging must not leak frame locals; Settings must not print the DB URL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import structlog

from policy_atlas.api.settings import Settings
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
