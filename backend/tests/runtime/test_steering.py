"""Steering structural-core tests for task 017."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import (
    characterisation_result,
    evidence_scope,
    grouping_result,
    orchestration_plan,
    runs,
    selection_result,
    source_appraisal_result,
    synthesis_result,
)
from policy_atlas.evidence_base.assess.appraise import (
    DEFAULT_RUBRIC_VERSION,
    _derive_rubric_version,
)
from policy_atlas.evidence_base.corpus.characterise import CharacteriseFailure, ScreenedSource
from policy_atlas.evidence_base.corpus.select import (
    SelectionCandidate,
    SelectionStratum,
    _parse_directive,
    select_documents,
)
from policy_atlas.evidence_base.extract.extract import KNOWN_PROFILE_IDS
from policy_atlas.evidence_base.sourcing.search_loop import (
    SEARCH_TARGET_MAX,
    SEARCH_TARGET_MIN,
)
from policy_atlas.runtime import harness, steering_events
from policy_atlas.runtime.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.runtime.runner import (
    NullIO,
    _apply_replacement_rerun,
    _reference_kwargs,
    _run_component_rerun,
    _skip_reason,
    _SteeringState,
    run_plan,
)
from policy_atlas.runtime.steering import (
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
from tests.runtime.test_runner import _base_plan, _cleanup, _runner_backends, _seed_project

IOF_PROFILE_ID, ICF_PROFILE_ID = KNOWN_PROFILE_IDS


class ScriptedIO:
    def __init__(
        self,
        responses: list[SteeringResponse] | None = None,
        by_steer_point: dict[str, list[SteeringResponse]] | None = None,
    ) -> None:
        self.responses = list(responses or [])
        # Steer-point-keyed responses (popped in order) — robust to which other
        # lattice points fire (P1 fires on the thin stub seed; positional
        # scripting would drift). Falls through to ``responses`` then Continue.
        self.by_steer_point = {key: list(value) for key, value in (by_steer_point or {}).items()}
        self.check_ins: list[tuple[str, dict[str, Any]]] = []
        self.pauses: list[tuple[dict[str, Any], str]] = []

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        self.check_ins.append((component, payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        self.pauses.append((dict(point), render))
        steer_point = point.get("steer_point")
        queued = self.by_steer_point.get(steer_point) if steer_point is not None else None
        if queued:
            return queued.pop(0)
        if self.responses:
            return self.responses.pop(0)
        return Continue()


class _InjectAtIO:
    """Return one scripted response at the first after_component pause of a named
    component, then Continue everywhere (for injecting a pending-component
    adjustment before a downstream component runs)."""

    def __init__(self, *, target_component: str, response: SteeringResponse) -> None:
        self.target_component = target_component
        self.response = response
        self.fired = False
        self.check_ins: list[tuple[str, dict[str, Any]]] = []
        self.pauses: list[tuple[dict[str, Any], str]] = []

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        self.check_ins.append((component, payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        self.pauses.append((dict(point), render))
        if (
            not self.fired
            and point.get("component") == self.target_component
            and point.get("boundary") == "after_component"
        ):
            self.fired = True
            return self.response
        return Continue()


def _compiled_by_component(
    engine: Engine, project_id: uuid.UUID
) -> dict[str, list[dict[str, Any]]]:
    by_component: dict[str, list[dict[str, Any]]] = {}
    with engine.connect() as conn:
        for entry in events.read(conn, project_id):
            if entry["event_type"] == "plan.compiled":
                by_component.setdefault(entry["payload"]["component"], []).append(entry["payload"])
    return by_component


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


@pytest.mark.parametrize(
    ("delta", "match"),
    [
        ({"appraisal": {"rubric": {}}}, "non-empty"),
        ({"appraisal": {"rubric": {"Not A Real Type": 3}}}, "unknown evidence type"),
        (
            {"appraisal": {"rubric": {"Expert Opinion and Commentary": 0}}},
            "between 1 and 5",
        ),
        ({"screening": {}}, "must contain exactly"),  # wrong key for "appraise"
    ],
)
def test_appraise_directive_delta_validation_fails_closed(
    delta: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(SteeringAdjustmentError, match=match):
        _validate_directive_delta("appraise", delta, backend_scope="both")


def test_appraise_directive_delta_validates_and_is_exempt_from_plan_round_trip() -> None:
    """D1: the appraisal rubric override is a commit-layer directive with no
    OrchestrationPlan field (apply_reselect precedent). It validates at the
    parser but is honestly exempted from the generic round-trip check —
    unlike every other component, it is never expected to appear in the
    recomposed chain's directive_delta."""
    delta = {"appraisal": {"rubric": {"Expert Opinion and Commentary": 5}}}
    _validate_directive_delta("appraise", delta, backend_scope="both")  # does not raise

    chain = compose(_base_plan())
    _validate_delta_round_trip({"appraise": delta}, amended_chain=chain)  # does not raise
    appraise_step = next(step for step in chain.steps if step.component == "appraise")
    assert appraise_step.directive_delta == {}  # confirmed: no plan field carries it


# --- D3 extraction.refresh: _validate_directive_delta flows through the parser ---


@pytest.mark.parametrize(
    "delta",
    [
        {"extraction": {"refresh": "abstract_only"}},
        {"extraction": {"refresh": "failed"}},
        {"extraction": {"refresh": "all"}},
        {"extraction": {"profiles": [IOF_PROFILE_ID, ICF_PROFILE_ID], "refresh": "all"}},
    ],
)
def test_extract_refresh_directive_delta_validates(delta: dict[str, Any]) -> None:
    _validate_directive_delta("extract", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    ("delta", "match"),
    [
        ({"extraction": {"refresh": "everything"}}, "refresh"),
        ({"extraction": {"refresh": 1}}, "refresh"),
        ({"extraction": {"bogus": True}}, "unknown keys"),
    ],
)
def test_extract_refresh_directive_delta_rejects_bogus_value(
    delta: dict[str, Any], match: str
) -> None:
    with pytest.raises(SteeringAdjustmentError, match=match):
        _validate_directive_delta("extract", delta, backend_scope="both")


