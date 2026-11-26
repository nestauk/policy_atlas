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
    monkeypatch.setenv("PUBLIC_APP_ORIGIN", "https://app.example.test")


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


@pytest.mark.parametrize(
    ("value", "expected"), [(None, "api"), ("api", "api"), ("ops", "ops")]
)
def test_service_role_defaults_to_api_and_accepts_ops(
    monkeypatch: pytest.MonkeyPatch, value: str | None, expected: str
) -> None:
    """The service role is API by default and accepts the isolated ops process."""
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("POLICY_ATLAS_SERVICE_ROLE", raising=False)
    else:
        monkeypatch.setenv("POLICY_ATLAS_SERVICE_ROLE", value)

    assert load_settings().service_role == expected


def test_service_role_rejects_unknown_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """A typo cannot accidentally create a process with an unclear route table."""
    _set_required_env(monkeypatch)
    monkeypatch.setenv("POLICY_ATLAS_SERVICE_ROLE", "worker")

    with pytest.raises(RuntimeError, match="POLICY_ATLAS_SERVICE_ROLE must be api or ops"):
        load_settings()


@pytest.mark.parametrize(("value", "enabled"), [(None, False), ("0", False), ("1", True)])
def test_self_signup_is_enabled_only_for_one(
    monkeypatch: pytest.MonkeyPatch, value: str | None, enabled: bool
) -> None:
    """The self-signup sweep stays off unless explicitly enabled with `1`."""
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("POLICY_ATLAS_SELF_SIGNUP", raising=False)
    else:
        monkeypatch.setenv("POLICY_ATLAS_SELF_SIGNUP", value)

    assert load_settings().self_signup_enabled is enabled


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ("https://v3.policyatlas.uk", True),
        ("http://localhost:5173", True),
        ("http://127.0.0.1:8003", True),
        (None, False),
        ("http://v3.policyatlas.uk", False),
        ("https://v3.policyatlas.uk/", False),
        ("https://v3.policyatlas.uk/app", False),
        ("https://v3.policyatlas.uk?x=1", False),
        ("https://v3.policyatlas.uk#top", False),
        ("https://user@v3.policyatlas.uk", False),
    ],
)
def test_ops_mode_requires_a_public_app_origin_and_the_api_ignores_it(
    monkeypatch: pytest.MonkeyPatch, value: str | None, accepted: bool
) -> None:
    _set_required_env(monkeypatch)
    if value is None:
        monkeypatch.delenv("PUBLIC_APP_ORIGIN", raising=False)
    else:
        monkeypatch.setenv("PUBLIC_APP_ORIGIN", value)
    monkeypatch.setenv("POLICY_ATLAS_SERVICE_ROLE", "api")
    assert load_settings().public_app_origin is None
    monkeypatch.setenv("POLICY_ATLAS_SERVICE_ROLE", "ops")
    if accepted:
        assert load_settings().public_app_origin == value
    else:
        with pytest.raises(RuntimeError, match="PUBLIC_APP_ORIGIN"):
            load_settings()


def test_self_signup_cap_and_ops_ui_directory_parse(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The sweep cap and operations bundle directory are configurable."""
    _set_required_env(monkeypatch)
    ops_ui_dir = tmp_path / "ops-ui"
    monkeypatch.setenv("POLICY_ATLAS_SELF_SIGNUP_MAX_PER_HOUR", "7")
    monkeypatch.setenv("OPS_UI_DIR", str(ops_ui_dir))

    settings = load_settings()

    assert settings.self_signup_max_per_hour == 7
    assert settings.ops_ui_dir == ops_ui_dir


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
    assert kwargs == {
        "pool_pre_ping": True,
        "hide_parameters": True,
        "pool_size": 7,
        "max_overflow": 3,
    }
