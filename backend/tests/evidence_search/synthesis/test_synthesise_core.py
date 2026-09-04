"""DB-backed tests for the synthesise component.

These tests require ``DATABASE_URL`` and are intended for the lead's DB-backed
verification run. The local Codex sandbox does not run them.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import EMBEDDING_PROFILE, UNIT_POLICY, StubEmbeddingBackend
from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    chunk_embedding,
    citation,
    extraction_result,
    grouping_result,
    synthesis_result,
    task_source_snapshot,
)
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.evidence_search.synthesis.grounding_judge import (
    JudgeResponseWire,
    StubGroundingJudgeBackend,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import (
    ChunkCitationWire,
    ClaimWire,
    SectionProposalWire,
    SectionProseWire,
    SectionRepairWire,
    SectionTurn,
    SectionWire,
    StubSynthesisBackend,
)
from policy_atlas.evidence_search.synthesis.synthesise import (
    SynthesiseContext,
    SynthesiseFailure,
    synthesise_scope,
)
from tests.helpers import (
    now,
    run_select,
    seed_characterisation,
    seed_ingested_full_text,
    seed_run,
    seed_scope,
    seed_select_doc,
    seed_task_and_run,
)
from tests.synthesis_wire import ScriptedSynthesisBackend, prose_section, repair_wire


def _count(conn: Connection, table: Any, task_id: uuid.UUID) -> int:
    """Task-scoped row count — the test DB carries residual committed rows
    from other suites' commit-survival tests, so global counts are meaningless."""
    if table is artefact or table is synthesis_result:
        stmt = select(func.count()).select_from(table).where(table.c.task_id == task_id)
        return int(conn.execute(stmt).scalar_one())
    block_ids = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.task_id == task_id)
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


def _task_annotations(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    block_ids = select(block.c.block_id).where(
        block.c.artefact_id.in_(
            select(artefact.c.artefact_id).where(artefact.c.task_id == task_id)
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
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    intent: str = "Test intent",
    characterisation_run_id: uuid.UUID | None = None,
    selection_run_id: uuid.UUID | None = None,
    extraction_run_id: uuid.UUID | None = None,
    grouping_run_id: uuid.UUID | None = None,
    backend: Any | None = None,
    grounding_judge_backend: Any | None = None,
) -> dict[str, Any]:
    return synthesise_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=SynthesiseContext(
            scope_id=scope_id,
            intent=intent,
            context={},
            characterisation_run_id=characterisation_run_id,
            selection_run_id=selection_run_id,
            extraction_run_id=extraction_run_id,
            grouping_run_id=grouping_run_id,
        ),
        synthesis_backend=backend or StubSynthesisBackend(),
        grounding_judge_backend=grounding_judge_backend or StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
    )


def _seed_envelope_chunk(
    conn: Connection,
    *,
    tss_id: uuid.UUID,
    content: str,
    segmentation_policy: str = "abstract_v1",
) -> uuid.UUID:
    envelope_snapshot_id = conn.execute(
        select(task_source_snapshot.c.source_snapshot_id).where(
            task_source_snapshot.c.task_source_snapshot_id == tss_id
        )
    ).scalar_one()
    chunk_id = uuid.uuid4()
    conn.execute(
        chunk_table.insert().values(
            chunk_id=chunk_id,
            source_snapshot_id=envelope_snapshot_id,
            sequence=0,
            content=content,
            content_hash=content_hash(content),
            locator={},
            segmentation_policy=segmentation_policy,
            created_at=now(),
        )
    )
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding_profile=EMBEDDING_PROFILE,
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": len(content)},
            vector=StubEmbeddingBackend().embed_texts([content])[0],
            created_at=now(),
        )
    )
    return chunk_id


