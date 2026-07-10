"""Tests for the screen component — schema, stub logic, round-trips, harness integration."""

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy import func, inspect, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas import events
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import (
    chunk as chunk_table,
)
from policy_atlas.schema import (
    evidence_scope,
    metadata,
    runs,
    source_screening_result,
    source_snapshot,
)
from policy_atlas.screen import ScreenContext, _load_stage2_docs, _stage2_payload, screen_sources
from policy_atlas.screen_prompt import (
    STAGE2_WINDOW_CHAR_BUDGET,
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
    ScreenRepWire,
)
from policy_atlas.screening_backend import StubScreeningBackend
from policy_atlas.windowing import greedy_windows
from tests.helpers import (
    now,
    seed_ingested_full_text,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

# --- Schema / structure ---

def test_screen_table_count(conn: Connection) -> None:
    assert len(metadata.tables) == 26


def test_pss_has_composite_unique(conn: Connection) -> None:
    inspector = inspect(conn)
    names = {uc["name"] for uc in inspector.get_unique_constraints("project_source_snapshot")}
    assert "uq_pss_id_project" in names


def test_evidence_scope_columns(conn: Connection) -> None:
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("evidence_scope")}
    assert {"context", "intent", "project_id", "evidence_scope_id", "created_at"} <= cols


def test_ssr_columns(conn: Connection) -> None:
    inspector = inspect(conn)
    cols = {c["name"] for c in inspector.get_columns("source_screening_result")}
    assert {
        "source_screening_result_id", "evidence_scope_id", "project_source_snapshot_id",
        "project_id", "screened_by_run_id", "status", "screen_basis",
        "screen_decision_confidence", "screen_stage", "screened_at",
    } <= cols


# --- Stub logic (pure Python, no DB) ---

def test_stub_relevant_with_abstract() -> None:
    result = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract="Some abstract text.",
            abstract_source=None,
            intent="Test",
            metadata={"abstract": "Some abstract text."},
        )
    )
    assert result.decision == "relevant"
    assert result.confidence == 0.9


def test_stub_relevant_without_abstract() -> None:
    result = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract=None,
            abstract_source=None,
            intent="Test",
            metadata={},
        )
    )
    assert result.decision == "relevant"
    assert result.confidence == 0.7


def test_stub_not_relevant() -> None:
    result = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract="Some text.",
            abstract_source=None,
            intent="Test",
            metadata={"_stub_not_relevant": True, "abstract": "Some text."},
        )
    )
    assert result.decision == "not_relevant"
    assert result.confidence == 0.95


def test_stub_unsure() -> None:
    result = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract="Some text.",
            abstract_source=None,
            intent="Test",
            metadata={"_stub_unsure": True, "abstract": "Some text."},
        )
    )
    assert result.decision == "unsure"
    assert result.confidence == 0.6


def test_stub_failed() -> None:
    with pytest.raises(RuntimeError):
        StubScreeningBackend().screen_envelope(
            ScreenEnvelopePayload(
                pss_id="pss-1",
                title="Test",
                abstract=None,
                abstract_source=None,
                intent="Test",
                metadata={"_stub_failed": True},
            )
        )


# --- Check constraints ---

def _ssr_insert(conn: Connection, project_id: uuid.UUID, run_id: uuid.UUID,
                scope_id: uuid.UUID, pss_id: uuid.UUID, **overrides: object) -> None:
    """Raw insert into source_screening_result for constraint testing."""
    defaults = dict(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        screened_by_run_id=run_id,
        status="relevant",
        screen_basis="title_abstract",
        screen_decision_confidence=0.9,
        screened_at=now(),
    )
    defaults.update(overrides)
    conn.execute(source_screening_result.insert().values(**defaults))


