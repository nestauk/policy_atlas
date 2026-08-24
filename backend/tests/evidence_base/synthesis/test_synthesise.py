"""Contract-bulk DB-backed tests for the synthesise component.

These tests require ``DATABASE_URL`` and are intended for the lead's DB-backed
verification run. The local Codex sandbox does not run them.
"""

from __future__ import annotations

import uuid
from collections import Counter
from typing import Any

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import StubEmbeddingBackend
from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    capability_run,
    citation,
    conversation,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    orchestration_plan,
    project_source_snapshot,
    runs,
    search_coverage_record,
    selection_result,
    source_extraction_record,
    synthesis_result,
)
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_base.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_base.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.evidence_base.extract.quote_verify import build_basis
from policy_atlas.evidence_base.synthesis.grounding_judge import (
    JudgeResponseWire,
    StubGroundingJudgeBackend,
    UnspannedAssertionWire,
)
from policy_atlas.evidence_base.synthesis.synthesis_backend import (
    NAV_LABEL_MAX,
    ChunkCitationWire,
    ClaimWire,
    GapPayloadWire,
    PatternPayloadWire,
    RepairItemWire,
    SectionProposalWire,
    SectionProseWire,
    SectionRepairWire,
    SectionTurn,
    SectionWire,
    StubSynthesisBackend,
    SynthesisBackend,
    ThemePayloadWire,
)
from policy_atlas.evidence_base.synthesis.synthesis_tools import SECTION_CAP, ToolExchange
from policy_atlas.evidence_base.synthesis.synthesise import (
    ChunkInfo,
    ClaimDraft,
    ClaimValidationBatch,
    CorpusProfile,
    CoverageRecord,
    FindingInfo,
    RejectedClaim,
    SectionAccounting,
    SubstrateView,
    SynthesiseContext,
    SynthesiseFailure,
    _apply_and_rebuild,
    _grouping_summary,
    _groups_unsectioned_by_facet,
    _load_findings,
    _repair_dependency_records,
    _repair_id_mismatch,
    _rollup_counts,
    _validate_sections,
    _validate_theme_claim,
    compile_synthesis_directive,
    propose_synthesis_plan,
    synthesise_scope,
)
from policy_atlas.runtime.orchestrate import persist_approved_plan
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan
from tests.evidence_base.group.test_group import (
    _group_row,
    seed_extraction,
)
from tests.evidence_base.group.test_group import (
    _run_group as _run_group_component,
)
from tests.helpers import (
    delete_project_data,
    now,
    run_select,
    seed_characterisation,
    seed_ingested_full_text,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_select_doc,
    seed_source,
)
from tests.synthesis_wire import ScriptedSynthesisBackend, prose_section


def _count(conn: Connection, table: Any, project_id: uuid.UUID) -> int:
    """Project-scoped row count — the test DB carries residual committed rows
    from other suites' commit-survival tests, so global counts are meaningless."""
    if table is artefact or table is synthesis_result:
        stmt = select(func.count()).select_from(table).where(table.c.project_id == project_id)
        return int(conn.execute(stmt).scalar_one())
    block_ids = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
        )
    )
    if table is block:
        stmt = select(func.count()).select_from(block).where(block.c.block_id.in_(block_ids))
    elif table is addressable_unit:
        stmt = (
            select(func.count())
            .select_from(addressable_unit)
            .where(addressable_unit.c.block_id.in_(block_ids))
        )
    elif table is annotation:
        stmt = (
            select(func.count())
            .select_from(annotation)
            .where(annotation.c.block_id.in_(block_ids))
        )
    elif table is citation:
        stmt = (
            select(func.count())
            .select_from(citation)
            .where(
                citation.c.annotation_id.in_(
                    select(annotation.c.annotation_id).where(
                        annotation.c.block_id.in_(block_ids)
                    )
                )
            )
        )
    else:
        raise AssertionError(f"unsupported table for scoped count: {table}")
    return int(conn.execute(stmt).scalar_one())


def _empty_substrate(grouping: dict[str, Any] | None) -> SubstrateView:
    return SubstrateView(
        characterisation=None,
        selection=None,
        extraction=None,
        grouping=grouping,
        corpus=CorpusProfile(
            screened_docs=0,
            ingested_docs=0,
            appraised_docs=0,
            appraised_ingested_docs=0,
            appraised_pss_ids=set(),
        ),
        coverage_records={},
        chunk_by_id={},
        chunks_by_pss_id={},
        finding_by_id={},
        icf_finding_by_id={},
        icf_profile_available=False,
        basis_by_snapshot_id={},
        selected_pss_ids=set(),
    )


def _repair_dependency_substrate() -> SubstrateView:
    chunk = ChunkInfo(
        chunk_id="chunk-1",
        pss_id="pss-1",
        source_snapshot_id="snapshot-1",
        sequence=1,
        content="Alpha quote appears in the full chunk content.",
        segmentation_policy="manual_v1",
        text_basis="full_text",
        origin="selected",
        appraised=True,
    )
    finding = FindingInfo(
        kind="iof",
        finding_id="finding-1",
        pss_id="pss-1",
        source_snapshot_id="snapshot-1",
        record={
            "kind": "iof",
            "finding_id": "finding-1",
            "intervention": "Alpha",
            "outcome": "Outcome",
            "effect_direction": "increase",
        },
        grounding=[{"quote": "Alpha quote"}],
        effect_direction="increase",
    )
    return SubstrateView(
        characterisation={
            "coverage": {"signals": {"thin": 2}},
            "themes": [{"theme_id": "theme-1", "name": "Access"}],
        },
        selection=None,
        extraction={"counts": {"findings": {"total": 1}}},
        grouping={
            "facets": ["intervention"],
            "groups": [
                {
                    "group_id": "intervention:g01",
                    "facet": "intervention",
                    "label": "Alpha",
                    "description": "Alpha services.",
                    "member_finding_ids": ["finding-1"],
                    "direction_spread": {"increase": 1},
                    "size": 1,
                }
            ],
        },
        corpus=CorpusProfile(
            screened_docs=1,
            ingested_docs=1,
            appraised_docs=1,
            appraised_ingested_docs=1,
            appraised_pss_ids={"pss-1"},
        ),
        coverage_records={
            "coverage-1": CoverageRecord(
                record_id="coverage-1",
                backends=[{"backend": "fixture"}],
                adequacy_verdict="adequate",
                verdict_origin="tool",
            )
        },
        chunk_by_id={"chunk-1": chunk},
        chunks_by_pss_id={"pss-1": [chunk]},
        finding_by_id={"finding-1": finding},
        icf_finding_by_id={},
        icf_profile_available=False,
        basis_by_snapshot_id={
            "snapshot-1": build_basis([("chunk-1", chunk.content)]),
        },
        selected_pss_ids={"pss-1"},
    )


def test_repair_dependency_records_select_per_claim_type() -> None:
    substrate = _repair_dependency_substrate()
    transcript: list[ToolExchange] = [
        {
            "tool": "search_chunks",
            "arguments": {"query": "alpha"},
            "result": {
                "chunks": [
                    {
                        "chunk_record_id": "chunk-1",
                        "already_returned": True,
                    }
                ]
            },
        }
    ]

    chunk_deps = _repair_dependency_records(
        ClaimWire(
            claim_type="chunk",
            text="Chunk claim.",
            citations=[ChunkCitationWire(chunk_record_id="chunk-1", quote="missing")],
        ),
        transcript=transcript,
        substrate=substrate,
    )
    assert chunk_deps == {
        "chunks": {
            "chunk-1": {
                "chunk_record_id": "chunk-1",
                "pss_id": "pss-1",
                "source_snapshot_id": "snapshot-1",
                "sequence": 1,
                "content": "Alpha quote appears in the full chunk content.",
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
                "origin": "selected",
                "appraised": True,
            }
        }
    }

    finding_deps = _repair_dependency_records(
        ClaimWire(
            claim_type="finding",
            text="Finding claim.",
            cited_finding_ids=["finding-1"],
        ),
        transcript=transcript,
        substrate=substrate,
    )
    assert finding_deps["findings"]["finding-1"]["intervention"] == "Alpha"
    assert finding_deps["chunks"]["chunk-1"]["content"].startswith("Alpha quote")

    pattern_deps = _repair_dependency_records(
        ClaimWire(
            claim_type="pattern",
            text="Pattern claim.",
            pattern=PatternPayloadWire(
                kind="direction_spread",
                computed_from="group_direction_spread",
                group_id="intervention:g01",
                stated={"increase": 1},
                base="extracted",
            ),
        ),
        transcript=transcript,
        substrate=substrate,
    )
    assert pattern_deps["computed"]["group_direction_spread:intervention:g01"] == {
        "computed_from": "group_direction_spread",
        "group_id": "intervention:g01",
        "direction_spread": {"increase": 1},
    }
    assert pattern_deps["groups"]["intervention:g01"]["label"] == "Alpha"
    assert "chunks" not in pattern_deps

    theme_deps = _repair_dependency_records(
        ClaimWire(
            claim_type="theme",
            text="Theme claim.",
            theme=ThemePayloadWire(
                source="grouping",
                referenced_ids=["intervention:g01"],
                base="extracted",
            ),
        ),
        transcript=transcript,
        substrate=substrate,
    )
    assert theme_deps == {
        "groups": {
            "intervention:g01": substrate.group_by_id["intervention:g01"],
        }
    }

    gap_deps = _repair_dependency_records(
        ClaimWire(
            claim_type="gap",
            text="Gap claim.",
            gap=GapPayloadWire(
                grade="corpus_absence",
                coverage_base="screened",
                coverage_record_id="coverage-1",
            ),
        ),
        transcript=transcript,
        substrate=substrate,
    )
    assert gap_deps["coverage_records"]["coverage-1"]["adequacy_verdict"] == "adequate"
    assert "chunks" not in gap_deps


def test_repair_application_binds_known_ids_regardless_of_order() -> None:
    substrate = _empty_substrate(grouping=None)
    prose = "First unsupported. Second unsupported."
    first_claim = ClaimWire(
        claim_type="gap",
        text="First unsupported.",
        gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
    )
    second_claim = ClaimWire(
        claim_type="gap",
        text="Second unsupported.",
        gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
    )
    initial = ClaimValidationBatch(
        drafts=[],
        rejected=[
            RejectedClaim(
                claim_id="s0c0",
                claim_index=0,
                claim=first_claim,
                reason="gap_invalid",
                span=(0, 18),
            ),
            RejectedClaim(
                claim_id="s0c1",
                claim_index=1,
                claim=second_claim,
                reason="gap_invalid",
                span=(19, 38),
            ),
        ],
    )
    failing = [
        {
            "claim_id": "s0c0",
            "claim_index": 0,
            "claim": first_claim.model_dump(mode="json"),
            "rationale": "gap_invalid",
            "span": [0, 18],
        },
        {
            "claim_id": "s0c1",
            "claim_index": 1,
            "claim": second_claim.model_dump(mode="json"),
            "rationale": "gap_invalid",
            "span": [19, 38],
        },
    ]
    repairs = [
        RepairItemWire(
            claim_id="s0c1",
            replacement_segment="Second repaired.",
            claim=ClaimWire(
                claim_type="gap",
                text="Second repaired.",
                gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
            ),
        ),
        RepairItemWire(
            claim_id="s0c0",
            replacement_segment="First repaired.",
            claim=ClaimWire(
                claim_type="gap",
                text="First repaired.",
                gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
            ),
        ),
    ]
    accounting = SectionAccounting(
        tool_call_counts={},
        tool_call_count=0,
        gathered_id_hash="",
        turns_used=0,
        turn_cap_hit=False,
    )

    final, final_prose, rejudge_calls, _usage, _unspanned = _apply_and_rebuild(
        prose=prose,
        initial=initial,
        failing=failing,
        repairs=repairs,
        substrate=substrate,
        section_group_ids=set(),
        citable_finding_ids=set(),
        citable_chunk_ids=set(),
        available_claim_types={"gap"},
        grounding_judge_backend=StubGroundingJudgeBackend(),
        accounting=accounting,
    )

    assert [claim.text for claim in final] == ["First repaired.", "Second repaired."]
    assert final_prose == "First repaired. Second repaired."
    assert rejudge_calls == 0
    assert accounting.claims_rejected_structural == 0
    assert _repair_id_mismatch(repairs, failing) is False