class _SearchAndCiteBackend(ScriptedSynthesisBackend):
    quote = "abstract-only subsidy evidence"

    def __init__(self) -> None:
        super().__init__(
            proposal=SectionProposalWire(
                sections=[
                    SectionWire(
                        title="Abstract-basis evidence",
                        focus="Evidence visible from abstract-basis chunks.",
                    )
                ]
            )
        )
        self.seen_chunks: list[dict[str, Any]] = []

    def section_turn(
        self, seed: dict[str, Any], transcript: list[Any], *, force_emit: bool
    ) -> UsageResult[SectionTurn]:
        # The code-injected conclusions section (ADR 0015 §8) is outside this
        # double's single-section scenario — emit nothing for it.
        if seed.get("section_index", 0) != 0:
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
        chunks = [
            chunk
            for exchange in transcript
            if exchange["tool"] == "search_chunks"
            for chunk in exchange["result"].get("chunks", [])
        ]
        self.seen_chunks = chunks
        if not chunks and not force_emit:
            return {
                "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "subsidy"}}],
                "claims": None,
            }, None
        chunk_id = chunks[0]["chunk_record_id"] if chunks else "missing"
        return {
            "tool_calls": [],
            "claims": prose_section(
                claims=[
                    ClaimWire(
                        claim_type="chunk",
                        text="The abstract reports subsidy evidence.",
                        citations=[
                            ChunkCitationWire(chunk_record_id=chunk_id, quote=self.quote)
                        ],
                    )
                ]
            ),
        }, None

    def repair_section(
        self, seed: dict[str, Any], transcript: list[Any], *, failing: list[dict[str, Any]]
    ) -> UsageResult[SectionRepairWire]:
        del seed, transcript, failing
        return repair_wire(claims=[]), None


class _CapturingJudgeBackend:
    mode = "stub"

    def __init__(self) -> None:
        self.envelopes: list[dict[str, Any]] = []
        self._delegate = StubGroundingJudgeBackend()

    def judge_block(self, envelope: dict[str, Any]) -> UsageResult[JudgeResponseWire]:
        self.envelopes.append(envelope)
        return self._delegate.judge_block(envelope)


