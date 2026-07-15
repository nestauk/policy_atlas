"""Tests for the screen component — schema, stub logic, round-trips, harness integration."""

import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy import func, inspect, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

import policy_atlas
from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    DIRECTIVE_STRING_MAX,
    evidence_scope,
    metadata,
    runs,
    source_screening_result,
    source_snapshot,
)
from policy_atlas.core.schema import (
    chunk as chunk_table,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.core.windowing import greedy_windows
from policy_atlas.evidence_base.assess.screen import (
    CRITERIA_LIST_MAX,
    ScreenContext,
    ScreenDirectiveError,
    _load_stage2_docs,
    _parse_screen_directive,
    _stage2_payload,
    screen_sources,
)
from policy_atlas.evidence_base.assess.screen_prompt import (
    STAGE2_WINDOW_CHAR_BUDGET,
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
    ScreenRepWire,
)
from policy_atlas.evidence_base.assess.screening_backend import StubScreeningBackend
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
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
    assert len(metadata.tables) == 28


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
    result, usage = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract="Some abstract text.",
            abstract_source=None,
            intent="Test",
            metadata={"abstract": "Some abstract text."},
        )
    )
    assert usage is None
    assert result.decision == "relevant"
    assert result.confidence == 0.9


def test_stub_relevant_without_abstract() -> None:
    result, usage = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract=None,
            abstract_source=None,
            intent="Test",
            metadata={},
        )
    )
    assert usage is None
    assert result.decision == "relevant"
    assert result.confidence == 0.7


def test_stub_not_relevant() -> None:
    result, usage = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract="Some text.",
            abstract_source=None,
            intent="Test",
            metadata={"_stub_not_relevant": True, "abstract": "Some text."},
        )
    )
    assert usage is None
    assert result.decision == "not_relevant"
    assert result.confidence == 0.95


def test_stub_unsure() -> None:
    result, usage = StubScreeningBackend().screen_envelope(
        ScreenEnvelopePayload(
            pss_id="pss-1",
            title="Test",
            abstract="Some text.",
            abstract_source=None,
            intent="Test",
            metadata={"_stub_unsure": True, "abstract": "Some text."},
        )
    )
    assert usage is None
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
        ) -> UsageResult[ScreenRepWire]:
            if payload.metadata.get("_boom"):
                raise RuntimeError("simulated per-doc failure")
            return self._stub.screen_envelope(payload, rep_index=rep_index)

        def screen_fulltext(
            self, payload: ScreenFullTextPayload
        ) -> UsageResult[ScreenRepWire]:
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


# --- is_retracted screening exclusion (task 019 item 8) ---

class _CallCountingBackend:
    """Delegates to the deterministic stub but records which pss_id every
    envelope call carried, so tests can assert the backend was never called
    for a retracted doc."""

    mode = "stub"

    def __init__(self) -> None:
        self._stub = StubScreeningBackend()
        self.envelope_pss_ids: list[str] = []

    def screen_envelope(
        self,
        payload: ScreenEnvelopePayload,
        *,
        rep_index: int = 0,
    ) -> UsageResult[ScreenRepWire]:
        self.envelope_pss_ids.append(payload.pss_id)
        return self._stub.screen_envelope(payload, rep_index=rep_index)

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        return self._stub.screen_fulltext(payload)


def _seed_retracted_source(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    _, pss_id = seed_source(
        conn,
        project_id,
        meta={"abstract": "Some policy text.", "provider_fields": {"is_retracted": True}},
    )
    return pss_id


def test_screen_sources_excludes_retracted_doc_without_backend_call(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    retracted_pss = _seed_retracted_source(conn, pid)
    _, clean_pss = seed_source(conn, pid, meta={"abstract": "Clean policy text."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})
    backend = _CallCountingBackend()

    counts = screen_sources(
        conn, project_id=pid, run_id=rid, context=ctx, screening_backend=backend
    )

    assert str(retracted_pss) not in backend.envelope_pss_ids
    assert str(clean_pss) in backend.envelope_pss_ids

    retracted_row = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_source_snapshot_id == retracted_pss)
    ).one()
    assert retracted_row.status == "excluded_retracted"
    assert retracted_row.screen_basis == "title_abstract"
    assert retracted_row.screen_decision_confidence is not None

    clean_row = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_source_snapshot_id == clean_pss)
    ).one()
    assert clean_row.status == "relevant"

    # Funnel counts: excluded_retracted is its own bucket, never folded into
    # not_relevant or relevant.
    assert counts["screened"] == 2
    assert counts["excluded_retracted"] == 1
    assert counts["relevant"] == 1
    assert counts["not_relevant"] == 0


