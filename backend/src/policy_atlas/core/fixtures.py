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


# Synthetic sources seeded into every agent run's corpus.
# syn-001: originally the walking-skeleton echo source (echo + its grounded-block
# leg retired in 023); retained as a plain synthetic upload fixture.
# syn-002: the on-topic appraised seed for the synthesise demo (task 013) — an
# uploaded full-text document about the skeleton scope's intent, sentinel-
# classified so appraise scores it; its chunks are what the chunk lane can
# honestly cite on the fixture corpus (the acquired fixture docs classify
# Unknown and are never appraised).
_SOURCES: dict[str, SourceFixture] = {
    "syn-001": SourceFixture(
        source_ref="syn-001",
        chunks=(
            "Synthetic Policy Atlas test source. ",
            "Evidence suggests that structured provenance tracking improves "
            "audit trail quality in policy research systems.",
        ),
    ),
    "syn-002": SourceFixture(
        source_ref="syn-002",
        chunks=(
            "Synthetic review of housing affordability policies. Across the "
            "reviewed programmes, inclusionary zoning requirements were "
            "associated with modest increases in the supply of "
            "affordable units in high-demand urban areas.",
            "Rental assistance vouchers reduced housing cost burden for "
            "low-income households in most included studies, while reported "
            "effects on neighbourhood mobility were mixed. Several studies "
            "note that voucher take-up depended on landlord participation.",
            "Evidence on rent stabilisation measures was divided: short-term "
            "affordability gains for sitting tenants were reported alongside "
            "reduced rental supply in some markets. The review found little "
            "evidence on long-run effects for new market entrants.",
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
