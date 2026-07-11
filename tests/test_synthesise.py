"""Contract-bulk DB-backed tests for the synthesise component.

These tests require ``DATABASE_URL`` and are intended for the lead's DB-backed
verification run. The local Codex sandbox does not run them.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.embeddings import StubEmbeddingBackend
from policy_atlas.grounding import content_hash
from policy_atlas.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    citation,
    extraction_result,
    grouping_result,
    search_coverage_record,
    synthesis_result,
)
from policy_atlas.synthesis_backend import (
    ChunkCitationWire,
    ClaimWire,
    GapPayloadWire,
    SectionClaimsWire,
    SectionProposalWire,
    SectionTurn,
    SectionWire,
    StubSynthesisBackend,
    SynthesisBackend,
)
from policy_atlas.synthesis_tools import ToolExchange
from policy_atlas.synthesise import SynthesiseContext, SynthesiseFailure, synthesise_scope
from policy_atlas.usage import UsageResult
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
        grounding_judge_backend=StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
    )


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
            extraction_provenance={"fingerprint": "t"},
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
            facet="intervention",
            grouping_provenance={},
            groups={"groups": [], "ungrouped": {}, "no_value": {}},
            counts={},
            flags={},
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
    from policy_atlas.schema import selection_result

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


class _BoundarySpanBackend:
    """Local backend: turn 1 searches chunks, turn 2 cites a boundary-spanning quote.

    Ids are only known once ``search_chunks`` executes at run time, so the
    citation is built from the transcript rather than scripted in advance.
    """

    mode = "stub"

    def __init__(self, proposal: SectionProposalWire) -> None:
        self._proposal = proposal

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
    ) -> UsageResult[SectionProposalWire]:
        del intent, substrate, rejection
        return self._proposal, None

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        force_emit: bool,
    ) -> UsageResult[SectionTurn]:
        del force_emit
        if not transcript:
            return {
                "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "rate"}}],
                "claims": None,
            }, None
        chunks = transcript[0]["result"]["chunks"]
        chunk_id = chunks[0]["chunk_record_id"]
        return {
            "tool_calls": [],
            "claims": SectionClaimsWire(
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

    def repair_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        failing: list[dict[str, Any]],
    ) -> UsageResult[SectionClaimsWire]:
        raise AssertionError("repair_section should not be called for a verified quote")


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


class _GapCorpusAbsenceBackend:
    """Local backend: immediately emits one corpus_absence gap claim."""

    mode = "stub"

    def __init__(self, coverage_record_id: str) -> None:
        self._coverage_record_id = coverage_record_id

    def propose_sections(
        self,
        *,
        intent: str,
        substrate: dict[str, Any],
        rejection: list[str] | None = None,
    ) -> UsageResult[SectionProposalWire]:
        del intent, substrate, rejection
        return SectionProposalWire(
            sections=[SectionWire(title="Corpus coverage", focus="What the search covered")]
        ), None

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
            "claims": SectionClaimsWire(
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

    def repair_section(
        self,
        seed: dict[str, Any],
        transcript: list[ToolExchange],
        *,
        failing: list[dict[str, Any]],
    ) -> UsageResult[SectionClaimsWire]:
        raise AssertionError("repair_section should not be called")


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
    from policy_atlas.synthesise import _load_corpus_profile

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
    from policy_atlas.synthesise import _load_screened_chunks

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
            extraction_provenance={"fingerprint": "t"},
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
            facet="intervention",
            grouping_provenance={},
            groups={
                "groups": [
                    {
                        "group_id": "g1",
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
            },
            counts={},
            flags={},
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


def test_block_content_is_joined_claim_texts(conn: Connection) -> None:
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
    for block_row in block_rows:
        unit_rows = conn.execute(
            select(addressable_unit).where(addressable_unit.c.block_id == block_row.block_id)
        ).all()
        assert unit_rows
        ordered_units = sorted(unit_rows, key=lambda u: int(u.locator["start"]))
        expected_content = "\n\n".join(u.content for u in ordered_units)
        assert block_row.content == expected_content
        assert block_row.content_hash == content_hash(expected_content)
        for unit_row in ordered_units:
            start = int(unit_row.locator["start"])
            end = int(unit_row.locator["end"])
            assert block_row.content[start:end] == unit_row.content
