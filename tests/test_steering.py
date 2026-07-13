"""Steering structural-core tests for task 017."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas import events
from policy_atlas.characterise import ScreenedSource
from policy_atlas.extract import KNOWN_PROFILE_IDS
from policy_atlas.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.runner import NullIO, run_plan
from policy_atlas.schema import (
    grouping_result,
    orchestration_plan,
    runs,
    selection_result,
    synthesis_result,
)
from policy_atlas.select import (
    SelectionCandidate,
    SelectionStratum,
    _parse_directive,
    select_documents,
)
from policy_atlas.steering import (
    Abort,
    Adjust,
    Continue,
    PausePoint,
    SteeringAdjustmentError,
    SteeringResponse,
    _validate_delta_round_trip,
    _validate_directive_delta,
    build_steer_point_options,
    pause_points,
    refuse_inexpressible,
    render_check_in,
    render_collation,
    steer_point_triggers,
)
from tests.helpers import now
from tests.test_runner import _base_plan, _cleanup, _runner_backends, _seed_project

IOF_PROFILE_ID, ICF_PROFILE_ID = KNOWN_PROFILE_IDS


class ScriptedIO:
    def __init__(self, responses: list[SteeringResponse] | None = None) -> None:
        self.responses = list(responses or [])
        self.check_ins: list[tuple[str, dict[str, Any]]] = []
        self.pauses: list[tuple[dict[str, Any], str]] = []

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        self.check_ins.append((component, payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        self.pauses.append((dict(point), render))
        if self.responses:
            return self.responses.pop(0)
        return Continue()


def _insert_plan_row(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan: OrchestrationPlan,
) -> uuid.UUID:
    plan_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            orchestration_plan.insert().values(
                plan_id=plan_id,
                project_id=project_id,
                evidence_scope_id=scope_id,
                version=1,
                status="approved",
                payload=plan.model_dump(mode="json"),
                created_at=now(),
                created_by="planner",
                approved_at=now(),
            )
        )
    return plan_id


def _cleanup_project(engine: Engine, project_id: uuid.UUID | None) -> None:
    if project_id is None:
        return
    with engine.begin() as conn:
        conn.execute(
            orchestration_plan.delete().where(orchestration_plan.c.project_id == project_id)
        )
    _cleanup(engine, project_id)


@pytest.mark.parametrize(
    ("delta", "match"),
    [
        ({"extraction": {"profiles": []}}, "must not be empty"),
        ({"extraction": {"profiles": ["not-a-profile"]}}, "not-a-profile"),
        (
            {"extraction": {"profiles": [IOF_PROFILE_ID, IOF_PROFILE_ID]}},
            "duplicate",
        ),
        ({"extraction": {"profiles": [ICF_PROFILE_ID]}}, "must include"),
    ],
)
def test_extract_directive_delta_validation_fails_closed(
    delta: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(SteeringAdjustmentError, match=match):
        _validate_directive_delta("extract", delta, backend_scope="both")


def test_pause_points_compile_pinned_for_all_modes() -> None:
    # deep depth: "select" must be present for the after-select pause points.
    plan = _base_plan(search_effort="standard", analysis_depth="deep")
    chain = compose(plan)

    assert pause_points("frequent", chain) == {
        PausePoint("after_component", component) for component in chain.components
    }
    assert pause_points("moderate", chain) == {
        PausePoint("after_component", "select"),
        PausePoint("before_component", "synthesise"),
    }
    assert pause_points("minimal", chain) == {PausePoint("after_component", "select")}
    assert pause_points("unattended", chain) == set()


def test_frequent_run_pauses_after_every_component_and_continue_matches_nullio(
    engine: Engine,
) -> None:
    pause_project_id: uuid.UUID | None = None
    null_project_id: uuid.UUID | None = None
    try:
        pause_project_id, pause_scope_id = _seed_project(engine)
        null_project_id, null_scope_id = _seed_project(engine)
        # deep depth: the default component set (select/extract/group) is
        # deep-only after the 018 regrade.
        plan = _base_plan(
            search_effort="standard",
            analysis_depth="deep",
            steering_mode="frequent",
        )
        io = ScriptedIO()

        pause_outcome = run_plan(
            engine,
            project_id=pause_project_id,
            evidence_scope_id=pause_scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=io,
        )
        null_outcome = run_plan(
            engine,
            project_id=null_project_id,
            evidence_scope_id=null_scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=NullIO(),
        )

        expected_components = compose(plan).components
        assert [(point["boundary"], point["component"]) for point, _ in io.pauses] == [
            ("after_component", component) for component in expected_components
        ]
        assert pause_outcome.status == null_outcome.status
        assert [step.component for step in pause_outcome.steps] == [
            step.component for step in null_outcome.steps
        ]
        assert [step.status for step in pause_outcome.steps] == [
            step.status for step in null_outcome.steps
        ]
    finally:
        _cleanup_project(engine, pause_project_id)
        _cleanup_project(engine, null_project_id)


def test_adjustment_writes_new_plan_version_and_changes_not_yet_run_group_directive(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="minimal")
        plan_id = _insert_plan_row(
            engine,
            project_id=project_id,
            scope_id=scope_id,
            plan=plan,
        )
        io = ScriptedIO(
            [Adjust(directive_deltas={"group": {"grouping": {"facet": "population"}}})]
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )

        assert outcome.status == "succeeded"
        with engine.connect() as conn:
            rows = conn.execute(
                select(
                    orchestration_plan.c.version,
                    orchestration_plan.c.status,
                    orchestration_plan.c.created_by,
                    orchestration_plan.c.payload,
                )
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
            facet = conn.execute(
                select(grouping_result.c.facet).where(grouping_result.c.project_id == project_id)
            ).scalar_one()

        assert [(row.version, row.status, row.created_by) for row in rows] == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]
        assert rows[1].payload["grouping_facet"] == "population"
        assert facet == "population"
    finally:
        _cleanup_project(engine, project_id)


def test_minimal_partial_delta_round_trips_despite_composer_injected_siblings(
    engine: Engine,
) -> None:
    # compose() always injects sibling keys the caller need not supply
    # (screen_full's {"stage": 2}); a criteria-only delta must still apply.
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(
            engine,
            project_id=project_id,
            scope_id=scope_id,
            plan=plan,
        )
        io = ScriptedIO(
            [
                Adjust(
                    directive_deltas={
                        "screen_full": {
                            "screening": {"criteria": ["Exclude opinion pieces."]}
                        }
                    }
                )
            ]
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )

        assert outcome.status == "succeeded"
        with engine.connect() as conn:
            rows = conn.execute(
                select(
                    orchestration_plan.c.version,
                    orchestration_plan.c.status,
                    orchestration_plan.c.payload,
                )
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(row.version, row.status) for row in rows] == [
            (1, "superseded"),
            (2, "approved"),
        ]
        assert rows[1].payload["screening_criteria"] == ["Exclude opinion pieces."]
    finally:
        _cleanup_project(engine, project_id)


def test_delta_round_trip_still_rejects_a_request_plan_fields_cannot_express() -> None:
    chain = compose(_base_plan())
    with pytest.raises(SteeringAdjustmentError):
        _validate_delta_round_trip(
            {"screen_full": {"screening": {"criteria": ["A rule the plan does not hold."]}}},
            amended_chain=chain,
        )


def test_adjustment_naming_already_run_component_reprompts_without_plan_write(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="minimal")
        plan_id = _insert_plan_row(
            engine,
            project_id=project_id,
            scope_id=scope_id,
            plan=plan,
        )
        # select is re-runnable at the deepening-selection steer point (task 7),
        # so the already-run rejection property is proven with characterise, an
        # already-run discretionary component the steer point never re-runs.
        io = ScriptedIO(
            [
                Adjust(directive_deltas={"characterise": {}}),
                Continue(),
            ]
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )

        assert outcome.status == "succeeded"
        assert len(io.pauses) == 2
        assert "already-run component 'characterise'" in io.pauses[1][1]
        with engine.connect() as conn:
            rows = conn.execute(
                select(orchestration_plan.c.version, orchestration_plan.c.status)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(row.version, row.status) for row in rows] == [(1, "approved")]
    finally:
        _cleanup_project(engine, project_id)


def test_abort_at_pause_stops_walk_marks_plan_abandoned_and_preserves_prior_runs(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(
            engine,
            project_id=project_id,
            scope_id=scope_id,
            plan=plan,
        )
        io = ScriptedIO([Continue(), Abort()])

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )

        assert outcome.status == "aborted"
        assert [step.component for step in outcome.steps] == ["acquire", "screen_abstract"]
        assert all(step.status == "succeeded" for step in outcome.steps)
        with engine.connect() as conn:
            plan_status = conn.execute(
                select(orchestration_plan.c.status).where(
                    orchestration_plan.c.plan_id == plan_id
                )
            ).scalar_one()
            run_statuses = conn.execute(
                select(runs.c.status)
                .where(runs.c.project_id == project_id)
                .order_by(runs.c.started_at)
            ).scalars().all()
            synth_count = conn.execute(
                select(func.count())
                .select_from(synthesis_result)
                .where(synthesis_result.c.project_id == project_id)
            ).scalar_one()

        assert plan_status == "abandoned"
        assert run_statuses == ["succeeded", "succeeded"]
        assert synth_count == 0
    finally:
        _cleanup_project(engine, project_id)


def test_unattended_auto_resolves_steer_point_without_pause_and_collates_flag(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            steering_mode="unattended",
            steer_point_defaults=[
                {"steer_point": "deepening_selection", "action": "proceed_flag"}
            ],
        )
        io = ScriptedIO()

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=io,
        )

        auto_events = [
            event for event in outcome.flagged_events if event["status"] == "auto_resolved"
        ]
        assert outcome.status == "succeeded"
        assert io.pauses == []
        assert auto_events == [
            {
                "component": "select",
                "status": "auto_resolved",
                "rule": "deepening_selection",
                "action": "proceed_flag",
            }
        ]
        assert "auto-resolutions" in outcome.collation_render
        assert "deepening_selection" in outcome.collation_render
    finally:
        _cleanup_project(engine, project_id)


def test_render_check_in_and_collation_are_deterministic_and_contain_key_facts() -> None:
    payload = {
        "component": "select",
        "status": "succeeded",
        "headline_counts": {"selected": 4, "base": 10},
        "wall_clock_s": 1.23456,
    }
    flagged_events = [
        {"component": "screen_abstract", "status": "failed", "reason": "boom"},
        {"component": "classify", "status": "retrying", "run_id": "run-1"},
        {"component": "extract", "status": "skipped", "reason": "blocked"},
        {
            "component": "select",
            "status": "auto_resolved",
            "rule": "deepening_selection",
            "action": "proceed_flag",
        },
    ]

    check_in = render_check_in(payload)
    collation = render_collation(flagged_events)

    assert check_in == render_check_in(payload)
    assert "select: succeeded" in check_in
    assert "wall_clock=1.235s" in check_in
    assert "base=10" in check_in
    assert "selected=4" in check_in
    assert collation == render_collation(flagged_events)
    assert "failures" in collation
    assert "retries" in collation
    assert "skips" in collation
    assert "auto-resolutions" in collation
    assert "deepening_selection" in collation


def _insert_selection_row(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    flags: dict[str, Any],
) -> uuid.UUID:
    run_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                project_id=project_id,
                status="succeeded",
                started_at=now(),
            )
        )
        conn.execute(
            selection_result.insert().values(
                selection_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                strategy="coverage_stratified_v1",
                budget=10,
                selection_provenance={},
                selected=[],
                excluded={},
                flags=flags,
                created_at=now(),
            )
        )
    return run_id


def _screened(
    *,
    quality: int | None,
    text_basis: str,
    screen_confidence: float | None,
    origin: str = "acquired",
    year: int | None = None,
) -> ScreenedSource:
    metadata: dict[str, Any] = {"title": "t", "abstract": "a"}
    if year is not None:
        metadata["year"] = year
    return ScreenedSource(
        pss_id=uuid.uuid4(),
        source_snapshot_id=uuid.uuid4(),
        full_text_snapshot_id=None,
        origin=origin,
        full_text_status="not_attempted",
        full_text_error=None,
        metadata=metadata,
        source_locator="x.pdf",
        text_basis=text_basis,
        screen_basis="title_abstract",
        screen_confidence=screen_confidence,
        screen_stage=1,
        primary_evidence_type="Impact evaluation",
        quality_score=quality,
        rubric_version="v1",
    )


def test_steer_point_triggers_map_each_flag_shape(engine: Engine) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        large_run = _insert_selection_row(
            engine, project_id=project_id, scope_id=scope_id,
            flags={"large_stratum_excluded": ["Housing supply"]},
        )
        nominated_run = _insert_selection_row(
            engine, project_id=project_id, scope_id=scope_id,
            flags={
                "priority_stratum_excluded": ["Health equity"],
                "must_include_conflict": ["doc-1"],
            },
        )
        thin_run = _insert_selection_row(
            engine, project_id=project_id, scope_id=scope_id,
            flags={"thin_base": {"sufficiently_confident": 2, "floor": 10}},
        )
        other_run = _insert_selection_row(
            engine, project_id=project_id, scope_id=scope_id,
            flags={"thin_full_text": {"share": 0.1, "floor": 0.5}},
        )
        empty_run = _insert_selection_row(
            engine, project_id=project_id, scope_id=scope_id, flags={},
        )

        with engine.connect() as conn:
            large = steer_point_triggers(
                conn, project_id=project_id, selection_run_id=large_run, plan=plan
            )
            nominated = steer_point_triggers(
                conn, project_id=project_id, selection_run_id=nominated_run, plan=plan
            )
            thin = steer_point_triggers(
                conn, project_id=project_id, selection_run_id=thin_run, plan=plan
            )
            other = steer_point_triggers(
                conn, project_id=project_id, selection_run_id=other_run, plan=plan
            )
            empty = steer_point_triggers(
                conn, project_id=project_id, selection_run_id=empty_run, plan=plan
            )
            missing = steer_point_triggers(
                conn, project_id=project_id, selection_run_id=uuid.uuid4(), plan=plan
            )

        assert large == [
            {"trigger": "excluded_large_stratum", "detail": ["Housing supply"]}
        ]
        assert nominated == [
            {
                "trigger": "excluded_user_nominated",
                "detail": {
                    "priority_stratum_excluded": ["Health equity"],
                    "must_include_conflict": ["doc-1"],
                },
            }
        ]
        assert thin == [
            {"trigger": "thin_base", "detail": {"sufficiently_confident": 2, "floor": 10}}
        ]
        # thin_full_text is a coverage caveat, not a deepening-selection trigger.
        assert other == []
        assert empty == []
        assert missing == []
    finally:
        _cleanup_project(engine, project_id)


def test_build_steer_point_options_speak_intents_with_pinned_grammar() -> None:
    # deep depth: the default component set (select/extract/group) is
    # deep-only after the 018 regrade; adjust_budget's pinned delta below is
    # deep's selection_budget (25).
    plan = _base_plan(search_effort="standard", analysis_depth="deep")
    options = build_steer_point_options(plan=plan, point="deepening_selection")
    by_id = {option["id"]: option for option in options}

    assert set(by_id) == {
        "deepen_clusters",
        "strongest_evidence",
        "most_relevant",
        "adjust_budget",
        "as_proposed",
    }
    assert by_id["deepen_clusters"]["delta"] == {
        "selection": {"priority_strata": [], "must_include_ids": []}
    }
    assert by_id["strongest_evidence"]["delta"] == {
        "selection": {"weight_emphasis": {"quality": 2.0}}
    }
    assert by_id["most_relevant"]["delta"] == {
        "selection": {"weight_emphasis": {"screen_confidence": 2.5}}
    }
    assert by_id["adjust_budget"]["delta"] == {"selection": {"budget": 25}}
    assert by_id["as_proposed"]["delta"] == {}
    # Every option speaks a user intent and carries an honest description.
    assert all(option["intent"] and option["description"] for option in options)
    # screen_confidence is named honestly as the relevance proxy, not true relevance.
    assert "proxy" in by_id["most_relevant"]["description"]


def test_emphasis_options_reorder_selection_through_the_real_select_path() -> None:
    options = {
        option["id"]: option
        for option in build_steer_point_options(plan=_base_plan(), point="deepening_selection")
    }
    year = datetime.now(UTC).year

    # Quality flip: doc A beats doc B on default weights; doc B (higher appraisal
    # quality) wins once the quality weight is doubled.
    doc_a = _screened(quality=2, text_basis="full_text", screen_confidence=0.9, year=year)
    doc_b = _screened(quality=5, text_basis="abstract_only", screen_confidence=0.6, year=None)
    quality_stratum = SelectionStratum(name="S", candidate_ids=(doc_a.pss_id, doc_b.pss_id))
    quality_candidates = [
        SelectionCandidate(source=doc_a, tags=()),
        SelectionCandidate(source=doc_b, tags=()),
    ]
    default_directive, _ = _parse_directive({"budget": 1})
    quality_directive, _ = _parse_directive(
        {**options["strongest_evidence"]["delta"]["selection"], "budget": 1}
    )

    default_quality = select_documents(
        quality_candidates, strata=[quality_stratum], strategy="coverage_stratified_v1",
        directive=default_directive, intent="q", ranking_backend=None,
    )
    emphasised_quality = select_documents(
        quality_candidates, strata=[quality_stratum], strategy="coverage_stratified_v1",
        directive=quality_directive, intent="q", ranking_backend=None,
    )
    assert [record["pss_id"] for record in default_quality.selected] == [str(doc_a.pss_id)]
    assert [record["pss_id"] for record in emphasised_quality.selected] == [str(doc_b.pss_id)]

    # Screen-confidence flip: doc C beats doc D by default; doc D (higher screen
    # confidence) wins once screen_confidence is emphasised x2.5.
    doc_c = _screened(quality=5, text_basis="full_text", screen_confidence=0.3, year=year)
    doc_d = _screened(quality=3, text_basis="full_text", screen_confidence=0.9, year=year)
    relevance_stratum = SelectionStratum(name="S", candidate_ids=(doc_c.pss_id, doc_d.pss_id))
    relevance_candidates = [
        SelectionCandidate(source=doc_c, tags=()),
        SelectionCandidate(source=doc_d, tags=()),
    ]
    relevance_directive, _ = _parse_directive(
        {**options["most_relevant"]["delta"]["selection"], "budget": 1}
    )

    default_relevance = select_documents(
        relevance_candidates, strata=[relevance_stratum], strategy="coverage_stratified_v1",
        directive=default_directive, intent="q", ranking_backend=None,
    )
    emphasised_relevance = select_documents(
        relevance_candidates, strata=[relevance_stratum], strategy="coverage_stratified_v1",
        directive=relevance_directive, intent="q", ranking_backend=None,
    )
    assert [record["pss_id"] for record in default_relevance.selected] == [str(doc_c.pss_id)]
    assert [record["pss_id"] for record in emphasised_relevance.selected] == [str(doc_d.pss_id)]


def test_moderate_steer_point_reselect_reruns_select_and_threads_new_run_id(
    engine: Engine,
) -> None:
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate mode, full (deep) chain
        plan_id = _insert_plan_row(
            engine, project_id=project_id, scope_id=scope_id, plan=plan
        )
        io = ScriptedIO(
            [
                Adjust(
                    directive_deltas={
                        "select": {"selection": {"weight_emphasis": {"quality": 2.0}}}
                    }
                )
            ]
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )

        assert outcome.status == "succeeded"

        with engine.connect() as conn:
            plan_rows = conn.execute(
                select(
                    orchestration_plan.c.version,
                    orchestration_plan.c.status,
                    orchestration_plan.c.created_by,
                )
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
            compiled = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == "plan.compiled"
            ]

        # A new user-attributed plan version row records the steering event.
        assert [(row.version, row.status, row.created_by) for row in plan_rows] == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]

        # Two select runs: the original plus the cheap re-run.
        select_run_ids = [
            entry["run_id"] for entry in compiled if entry["payload"]["component"] == "select"
        ]
        assert len(select_run_ids) == 2

        # The re-run select runs under the amended plan version.
        rerun_select = next(
            entry for entry in compiled if entry["run_id"] == select_run_ids[1]
        )
        assert rerun_select["payload"]["plan_version"] == 2

        # Extract threads the NEW selection run id, not the original.
        extract_payload = next(
            entry["payload"] for entry in compiled if entry["payload"]["component"] == "extract"
        )
        assert extract_payload["selection_run_id"] == str(select_run_ids[1])
        assert extract_payload["selection_run_id"] != str(select_run_ids[0])

        # The steer point fired exactly once (no re-fire after the re-run).
        steer_pauses = [point for point, _ in io.pauses if point.get("kind") == "steer_point"]
        assert len(steer_pauses) == 1

        # The walk completed through synthesise.
        assert [step.component for step in outcome.steps][-1] == "synthesise"
        select_steps = [step for step in outcome.steps if step.component == "select"]
        assert len(select_steps) == 2
        assert all(step.status == "succeeded" for step in select_steps)
    finally:
        _cleanup_project(engine, project_id)


def test_refuse_inexpressible_returns_honest_not_yet_message() -> None:
    message = refuse_inexpressible("rank by author reputation")
    assert "not yet expressible" in message
    assert "rank by author reputation" in message
    assert "seam" in message
