"""Pure tests for synthesise helpers and claim validators."""

from __future__ import annotations

from typing import Any

from policy_atlas.quote_verify import build_basis
from policy_atlas.synthesis_backend import (
    ClaimWire,
    GapPayloadWire,
    PatternPayloadWire,
    SparsitySignalWire,
    ThemePayloadWire,
)
from policy_atlas.synthesis_tools import ARTEFACT_TITLE_MAX, SECTION_CAP, SECTION_TURN_CAP
from policy_atlas.synthesise import (
    ChunkInfo,
    ClaimDraft,
    CorpusProfile,
    CoverageRecord,
    FindingInfo,
    SubstrateView,
    build_ledger,
    derive_artefact_title,
    generation_budget_max,
    validate_claims,
)


def _claim(data: dict[str, Any]) -> ClaimWire:
    return ClaimWire.model_validate(data)


def _substrate() -> SubstrateView:
    chunk = ChunkInfo(
        chunk_id="11111111-1111-1111-1111-111111111111",
        pss_id="pss-1",
        source_snapshot_id="snap-1",
        sequence=0,
        content="alpha quoted evidence appears here",
        segmentation_policy="manual_v1",
        origin="unselected_screened",
        appraised=True,
    )
    unappraised = ChunkInfo(
        chunk_id="22222222-2222-2222-2222-222222222222",
        pss_id="pss-2",
        source_snapshot_id="snap-2",
        sequence=0,
        content="beta quoted evidence appears here",
        segmentation_policy="manual_v1",
        origin="selected",
        appraised=False,
    )
    finding = FindingInfo(
        finding_id="finding-1",
        pss_id="pss-1",
        source_snapshot_id="snap-finding",
        record={
            "finding_id": "finding-1",
            "effect_direction": "positive",
            "intervention": "A",
            "outcome": "B",
        },
        grounding=[
            {
                "quote": "finding anchor quote",
                "match_status": "exact",
                "quote_verified": True,
                "spans": [
                    {
                        "chunk_id": "11111111-1111-1111-1111-111111111111",
                        "start": 0,
                        "end": 20,
                    }
                ],
            }
        ],
        effect_direction="positive",
    )
    return SubstrateView(
        characterisation={
            "coverage": {
                "distributions": {"origin": {"uploaded": 2}},
                "sparsity": {"zero_count": 0},
            },
            "themes": [{"theme_id": "theme-1", "name": "Theme one"}],
        },
        selection=None,
        extraction={"counts": {"findings_total": 1}},
        grouping={
            "facet": "intervention",
            "groups": [
                {
                    "group_id": "group-1",
                    "label": "Group 1",
                    "direction_spread": {"positive": 1},
                    "member_finding_ids": ["finding-1"],
                }
            ],
        },
        corpus=CorpusProfile(
            screened_docs=2,
            ingested_docs=2,
            appraised_docs=1,
            appraised_ingested_docs=1,
            appraised_pss_ids={"pss-1"},
        ),
        coverage_records={
            "cov-ok": CoverageRecord(
                record_id="cov-ok",
                backends=[{"backend": "fixture"}],
                adequacy_verdict="adequate",
                verdict_origin="model",
            ),
            "cov-bad": CoverageRecord(
                record_id="cov-bad",
                backends=[{"backend": "fixture"}],
                adequacy_verdict="inadequate",
                verdict_origin="model",
            ),
        },
        chunk_by_id={chunk.chunk_id: chunk, unappraised.chunk_id: unappraised},
        chunks_by_pss_id={"pss-1": [chunk], "pss-2": [unappraised]},
        finding_by_id={"finding-1": finding},
        basis_by_snapshot_id={
            "snap-finding": build_basis(
                [("11111111-1111-1111-1111-111111111111", "finding anchor quote")]
            )
        },
        selected_pss_ids={"pss-2"},
    )


def _rejected_reason(claim: ClaimWire, **kwargs: Any) -> str:
    citable_finding_ids = kwargs.pop("citable_finding_ids", {"finding-1"})
    citable_chunk_ids = kwargs.pop(
        "citable_chunk_ids", {"11111111-1111-1111-1111-111111111111"}
    )
    batch = validate_claims(
        [claim],
        substrate=_substrate(),
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids=citable_finding_ids,
        citable_chunk_ids=citable_chunk_ids,
        **kwargs,
    )
    assert len(batch.rejected) == 1
    return batch.rejected[0].reason


def test_artefact_title_strips_control_chars_and_truncates() -> None:
    title = derive_artefact_title("A\x07B")
    assert title == "AB"

    long = "x" * (ARTEFACT_TITLE_MAX + 10)
    truncated = derive_artefact_title(long)
    assert len(truncated) == ARTEFACT_TITLE_MAX
    assert truncated.endswith("…")


