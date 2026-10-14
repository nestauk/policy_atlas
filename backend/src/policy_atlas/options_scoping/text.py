"""Two small text helpers shared across the options-scoping package."""

from __future__ import annotations


def clean_text(value: str | None) -> str | None:
    """Whitespace collapsed to single spaces; ``None`` for no text or blank text."""
    if value is None:
        return None
    return " ".join(value.split()) or None


def fold_text(value: str) -> str:
    """Whitespace collapsed and case folded: the form two texts compare in."""
    return " ".join(value.split()).casefold()