def test_repair_application_rejects_unknown_ids_and_marks_missing() -> None:
    substrate = _empty_substrate(grouping=None)
    claim = ClaimWire(
        claim_type="gap",
        text="Unsupported.",
        gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
    )
    initial = ClaimValidationBatch(
        drafts=[],
        rejected=[
            RejectedClaim(
                claim_id="s0c0",
                claim_index=0,
                claim=claim,
                reason="gap_invalid",
                span=(0, 12),
            )
        ],
    )
    failing = [
        {
            "claim_id": "s0c0",
            "claim_index": 0,
            "claim": claim.model_dump(mode="json"),
            "rationale": "gap_invalid",
            "span": [0, 12],
        }
    ]
    repairs = [
        RepairItemWire(
            claim_id="unknown",
            replacement_segment="Repaired.",
            claim=ClaimWire(
                claim_type="gap",
                text="Repaired.",
                gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
            ),
        )
    ]
    accounting = SectionAccounting(
        tool_call_counts={},
        tool_call_count=0,
        gathered_id_hash="",
        turns_used=0,
        turn_cap_hit=False,
    )

    final, final_prose, _rejudge_calls, _usage, _unspanned = _apply_and_rebuild(
        prose="Unsupported.",
        initial=initial,
        failing=failing,
        repairs=repairs,
        substrate=substrate,
        section_group_ids=set(),
        citable_finding_ids=set(),
        citable_chunk_ids=set(),
        available_claim_types={"gap"},
        grounding_judge_backend=StubGroundingJudgeBackend(),
        accounting=accounting,
    )

    assert final == []
    assert final_prose == "Unsupported."
    assert accounting.claims_rejected_structural == 2
    assert _repair_id_mismatch(repairs, failing) is True


def _single_facet_grouping_row() -> dict[str, Any]:
    return {
        "groups": {
            "intervention": {
                "groups": [
                    {
                        "group_id": "intervention:g01",
                        "facet": "intervention",
                        "label": "Alpha",
                        "description": "Alpha services.",
                        "member_values": ["Alpha"],
                        "member_finding_ids": ["f1"],
                        "size": 1,
                        "direction_spread": {"increase": 1},
                    }
                ],
                "ungrouped": {"member_finding_ids": []},
                "no_value": {"member_finding_ids": []},
            }
        },
        "counts": {"intervention": {"groups": 1, "ungrouped": 0, "no_value": 0}},
        "flags": {"intervention": {"status": "succeeded"}},
    }


def _multi_facet_grouping_row() -> dict[str, Any]:
    return {
        "groups": {
            "intervention": {
                "groups": [
                    {
                        "group_id": "intervention:g01",
                        "facet": "intervention",
                        "label": "Alpha",
                        "description": "Alpha services.",
                        "member_values": ["Alpha"],
                        "member_finding_ids": ["f1"],
                        "size": 1,
                        "direction_spread": {"increase": 1},
                    }
                ],
                "ungrouped": {"member_finding_ids": []},
                "no_value": {"member_finding_ids": ["f3"]},
            },
            "barrier_theme": {
                "groups": [
                    {
                        "group_id": "barrier_theme:g01",
                        "facet": "barrier_theme",
                        "label": "Planning delays",
                        "description": "Planning delays slow delivery.",
                        "member_finding_ids": ["f2"],
                        "size": 1,
                        "direction_spread": None,
                    }
                ],
                "ungrouped": {"member_finding_ids": []},
            },
        },
        "counts": {
            "intervention": {"groups": 1, "ungrouped": 0, "no_value": 1},
            "barrier_theme": {"groups": 1, "ungrouped": 0},
        },
        "flags": {
            "intervention": {"status": "succeeded"},
            "barrier_theme": {"status": "succeeded"},
        },
    }


def test_migrated_single_facet_grouping_row_consumed_by_qualified_read_paths() -> None:
    summary = _grouping_summary(_single_facet_grouping_row())
    assert summary is not None
    substrate = _empty_substrate(summary)

    assert summary["facets"] == ["intervention"]
    assert summary["groups"][0]["group_id"] == "intervention:g01"
    assert "no_value" in summary["residuals"]["intervention"]
    assert substrate.grouping_group_ids == {"intervention:g01"}
    assert set(substrate.group_by_id) == {"intervention:g01"}

    sections, reasons, normalisations = _validate_sections(
        SectionProposalWire(
            sections=[
                SectionWire(
                    title="Alpha services",
                    focus="Alpha intervention evidence.",
                    group_ids=["intervention:g01"],
                )
            ]
        ),
        grouping_group_ids=substrate.grouping_group_ids,
    )
    assert [section.group_ids for section in sections] == [["intervention:g01"]]
    assert reasons == []
    assert normalisations == []

    unsectioned_by_facet = _groups_unsectioned_by_facet(
        substrate, assigned_groups={"intervention:g01"}
    )
    assert unsectioned_by_facet == {"intervention": 0}
    counts = _rollup_counts(
        all_claims=[],
        section_blocks=[],
        sections_total=1,
        substrate=substrate,
        groups_unsectioned=sum(unsectioned_by_facet.values()),
        groups_unsectioned_by_facet=unsectioned_by_facet,
        chunk_claims_rejected=0,
        claims_rejected_structural=0,
        gap_claims_degraded=0,
        span_bind_failures=0,
        unspanned_assertions=0,
        unspanned_overlap_filtered=0,
        unspanned_duplicate_stale=0,
        unspanned_unlocated=0,
        tool_calls_total=0,
    )
    assert counts["groups_total"] == 1
    assert counts["groups_unsectioned"] == 0
    assert counts["groups_unsectioned_by_facet"] == {"intervention": 0}

    draft = _validate_theme_claim(
        ClaimWire(
            claim_type="theme",
            text="The intervention grouping identifies Alpha services.",
            theme=ThemePayloadWire(
                source="grouping",
                referenced_ids=["intervention:g01"],
                base="extracted",
            ),
        ),
        claim_id="c1",
        claim_index=0,
        substrate=substrate,
    )
    assert isinstance(draft, ClaimDraft)


def test_multi_facet_grouping_row_consumed_with_per_facet_honesty() -> None:
    summary = _grouping_summary(_multi_facet_grouping_row())
    assert summary is not None
    substrate = _empty_substrate(summary)

    assert substrate.grouping_group_ids == {"intervention:g01", "barrier_theme:g01"}
    assert summary["facet"] is None
    assert summary["facets"] == ["intervention", "barrier_theme"]
    assert "no_value" in summary["residuals"]["intervention"]
    assert "no_value" not in summary["residuals"]["barrier_theme"]

    unsectioned_by_facet = _groups_unsectioned_by_facet(
        substrate, assigned_groups={"intervention:g01"}
    )
    assert unsectioned_by_facet == {"barrier_theme": 1, "intervention": 0}
    counts = _rollup_counts(
        all_claims=[],
        section_blocks=[],
        sections_total=1,
        substrate=substrate,
        groups_unsectioned=sum(unsectioned_by_facet.values()),
        groups_unsectioned_by_facet=unsectioned_by_facet,
        chunk_claims_rejected=0,
        claims_rejected_structural=0,
        gap_claims_degraded=0,
        span_bind_failures=0,
        unspanned_assertions=0,
        unspanned_overlap_filtered=0,
        unspanned_duplicate_stale=0,
        unspanned_unlocated=0,
        tool_calls_total=0,
    )
    assert counts["groups_total"] == 2
    assert counts["groups_unsectioned"] == 1
    assert counts["groups_unsectioned_by_facet"] == {
        "barrier_theme": 1,
        "intervention": 0,
    }

    draft = _validate_theme_claim(
        ClaimWire(
            claim_type="theme",
            text="The barrier grouping identifies planning delays.",
            theme=ThemePayloadWire(
                source="grouping",
                referenced_ids=["barrier_theme:g01"],
                base="extracted",
            ),
        ),
        claim_id="c2",
        claim_index=0,
        substrate=substrate,
    )
    assert isinstance(draft, ClaimDraft)

    rejected = _validate_theme_claim(
        ClaimWire(
            claim_type="theme",
            text="The grouping identifies an unknown theme.",
            theme=ThemePayloadWire(
                source="grouping",
                referenced_ids=["outcome:g01"],
                base="extracted",
            ),
        ),
        claim_id="c3",
        claim_index=1,
        substrate=substrate,
    )
    assert isinstance(rejected, RejectedClaim)
    assert rejected.reason == "theme_unknown_id"


def test_section_validation_rejects_unqualified_group_ids_with_expected_form() -> None:
    summary = _grouping_summary(_single_facet_grouping_row())
    assert summary is not None
    substrate = _empty_substrate(summary)

    _sections, reasons, _normalisations = _validate_sections(
        SectionProposalWire(
            sections=[
                SectionWire(
                    title="Legacy group",
                    focus="Legacy id should not resolve.",
                    group_ids=["g01"],
                )
            ]
        ),
        grouping_group_ids=substrate.grouping_group_ids,
    )

    assert len(reasons) == 1
    assert "group_ids_unknown" in reasons[0]
    assert "<facet>:gNN" in reasons[0]


def test_failed_facet_stays_visible_while_sibling_groups_resolve() -> None:
    row = _multi_facet_grouping_row()
    row["groups"]["outcome"] = {
        "groups": [],
        "ungrouped": {"member_finding_ids": []},
        "no_value": {"member_finding_ids": []},
    }
    row["counts"]["outcome"] = {"groups": 0, "ungrouped": 0, "no_value": 0}
    row["flags"]["outcome"] = {
        "status": "failed",
        "failure_class": "backend_error",
        "groups_rejected": False,
        "value_cap_exceeded": False,
    }

    summary = _grouping_summary(row)
    assert summary is not None
    substrate = _empty_substrate(summary)

    assert summary["facets"] == ["intervention", "barrier_theme", "outcome"]
    assert summary["facet_status"]["outcome"]["status"] == "failed"
    assert substrate.grouping_group_ids == {"intervention:g01", "barrier_theme:g01"}
    assert _groups_unsectioned_by_facet(
        substrate, assigned_groups={"intervention:g01", "barrier_theme:g01"}
    ) == {"barrier_theme": 0, "intervention": 0, "outcome": 0}


def _project_annotations(conn: Connection, project_id: uuid.UUID) -> list[Any]:
    block_ids = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
        )
    )
    return [
        row.payload
        for row in conn.execute(
            select(annotation.c.payload).where(annotation.c.block_id.in_(block_ids))
        )
    ]


def _run_synthesise(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    intent: str = "Test intent",
    context: dict[str, Any] | None = None,
    characterisation_run_id: uuid.UUID | None = None,
    selection_run_id: uuid.UUID | None = None,
    extraction_run_id: uuid.UUID | None = None,
    grouping_run_id: uuid.UUID | None = None,
    backend: SynthesisBackend | None = None,
    judge_backend: Any | None = None,
) -> dict[str, Any]:
    return synthesise_scope(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=SynthesiseContext(
            scope_id=scope_id,
            intent=intent,
            context=context or {},
            characterisation_run_id=characterisation_run_id,
            selection_run_id=selection_run_id,
            extraction_run_id=extraction_run_id,
            grouping_run_id=grouping_run_id,
        ),
        synthesis_backend=backend or StubSynthesisBackend(),
        grounding_judge_backend=judge_backend or StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
    )


