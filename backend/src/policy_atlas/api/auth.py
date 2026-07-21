"""RS256 OIDC bearer-token authentication for API route dependencies."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Annotated, Any, cast

import httpx
import jwt
import structlog
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.algorithms import RSAAlgorithm

from policy_atlas.api.settings import Settings

log = structlog.get_logger()

_bearer_scheme = HTTPBearer(auto_error=False)

# How long an unknown kid is remembered as missing-after-refresh before a
# repeat lookup is allowed to trigger another refresh. Bounds outbound JWKS
# fetches an unauthenticated caller can force by replaying a bogus kid.
_NEGATIVE_CACHE_TTL_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """Identity derived from a verified bearer token.

    Args:
        user_id: Subject claim from the verified token.
    """

    user_id: str


class JwksProvider:
    """Caches a local or remote JSON Web Key Set with kid lookup support."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        """Initialise the provider without performing network or file I/O.

        Args:
            settings: Validated OIDC configuration.
            client: Lifespan-owned HTTP client for remote JWKS fetches.
        """
        self._settings = settings
        self._client = client
        self._keys: dict[str, Any] = {}
        self._expires_at = 0.0
        self._missing_since: dict[str, float] = {}

    def get_key(self, kid: str) -> Any:
        """Return a public key, refreshing once when the kid is unknown.

        An unknown kid still missing right after a refresh is negatively
        cached for `_NEGATIVE_CACHE_TTL_SECONDS`: a repeat lookup within that
        window raises immediately without triggering another refresh, so a
        replayed bogus kid cannot force unbounded outbound JWKS fetches.

        Args:
            kid: Key identifier carried by the JWT header.

        Returns:
            A PyJWT-compatible RSA public key.

        Raises:
            KeyError: If the key is absent after refresh, or still negatively
                cached as missing from a recent refresh.
            ValueError: If the JWKS is malformed.
            httpx.HTTPError: If remote JWKS retrieval fails.
        """
        refreshed = False
        if time.monotonic() >= self._expires_at:
            self.refresh()
            refreshed = True
        key = self._keys.get(kid)
        if key is not None:
            self._missing_since.pop(kid, None)
            return key
        if not refreshed:
            missing_at = self._missing_since.get(kid)
            still_negatively_cached = (
                missing_at is not None
                and time.monotonic() - missing_at < _NEGATIVE_CACHE_TTL_SECONDS
            )
            if still_negatively_cached:
                raise KeyError(kid)
            self.refresh()
            key = self._keys.get(kid)
            if key is not None:
                self._missing_since.pop(kid, None)
                return key
        self._missing_since[kid] = time.monotonic()
        raise KeyError(kid)

    def refresh(self) -> None:
        """Refresh the cached JWKS from its configured local or remote source."""
        payload = self._read_jwks()
        raw_keys = payload.get("keys")
        if not isinstance(raw_keys, list):
            raise ValueError("JWKS must contain a keys list")
        keys: dict[str, Any] = {}
        for raw_key in raw_keys:
            if not isinstance(raw_key, dict):
                continue
            kid = raw_key.get("kid")
            if not isinstance(kid, str) or raw_key.get("kty") != "RSA":
                continue
            try:
                keys[kid] = RSAAlgorithm.from_jwk(json.dumps(raw_key))
            except (TypeError, ValueError):
                continue
        self._keys = keys
        self._expires_at = time.monotonic() + self._settings.jwks_cache_ttl_seconds

    def _read_jwks(self) -> dict[str, Any]:
        """Read one configured JWKS source into a JSON object."""
        if self._settings.oidc_jwks_path is not None:
            value = json.loads(self._settings.oidc_jwks_path.read_text(encoding="utf-8"))
        else:
            assert self._settings.oidc_jwks_url is not None
            response = self._client.get(self._settings.oidc_jwks_url)
            response.raise_for_status()
            value = response.json()
        if not isinstance(value, dict):
            raise ValueError("JWKS must be a JSON object")
        return value


class JwtAuthenticator:
    """Verifies RS256 bearer tokens against an issuer JWKS."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        """Build an authenticator backed by a cached JWKS provider.

        Args:
            settings: Validated OIDC settings.
            client: Lifespan-owned HTTP client.
        """
        self._settings = settings
        self.jwks = JwksProvider(settings, client)

    def authenticate(self, token: str) -> AuthenticatedUser:
        """Validate a bearer token and derive its authenticated subject.

        Args:
            token: Raw bearer token, never logged.

        Returns:
            The subject identity extracted from a verified token.

        Raises:
            jwt.PyJWTError: If token parsing or verification fails.
            KeyError: If the signing kid is unavailable.
            ValueError: If JWKS data is malformed.
            httpx.HTTPError: If remote JWKS retrieval fails.
        """
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise jwt.InvalidAlgorithmError("only RS256 bearer tokens are accepted")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise jwt.InvalidTokenError("token header has no kid")
        claims = jwt.decode(
            token,
            key=self.jwks.get_key(kid),
            algorithms=["RS256"],
            audience=self._settings.oidc_audience,
            issuer=self._settings.oidc_issuer,
            options={"require": ["exp", "sub"]},
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise jwt.InvalidTokenError("token has no subject")
        return AuthenticatedUser(user_id=subject)


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthenticatedUser:
    """Return the verified caller identity for an authenticated route.

    Args:
        request: Incoming FastAPI request carrying lifespan-owned state.
        credentials: Parsed HTTP bearer credentials, if present.

    Returns:
        The authenticated subject.

    Raises:
        HTTPException: Always with 401 when the bearer token is absent or invalid.
    """
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthenticated()
    authenticator = cast(JwtAuthenticator, request.app.state.authenticator)
    try:
        return authenticator.authenticate(credentials.credentials)
    except (httpx.HTTPError, jwt.PyJWTError, KeyError, OSError, ValueError):
        log.info("auth.token_rejected")
        raise _unauthenticated() from None


def _unauthenticated() -> HTTPException:
    """Build the contract-preserving unauthenticated response exception."""
    return HTTPException(
        status_code=401,
        detail="authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )
