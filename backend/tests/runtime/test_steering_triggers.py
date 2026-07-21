"""Trigger-floor reader tests (task 024, contract decision 8).

Every reader is a pure SELECT over persisted state: seeded rows only, no
runner walk. Each class gets a fired case and a not-fired case seeded exactly
at/over and under its threshold.
"""

from __future__ import annotations

import inspect
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import (
    event_log,
    extraction_result,
    grouping_result,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
)
from policy_atlas.runtime import steering_triggers as st
from tests.helpers import (
    now,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

_seed_project_run = seed_project_and_run

# --- Local seed helpers (no existing tests/helpers seeder for these tables) --


def _seed_coverage_record(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    run_id: uuid.UUID,
    adequacy_verdict: str = "adequate",
    stop_condition: str = "completed",
) -> None:
    conn.execute(
        search_coverage_record.insert().values(
            search_coverage_record_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_id=project_id,
            acquired_by_run_id=run_id,
            backends=[{"backend": "openalex", "trust_class": "curated", "mode": "fixture"}],
            scope_filters={},
            stop_condition=stop_condition,
            adequacy_verdict=adequacy_verdict,
            verdict_origin="model",
            created_at=now(),
        )
    )


def _seed_classification_rows(
    conn: Connection, *, project_id: uuid.UUID, scope_id: uuid.UUID, types: list[str]
) -> uuid.UUID:
    run_id = seed_run(conn, project_id)
    for evidence_type in types:
        _, pss_id = seed_source(conn, project_id)
        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=project_id,
                classified_by_run_id=run_id,
                primary_evidence_type=evidence_type,
                classified_at=now(),
            )
        )
    return run_id


def _seed_appraisal_rows(
    conn: Connection, *, project_id: uuid.UUID, scope_id: uuid.UUID, scores: list[int]
) -> uuid.UUID:
    run_id = seed_run(conn, project_id)
    for score in scores:
        _, pss_id = seed_source(conn, project_id)
        conn.execute(
            source_appraisal_result.insert().values(
                source_appraisal_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=project_id,
                appraised_by_run_id=run_id,
                quality_score=score,
                rubric_version="v1",
                appraised_at=now(),
            )
        )
    return run_id


def _seed_selection_result(
    conn: Connection, *, project_id: uuid.UUID, scope_id: uuid.UUID
) -> uuid.UUID:
    run_id = seed_run(conn, project_id)
    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[],
            excluded={},
            flags={},
            created_at=now(),
        )
    )
    return run_id


def _seed_extraction_result(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    counts: dict[str, Any],
) -> uuid.UUID:
    selection_run_id = _seed_selection_result(conn, project_id=project_id, scope_id=scope_id)
    run_id = seed_run(conn, project_id)
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={},
            docs=[],
            counts=counts,
            flags=[],
            created_at=now(),
        )
    )
    return run_id


def _seed_grouping_result(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    flags: dict[str, Any],
) -> uuid.UUID:
    extraction_run_id = _seed_extraction_result(
        conn, project_id=project_id, scope_id=scope_id, counts={"selected": 0, "profiles": {}}
    )
    run_id = seed_run(conn, project_id)
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            extraction_run_id=extraction_run_id,
            grouping_provenance={},
            groups={},
            counts={},
            flags=flags,
            created_at=now(),
        )
    )
    return run_id


def _table_counts(conn: Connection, project_id: uuid.UUID) -> dict[str, int]:
    tables = [
        search_coverage_record,
        source_classification_result,
        source_appraisal_result,
        extraction_result,
        grouping_result,
        event_log,
    ]
    return {
        table.name: conn.execute(
            select(func.count()).select_from(table).where(table.c.project_id == project_id)
        ).scalar_one()
        for table in tables
    }


# --- Class 2: P1 coverage triggers -----------------------------------------


