"""Invite-link codes: how they are made, checked and shown.

A code is 12 characters from an alphabet with no look-alike characters
(no ``0 O 1 I L``). It is stored without hyphens and shown as
``XXXX-XXXX-XXXX``. The database check on ``invite_link.code`` is built from
:data:`ALPHABET` and :data:`CODE_LENGTH`, so the two stay in step.
"""

import secrets

#: Digits 2-9 and the upper-case letters without I, L and O: 31 characters.
ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
CODE_LENGTH = 12


def normalise(value: str | None) -> str | None:
    """Return the stored form of a code a person typed or pasted.

    Args:
        value: The raw code, possibly with hyphens, spaces or lower-case letters.

    Returns:
        The upper-case code without hyphens or spaces, or ``None`` when that is not
        exactly ``CODE_LENGTH`` characters of ``ALPHABET``.
    """
    if value is None:
        return None
    code = value.upper().replace("-", "").replace(" ", "")
    if len(code) != CODE_LENGTH or any(char not in ALPHABET for char in code):
        return None
    return code


def new_code() -> str:
    """Return a new random code in its stored form (no hyphens)."""
    return "".join(secrets.choice(ALPHABET) for _ in range(CODE_LENGTH))


def display(code: str) -> str:
    """Return a stored code in groups of four joined by hyphens (``XXXX-XXXX-XXXX``)."""
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))