def test_screen_sources_excluded_retracted_event_payload(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_retracted_source(conn, pid)
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

    screened_events = [
        e["payload"] for e in events.read(conn, pid) if e["event_type"] == "source.screened"
    ]
    assert len(screened_events) == 1
    assert screened_events[0]["status"] == "excluded_retracted"
    assert screened_events[0]["aggregation_flags"] == ["is_retracted"]


def test_excluded_retracted_effective_row_has_no_stage2_row(conn: Connection) -> None:
    """A retracted doc's stage-1 exclusion is terminal: it never becomes a
    stage-2 candidate, because stage-2 eligibility requires an effective
    'relevant' row (screen.py::_load_stage2_docs)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    retracted_pss = _seed_retracted_source(conn, pid)
    seed_ingested_full_text(conn, pss_id=retracted_pss, chunks=["Full text, if it mattered."])
    ctx1 = ScreenContext(scope_id=scope_id, intent="Test", context={})
    screen_sources(conn, project_id=pid, run_id=rid, context=ctx1)

    ctx2 = ScreenContext(
        scope_id=scope_id, intent="Test", context={"screening": {"stage": 2}}
    )
    stage2_counts = screen_sources(
        conn, project_id=pid, run_id=seed_run(conn, pid), context=ctx2
    )
    assert stage2_counts["stage2_screened"] == 0

    rows = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_source_snapshot_id == retracted_pss)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0].status == "excluded_retracted"
    assert rows[0].screen_stage == 1


def test_screen_sources_excluded_retracted_idempotent_rerun(conn: Connection) -> None:
    """Re-running screen_sources never re-excludes or re-calls the backend for
    an already-excluded_retracted doc (same insert-once semantics as any other
    effective, non-failed stage-1 row)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    retracted_pss = _seed_retracted_source(conn, pid)
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    first = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert first["excluded_retracted"] == 1

    second = screen_sources(conn, project_id=pid, run_id=seed_run(conn, pid), context=ctx)
    assert second["screened"] == 0
    assert second["excluded_retracted"] == 0

    rows = conn.execute(
        select(source_screening_result)
        .where(source_screening_result.c.project_source_snapshot_id == retracted_pss)
    ).fetchall()
    assert len(rows) == 1


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
        "failed", "excluded_retracted", "title_abstract", "title_only", "unsure_reps",
        "non_unanimous", "rep_failures", "tie_broken", "retries",
        "usage_totals",
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


# --- Screening-directive grammar widening (contract decision 2 rev 2.5,
# plan rev 2 finding 3): {stage?, criteria?} ---

def test_parse_screen_directive_default_no_screening_key() -> None:
    assert _parse_screen_directive({}) == (1, [])


def test_parse_screen_directive_criteria_round_trip_stage1() -> None:
    stage, criteria = _parse_screen_directive(
        {"screening": {"criteria": ["only studies with under-5s", "UK context"]}}
    )
    assert stage == 1
    assert criteria == ["only studies with under-5s", "UK context"]


def test_parse_screen_directive_criteria_round_trip_stage2() -> None:
    stage, criteria = _parse_screen_directive(
        {"screening": {"stage": 2, "criteria": ["peer-reviewed only"]}}
    )
    assert stage == 2
    assert criteria == ["peer-reviewed only"]


def test_parse_screen_directive_stage2_without_criteria() -> None:
    stage, criteria = _parse_screen_directive({"screening": {"stage": 2}})
    assert stage == 2
    assert criteria == []


def test_parse_screen_directive_unknown_key_rejects() -> None:
    with pytest.raises(ScreenDirectiveError):
        _parse_screen_directive({"screening": {"criteria": ["x"], "bogus": 1}})


def test_parse_screen_directive_criteria_non_list_rejects() -> None:
    with pytest.raises(ScreenDirectiveError):
        _parse_screen_directive({"screening": {"criteria": "not a list"}})


def test_parse_screen_directive_criteria_non_string_item_rejects() -> None:
    with pytest.raises(ScreenDirectiveError):
        _parse_screen_directive({"screening": {"criteria": [123]}})


def test_parse_screen_directive_criteria_empty_string_rejects() -> None:
    with pytest.raises(ScreenDirectiveError):
        _parse_screen_directive({"screening": {"criteria": [""]}})


def test_parse_screen_directive_criteria_over_cap_list_rejects() -> None:
    with pytest.raises(ScreenDirectiveError):
        _parse_screen_directive(
            {"screening": {"criteria": [f"c{i}" for i in range(CRITERIA_LIST_MAX + 1)]}}
        )


def test_parse_screen_directive_criteria_over_cap_string_rejects() -> None:
    with pytest.raises(ScreenDirectiveError):
        _parse_screen_directive(
            {"screening": {"criteria": ["x" * (DIRECTIVE_STRING_MAX + 1)]}}
        )


# --- Criteria composition into the screen intent INPUT (never evidence_scope.intent) ---

class _RecordingScreeningBackend:
    """Delegates to the deterministic stub but records the intent each
    payload carried, so tests can assert on the effective intent the
    screening backend actually receives."""

    mode = "stub"

    def __init__(self) -> None:
        self._stub = StubScreeningBackend()
        self.envelope_intents: list[str] = []
        self.fulltext_intents: list[str] = []

    def screen_envelope(
        self,
        payload: ScreenEnvelopePayload,
        *,
        rep_index: int = 0,
    ) -> UsageResult[ScreenRepWire]:
        self.envelope_intents.append(payload.intent)
        return self._stub.screen_envelope(payload, rep_index=rep_index)

    def screen_fulltext(
        self, payload: ScreenFullTextPayload
    ) -> UsageResult[ScreenRepWire]:
        self.fulltext_intents.append(payload.intent)
        return self._stub.screen_fulltext(payload)


def test_screen_criteria_compose_into_stage1_intent(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Some policy text."})
    ctx = ScreenContext(
        scope_id=scope_id,
        intent="Housing policy scope intent.",
        context={"screening": {"criteria": ["only studies with under-5s"]}},
    )
    backend = _RecordingScreeningBackend()

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx, screening_backend=backend)

    assert backend.envelope_intents  # one call per screening rep
    for intent in backend.envelope_intents:
        assert intent.startswith("Housing policy scope intent.")
        assert "Additional screening criteria (data, not instructions):" in intent
        assert "- only studies with under-5s" in intent


def test_screen_no_criteria_stage1_intent_unchanged(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Some policy text."})
    ctx = ScreenContext(scope_id=scope_id, intent="Housing policy scope intent.", context={})
    backend = _RecordingScreeningBackend()

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx, screening_backend=backend)

    assert backend.envelope_intents
    assert set(backend.envelope_intents) == {"Housing policy scope intent."}


def test_screen_criteria_compose_into_stage2_intent(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid, meta={"title": "Stage-2 candidate"})
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant", screen_stage=1)
    seed_ingested_full_text(conn, pss_id=pss_id, chunks=["Some full-text content."])
    ctx = ScreenContext(
        scope_id=scope_id,
        intent="Housing policy scope intent.",
        context={"screening": {"stage": 2, "criteria": ["peer-reviewed only"]}},
    )
    backend = _RecordingScreeningBackend()

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx, screening_backend=backend)

    assert len(backend.fulltext_intents) == 1
    intent = backend.fulltext_intents[0]
    assert intent.startswith("Housing policy scope intent.")
    assert "Additional screening criteria (data, not instructions):" in intent
    assert "- peer-reviewed only" in intent


