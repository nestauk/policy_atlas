"""Environment-backed configuration for the Policy Atlas API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated process configuration for the API application.

    Args:
        oidc_issuer: Expected OIDC token issuer.
        oidc_client_id: Expected OIDC client identifier.
        oidc_jwks_url: Remote issuer JWKS URL, used by Cognito-shaped deployments.
        oidc_jwks_path: Local JWKS path, used only by the development issuer.
        app_origin: Sole browser origin allowed by CORS.
        database_url: SQLAlchemy database URL.
        run_executor_max: Maximum number of concurrent walk workers.
        jwks_cache_ttl_seconds: Duration for which a fetched JWKS is retained.
        sse_poll_interval_seconds: Durable-tail poll cadence for SSE clients.
        sse_heartbeat_seconds: Idle interval before an SSE keep-alive comment.
        db_pool_size: SQLAlchemy engine connection pool size.
        db_max_overflow: SQLAlchemy engine pool overflow above ``db_pool_size``.
    """

    oidc_issuer: str
    oidc_client_id: str
    oidc_jwks_url: str | None
    oidc_jwks_path: Path | None
    app_origin: str
    database_url: str
    run_executor_max: int = 2
    jwks_cache_ttl_seconds: int = 300
    sse_poll_interval_seconds: float = 0.4
    sse_heartbeat_seconds: float = 15.0
    db_pool_size: int = 5
    db_max_overflow: int = 10


def load_settings() -> Settings:
    """Load and validate API configuration from the environment.

    Returns:
        A frozen, validated application settings object.

    Raises:
        RuntimeError: If required configuration is absent or mutually exclusive
            JWKS configuration is invalid.
    """
    # Pure os.environ by design: the DEV entry point loads backend/.env via
    # `uv run --env-file` (backend Makefile `dev` target). Loading .env here
    # would leak a developer's live keys into every test process that builds
    # an app (live-check finding, 2026-07-21: it flipped the CLI pin test
    # into live mode under socket-deny).
    issuer = _required("OIDC_ISSUER")
    client_id = _required("OIDC_CLIENT_ID")
    app_origin = _required("APP_ORIGIN")
    database_url = _required("DATABASE_URL")
    jwks_url = _optional("OIDC_JWKS_URL")
    jwks_path_value = _optional("OIDC_JWKS_PATH")
    if (jwks_url is None) == (jwks_path_value is None):
        raise RuntimeError("set exactly one of OIDC_JWKS_URL or OIDC_JWKS_PATH")
    # https only: the JWKS is the verifier's trust root — fetching it over
    # cleartext would let an on-path attacker mint accepted tokens. Local dev
    # uses OIDC_JWKS_PATH, never a plain-http URL.
    if jwks_url is not None and not jwks_url.startswith("https://"):
        raise RuntimeError("OIDC_JWKS_URL must be an HTTPS URL")

    jwks_path = Path(jwks_path_value) if jwks_path_value is not None else None
    if jwks_path is not None and not jwks_path.is_file():
        raise RuntimeError("OIDC_JWKS_PATH must name an existing JWKS file")

    return Settings(
        oidc_issuer=issuer,
        oidc_client_id=client_id,
        oidc_jwks_url=jwks_url,
        oidc_jwks_path=jwks_path,
        app_origin=app_origin,
        database_url=database_url,
        run_executor_max=_positive_int("RUN_EXECUTOR_MAX", default=2),
        jwks_cache_ttl_seconds=_positive_int("OIDC_JWKS_CACHE_TTL_SECONDS", default=300),
        sse_poll_interval_seconds=_positive_float("SSE_POLL_INTERVAL_SECONDS", default=0.4),
        sse_heartbeat_seconds=_positive_float("SSE_HEARTBEAT_SECONDS", default=15.0),
        db_pool_size=_positive_int("DB_POOL_SIZE", default=5),
        db_max_overflow=_nonnegative_int("DB_MAX_OVERFLOW", default=10),
    )


def _required(name: str) -> str:
    """Return a non-blank environment value or raise a startup error."""
    value = _optional(name)
    if value is None:
        raise RuntimeError(f"{name} environment variable is required")
    return value


def _optional(name: str) -> str | None:
    """Return a stripped environment value, treating blanks as absent."""
    value = os.environ.get(name)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _positive_int(name: str, *, default: int) -> int:
    """Load a positive integer environment value with a safe default."""
    value = _optional(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive integer") from exc
    if parsed < 1:
        raise RuntimeError(f"{name} must be a positive integer")
    return parsed


def _nonnegative_int(name: str, *, default: int) -> int:
    """Load a non-negative integer environment value with a safe default."""
    value = _optional(name)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a non-negative integer") from exc
    if parsed < 0:
        raise RuntimeError(f"{name} must be a non-negative integer")
    return parsed


def _positive_float(name: str, *, default: float) -> float:
    """Load a positive finite floating-point environment value."""
    value = _optional(name)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be a positive number") from exc
    if not isfinite(parsed) or parsed <= 0:
        raise RuntimeError(f"{name} must be a positive number")
    return parsed
