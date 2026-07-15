"""Content hashing for source/block identity (NFC-normalised, whitespace-collapsed)."""

import hashlib
import unicodedata


def _normalize(text: str) -> str:
    """NFC + collapse whitespace."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def content_hash(content: str) -> str:
    """Return the SHA-256 hex digest of normalised content.

    Args:
        content: Text to hash.

    Returns:
        Hex-encoded SHA-256 of the NFC-normalised, whitespace-collapsed content.
    """
    return hashlib.sha256(_normalize(content).encode()).hexdigest()