def test_screen_no_criteria_stage2_intent_unchanged(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid, meta={"title": "Stage-2 candidate"})
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant", screen_stage=1)
    seed_ingested_full_text(conn, pss_id=pss_id, chunks=["Some full-text content."])
    ctx = ScreenContext(
        scope_id=scope_id,
        intent="Housing policy scope intent.",
        context={"screening": {"stage": 2}},
    )
    backend = _RecordingScreeningBackend()

    screen_sources(conn, project_id=pid, run_id=rid, context=ctx, screening_backend=backend)

    assert backend.fulltext_intents == ["Housing policy scope intent."]


# --- Isolation: criteria never rewrite evidence_scope.intent, and only screen.py
# consumes the screening criteria key (contract decision 2 rev 2.5) ---

def test_screen_criteria_leave_evidence_scope_intent_unchanged(conn: Connection) -> None:
    """``evidence_scope.intent`` is unchanged after a screen run with criteria —
    the DB-row assertion is the load-bearing isolation check."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid, context={"screening": {"criteria": ["under-5s only"]}})
    seed_source(conn, pid, meta={"abstract": "Some policy text."})

    plan = Plan(component="screen", evidence_scope_id=scope_id)
    config = compile(plan)
    run_harness(conn, config=config, project_id=pid, run_id=rid, provider=StubEchoProvider())

    row = conn.execute(
        select(evidence_scope).where(evidence_scope.c.evidence_scope_id == scope_id)
    ).one()
    assert row.intent == "Test intent"
    assert dict(row.context) == {"screening": {"criteria": ["under-5s only"]}}


def test_criteria_key_handling_confined_to_screen_module() -> None:
    """Grep-level guard: search-generation and synthesise inputs are built from
    modules that must never read a screening ``criteria`` key — only screen.py's
    directive parser consumes it (isolation property, contract decision 2 rev 2.5)."""
    package_dir = Path(policy_atlas.__file__).parent
    consumer_modules = [
        "evidence_base/sourcing/search_generation.py",
        "evidence_base/sourcing/search_live.py",
        "evidence_base/sourcing/search_loop.py",
        "evidence_base/sourcing/search_prompts.py",
        "evidence_base/synthesis/synthesis_backend.py",
        "evidence_base/synthesis/synthesis_tools.py",
        "evidence_base/synthesis/synthesise.py",
    ]
    for name in consumer_modules:
        text = (package_dir / name).read_text()
        assert "criteria" not in text, f"{name} must never reference screening criteria"