def test_extract_refresh_is_exempt_from_plan_round_trip_but_profiles_still_are() -> None:
    """D3: refresh has no OrchestrationPlan field (commit-layer, appraisal-rubric
    precedent) and is silently exempted from the round-trip comparison; the
    sibling profiles key still round-trips normally."""
    # _base_plan()'s default "deep" depth compiles extract_profiles to both
    # IOF and ICF (ANALYSIS_DEPTH_TABLE["deep"]) — matched here so the
    # profiles half of the round-trip check genuinely passes.
    delta = {
        "extraction": {"profiles": [IOF_PROFILE_ID, ICF_PROFILE_ID], "refresh": "all"}
    }
    _validate_directive_delta("extract", delta, backend_scope="both")  # does not raise

    chain = compose(_base_plan())
    # Does not raise: profiles round-trips through extract_profiles; refresh is
    # discarded rather than compared.
    _validate_delta_round_trip({"extract": delta}, amended_chain=chain)


# --- D5 search.target: _validate_directive_delta flows through the parser ---


@pytest.mark.parametrize(
    "delta",
    [
        {"search": {"target": 5}},
        {"search": {"target": 60}},
        {"search": {"depth": "deep", "target": 30}},
    ],
)
def test_acquire_target_directive_delta_validates(delta: dict[str, Any]) -> None:
    _validate_directive_delta("acquire", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    "delta",
    [
        {"search": {"target": SEARCH_TARGET_MIN - 1}},
        {"search": {"target": SEARCH_TARGET_MAX + 1}},
        {"search": {"target": "30"}},
    ],
)
def test_acquire_target_directive_delta_rejects_out_of_range(delta: dict[str, Any]) -> None:
    with pytest.raises(SteeringAdjustmentError):
        _validate_directive_delta("acquire", delta, backend_scope="both")


# --- D6/D7 selection.strata_scope / selection.exclude_ids ---


@pytest.mark.parametrize(
    "delta",
    [
        {"selection": {"strata_scope": {"only": ["A"]}}},
        {"selection": {"strata_scope": {"exclude": ["A", "B"]}}},
        {"selection": {"exclude_ids": [str(uuid.uuid4())]}},
        {
            "selection": {
                "strata_scope": {"only": ["A"]},
                "exclude_ids": [str(uuid.uuid4())],
            }
        },
    ],
)
def test_select_strata_scope_and_exclude_ids_directive_delta_validates(
    delta: dict[str, Any]
) -> None:
    _validate_directive_delta("select", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    "delta",
    [
        {"selection": {"strata_scope": {"only": ["A"], "exclude": ["B"]}}},
        {"selection": {"strata_scope": {"only": []}}},
        {"selection": {"exclude_ids": ["not-a-uuid"]}},
    ],
)
def test_select_strata_scope_and_exclude_ids_directive_delta_rejects_bogus(
    delta: dict[str, Any]
) -> None:
    with pytest.raises(SteeringAdjustmentError):
        _validate_directive_delta("select", delta, backend_scope="both")


def test_select_exclude_ids_conflicting_with_must_include_ids_rejected() -> None:
    """D7: the same id in both exclude_ids and must_include_ids fails closed."""
    shared_id = str(uuid.uuid4())
    delta = {
        "selection": {"must_include_ids": [shared_id], "exclude_ids": [shared_id]}
    }
    with pytest.raises(SteeringAdjustmentError, match="conflicts"):
        _validate_directive_delta("select", delta, backend_scope="both")


# --- D8 grouping.granularity ---


@pytest.mark.parametrize(
    "delta",
    [
        {"grouping": {"granularity": "coarser"}},
        {"grouping": {"granularity": "standard"}},
        {"grouping": {"granularity": "finer"}},
        {"grouping": {"facet": "outcome", "granularity": "finer"}},
    ],
)
def test_group_granularity_directive_delta_validates(delta: dict[str, Any]) -> None:
    _validate_directive_delta("group", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    "delta",
    [
        {"grouping": {"granularity": "bogus"}},
        {"grouping": {"granularity": 1}},
    ],
)
def test_group_granularity_directive_delta_rejects_bogus_value(
    delta: dict[str, Any]
) -> None:
    with pytest.raises(SteeringAdjustmentError):
        _validate_directive_delta("group", delta, backend_scope="both")


# --- B1 search.guidance: _validate_directive_delta flows through the parser ---


@pytest.mark.parametrize(
    "delta",
    [
        {"search": {"guidance": ["prioritise UK policy evaluations"]}},
        {
            "search": {
                "depth": "deep",
                "target": 30,
                "guidance": ["prioritise UK policy evaluations", "avoid clinical literature"],
            }
        },
    ],
)
def test_acquire_guidance_directive_delta_validates(delta: dict[str, Any]) -> None:
    _validate_directive_delta("acquire", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    "delta",
    [
        {"search": {"guidance": []}},
        {"search": {"guidance": ["a", "b", "c", "d", "e", "f"]}},
        {"search": {"guidance": [""]}},
        {"search": {"guidance": [123]}},
    ],
)
def test_acquire_guidance_directive_delta_rejects_malformed(delta: dict[str, Any]) -> None:
    with pytest.raises(SteeringAdjustmentError):
        _validate_directive_delta("acquire", delta, backend_scope="both")


# --- B3 grouping.guidance: _validate_directive_delta flows through the parser ---


@pytest.mark.parametrize(
    "delta",
    [
        {"grouping": {"guidance": ["organise by policy instrument, not sector"]}},
        {"grouping": {"facet": "outcome", "granularity": "finer", "guidance": ["a"]}},
    ],
)
def test_group_guidance_directive_delta_validates(delta: dict[str, Any]) -> None:
    _validate_directive_delta("group", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    "delta",
    [
        {"grouping": {"guidance": []}},
        {"grouping": {"guidance": ["a", "b", "c", "d", "e", "f"]}},
        {"grouping": {"guidance": [123]}},
    ],
)
def test_group_guidance_directive_delta_rejects_malformed(delta: dict[str, Any]) -> None:
    with pytest.raises(SteeringAdjustmentError):
        _validate_directive_delta("group", delta, backend_scope="both")


# --- B5/D9 characterise.themes / characterise.guidance ---


@pytest.mark.parametrize(
    "delta",
    [
        {"characterise": {"themes": "fewer"}},
        {"characterise": {"themes": "standard"}},
        {"characterise": {"themes": "more"}},
        {"characterise": {"guidance": ["organise around policy instruments"]}},
        {"characterise": {"themes": "fewer", "guidance": ["organise around policy instruments"]}},
    ],
)
def test_characterise_directive_delta_validates(delta: dict[str, Any]) -> None:
    _validate_directive_delta("characterise", delta, backend_scope="both")  # does not raise


@pytest.mark.parametrize(
    ("delta", "match"),
    [
        ({"characterise": {"themes": "bogus"}}, "themes"),
        ({"characterise": {"guidance": []}}, "guidance"),
        ({"characterise": {"unknown_key": True}}, "unknown keys"),
        ({"screening": {}}, "must contain exactly"),  # wrong key for "characterise"
    ],
)
def test_characterise_directive_delta_validation_fails_closed(
    delta: dict[str, Any],
    match: str,
) -> None:
    with pytest.raises(SteeringAdjustmentError, match=match):
        _validate_directive_delta("characterise", delta, backend_scope="both")


def test_characterise_directive_delta_validates_and_is_exempt_from_plan_round_trip() -> None:
    """B5/D9: the characterise themes/guidance directive is a commit-layer
    directive with no OrchestrationPlan field (the appraise/D1 precedent). It
    validates at the parser but is honestly exempted from the generic
    round-trip check — it is never expected to appear in the recomposed
    chain's directive_delta."""
    delta = {
        "characterise": {
            "themes": "fewer",
            "guidance": ["organise around policy instruments"],
        }
    }
    _validate_directive_delta("characterise", delta, backend_scope="both")  # does not raise

    chain = compose(_base_plan())
    _validate_delta_round_trip({"characterise": delta}, amended_chain=chain)  # does not raise
    characterise_step = next(step for step in chain.steps if step.component == "characterise")
    assert characterise_step.directive_delta == {}  # confirmed: no plan field carries it


# --- Every directive branch of _validate_directive_delta must refuse, never crash ---


@pytest.mark.parametrize(
    ("component", "delta"),
    [
        ("acquire", {"search": "boom"}),
        ("screen_abstract", {"screening": "boom"}),
        ("screen_full", {"screening": "boom"}),
        ("select", {"selection": "boom"}),
        ("extract", {"extraction": "boom"}),
        ("group", {"grouping": "boom"}),
        ("appraise", {"appraisal": "boom"}),
        ("characterise", {"characterise": "boom"}),
        ("synthesise", {"synthesis": "boom"}),
    ],
)
def test_every_directive_branch_maps_errors_to_refusal(
    component: str, delta: dict[str, Any]
) -> None:
    """Every component branch wraps its parser's type error as a refusal.

    A string where each branch's parser requires a mapping used to reach an
    unwrapped exception in at least one branch (the screen_abstract/
    screen_full live-check finding, 2026-07-21) — the fix was to wrap every
    branch's parser call, not just that one. This pins the fix as complete
    across every branch _validate_directive_delta actually dispatches on,
    not only the ones the fix touched.
    """
    with pytest.raises(SteeringAdjustmentError):
        _validate_directive_delta(component, delta, backend_scope="both")


def test_pause_points_compile_pinned_for_all_modes() -> None:
    # deep depth: "select" must be present for the after-select pause points.
    plan = _base_plan(search_effort="standard", analysis_depth="deep")
    chain = compose(plan)

    # Frequent (task 024 lattice): pause after every component PLUS the two
    # before-boundary lattice points P2 (before select) and P4 (before synthesise).
    assert pause_points("frequent", chain) == {
        PausePoint("after_component", component) for component in chain.components
    } | {
        PausePoint("before_component", "select"),
        PausePoint("before_component", "synthesise"),
    }
    # Moderate always-pauses at P2 + P3 + P4 (P1 is fired-only, so not static).
    assert pause_points("moderate", chain) == {
        PausePoint("before_component", "select"),
        PausePoint("after_component", "select"),
        PausePoint("before_component", "synthesise"),
    }
    # Minimal: all four lattice points are fired-only (named behaviour change —
    # the pre-024 minimal always-paused at deepening_selection); the static set
    # is empty and the runner evaluates each point's floor triggers at the
    # boundary.
    assert pause_points("minimal", chain) == set()
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

        # Frequent pauses after every component, with P2 (before select) inserted
        # right before select runs and P4 (before synthesise) right before
        # synthesise runs (the two before-boundary lattice points).
        expected_components = compose(plan).components
        expected_sequence: list[tuple[str, str]] = []
        for component in expected_components:
            if component == "select":
                expected_sequence.append(("before_component", "select"))
            if component == "synthesise":
                expected_sequence.append(("before_component", "synthesise"))
            expected_sequence.append(("after_component", component))
        assert [
            (point["boundary"], point["component"]) for point, _ in io.pauses
        ] == expected_sequence
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
            [Adjust(directive_deltas={"group": {"grouping": {"facets": ["population"]}}})]
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
            facets = conn.execute(
                select(grouping_result.c.grouping_provenance).where(
                    grouping_result.c.project_id == project_id
                )
            ).scalar_one()["facets"]

        assert [(row.version, row.status, row.created_by) for row in rows] == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]
        assert rows[1].payload["grouping_facets"] == ["population"]
        assert facets == ["population"]
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


def test_appraise_adjustment_accepted_end_to_end_but_absent_from_plan_payload(
    engine: Engine,
) -> None:
    """D1 end-to-end: an appraisal-rubric Adjust for the not-yet-run
    ``appraise`` component is accepted by the full ``apply_adjustment`` path
    (parser validates, round-trip is exempted) and commits a new
    user-attributed plan version — but, being a commit-layer directive with
    no OrchestrationPlan field, the amended payload carries no trace of it.
    This is the flagged, deliberately-landed behaviour for D1 (task 024
    Family D), not a bug: a full commit-layer apply path (an appraise
    analogue of ``apply_reselect``) is out of scope here."""
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
        # "frequent" pauses after every component; the Adjust fires at the
        # very first pause (after acquire) — appraise has not run yet either
        # way, so any not-yet-run pause validates it (group-test precedent).
        io = ScriptedIO(
            [
                Adjust(
                    directive_deltas={
                        "appraise": {
                            "appraisal": {"rubric": {"Expert Opinion and Commentary": 5}}
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
                    orchestration_plan.c.created_by,
                    orchestration_plan.c.payload,
                )
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert [(row.version, row.status, row.created_by) for row in rows] == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]
        # No OrchestrationPlan field carries the appraisal directive.
        assert "appraisal" not in rows[1].payload
        assert "rubric" not in rows[1].payload
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
        # select/characterise/group are each re-runnable at their own steer point
        # (task 7 / 15b — characterise re-runs at P2), so the already-run rejection
        # property is proven with appraise, an already-run component no steer point
        # ever re-runs. It is delivered at P2 (evidence_base_coverage, after
        # appraise has run) so the rejection is "already-run"; the reprompt then
        # Continues.
        io = ScriptedIO(
            by_steer_point={
                "evidence_base_coverage": [Adjust(directive_deltas={"appraise": {}})]
            }
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
        # Under the lattice an already-run adjustment is rejected at whichever
        # lattice pause first fires (P2 fires on the thin seed); the rejection
        # render surfaces and no plan-version row is written.
        assert any(
            "already-run component 'appraise'" in render for _, render in io.pauses
        )
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
        # Generalised path (Task 12): every lattice boundary auto-resolves in
        # Unattended. P3 applies the pinned deepening_selection rule; P2/P4 fall
        # to the discretion floor (unconfigured_default, no pinned rule).
        rules = {event["rule"] for event in auto_events}
        assert "deepening_selection" in rules
        assert "unconfigured_default" in rules
        p3 = [event for event in auto_events if event["steer_point"] == "deepening_selection"]
        assert p3 == [
            {
                "component": "select",
                "status": "auto_resolved",
                "steer_point": "deepening_selection",
                "rule": "deepening_selection",
                "action": "proceed_flag",
            }
        ]
        # Loudest-flag collation ordering: unconfigured_default is reviewed FIRST.
        collation = outcome.collation_render
        assert "auto-resolutions" in collation
        assert collation.index("unconfigured_default") < collation.index(
            "rule=deepening_selection"
        )
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
        "add_extraction_profile",
        "refresh_extraction",
        "scope_strata",
        "exclude_docs",
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
        # Reselect lands at the P3 deepening_selection pause; every other lattice
        # pause (P1 fires on the thin stub seed, P2, P4) Continues.
        io = ScriptedIO(
            by_steer_point={
                "deepening_selection": [
                    Adjust(
                        directive_deltas={
                            "select": {"selection": {"weight_emphasis": {"quality": 2.0}}}
                        }
                    )
                ]
            }
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

        # The P3 deepening_selection steer point fired exactly once — not
        # re-entered after the reselect (one adjustment cycle per boundary).
        steer_points = [
            point["steer_point"] for point, _ in io.pauses if point.get("kind") == "steer_point"
        ]
        assert steer_points.count("deepening_selection") == 1

        # The walk completed through synthesise.
        assert [step.component for step in outcome.steps][-1] == "synthesise"
        select_steps = [step for step in outcome.steps if step.component == "select"]
        assert len(select_steps) == 2
        assert all(step.status == "succeeded" for step in select_steps)
    finally:
        _cleanup_project(engine, project_id)


def test_p2_recharacterise_option_reruns_and_rethreads_reference(engine: Engine) -> None:
    """A canonical P2 (before select) re-characterise option Adjust re-runs
    characterise (replacement) — both characterisation rows persist and select
    references the NEW run (Task 15b)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P2 (evidence_base_coverage) pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO(
            by_steer_point={
                "evidence_base_coverage": [
                    Adjust(
                        directive_deltas={
                            "characterise": {
                                "characterise": {
                                    "themes": "standard",
                                    "guidance": ["focus on rural areas"],
                                }
                            }
                        }
                    )
                ]
            }
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
            compiled = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == "plan.compiled"
            ]
            char_row_runs = set(
                conn.execute(
                    select(characterisation_result.c.run_id).where(
                        characterisation_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        char_runs = [
            entry["run_id"] for entry in compiled if entry["payload"]["component"] == "characterise"
        ]
        # Two characterise runs; both rows persist (replacement never deletes).
        assert len(char_runs) == 2
        assert char_row_runs == set(char_runs)
        # select references the RE-RUN characterise, not the original.
        select_payload = next(
            entry["payload"] for entry in compiled if entry["payload"]["component"] == "select"
        )
        assert select_payload["characterisation_run_id"] == str(char_runs[1])
        assert select_payload["characterisation_run_id"] != str(char_runs[0])
        # The decision stamps rerun_mode=replacement.
        with engine.connect() as conn:
            replacements = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_DECISION
                and entry["payload"].get("rerun_mode") == "replacement"
                and entry["payload"].get("boundary") == "before_component"
            ]
        assert len(replacements) == 1
    finally:
        _cleanup_project(engine, project_id)


def test_p4_regroup_option_reruns_and_rethreads_reference(engine: Engine) -> None:
    """A canonical P4 (before synthesise) re-group option Adjust re-runs group
    (replacement) — both grouping rows persist and synthesise references the NEW
    group run (Task 15b)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P4 (synthesis_shape) pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO(
            by_steer_point={
                "synthesis_shape": [
                    Adjust(directive_deltas={"group": {"grouping": {"granularity": "coarser"}}})
                ]
            }
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
            compiled = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == "plan.compiled"
            ]
            group_row_runs = set(
                conn.execute(
                    select(grouping_result.c.run_id).where(
                        grouping_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        group_runs = [
            entry["run_id"] for entry in compiled if entry["payload"]["component"] == "group"
        ]
        assert len(group_runs) == 2
        assert group_row_runs == set(group_runs)
        # synthesise references the RE-RUN group, not the original.
        synth_payload = next(
            entry["payload"] for entry in compiled if entry["payload"]["component"] == "synthesise"
        )
        assert synth_payload["grouping_run_id"] == str(group_runs[1])
        assert synth_payload["grouping_run_id"] != str(group_runs[0])
        with engine.connect() as conn:
            replacements = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_DECISION
                and entry["payload"].get("rerun_mode") == "replacement"
                and entry["payload"].get("boundary") == "before_component"
            ]
        assert len(replacements) == 1
    finally:
        _cleanup_project(engine, project_id)


# --- Pending commit-layer overlays (task 024, 15c) -------------------------


def test_pending_overlay_appraise_rubric_reaches_run(engine: Engine) -> None:
    """A pending appraise rubric adjustment (commit-layer, no plan field) is
    stored as an overlay and reaches the appraise run: every appraisal row carries
    the derived override rubric_version, and the plan.compiled event echoes it."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        rubric = {"Expert Opinion and Commentary": 5}
        # Injected at the after-classify pause — appraise has not yet run.
        io = _InjectAtIO(
            target_component="classify",
            response=Adjust(directive_deltas={"appraise": {"appraisal": {"rubric": rubric}}}),
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

        expected_version = _derive_rubric_version(rubric)
        assert expected_version != DEFAULT_RUBRIC_VERSION
        with engine.connect() as conn:
            versions = set(
                conn.execute(
                    select(source_appraisal_result.c.rubric_version).where(
                        source_appraisal_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        # The override reached appraise: every row carries the derived version.
        assert versions == {expected_version}

        # Provenance: the appraise plan.compiled event echoes the executed overlay.
        appraise_payloads = _compiled_by_component(engine, project_id)["appraise"]
        assert appraise_payloads[0]["pending_overlay"] == {"appraisal": {"rubric": rubric}}
    finally:
        _cleanup_project(engine, project_id)


def test_pending_overlay_characterise_echoes_and_does_not_leak(engine: Engine) -> None:
    """A pending characterise themes/guidance overlay echoes on characterise's
    plan.compiled event and does NOT leak onto other components' events."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        char_delta = {"characterise": {"themes": "standard", "guidance": ["focus on rural areas"]}}
        io = _InjectAtIO(
            target_component="classify",
            response=Adjust(directive_deltas={"characterise": char_delta}),
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

        by_component = _compiled_by_component(engine, project_id)
        # The overlay echoes on characterise only.
        assert by_component["characterise"][0]["pending_overlay"] == char_delta
        # It does not leak onto appraise / select / group / synthesise events.
        for other in ("appraise", "select", "group", "synthesise"):
            assert all("pending_overlay" not in payload for payload in by_component[other])
    finally:
        _cleanup_project(engine, project_id)


def test_plan_mappable_screening_criteria_takes_plan_path_no_overlay(engine: Engine) -> None:
    """Guard: a plan-mappable delta (screening criteria) takes the EXISTING plan
    path — it maps to the plan payload and is NOT overlaid (no double-apply)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        new_criteria = ["Include only randomised controlled trials"]
        # Injected at the after-acquire pause — screen_abstract has not yet run.
        io = _InjectAtIO(
            target_component="acquire",
            response=Adjust(
                directive_deltas={"screen_abstract": {"screening": {"criteria": new_criteria}}}
            ),
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

        # The criteria took the plan path: a new version carries them in its payload.
        with engine.connect() as conn:
            rows = conn.execute(
                select(orchestration_plan.c.version, orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version)
            ).all()
        assert rows[-1].payload["screening_criteria"] == new_criteria
        # No overlay was minted for a plan-mappable component (no double-apply).
        by_component = _compiled_by_component(engine, project_id)
        for payloads in by_component.values():
            assert all("pending_overlay" not in payload for payload in payloads)
    finally:
        _cleanup_project(engine, project_id)


# --- Mixed-grammar delta splitting (task 024, 15d) -------------------------


def _scope_context(engine: Engine, scope_id: uuid.UUID) -> dict[str, Any]:
    with engine.connect() as conn:
        context: dict[str, Any] = conn.execute(
            select(evidence_scope.c.context).where(
                evidence_scope.c.evidence_scope_id == scope_id
            )
        ).scalar_one()
    return context


def test_pending_extract_split_maps_profiles_and_overlays_refresh_and_emphasis(
    engine: Engine,
) -> None:
    """A pending-extract Adjust carrying profiles + refresh + relevance_emphasis
    SPLITS: profiles map to the plan payload; refresh (D3) and relevance_emphasis
    (the B2' entry point) fold into the overlay and reach the run — the scope
    context carries all three and the plan.compiled event echoes ONLY the
    commit-layer keys (never silently dropped again)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        emphasis = ["prioritise rural areas"]
        delta = {
            "extract": {
                "extraction": {
                    "profiles": [IOF_PROFILE_ID],
                    "refresh": "abstract_only",
                    "relevance_emphasis": emphasis,
                }
            }
        }
        io = _InjectAtIO(target_component="select", response=Adjust(directive_deltas=delta))

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

        # profiles took the PLAN path (a new version carries extract_profiles).
        with engine.connect() as conn:
            latest = conn.execute(
                select(orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version.desc())
                .limit(1)
            ).scalar_one()
        assert latest["extract_profiles"] == ["iof"]

        # The overlay echoes ONLY the commit-layer keys — profiles are NOT overlaid.
        extract_compiled = _compiled_by_component(engine, project_id)["extract"]
        assert extract_compiled[0]["pending_overlay"] == {
            "extraction": {"refresh": "abstract_only", "relevance_emphasis": emphasis}
        }

        # The run consumed refresh + relevance_emphasis: the scope context carries
        # them alongside the plan-path profiles (the merged executed directive).
        extraction_ctx = _scope_context(engine, scope_id)["extraction"]
        assert extraction_ctx["refresh"] == "abstract_only"
        assert extraction_ctx["relevance_emphasis"] == emphasis
        assert extraction_ctx["profiles"] == [IOF_PROFILE_ID]
    finally:
        _cleanup_project(engine, project_id)


def test_pending_group_split_maps_facets_and_overlays_granularity_guidance(
    engine: Engine,
) -> None:
    """A pending-group Adjust carrying facets + granularity + guidance SPLITS:
    facets map to the plan; granularity (D8) + guidance (B3) overlay and reach the
    run. The plan.compiled event echoes only the commit-layer keys and the scope
    context carries them alongside the plan-path facets."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        guidance = ["group rural and urban separately"]
        delta = {
            "group": {
                "grouping": {
                    "facets": ["population"],
                    "granularity": "coarser",
                    "guidance": guidance,
                }
            }
        }
        io = _InjectAtIO(target_component="extract", response=Adjust(directive_deltas=delta))

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

        # facets took the PLAN path.
        with engine.connect() as conn:
            latest = conn.execute(
                select(orchestration_plan.c.payload)
                .where(orchestration_plan.c.project_id == project_id)
                .order_by(orchestration_plan.c.version.desc())
                .limit(1)
            ).scalar_one()
        assert latest["grouping_facets"] == ["population"]

        # The overlay echoes ONLY granularity + guidance (facets are NOT overlaid).
        group_compiled = _compiled_by_component(engine, project_id)["group"]
        assert group_compiled[0]["pending_overlay"] == {
            "grouping": {"granularity": "coarser", "guidance": guidance}
        }

        # The run consumed granularity + guidance (scope-context row).
        grouping_ctx = _scope_context(engine, scope_id)["grouping"]
        assert grouping_ctx["granularity"] == "coarser"
        assert grouping_ctx["guidance"] == guidance
        assert grouping_ctx["facets"] == ["population"]
    finally:
        _cleanup_project(engine, project_id)


def test_p3_refresh_extraction_option_applies_end_to_end(engine: Engine) -> None:
    """The canonical P3 refresh_extraction option (profiles + refresh) applies
    cleanly on pending extract: profiles map to the plan, refresh reaches the run
    via the overlay."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()  # moderate: P3 (deepening_selection) pauses
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        option = next(
            opt
            for opt in build_steer_point_options(plan=plan, point="deepening_selection")
            if opt["id"] == "refresh_extraction"
        )
        io = ScriptedIO(
            by_steer_point={
                "deepening_selection": [Adjust(directive_deltas=option["delta"])]
            }
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

        # The refresh reached the run through the overlay.
        extraction_ctx = _scope_context(engine, scope_id)["extraction"]
        assert extraction_ctx["refresh"] == "abstract_only"
        extract_compiled = _compiled_by_component(engine, project_id)["extract"]
        assert extract_compiled[0]["pending_overlay"] == {
            "extraction": {"refresh": "abstract_only"}
        }
    finally:
        _cleanup_project(engine, project_id)


def test_pending_select_commit_layer_key_overlays_to_run(engine: Engine) -> None:
    """FIX 3b: a non-budget select key on PENDING select is now a commit-layer
    directive — it folds into the pending overlay and reaches select's executed
    directive at its run (the same mechanism appraise/characterise/synthesise use),
    closing the compile/apply gap that previously crashed or was falsely rejected.
    ``strata_scope`` (D6) + ``weight_emphasis`` ride the overlay; ``exclude`` names
    a non-existent stratum so selection is unaffected (only the plumbing is under
    test)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(steering_mode="frequent")
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        selection_delta = {
            "strata_scope": {"exclude": ["nonexistent-stratum"]},
            "weight_emphasis": {"quality": 2.0},
        }
        io = _InjectAtIO(
            target_component="characterise",
            response=Adjust(directive_deltas={"select": {"selection": selection_delta}}),
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

        # No honest-rejection this time: the commit-layer keys are accepted, not
        # refused as "not yet mappable".
        with engine.connect() as conn:
            rejected = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == steering_events.STEERING_REJECTED
            ]
        assert not any("not yet mappable" in e["payload"].get("reason", "") for e in rejected)

        # The plan.compiled event echoes the whole commit-layer select delta
        # (nothing is plan-mappable here — budget is absent — so ALL of it overlays).
        select_compiled = _compiled_by_component(engine, project_id)["select"]
        assert select_compiled[0]["pending_overlay"] == {"selection": selection_delta}

        # The run consumed it: select's executed directive input (the scope context)
        # carries strata_scope + weight_emphasis.
        selection_ctx = _scope_context(engine, scope_id)["selection"]
        assert selection_ctx["strata_scope"] == {"exclude": ["nonexistent-stratum"]}
        assert selection_ctx["weight_emphasis"] == {"quality": 2.0}
    finally:
        _cleanup_project(engine, project_id)


def test_refuse_inexpressible_returns_honest_not_yet_message() -> None:
    message = refuse_inexpressible("rank by author reputation")
    assert "not yet expressible" in message
    assert "rank by author reputation" in message
    assert "seam" in message


# --- Replacement re-run generalisation (task 7 · contract decision 7) --------
# reselect (wired via the deepening-selection steer point) · re-characterise ·
# re-group. P2/P4 steer points that ENTER re-characterise/re-group land in
# Phase 4; here the generalised runner functions are exercised directly against
# a walked plan state, real DB, stub backends.


def _walk_to_completion(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    plan: OrchestrationPlan,
    plan_id: uuid.UUID,
) -> tuple[Any, dict[str, uuid.UUID], _SteeringState]:
    """Walk a plan to completion (no live steering) and reconstruct walk state.

    Returns the run outcome, the ``component -> successful run id`` map read from
    the outcome, and a ``_SteeringState`` positioned at the approved v1 plan row —
    the input a replacement re-run needs.
    """
    outcome = run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=NullIO(),
    )
    assert outcome.status == "succeeded"
    successful_runs = {
        step.component: step.run_id
        for step in outcome.steps
        if step.status == "succeeded" and step.run_id is not None
    }
    state = _SteeringState(
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        chain=compose(plan),
        pause_points=set(),
    )
    return outcome, successful_runs, state


def _plan_version_rows(engine: Engine, project_id: uuid.UUID) -> list[tuple[int, str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(
            select(
                orchestration_plan.c.version,
                orchestration_plan.c.status,
                orchestration_plan.c.created_by,
            )
            .where(orchestration_plan.c.project_id == project_id)
            .order_by(orchestration_plan.c.version)
        ).all()
    return [(row.version, row.status, row.created_by) for row in rows]


def _replacement_decisions(engine: Engine, project_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry
            for entry in events.read(conn, project_id)
            if entry["event_type"] == steering_events.STEERING_DECISION
            and entry["payload"].get("rerun_mode") == "replacement"
        ]


def test_re_characterise_moves_reference_preserves_rows_and_stamps_replacement(
    engine: Engine,
) -> None:
    """Re-characterise: new characterisation_result row, both rows persist, the
    walk's reference moves to the new run, a user-attributed plan version row is
    appended and the decision stamps rerun_mode=replacement."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state = _walk_to_completion(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )
        original_char = successful_runs["characterise"]

        base = steering_events.base_payload(
            capability_run_id=outcome.capability_run_id,
            plan_id=plan_id,
            plan_version=1,
            boundary="after_component",
            component="characterise",
        )
        adjustment = Adjust(
            directive_deltas={"characterise": {"characterise": {"themes": "more"}}}
        )
        rerun_state, merged = _apply_replacement_rerun(
            engine,
            project_id=project_id,
            state=state,
            adjustment=adjustment,
            base=base,
            event_run_id=original_char,
            component="characterise",
        )
        # characterise's compiled step carries no directive, so the merged fine
        # directive is exactly the option value.
        assert merged == {"characterise": {"themes": "more"}}

        _, new_char = _run_component_rerun(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=rerun_state,
            component="characterise",
            directive_delta=merged,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            blocked_discretionary={},
            step_outcomes=[],
            flagged_events=[],
            capability_run_id=outcome.capability_run_id,
        )

        assert new_char != original_char
        # The reference moves: downstream select would now reference the new run.
        assert successful_runs["characterise"] == new_char
        assert _reference_kwargs("select", successful_runs)["characterisation_run_id"] == new_char

        with engine.connect() as conn:
            char_run_ids = (
                conn.execute(
                    select(characterisation_result.c.run_id).where(
                        characterisation_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        # Rows immutable: BOTH the old and new characterisation rows persist.
        assert set(char_run_ids) == {original_char, new_char}

        assert _plan_version_rows(engine, project_id) == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]
        decisions = _replacement_decisions(engine, project_id)
        assert len(decisions) == 1
        assert decisions[0]["payload"]["boundary"] == "after_component"
        assert decisions[0]["payload"]["component"] == "characterise"
    finally:
        _cleanup_project(engine, project_id)


def test_re_group_moves_reference_preserves_rows_and_stamps_replacement(
    engine: Engine,
) -> None:
    """Re-group (same facet): new grouping_result row, both rows persist, and
    synthesise's reference rule picks the new grouping run."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state = _walk_to_completion(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )
        original_group = successful_runs["group"]

        base = steering_events.base_payload(
            capability_run_id=outcome.capability_run_id,
            plan_id=plan_id,
            plan_version=1,
            boundary="after_component",
            component="group",
        )
        adjustment = Adjust(
            directive_deltas={"group": {"grouping": {"granularity": "coarser"}}}
        )
        rerun_state, merged = _apply_replacement_rerun(
            engine,
            project_id=project_id,
            state=state,
            adjustment=adjustment,
            base=base,
            event_run_id=original_group,
            component="group",
        )
        # group's compiled step carries the plan facet; the option merges over it.
        assert merged == {"grouping": {"facets": ["outcome"], "granularity": "coarser"}}

        _, new_group = _run_component_rerun(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=rerun_state,
            component="group",
            directive_delta=merged,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            blocked_discretionary={},
            step_outcomes=[],
            flagged_events=[],
            capability_run_id=outcome.capability_run_id,
        )

        assert new_group != original_group
        assert successful_runs["group"] == new_group
        # synthesise references group first (deepest-available reference rule).
        assert _reference_kwargs("synthesise", successful_runs)["grouping_run_id"] == new_group

        with engine.connect() as conn:
            group_run_ids = (
                conn.execute(
                    select(grouping_result.c.run_id).where(
                        grouping_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
        assert set(group_run_ids) == {original_group, new_group}

        assert _plan_version_rows(engine, project_id) == [
            (1, "superseded", "planner"),
            (2, "approved", "user"),
        ]
        decisions = _replacement_decisions(engine, project_id)
        assert len(decisions) == 1
        assert decisions[0]["payload"]["component"] == "group"
    finally:
        _cleanup_project(engine, project_id)


def test_reselect_preserves_both_selection_rows_and_moves_reference(
    engine: Engine,
) -> None:
    """Re-select via the wired deepening-selection steer point: both
    selection_result rows persist (immutable), extract references the new run,
    and the steer point is not re-entered (one adjustment cycle per boundary)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        # Reselect lands at P3 (deepening_selection); other lattice pauses Continue.
        io = ScriptedIO(
            by_steer_point={
                "deepening_selection": [
                    Adjust(
                        directive_deltas={
                            "select": {"selection": {"weight_emphasis": {"quality": 2.0}}}
                        }
                    )
                ]
            }
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
            selection_run_ids = (
                conn.execute(
                    select(selection_result.c.run_id).where(
                        selection_result.c.project_id == project_id
                    )
                )
                .scalars()
                .all()
            )
            compiled = [
                entry
                for entry in events.read(conn, project_id)
                if entry["event_type"] == "plan.compiled"
            ]

        compiled_select = [
            entry["run_id"] for entry in compiled if entry["payload"]["component"] == "select"
        ]
        # Rows immutable: BOTH the original and re-run selection rows persist.
        assert len(selection_run_ids) == 2
        assert set(selection_run_ids) == set(compiled_select)

        # The walk's reference moved: extract threads the re-run (second) select.
        extract_payload = next(
            entry["payload"] for entry in compiled if entry["payload"]["component"] == "extract"
        )
        assert extract_payload["selection_run_id"] == str(compiled_select[1])

        # The P3 re-run boundary is not re-entered after the reselect (one cycle).
        steer_points = [
            point["steer_point"] for point, _ in io.pauses if point.get("kind") == "steer_point"
        ]
        assert steer_points.count("deepening_selection") == 1

        decisions = _replacement_decisions(engine, project_id)
        assert len(decisions) == 1
        assert decisions[0]["payload"]["component"] == "select"
    finally:
        _cleanup_project(engine, project_id)


def test_failed_replacement_rerun_blocks_downstream_discretionary(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed replacement re-run marks the component blocked so downstream
    discretionary dependents skip — mirroring a select re-run failure today
    (DISCRETIONARY_REQUIREMENTS maps select->characterise)."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan()
        plan_id = _insert_plan_row(engine, project_id=project_id, scope_id=scope_id, plan=plan)
        outcome, successful_runs, state = _walk_to_completion(
            engine, project_id=project_id, scope_id=scope_id, plan=plan, plan_id=plan_id
        )

        base = steering_events.base_payload(
            capability_run_id=outcome.capability_run_id,
            plan_id=plan_id,
            plan_version=1,
            boundary="after_component",
            component="characterise",
        )
        adjustment = Adjust(
            directive_deltas={"characterise": {"characterise": {"themes": "more"}}}
        )
        rerun_state, merged = _apply_replacement_rerun(
            engine,
            project_id=project_id,
            state=state,
            adjustment=adjustment,
            base=base,
            event_run_id=successful_runs["characterise"],
            component="characterise",
        )

        # Fault-inject the re-run only (the initial walk already succeeded).
        def failing_characterise_scope(*args: Any, **kwargs: Any) -> dict[str, Any]:
            del args, kwargs
            raise CharacteriseFailure(
                coverage={"base_counts": {}}, error="forced re-run failure"
            )

        monkeypatch.setattr(harness, "characterise_scope", failing_characterise_scope)

        blocked_discretionary: dict[str, str] = {}
        step_outcomes: list[Any] = []
        flagged_events: list[dict[str, Any]] = []
        _run_component_rerun(
            engine,
            NullIO(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            state=rerun_state,
            component="characterise",
            directive_delta=merged,
            backends=_runner_backends(),
            session_id=None,
            successful_runs=successful_runs,
            blocked_discretionary=blocked_discretionary,
            step_outcomes=step_outcomes,
            flagged_events=flagged_events,
            capability_run_id=outcome.capability_run_id,
        )

        assert step_outcomes[-1].status == "failed"
        assert step_outcomes[-1].retried is True
        # The failed re-run is un-threaded and the component is blocked.
        assert "characterise" not in successful_runs
        assert "characterise" in blocked_discretionary
        assert any(flag["status"] == "failed" for flag in flagged_events)
        # Mirrors select's failure today: a downstream discretionary dependent skips.
        assert _skip_reason("select", blocked_discretionary) is not None
    finally:
        _cleanup_project(engine, project_id)