def test_p1_coverage_fires_on_inadequate_and_stop_condition(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_coverage_record(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
        adequacy_verdict="inadequate",
        stop_condition="error",
    )
    triggers = st.p1_coverage_triggers(conn, project_id=project_id, acquire_run_id=run_id)
    names = {t["trigger"] for t in triggers}
    assert names == {"coverage_inadequate", "coverage_stop_condition"}
    detail = next(t for t in triggers if t["trigger"] == "coverage_stop_condition")["detail"]
    assert detail == {"stop_condition": "error"}


def test_p1_coverage_not_fired_on_adequate_completed(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_coverage_record(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=run_id,
        adequacy_verdict="adequate",
        stop_condition="completed",
    )
    assert st.p1_coverage_triggers(conn, project_id=project_id, acquire_run_id=run_id) == []


def test_p1_coverage_missing_record_returns_empty(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    assert (
        st.p1_coverage_triggers(conn, project_id=project_id, acquire_run_id=uuid.uuid4()) == []
    )


# --- Class 3 (own reader): screened-relevant floor -------------------------


def test_screened_relevant_floor_fires_under_floor(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    for _ in range(st.P2_MIN_RELEVANT - 1):
        _, pss_id = seed_source(conn, project_id)
        seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    triggers = st.screened_relevant_floor_trigger(
        conn, project_id=project_id, evidence_scope_id=scope_id
    )
    assert triggers == [
        {
            "trigger": "screened_relevant_below_floor",
            "detail": {"relevant_count": st.P2_MIN_RELEVANT - 1, "floor": st.P2_MIN_RELEVANT},
        }
    ]


def test_screened_relevant_floor_not_fired_at_floor(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    for _ in range(st.P2_MIN_RELEVANT):
        _, pss_id = seed_source(conn, project_id)
        seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    assert (
        st.screened_relevant_floor_trigger(conn, project_id=project_id, evidence_scope_id=scope_id)
        == []
    )


# --- Classes 3/6: classification collapse ----------------------------------


def test_classification_collapse_fires_on_dominant_type(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    types = ["Observational Research Studies"] * 9 + ["Modelling & Simulation"] * 1
    _seed_classification_rows(conn, project_id=project_id, scope_id=scope_id, types=types)
    triggers = st.classification_collapse_trigger(
        conn, project_id=project_id, evidence_scope_id=scope_id
    )
    assert triggers == [
        {
            "trigger": "classification_type_mix_collapse",
            "detail": {
                "primary_evidence_type": "Observational Research Studies",
                "count": 9,
                "total": 10,
                "share": 0.9,
            },
        }
    ]


def test_classification_collapse_not_fired_at_dominant_boundary(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    types = ["Observational Research Studies"] * 4 + ["Modelling & Simulation"] * 1
    _seed_classification_rows(conn, project_id=project_id, scope_id=scope_id, types=types)
    assert (
        st.classification_collapse_trigger(conn, project_id=project_id, evidence_scope_id=scope_id)
        == []
    )


def test_classification_collapse_fires_on_unknown_share(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    types = (
        ["Unknown / Insufficient information"] * 4
        + ["Observational Research Studies"] * 3
        + ["Modelling & Simulation"] * 3
    )
    _seed_classification_rows(conn, project_id=project_id, scope_id=scope_id, types=types)
    triggers = st.classification_collapse_trigger(
        conn, project_id=project_id, evidence_scope_id=scope_id
    )
    assert triggers == [
        {
            "trigger": "classification_unknown_share",
            "detail": {"unknown_count": 4, "total": 10, "share": 0.4},
        }
    ]


def test_classification_collapse_not_fired_at_unknown_boundary(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    types = ["Unknown / Insufficient information"] * 3 + ["Observational Research Studies"] * 7
    _seed_classification_rows(conn, project_id=project_id, scope_id=scope_id, types=types)
    assert (
        st.classification_collapse_trigger(conn, project_id=project_id, evidence_scope_id=scope_id)
        == []
    )


def test_classification_collapse_no_rows_returns_empty(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    assert (
        st.classification_collapse_trigger(conn, project_id=project_id, evidence_scope_id=scope_id)
        == []
    )


# --- Classes 3/7: appraisal collapse ----------------------------------------


def test_appraisal_collapse_fires_over_threshold(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    scores = [1] * 8 + [5] * 2
    _seed_appraisal_rows(conn, project_id=project_id, scope_id=scope_id, scores=scores)
    triggers = st.appraisal_collapse_trigger(
        conn, project_id=project_id, evidence_scope_id=scope_id
    )
    assert triggers == [
        {
            "trigger": "appraisal_quality_collapse",
            "detail": {"weak_count": 8, "total": 10, "share": 0.8, "score_max": 2},
        }
    ]


def test_appraisal_collapse_not_fired_at_boundary(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    scores = [1] * 7 + [5] * 3
    _seed_appraisal_rows(conn, project_id=project_id, scope_id=scope_id, scores=scores)
    assert (
        st.appraisal_collapse_trigger(conn, project_id=project_id, evidence_scope_id=scope_id)
        == []
    )


# --- Class 4: grouping flags -------------------------------------------------


def test_grouping_flag_fires_on_flagged_facet(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    flags: dict[str, dict[str, Any]] = {
        "intervention": {
            "status": "failed",
            "failure_class": "timeout",
            "groups_rejected": False,
            "value_cap_exceeded": False,
        },
        "outcome": {
            "status": "succeeded",
            "failure_class": None,
            "groups_rejected": False,
            "value_cap_exceeded": False,
        },
    }
    group_run_id = _seed_grouping_result(
        conn, project_id=project_id, scope_id=scope_id, flags=flags
    )
    triggers = st.grouping_flag_triggers(conn, project_id=project_id, group_run_id=group_run_id)
    assert triggers == [
        {
            "trigger": "grouping_facet_flagged",
            "detail": {"facet": "intervention", **flags["intervention"]},
        }
    ]


def test_grouping_flag_not_fired_when_all_succeeded(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    flags = {
        "outcome": {
            "status": "succeeded",
            "failure_class": None,
            "groups_rejected": False,
            "value_cap_exceeded": False,
        },
    }
    group_run_id = _seed_grouping_result(
        conn, project_id=project_id, scope_id=scope_id, flags=flags
    )
    assert st.grouping_flag_triggers(conn, project_id=project_id, group_run_id=group_run_id) == []


# --- Class 5: screen quality-collapse ---------------------------------------


def _seed_component_completed(
    conn: Connection, *, project_id: uuid.UUID, run_id: uuid.UUID, counts: dict[str, Any]
) -> None:
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="component.completed",
        payload={"component": "screen", **counts},
    )


def test_screen_quality_collapse_fires_on_stage1_quorum_failure(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    _seed_component_completed(
        conn, project_id=project_id, run_id=run_id, counts={"screened": 10, "failed": 3}
    )
    triggers = st.screen_quality_collapse_trigger(conn, project_id=project_id, run_id=run_id)
    assert triggers == [
        {
            "trigger": "screen_quorum_failure_spike",
            "detail": {"failed": 3, "screened": 10, "share": 0.3},
        }
    ]


def test_screen_quality_collapse_not_fired_at_stage1_boundary(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    _seed_component_completed(
        conn, project_id=project_id, run_id=run_id, counts={"screened": 10, "failed": 2}
    )
    assert st.screen_quality_collapse_trigger(conn, project_id=project_id, run_id=run_id) == []


def test_screen_quality_collapse_fires_on_stage2_demote_spike(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    _seed_component_completed(
        conn,
        project_id=project_id,
        run_id=run_id,
        counts={"stage2_screened": 10, "failed": 0, "demoted": 6},
    )
    triggers = st.screen_quality_collapse_trigger(conn, project_id=project_id, run_id=run_id)
    assert triggers == [
        {
            "trigger": "screen_stage2_demote_spike",
            "detail": {"demoted": 6, "stage2_screened": 10, "share": 0.6},
        }
    ]


def test_screen_quality_collapse_not_fired_at_stage2_boundary(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    _seed_component_completed(
        conn,
        project_id=project_id,
        run_id=run_id,
        counts={"stage2_screened": 10, "failed": 2, "demoted": 5},
    )
    assert st.screen_quality_collapse_trigger(conn, project_id=project_id, run_id=run_id) == []


def test_screen_quality_collapse_no_event_returns_empty(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    assert (
        st.screen_quality_collapse_trigger(conn, project_id=project_id, run_id=uuid.uuid4()) == []
    )


# --- Class 8: extraction failure / vetting_failed spikes -------------------


def test_extraction_spike_fires_on_failure_and_vetting(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    counts = {
        "selected": 10,
        "profiles": {"iof_v1": {"failed": 3, "vetting_failed": 3}},
    }
    extract_run_id = _seed_extraction_result(
        conn, project_id=project_id, scope_id=scope_id, counts=counts
    )
    triggers = st.extraction_spike_triggers(
        conn, project_id=project_id, extract_run_id=extract_run_id
    )
    names = {t["trigger"] for t in triggers}
    assert names == {"extraction_failure_spike", "extraction_vetting_failed_spike"}


def test_extraction_spike_not_fired_at_boundary(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    counts = {
        "selected": 10,
        "profiles": {"iof_v1": {"failed": 2, "vetting_failed": 2}},
    }
    extract_run_id = _seed_extraction_result(
        conn, project_id=project_id, scope_id=scope_id, counts=counts
    )
    assert (
        st.extraction_spike_triggers(conn, project_id=project_id, extract_run_id=extract_run_id)
        == []
    )


def test_extraction_spike_no_row_returns_empty(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    assert (
        st.extraction_spike_triggers(conn, project_id=project_id, extract_run_id=uuid.uuid4())
        == []
    )


# --- Class 9: downstream-capability-reduced ---------------------------------


def test_downstream_capability_reduced_fires_on_skip_and_fail(conn: Connection) -> None:
    project_id, run_a = _seed_project_run(conn)
    run_b = seed_run(conn, project_id)
    events.append(
        conn,
        project_id=project_id,
        run_id=run_a,
        event_type="component.skipped",
        payload={"component": "characterise", "status": "skipped", "reason": "not_enabled"},
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=run_b,
        event_type="component.failed",
        payload={"component": "group", "error": "boom"},
    )
    triggers = st.downstream_capability_reduced_triggers(
        conn, project_id=project_id, run_ids=[run_a, run_b]
    )
    assert len(triggers) == 2
    assert {t["detail"]["component"] for t in triggers} == {"characterise", "group"}
    assert {t["detail"]["event_type"] for t in triggers} == {
        "component.skipped",
        "component.failed",
    }


def test_downstream_capability_reduced_not_fired_on_clean_completion(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="component.completed",
        payload={"component": "screen", "screened": 5},
    )
    assert (
        st.downstream_capability_reduced_triggers(conn, project_id=project_id, run_ids=[run_id])
        == []
    )


def test_downstream_capability_reduced_empty_run_ids(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    assert (
        st.downstream_capability_reduced_triggers(conn, project_id=project_id, run_ids=[]) == []
    )


# --- The aggregator ----------------------------------------------------------


def test_floor_triggers_after_acquire_fires_class2_and_class9(conn: Connection) -> None:
    project_id, acquire_run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_coverage_record(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        run_id=acquire_run_id,
        adequacy_verdict="inadequate",
        stop_condition="completed",
    )
    skip_run_id = seed_run(conn, project_id)
    events.append(
        conn,
        project_id=project_id,
        run_id=skip_run_id,
        event_type="component.skipped",
        payload={"component": "characterise", "status": "skipped", "reason": "not_enabled"},
    )
    triggers = st.floor_triggers(
        conn,
        project_id=project_id,
        boundary_component="after_acquire",
        evidence_scope_id=scope_id,
        run_ids={"acquire": acquire_run_id, "characterise": skip_run_id},
    )
    names = {t["trigger"] for t in triggers}
    assert names == {"coverage_inadequate", "downstream_capability_reduced"}


def test_floor_triggers_pre_select_fires_classes_3_6_7(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    screen_run_id = seed_run(conn, project_id)
    for _ in range(st.P2_MIN_RELEVANT - 1):
        _, pss_id = seed_source(conn, project_id)
        seed_screening_result(
            conn, project_id, screen_run_id, scope_id, pss_id, status="relevant"
        )
    types = ["Observational Research Studies"] * 9 + ["Modelling & Simulation"] * 1
    _seed_classification_rows(conn, project_id=project_id, scope_id=scope_id, types=types)
    scores = [1] * 8 + [5] * 2
    _seed_appraisal_rows(conn, project_id=project_id, scope_id=scope_id, scores=scores)
    events.append(
        conn,
        project_id=project_id,
        run_id=screen_run_id,
        event_type="component.skipped",
        payload={"component": "characterise", "status": "skipped", "reason": "not_enabled"},
    )

    triggers = st.floor_triggers(
        conn,
        project_id=project_id,
        boundary_component="pre_select",
        evidence_scope_id=scope_id,
        run_ids={"screen": screen_run_id},
    )
    names = {t["trigger"] for t in triggers}
    assert names == {
        "screened_relevant_below_floor",
        "classification_type_mix_collapse",
        "appraisal_quality_collapse",
        "downstream_capability_reduced",
    }


def test_floor_triggers_after_group_fires_class4_and_class9(conn: Connection) -> None:
    project_id, other_run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    flags = {
        "intervention": {
            "status": "failed",
            "failure_class": "timeout",
            "groups_rejected": False,
            "value_cap_exceeded": False,
        },
    }
    group_run_id = _seed_grouping_result(
        conn, project_id=project_id, scope_id=scope_id, flags=flags
    )
    events.append(
        conn,
        project_id=project_id,
        run_id=other_run_id,
        event_type="component.failed",
        payload={"component": "group", "error": "boom"},
    )
    triggers = st.floor_triggers(
        conn,
        project_id=project_id,
        boundary_component="after_group",
        evidence_scope_id=scope_id,
        run_ids={"group": group_run_id, "other": other_run_id},
    )
    names = {t["trigger"] for t in triggers}
    assert names == {"grouping_facet_flagged", "downstream_capability_reduced"}


@pytest.mark.parametrize(
    "boundary_component",
    ["after_screen", "after_classify", "after_appraise", "after_extract"],
)
def test_floor_triggers_every_boundary_includes_class9(
    conn: Connection, boundary_component: str
) -> None:
    project_id, tagged_run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    events.append(
        conn,
        project_id=project_id,
        run_id=tagged_run_id,
        event_type="component.skipped",
        payload={"component": "characterise", "status": "skipped", "reason": "not_enabled"},
    )
    run_ids = {
        "screen": tagged_run_id,
        "classify": tagged_run_id,
        "appraise": tagged_run_id,
        "extract": tagged_run_id,
    }
    triggers = st.floor_triggers(
        conn,
        project_id=project_id,
        boundary_component=boundary_component,  # type: ignore[arg-type]
        evidence_scope_id=scope_id,
        run_ids=run_ids,
    )
    assert "downstream_capability_reduced" in {t["trigger"] for t in triggers}


def test_floor_triggers_unknown_boundary_raises(conn: Connection) -> None:
    project_id, _run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    with pytest.raises(ValueError, match="unknown floor boundary_component"):
        st.floor_triggers(
            conn,
            project_id=project_id,
            boundary_component="not_a_boundary",  # type: ignore[arg-type]
            evidence_scope_id=scope_id,
            run_ids={},
        )


# --- Structural: readers never write; no component-internal access --------


def test_readers_never_write(conn: Connection) -> None:
    project_id, run_id = _seed_project_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_coverage_record(
        conn, project_id=project_id, scope_id=scope_id, run_id=run_id,
        adequacy_verdict="inadequate", stop_condition="error",
    )
    before = _table_counts(conn, project_id)
    st.floor_triggers(
        conn,
        project_id=project_id,
        boundary_component="after_acquire",
        evidence_scope_id=scope_id,
        run_ids={"acquire": run_id},
    )
    after = _table_counts(conn, project_id)
    assert before == after


def test_module_contains_no_write_statements() -> None:
    """Structural guard: the trigger-floor module is pure SELECTs (spec's own rule)."""
    source = inspect.getsource(st)
    for forbidden in (".insert(", ".update(", ".delete("):
        assert forbidden not in source
