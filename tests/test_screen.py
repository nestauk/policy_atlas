"""Tests for the screen component — schema, stub logic, round-trips, harness integration."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import inspect, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas import events
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import (
    evidence_scope,
    metadata,
    runs,
    source_screening_result,
)
from policy_atlas.screen import ScreenContext, _stub_screen, screen_sources
from tests.helpers import now, seed_project_and_run, seed_scope, seed_source

# --- Schema / structure ---

def test_screen_table_count(conn: Connection) -> None:
    assert len(metadata.tables) == 20


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
        "screen_decision_confidence", "screened_at",
    } <= cols


# --- Stub logic (pure Python, no DB) ---

def test_stub_relevant_with_abstract() -> None:
    result = _stub_screen({"abstract": "Some abstract text."})
    assert result.status == "relevant"
    assert result.basis == "title_abstract"
    assert result.decision_confidence == 0.9


def test_stub_relevant_without_abstract() -> None:
    result = _stub_screen({})
    assert result.status == "relevant"
    assert result.basis == "title_only"
    assert result.decision_confidence == 0.7


def test_stub_not_relevant() -> None:
    result = _stub_screen({"_stub_not_relevant": True, "abstract": "Some text."})
    assert result.status == "not_relevant"
    assert result.basis == "title_abstract"
    assert result.decision_confidence == 0.95


def test_stub_failed() -> None:
    result = _stub_screen({"_stub_failed": True})
    assert result.status == "failed"
    assert result.basis is None
    assert result.decision_confidence is None


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
        _ssr_insert(conn, pid, rid, scope_id, pss_id, screen_basis="full_text")
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


def test_screen_sources_doc_exception_isolated(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One document's screening exception lands as status='failed'; other docs still process."""
    import policy_atlas.screen as screen_mod

    original = screen_mod._stub_screen

    def flaky(meta: dict[str, Any]) -> Any:
        if meta.get("_boom"):
            raise RuntimeError("simulated per-doc failure")
        return original(meta)

    monkeypatch.setattr(screen_mod, "_stub_screen", flaky)

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"_boom": True})
    seed_source(conn, pid, meta={"abstract": "Fine doc."})
    ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})

    counts = screen_sources(conn, project_id=pid, run_id=rid, context=ctx)

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

    # component.completed payload has all seven keys
    log_entries = events.read(conn, pid)
    completed = [e for e in log_entries if e["event_type"] == "component.completed"]
    assert len(completed) == 1
    payload = completed[0]["payload"]
    expected_keys = {
        "component", "screened", "relevant", "not_relevant",
        "failed", "title_abstract", "title_only",
    }
    assert set(payload.keys()) == expected_keys

    # Run ended as succeeded
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert run_row.status == "succeeded"
