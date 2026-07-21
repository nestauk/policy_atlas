"""Provider-neutral conformance tests for the API OIDC auth boundary."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, cast

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from policy_atlas.api.app import create_app
from policy_atlas.api.auth import AuthenticatedUser, get_current_user
from policy_atlas.api.dev_issuer import init, mint_token
from policy_atlas.api.settings import Settings


@pytest.fixture
def issuer_a(tmp_path: Path) -> tuple[Path, Settings]:
    """Create the first file-backed development issuer configuration."""
    key_dir = tmp_path / "issuer-a"
    return key_dir, _settings("http://dev-issuer-a.local", "audience-a", init(key_dir, kid="a-1"))


@pytest.fixture
def issuer_b(tmp_path: Path) -> tuple[Path, Settings]:
    """Create the second, intentionally incompatible development issuer."""
    key_dir = tmp_path / "issuer-b"
    return key_dir, _settings("http://dev-issuer-b.local", "audience-b", init(key_dir, kid="b-1"))


def test_provider_conformance(
    engine: Engine,
    issuer_a: tuple[Path, Settings],
    issuer_b: tuple[Path, Settings],
) -> None:
    """Accept only an unexpired RS256 token from the configured issuer and audience."""
    del engine
    key_dir_a, settings_a = issuer_a
    key_dir_b, settings_b = issuer_b
    valid = mint_token(
        "user-a", settings_a.oidc_issuer, settings_a.oidc_audience, 60, key_dir_a, kid="a-1"
    )
    invalid_tokens = (
        _signed_token(key_dir_a, "a-1", settings_a.oidc_issuer, settings_a.oidc_audience, -1),
        mint_token("user-a", settings_a.oidc_issuer, "other", 60, key_dir_a, kid="a-1"),
        mint_token(
            "user-a",
            "http://dev-issuer-other.local",
            settings_a.oidc_audience,
            60,
            key_dir_a,
            kid="a-1",
        ),
        mint_token(
            "user-b",
            settings_b.oidc_issuer,
            settings_b.oidc_audience,
            60,
            key_dir_b,
            kid="b-1",
        ),
        _hs256_token(key_dir_a, "a-1", settings_a.oidc_issuer, settings_a.oidc_audience),
        jwt.encode(
            _claims(settings_a.oidc_issuer, settings_a.oidc_audience, 60),
            key="",
            algorithm="none",
            headers={"kid": "a-1"},
        ),
    )

    with _client(settings_a) as client:
        assert client.get("/probe", headers=_authorization(valid)).json() == {"user_id": "user-a"}
        for token in invalid_tokens:
            _assert_unauthenticated(client.get("/probe", headers=_authorization(token)))


def test_key_rotation_refreshes_file_jwks(engine: Engine, issuer_a: tuple[Path, Settings]) -> None:
    """Verify both active kids, then reject a retired kid after a cache refresh."""
    del engine
    key_dir, settings = issuer_a
    init(key_dir, kid="a-2")
    token_a1 = mint_token(
        "user-a", settings.oidc_issuer, settings.oidc_audience, 60, key_dir, kid="a-1"
    )
    token_a2 = mint_token(
        "user-a", settings.oidc_issuer, settings.oidc_audience, 60, key_dir, kid="a-2"
    )
    with _client(settings) as client:
        assert client.get("/probe", headers=_authorization(token_a1)).status_code == 200
        assert client.get("/probe", headers=_authorization(token_a2)).status_code == 200
        _remove_kid(settings.oidc_jwks_path, "a-1")
        app = cast(FastAPI, client.app)
        app.state.authenticator.jwks.refresh()
        _assert_unauthenticated(client.get("/probe", headers=_authorization(token_a1)))
        assert client.get("/probe", headers=_authorization(token_a2)).status_code == 200


def test_missing_and_malformed_authorization_are_unauthenticated(
    engine: Engine, issuer_a: tuple[Path, Settings]
) -> None:
    """Keep malformed bearer input indistinguishable from a missing token."""
    del engine
    _, settings = issuer_a
    with _client(settings) as client:
        _assert_unauthenticated(client.get("/probe"))
        _assert_unauthenticated(client.get("/probe", headers={"Authorization": "Basic abc"}))
        _assert_unauthenticated(client.get("/probe", headers={"Authorization": "Bearer"}))


@contextmanager
def _client(settings: Settings) -> Iterator[TestClient]:
    """Run an authenticated probe app with its lifespan active."""
    router = APIRouter()

    @router.get("/probe")
    def probe(user: Annotated[AuthenticatedUser, Depends(get_current_user)]) -> dict[str, str]:
        """Expose the authenticated subject for provider conformance assertions."""
        return {"user_id": user.user_id}

    with TestClient(create_app(settings=settings, routers=(router,))) as client:
        yield client


def _settings(issuer: str, audience: str, jwks_path: Path) -> Settings:
    """Build an explicit test configuration without remote JWKS access."""
    return Settings(
        issuer,
        audience,
        None,
        jwks_path,
        "http://app.example.test",
        os.environ["DATABASE_URL"],
    )


def _authorization(token: str) -> dict[str, str]:
    """Return one bearer authorization header."""
    return {"Authorization": f"Bearer {token}"}


def _assert_unauthenticated(response: Any) -> None:
    """Assert a 401 uses the contract envelope and bearer challenge."""
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthenticated"
    assert set(response.json()) == {"error"}


def _signed_token(key_dir: Path, kid: str, issuer: str, audience: str, ttl: int) -> str:
    """Sign claims with an arbitrary expiry offset for conformance cases."""
    private_key = cast(
        rsa.RSAPrivateKey,
        serialization.load_pem_private_key((key_dir / f"{kid}.pem").read_bytes(), None),
    )
    return jwt.encode(
        _claims(issuer, audience, ttl), private_key, algorithm="RS256", headers={"kid": kid}
    )


def _hs256_token(key_dir: Path, kid: str, issuer: str, audience: str) -> str:
    """Forge the classic public-key-as-HMAC-secret token without PyJWT safeguards."""
    private_key = cast(
        rsa.RSAPrivateKey,
        serialization.load_pem_private_key((key_dir / f"{kid}.pem").read_bytes(), None),
    )
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    header = _base64url_json({"alg": "HS256", "kid": kid, "typ": "JWT"})
    payload = _base64url_json(_claims(issuer, audience, 60))
    signature = hmac.new(public_key, f"{header}.{payload}".encode(), hashlib.sha256).digest()
    return f"{header}.{payload}.{_base64url(signature)}"


def _claims(issuer: str, audience: str, ttl: int) -> dict[str, object]:
    """Return standard claims for a near-term token."""
    now = int(time.time())
    return {"sub": "user-a", "iss": issuer, "aud": audience, "iat": now, "exp": now + ttl}


def _remove_kid(jwks_path: Path | None, kid: str) -> None:
    """Remove a key from the development JWKS to model key retirement."""
    assert jwks_path is not None
    payload = json.loads(jwks_path.read_text(encoding="utf-8"))
    payload["keys"] = [key for key in payload["keys"] if key["kid"] != kid]
    jwks_path.write_text(json.dumps(payload), encoding="utf-8")


def _base64url_json(value: dict[str, object]) -> str:
    """Encode a compact JWT header or payload segment."""
    return _base64url(json.dumps(value, separators=(",", ":")).encode())


def _base64url(value: bytes) -> str:
    """Encode bytes as an unpadded base64url JWT segment."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()