def test_section_budget_rejects_an_over_budget_proposal_for_bounded_repair() -> None:
    """A five-section proposal is rejected when the plan ceiling is three."""
    proposal = SectionProposalWire(
        sections=[
            SectionWire(title=f"Evidence aspect {index}", focus="A focused evidence aspect.")
            for index in range(5)
        ]
    )
    _sections, reasons, _normalisations = _validate_sections(
        proposal, grouping_group_ids=None, section_budget=3
    )
    assert reasons == ["section_count_out_of_range: 1..3"]


def test_section_budget_validator_never_exceeds_the_global_section_cap() -> None:
    """A malformed above-cap budget clamps to ``SECTION_CAP`` rather than widening it."""
    proposal = SectionProposalWire(
        sections=[
            SectionWire(title=f"Evidence aspect {index}", focus="A focused evidence aspect.")
            for index in range(SECTION_CAP + 1)
        ]
    )
    _sections, reasons, _normalisations = _validate_sections(
        proposal,
        grouping_group_ids=None,
        section_budget=SECTION_CAP + 10,
    )
    assert reasons == [f"section_count_out_of_range: 1..{SECTION_CAP}"]


def test_section_validation_accepts_a_valid_nav_label() -> None:
    proposal = SectionProposalWire(
        sections=[
            SectionWire(
                title="Evidence aspect",
                focus="A focused evidence aspect.",
                nav_label="Short label",
            )
        ]
    )
    sections, reasons, normalisations = _validate_sections(proposal, grouping_group_ids=None)
    assert reasons == []
    assert normalisations == []
    assert [section.nav_label for section in sections] == ["Short label"]


def test_section_validation_accepts_a_nav_label_at_the_max_boundary() -> None:
    nav_label = "a" * NAV_LABEL_MAX
    proposal = SectionProposalWire(
        sections=[
            SectionWire(
                title="Evidence aspect",
                focus="A focused evidence aspect.",
                nav_label=nav_label,
            )
        ]
    )
    sections, reasons, normalisations = _validate_sections(proposal, grouping_group_ids=None)
    assert reasons == []
    assert normalisations == []
    assert sections[0].nav_label == nav_label


def test_section_validation_rejects_an_over_long_nav_label_without_truncating() -> None:
    """rev 8 M5: nav_label is rejected at the boundary, never clamped."""
    nav_label = "a" * (NAV_LABEL_MAX + 1)
    proposal = SectionProposalWire(
        sections=[
            SectionWire(
                title="Evidence aspect",
                focus="A focused evidence aspect.",
                nav_label=nav_label,
            )
        ]
    )
    _sections, reasons, normalisations = _validate_sections(proposal, grouping_group_ids=None)
    assert len(reasons) == 1
    assert "nav_label_too_long" in reasons[0]
    assert normalisations == []


def test_section_validation_allows_an_omitted_nav_label() -> None:
    proposal = SectionProposalWire(
        sections=[
            SectionWire(title="Evidence aspect", focus="A focused evidence aspect.")
        ]
    )
    sections, reasons, _normalisations = _validate_sections(proposal, grouping_group_ids=None)
    assert reasons == []
    assert sections[0].nav_label is None


def test_section_validation_rejects_a_blank_nav_label() -> None:
    proposal = SectionProposalWire(
        sections=[
            SectionWire(
                title="Evidence aspect",
                focus="A focused evidence aspect.",
                nav_label="   ",
            )
        ]
    )
    _sections, reasons, _normalisations = _validate_sections(proposal, grouping_group_ids=None)
    assert len(reasons) == 1
    assert "nav_label_invalid" in reasons[0]


def test_transitive_resolution_from_grouping_reference(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Grouping doc")
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": [pss_id]},
    )
    _, _, selection_run_id = run_select(conn, project_id, scope_id, characterisation_run_id)

    extraction_run_id = seed_run(conn, project_id)
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "fingerprint": "t",
                "profiles": {IOF_PROFILE_ID: {"fingerprint": "t"}},
            },
            docs=[],
            counts={"findings": {"total": 0}},
            flags={},
            created_at=now(),
        )
    )
    grouping_run_id = seed_run(conn, project_id)
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=grouping_run_id,
            extraction_run_id=extraction_run_id,
            grouping_provenance={"facets": ["intervention"]},
            groups={"intervention": {"groups": [], "ungrouped": {}, "no_value": {}}},
            counts={"intervention": {}},
            flags={"intervention": []},
            created_at=now(),
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        grouping_run_id=grouping_run_id,
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.characterisation_run_id == characterisation_run_id
    assert row.selection_run_id == selection_run_id
    assert row.extraction_run_id == extraction_run_id
    how_resolved = row.synthesis_provenance["resolved_references"]["how_resolved"]
    assert how_resolved["grouping"] == "explicit"
    assert how_resolved["extraction"] == "transitive:grouping"
    assert how_resolved["selection"] == "transitive:extraction"
    assert how_resolved["characterisation"] == "transitive:selection"


def test_missing_referenced_row_fails_structurally(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    with pytest.raises(SynthesiseFailure, match="missing_referenced_row"):
        _run_synthesise(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            selection_run_id=uuid.uuid4(),
        )

    assert _count(conn, artefact, project_id) == 0


def test_artefact_records_walkable_conversation_plan_run_lineage(conn: Connection) -> None:
    """A stub synthesis preserves the row-grain lineage without fabricating legacy links."""
    project_id, run_id = seed_project_and_run(conn)
    conversation_id = uuid.uuid4()
    now_at = now()
    conn.execute(
        conversation.insert().values(
            id=conversation_id,
            project_id=project_id,
            kind="planning",
            title="Planning",
            entry_artefact_id=None,
            status="active",
            created_at=now_at,
            closed_at=None,
            archived_at=None,
        )
    )
    plan = OrchestrationPlan(
        title="Lineage test plan",
        question="What evidence supports the test intervention?",
        backend_scope="both",
        search_effort="rapid",
        analysis_depth="landscape",
        components=[],
        component_rationale={},
        steering_mode="moderate",
    )
    scope_id, plan_id = persist_approved_plan(
        conn,
        project_id=project_id,
        plan=plan,
        conversation_id=conversation_id,
    )
    capability_run_id = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=capability_run_id,
            project_id=project_id,
            evidence_scope_id=scope_id,
            capability="evidence_base",
            plan_id=plan_id,
            plan_version=1,
            status="running",
            session_id=None,
            started_at=now_at,
            ended_at=None,
        )
    )
    conn.execute(
        update(runs)
        .where(runs.c.run_id == run_id)
        .where(runs.c.project_id == project_id)
        .values(capability_run_id=capability_run_id)
    )
    seed_select_doc(conn, project_id, run_id, scope_id, title="Lineage source")

    summary = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
    )
    lineage = conn.execute(
        select(
            conversation.c.id,
            orchestration_plan.c.plan_id,
            capability_run.c.capability_run_id,
            artefact.c.capability_run_id,
        )
        .join(orchestration_plan, orchestration_plan.c.conversation_id == conversation.c.id)
        .join(
            capability_run,
            (capability_run.c.plan_id == orchestration_plan.c.plan_id)
            & (capability_run.c.plan_version == orchestration_plan.c.version),
        )
        .join(artefact, artefact.c.capability_run_id == capability_run.c.capability_run_id)
        .where(artefact.c.artefact_id == uuid.UUID(summary["artefact_id"]))
    ).one()
    assert lineage == (conversation_id, plan_id, capability_run_id, capability_run_id)

    legacy_plan_id = uuid.uuid4()
    legacy_artefact_id = uuid.uuid4()
    conn.execute(
        orchestration_plan.insert().values(
            plan_id=legacy_plan_id,
            project_id=project_id,
            conversation_id=None,
            evidence_scope_id=scope_id,
            version=2,
            status="superseded",
            payload=plan.model_dump(mode="json"),
            created_at=now_at,
            created_by="user",
            approved_at=now_at,
        )
    )
    conn.execute(
        artefact.insert().values(
            artefact_id=legacy_artefact_id,
            project_id=project_id,
            capability_run_id=None,
            title="Legacy artefact",
            created_at=now_at,
        )
    )
    assert conn.execute(
        select(orchestration_plan.c.conversation_id).where(
            orchestration_plan.c.plan_id == legacy_plan_id
        )
    ).scalar_one() is None
    assert conn.execute(
        select(artefact.c.capability_run_id).where(artefact.c.artefact_id == legacy_artefact_id)
    ).scalar_one() is None


def test_unmatched_retrieval_boost_recorded_never_fatal(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Boost doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=["Boost doc evidence chunk one.", "Boost doc evidence chunk two."],
    )

    summary = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        context={"synthesis": {"retrieval_boosts": {"tags": {"no-such-tag": 5}}}},
    )

    assert summary["artefact_id"]
    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    unmatched = row.synthesis_provenance["retrieval_scope"]["unmatched_boosts"]
    assert "no-such-tag" in unmatched.get("tags", [])


def test_determinism_two_runs_identical_content(conn: Connection) -> None:
    project_id, run_id_1 = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    summary_1 = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id_1,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )
    run_id_2 = seed_run(conn, project_id)
    summary_2 = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id_2,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )

    rows = conn.execute(
        select(synthesis_result)
        .where(synthesis_result.c.project_id == project_id)
        .order_by(synthesis_result.c.run_id)
    ).all()
    assert len(rows) == 2
    row_by_run = {row.run_id: row for row in rows}
    row_1 = row_by_run[run_id_1]
    row_2 = row_by_run[run_id_2]
    assert row_1.artefact_id != row_2.artefact_id

    def ordered_block_rows(row: Any) -> list[Any]:
        block_ids = [uuid.UUID(str(entry["block_id"])) for entry in row.blocks]
        rows_by_id = {
            r.block_id: r
            for r in conn.execute(select(block).where(block.c.block_id.in_(block_ids)))
        }
        return [rows_by_id[bid] for bid in block_ids]

    blocks_1 = ordered_block_rows(row_1)
    blocks_2 = ordered_block_rows(row_2)
    assert [b.content for b in blocks_1] == [b.content for b in blocks_2]
    assert [b.content_hash for b in blocks_1] == [b.content_hash for b in blocks_2]
    assert row_1.counts == row_2.counts
    assert summary_1["counts"] == summary_2["counts"]


def test_directive_sections_and_malformed_directive(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
        context={
            "synthesis": {
                "sections": [
                    {
                        "title": "Housing outcomes in the corpus",
                        "focus": "What the corpus reports",
                    }
                ]
            }
        },
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.synthesis_provenance["section_set"]["source"] == "scope_context"
    assert row.blocks[0]["title"] == "Housing outcomes in the corpus"

    run_id_2 = seed_run(conn, project_id)
    with pytest.raises(SynthesiseFailure, match="synthesis_directive_invalid"):
        _run_synthesise(
            conn,
            project_id=project_id,
            run_id=run_id_2,
            scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
            context={"synthesis": {"bogus": 1}},
        )

    assert _count(conn, artefact, project_id) == 1


def test_selection_provenance_without_characterisation_ref_fails(conn: Connection) -> None:
    from policy_atlas.core.schema import selection_result

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    selection_run_id = seed_run(conn, project_id)
    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=selection_run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[],
            excluded={},
            flags={},
            created_at=now(),
        )
    )

    with pytest.raises(SynthesiseFailure, match="selection_provenance_invalid"):
        _run_synthesise(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            selection_run_id=selection_run_id,
        )

    assert _count(conn, artefact, project_id) == 0


