"""DB-backed tests for the synthesise component.

These tests require ``DATABASE_URL`` and are intended for the lead's DB-backed
verification run. The local Codex sandbox does not run them.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.embeddings import EMBEDDING_PROFILE, UNIT_POLICY, StubEmbeddingBackend
from policy_atlas.grounding import content_hash
from policy_atlas.grounding_judge import StubGroundingJudgeBackend
from policy_atlas.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    chunk_embedding,
    citation,
    project_source_snapshot,
    source_snapshot,
    synthesis_result,
)
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.synthesis_backend import StubSynthesisBackend
from policy_atlas.synthesise import SynthesiseContext, SynthesiseFailure, synthesise_scope
from tests.helpers import (
    now,
    run_select,
    seed_characterisation,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_select_doc,
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
    characterisation_run_id: uuid.UUID | None = None,
    selection_run_id: uuid.UUID | None = None,
    extraction_run_id: uuid.UUID | None = None,
    grouping_run_id: uuid.UUID | None = None,
    backend: StubSynthesisBackend | None = None,
) -> dict[str, Any]:
    return synthesise_scope(
        conn,
        project_id=project_id,
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
        grounding_judge_backend=StubGroundingJudgeBackend(),
        embedding_backend=StubEmbeddingBackend(),
    )


def _seed_ingested_full_text(
    conn: Connection,
    *,
    pss_id: uuid.UUID,
    chunks: list[str],
) -> uuid.UUID:
    full_snapshot_id = uuid.uuid4()
    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=full_snapshot_id,
            content_hash=content_hash("\n".join(chunks)),
            text_basis="full_text",
            source_locator=f"full-text-{full_snapshot_id}",
            metadata={"title": "Full text fixture", "abstract": "Full text abstract."},
            created_at=now(),
        )
    )
    conn.execute(
        update(project_source_snapshot)
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
        .values(full_text_snapshot_id=full_snapshot_id, full_text_status="ingested")
    )
    embedder = StubEmbeddingBackend()
    vectors = embedder.embed_texts(chunks)
    for index, content in enumerate(chunks):
        chunk_id = uuid.uuid4()
        conn.execute(
            chunk_table.insert().values(
                chunk_id=chunk_id,
                source_snapshot_id=full_snapshot_id,
                sequence=index,
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
                vector=vectors[index],
                created_at=now(),
            )
        )
    return full_snapshot_id


def test_zero_substrate_fails_without_artefact_or_rollup(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    with pytest.raises(SynthesiseFailure, match="no_groundable_substrate"):
        _run_synthesise(conn, project_id=project_id, run_id=run_id, scope_id=scope_id)

    assert _count(conn, artefact, project_id) == 0
    assert _count(conn, synthesis_result, project_id) == 0


def test_characterisation_only_stub_writes_substrate_and_rollup(conn: Connection) -> None:
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

    summary = _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        characterisation_run_id=characterisation_run_id,
    )

    assert summary["section_count"] == 2
    assert _count(conn, artefact, project_id) == 1
    assert _count(conn, block, project_id) == 2
    assert _count(conn, addressable_unit, project_id) > 0
    assert _count(conn, annotation, project_id) > 0
    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.synthesis_provenance["prompt_versions"]["sections"] == "synthesise_sections_v1"
    assert row.synthesis_provenance["section_set"]["source"] == "proposal"
    claim_types = {
        claim_type
        for claim_type, count in row.counts["claims_total"].items()
        if count
    }
    assert claim_types <= {"pattern", "theme", "gap", "reasoning"}
    assert "chunk" not in claim_types
    assert "finding" not in claim_types


def test_chunk_substrate_writes_verified_unselected_citations(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Test intent evidence")
    _seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=[
            "Test intent evidence says alpha quoted evidence appears here.",
            "Further test intent evidence appears in a second chunk.",
        ],
    )

    _run_synthesise(conn, project_id=project_id, run_id=run_id, scope_id=scope_id)

    assert _count(conn, citation, project_id) > 0
    citation_payloads = [
        payload
        for payload in _project_annotations(conn, project_id)
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
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.synthesis_provenance["sections"][0]["gathered_id_hash"]


def test_explicit_shallower_reference_mismatch_fails(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Selected doc")
    characterisation_run_id = seed_run(conn, project_id)
    other_characterisation_run_id = seed_run(conn, project_id)
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        characterisation_run_id,
        themes={"theme-a": [pss_id]},
    )
    seed_characterisation(
        conn,
        project_id,
        scope_id,
        other_characterisation_run_id,
        themes={"theme-b": [pss_id]},
    )
    _, _, selection_run_id = run_select(
        conn, project_id, scope_id, characterisation_run_id
    )

    with pytest.raises(SynthesiseFailure, match="reference_mismatch"):
        _run_synthesise(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            characterisation_run_id=other_characterisation_run_id,
            selection_run_id=selection_run_id,
        )


def test_fabricated_chunk_quote_is_excluded_and_never_persisted(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="stubfabricate")
    _seed_ingested_full_text(
        conn,
        pss_id=pss_id,
        chunks=["stubfabricate evidence text is real but contains no fabricated quote."],
    )

    _run_synthesise(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        intent="stubfabricate",
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.counts["chunk_claims_rejected"] > 0
    assert _count(conn, citation, project_id) == 0
    fabricated = "This quote is fabricated entirely and appears nowhere."
    block_text = "\n".join(
        row.content
        for row in conn.execute(
            select(block.c.content).where(
                block.c.artefact_id.in_(
                    select(artefact.c.artefact_id).where(artefact.c.project_id == project_id)
                )
            )
        )
    )
    annotation_text = json.dumps(_project_annotations(conn, project_id), sort_keys=True)
    rollup_text = json.dumps(row._mapping, default=str, sort_keys=True)
    assert fabricated not in block_text
    assert fabricated not in annotation_text
    assert fabricated not in rollup_text


def test_same_run_reexecution_is_loud(conn: Connection) -> None:
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
    with pytest.raises(IntegrityError):
        _run_synthesise(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
        )


def test_backend_failure_writes_no_rollup(conn: Connection) -> None:
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

    with pytest.raises(SynthesiseFailure):
        _run_synthesise(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
            backend=StubSynthesisBackend(fail=True),
        )

    assert _count(conn, synthesis_result, project_id) == 0


def test_uploaded_full_text_doc_feeds_chunk_lane(conn: Connection) -> None:
    """An uploaded document carries its full text on the ENVELOPE snapshot
    (full_text_status stays 'not_attempted' — that column is fetch-pipeline
    state, never text availability). Its chunks must be retrievable and its
    appraised status must open the chunk lane (the skeleton's designed rapid
    substrate)."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="Uploaded evidence")
    # Chunk + embed the ENVELOPE snapshot (the upload-ingest shape), leaving
    # full_text_status='not_attempted' and no full_text_snapshot_id.
    envelope_snapshot_id = conn.execute(
        select(project_source_snapshot.c.source_snapshot_id).where(
            project_source_snapshot.c.project_source_snapshot_id == pss_id
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
        conn, project_id=project_id, run_id=run_id, scope_id=scope_id,
        intent="Uploaded evidence",
    )

    row = conn.execute(
        select(synthesis_result).where(synthesis_result.c.project_id == project_id)
    ).one()
    assert row.synthesis_provenance["substrate_profile"]["ingested_docs"] == 1
    assert row.synthesis_provenance["retrieval_scope"]["unit_count"] == 1
    assert row.counts["claims_total"]["chunk"] > 0
    assert _count(conn, citation, project_id) > 0
