"""Tests for the classify component — schema, stub logic, round-trips, harness integration."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas import events
from policy_atlas.classify import ClassifyContext, _stub_classify, classify_sources
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import (
    metadata,
    runs,
    source_classification_result,
    source_screening_result,
)
from tests.helpers import (
    now,
    seed_project_and_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

# --- Schema ---

def test_table_count(conn: Connection) -> None:
    assert len(metadata.tables) == 23


# --- Stub logic (pure Python, no DB) ---

def test_stub_default_unknown() -> None:
    result = _stub_classify({})
    assert result.primary_evidence_type == "Unknown / Insufficient information"


def test_stub_non_evidence() -> None:
    result = _stub_classify({"_stub_non_evidence": True})
    assert result.primary_evidence_type == "Other (Non-evidence documents)"


def test_stub_policy_guidance() -> None:
    result = _stub_classify({"_stub_policy_guidance": True})
    assert result.primary_evidence_type == "Policy Syntheses & Guidance Documents"


def test_stub_rct() -> None:
    result = _stub_classify({"_stub_rct": True})
    assert result.primary_evidence_type == "RCTs and Quasi-Experimental Studies"


# --- Round-trips ---

def test_classify_sources_round_trip(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1
    assert rows[0].evidence_scope_id == scope_id
    assert rows[0].project_source_snapshot_id == pss_id


def test_classify_sources_non_evidence_persists(conn: Connection) -> None:
    """Non-evidence rows land in source_classification_result (flag-don't-drop)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid, meta={"_stub_non_evidence": True})
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).one()
    assert row.primary_evidence_type == "Other (Non-evidence documents)"


def test_classify_sources_skips_not_relevant(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_relevant = seed_source(conn, pid)
    _, pss_not_relevant = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_relevant, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, pss_not_relevant, status="not_relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 1
    assert counts["skipped"] == 1
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1


def test_classify_sources_skips_failed(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_failed = seed_source(conn, pid)
    # Insert failed row manually (no basis/confidence)
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_failed,
        project_id=pid,
        screened_by_run_id=rid,
        status="failed",
        screen_basis=None,
        screen_decision_confidence=None,
        screened_at=now(),
    ))

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 0
    assert counts["skipped"] == 1


def test_classify_count_invariant(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, p1 = seed_source(conn, pid)
    _, p2 = seed_source(conn, pid)
    _, p3 = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, p1, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, p2, status="not_relevant")
    conn.execute(source_screening_result.insert().values(
        source_screening_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=p3,
        project_id=pid,
        screened_by_run_id=rid,
        status="failed",
        screen_basis=None,
        screen_decision_confidence=None,
        screened_at=now(),
    ))

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] + counts["skipped"] + counts["already_classified"] == 3