class _BoundarySpanBackend(ScriptedSynthesisBackend):
    """Local backend: turn 1 searches chunks, turn 2 cites a boundary-spanning quote.

    Ids are only known once ``search_chunks`` executes at run time, so the
    citation is built from the transcript rather than scripted in advance.
    """

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        del force_emit
        # The code-injected conclusions section (ADR 0015 §8) is not part of
        # this double's scenario — emit nothing for it.
        if seed.get("section_index", 0) != 0:
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
        if not transcript:
            return {
                "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "rate"}}],
                "claims": None,
            }, None
        chunks = transcript[0]["result"]["chunks"]
        chunk_id = chunks[0]["chunk_record_id"]
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="chunk",
                        text="The rate fell after the programme began (stub).",
                        citations=[
                            ChunkCitationWire(
                                chunk_record_id=chunk_id,
                                quote="after the programme",
                            )
                        ],
                    )
                ]
            ),
        }, None


def test_boundary_spanning_quote_writes_row_per_chunk(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Boundary doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=["The rate fell sharply after", "the programme began in 2019."],
    )

    backend = _BoundarySpanBackend(
        proposal=SectionProposalWire(
            sections=[
                SectionWire(title="Rate change evidence", focus="What changed and when"),
            ]
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=backend,
    )

    assert _count(conn, citation, project_id) == 2
    citation_rows = conn.execute(
        select(citation.c.chunk_id, citation.c.quote).where(
            citation.c.annotation_id.in_(
                select(annotation.c.annotation_id).where(
                    annotation.c.block_id.in_(
                        select(block.c.block_id).where(
                            block.c.artefact_id.in_(
                                select(artefact.c.artefact_id).where(
                                    artefact.c.project_id == project_id
                                )
                            )
                        )
                    )
                )
            )
        )
    ).all()
    assert len(citation_rows) == 2
    assert citation_rows[0].quote == citation_rows[1].quote == "after the programme"
    assert citation_rows[0].chunk_id != citation_rows[1].chunk_id

    chunk_payloads = [
        payload
        for payload in _project_annotations(conn, project_id)
        if payload.get("claim_type") == "chunk"
    ]
    assert len(chunk_payloads) == 1
    spans = chunk_payloads[0]["citations"][0]["spans"]
    assert len(spans) == 2
    chunk_ids_in_spans = {span["chunk_id"] for span in spans}
    assert len(chunk_ids_in_spans) == 2
    for span in spans:
        assert "start" in span and "end" in span


def test_judge_persistence_keys_on_cited_claims_only(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Judge doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=[
            "Judge doc evidence says alpha quoted evidence appears here.",
            "Further judge doc evidence appears in a second chunk.",
        ],
    )

    _run_synthesise(conn, project_id=project_id, run_id=run_id, scope_id=scope_id)

    payloads = _project_annotations(conn, project_id)
    chunk_payloads = [p for p in payloads if p.get("claim_type") == "chunk"]
    assert chunk_payloads
    for payload in chunk_payloads:
        assert "verdict" in payload
        assert "weakly_grounded" in payload
        assert "rationale" in payload
        assert "judge_model" in payload
        assert "judge_prompt_version" in payload
        assert "envelope_version" in payload
        assert isinstance(payload["segmentation_policies"], dict)
        cited_chunk_ids = {
            citation["cited_chunk_record_id"] for citation in payload["citations"]
        }
        assert set(payload["segmentation_policies"]) <= cited_chunk_ids
        assert all(
            value == "manual_v1" for value in payload["segmentation_policies"].values()
        )
        assert "judge_io_ref" in payload

    gap_payloads = [p for p in payloads if p.get("claim_type") == "gap"]
    assert gap_payloads
    for payload in gap_payloads:
        assert "verdict" not in payload


def test_provenance_required_keys(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    provenance = row.synthesis_provenance

    prompt_versions = provenance["prompt_versions"]
    assert set(prompt_versions) >= {"sections", "section", "judge", "tool_schemas"}

    assert "models" in provenance
    assert "envelope_policy_version" in provenance
    assert "backend_modes" in provenance
    assert "call_counts" in provenance
    assert "generation_budget_max" in provenance
    assert "substrate_profile" in provenance
    assert "resolved_references" in provenance

    retrieval_scope = provenance["retrieval_scope"]
    assert retrieval_scope["reranker"] == "none"

    assert "source" in provenance["section_set"]

    caps = provenance["caps"]
    assert set(caps) == {
        "SECTION_CAP",
        "SECTION_TURN_CAP",
        "SYNTH_CHUNK_TOP_K",
        "SYNTH_CHUNK_CHAR_BUDGET",
        "RETRIEVAL_UNIT_CAP",
        "REPAIR_ROUND_CAP",
    }

    sections = provenance["sections"]
    assert sections
    for section in sections:
        assert "tool_call_counts" in section
        assert "gathered_id_hash" in section

    assert "inherited_chain_base" in provenance
    assert "directive" in provenance


def test_delete_project_data_after_synthesise(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Delete-safe doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=[
            "Delete-safe doc evidence chunk one appears here.",
            "Delete-safe doc evidence chunk two appears here too.",
        ],
    )

    _run_synthesise(conn, project_id=project_id, run_id=run_id, scope_id=scope_id)
    assert _count(conn, synthesis_result, project_id) == 1
    assert _count(conn, artefact, project_id) == 1

    delete_project_data(conn, project_id)

    assert _count(conn, synthesis_result, project_id) == 0
    assert _count(conn, artefact, project_id) == 0


class _GapCorpusAbsenceBackend(ScriptedSynthesisBackend):
    """Local backend: immediately emits one corpus_absence gap claim."""

    def __init__(self, coverage_record_id: str) -> None:
        super().__init__(
            proposal=SectionProposalWire(
                sections=[SectionWire(title="Corpus coverage", focus="What the search covered")]
            )
        )
        self._coverage_record_id = coverage_record_id

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        del seed, transcript, force_emit
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="gap",
                        text="No further evidence on this topic was located (stub).",
                        gap=GapPayloadWire(
                            grade="corpus_absence",
                            coverage_base="screened",
                            coverage_record_id=self._coverage_record_id,
                        ),
                    )
                ]
            ),
        }, None


def test_gap_corpus_caveat_and_degradation(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    adequate_record_id = uuid.uuid4()
    acquired_run_id_1 = seed_run(conn, project_id)
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=adequate_record_id,
            evidence_scope_id=scope_id,
            project_id=project_id,
            acquired_by_run_id=acquired_run_id_1,
            backends=[{"backend": "openalex", "trust_class": "curated", "mode": "fixture"}],
            scope_filters={},
            stop_condition="breadth_truncated",
            adequacy_verdict="adequate",
            verdict_origin="model",
            created_at=now(),
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
        backend=_GapCorpusAbsenceBackend(str(adequate_record_id)),
    )

    payloads = _project_annotations(conn, project_id)
    gap_payloads = [p for p in payloads if p.get("claim_type") == "gap"]
    assert gap_payloads
    caveat = gap_payloads[0]["gap"]["caveat"]
    assert caveat["adequacy_verdict"] == "adequate"
    assert caveat["verdict_origin"] == "model"
    assert caveat["search_space"] == [
        {"backend": "openalex", "trust_class": "curated", "mode": "fixture"}
    ]

    # Second case: an inadequate coverage record degrades the claim, never drops it.
    inadequate_record_id = uuid.uuid4()
    acquired_run_id_2 = seed_run(conn, project_id)
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=inadequate_record_id,
            evidence_scope_id=scope_id,
            project_id=project_id,
            acquired_by_run_id=acquired_run_id_2,
            backends=[{"backend": "openalex", "trust_class": "curated", "mode": "fixture"}],
            scope_filters={},
            stop_condition="breadth_truncated",
            adequacy_verdict="inadequate",
            verdict_origin="model",
            created_at=now(),
        )
    )
    run_id_2 = seed_run(conn, project_id)

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id_2,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
        backend=_GapCorpusAbsenceBackend(str(inadequate_record_id)),
    )

    row = conn.execute(
        select(synthesis_result)
        .where(synthesis_result.c.project_id == project_id)
        .where(synthesis_result.c.run_id == run_id_2)
    ).one()
    assert row.counts["gap_claims_degraded"] >= 1

    degraded_payloads = [
        p
        for p in _project_annotations(conn, project_id)
        if p.get("claim_type") == "gap" and p.get("gap", {}).get("degraded")
    ]
    assert degraded_payloads
    assert degraded_payloads[0]["gap"]["grade"] == "inferred"


def test_corpus_profile_excludes_demoted_doc(conn: Connection) -> None:
    """_load_corpus_profile reads the effective row: a stage-2-demoted doc's
    stale stage-1 'relevant' row must never be counted (task 014 sweep)."""
    from policy_atlas.evidence_base.synthesis.synthesise import _load_corpus_profile

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    seed_select_doc(conn, project_id, run_id, scope_id, title="confirmed")

    _, demoted_pss = seed_source(conn, project_id, meta={"title": "demoted"})
    seed_screening_result(
        conn, project_id, run_id, scope_id, demoted_pss, status="relevant", screen_stage=1
    )
    seed_screening_result(
        conn, project_id, run_id, scope_id, demoted_pss, status="not_relevant", screen_stage=2
    )

    profile = _load_corpus_profile(conn, project_id=project_id, scope_id=scope_id)
    assert profile.screened_docs == 1


def test_screened_chunks_excludes_demoted_doc(conn: Connection) -> None:
    """_load_screened_chunks reads the effective row — a second, previously raw
    source_screening_result consumer found during the task 014 sweep."""
    from policy_atlas.evidence_base.synthesis.synthesise import _load_screened_chunks

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    confirmed_pss = seed_select_doc(conn, project_id, run_id, scope_id, title="confirmed")
    seed_ingested_full_text(conn, pss_id=confirmed_pss, chunks=["Confirmed doc body."])

    _, demoted_pss = seed_source(conn, project_id, meta={"title": "demoted"})
    seed_screening_result(
        conn, project_id, run_id, scope_id, demoted_pss, status="relevant", screen_stage=1
    )
    seed_screening_result(
        conn, project_id, run_id, scope_id, demoted_pss, status="not_relevant", screen_stage=2
    )
    seed_ingested_full_text(conn, pss_id=demoted_pss, chunks=["Demoted doc body."])

    _chunk_by_id, chunks_by_pss, _basis_by_pss = _load_screened_chunks(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        selected_pss_ids=set(),
        appraised_pss_ids=set(),
    )
    assert str(confirmed_pss) in chunks_by_pss
    assert str(demoted_pss) not in chunks_by_pss


