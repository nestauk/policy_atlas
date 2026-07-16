"""Tests for the appraise component — rubric, schema, round-trips, harness integration."""

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    EVIDENCE_TYPES,
    metadata,
    runs,
    source_appraisal_result,
    source_classification_result,
)
from policy_atlas.evidence_base.assess.appraise import (
    DEFAULT_RUBRIC,
    DEFAULT_RUBRIC_VERSION,
    SCORE_LABELS,
    AppraiseContext,
    appraise_sources,
)
from policy_atlas.evidence_base.assess.classify import ClassifyContext, classify_sources
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    now,
    seed_project_and_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

# --- helpers ---

def _seed_classified(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    evidence_type: str,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed a source + stage-1 relevant screening + classification row directly.

    The screening row mirrors the production precondition: classify only ever
    classifies effective-relevant docs, and appraise's write path requires
    that effective-relevant row (014 review finding).

    Returns (source_snapshot_id, pss_id).
    """
    snap_id, pss_id = seed_source(conn, project_id)
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id)
    conn.execute(source_classification_result.insert().values(
        source_classification_result_id=uuid.uuid4(),
        evidence_scope_id=scope_id,
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        classified_by_run_id=run_id,
        primary_evidence_type=evidence_type,
        classified_at=now(),
    ))
    return snap_id, pss_id


def _ctx(scope_id: uuid.UUID) -> AppraiseContext:
    return AppraiseContext(scope_id=scope_id, intent="Test", context={})


def _appraisal_rows(conn: Connection, project_id: uuid.UUID) -> list[sa.Row[Any]]:
    return list(conn.execute(
        select(source_appraisal_result).where(
            source_appraisal_result.c.project_id == project_id
        )
    ).fetchall())


# --- Schema ---

def test_table_count(conn: Connection) -> None:
    assert len(metadata.tables) == 29


# --- Rubric and labels (pure Python, no DB) ---

def test_rubric_domain_is_evidence_types_minus_non_appraisable() -> None:
    non_appraisable = {"Other (Non-evidence documents)", "Unknown / Insufficient information"}
    assert set(DEFAULT_RUBRIC) == set(EVIDENCE_TYPES) - non_appraisable
    assert all(score in range(1, 6) for score in DEFAULT_RUBRIC.values())


def test_rubric_matches_v2_hierarchy_exactly() -> None:
    assert DEFAULT_RUBRIC == {
        "Systematic Review and Meta-Analysis":   5,
        "RCTs and Quasi-Experimental Studies":   4,
        "Observational Research Studies":        3,
        "Modelling & Simulation":                2,
        "Policy Syntheses & Guidance Documents": 2,
        "Qualitative & Contextual Evidence":     2,
        "Expert Opinion and Commentary":         1,
    }


def test_score_labels_domain() -> None:
    # Wording itself is untested — presentation copy, retune freely.
    assert set(SCORE_LABELS) == {1, 2, 3, 4, 5}


# --- Round-trips ---

def test_appraise_sources_round_trip_via_classify(conn: Connection) -> None:
    """Full chain: sentinel metadata → classify → appraise; scores match the rubric."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    sentinels = {
        "_stub_systematic_review": 5,
        "_stub_rct": 4,
        "_stub_expert_opinion": 1,
    }
    pss_by_score = {}
    for sentinel, score in sentinels.items():
        _, pss_id = seed_source(conn, pid, meta={sentinel: True})
        seed_screening_result(conn, pid, rid, scope_id, pss_id)
        pss_by_score[pss_id] = score
    classify_sources(
        conn, project_id=pid, run_id=rid,
        context=ClassifyContext(scope_id=scope_id, intent="Test", context={}),
    )

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["appraised"] == 3
    assert counts["by_score"] == {5: 1, 4: 1, 1: 1}
    rows = _appraisal_rows(conn, pid)
    assert {r.project_source_snapshot_id: r.quality_score for r in rows} == pss_by_score


