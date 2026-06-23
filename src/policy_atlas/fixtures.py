"""Synthetic source fixtures — public-safe, no real acquired/uploaded text.

Shared between the runtime entrypoint and the test suite so both operate
on the same synthetic source chunk.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceFixture:
    """A synthetic source: its reference and ordered text chunks."""

    source_ref: str
    chunks: tuple[str, ...]


# Single synthetic source used by the walking-skeleton thread.
# The quote in produce_grounded_block must be a verbatim substring of joined chunks.
_SOURCES: dict[str, SourceFixture] = {
    "syn-001": SourceFixture(
        source_ref="syn-001",
        chunks=(
            "Synthetic Policy Atlas test source. ",
            "Evidence suggests that structured provenance tracking improves "
            "audit trail quality in policy research systems.",
        ),
    ),
}


def get_source(source_ref: str) -> SourceFixture:
    """Look up a synthetic source fixture by reference.

    Args:
        source_ref: Source reference key (e.g. ``"syn-001"``).

    Returns:
        The matching SourceFixture.

    Raises:
        KeyError: If no fixture is registered for ``source_ref``.
    """
    try:
        return _SOURCES[source_ref]
    except KeyError:
        raise KeyError(f"Unknown synthetic source_ref: {source_ref!r}") from None
