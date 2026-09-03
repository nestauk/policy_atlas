"""Shared helpers for building the v2 prose-first synthesis emission wire in tests.

ADR 0015: the section loop emits ``SectionProseWire`` (prose + claims, each
claim text an exact substring of the prose) and the repair pass emits
``SectionRepairWire`` (per-claim prose-segment replacements). These helpers keep
test fixtures terse while guaranteeing every claim text binds as a span.
"""

from __future__ import annotations

from typing import Any

from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_base.synthesis.synthesis_backend import (
    CaseStudyWire,
    ClaimWire,
    IntroWire,
    NoteWire,
    RepairItemWire,
    SectionProposalWire,
    SectionProseWire,
    SectionRepairWire,
    SectionTurn,
    SummaryJudgeWire,
    SummaryWire,
)
from policy_atlas.evidence_base.synthesis.synthesis_tools import ToolExchange


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


class ScriptedSynthesisBackend:
    """Base for section-loop test doubles that script one scenario's ``section_turn``.

    Shares the plumbing every scripted synthesis backend needs: ``mode =
    "stub"``, a fixed ``propose_sections`` proposal (pass it via ``proposal=``
    or set ``self._proposal`` in a subclass ``__init__``), an absence-path
    ``write_key_findings`` (``empty_key_findings``), and a ``repair_section``
    default that fails loudly if called — most scripted scenarios never
    expect a repair pass. Override whichever of the three a scenario needs
    differently; ``section_turn`` has no shared default (task 023 WP8 —
    it's each scenario's reason for existing) and subclasses must implement it.
    """

    mode = "stub"

    def __init__(self, *, proposal: SectionProposalWire | None = None) -> None:
        self._proposal = proposal

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
        section_budget: int | None = None,
    ) -> UsageResult[SectionProposalWire]:
        del intent, substrate, rejection, section_budget
        if self._proposal is None:
            raise AssertionError(
                f"{type(self).__name__} has no propose_sections() proposal configured"
            )
        return self._proposal, None

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        raise NotImplementedError

    def repair_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        failing: list[dict[str, Any]],
    ) -> UsageResult[SectionRepairWire]:
        del seed, transcript, failing
        raise AssertionError(f"{type(self).__name__}.repair_section should not be called")

    def write_key_findings(self, seed: dict[str, Any]) -> UsageResult[SectionProseWire]:
        return empty_key_findings(seed)

    def write_case_studies(self, seed: dict[str, Any]) -> UsageResult[CaseStudyWire]:
        """Absence-path case studies for section-focused scripted backends."""
        del seed
        return CaseStudyWire(cards=[]), None

    def write_source_note(self, seed: dict[str, Any]) -> UsageResult[NoteWire]:
        """Empty MRS note for section-focused scripted backends."""
        del seed
        return NoteWire(note=""), None

    def write_full_report_intro(self, seed: dict[str, Any]) -> UsageResult[IntroWire]:
        """Deterministic full-report intro for section-focused scripted backends."""
        del seed
        return IntroWire(intro=""), None

    def write_block_summary(self, seed: dict[str, Any]) -> UsageResult[SummaryWire]:
        """Return a deterministic summary for protocol completeness in test doubles."""
        return SummaryWire(summary=str(seed.get("prose", ""))[:200]), None

    def judge_summary(
        self, *, summary: str, detail: dict[str, Any]
    ) -> UsageResult[SummaryJudgeWire]:
        """Return a passing summary verdict for protocol completeness in test doubles."""
        del summary, detail
        return SummaryJudgeWire(verdict="pass", reason="test stub"), None

    @staticmethod
    def _repair_unchanged(failing: list[dict[str, Any]]) -> SectionRepairWire:
        """Rebuild each failing claim's ``ClaimWire`` unchanged (a no-op passthrough repair).

        Shared by scenarios whose repair pass deliberately returns the
        failing claim(s) verbatim (e.g. a fabricated quote that repair cannot fix).
        """
        claims: list[ClaimWire] = []
        for record in failing:
            raw = record.get("claim", record)
            claim_data = {k: v for k, v in raw.items() if k in ClaimWire.model_fields}
            claims.append(ClaimWire.model_validate(claim_data))
        return repair_wire(claims=claims)
