"""Shared helpers for building the v2 prose-first synthesis emission wire in tests.

ADR 0015: the section loop emits ``SectionProseWire`` (prose + claims, each
claim text an exact substring of the prose) and the repair pass emits
``SectionRepairWire`` (per-claim prose-segment replacements). These helpers keep
test fixtures terse while guaranteeing every claim text binds as a span.
"""

from __future__ import annotations

from policy_atlas.synthesis_backend import (
    ClaimWire,
    RepairItemWire,
    SectionProseWire,
    SectionRepairWire,
)


def prose_section(*, claims: list[ClaimWire]) -> SectionProseWire:
    """Build a ``SectionProseWire`` whose prose contains every claim text.

    The prose is the claim texts joined by single spaces, so each text is an
    exact substring and the ordered-cursor span binder locates each in order.
    """
    return SectionProseWire(
        prose=" ".join(claim.text for claim in claims),
        claims=list(claims),
    )


def repair_wire(*, claims: list[ClaimWire]) -> SectionRepairWire:
    """Build a ``SectionRepairWire`` from reworded replacement claims.

    Each replacement claim's text is spliced verbatim as its prose segment (an
    exact substring), positionally mapped to the failing claims.
    """
    return SectionRepairWire(
        repairs=[
            RepairItemWire(replacement_segment=claim.text, claim=claim)
            for claim in claims
        ]
    )