def test_groups_unsectioned_counted(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Grouping doc")
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": [pss_id]},
    )
    _, _, selection_run_id = run_select(conn, project_id, scope_id, characterisation_run_id)

    extraction_run_id = seed_run(conn, project_id)
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "fingerprint": "t",
                "profiles": {IOF_PROFILE_ID: {"fingerprint": "t"}},
            },
            docs=[],
            counts={"findings": {"total": 0}},
            flags={},
            created_at=now(),
        )
    )
    grouping_run_id = seed_run(conn, project_id)
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=grouping_run_id,
            extraction_run_id=extraction_run_id,
            grouping_provenance={"facets": ["intervention"]},
            groups={
                "intervention": {
                    "groups": [
                        {
                            "group_id": "intervention:g01",
                            "facet": "intervention",
                            "label": "L",
                            "description": "D",
                            "member_values": [],
                            "member_finding_ids": [],
                            "size": 0,
                            "direction_spread": {},
                        }
                    ],
                    "ungrouped": {},
                    "no_value": {},
                }
            },
            counts={"intervention": {}},
            flags={"intervention": []},
            created_at=now(),
        )
    )

    backend = StubSynthesisBackend(
        proposal=SectionProposalWire(
            sections=[SectionWire(title="Grouping coverage", focus="What the groups cover")]
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        grouping_run_id=grouping_run_id,
        backend=backend,
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.counts["groups_unsectioned"] == 1
    assert row.flags.get("groups_unsectioned") is True


def test_fresh_single_facet_group_shape_is_consumed_by_synthesise(
    conn: Connection,
) -> None:
    project_id, synthesis_run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {"intervention": "Alpha coaching", "outcome": "Attendance"},
                    {"intervention": "Alpha counselling", "outcome": "Retention"},
                ],
            )
        ],
    )
    # seed_extraction's selection row carries a bare test provenance; synthesise
    # resolves selection -> characterisation, so complete the chain here.
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn, project_id, scope_id, characterisation_run_id, themes={"theme-a": []}
    )
    conn.execute(
        update(selection_result)
        .where(selection_result.c.run_id == seeded.selection_run_id)
        .values(
            selection_provenance={
                "strategy": "test",
                "characterisation_run_id": str(characterisation_run_id),
            }
        )
    )
    _summary, grouping_run_id = _run_group_component(
        conn, project_id, scope_id, seeded.run_id
    )
    grouping_row = _group_row(conn, project_id, grouping_run_id)
    facet_payload = grouping_row["groups"]["intervention"]
    group_id = facet_payload["groups"][0]["group_id"]

    assert group_id == "intervention:g01"
    assert grouping_row["counts"]["intervention"]["groups"] == 1

    backend = StubSynthesisBackend(
        proposal=SectionProposalWire(
            sections=[
                SectionWire(
                    title="Alpha services",
                    focus="Evidence on Alpha service findings.",
                    group_ids=[group_id],
                )
            ]
        )
    )
    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=synthesis_run_id,
        scope_id=scope_id,
        extraction_run_id=seeded.run_id,
        grouping_run_id=grouping_run_id,
        backend=backend,
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    section_blocks = [b for b in row.blocks if b.get("title") == "Alpha services"]
    assert len(section_blocks) == 1
    assert section_blocks[0]["group_ids"] == [group_id]
    assert row.counts["groups_total"] == 1
    assert row.counts["groups_unsectioned"] == 0


def test_block_content_is_authored_prose_and_units_are_span_anchored(
    conn: Connection,
) -> None:
    """ADR 0015 §3/§7: the block content IS the authored prose, and every
    persisted addressable unit satisfies block.content[start:end] == unit.content.
    The content is more than the bare "\\n\\n" join of claim texts (the stub
    splices a connective sentence between claims)."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )

    block_rows = conn.execute(
        select(block).where(
            block.c.artefact_id.in_(
                select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
            )
        )
    ).all()
    assert block_rows
    saw_multi_claim_block = False
    for block_row in block_rows:
        unit_rows = conn.execute(
            select(addressable_unit).where(addressable_unit.c.block_id == block_row.block_id)
        ).all()
        assert unit_rows
        # content_hash is over the block content (the authored prose).
        assert block_row.content_hash == content_hash(block_row.content)
        # Every unit's locator round-trips into the block content.
        for unit_row in unit_rows:
            start = int(unit_row.locator["start"])
            end = int(unit_row.locator["end"])
            assert block_row.content[start:end] == unit_row.content
        # The block content is NOT the bare join of the claim unit texts — the
        # prose carries connective tissue between claims (ADR 0015).
        claim_units = sorted(unit_rows, key=lambda u: int(u.locator["start"]))
        if len(claim_units) > 1:
            saw_multi_claim_block = True
            assert block_row.content != "\n\n".join(u.content for u in claim_units)
    assert saw_multi_claim_block


# --- ADR 0015: span-bind repair lane + unspanned-assertion plumbing ---


class _SpanBindBackend(ScriptedSynthesisBackend):
    """Emits a single reasoning claim whose text is NOT a substring of the
    prose (a span-bind failure), then repairs it with a rewritten claim text
    that is/ isn't present in the (unchanged) prose."""

    _PROSE = "Alpha reasoning sentence. Beta reasoning sentence."

    def __init__(self, *, repair_text: str) -> None:
        super().__init__(
            proposal=SectionProposalWire(
                sections=[SectionWire(title="Span bind evidence", focus="What binds")]
            )
        )
        self._repair_text = repair_text

    def section_turn(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
    ) -> UsageResult[SectionTurn]:
        del transcript, force_emit
        # The code-injected conclusions section (ADR 0015 §8) is outside this
        # double's span-bind scenario — emit nothing for it.
        if seed.get("section_index", 0) != 0:
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
        return {
            "tool_calls": [],
            "claims": SectionProseWire(
                prose=self._PROSE,
                claims=[
                    ClaimWire(
                        claim_type="reasoning",
                        text="GAMMA sentence absent from the prose.",
                    )
                ],
            ),
        }, None

    def repair_section(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, failing: list[dict[str, Any]]
    ) -> UsageResult[SectionRepairWire]:
        del seed, transcript
        claim_id = str(failing[0]["claim_id"])
        return SectionRepairWire(
            repairs=[
                RepairItemWire(
                    claim_id=claim_id,
                    replacement_segment="",
                    claim=ClaimWire(claim_type="reasoning", text=self._repair_text),
                )
            ]
        ), None


def test_span_not_found_repairs_and_rebinds_into_unchanged_prose(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn, project_id, scope_id, characterisation_run_id, themes={"theme-a": []}
    )

    # The repair rewrites the claim to a sentence that IS a substring of the prose.
    summary = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
        backend=_SpanBindBackend(repair_text="Alpha reasoning sentence."),
    )

    assert summary["counts"]["span_bind_failures"] == 0
    # Two blocks now exist (the section + the empty code-injected conclusions);
    # target the section's block by its prose content.
    block_row = conn.execute(
        select(block).where(
            block.c.artefact_id.in_(
                select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
            ),
            block.c.content == _SpanBindBackend._PROSE,
        )
    ).one()
    # Prose is untouched by the span-bind lane.
    assert block_row.content == _SpanBindBackend._PROSE
    unit_rows = conn.execute(
        select(addressable_unit).where(addressable_unit.c.block_id == block_row.block_id)
    ).all()
    assert len(unit_rows) == 1
    unit = unit_rows[0]
    assert unit.content == "Alpha reasoning sentence."
    start, end = int(unit.locator["start"]), int(unit.locator["end"])
    assert block_row.content[start:end] == unit.content


def test_exhausted_span_bind_failure_is_counted_prose_untouched(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn, project_id, scope_id, characterisation_run_id, themes={"theme-a": []}
    )

    # The repair rewrites to a sentence STILL absent from the prose — the claim
    # is excluded (span_bind_failures) and the prose is left untouched.
    summary = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
        backend=_SpanBindBackend(repair_text="Still absent from the prose."),
    )

    assert summary["counts"]["span_bind_failures"] == 1
    assert summary["flags"].get("span_bind_failed") is True
    # Two blocks now exist (the section + the empty code-injected conclusions);
    # target the section's block by its prose content.
    block_row = conn.execute(
        select(block).where(
            block.c.artefact_id.in_(
                select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
            ),
            block.c.content == _SpanBindBackend._PROSE,
        )
    ).one()
    assert block_row.content == _SpanBindBackend._PROSE
    # No claim survived — no addressable unit was minted (both blocks empty of units).
    assert _count(conn, addressable_unit, project_id) == 0


class _UnspannedJudge(StubGroundingJudgeBackend):
    """The stub judge plus a bound + an unbound unspanned assertion, to exercise
    the flag-not-drop persistence lane (ADR 0015 §5)."""

    _BOUND = "the section observes the following"
    _UNBOUND = "THIS EXCERPT IS ABSENT FROM THE PROSE"

    def judge_block(self, envelope: dict[str, Any]) -> UsageResult[JudgeResponseWire]:
        response, usage = super().judge_block(envelope)
        prose = envelope.get("section_prose", "")
        extra: list[UnspannedAssertionWire] = []
        if isinstance(prose, str) and self._BOUND in prose:
            extra.append(
                UnspannedAssertionWire(excerpt=self._BOUND, rationale="bound excerpt")
            )
        extra.append(
            UnspannedAssertionWire(excerpt=self._UNBOUND, rationale="unbound excerpt")
        )
        return JudgeResponseWire(
            verdicts=response.verdicts, unspanned_assertions=extra
        ), usage


def test_unspanned_assertion_bound_minted_unbound_counted(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn, project_id, scope_id, characterisation_run_id, themes={"theme-a": []}
    )

    backend = StubSynthesisBackend(
        proposal=SectionProposalWire(
            sections=[SectionWire(title="Unspanned evidence", focus="What is asserted")]
        )
    )
    summary = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
        backend=backend,
        judge_backend=_UnspannedJudge(),
    )

    # Two blocks now carry stub claims (the proposed section + the code-injected
    # conclusions section, ADR 0015 §8); the judge flags the same bound + unbound
    # excerpt on each, so the run-level counts are two of each. The unbound
    # excerpt is absent from the prose, so it lands in unspanned_unlocated
    # (item 17(ii)).
    assert summary["counts"]["unspanned_assertions"] == 2
    assert summary["counts"]["unspanned_unlocated"] == 2
    assert summary["counts"]["unspanned_overlap_filtered"] == 0
    assert summary["counts"]["unspanned_duplicate_stale"] == 0
    assert summary["flags"].get("unspanned_assertions_present") is True

    block_ids = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
        )
    )
    block_contents = {
        row.block_id: row.content
        for row in conn.execute(
            select(block.c.block_id, block.c.content).where(block.c.block_id.in_(block_ids))
        )
    }
    unspanned_units = conn.execute(
        select(
            addressable_unit,
            annotation.c.payload,
            annotation.c.block_id,
        )
        .join(annotation, annotation.c.unit_id == addressable_unit.c.unit_id)
        .where(annotation.c.block_id.in_(block_ids))
        .where(annotation.c.annotation_type == "unspanned_assertion")
    ).all()
    # One bound excerpt minted per block; the unbound excerpt never binds.
    assert len(unspanned_units) == 2
    for row in unspanned_units:
        assert row.payload["rationale"] == "bound excerpt"
        assert row.content == _UnspannedJudge._BOUND
        start, end = int(row.locator["start"]), int(row.locator["end"])
        assert block_contents[row.block_id][start:end] == _UnspannedJudge._BOUND
    # The unbound excerpt minted no annotation in any block.
    assert all(
        _UnspannedJudge._UNBOUND not in content for content in block_contents.values()
    )


# --- ADR 0015 §8 / B-B3: conclusions + key-findings blocks ---


class _CapturingJudge(StubGroundingJudgeBackend):
    """Stub judge that records every envelope it is handed."""

    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[dict[str, Any]] = []

    def judge_block(self, envelope: dict[str, Any]) -> UsageResult[JudgeResponseWire]:
        self.envelopes.append(envelope)
        return super().judge_block(envelope)


def _blocks_by_role(row: Any) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for entry in row.blocks:
        grouped.setdefault(entry["role"], []).append(entry)
    return grouped


def test_conclusions_and_key_findings_composition(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Composition doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=[
            "Composition evidence says alpha quoted evidence appears here.",
            "Further composition evidence appears in a second chunk.",
        ],
    )
    judge = _CapturingJudge()

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        intent="What does the evidence say?",
        judge_backend=judge,
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()

    # Every roll-up block entry carries a role.
    assert all("role" in entry for entry in row.blocks)

    # Key-findings block leads the presentation order (shown first) and the
    # conclusions block is last.
    assert row.blocks[0]["role"] == "key_findings"
    assert row.blocks[0]["title"] == "Key findings"
    assert row.blocks[-1]["role"] == "conclusions"
    assert row.blocks[-1]["title"] == "Conclusions"
    assert row.counts["key_findings"] == {"present": True}

    # The conclusions focus is evidence-descriptive, never a recommendation.
    conclusions = _blocks_by_role(row)["conclusions"][0]
    assert "What this evidence amounts to against the question" in conclusions["focus"]
    assert "recommendations" in conclusions["focus"]

    # The key-findings block re-cites a section's chunk claim, verified anew.
    key_findings = _blocks_by_role(row)["key_findings"][0]
    assert key_findings["citations_verified"] >= 1

    # The judge saw the run intent and each block's section focus, including the
    # key-findings pass (section_focus == "key findings").
    assert judge.envelopes
    assert all(env["intent"] == "What does the evidence say?" for env in judge.envelopes)
    focuses = {env["section_focus"] for env in judge.envelopes}
    assert "key findings" in focuses

    # Provenance records the key-findings prompt version and its call counts.
    provenance = row.synthesis_provenance
    assert provenance["prompt_versions"]["key_findings"] == "synthesise_key_findings_v2"
    call_counts = provenance["call_counts"]
    assert call_counts["key_findings"] == 1
    assert call_counts["key_findings_judge"] >= 1


