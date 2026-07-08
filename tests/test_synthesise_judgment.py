"""Judgment/security tests for the synthesise component (the repo's first agent loop).

These exercise the code-enforced disciplines of task 013: cap binding, closed
read-only tool set, per-section citation isolation, foreign-project scope guards,
zero egress, and honest judge-coverage failure. DB-backed tests require
``DATABASE_URL`` and are for the lead's DB-backed verification run.
"""

from __future__ import annotations

import inspect
import json
import socket
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection

from policy_atlas.embeddings import EMBEDDING_PROFILE, UNIT_POLICY, StubEmbeddingBackend
from policy_atlas.grounding import content_hash
from policy_atlas.grounding_judge import (
    ClaimVerdictWire,
    JudgeResponseWire,
    StubGroundingJudgeBackend,
)
from policy_atlas.schema import (
    TOPIC_THEME,
    addressable_unit,
    annotation,
    artefact,
    block,
    chunk_embedding,
    citation,
    project_source_snapshot,
    source_snapshot,
    source_tag,
    synthesis_result,
)
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.synthesis_backend import (
    ChunkCitationWire,
    ClaimWire,
    GapPayloadWire,
    SectionClaimsWire,
    SectionProposalWire,
    SectionTurn,
    SectionWire,
    StubSynthesisBackend,
)
from policy_atlas.synthesis_tools import (
    REASONING_CLAIMS_MAX,
    SECTION_CAP,
    SECTION_TURN_CAP,
    ToolValidationError,
    build_retrieval_scope,
    make_lookup_reader,
    run_section_loop,
)
from policy_atlas.synthesise import (
    SynthesiseContext,
    SynthesiseFailure,
    generation_budget_max,
    synthesise_scope,
)
from tests.helpers import (
    now,
    seed_characterisation,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
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
    backend: StubSynthesisBackend | None = None,
    judge_backend: Any = None,
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


# --- Test 1: caps bind ---


class _CapCountingBackend:
    """Loops forever on a lookup call until force_emit, then emits one gap claim.

    Wraps its own ``section_turn`` to count backend invocations, so the caps-bind
    test can assert the loop makes exactly ``SECTION_TURN_CAP`` backend calls.
    """

    mode = "stub"

    def __init__(self) -> None:
        self.calls = 0

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[Any],
        *,
        force_emit: bool,
    ) -> SectionTurn:
        self.calls += 1
        if force_emit:
            return {
                "tool_calls": [],
                "claims": SectionClaimsWire(
                    claims=[
                        ClaimWire(
                            claim_type="gap",
                            text="Evidence here is thin (stub inference).",
                            gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
                        )
                    ]
                ),
            }
        return {
            "tool_calls": [
                {"tool": "lookup", "arguments": {"kind": "coverage_records"}}
            ],
            "claims": None,
        }


def test_caps_bind() -> None:
    backend = _CapCountingBackend()
    tools = {
        "lookup": lambda arguments: {"kind": "coverage_records", "result": []},
    }
    result = run_section_loop(backend, seed={"section_index": 0}, tools=tools)

    # The forced emission is the SECTION_TURN_CAP-th backend call, so exactly
    # SECTION_TURN_CAP - 1 tool executions occur before it.
    assert backend.calls == SECTION_TURN_CAP
    assert sum(result["tool_call_counts"].values()) == SECTION_TURN_CAP - 1
    assert result["turn_cap_hit"] is True

    assert (
        inspect.signature(run_section_loop).parameters["turn_cap"].default
        is SECTION_TURN_CAP
    )
    assert generation_budget_max() == 2 + SECTION_CAP * (SECTION_TURN_CAP + 3)
