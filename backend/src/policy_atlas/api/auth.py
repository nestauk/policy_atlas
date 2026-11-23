"""RS256 OIDC bearer-token authentication for API route dependencies."""

from __future__ import annotations

import json
import threading
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

# Floor between two JWKS fetches, whatever key id triggered them. A caller can
# send a fresh random kid on every request; this bounds the outbound fetches
# they can force to one per window. A genuinely new signing key is picked up
# at most this long after the last fetch.
_MIN_REFRESH_INTERVAL_SECONDS = 30.0


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
        # Never refreshed yet, so the first lookup is always allowed to fetch.
        self._last_refresh_at = float("-inf")
        self._refresh_lock = threading.Lock()

    def get_key(self, kid: str) -> Any:
        """Return a public key, fetching the key set at most once per window.

        Decision, in order:

        1. The kid is cached and the cache has not expired: return it (no lock).
        2. Otherwise take the refresh lock and look again (another thread may
           have refreshed while this one waited); a fresh hit is returned.
        3. If the last fetch started at least `_MIN_REFRESH_INTERVAL_SECONDS`
           ago, claim the slot (stamp the time before the network call, so a
           slow fetch still holds it), refresh, and look the kid up again.
        4. Inside the window no fetch happens: a kid from the old, expired
           cache is still served; an unknown kid raises `KeyError` at once.

        A failed refresh keeps the previous keys (see `refresh`), so a known
        kid keeps verifying while the key source is down.

        Args:
            kid: Key identifier carried by the JWT header.

        Returns:
            A PyJWT-compatible RSA public key.

        Raises:
            KeyError: If the kid is not in the key set and no refresh is due,
                or still missing after one.
            ValueError: If the JWKS is malformed and no keys were cached before.
            OSError: If the local JWKS file cannot be read and no keys were
                cached before.
            httpx.HTTPError: If remote JWKS retrieval fails and no keys were
                cached before.
        """
        key = self._keys.get(kid)
        if key is not None and time.monotonic() < self._expires_at:
            return key
        with self._refresh_lock:
            key = self._keys.get(kid)
            now = time.monotonic()
            if key is not None and now < self._expires_at:
                return key
            if now - self._last_refresh_at >= _MIN_REFRESH_INTERVAL_SECONDS:
                self._last_refresh_at = now
                try:
                    self.refresh()
                except Exception:
                    # `refresh` raises only when there are no keys at all,
                    # so nobody can verify anyway: give the slot back, or a
                    # blip at boot would reject every token for a window.
                    self._last_refresh_at = float("-inf")
                    raise
                key = self._keys.get(kid)
        if key is None:
            raise KeyError(kid)
        return key

    def refresh(self) -> None:
        """Refresh the cached JWKS from its configured local or remote source.

        A failed read, a malformed key set or one with no usable RSA key
        keeps the previous keys and logs `auth.jwks_refresh_failed`; the
        error is raised only when there are no previous keys to fall back on.

        Raises:
            ValueError: If the JWKS is malformed and no keys were cached before.
            OSError: If the local file cannot be read and no keys were cached.
            httpx.HTTPError: If the remote fetch fails and no keys were cached.
        """
        try:
            payload = self._read_jwks()
            raw_keys = payload.get("keys")
            if not isinstance(raw_keys, list):
                raise ValueError("JWKS must contain a keys list")
        except (httpx.HTTPError, OSError, ValueError) as exc:
            # Class name only: the message can carry the JWKS URL.
            log.error("auth.jwks_refresh_failed", error_class=type(exc).__name__)
            if not self._keys:
                raise
            return
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
        if not keys and self._keys:
            # A list with no usable RSA key is a failed refresh too: keep the
            # working set rather than sign everyone out.
            log.error("auth.jwks_refresh_failed", error_class="NoUsableKeys")
            return
        self._keys = keys
        self._expires_at = time.monotonic() + self._settings.jwks_cache_ttl_seconds
        log.info("auth.jwks_refreshed", key_count=len(keys))

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
            issuer=self._settings.oidc_issuer,
            options={"require": ["exp", "sub"], "verify_aud": False},
        )
        if claims.get("token_use") != "access":
            raise jwt.InvalidTokenError("token is not an access token")
        if claims.get("client_id") != self._settings.oidc_client_id:
            raise jwt.InvalidTokenError("token client_id mismatch")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise jwt.InvalidTokenError("token has no subject")
        return AuthenticatedUser(user_id=subject)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthenticatedUser:
    """Return the verified caller identity for an authenticated route.

    Plain ``def`` on purpose: FastAPI runs it on its worker thread pool, so a
    key-set fetch inside it never blocks the event loop.

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


def get_optional_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AuthenticatedUser | None:
    """Return no user only when the raw ``Authorization`` header is absent.

    The conditionally-public read surface treats a missing header as
    anonymous. Any present header, including a wrong scheme or malformed
    bearer value that ``HTTPBearer`` does not parse, follows the strict
    authentication path and therefore returns 401 on failure.

    Args:
        request: Incoming FastAPI request carrying the raw headers.
        credentials: Parsed HTTP bearer credentials, if present.

    Returns:
        The authenticated subject, or ``None`` when no Authorization header
        was sent.

    Raises:
        HTTPException: 401 when an Authorization header is present but does
            not authenticate.
    """
    if "authorization" not in request.headers:
        return None
    return get_current_user(request, credentials)


def _unauthenticated() -> HTTPException:
    """Build the contract-preserving unauthenticated response exception."""
    return HTTPException(
        status_code=401,
        detail="authentication is required",
        headers={"WWW-Authenticate": "Bearer"},
    )