def test_classify_sources_idempotent_rerun(conn: Connection) -> None:
    """Re-running classify_sources for the same scope does not raise or duplicate rows."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    first = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert first["classified"] == 1
    assert first["already_classified"] == 0

    second = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)
    assert second["classified"] == 0
    assert second["already_classified"] == 1
    assert second["classified"] + second["skipped"] + second["already_classified"] == 1

    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1


def test_classified_by_run_id(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    row = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).one()
    assert row.classified_by_run_id == rid


# --- Check / unique constraints ---

def test_ck_bad_primary_evidence_type(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)

    with pytest.raises(IntegrityError):
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=pid,
            classified_by_run_id=rid,
            primary_evidence_type="Not A Valid Type",
            classified_at=now(),
        ))
    conn.rollback()
    conn.begin()


def test_uq_scope_source_duplicate(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    with pytest.raises(IntegrityError):
        conn.execute(source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=pid,
            classified_by_run_id=rid,
            primary_evidence_type="Unknown / Insufficient information",
            classified_at=now(),
        ))
    conn.rollback()
    conn.begin()


def test_cross_project_fk_rejected(conn: Connection) -> None:
    pid_a, rid_a = seed_project_and_run(conn)
    pid_b, _ = seed_project_and_run(conn)

    scope_id = seed_scope(conn, pid_a)
    _, pss_id_b = seed_source(conn, pid_b)

    # scope belongs to project A, pss belongs to project B → FK violation
    with pytest.raises(IntegrityError):
        conn.execute(sa.text(
            "INSERT INTO source_classification_result "
            "(source_classification_result_id, evidence_scope_id, project_source_snapshot_id, "
            " project_id, classified_by_run_id, primary_evidence_type, classified_at) "
            "VALUES (:scrid, :scope_id, :pss_id, :pid_a, :rid_a, "
            "'Unknown / Insufficient information', :ts)"
        ), {
            "scrid": uuid.uuid4(),
            "scope_id": scope_id,
            "pss_id": pss_id_b,
            "pid_a": pid_a,
            "rid_a": rid_a,
            "ts": now(),
        })
    conn.rollback()
    conn.begin()


def test_classify_sources_doc_exception_isolated(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One document's classify exception falls back to Unknown; other docs still process."""
    import policy_atlas.classify as classify_mod

    original = classify_mod._stub_classify

    def flaky(meta: dict[str, Any]) -> Any:
        if meta.get("_boom"):
            raise RuntimeError("simulated per-doc failure")
        return original(meta)

    monkeypatch.setattr(classify_mod, "_stub_classify", flaky)

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_boom = seed_source(conn, pid, meta={"_boom": True})
    _, pss_fine = seed_source(conn, pid, meta={"_stub_rct": True})
    seed_screening_result(conn, pid, rid, scope_id, pss_boom, status="relevant")
    seed_screening_result(conn, pid, rid, scope_id, pss_fine, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    counts = classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    assert counts["classified"] == 2
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    by_pss = {r.project_source_snapshot_id: r.primary_evidence_type for r in rows}
    assert by_pss[pss_boom] == "Unknown / Insufficient information"
    assert by_pss[pss_fine] == "RCTs and Quasi-Experimental Studies"


# --- Harness integration ---

def test_harness_classify_component(conn: Connection) -> None:
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    seed_source(conn, pid, meta={"abstract": "Housing policy."})
    seed_source(conn, pid, meta={"_stub_not_relevant": True, "abstract": "Off-topic."})

    # Screen first so there are relevant rows
    from policy_atlas.screen import ScreenContext, screen_sources
    screen_ctx = ScreenContext(scope_id=scope_id, intent="Test", context={})
    screen_sources(conn, project_id=pid, run_id=rid_screen, context=screen_ctx)

    # Create a second run for classify
    rid_classify = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid_classify, project_id=pid, status="running", started_at=now()
    ))

    plan = Plan(component="classify", evidence_scope_id=scope_id)
    config = compile(plan)
    run_harness(
        conn, config=config, project_id=pid, run_id=rid_classify, provider=StubEchoProvider()
    )

    # One classification row (only the relevant source)
    rows = conn.execute(
        select(source_classification_result).where(
            source_classification_result.c.project_id == pid
        )
    ).fetchall()
    assert len(rows) == 1

    # component.completed payload has the right keys
    log_entries = events.read(conn, pid)
    completed = [e for e in log_entries if e["event_type"] == "component.completed"
                 and e["payload"].get("component") == "classify"]
    assert len(completed) == 1
    payload = completed[0]["payload"]
    assert set(payload.keys()) >= {"component", "classified", "by_type", "skipped"}
    assert payload["classified"] == 1
    assert payload["skipped"] == 1

    # Run ended as succeeded
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid_classify)).one()
    assert run_row.status == "succeeded"


def test_source_classified_event_payload(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    snap_id, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    log_entries = events.read(conn, pid)
    classified_events = [e for e in log_entries if e["event_type"] == "source.classified"]
    assert len(classified_events) == 1
    p = classified_events[0]["payload"]
    assert p["source_snapshot_id"] == str(snap_id)
    assert p["project_source_snapshot_id"] == str(pss_id)
    assert p["evidence_scope_id"] == str(scope_id)
    assert p["primary_evidence_type"] == "Unknown / Insufficient information"


def test_delete_project_data_removes_classification(conn: Connection) -> None:
    from tests.helpers import delete_project_data

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant")

    ctx = ClassifyContext(scope_id=scope_id, intent="Test", context={})
    classify_sources(conn, project_id=pid, run_id=rid, context=ctx)

    # Verify row exists
    count_before = conn.execute(
        sa.select(sa.func.count()).select_from(source_classification_result)
        .where(source_classification_result.c.project_id == pid)
    ).scalar_one()
    assert count_before == 1

    conn.commit()
    delete_project_data(conn, pid)
    conn.commit()

    count_after = conn.execute(
        sa.select(sa.func.count()).select_from(source_classification_result)
        .where(source_classification_result.c.project_id == pid)
    ).scalar_one()
    assert count_after == 0
