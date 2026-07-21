"""Development-only RSA issuer for local Policy Atlas API authentication."""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

DEFAULT_ISSUER = "http://dev-issuer.local"
DEFAULT_KID = "dev-key"


def init(key_dir: Path, *, kid: str = DEFAULT_KID) -> Path:
    """Create an RSA key and add its public JWK to a local development JWKS.

    Args:
        key_dir: Directory in which private keys and ``jwks.json`` are stored.
        kid: Identifier assigned to the new signing key.

    Returns:
        The written JWKS path.

    Raises:
        ValueError: If the requested key identifier is empty.
    """
    if not kid:
        raise ValueError("kid must not be empty")
    key_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_path = _private_key_path(key_dir, kid)
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(private_path, 0o600)

    jwks_path = key_dir / "jwks.json"
    keys = _read_jwks(jwks_path)
    keys = [key for key in keys if key.get("kid") != kid]
    keys.append(_public_jwk(private_key.public_key(), kid))
    jwks_path.write_text(json.dumps({"keys": keys}, indent=2) + "\n", encoding="utf-8")
    return jwks_path


def mint_token(
    sub: str,
    issuer: str,
    client_id: str,
    ttl: int,
    key_dir: Path,
    *,
    kid: str = DEFAULT_KID,
) -> str:
    """Mint a short-lived RS256 token using a local development private key.

    Args:
        sub: Subject claim to encode.
        issuer: Non-production issuer claim to encode.
        client_id: Client identifier claim to encode.
        ttl: Token lifetime in seconds.
        key_dir: Directory previously initialized with :func:`init`.
        kid: Signing key identifier.

    Returns:
        An RS256 JWT suitable for local API development.

    Raises:
        ValueError: If required claims are blank or the TTL is invalid.
        FileNotFoundError: If the selected development private key does not exist.
    """
    if not sub or not issuer or not client_id:
        raise ValueError("sub, issuer and client_id must not be empty")
    if ttl < 1:
        raise ValueError("ttl must be positive")
    private_key = cast(
        rsa.RSAPrivateKey,
        serialization.load_pem_private_key(
            _private_key_path(key_dir, kid).read_bytes(), password=None
        ),
    )
    now = int(time.time())
    return jwt.encode(
        {
            "sub": sub,
            "iss": issuer,
            "client_id": client_id,
            "token_use": "access",
            "iat": now,
            "exp": now + ttl,
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the development issuer command-line interface.

    Args:
        argv: Optional command-line arguments excluding the program name.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--dir", type=Path, required=True)
    init_parser.add_argument("--kid", default=DEFAULT_KID)
    mint_parser = subparsers.add_parser("mint")
    mint_parser.add_argument("--dir", type=Path, required=True)
    mint_parser.add_argument("--sub", required=True)
    mint_parser.add_argument("--issuer", default=DEFAULT_ISSUER)
    mint_parser.add_argument("--client-id", required=True)
    mint_parser.add_argument("--ttl", type=int, default=3600)
    mint_parser.add_argument("--kid", default=DEFAULT_KID)
    args = parser.parse_args(argv)

    if args.command == "init":
        init(args.dir, kid=args.kid)
        return 0
    token = mint_token(
        args.sub,
        args.issuer,
        args.client_id,
        args.ttl,
        args.dir,
        kid=args.kid,
    )
    print(token)
    return 0


def _private_key_path(key_dir: Path, kid: str) -> Path:
    """Return the local private-key path for one development kid."""
    return key_dir / f"{kid}.pem"


def _read_jwks(jwks_path: Path) -> list[dict[str, Any]]:
    """Read existing development JWKS entries, treating a missing file as empty."""
    if not jwks_path.exists():
        return []
    payload = json.loads(jwks_path.read_text(encoding="utf-8"))
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, list):
        raise ValueError("existing JWKS must contain a keys list")
    return [key for key in keys if isinstance(key, dict)]


def _public_jwk(public_key: rsa.RSAPublicKey, kid: str) -> dict[str, str]:
    """Serialize one RSA public key as an RFC 7517 JSON Web Key."""
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _base64url_uint(numbers.n),
        "e": _base64url_uint(numbers.e),
    }


def _base64url_uint(value: int) -> str:
    """Encode a positive integer in the base64url JWK representation."""
    length = max(1, (value.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode("ascii")


if __name__ == "__main__":
    raise SystemExit(main())