def test_budget_formula_and_ledger_marker() -> None:
    assert generation_budget_max() == 2 + SECTION_CAP * (SECTION_TURN_CAP + 3)

    ledger = build_ledger(
        [
            ClaimDraft(
                claim_id="s0c0",
                claim_index=0,
                claim_type="reasoning",
                text="Reasoning.",
                annotation_type="reasoning",
                payload={},
                cited_ids=["not-citable-here"],
                flags=["weak"],
            )
        ]
    )
    assert ledger == [
        {
            "claim_id": "s0c0",
            "claim_type": "reasoning",
            "text": "Reasoning.",
            "cited_ids": ["not-citable-here"],
            "flags": ["weak"],
            "ledger_note": "context, never evidence — not citable",
        }
    ]


def test_validator_reject_reasons_are_reachable() -> None:
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "11111111-1111-1111-1111-111111111111",
                            "quote": "alpha quoted evidence",
                        }
                    ],
                }
            ),
            available_claim_types={"gap", "reasoning"},
        )
        == "substrate_ungated_type"
    )
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "finding",
                    "text": "Finding claim.",
                    "cited_finding_ids": ["missing"],
                }
            )
        )
        == "uncited_finding_id"
    )
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "11111111-1111-1111-1111-111111111111",
                            "quote": "alpha quoted evidence",
                        }
                    ],
                }
            ),
            citable_chunk_ids=set(),
        )
        == "unreturned_chunk_id"
    )
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "22222222-2222-2222-2222-222222222222",
                            "quote": "beta quoted evidence",
                        }
                    ],
                }
            ),
            citable_chunk_ids={"22222222-2222-2222-2222-222222222222"},
        )
        == "unappraised_doc_citation"
    )


def test_pattern_theme_gap_and_reasoning_validation_edges() -> None:
    assert (
        _rejected_reason(
            ClaimWire(
                claim_type="pattern",
                text="Wrong count.",
                pattern=PatternPayloadWire(
                    kind="coverage_count",
                    computed_from="characterisation_coverage",
                    path=["distributions", "origin"],
                    stated={"uploaded": 99},
                    base="screened",
                ),
            )
        )
        == "pattern_mismatch"
    )
    assert (
        _rejected_reason(_claim({"claim_type": "pattern", "text": "Scanned shape."}))
        == "content_scan_prohibited"
    )
    assert (
        _rejected_reason(
            ClaimWire(
                claim_type="theme",
                text="Unknown theme.",
                theme=ThemePayloadWire(
                    source="characterisation", referenced_ids=["missing"], base="screened"
                ),
            )
        )
        == "theme_unknown_id"
    )
    assert (
        _rejected_reason(
            ClaimWire(
                claim_type="gap",
                text="Sparse gap.",
                gap=GapPayloadWire(
                    grade="acknowledged_sparsity",
                    coverage_base="screened",
                    sparsity=SparsitySignalWire(
                        path=["distributions", "origin", "uploaded"], stated_count=99
                    ),
                ),
            )
        )
        == "sparsity_mismatch"
    )

    reasoning = [
        _claim({"claim_type": "reasoning", "text": f"Reasoning {index}."})
        for index in range(4)
    ]
    batch = validate_claims(
        reasoning,
        substrate=_substrate(),
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
    )
    assert [rejection.reason for rejection in batch.rejected] == ["reasoning_over_cap"]


def test_gap_degradation_and_caveat_payloads() -> None:
    substrate = _substrate()
    degraded = validate_claims(
        [
            ClaimWire(
                claim_type="gap",
                text="No studies were found in the searched space.",
                gap=GapPayloadWire(
                    grade="corpus_absence",
                    coverage_base="searched",
                    coverage_record_id="cov-bad",
                ),
            )
        ],
        substrate=substrate,
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
    )
    assert degraded.drafts[0].flags == ["gap_degraded"]
    assert degraded.drafts[0].payload["gap"]["grade"] == "inferred"
    assert degraded.drafts[0].payload["gap"]["coverage_base"] == "screened"

    caveated = validate_claims(
        [
            ClaimWire(
                claim_type="gap",
                text="No studies were found in the searched space.",
                gap=GapPayloadWire(
                    grade="corpus_absence",
                    coverage_base="searched",
                    coverage_record_id="cov-ok",
                ),
            )
        ],
        substrate=substrate,
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
    )
    caveat = caveated.drafts[0].payload["gap"]["caveat"]
    assert caveat == {
        "search_space": [{"backend": "fixture"}],
        "adequacy_verdict": "adequate",
        "verdict_origin": "model",
    }