def test_zero_substrate_fails_without_artefact_or_rollup(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    with pytest.raises(SynthesiseFailure, match="no_groundable_substrate"):
        _run_synthesise(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)

    assert _count(conn, artefact, task_id) == 0
    assert _count(conn, synthesis_result, task_id) == 0


def test_all_fetch_failed_abstract_basis_corpus_synthesises_with_labels(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = seed_select_doc(
        conn,
        task_id,
        run_id,
        scope_id,
        title="abstract-only policy evidence",
        text_basis="abstract",
    )
    chunk_id = _seed_envelope_chunk(
        conn,
        tss_id=tss_id,
        content=(
            "The abstract-only subsidy evidence reports improved policy outcomes "
            "without a fetched full text."
        ),
    )
    backend = _SearchAndCiteBackend()
    judge = _CapturingJudgeBackend()

    summary = _run_synthesise(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        backend=backend,
        grounding_judge_backend=judge,
    )

    # One proposed section + the code-injected (empty) conclusions section.
    assert summary["section_count"] == 2
    assert backend.seen_chunks
    assert {chunk["text_basis"] for chunk in backend.seen_chunks} == {"abstract_only"}
    assert backend.seen_chunks[0]["chunk_record_id"] == str(chunk_id)
    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()
    assert row.synthesis_provenance["substrate_profile"]["ingested_docs"] == 0
    assert row.synthesis_provenance["retrieval_scope"]["unit_count"] == 1
    payloads = _task_annotations(conn, task_id)
    citation_payload = next(payload for payload in payloads if "citations" in payload)
    assert citation_payload["citations"][0]["text_basis"] == "abstract_only"
    assert citation_payload["citations"][0]["spans"][0]["text_basis"] == "abstract_only"
    assert judge.envelopes
    assert judge.envelopes[0]["chunks"] == [
        {
            "chunk_record_id": str(chunk_id),
            "segmentation_policy": "abstract_v1",
            "text_basis": "abstract_only",
            "content": (
                "The abstract-only subsidy evidence reports improved policy outcomes "
                "without a fetched full text."
            ),
        }
    ]


def test_characterisation_only_stub_writes_substrate_and_rollup(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    characterisation_run_id = seed_run(conn, task_id)
    seed_characterisation(
        conn,
        task_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    summary = _run_synthesise(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )

    # Two proposed sections + the code-injected conclusions section (ADR 0015 §8).
    assert summary["section_count"] == 3
    assert _count(conn, artefact, task_id) == 1
    assert _count(conn, block, task_id) == 3
    assert _count(conn, addressable_unit, task_id) > 0
    assert _count(conn, annotation, task_id) > 0
    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()
    assert row.synthesis_provenance["prompt_versions"]["sections"] == "synthesise_sections_v5"
    assert row.synthesis_provenance["section_set"]["source"] == "proposal"
    claim_types = {
        claim_type
        for claim_type, count in row.counts["claims_total"].items()
        if count
    }
    assert claim_types <= {"pattern", "theme", "gap", "reasoning"}
    assert "chunk" not in claim_types
    assert "finding" not in claim_types
    # No headline finding/chunk claims survive, so the key-findings pass mints
    # no block — the explicit absence path (ADR 0015 §8).
    assert row.counts["key_findings"] == {"present": False, "reason": "no_headline_claims"}


def test_chunk_substrate_writes_verified_unselected_citations(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = seed_select_doc(conn, task_id, run_id, scope_id, title="Test intent evidence")
    seed_ingested_full_text(
        conn,
        tss_id=tss_id,
        chunks=[
            "Test intent evidence says alpha quoted evidence appears here.",
            "Further test intent evidence appears in a second chunk.",
        ],
    )

    _run_synthesise(conn, task_id=task_id, run_id=run_id, scope_id=scope_id)

    assert _count(conn, citation, task_id) > 0
    citation_payloads = [
        payload
        for payload in _task_annotations(conn, task_id)
        if payload.get("claim_type") == "chunk"
    ]
    origins = [
        span["origin"]
        for payload in citation_payloads
        for citation_payload in payload.get("citations", [])
        for span in citation_payload.get("spans", [])
    ]
    assert "unselected_screened" in origins
    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()
    assert row.synthesis_provenance["sections"][0]["gathered_id_hash"]


def test_explicit_shallower_reference_mismatch_fails(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = seed_select_doc(conn, task_id, run_id, scope_id, title="Selected doc")
    characterisation_run_id = seed_run(conn, task_id)
    other_characterisation_run_id = seed_run(conn, task_id)
    seed_characterisation(
        conn,
        task_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": [tss_id]},
    )
    seed_characterisation(
        conn,
        task_id,
        scope_id,
        other_characterisation_run_id,
        themes={"theme-b": [tss_id]},
    )
    _, _, selection_run_id = run_select(
        conn, task_id, scope_id, characterisation_run_id
    )

    with pytest.raises(SynthesiseFailure, match="reference_mismatch"):
        _run_synthesise(
            conn,
            task_id=task_id,
            run_id=run_id,
            scope_id=scope_id,
            characterisation_run_id=other_characterisation_run_id,
            selection_run_id=selection_run_id,
        )


def test_fabricated_chunk_quote_is_excluded_and_never_persisted(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = seed_select_doc(conn, task_id, run_id, scope_id, title="stubfabricate")
    seed_ingested_full_text(
        conn,
        tss_id=tss_id,
        chunks=["stubfabricate evidence text is real but contains no fabricated quote."],
    )

    _run_synthesise(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        intent="stubfabricate",
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()
    assert row.counts["chunk_claims_rejected"] > 0
    assert _count(conn, citation, task_id) == 0
    fabricated = "This quote is fabricated entirely and appears nowhere."
    block_text = "\n".join(
        row.content
        for row in conn.execute(
            select(block.c.content).where(
                block.c.artefact_id.in_(
                    select(artefact.c.artefact_id).where(artefact.c.task_id == task_id)
                )
            )
        )
    )
    annotation_text = json.dumps(_task_annotations(conn, task_id), sort_keys=True)
    rollup_text = json.dumps(row._mapping, default=str, sort_keys=True)
    assert fabricated not in block_text
    assert fabricated not in annotation_text
    assert fabricated not in rollup_text


def test_same_run_reexecution_is_loud(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    characterisation_run_id = seed_run(conn, task_id)
    seed_characterisation(
        conn,
        task_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    _run_synthesise(
        conn,
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )
    artefacts_before = _count(conn, artefact, task_id)
    with pytest.raises(SynthesiseFailure, match="same_run_reexecution"):
        _run_synthesise(
            conn,
            task_id=task_id,
            run_id=run_id,
            scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
        )
    # The guard fires before any write: no orphan artefact, transaction
    # still healthy for the failure event.
    assert _count(conn, artefact, task_id) == artefacts_before
    assert conn.execute(select(func.count()).select_from(artefact)).scalar() is not None


def test_how_resolved_records_explicit_extraction_not_transitive(conn: Connection) -> None:
    """Supplying BOTH grouping_run_id and its matching extraction_run_id
    explicitly must record 'explicit' for extraction in how_resolved, not
    'transitive:grouping' — the honesty fix for reference provenance."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = seed_select_doc(conn, task_id, run_id, scope_id, title="Grouping doc")
    characterisation_run_id = seed_run(conn, task_id)
    seed_characterisation(
        conn,
        task_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": [tss_id]},
    )
    _, _, selection_run_id = run_select(conn, task_id, scope_id, characterisation_run_id)

    extraction_run_id = seed_run(conn, task_id)
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=task_id,
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
    grouping_run_id = seed_run(conn, task_id)
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            task_id=task_id,
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
        task_id=task_id,
        run_id=run_id,
        scope_id=scope_id,
        grouping_run_id=grouping_run_id,
        extraction_run_id=extraction_run_id,
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()
    how_resolved = row.synthesis_provenance["resolved_references"]["how_resolved"]
    assert how_resolved["grouping"] == "explicit"
    assert how_resolved["extraction"] == "explicit"
    assert how_resolved["selection"] == "transitive:extraction"
    assert how_resolved["characterisation"] == "transitive:selection"


def test_backend_failure_writes_no_rollup(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    characterisation_run_id = seed_run(conn, task_id)
    seed_characterisation(
        conn,
        task_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": []},
    )

    with pytest.raises(SynthesiseFailure):
        _run_synthesise(
            conn,
            task_id=task_id,
            run_id=run_id,
            scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
            backend=StubSynthesisBackend(fail=True),
        )

    assert _count(conn, synthesis_result, task_id) == 0


def test_uploaded_full_text_doc_feeds_chunk_lane(conn: Connection) -> None:
    """An uploaded document carries its full text on the ENVELOPE snapshot
    (full_text_status stays 'not_attempted' — that column is fetch-pipeline
    state, never text availability). Its chunks must be retrievable and its
    appraised status must open the chunk lane (the skeleton's designed rapid
    substrate)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_id = seed_select_doc(conn, task_id, run_id, scope_id, title="Uploaded evidence")
    # Chunk + embed the ENVELOPE snapshot (the upload-ingest shape), leaving
    # full_text_status='not_attempted' and no full_text_snapshot_id.
    envelope_snapshot_id = conn.execute(
        select(task_source_snapshot.c.source_snapshot_id).where(
            task_source_snapshot.c.task_source_snapshot_id == tss_id
        )
    ).scalar_one()
    embedder = StubEmbeddingBackend()
    content = "Uploaded evidence says alpha quoted evidence appears here."
    chunk_id = uuid.uuid4()
    conn.execute(
        chunk_table.insert().values(
            chunk_id=chunk_id,
            source_snapshot_id=envelope_snapshot_id,
            sequence=0,
            content=content,
            content_hash=content_hash(content),
            locator={},
            segmentation_policy="manual_v1",
            created_at=now(),
        )
    )
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding_profile=EMBEDDING_PROFILE,
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": len(content)},
            vector=embedder.embed_texts([content])[0],
            created_at=now(),
        )
    )

    _run_synthesise(
        conn, task_id=task_id, run_id=run_id, scope_id=scope_id,
        intent="Uploaded evidence",
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.task_id == task_id)
    ).one()
    assert row.synthesis_provenance["substrate_profile"]["ingested_docs"] == 1
    assert row.synthesis_provenance["retrieval_scope"]["unit_count"] == 1
    assert row.counts["claims_total"]["chunk"] > 0
    assert _count(conn, citation, task_id) > 0


def test_text_basis_matches_across_both_retrieval_paths(conn: Connection) -> None:
    """016 review stack (item 9): synthesise.py's ``_load_screened_chunks`` and
    synthesis_tools.py's ``build_retrieval_scope`` now share one
    ``chunk_text_basis_case`` helper — pin that both report the identical
    ``text_basis`` per chunk for a mixed corpus (one ingested full-text doc,
    one abstract-only doc)."""
    from policy_atlas.evidence_search.synthesis.synthesis_tools import build_retrieval_scope
    from policy_atlas.evidence_search.synthesis.synthesise import _load_screened_chunks

    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    full_text_tss_id = seed_select_doc(conn, task_id, run_id, scope_id, title="Full-text doc")
    seed_ingested_full_text(
        conn, tss_id=full_text_tss_id,
        chunks=["Full text chunk one.", "Full text chunk two."],
    )

    abstract_tss_id = seed_select_doc(
        conn, task_id, run_id, scope_id, title="Abstract-only doc", text_basis="abstract",
    )
    envelope_snapshot_id = conn.execute(
        select(task_source_snapshot.c.source_snapshot_id).where(
            task_source_snapshot.c.task_source_snapshot_id == abstract_tss_id
        )
    ).scalar_one()
    abstract_content = "Abstract-only evidence chunk."
    abstract_chunk_id = uuid.uuid4()
    conn.execute(
        chunk_table.insert().values(
            chunk_id=abstract_chunk_id,
            source_snapshot_id=envelope_snapshot_id,
            sequence=0,
            content=abstract_content,
            content_hash=content_hash(abstract_content),
            locator={},
            segmentation_policy="abstract_v1",
            created_at=now(),
        )
    )
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=abstract_chunk_id,
            embedding_profile=EMBEDDING_PROFILE,
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": len(abstract_content)},
            vector=StubEmbeddingBackend().embed_texts([abstract_content])[0],
            created_at=now(),
        )
    )

    chunk_by_id, _chunks_by_tss, _basis = _load_screened_chunks(
        conn,
        task_id=task_id,
        scope_id=scope_id,
        selected_tss_ids=set(),
        appraised_tss_ids=set(),
    )
    scope = build_retrieval_scope(
        conn, task_id=task_id, scope_id=scope_id, selected_tss_ids=set()
    )

    # scope.chunks is embedding-scoped, chunk_by_id is not — every chunk here
    # has an embedding, so the two keysets must still coincide exactly.
    assert set(chunk_by_id) == set(scope.chunks)
    for chunk_id, info in chunk_by_id.items():
        assert info.text_basis == scope.chunks[chunk_id]["text_basis"]
    assert chunk_by_id[str(abstract_chunk_id)].text_basis == "abstract_only"
    other_bases = {
        info.text_basis for cid, info in chunk_by_id.items() if cid != str(abstract_chunk_id)
    }
    assert other_bases == {"full_text"}
