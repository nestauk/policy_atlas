"""Shared helpers for building the v2 prose-first synthesis emission wire in tests.

ADR 0015: the section loop emits ``SectionProseWire`` (prose + claims, each
claim text an exact substring of the prose) and the repair pass emits
``SectionRepairWire`` (per-claim prose-segment replacements). These helpers keep
test fixtures terse while guaranteeing every claim text binds as a span.
"""

from __future__ import annotations

from typing import Any

from policy_atlas.synthesis_backend import (
    ClaimWire,
    RepairItemWire,
    SectionProseWire,
    SectionRepairWire,
)
from policy_atlas.usage import UsageResult


def empty_key_findings(_seed: dict[str, Any]) -> UsageResult[SectionProseWire]:
    """The absence-path key-findings emission (empty prose + no claims).

    A ``write_key_findings`` for section-focused test backends that do not
    exercise the key-findings pass — no headline block is minted (ADR 0015 §8).
    """
    return SectionProseWire(prose="", claims=[]), None


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
    exact substring), id-mapped to the failing claims.
    """
    return SectionRepairWire(
        repairs=[
            RepairItemWire(
                claim_id=f"s0c{index}",
                replacement_segment=claim.text,
                claim=claim,
            )
            for index, claim in enumerate(claims)
        ]
    )
