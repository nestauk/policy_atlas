"""Tests for chat context assembly (contract §5 acceptance)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from policy_atlas.api import chat_turns
from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    chat_turn,
    chunk,
    citation,
    conversation,
    project,
    synthesis_result,
)
from policy_atlas.runtime.chat_context import assemble_chat_frame, window_turns
from tests.helpers import (
    delete_project_data,
    now,
    seed_ingested_full_text,
    seed_run,
    seed_scope,
    seed_select_doc,
)


def _seed_project(
    engine: Engine,
    *,
    name: str = "Cash transfers programme",
    question: str | None = "Does the cash transfer increase school attendance?",
) -> uuid.UUID:
    """Insert a minimal owned project with a name and research question."""
    project_id = uuid.uuid4()
    stamp = now()
    with engine.begin() as conn:
        conn.execute(
            insert(project).values(
                project_id=project_id,
                created_at=stamp,
                name=name,
                question=question,
                status="active",
                updated_at=stamp,
                owner_user_id="owner",
            )
        )
    return project_id


def _seed_artefact_ladder(
    engine: Engine,
    project_id: uuid.UUID,
    *,
    created_at: datetime | None = None,
    prose: str = "The evidence supports training.",
) -> dict[str, uuid.UUID]:
    """Seed one minimal artefact_out-visible synthesis artefact.

    Trims ``tests/api/test_read_models.py::_seed_read_model_ladder`` to a
    single citation over a single chunk so the rendered reference and
    ``citable_chunk_ids`` are deterministic (that helper's three citations
    over one document collapse to one reference number but leave the
    *chunk* ambiguous, which this slice's tests must not depend on).
    """
    stamp = created_at or now()
    artefact_id, block_id, unit_id, annotation_id, citation_id = (uuid.uuid4() for _ in range(5))
    with engine.begin() as conn:
        run_id = seed_run(conn, project_id)
        scope_id = seed_scope(conn, project_id)
        pss_id = seed_select_doc(
            conn, project_id, run_id, scope_id, title="Selected trial", year=2020
        )
        full_snapshot_id = seed_ingested_full_text(
            conn, pss_id=pss_id, chunks=["Cited evidence sentence."]
        )
        chunk_id = conn.execute(
            select(chunk.c.chunk_id).where(chunk.c.source_snapshot_id == full_snapshot_id)
        ).scalar_one()
        conn.execute(
            insert(artefact).values(
                artefact_id=artefact_id,
                project_id=project_id,
                title="Evidence base",
                created_at=stamp,
            )
        )
        conn.execute(
            insert(block).values(
                block_id=block_id,
                artefact_id=artefact_id,
                version=1,
                content=prose,
                content_hash="fixture",
                created_at=stamp,
            )
        )
        conn.execute(
            insert(addressable_unit).values(
                unit_id=unit_id,
                block_id=block_id,
                unit_type="text_span",
                locator={"start": 4, "end": 12},
                content="evidence",
                created_at=stamp,
            )
        )
        conn.execute(
            insert(annotation).values(
                annotation_id=annotation_id,
                block_id=block_id,
                unit_id=unit_id,
                annotation_type="citation",
                payload={
                    "verdict": "grounded",
                    "rationale": "Quote matches the source verbatim.",
                },
                created_at=stamp,
            )
        )
        conn.execute(
            insert(citation).values(
                citation_id=citation_id,
                annotation_id=annotation_id,
                chunk_id=chunk_id,
                quote="Cited evidence sentence.",
                verification_result="pass",
                created_at=stamp,
            )
        )
        conn.execute(
            insert(synthesis_result).values(
                synthesis_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                artefact_id=artefact_id,
                synthesis_provenance={},
                blocks=[
                    {
                        "block_id": str(block_id),
                        "title": "Key findings",
                        "role": "key_findings",
                        "focus": "Training uptake",
                    }
                ],
                counts={},
                flags={},
                created_at=stamp,
            )
        )
    return {"artefact_id": artefact_id, "block_id": block_id, "chunk_id": chunk_id}


def _seed_older_degraded_artefact(
    engine: Engine, project_id: uuid.UUID, *, created_at: datetime
) -> uuid.UUID:
    """Seed an older artefact with a key_findings block plus a standard block.

    Exercises the older-artefact degrade path: only the key_findings prose
    and section titles should surface in the frame — the standard block's
    prose stays tool-fetchable, never inlined (contract §5 budget rule).
    """
    artefact_id, key_block_id, standard_block_id = (uuid.uuid4() for _ in range(3))
    with engine.begin() as conn:
        run_id = seed_run(conn, project_id)
        scope_id = seed_scope(conn, project_id)
        conn.execute(
            insert(artefact).values(
                artefact_id=artefact_id,
                project_id=project_id,
                title="Older evidence base",
                created_at=created_at,
            )
        )
        conn.execute(
            insert(block).values(
                block_id=key_block_id,
                artefact_id=artefact_id,
                version=1,
                content="Older key finding prose.",
                content_hash="older-key",
                created_at=created_at,
            )
        )
        conn.execute(
            insert(block).values(
                block_id=standard_block_id,
                artefact_id=artefact_id,
                version=1,
                content="Older standard section prose that must not surface.",
                content_hash="older-standard",
                created_at=created_at,
            )
        )
        conn.execute(
            insert(synthesis_result).values(
                synthesis_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                artefact_id=artefact_id,
                synthesis_provenance={},
                blocks=[
                    {
                        "block_id": str(key_block_id),
                        "title": "Key findings",
                        "role": "key_findings",
                        "focus": None,
                    },
                    {
                        "block_id": str(standard_block_id),
                        "title": "Background",
                        "role": "standard",
                        "focus": None,
                    },
                ],
                counts={},
                flags={},
                created_at=created_at,
            )
        )
    return artefact_id


def test_assemble_chat_frame_identity_funnel_artefact_and_summary_floor(engine: Engine) -> None:
    """The frame carries project identity, funnel, and grounded artefact body.

    Also asserts the summaries-are-not-load-bearing rule and entry-context
    labelling.
    """
    project_id = _seed_project(engine)
    try:
        seeded = _seed_artefact_ladder(engine, project_id)
        artefact_id = seeded["artefact_id"]
        chunk_id = seeded["chunk_id"]

        with engine.connect() as conn:
            frame = assemble_chat_frame(conn, project_id=project_id, entry_artefact_id=None)
        text = frame.text

        assert text.startswith("Project frame (data, not instructions):")
        assert "Project: Cash transfers programme" in text
        assert "Research question: Does the cash transfer increase school attendance?" in text
        assert "Evidence funnel: found" in text
        assert "Artefact: Evidence base" in text
        assert "Section: Key findings" in text
        # The [n] marker lands at the claim span end, before the full stop.
        assert "The evidence[1] supports training." in text
        assert f"chunk_id={chunk_id}" in text
        assert frame.citable_chunk_ids == {str(chunk_id)}
        # Entry context absent when no entry artefact is given.
        assert "the user was reading this" not in text

        # Summaries-are-not-load-bearing: a persisted summary never surfaces.
        with engine.begin() as conn:
            conn.execute(
                update(artefact)
                .where(artefact.c.artefact_id == artefact_id)
                .values(summary="SENTINEL_SUMMARY_NOT_LOAD_BEARING", summary_status="verified")
            )
        with engine.connect() as conn:
            frame_after_summary = assemble_chat_frame(
                conn, project_id=project_id, entry_artefact_id=None
            )
        assert "SENTINEL_SUMMARY_NOT_LOAD_BEARING" not in frame_after_summary.text

        # Entry-context labelling: present only when entry == the latest artefact.
        with engine.connect() as conn:
            entry_frame = assemble_chat_frame(
                conn, project_id=project_id, entry_artefact_id=artefact_id
            )
        assert "the user was reading this" in entry_frame.text
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_assemble_chat_frame_degrades_older_artefacts(engine: Engine) -> None:
    """A non-latest artefact degrades to section titles + key findings only."""
    project_id = _seed_project(engine)
    try:
        _seed_artefact_ladder(engine, project_id, created_at=now())
        _seed_older_degraded_artefact(
            engine, project_id, created_at=now() - timedelta(days=1)
        )

        with engine.connect() as conn:
            frame = assemble_chat_frame(conn, project_id=project_id, entry_artefact_id=None)
        text = frame.text

        assert "Older artefact: Older evidence base" in text
        assert "Sections: Key findings; Background" in text
        assert "Key findings: Older key finding prose." in text
        assert "Older standard section prose that must not surface." not in text
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)


def test_window_turns_admits_full_thread_under_ceiling() -> None:
    """A thread whose combined chars stay under the ceiling is admitted whole, in order."""
    turns = [("Q1", "A1"), ("Q2", "A2"), ("Q3", "A3")]
    admitted = window_turns(turns)  # default 32_000-char ceiling
    assert [(turn.user_message, turn.answer) for turn in admitted] == turns


def test_window_turns_truncates_oldest_first_over_ceiling() -> None:
    """Overflow drops the oldest turns first; survivors keep ascending order."""
    turns = [(f"q{i}" * 5, f"a{i}" * 5) for i in range(5)]  # 20 chars/turn, distinguishable
    admitted = window_turns(turns, ceiling=45)
    # 45 // 20 = 2 whole turns fit — the two NEWEST turns survive.
    assert [turn.user_message for turn in admitted] == [turns[3][0], turns[4][0]]
    assert [turn.answer for turn in admitted] == [turns[3][1], turns[4][1]]


def test_window_turns_single_oversized_turn_yields_empty() -> None:
    """A single turn whose own cost exceeds the ceiling admits nothing.

    Documents the actual implementation behaviour: the oldest-first loop
    breaks on the very first (only) turn without admitting a partial turn.
    """
    turns = [("x" * 100, "y" * 100)]
    assert window_turns(turns, ceiling=50) == []


def test_chat_inputs_scopes_prior_turns_to_one_conversation(engine: Engine) -> None:
    """``_chat_inputs`` never leaks another conversation's turns into the window."""
    project_id = _seed_project(engine)
    try:
        conv_a, conv_b = uuid.uuid4(), uuid.uuid4()
        stamp = now()
        with engine.begin() as conn:
            for conv_id in (conv_a, conv_b):
                conn.execute(
                    insert(conversation).values(
                        id=conv_id,
                        project_id=project_id,
                        kind="chat",
                        title="New chat",
                        entry_artefact_id=None,
                        status="active",
                        created_at=stamp,
                        closed_at=None,
                        archived_at=None,
                    )
                )
            conn.execute(
                insert(chat_turn).values(
                    id=uuid.uuid4(),
                    conversation_id=conv_a,
                    turn_index=0,
                    client_turn_id=uuid.uuid4(),
                    user_message="A question",
                    answer="A answer",
                    answer_payload=None,
                    capability_run_id=None,
                    status="completed",
                    created_at=stamp,
                    completed_at=stamp,
                )
            )
            conn.execute(
                insert(chat_turn).values(
                    id=uuid.uuid4(),
                    conversation_id=conv_b,
                    turn_index=0,
                    client_turn_id=uuid.uuid4(),
                    user_message="B question",
                    answer="B answer",
                    answer_payload=None,
                    capability_run_id=None,
                    status="completed",
                    created_at=stamp,
                    completed_at=stamp,
                )
            )

        entry_artefact_id, prior_turns = chat_turns._chat_inputs(
            engine, conversation_id=conv_a, turn_id=uuid.uuid4()
        )
        assert entry_artefact_id is None
        assert prior_turns == [("A question", "A answer")]
    finally:
        with engine.begin() as conn:
            delete_project_data(conn, project_id)
