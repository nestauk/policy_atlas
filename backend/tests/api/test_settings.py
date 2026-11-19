"""Environment-parsing tests for `policy_atlas.api.settings` (pin 9, task 026 C.3).

The DB pool settings (`db_pool_size`/`db_max_overflow`) are parsed here; their
threading into the lifespan's `create_engine` call is covered by the last test
in this file, which drives the real lifespan through `TestClient`.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as real_create_engine
from sqlalchemy.engine import Engine

import policy_atlas.api.app as app_module
from policy_atlas.api.app import create_app
from policy_atlas.api.dev_issuer import init
from policy_atlas.api.settings import Settings, load_settings


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set the minimum environment `load_settings` needs to succeed."""
    monkeypatch.setenv("OIDC_ISSUER", "http://dev-issuer.local")
    monkeypatch.setenv("OIDC_CLIENT_ID", "settings-test")
    monkeypatch.setenv("APP_ORIGIN", "http://app.example.test")
    monkeypatch.setenv("DATABASE_URL", os.environ["DATABASE_URL"])
    monkeypatch.setenv("OIDC_JWKS_URL", "https://dev-issuer.local/jwks")
    monkeypatch.delenv("OIDC_JWKS_PATH", raising=False)


def test_db_pool_settings_default_to_five_and_ten(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absent `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` fall back to the documented defaults."""
    _set_required_env(monkeypatch)
    monkeypatch.delenv("DB_POOL_SIZE", raising=False)
    monkeypatch.delenv("DB_MAX_OVERFLOW", raising=False)

    settings = load_settings()

    assert settings.db_pool_size == 5
    assert settings.db_max_overflow == 10


def test_db_pool_settings_honor_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DB_POOL_SIZE`/`DB_MAX_OVERFLOW` override the defaults when set."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DB_POOL_SIZE", "15")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "10")

    settings = load_settings()

    assert settings.db_pool_size == 15
    assert settings.db_max_overflow == 10


@pytest.mark.parametrize(("value", "enabled"), [(None, False), ("0", False), ("1", True)])
def test_the_theory_of_change_setting_is_on_only_for_1(
    monkeypatch: pytest.MonkeyPatch, value: str | None, enabled: bool
) -> None:
    """`POLICY_ATLAS_THEORY_OF_CHANGE` (task 054, C15): off unless exactly `1`."""
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("POLICY_ATLAS_THEORY_OF_CHANGE", raising=False)
    else:
        monkeypatch.setenv("POLICY_ATLAS_THEORY_OF_CHANGE", value)

    assert load_settings().theory_of_change_enabled is enabled


@pytest.mark.parametrize(
    ("value", "elements"),
    [
        (None, frozenset()),
        ("", frozenset()),
        ("citation_flag", frozenset({"citation_flag"})),
        (" onboarding , problem_report,", frozenset({"onboarding", "problem_report"})),
    ],
)
def test_the_feedback_setting_is_a_list_of_element_names(
    monkeypatch: pytest.MonkeyPatch, value: str | None, elements: frozenset[str]
) -> None:
    """`POLICY_ATLAS_FEEDBACK`: every element is off unless the list names it."""
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("POLICY_ATLAS_FEEDBACK", raising=False)
    else:
        monkeypatch.setenv("POLICY_ATLAS_FEEDBACK", value)

    assert load_settings().feedback_elements == elements


def test_an_unknown_feedback_element_fails_at_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    """A spelling mistake must not leave an element silently off."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("POLICY_ATLAS_FEEDBACK", "citation_flag,thumbs")

    with pytest.raises(RuntimeError, match="unknown elements \\['thumbs'\\]"):
        load_settings()


@pytest.mark.parametrize(("value", "version"), [(None, None), ("", None), ("v3.2.0", "v3.2.0")])
def test_the_version_setting_is_optional(
    monkeypatch: pytest.MonkeyPatch, value: str | None, version: str | None
) -> None:
    """`POLICY_ATLAS_VERSION` is stored on feedback events; blank means unknown."""
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("POLICY_ATLAS_VERSION", raising=False)
    else:
        monkeypatch.setenv("POLICY_ATLAS_VERSION", value)

    assert load_settings().pa_version == version


def test_db_pool_size_zero_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DB_POOL_SIZE` must be a positive integer — a zero-sized pool is nonsensical."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DB_POOL_SIZE", "0")

    with pytest.raises(RuntimeError, match="DB_POOL_SIZE must be a positive integer"):
        load_settings()


def test_db_max_overflow_zero_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DB_MAX_OVERFLOW=0` disables overflow but is a valid, documented value."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")

    settings = load_settings()

    assert settings.db_max_overflow == 0


def test_db_max_overflow_negative_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """`DB_MAX_OVERFLOW` rejects negative values via the non-negative helper."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("DB_MAX_OVERFLOW", "-1")

    with pytest.raises(RuntimeError, match="DB_MAX_OVERFLOW must be a non-negative integer"):
        load_settings()


def test_lifespan_threads_pool_settings_into_create_engine(
    engine: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The lifespan passes `db_pool_size`/`db_max_overflow` through to `create_engine`."""
    del engine  # forces the session migration to head before this test runs
    captured: dict[str, object] = {}

    def _spy_create_engine(url: str, **kwargs: object) -> Engine:
        captured["kwargs"] = kwargs
        return real_create_engine(url, **kwargs)

    monkeypatch.setattr(app_module, "create_engine", _spy_create_engine)

    settings = Settings(
        "http://dev-issuer.local",
        "lifespan-pool-test",
        None,
        init(tmp_path / "issuer"),
        "http://app.example.test",
        os.environ["DATABASE_URL"],
        db_pool_size=7,
        db_max_overflow=3,
    )
    app = create_app(settings=settings)
    with TestClient(app):
        pass

    kwargs = captured["kwargs"]
    assert kwargs == {"pool_pre_ping": True, "pool_size": 7, "max_overflow": 3}