def test_key_findings_absence_path_mints_no_block(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Absence doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=["Absence evidence says alpha quoted evidence appears here."],
    )

    # The stub sentinel forces the no-headline emission even though a citable
    # chunk claim exists in the ledger.
    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        intent="stubnoheadline: what does the evidence say?",
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.counts["key_findings"] == {"present": False, "reason": "no_headline_claims"}
    assert all(entry["role"] != "key_findings" for entry in row.blocks)
    # The conclusions section still rides — the absence path is only the
    # key-findings block.
    assert any(entry["role"] == "conclusions" for entry in row.blocks)


class _UncitedKeyFindingsBackend(ScriptedSynthesisBackend):
    """Section 0 cites its own gathered chunk; the key-findings pass cites a
    chunk id no section cited — structurally uncitable, rejected + counted."""

    def __init__(self) -> None:
        super().__init__(
            proposal=SectionProposalWire(
                sections=[SectionWire(title="Uncited-union evidence", focus="What is gathered")]
            )
        )
        self.section0_chunk_id: str | None = None

    def section_turn(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
    ) -> UsageResult[SectionTurn]:
        del force_emit
        if seed.get("section_index", 0) != 0:
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
        chunks = [
            chunk
            for exchange in transcript
            if exchange["tool"] == "search_chunks"
            for chunk in exchange["result"].get("chunks", [])
        ]
        if not chunks:
            return {
                "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "evidence"}}],
                "claims": None,
            }, None
        chunk = next((record for record in chunks if record.get("appraised")), chunks[0])
        self.section0_chunk_id = chunk["chunk_record_id"]
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="chunk",
                        text="Section cites its own gathered chunk (stub).",
                        citations=[
                            ChunkCitationWire(
                                chunk_record_id=chunk["chunk_record_id"],
                                quote=chunk["content"][:20],
                            )
                        ],
                    )
                ]
            ),
        }, None

    def repair_section(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, failing: list[dict[str, Any]]
    ) -> UsageResult[SectionRepairWire]:
        del seed, transcript, failing
        # The uncitable claim cannot be repaired; the pass lands it as a counted
        # structural rejection.
        return SectionRepairWire(repairs=[]), None

    def write_key_findings(self, seed: dict[str, Any]) -> UsageResult[SectionProseWire]:
        return SectionProseWire(
            prose="Headline citing an uncited chunk id (stub).",
            claims=[
                ClaimWire(
                    claim_type="chunk",
                    text="Headline citing an uncited chunk id (stub).",
                    citations=[
                        ChunkCitationWire(
                            chunk_record_id="00000000-0000-0000-0000-000000000000",
                            quote="never gathered by any section",
                        )
                    ],
                )
            ],
        ), None


def test_key_findings_claim_citing_uncited_id_is_rejected_and_counted(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Union doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=["Union evidence says alpha quoted evidence appears here."],
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=_UncitedKeyFindingsBackend(),
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    # The key-findings block is minted (its prose is non-empty), but its claim
    # citing a chunk no section cited is rejected + counted — never persisted.
    assert row.counts["key_findings"]["present"] is True
    assert row.counts["claims_rejected_structural"] >= 1
    assert row.flags.get("claims_rejected_structural") is True
    # Exactly the one section chunk claim survives (not the uncited key-findings one).
    assert row.counts["claims_total"].get("chunk", 0) == 1


# --- Task 020 Phase C: writer-envelope carriage of effect_basis/study_geography ---


def _seed_iof_row(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    snap_id: uuid.UUID,
    pss_id: uuid.UUID,
    record_id: uuid.UUID,
    finding_id: uuid.UUID,
    extraction_fingerprint: str,
    **overrides: Any,
) -> None:
    """Insert one source_extraction_record + intervention_outcome_finding pair.

    Minimal, non-memo-shaped fixture for direct ``_load_findings`` unit tests
    (no selection/characterisation/grouping scaffolding required).
    """
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=record_id,
            project_id=project_id,
            source_snapshot_id=snap_id,
            project_source_snapshot_id=pss_id,
            extraction_fingerprint=extraction_fingerprint,
            status="extracted",
            basis="full_text",
            error=None,
            finding_count=1,
            run_id=run_id,
            created_at=now(),
        )
    )
    values: dict[str, Any] = {
        "finding_id": finding_id,
        "project_id": project_id,
        "extraction_record_id": record_id,
        "intervention": "Alpha",
        "outcome": "Outcome",
        "population": None,
        "comparator": None,
        "effect_direction": "increase",
        "estimate_level": "study",
        "study_design": None,
        "study_geography": None,
        "stratum_qualifiers": [],
        "statistics": {},
        "causality_by_design": None,
        "effect_basis": None,
        "is_primary": None,
        "is_prevalence_only": None,
        "field_coverage": {},
        "grounding": [],
        "created_at": now(),
    }
    values.update(overrides)
    conn.execute(intervention_outcome_finding.insert().values(**values))


def test_load_findings_carries_effect_basis_and_study_geography(conn: Connection) -> None:
    """Task 020 C2: synthesise's own read path (``_load_findings``) carries the
    two new finding-grain fields through to the substrate record — the same
    carriage pinned for ``query_findings`` in test_synthesis_tools.py."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Geo doc"})
    record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    _seed_iof_row(
        conn,
        project_id=project_id,
        run_id=run_id,
        snap_id=snap_id,
        pss_id=pss_id,
        record_id=record_id,
        finding_id=finding_id,
        extraction_fingerprint="fp-load-findings-carries",
        intervention="Coaching",
        outcome="Test scores",
        effect_basis="observed",
        study_geography="England",
    )

    findings, _icf_findings, _icf_available, _bases = _load_findings(
        conn,
        project_id=project_id,
        extraction_row={
            "extraction_provenance": {"profiles": {IOF_PROFILE_ID: {}}},
            "docs": [
                {"profiles": {IOF_PROFILE_ID: {"extraction_record_id": str(record_id)}}}
            ]
        },
    )

    record = findings[str(finding_id)].record
    assert record["effect_basis"] == "observed"
    assert record["study_geography"] == "England"


def test_load_findings_tolerates_v1_null_rows(conn: Connection) -> None:
    """Old-row tolerance (task 020 C2): a v1 row's NULL effect_basis/
    study_geography and a field_coverage dict lacking the new keys pass
    through as ``None`` — never a ``KeyError``."""
    project_id, run_id = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "V1 doc"})
    record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    _seed_iof_row(
        conn,
        project_id=project_id,
        run_id=run_id,
        snap_id=snap_id,
        pss_id=pss_id,
        record_id=record_id,
        finding_id=finding_id,
        extraction_fingerprint="fp-load-findings-v1",
        intervention="Coaching",
        outcome="Test scores",
        field_coverage={"study_design": "not_extracted"},
    )

    findings, _icf_findings, _icf_available, _bases = _load_findings(
        conn,
        project_id=project_id,
        extraction_row={
            "extraction_provenance": {"profiles": {IOF_PROFILE_ID: {}}},
            "docs": [
                {"profiles": {IOF_PROFILE_ID: {"extraction_record_id": str(record_id)}}}
            ]
        },
    )

    record = findings[str(finding_id)].record
    assert record["effect_basis"] is None
    assert record["study_geography"] is None
    assert "effect_basis" not in record["field_coverage"]
    assert "study_geography" not in record["field_coverage"]


def test_load_findings_batches_chunk_basis_query(conn: Connection) -> None:
    """013 review N+1 finding, task 020 C3 rider: ``_load_findings`` issues
    exactly ONE chunk query over the whole distinct-snapshot set — never one
    per snapshot — and every snapshot's ``BasisText`` output is unchanged: two
    chunked docs build from their chunks, and a third chunkless doc falls back
    to its already-selected envelope abstract at zero extra queries."""
    project_id, run_id = seed_project_and_run(conn)

    record_ids: list[uuid.UUID] = []
    expected_basis: dict[str, Any] = {}

    for index, chunks in enumerate([
        ["alpha chunk one.", "alpha chunk two."],
        ["beta chunk one."],
    ]):
        snap_id, pss_id = seed_source(conn, project_id, meta={"title": f"Doc {index}"})
        record_id = uuid.uuid4()
        finding_id = uuid.uuid4()
        record_ids.append(record_id)
        _seed_iof_row(
            conn,
            project_id=project_id,
            run_id=run_id,
            snap_id=snap_id,
            pss_id=pss_id,
            record_id=record_id,
            finding_id=finding_id,
            extraction_fingerprint=f"fp-batch-{index}",
        )
        chunk_pairs: list[tuple[str, str]] = []
        for seq, content in enumerate(chunks):
            chunk_id = uuid.uuid4()
            chunk_pairs.append((str(chunk_id), content))
            conn.execute(
                chunk_table.insert().values(
                    chunk_id=chunk_id,
                    source_snapshot_id=snap_id,
                    sequence=seq,
                    content=content,
                    content_hash=content_hash(content),
                    locator={},
                    segmentation_policy="manual_v1",
                    created_at=now(),
                )
            )
        expected_basis[str(snap_id)] = build_basis(chunk_pairs)

    # The chunkless doc: no chunk rows — falls back to the envelope metadata's
    # abstract, already selected by the findings query (zero extra queries).
    snap_id, pss_id = seed_source(
        conn, project_id, meta={"title": "Doc 2", "abstract": "The chunkless abstract."}
    )
    record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    record_ids.append(record_id)
    _seed_iof_row(
        conn,
        project_id=project_id,
        run_id=run_id,
        snap_id=snap_id,
        pss_id=pss_id,
        record_id=record_id,
        finding_id=finding_id,
        extraction_fingerprint="fp-batch-2",
    )
    expected_basis[str(snap_id)] = build_basis([(None, "The chunkless abstract.")])

    extraction_row = {
        "extraction_provenance": {"profiles": {IOF_PROFILE_ID: {}}},
        "docs": [
            {"profiles": {IOF_PROFILE_ID: {"extraction_record_id": str(rid)}}}
            for rid in record_ids
        ],
    }

    query_count = 0

    def _count_query(
        db_conn: Connection,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        del db_conn, cursor, statement, parameters, context, executemany
        nonlocal query_count
        query_count += 1

    event.listen(conn, "before_cursor_execute", _count_query)
    try:
        findings, _icf_findings, _icf_available, basis_by_snapshot = _load_findings(
            conn, project_id=project_id, extraction_row=extraction_row
        )
    finally:
        event.remove(conn, "before_cursor_execute", _count_query)

    # One statement for the findings-rows select, one batched chunk query over
    # the three distinct snapshots — never one chunk query per snapshot.
    assert query_count == 2
    assert len(findings) == 3
    assert set(basis_by_snapshot) == set(expected_basis)
    for snapshot_key, expected in expected_basis.items():
        actual = basis_by_snapshot[snapshot_key]
        assert actual.raw_text == expected.raw_text
        assert actual.segments == expected.segments


def _seed_group_with_findings(
    conn: Connection, findings: list[dict[str, Any]]
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    """Seed one screened+selected+characterised doc, N intervention_outcome_finding
    rows sharing one extraction record, and one grouping group holding every
    finding as a member — ready for a full ``synthesise_scope`` run.

    Args:
        conn: Open database connection.
        findings: Per-finding column overrides (merged onto shared defaults).

    Returns:
        ``(project_id, run_id, scope_id, extraction_run_id, grouping_run_id,
        finding_ids)``; ``finding_ids[i]`` corresponds to ``findings[i]``.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Finding doc")
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn, project_id, scope_id, characterisation_run_id, themes={"theme-a": [pss_id]}
    )
    _, _, selection_run_id = run_select(conn, project_id, scope_id, characterisation_run_id)

    snap_id = conn.execute(
        select(project_source_snapshot.c.source_snapshot_id).where(
            project_source_snapshot.c.project_source_snapshot_id == pss_id
        )
    ).scalar_one()

    extraction_run_id = seed_run(conn, project_id)
    record_id = uuid.uuid4()
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=record_id,
            project_id=project_id,
            source_snapshot_id=snap_id,
            project_source_snapshot_id=pss_id,
            extraction_fingerprint="fp-group-seed",
            status="extracted",
            basis="full_text",
            error=None,
            finding_count=len(findings),
            run_id=extraction_run_id,
            created_at=now(),
        )
    )

    finding_ids: list[uuid.UUID] = []
    direction_spread: Counter[str] = Counter()
    for overrides in findings:
        finding_id = uuid.uuid4()
        finding_ids.append(finding_id)
        values: dict[str, Any] = {
            "finding_id": finding_id,
            "project_id": project_id,
            "extraction_record_id": record_id,
            "intervention": "Alpha service",
            "outcome": "Outcome",
            "population": None,
            "comparator": None,
            "effect_direction": "increase",
            "estimate_level": "study",
            "study_design": None,
            "study_geography": None,
            "stratum_qualifiers": [],
            "statistics": {},
            "causality_by_design": None,
            "effect_basis": None,
            "is_primary": None,
            "is_prevalence_only": None,
            "field_coverage": {},
            "grounding": [],
            "created_at": now(),
        }
        values.update(overrides)
        conn.execute(intervention_outcome_finding.insert().values(**values))
        direction_spread[values["effect_direction"]] += 1

    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "profiles": {IOF_PROFILE_ID: {"fingerprint": "t"}}
            },
            docs=[
                {"profiles": {IOF_PROFILE_ID: {"extraction_record_id": str(record_id)}}}
            ],
            counts={
                "selected": 1,
                "profiles": {IOF_PROFILE_ID: {"findings": {"total": len(findings)}}},
            },
            flags={},
            created_at=now(),
        )
    )

    grouping_run_id = seed_run(conn, project_id)
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=grouping_run_id,
            extraction_run_id=extraction_run_id,
            grouping_provenance={"facets": ["intervention"]},
            groups={
                "intervention": {
                    "groups": [
                        {
                            "group_id": "intervention:g01",
                            "facet": "intervention",
                            "label": "alpha",
                            "description": "D",
                            "member_values": [],
                            "member_finding_ids": [str(fid) for fid in finding_ids],
                            "size": len(finding_ids),
                            "direction_spread": dict(direction_spread),
                        }
                    ],
                    "ungrouped": {},
                    "no_value": {},
                }
            },
            counts={"intervention": {}},
            flags={"intervention": []},
            created_at=now(),
        )
    )
    return project_id, run_id, scope_id, extraction_run_id, grouping_run_id, finding_ids