def test_non_evidence_skipped_and_counted(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Other (Non-evidence documents)")

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["appraised"] == 0
    assert counts["skipped_non_evidence"] == 1
    assert counts["skipped_unknown"] == 0
    assert _appraisal_rows(conn, pid) == []


def test_unknown_skipped_and_counted(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Unknown / Insufficient information")

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["appraised"] == 0
    assert counts["skipped_unknown"] == 1
    assert counts["skipped_non_evidence"] == 0
    assert _appraisal_rows(conn, pid) == []


def test_unclassified_counted_not_appraised(conn: Connection) -> None:
    """A relevant screening row with no classification row is reported, never processed."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id)

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["appraised"] == 0
    assert counts["unclassified"] == 1
    assert _appraisal_rows(conn, pid) == []


def test_demoted_doc_not_counted_unclassified(conn: Connection) -> None:
    """A stage-2-demoted doc's stale stage-1 'relevant' row must not inflate
    'unclassified' (task 014 sweep: effective-stage-and-status grain — a raw
    status='relevant' join would count this doc even though classify correctly
    never classified it)."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="relevant", screen_stage=1)
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="not_relevant", screen_stage=2)

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["appraised"] == 0
    assert counts["unclassified"] == 0
    assert _appraisal_rows(conn, pid) == []


def test_classified_then_demoted_not_appraised_on_rerun(conn: Connection) -> None:
    """A doc classified while effective-relevant, then stage-2 demoted, must
    not gain an appraisal on a later appraise run (014 review finding: the
    appraise WRITE path is effective-grained too, not just the audit counts);
    the exclusion is counted, never silent."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = _seed_classified(conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis")
    seed_screening_result(conn, pid, rid, scope_id, pss_id, status="not_relevant", screen_stage=2)

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["appraised"] == 0
    assert counts["skipped_demoted"] == 1
    assert _appraisal_rows(conn, pid) == []

    # An earlier-appraised doc that is demoted later counts once (already_appraised),
    # never twice.
    _, pss_second = _seed_classified(conn, pid, rid, scope_id, "Observational Research Studies")
    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))
    assert counts["appraised"] == 1
    seed_screening_result(
        conn, pid, rid, scope_id, pss_second, status="not_relevant", screen_stage=2
    )
    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))
    assert counts["already_appraised"] == 1
    assert counts["skipped_demoted"] == 1


def test_appraise_sources_idempotent_rerun(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis")
    _seed_classified(conn, pid, rid, scope_id, "Observational Research Studies")

    first = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))
    assert first["appraised"] == 2
    assert first["already_appraised"] == 0

    second = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))
    assert second["appraised"] == 0
    assert second["already_appraised"] == 2
    assert second["by_score"] == {}
    assert len(_appraisal_rows(conn, pid)) == 2


def test_mixed_rerun_skip_counts_stable_and_invariant_holds(conn: Connection) -> None:
    """Skip counts are recomputed per call, not accumulated; the counting invariant holds."""
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis")
    _seed_classified(conn, pid, rid, scope_id, "Other (Non-evidence documents)")
    _seed_classified(conn, pid, rid, scope_id, "Unknown / Insufficient information")
    classification_rows = 3
    # A relevant-but-unclassified row: recomputed per call, like the skip counts
    _, pss_unclassified = seed_source(conn, pid)
    seed_screening_result(conn, pid, rid, scope_id, pss_unclassified)

    for expected_appraised, expected_already in [(1, 0), (0, 1)]:
        counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))
        assert counts["appraised"] == expected_appraised
        assert counts["already_appraised"] == expected_already
        assert counts["skipped_non_evidence"] == 1
        assert counts["skipped_unknown"] == 1
        assert counts["unclassified"] == 1
        assert (
            counts["appraised"] + counts["already_appraised"]
            + counts["skipped_non_evidence"] + counts["skipped_unknown"]
            + counts["skipped_demoted"]
            == classification_rows
        )


def test_by_score_is_sparse(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis")

    counts = appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    assert counts["by_score"] == {5: 1}  # no zero-valued keys for unobserved scores


def test_rubric_version_persisted_on_every_row(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "RCTs and Quasi-Experimental Studies")
    _seed_classified(conn, pid, rid, scope_id, "Expert Opinion and Commentary")

    appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    rows = _appraisal_rows(conn, pid)
    assert len(rows) == 2
    assert all(r.rubric_version == "v2-hierarchy-v1" for r in rows)
    assert DEFAULT_RUBRIC_VERSION == "v2-hierarchy-v1"


def test_appraised_by_run_id(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Modelling & Simulation")

    appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    (row,) = _appraisal_rows(conn, pid)
    assert row.appraised_by_run_id == rid


# --- Check / unique / FK constraints ---

@pytest.mark.parametrize("bad_score", [0, 6])
def test_ck_quality_score_bounds(conn: Connection, bad_score: int) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_id = seed_source(conn, pid)

    with pytest.raises(IntegrityError):
        conn.execute(source_appraisal_result.insert().values(
            source_appraisal_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=pid,
            appraised_by_run_id=rid,
            quality_score=bad_score,
            rubric_version=DEFAULT_RUBRIC_VERSION,
            appraised_at=now(),
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
            "INSERT INTO source_appraisal_result "
            "(source_appraisal_result_id, evidence_scope_id, project_source_snapshot_id, "
            " project_id, appraised_by_run_id, quality_score, rubric_version, appraised_at) "
            "VALUES (:sarid, :scope_id, :pss_id, :pid_a, :rid_a, 3, 'v2-hierarchy-v1', :ts)"
        ), {
            "sarid": uuid.uuid4(),
            "scope_id": scope_id,
            "pss_id": pss_id_b,
            "pid_a": pid_a,
            "rid_a": rid_a,
            "ts": now(),
        })
    conn.rollback()
    conn.begin()


def test_uq_scope_source_duplicate(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis")

    appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))
    (row,) = _appraisal_rows(conn, pid)

    with pytest.raises(IntegrityError):
        conn.execute(source_appraisal_result.insert().values(
            source_appraisal_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=row.project_source_snapshot_id,
            project_id=pid,
            appraised_by_run_id=rid,
            quality_score=5,
            rubric_version=DEFAULT_RUBRIC_VERSION,
            appraised_at=now(),
        ))
    conn.rollback()
    conn.begin()


# --- Harness integration ---

def test_harness_appraise_component(conn: Connection) -> None:
    pid, rid_screen = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _, pss_sr = seed_source(conn, pid, meta={"_stub_systematic_review": True})
    _, pss_non_ev = seed_source(conn, pid, meta={"_stub_non_evidence": True})
    seed_screening_result(conn, pid, rid_screen, scope_id, pss_sr)
    seed_screening_result(conn, pid, rid_screen, scope_id, pss_non_ev)
    classify_sources(
        conn, project_id=pid, run_id=rid_screen,
        context=ClassifyContext(scope_id=scope_id, intent="Test", context={}),
    )

    rid_appraise = uuid.uuid4()
    conn.execute(runs.insert().values(
        run_id=rid_appraise, project_id=pid, status="running", started_at=now()
    ))

    plan = Plan(component="appraise", evidence_scope_id=scope_id)
    run_harness(
        conn, config=compile(plan), project_id=pid, run_id=rid_appraise,
        provider=StubEchoProvider(),
    )

    # One appraisal row (only the SR source; non-evidence skipped)
    rows = _appraisal_rows(conn, pid)
    assert len(rows) == 1
    assert rows[0].project_source_snapshot_id == pss_sr
    assert rows[0].quality_score == 5

    log_entries = events.read(conn, pid)
    completed = [e for e in log_entries if e["event_type"] == "component.completed"
                 and e["payload"].get("component") == "appraise"]
    assert len(completed) == 1
    payload = completed[0]["payload"]
    assert payload["appraised"] == 1
    assert payload["by_score"] == {"5": 1}  # JSON object keys are strings
    assert payload["skipped_non_evidence"] == 1
    assert payload["skipped_unknown"] == 0
    assert payload["already_appraised"] == 0
    assert payload["unclassified"] == 0

    # No source.appraised event for the skipped row
    appraised_events = [e for e in log_entries if e["event_type"] == "source.appraised"]
    assert len(appraised_events) == 1
    assert appraised_events[0]["payload"]["project_source_snapshot_id"] == str(pss_sr)

    run_row = conn.execute(select(runs).where(runs.c.run_id == rid_appraise)).one()
    assert run_row.status == "succeeded"


def test_source_appraised_event_payload(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    snap_id, pss_id = _seed_classified(
        conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis"
    )

    appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    log_entries = events.read(conn, pid)
    appraised_events = [e for e in log_entries if e["event_type"] == "source.appraised"]
    assert len(appraised_events) == 1
    assert appraised_events[0]["payload"] == {
        "source_snapshot_id": str(snap_id),
        "project_source_snapshot_id": str(pss_id),
        "evidence_scope_id": str(scope_id),
        "quality_score": 5,
        "rubric_version": "v2-hierarchy-v1",
    }


def test_delete_project_data_removes_appraisal(conn: Connection) -> None:
    from tests.helpers import delete_project_data

    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)
    _seed_classified(conn, pid, rid, scope_id, "Systematic Review and Meta-Analysis")
    appraise_sources(conn, project_id=pid, run_id=rid, context=_ctx(scope_id))

    count_before = conn.execute(
        sa.select(sa.func.count()).select_from(source_appraisal_result)
        .where(source_appraisal_result.c.project_id == pid)
    ).scalar_one()
    assert count_before == 1

    conn.commit()
    delete_project_data(conn, pid)
    conn.commit()

    count_after = conn.execute(
        sa.select(sa.func.count()).select_from(source_appraisal_result)
        .where(source_appraisal_result.c.project_id == pid)
    ).scalar_one()
    assert count_after == 0