def test_ck_bad_status(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    with pytest.raises(IntegrityError):
        _ssr_insert(conn, pid, rid, scope_id, pss_id, status="unknown_status")
    conn.rollback()
    conn.begin()


def test_ck_bad_basis(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    with pytest.raises(IntegrityError):
        _ssr_insert(conn, pid, rid, scope_id, pss_id, screen_basis="body_text")
    conn.rollback()
    conn.begin()


def test_ck_confidence_out_of_range(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    with pytest.raises(IntegrityError):
        _ssr_insert(conn, pid, rid, scope_id, pss_id, screen_decision_confidence=1.5)
    conn.rollback()
    conn.begin()


def test_ck_failed_with_non_null_basis(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    with pytest.raises(IntegrityError):
        _ssr_insert(conn, pid, rid, scope_id, pss_id,
                    status="failed", screen_basis="title_only", screen_decision_confidence=None)
    conn.rollback()
    conn.begin()


def test_ck_relevant_with_null_confidence(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    with pytest.raises(IntegrityError):
        _ssr_insert(
            conn, pid, rid, scope_id, pss_id,
            status="relevant", screen_basis="title_abstract", screen_decision_confidence=None,
        )
    conn.rollback()
    conn.begin()


def test_partial_unique_stage_matrix(conn: Connection) -> None:
    """uq_ssr_scope_source_stage: non-failed stage-1 + stage-2 rows coexist per
    (scope, source); a second non-failed stage-2 row conflicts; failed rows at
    either stage never conflict with the non-failed rows or each other."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)

    _ssr_insert(conn, pid, rid, scope_id, pss_id, screen_stage=1)
    _ssr_insert(conn, pid, rid, scope_id, pss_id, screen_stage=2, screen_basis="full_text")

    with pytest.raises(IntegrityError, match="uq_ssr_scope_source_stage"), conn.begin_nested():
        _ssr_insert(conn, pid, rid, scope_id, pss_id, screen_stage=2, screen_basis="full_text")

    _ssr_insert(
        conn, pid, rid, scope_id, pss_id, screen_stage=1,
        status="failed", screen_basis=None, screen_decision_confidence=None,
    )
    _ssr_insert(
        conn, pid, rid, scope_id, pss_id, screen_stage=2,
        status="failed", screen_basis=None, screen_decision_confidence=None,
    )
    _ssr_insert(
        conn, pid, rid, scope_id, pss_id, screen_stage=2,
        status="failed", screen_basis=None, screen_decision_confidence=None,
    )

    rows = conn.execute(
        select(source_screening_result.c.screen_stage, source_screening_result.c.status)
        .where(source_screening_result.c.project_source_snapshot_id == pss_id)
    ).fetchall()
    assert len(rows) == 5
    assert sum(1 for r in rows if r.status == "failed") == 3
    assert sum(1 for r in rows if r.status != "failed") == 2


# --- Round-trips ---

def test_screen_sources_relevant_with_abstract(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Some policy text."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).one()
    assert row.status == "relevant"
    assert row.screen_basis == "title_abstract"
    assert row.screened_by_run_id == rid


def test_screen_sources_fail_open(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).one()
    assert row.status == "relevant"
    assert row.screen_basis == "title_only"


def test_screen_sources_not_relevant(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"_stub_not_relevant": True, "abstract": "X"})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).one()
    assert row.status == "not_relevant"


def test_screen_sources_failed(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"_stub_failed": True})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).one()
    assert row.status == "failed"
    assert row.screen_basis is None
    assert row.screen_decision_confidence is None


def test_screen_sources_mixed_counts(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "X"})            # relevant, title_abstract
    seed_source(conn, pid, meta={"_stub_not_relevant": True, "abstract": "X"})  # not_relevant
    seed_source(conn, pid, meta={"_stub_failed": True})        # failed
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    counts = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["screened"] == 3
    assert counts["relevant"] == 1
    assert counts["not_relevant"] == 1
    assert counts["failed"] == 1
    assert counts["title_abstract"] == 2   # relevant + not_relevant both have abstract
    assert counts["title_only"] == 0


def test_screen_sources_unsure_unanimous_relevant_at_half_confidence(conn: Connection) -> None:
    """Three unanimous ``_stub_unsure`` reps vote relevant and average to p=0.5."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"_stub_unsure": True, "abstract": "Ambiguous evidence."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    counts = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).one()
    assert row.status == "relevant"
    assert row.screen_decision_confidence == pytest.approx(0.5)
    assert counts["relevant"] == 1
    assert counts["unsure_reps"] == 3
    assert counts["non_unanimous"] == 0


def test_screen_sources_retry_after_failure_preserves_failed_rows_and_adds_new(
    conn: Connection,
) -> None:
    """A source that fails stage-1 twice, then screens clean, keeps both failed
    rows as attempt history and gets exactly one new relevant row.

    Also proves the candidate query counts effective grain: attempt history
    (one, then two, failed rows) never inflates or deflates ``screened``.
    """
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    snap_id, pss_id = seed_source(conn, pid, meta={"_stub_failed": True})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    first = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert first["screened"] == 1
    assert first["failed"] == 1

    second = screen_sources(conn, project_id=pid, run_id=seed_run(conn, pid), context=ctx)
    assert second["screened"] == 1
    assert second["failed"] == 1

    conn.execute(
        update(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id == snap_id)
        .values(metadata={"abstract": "Now screenable evidence text."})
    )

    third = screen_sources(conn, project_id=pid, run_id=seed_run(conn, pid), context=ctx)
    assert third["screened"] == 1
    assert third["relevant"] == 1
    assert third["failed"] == 0

    rows = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_source_snapshot_id == pss_id)
        .order_by(source_screening_result.c.screened_at)
    ).fetchall()
    assert [r.status for r in rows] == ["failed", "failed", "relevant"]
    for failed_row in rows[:2]:
        assert failed_row.screen_basis is None
        assert failed_row.screen_decision_confidence is None
    assert rows[2].screen_basis == "title_abstract"


def test_screen_sources_idempotent_rerun(conn: Connection) -> None:
    """Re-running screen_sources for the same project does not raise or duplicate rows."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Some text."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    first = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert first["screened"] == 1

    second = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert second["screened"] == 0

    rows = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).fetchall()
    assert len(rows) == 1


def test_screen_sources_doc_exception_isolated(conn: Connection) -> None:
    """One document's screening exception lands as status='failed'; other docs still process."""
    class FlakyBackend:
        mode = "stub"

        def __init__(self) -> None:
            self._stub = StubScreeningBackend()

        def screen_envelope(
            self,
            payload: ScreenEnvelopePayload,
            *,
            rep_index: int = 0,
        ) -> ScreenRepWire:
            if payload.metadata.get("_boom"):
                raise RuntimeError("simulated per-doc failure")
            return self._stub.screen_envelope(payload, rep_index=rep_index)

        def screen_fulltext(self, payload: ScreenFullTextPayload) -> ScreenRepWire:
            return self._stub.screen_fulltext(payload)

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"_boom": True})
    seed_source(conn, pid, meta={"abstract": "Fine doc."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    counts = screen_sources(
        conn,
        project_id=pid,
        run_id=rid,
        context=ctx,
        screening_backend=FlakyBackend(),
    )

    assert counts["screened"] == 2
    assert counts["failed"] == 1
    assert counts["relevant"] == 1
    rows = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).fetchall()
    assert {r.status for r in rows} == {"failed", "relevant"}


def test_screen_context_from_jsonb(conn: Connection) -> None:
    """ScreenContext.context is loaded from evidence_scope.context JSONB via the harness path."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid, context={"theme": "housing", "year": 2024})
    seed_source(conn, pid, meta={"abstract": "Housing policy."})

    plan = Plan(component="screen", evidence_scope_id=scope_id)
    config = compile(plan)
    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    # Verify the JSONB round-trips through the harness DB load path (harness.py: dict(row.context))
    row = conn.execute(
        select(evidence_scope).where(evidence_scope.c.evidence_scope_id == scope_id)
    ).one()
    assert dict(row.context) == {"theme": "housing", "year": 2024}


def test_source_screened_event_payload(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    snap_id, pss_id = seed_source(conn, pid, meta={"abstract": "Policy doc."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    log_entries = events.read(conn, pid)
    screened_events = [e for e in log_entries if e["event_type"] == "source.screened"]
    assert len(screened_events) == 1
    payload = screened_events[0]["payload"]
    assert payload["source_snapshot_id"] == str(snap_id)
    assert payload["project_source_snapshot_id"] == str(pss_id)
    assert payload["evidence_scope_id"] == str(scope_id)
    assert payload["status"] == "relevant"
    assert payload["screen_basis"] == "title_abstract"
    assert payload["screen_decision_confidence"] == 0.9
    assert payload["screen_stage"] == 1
    assert payload["reps"] == [
        {
            "decision": "relevant",
            "confidence": 0.9,
            "reason": "Deterministic stub inclusion.",
        },
        {
            "decision": "relevant",
            "confidence": 0.9,
            "reason": "Deterministic stub inclusion.",
        },
        {
            "decision": "relevant",
            "confidence": 0.9,
            "reason": "Deterministic stub inclusion.",
        },
    ]
    assert payload["agreement"] == {"agreeing": 3, "survivors": 3}
    assert payload["aggregation_flags"] == []


def test_unique_constraint_scope_source(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid, meta={"abstract": "X"})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    with pytest.raises(IntegrityError):
        _ssr_insert(conn, pid, rid, scope_id, pss_id)
    conn.rollback()
    conn.begin()


def test_cross_project_fk_rejected(conn: Connection) -> None:
    pid_a, rid_a = seed_project_and_run(conn)
    pid_b, _ = seed_project_and_run(conn)

    scope_id = seed_scope(conn, pid_a)
    _, pss_id_b = seed_source(conn, pid_b)

    # scope belongs to project A, pss belongs to project B → FK violation
    _cross_cols = (
        "source_screening_result_id, evidence_scope_id, project_source_snapshot_id, "
        "project_id, screened_by_run_id, status, screen_basis, "
        "screen_decision_confidence, screened_at"
    )
    with pytest.raises(IntegrityError):
        conn.execute(sa.text(
            f"INSERT INTO source_screening_result ({_cross_cols}) "
            "VALUES (:ssrid, :scope_id, :pss_id, :pid_a, :rid_a, "
            "'relevant', 'title_abstract', 0.9, :screened_at)"
        ), {
            "ssrid": uuid.uuid4(),
            "scope_id": scope_id,
            "pss_id": pss_id_b,
            "pid_a": pid_a,
            "rid_a": rid_a,
            "screened_at": now(),
        })
    conn.rollback()
    conn.begin()


# --- Harness integration ---

def test_harness_screen_component(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Housing policy."})
    seed_source(conn, pid, meta={})

    plan = Plan(component="screen", evidence_scope_id=scope_id)
    config = compile(plan)

    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    # Two result rows
    result_rows = conn.execute(
        select(source_screening_result).where(source_screening_result.c.project_id == pid)
    ).fetchall()
    assert len(result_rows) == 2

    # component.completed payload has the stage-1 summary keys
    log_entries = events.read(conn, pid)
    completed = [e for e in log_entries if e["event_type"] == "component.completed"]
    assert len(completed) == 1
    payload = completed[0]["payload"]
    expected_keys = {
        "component", "screened", "relevant", "not_relevant",
        "failed", "title_abstract", "title_only", "unsure_reps",
        "non_unanimous", "rep_failures", "tie_broken", "retries",
    }
    assert set(payload.keys()) == expected_keys

    # Run ended as succeeded
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert run_row.status == "succeeded"


# --- Stage-2 prefix hydration (contract decision 11, rider on _load_stage2_docs) ---

def _all_chunk_segments(conn: Connection, snapshot_id: uuid.UUID) -> list[tuple[str, str]]:
    """Full ``(segment_id, content)`` list for a chunk snapshot, in sequence order."""
    rows = conn.execute(
        select(chunk_table.c.chunk_id, chunk_table.c.content)
        .where(chunk_table.c.source_snapshot_id == snapshot_id)
        .order_by(chunk_table.c.sequence)
    ).fetchall()
    return [(str(row.chunk_id), row.content) for row in rows]


def _seed_stage2_candidate(
    conn: Connection, pid: uuid.UUID, rid: uuid.UUID, scope_id: uuid.UUID, chunks: list[str],
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a stage-1-relevant doc with ingested full-text chunks.

    Returns (pss_id, chunk_snapshot_id).
    """
    _, pss_id = seed_source(conn, pid, meta={"title": "Stage-2 candidate"})
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant", screen_stage=1)
    chunk_snapshot_id = seed_ingested_full_text(conn, pss_id=pss_id, chunks=chunks)
    return pss_id, chunk_snapshot_id


def test_stage2_prefix_hydration_equivalence_large_doc(conn: Connection) -> None:
    """A doc whose chunks total well over the window budget: the payload built from the
    rider's loaded prefix is byte-identical to the first window over the full chunk list."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    chunk_texts = [f"chunk{i:03d}".ljust(3000, "x") for i in range(30)]
    pss_id, chunk_snapshot_id = _seed_stage2_candidate(conn, pid, rid, scope_id, chunk_texts)

    all_segments = _all_chunk_segments(conn, chunk_snapshot_id)
    assert len(all_segments) == 30
    expected_first_window = greedy_windows(
        all_segments, char_budget=STAGE2_WINDOW_CHAR_BUDGET, overlap_segments=0
    )[0]

    docs, skipped = _load_stage2_docs(conn, project_id=pid, scope_id=scope_id)
    assert skipped == 0
    assert len(docs) == 1
    assert docs[0].pss_id == pss_id

    payload = _stage2_payload(docs[0], intent="Test intent")
    assert payload is not None
    assert [(s["segment_id"], s["content"]) for s in payload.segments] == expected_first_window


def test_stage2_prefix_hydration_only_loads_the_prefix(conn: Connection) -> None:
    """Rev 2.4 acceptance (finding 6), tightened by the 016 review stack's
    peek-before-append fix: the loader must not materialise the whole doc, and
    (with no oversize first chunk in play here) loaded content never exceeds the
    window budget — the crossing chunk itself is peeked but never appended.
    """
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    chunk_texts = [f"chunk{i:03d}".ljust(3000, "x") for i in range(30)]
    _pss_id, chunk_snapshot_id = _seed_stage2_candidate(conn, pid, rid, scope_id, chunk_texts)

    total_in_db = conn.execute(
        select(func.count())
        .select_from(chunk_table)
        .where(chunk_table.c.source_snapshot_id == chunk_snapshot_id)
    ).scalar_one()
    assert total_in_db == 30

    docs, _skipped = _load_stage2_docs(conn, project_id=pid, scope_id=scope_id)
    loaded_chunks = docs[0].chunks
    assert len(loaded_chunks) < total_in_db

    loaded_chars = sum(len(content) for _chunk_id, content in loaded_chunks)
    assert loaded_chars <= STAGE2_WINDOW_CHAR_BUDGET


def test_stage2_prefix_hydration_oversize_single_chunk(conn: Connection) -> None:
    """A single chunk bigger than the window budget splits into ``#pN`` parts;
    only the leading split parts belong in the first window."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    oversize_chunk = "y" * (STAGE2_WINDOW_CHAR_BUDGET + 10_000)
    _pss_id, chunk_snapshot_id = _seed_stage2_candidate(
        conn, pid, rid, scope_id, [oversize_chunk]
    )

    all_segments = _all_chunk_segments(conn, chunk_snapshot_id)
    assert len(all_segments) == 1
    expected_first_window = greedy_windows(
        all_segments, char_budget=STAGE2_WINDOW_CHAR_BUDGET, overlap_segments=0
    )[0]
    # The single chunk is longer than the budget, so greedy_windows must have
    # split it into #pN sub-segments; the first window keeps only the leading
    # part (its own length equals the budget, the remainder spills to window 1).
    assert expected_first_window == [(f"{all_segments[0][0]}#p0", "y" * STAGE2_WINDOW_CHAR_BUDGET)]

    docs, skipped = _load_stage2_docs(conn, project_id=pid, scope_id=scope_id)
    assert skipped == 0
    payload = _stage2_payload(docs[0], intent="Test intent")
    assert payload is not None
    assert [(s["segment_id"], s["content"]) for s in payload.segments] == expected_first_window


def test_stage2_prefix_hydration_small_doc_unchanged(conn: Connection) -> None:
    """A doc whose chunks total well under the window budget loads (and windows) unchanged."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    chunk_texts = [f"chunk{i:03d}".ljust(1_000, "x") for i in range(5)]
    _pss_id, chunk_snapshot_id = _seed_stage2_candidate(conn, pid, rid, scope_id, chunk_texts)

    all_segments = _all_chunk_segments(conn, chunk_snapshot_id)
    assert len(all_segments) == 5

    docs, skipped = _load_stage2_docs(conn, project_id=pid, scope_id=scope_id)
    assert skipped == 0
    assert [(str(cid), content) for cid, content in docs[0].chunks] == all_segments

    windows = greedy_windows(
        all_segments, char_budget=STAGE2_WINDOW_CHAR_BUDGET, overlap_segments=0
    )
    assert len(windows) == 1
    payload = _stage2_payload(docs[0], intent="Test intent")
    assert payload is not None
    assert [(s["segment_id"], s["content"]) for s in payload.segments] == windows[0]