def _seed_group_with_iof_and_icf(
    conn: Connection,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="ICF doc")
    full_snapshot_id = seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=["Training gaps slowed Alpha service delivery."],
    )
    characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn, project_id, scope_id, characterisation_run_id, themes={"theme-a": [pss_id]}
    )
    _, _, selection_run_id = run_select(conn, project_id, scope_id, characterisation_run_id)

    extraction_run_id = seed_run(conn, project_id)
    iof_record_id = uuid.uuid4()
    icf_record_id = uuid.uuid4()
    for record_id, fingerprint in (
        (iof_record_id, "fp-synth-iof"),
        (icf_record_id, "fp-synth-icf"),
    ):
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                project_id=project_id,
                source_snapshot_id=full_snapshot_id,
                project_source_snapshot_id=pss_id,
                extraction_fingerprint=fingerprint,
                status="extracted",
                basis="full_text",
                error=None,
                finding_count=1,
                run_id=extraction_run_id,
                created_at=now(),
            )
        )
    iof_finding_id = uuid.uuid4()
    icf_finding_id = uuid.uuid4()
    conn.execute(
        intervention_outcome_finding.insert().values(
            finding_id=iof_finding_id,
            project_id=project_id,
            extraction_record_id=iof_record_id,
            intervention="Alpha service",
            outcome="Attendance",
            population=None,
            comparator=None,
            effect_direction="increase",
            estimate_level="study",
            study_design=None,
            study_geography=None,
            stratum_qualifiers=[],
            statistics={},
            causality_by_design=None,
            effect_basis=None,
            is_primary=None,
            is_prevalence_only=None,
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    conn.execute(
        implementation_context_finding.insert().values(
            finding_id=icf_finding_id,
            project_id=project_id,
            extraction_record_id=icf_record_id,
            context_type="barrier",
            claim="Training gaps slowed Alpha service delivery.",
            intervention="Alpha service",
            outcome=None,
            population=None,
            setting=None,
            study_geography=None,
            study_design=None,
            claim_level="study",
            claim_basis="studied",
            level="provider",
            resource_requirements=None,
            workforce_requirements="training",
            field_coverage={},
            grounding=[{"quote": "Training gaps slowed Alpha service delivery."}],
            created_at=now(),
        )
    )

    def _profile_counts() -> dict[str, Any]:
        return {
            "selected": 1,
            "extracted": 1,
            "no_findings": 0,
            "failed": 0,
            "fresh": 1,
            "reused": 0,
            "findings": {
                "total": 1,
                "quote_unverified": 0,
                "dedup_collapsed": 0,
                "invalid_dropped": 0,
            },
        }

    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "profiles": {
                    IOF_PROFILE_ID: {"fingerprint": "fp-synth-iof", "profile": IOF_PROFILE_ID},
                    ICF_PROFILE_ID: {"fingerprint": "fp-synth-icf", "profile": ICF_PROFILE_ID},
                },
                "pass_count": 1,
            },
            docs=[
                {
                    "pss_id": str(pss_id),
                    "basis": "full_text",
                    "profiles": {
                        IOF_PROFILE_ID: {
                            "status": "extracted",
                            "basis": "full_text",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(iof_record_id),
                            "order": 0,
                        },
                        ICF_PROFILE_ID: {
                            "status": "extracted",
                            "basis": "full_text",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(icf_record_id),
                            "order": 0,
                        },
                    },
                }
            ],
            counts={
                "selected": 1,
                "basis": {"full_text": 1, "abstract_only": 0},
                "profiles": {
                    IOF_PROFILE_ID: _profile_counts(),
                    ICF_PROFILE_ID: _profile_counts(),
                },
            },
            flags={},
            created_at=now(),
        )
    )

    grouping_run_id = seed_run(conn, project_id)
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=grouping_run_id,
            extraction_run_id=extraction_run_id,
            grouping_provenance={"facets": ["intervention"]},
            groups={
                "intervention": {
                    "groups": [
                        {
                            "group_id": "intervention:g01",
                            "facet": "intervention",
                            "label": "alpha",
                            "description": "D",
                            "member_values": ["Alpha service"],
                            "member_finding_ids": [str(iof_finding_id), str(icf_finding_id)],
                            "member_finding_kinds": ["iof", "icf"],
                            "member_counts": {"iof": 1, "icf": 1},
                            "size": 2,
                            "direction_spread": {"increase": 1},
                        }
                    ],
                    "ungrouped": {},
                    "no_value": {},
                }
            },
            counts={"intervention": {}},
            flags={"intervention": []},
            created_at=now(),
        )
    )
    return (
        project_id,
        run_id,
        scope_id,
        extraction_run_id,
        grouping_run_id,
        iof_finding_id,
        icf_finding_id,
    )


class _FindingClaimBackend(ScriptedSynthesisBackend):
    """Section 0 emits one finding claim citing a known finding id on its
    first turn, with no tool calls; every other section/pass emits nothing."""

    def __init__(self, *, proposal: SectionProposalWire, finding_id: str) -> None:
        super().__init__(proposal=proposal)
        self._finding_id = finding_id

    def section_turn(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
    ) -> UsageResult[SectionTurn]:
        del force_emit
        if seed.get("section_index", 0) != 0 or transcript:
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="finding",
                        text="Coaching raised test scores in the cited finding (stub).",
                        cited_finding_ids=[self._finding_id],
                    )
                ]
            ),
        }, None


def test_annotation_payload_excludes_finding_metadata_row_join_resolves(
    conn: Connection,
) -> None:
    """Adversarial finding 6 (owner 2026-07-12): a finding claim's annotation
    payload never embeds effect_basis/study_geography — the payload
    deliberately does not carry finding-record metadata; a reader resolves
    those fields for ``cited_finding_ids`` via the intervention_outcome_finding
    row join instead."""
    (
        project_id,
        run_id,
        scope_id,
        extraction_run_id,
        grouping_run_id,
        finding_ids,
    ) = _seed_group_with_findings(
        conn,
        [
            {
                "intervention": "Coaching",
                "outcome": "Test scores",
                "effect_direction": "increase",
                "effect_basis": "observed",
                "study_geography": "England",
            }
        ],
    )
    finding_id = finding_ids[0]

    backend = _FindingClaimBackend(
        proposal=SectionProposalWire(
            sections=[
                SectionWire(
                    title="Coaching",
                    focus="What coaching does",
                    group_ids=["intervention:g01"],
                )
            ]
        ),
        finding_id=str(finding_id),
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        backend=backend,
    )

    payloads = _project_annotations(conn, project_id)
    finding_payloads = [
        payload
        for payload in payloads
        if str(finding_id) in payload.get("cited_finding_ids", [])
    ]
    assert finding_payloads
    for payload in finding_payloads:
        assert "effect_basis" not in payload
        assert "study_geography" not in payload

    # The row join is the source of truth these fields resolve from.
    row = conn.execute(
        select(
            intervention_outcome_finding.c.effect_basis,
            intervention_outcome_finding.c.study_geography,
        ).where(intervention_outcome_finding.c.finding_id == finding_id)
    ).one()
    assert row.effect_basis == "observed"
    assert row.study_geography == "England"


class _SeedCapturingBackend:
    """Wraps a delegate backend, recording every section-loop seed by section index."""

    mode = "stub"

    def __init__(self, inner: SynthesisBackend) -> None:
        self._inner = inner
        self.seeds_by_section: dict[int, list[dict[str, Any]]] = {}
        self.key_findings_seeds: list[dict[str, Any]] = []

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
        section_budget: int | None = None,
    ) -> UsageResult[SectionProposalWire]:
        return self._inner.propose_sections(
            intent=intent,
            substrate=substrate,
            rejection=rejection,
            section_budget=section_budget,
        )

    def section_turn(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
    ) -> UsageResult[SectionTurn]:
        section_index = seed.get("section_index", 0)
        self.seeds_by_section.setdefault(
            section_index if isinstance(section_index, int) else 0, []
        ).append(seed)
        return self._inner.section_turn(seed, transcript, force_emit=force_emit)

    def repair_section(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, failing: list[dict[str, Any]]
    ) -> UsageResult[SectionRepairWire]:
        return self._inner.repair_section(seed, transcript, failing=failing)

    def write_key_findings(self, seed: dict[str, Any]) -> UsageResult[SectionProseWire]:
        self.key_findings_seeds.append(seed)
        return self._inner.write_key_findings(seed)

    def write_block_summary(self, seed: dict[str, Any]):  # type: ignore[no-untyped-def]
        return self._inner.write_block_summary(seed)

    def judge_summary(self, *, summary: str, detail: dict[str, Any]):  # type: ignore[no-untyped-def]
        return self._inner.judge_summary(summary=summary, detail=detail)


def test_key_findings_seed_carries_only_cited_only_chunk_content(conn: Connection) -> None:
    """022 rider 16: the key-findings seed's chunk_content_by_id is filtered
    to chunks cited by surviving claims — not the run's whole gathered union.

    Three chunks are ingested for one doc; the default stub backend's
    section loop cites at most one chunk claim per section (2 sections: the
    one directed section + the always-injected conclusions section), so at
    least one of the three chunks is gathered (returned by search_chunks)
    but never cited across the whole run."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Rider-16 doc")
    seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=[
            "Rider evidence chunk alpha reports on the policy outcome directly.",
            "Rider evidence chunk beta reports on a related policy outcome.",
            "Rider evidence chunk gamma reports on a further policy outcome.",
        ],
    )
    capture = _SeedCapturingBackend(StubSynthesisBackend())

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        context={
            "synthesis": {
                "sections": [{"title": "Evidence", "focus": "What the evidence shows."}]
            }
        },
        backend=capture,
    )

    assert len(capture.key_findings_seeds) == 1
    kf_chunk_content = capture.key_findings_seeds[0]["chunk_content_by_id"]

    # The run gathered all three chunks (each section's search_chunks call
    # returns every matching chunk), but at most two claims across the run's
    # two sections can cite a chunk — so filtering must have dropped at
    # least one gathered-but-uncited chunk from the key-findings seed.
    assert 0 < len(kf_chunk_content) < 3


def test_grouped_section_seed_member_findings_include_icf_records(
    conn: Connection,
) -> None:
    (
        project_id,
        run_id,
        scope_id,
        extraction_run_id,
        grouping_run_id,
        _iof_finding_id,
        icf_finding_id,
    ) = _seed_group_with_iof_and_icf(conn)
    capture = _SeedCapturingBackend(
        StubSynthesisBackend(
            script=[[{"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}]],
            proposal=SectionProposalWire(
                sections=[
                    SectionWire(
                        title="Alpha",
                        focus="Alpha coverage",
                        group_ids=["intervention:g01"],
                    )
                ]
            ),
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        backend=capture,
    )

    seed = capture.seeds_by_section[0][0]
    members = {finding["finding_id"]: finding for finding in seed["member_findings"]}
    assert members[str(icf_finding_id)]["kind"] == "icf"
    assert members[str(icf_finding_id)]["context_type"] == "barrier"


def test_section_seed_substrate_carries_no_membership_lists(conn: Connection) -> None:
    """022 rider 18 (F0 § DTO spec): prompt-facing characterisation themes and
    grouping groups carry id/label/description/size/spread — never membership
    UUID lists; residuals carry counts only."""
    (
        project_id,
        run_id,
        scope_id,
        extraction_run_id,
        grouping_run_id,
        _iof_finding_id,
        _icf_finding_id,
    ) = _seed_group_with_iof_and_icf(conn)
    capture = _SeedCapturingBackend(
        StubSynthesisBackend(
            script=[[{"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}]],
            proposal=SectionProposalWire(
                sections=[
                    SectionWire(
                        title="Alpha",
                        focus="Alpha coverage",
                        group_ids=["intervention:g01"],
                    )
                ]
            ),
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        backend=capture,
    )

    seed = capture.seeds_by_section[0][0]
    substrate = seed["substrate"]

    theme = substrate["characterisation"]["themes"][0]
    assert "member_ids" not in theme
    assert {"theme_id", "name", "description", "size"} <= set(theme)

    group = substrate["grouping"]["groups"][0]
    assert "member_finding_ids" not in group
    assert {"group_id", "facet", "label", "description", "size", "direction_spread"} <= set(
        group
    )

    residual = substrate["grouping"]["residuals"]["intervention"]
    assert residual["ungrouped"] == {"count": 0}
    assert "finding_ids" not in residual["ungrouped"]
    assert "member_finding_ids" not in residual["ungrouped"]


def test_icf_finding_claim_annotation_resolves_via_row(
    conn: Connection,
) -> None:
    (
        project_id,
        run_id,
        scope_id,
        extraction_run_id,
        grouping_run_id,
        _iof_finding_id,
        icf_finding_id,
    ) = _seed_group_with_iof_and_icf(conn)
    backend = _FindingClaimBackend(
        proposal=SectionProposalWire(
            sections=[
                SectionWire(
                    title="Alpha",
                    focus="Alpha coverage",
                    group_ids=["intervention:g01"],
                )
            ]
        ),
        finding_id=str(icf_finding_id),
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        backend=backend,
    )

    payloads = _project_annotations(conn, project_id)
    finding_payloads = [
        payload
        for payload in payloads
        if str(icf_finding_id) in payload.get("cited_finding_ids", [])
    ]
    assert finding_payloads
    payload = finding_payloads[0]
    assert payload["cited_finding_kinds"] == ["icf"]
    assert payload["anchors"][0]["kind"] == "icf"
    assert payload["anchors"][0]["match_status"] == "exact"
    assert "context_type" not in payload
    assert "claim" not in payload


def test_mixed_and_unclear_findings_survive_synthesise_section_seed(
    conn: Connection,
) -> None:
    """V2 silent-zeroing autopsy (task 020 C7): mixed/unclear findings are
    group members like any other and must reach the section-loop seed's
    ``member_findings`` list and ``computed_spread`` — never dropped at
    synthesise's aggregation step."""
    (
        project_id,
        run_id,
        scope_id,
        extraction_run_id,
        grouping_run_id,
        finding_ids,
    ) = _seed_group_with_findings(
        conn,
        [
            {
                "intervention": "Alpha service",
                "outcome": "Outcome A",
                "effect_direction": "mixed",
            },
            {
                "intervention": "Alpha service",
                "outcome": "Outcome B",
                "effect_direction": "unclear",
            },
        ],
    )
    mixed_id, unclear_id = finding_ids

    capture = _SeedCapturingBackend(
        StubSynthesisBackend(
            script=[[{"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}]],
            proposal=SectionProposalWire(
                sections=[
                    SectionWire(
                        title="Alpha",
                        focus="Alpha coverage",
                        group_ids=["intervention:g01"],
                    )
                ]
            ),
        )
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        backend=capture,
    )

    seed = capture.seeds_by_section[0][0]
    member_directions = {
        finding["finding_id"]: finding["effect_direction"] for finding in seed["member_findings"]
    }
    assert member_directions[str(mixed_id)] == "mixed"
    assert member_directions[str(unclear_id)] == "unclear"
    assert seed["computed_spread"] == {"mixed": 1, "unclear": 1}


# --- propose_synthesis_plan (022 F5 steer surface) ---


def _runs_count(conn: Connection, project_id: uuid.UUID) -> int:
    return int(
        conn.execute(
            select(func.count()).select_from(runs).where(runs.c.project_id == project_id)
        ).scalar_one()
    )


def test_propose_synthesis_plan_is_side_effect_free(conn: Connection) -> None:
    """propose_synthesis_plan mints no artefact and writes no row (contract item 14)."""
    project_id, _run_id, scope_id, extraction_run_id, grouping_run_id, _finding_ids = (
        _seed_group_with_findings(conn, [{"intervention": "Alpha service"}])
    )

    before = {
        "artefact": _count(conn, artefact, project_id),
        "synthesis_result": _count(conn, synthesis_result, project_id),
        "block": _count(conn, block, project_id),
        "annotation": _count(conn, annotation, project_id),
        "addressable_unit": _count(conn, addressable_unit, project_id),
        "citation": _count(conn, citation, project_id),
        "runs": _runs_count(conn, project_id),
    }

    proposal = propose_synthesis_plan(
        conn,
        project_id=project_id,
        context=SynthesiseContext(
            scope_id=scope_id,
            intent="What works to cut fuel poverty",
            context={},
            extraction_run_id=extraction_run_id,
            grouping_run_id=grouping_run_id,
        ),
        synthesis_backend=StubSynthesisBackend(),
    )

    after = {
        "artefact": _count(conn, artefact, project_id),
        "synthesis_result": _count(conn, synthesis_result, project_id),
        "block": _count(conn, block, project_id),
        "annotation": _count(conn, annotation, project_id),
        "addressable_unit": _count(conn, addressable_unit, project_id),
        "citation": _count(conn, citation, project_id),
        "runs": _runs_count(conn, project_id),
    }
    assert before == after
    # A plan was still produced from the read-only substrate.
    assert proposal["proposed_sections"]


def test_propose_synthesis_plan_output_schema(conn: Connection) -> None:
    """The proposal payload matches the § Steer schemas shape exactly."""
    project_id, _run_id, scope_id, extraction_run_id, grouping_run_id, finding_ids = (
        _seed_group_with_findings(conn, [{"intervention": "Alpha service"}])
    )

    proposal = propose_synthesis_plan(
        conn,
        project_id=project_id,
        context=SynthesiseContext(
            scope_id=scope_id,
            intent="What works to cut fuel poverty",
            context={},
            extraction_run_id=extraction_run_id,
            grouping_run_id=grouping_run_id,
        ),
        synthesis_backend=StubSynthesisBackend(),
    )

    assert set(proposal) == {"proposed_sections", "available_groups", "boostable"}
    for section in proposal["proposed_sections"]:
        assert set(section) == {"title", "focus", "group_ids"}
    # available_groups reads the persisted grouping payload.
    assert proposal["available_groups"] == [
        {
            "group_id": "intervention:g01",
            "facet": "intervention",
            "label": "alpha",
            "size": len(finding_ids),
        }
    ]
    boostable = proposal["boostable"]
    assert set(boostable) == {"appraisal_tiers", "evidence_types", "screen_confidence"}
    assert boostable["appraisal_tiers"] == ["1", "2", "3", "4", "5"]
    assert "Systematic Review and Meta-Analysis" in boostable["evidence_types"]
    assert boostable["screen_confidence"] == {
        "lo_bounds": [0.5, 4.0],
        "hi_bounds": [0.5, 4.0],
    }


def test_propose_then_compile_directive_round_trips_into_a_run(conn: Connection) -> None:
    """A proposal → compiled directive drives a synthesise run's sections + boosts."""
    project_id, run_id, scope_id, extraction_run_id, grouping_run_id, _finding_ids = (
        _seed_group_with_findings(conn, [{"intervention": "Alpha service"}])
    )
    plan_context = SynthesiseContext(
        scope_id=scope_id,
        intent="What works to cut fuel poverty",
        context={},
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
    )
    proposal = propose_synthesis_plan(
        conn,
        project_id=project_id,
        context=plan_context,
        synthesis_backend=StubSynthesisBackend(),
    )
    available_ids = [group["group_id"] for group in proposal["available_groups"]]

    directive = compile_synthesis_directive(
        {
            "sections": [
                {
                    "title": "Interventions in the corpus",
                    "focus": "What the assembled evidence reports on interventions.",
                    "group_ids": available_ids,
                }
            ],
            "group_ids": available_ids,
            "retrieval_boosts": {"screen_confidence": {"lo": 1.0, "hi": 3.0}},
        }
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        extraction_run_id=extraction_run_id,
        grouping_run_id=grouping_run_id,
        context={"synthesis": directive},
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.synthesis_provenance["section_set"]["source"] == "scope_context"
    block_titles = {block_row["title"] for block_row in row.blocks}
    assert "Interventions in the corpus" in block_titles
    boosts = row.synthesis_provenance["directive"]["retrieval_boosts"]
    assert boosts["screen_confidence"] == {"lo": 1.0, "hi": 3.0}
