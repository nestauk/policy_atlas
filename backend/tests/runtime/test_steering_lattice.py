"""Task 024 Task 11 — the steer-point lattice: topology, options, bundles, authority.

Covers the deliverables owned by the lattice task: the mode table topology
(including Minimal's named fired-only behaviour change), every canonical option
compiling through its existing grammar, deterministic bundle renders, the P4
proposal wiring, lattice pause-event payloads (steer_point + options + triggers +
bundle), and the authority-order rule (a live user answer beats a standing rule).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import extraction_result, task_plan
from policy_atlas.evidence_search.synthesis.synthesis_backend import StubSynthesisBackend
from policy_atlas.evidence_search.synthesis.synthesis_tools import parse_synthesis_directive
from policy_atlas.runtime import runner as runner_module
from policy_atlas.runtime import steering_bundles
from policy_atlas.runtime.runner import run_plan
from policy_atlas.runtime.steering import (
    DEEPENING_SELECTION,
    EVIDENCE_SEARCH_COVERAGE,
    FINDING_GROUPS,
    LATTICE_POINTS,
    SEARCH_EXCEPTION,
    SYNTHESIS_SHAPE,
    Adjust,
    _validate_directive_delta,
    build_steer_point_options,
    generic_floor_options,
)
from policy_atlas.runtime.task_plan import compose
from tests.runtime.test_runner import _base_plan, _runner_backends, _seed_task
from tests.runtime.test_steering import ScriptedIO, _cleanup_task, _insert_plan_row

_ALL_POINTS = [
    SEARCH_EXCEPTION,
    EVIDENCE_SEARCH_COVERAGE,
    DEEPENING_SELECTION,
    FINDING_GROUPS,
    SYNTHESIS_SHAPE,
]


@pytest.mark.parametrize(
    ("mode", "floor_fired", "expected"),
    [
        ("frequent", False, set(_ALL_POINTS)),
        ("frequent", True, set(_ALL_POINTS)),
        ("moderate", False, {SEARCH_EXCEPTION, SYNTHESIS_SHAPE}),
        ("moderate", True, set(_ALL_POINTS)),
        ("minimal", False, set()),
        ("minimal", True, set(_ALL_POINTS)),
        ("unattended", False, set()),
        ("unattended", True, set()),
    ],
    ids=[
        "frequent-unfired",
        "frequent-fired",
        "moderate-unfired",
        "moderate-fired",
        "minimal-unfired",
        "minimal-fired",
        "unattended-unfired",
        "unattended-fired",
    ],
)
def test_lattice_mode_policy_is_applied_at_every_runner_boundary(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    floor_fired: bool,
    expected: set[str],
) -> None:
    """Exercise every mode × lattice point through the runner boundary path.

    This deliberately does not inspect ``_LATTICE_MODE_POLICY``: the observable
    pause surfaces prove the policy after the runner has read the point, its
    triggers, and the mode together.  A deep plan visits all five points.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        monkeypatch.setattr(
            runner_module,
            "_lattice_triggers",
            lambda *args, **kwargs: (
                [{"trigger": "test_floor", "detail": {}}] if floor_fired else []
            ),
        )
        plan = _base_plan(steering_mode=mode, steer_point_defaults=[])
        plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        io = ScriptedIO()
        outcome = run_plan(
            engine,
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )
        assert outcome.status == "succeeded"
        paused = {
            point["steer_point"]
            for point, _render in io.pauses
            if point.get("kind") == "steer_point"
        }
        assert paused == expected
    finally:
        _cleanup_task(engine, task_id)


def test_each_lattice_point_exposes_its_landed_floor_only() -> None:
    """Pin point-specific option ids and exclude depth-inappropriate controls."""
    plan = _base_plan(search_effort="standard", analysis_depth="deep")
    expected_ids = {
        SEARCH_EXCEPTION: {
            "continue",
            "deepen_search",
            "rescope_filters",
            "guide_queries",
            "abort",
        },
        EVIDENCE_SEARCH_COVERAGE: {
            "continue",
            "search_more",
            "adjust_criteria_rescreen",
            "recharacterise",
            "scope_strata",
            "exclude_docs",
        },
        DEEPENING_SELECTION: {
            "deepen_clusters",
            "strongest_evidence",
            "most_relevant",
            "adjust_budget",
            "as_proposed",
        },
        FINDING_GROUPS: {"as_proposed", "regroup_granularity", "regroup_guided"},
        SYNTHESIS_SHAPE: {"as_proposed", "emphasis_boosts", "edit_sections"},
    }
    for point, ids in expected_ids.items():
        assert {option["id"] for option in build_steer_point_options(plan=plan, point=point)} == ids

    non_deep = _base_plan(
        search_effort="standard",
        analysis_depth="standard",
        components=["characterise", "screen_full", "select"],
        component_rationale={
            "characterise": "Maps themes and coverage before deeper work",
            "screen_full": "Full-text confirmation is useful for this run",
            "select": "Guides synthesis emphasis at standard depth",
        },
        grouping_facets=None,
        extract_profiles=None,
    )
    assert "group" not in compose(non_deep).components
    group_component = LATTICE_POINTS[FINDING_GROUPS].component
    assert group_component not in compose(non_deep).components
    p3_ids = {
        option["id"]
        for option in build_steer_point_options(plan=plan, point=DEEPENING_SELECTION)
    }
    assert {"refresh_extraction", "enable_icf", "extract_icf"}.isdisjoint(p3_ids)


# --- Option grammar: every canonical delta compiles ------------------------


def _compile_option_delta(delta: dict[str, Any]) -> None:
    """Compile one option delta through the grammar its shape names (fail-closed)."""
    if not delta:
        return  # continue / abort / accept_thin / as_proposed — no directive
    keys = set(delta)
    if keys == {"selection"}:
        # Bare select fine-directive (the legacy P3 shape the wired reselect uses).
        _validate_directive_delta("select", delta, backend_scope="both")
        return
    if keys == {"synthesis"}:
        # Synthesis directive namespace (context["synthesis"]).
        parse_synthesis_directive({"synthesis": delta["synthesis"]}, grouping_group_ids=set())
        return
    assert len(keys) == 1, f"component-qualified option delta must name one component: {delta!r}"
    (component,) = keys
    _validate_directive_delta(component, delta[component], backend_scope="both")


def test_every_canonical_option_delta_compiles() -> None:
    plan = _base_plan(search_effort="standard", analysis_depth="deep")
    seen: set[str] = set()
    for point in _ALL_POINTS:
        options = build_steer_point_options(plan=plan, point=point)
        assert options, f"{point} has no options"
        for option in options:
            # Every option is well-shaped data.
            assert set(option) >= {"id", "intent", "label", "description", "delta"}
            assert "requires_user_input" in option
            assert option["intent"] and option["description"]
            _compile_option_delta(option["delta"])  # raises on any non-compiling delta
            seen.add(f"{point}:{option['id']}")
    # The owner-ruled P2/P3 re-home and new Groups point are all present.
    assert "deepening_selection:deepen_clusters" in seen
    assert "evidence_search_coverage:scope_strata" in seen
    assert "evidence_search_coverage:adjust_criteria_rescreen" in seen
    assert "finding_groups:regroup_granularity" in seen


def test_generic_floor_options_are_continue_change_mode_abort() -> None:
    ids = [option["id"] for option in generic_floor_options()]
    assert ids == ["continue", "change_mode", "abort"]
    for option in generic_floor_options():
        _compile_option_delta(option["delta"])  # all empty — trivially compile


def test_unknown_steer_point_rejected() -> None:
    with pytest.raises(ValueError, match="unknown steer point"):
        build_steer_point_options(plan=_base_plan(), point="not_a_point")


# --- Bundles: deterministic renders over persisted rows --------------------


def _walk(engine: Engine, task_id: uuid.UUID, scope_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Run a moderate deep plan to completion (NullIO) and return run ids by component."""
    plan = _base_plan()  # moderate, deep chain
    plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=ScriptedIO(),  # Continue at every fired/always pause
    )
    assert outcome.status == "succeeded"
    return {step.component: step.run_id for step in outcome.steps if step.run_id is not None}


def test_p3_bundle_shape_and_determinism(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        with engine.connect() as conn:
            bundle = steering_bundles.p3_bundle(
                conn, task_id=task_id, selection_run_id=runs_by["select"]
            )
            again = steering_bundles.p3_bundle(
                conn, task_id=task_id, selection_run_id=runs_by["select"]
            )
        assert bundle == again  # deterministic
        assert bundle["bundle_version"] == "v1"
        assert set(bundle) == {
            "bundle_version",
            "budget",
            "strategy",
            "selection_preview",
            "composition_by_stratum",
            "full_text_availability",
            "budget_picture",
            "ranking_trust",
            "flags",
            "notable_exclusions",
            "dropped_strata",
        }
        assert isinstance(bundle["selection_preview"], list)
        assert len(bundle["selection_preview"]) <= steering_bundles.SELECTION_PREVIEW_N
        for entry in bundle["selection_preview"]:
            assert set(entry) == {
                "tss_id",
                "title",
                "stratum",
                "evidence_type",
                "quality_tier",
                "reason",
                "text_basis",
            }
        assert set(bundle["ranking_trust"]) == {
            "effective_weights",
            "signal_availability",
            "backend_mode",
            "unmatched_boosts",
        }
    finally:
        _cleanup_task(engine, task_id)


def test_p2_bundle_shape_and_determinism(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        with engine.connect() as conn:
            bundle = steering_bundles.p2_bundle(
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                characterisation_run_id=runs_by.get("characterise"),
            )
            again = steering_bundles.p2_bundle(
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                characterisation_run_id=runs_by.get("characterise"),
            )
        assert bundle == again
        assert bundle["bundle_version"] == "v1"
        assert set(bundle) == {
            "bundle_version",
            "coverage",
            "themes",
            "unclustered_count",
            "search_coverage",
            "screen_counts",
            "screened_event_counts",
            "executed_queries",
            "zero_result_queries",
        }
        # Characterise ran, so coverage is present with its pinned top-level keys.
        assert isinstance(bundle["coverage"], dict)
        assert {"base", "base_counts", "distributions", "rates"} <= set(bundle["coverage"])
        # Effective screen counts by status/stage/generation, sorted deterministically.
        assert bundle["screen_counts"] == sorted(
            bundle["screen_counts"],
            key=lambda e: (e["status"], e["screen_stage"], e["screen_generation"]),
        )
    finally:
        _cleanup_task(engine, task_id)


def _acquire_completion_payload(
    engine: Engine, task_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, Any]:
    """The acquire run's ``component.completed`` payload — the headline's own source."""
    with engine.connect() as conn:
        entries = events.read_for_run(conn, task_id, run_id)
    payload = next(
        entry["payload"]
        for entry in reversed(entries)
        if entry["event_type"] == "component.completed"
        and entry["payload"].get("component") == "acquire"
    )
    assert isinstance(payload, dict)
    return payload


def test_p1_bundle_backend_counts_sum_to_the_acquired_headline(engine: Engine) -> None:
    """Task 031 invariant 1: a non-zero headline never sits above an all-zero line.

    Before this slice ``p1_bundle`` summed ``backends[].count`` on the coverage
    record, a key acquire never writes — so the line was permanently zero
    (defect 1a). It now reads the acquire run's own ``by_backend`` counts.

    The walk's stub search returns records the seeded task already holds, so
    its real headline is an honest 0. A later completion payload with a non-zero
    headline is appended on the same run to make the invariant bite; acquire
    defines that headline as the sum of the same ``by_backend`` values
    (acquire.py), which is what the assertion checks.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        acquire_run_id = runs_by["acquire"]
        real = _acquire_completion_payload(engine, task_id, acquire_run_id)
        assert "by_backend" in real, "acquire must persist per-backend counts"
        assert real["acquired"] == sum(
            stats["acquired"] for stats in real["by_backend"].values()
        ), "acquire's headline is the sum of its per-backend counts"

        by_backend = {"openalex": {"acquired": 5}, "overton": {"acquired": 2}}
        headline = 7
        with engine.begin() as conn:
            events.append(
                conn,
                task_id=task_id,
                run_id=acquire_run_id,
                event_type="component.completed",
                payload={"component": "acquire", "acquired": headline, "by_backend": by_backend},
            )

        with engine.connect() as conn:
            bundle = steering_bundles.p1_bundle(
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                acquire_run_id=acquire_run_id,
            )
        assert sum(entry["count"] for entry in bundle["backends"]) == headline
        assert bundle["backends"] == [
            {"backend": "openalex", "count": 5},
            {"backend": "overton", "count": 2},
        ]
    finally:
        _cleanup_task(engine, task_id)


def test_p1_bundle_scopes_queries_to_one_run_while_p2_spans_every_round(
    engine: Engine,
) -> None:
    """Task 031 invariant 2: P1 lists one round; P2 keeps the whole picture.

    The scope's other-round search calls are seeded on a second real run id, so
    the assertion is about the run filter rather than about a fabricated row.
    ``_executed_queries`` is shared, and spanning every round stays correct for
    P2's coverage picture — that half is the regression guard.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        acquire_run_id = runs_by["acquire"]
        other_round_run_id = runs_by["screen_abstract"]
        assert other_round_run_id != acquire_run_id

        with engine.begin() as conn:
            for run_id, query in (
                (acquire_run_id, "this round query"),
                (other_round_run_id, "other round query"),
            ):
                events.append(
                    conn,
                    task_id=task_id,
                    run_id=run_id,
                    event_type="search.executed",
                    payload={
                        "backend": "openalex",
                        "trust_class": "academic",
                        "mode": "live",
                        "query": query,
                        "query_origin": "seed",
                        "verb": "search",
                        "depth": "deep",
                        "filters": {},
                        "status": "ok",
                        "result_count": 3,
                        "error": None,
                        "evidence_scope_id": str(scope_id),
                    },
                )

        with engine.connect() as conn:
            p1 = steering_bundles.p1_bundle(
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                acquire_run_id=acquire_run_id,
            )
            p2 = steering_bundles.p2_bundle(
                conn, task_id=task_id, evidence_scope_id=scope_id
            )
        assert "this round query" in p1["queries"]
        assert "other round query" not in p1["queries"]
        p2_queries = [entry["query"] for entry in p2["executed_queries"]]
        assert "this round query" in p2_queries
        assert "other round query" in p2_queries
    finally:
        _cleanup_task(engine, task_id)


def test_p1_bundle_without_an_acquire_run_reports_absence_not_zeros(
    engine: Engine,
) -> None:
    """No acquire run recorded: empty counts and queries, never numbers from another round."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        _walk(engine, task_id, scope_id)
        with engine.connect() as conn:
            bundle = steering_bundles.p1_bundle(
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                acquire_run_id=None,
            )
        assert bundle["backends"] == []
        assert bundle["queries"] == []
        assert bundle["sample_titles"], "titles come from TSS and do not need the run id"
    finally:
        _cleanup_task(engine, task_id)


def test_p1_bundle_is_empty_when_the_boundary_run_is_not_the_successful_acquire(
    engine: Engine,
) -> None:
    """A failed round's P1 shows absence, not the previous round's numbers.

    ``successful_runs`` is written only on the success path (`runner.py`), but a
    failed acquire still presents its boundary. Without the boundary-run gate,
    round 2's P1 would render round 1's counts and queries under round 2's
    label — defect 1b inverted, and harder to spot than the zeros it replaced.
    """
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        succeeded = runs_by["acquire"]
        failed_later_round = uuid.uuid4()
        with engine.begin() as conn:
            events.append(
                conn,
                task_id=task_id,
                run_id=succeeded,
                event_type="component.completed",
                payload={
                    "component": "acquire",
                    "acquired": 4,
                    "by_backend": {"openalex": {"acquired": 4}},
                },
            )
            events.append(
                conn,
                task_id=task_id,
                run_id=succeeded,
                event_type="search.executed",
                payload={
                    "backend": "openalex",
                    "query": "round one query",
                    "status": "ok",
                    "result_count": 4,
                    "evidence_scope_id": str(scope_id),
                },
            )

        stale = runner_module._build_bundle(
            engine,
            name=SEARCH_EXCEPTION,
            task_id=task_id,
            evidence_scope_id=scope_id,
            successful_runs={"acquire": succeeded},
            backends=_runner_backends(),
            section_budget=None,
            boundary_run_id=failed_later_round,
        )
        assert stale is not None
        assert stale["backends"] == []
        assert stale["queries"] == []

        # Same call, boundary matching the successful run: the card fills in.
        current = runner_module._build_bundle(
            engine,
            name=SEARCH_EXCEPTION,
            task_id=task_id,
            evidence_scope_id=scope_id,
            successful_runs={"acquire": succeeded},
            backends=_runner_backends(),
            section_budget=None,
            boundary_run_id=succeeded,
        )
        assert current is not None
        assert current["queries"] == ["round one query"]
        assert current["backends"] == [{"backend": "openalex", "count": 4}]
    finally:
        _cleanup_task(engine, task_id)


def test_p2_bundle_parses_executed_and_zero_result_queries(engine: Engine) -> None:
    """Executed/zero-result queries come from seeded search.executed event payloads."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        acquire_run_id = runs_by["acquire"]
        # Seed two search.executed events on the acquire run (the N1 payload keys).
        with engine.begin() as conn:
            for query, count in (("childhood obesity policy", 7), ("rare edge subtopic", 0)):
                events.append(
                    conn,
                    task_id=task_id,
                    run_id=acquire_run_id,
                    event_type="search.executed",
                    payload={
                        "backend": "openalex",
                        "trust_class": "academic",
                        "mode": "live",
                        "query": query,
                        "query_origin": "seed",
                        "verb": "search",
                        "depth": "standard",
                        "filters": {},
                        "status": "ok",
                        "result_count": count,
                        "error": None,
                        "evidence_scope_id": str(scope_id),
                    },
                )
        with engine.connect() as conn:
            bundle = steering_bundles.p2_bundle(
                conn, task_id=task_id, evidence_scope_id=scope_id
            )
        queries = [entry["query"] for entry in bundle["executed_queries"]]
        assert queries == ["childhood obesity policy", "rare edge subtopic"]
        assert bundle["executed_queries"][0]["result_count"] == 7
        assert bundle["zero_result_queries"] == [
            {"query": "rare edge subtopic", "backend": "openalex"}
        ]
    finally:
        _cleanup_task(engine, task_id)


def test_p2_bundle_screened_event_counts_reflect_latest_generation_only(
    engine: Engine,
) -> None:
    """A criteria re-screen bumps ``screen_generation`` scope-wide; the P2
    ``screened_event_counts`` tally must reflect the current generation only —
    not an inflated sum across a stale generation and the current one."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        screen_run_id = runs_by["screen_full"]
        with engine.begin() as conn:
            for status, generation in (
                ("included", 0),
                ("included", 0),
                ("excluded", 0),
                ("included", 1),
                ("included", 1),
                ("included", 1),
            ):
                events.append(
                    conn,
                    task_id=task_id,
                    run_id=screen_run_id,
                    event_type="source.screened",
                    payload={
                        "evidence_scope_id": str(scope_id),
                        "status": status,
                        "screen_generation": generation,
                    },
                )
        with engine.connect() as conn:
            bundle = steering_bundles.p2_bundle(
                conn, task_id=task_id, evidence_scope_id=scope_id
            )
        # Only the max-generation (1) events count — generation 0 is superseded.
        assert bundle["screened_event_counts"] == {"included": 3}
    finally:
        _cleanup_task(engine, task_id)


def test_p4_bundle_wires_propose_synthesis_plan(engine: Engine) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk(engine, task_id, scope_id)
        with engine.connect() as conn:
            context = runner_module._synthesise_context(  # the walk's real inputs
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                successful_runs=runs_by,
            )
            assert context is not None
            backend = StubSynthesisBackend()
            bundle = steering_bundles.p4_bundle(
                conn,
                task_id=task_id,
                context=context,
                synthesis_backend=backend,
                group_run_id=runs_by.get("group"),
                section_budget=3,
            )
        assert bundle["bundle_version"] == "v1"
        assert set(bundle) == {"bundle_version", "proposal", "grouping_flags", "priority_counts"}
        # The proposal is the read-only propose_synthesis_plan payload.
        assert set(bundle["proposal"]) == {"proposed_sections", "available_groups", "boostable"}
        assert backend.proposal_inputs[0]["section_budget"] == 3
        # Grouping flags read from the group run; B2' priority counts absent (None).
        assert isinstance(bundle["grouping_flags"], dict)
        assert bundle["priority_counts"] is None
    finally:
        _cleanup_task(engine, task_id)


def _walk_no_group(
    engine: Engine, task_id: uuid.UUID, scope_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Run a moderate deep plan through extract but with no group step configured."""
    plan = _base_plan(
        components=["screen_full", "characterise", "select", "extract"],
        component_rationale={
            "screen_full": "Full-text confirmation is useful for this run",
            "characterise": "Maps themes and coverage before deeper work",
            "select": "Narrows the relevant corpus for extraction",
            "extract": "Captures intervention-outcome findings",
        },
        grouping_facets=None,
    )
    plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    outcome = run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=ScriptedIO(),  # Continue at every fired/always pause
    )
    assert outcome.status == "succeeded"
    return {step.component: step.run_id for step in outcome.steps if step.run_id is not None}


def test_p4_bundle_priority_counts_ungrouped_totals_without_group_step(engine: Engine) -> None:
    """Fix C: extract carries B2' relevance annotations but no group step ran —
    priority_counts must report the ungrouped totals, not None (which would be
    indistinguishable from "no annotations")."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        runs_by = _walk_no_group(engine, task_id, scope_id)
        assert "group" not in runs_by
        extract_run_id = runs_by["extract"]
        with engine.begin() as conn:
            provenance = conn.execute(
                select(extraction_result.c.extraction_provenance).where(
                    extraction_result.c.run_id == extract_run_id
                )
            ).scalar_one()
            provenance["relevance"] = {
                "annotations": {"f1": "priority", "f2": "normal", "f3": "priority"}
            }
            conn.execute(
                update(extraction_result)
                .where(extraction_result.c.run_id == extract_run_id)
                .values(extraction_provenance=provenance)
            )
        with engine.connect() as conn:
            context = runner_module._synthesise_context(
                conn,
                task_id=task_id,
                evidence_scope_id=scope_id,
                successful_runs=runs_by,
            )
            assert context is not None
            bundle = steering_bundles.p4_bundle(
                conn,
                task_id=task_id,
                context=context,
                synthesis_backend=StubSynthesisBackend(),
                group_run_id=runs_by.get("group"),
            )
        assert bundle["grouping_flags"] is None
        assert bundle["priority_counts"] == {"priority": 2, "normal": 1}
    finally:
        _cleanup_task(engine, task_id)


# --- Pause-event payloads carry the lattice surface ------------------------


def _pause_events(engine: Engine, task_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry
            for entry in events.read(conn, task_id)
            if entry["event_type"] == "steering.pause"
        ]


def test_lattice_pause_events_carry_steer_point_options_triggers_and_bundle(
    engine: Engine,
) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        _walk(engine, task_id, scope_id)  # moderate run, all pauses Continue
        pauses = _pause_events(engine, task_id)
        steer_pauses = {
            entry["payload"]["steer_point"]: entry["payload"]
            for entry in pauses
            if entry["payload"].get("kind") == "steer_point"
        }
        # Moderate always pauses at P2/P3/P4; every lattice pause carries its
        # steer_point name, options and fired triggers.
        assert {EVIDENCE_SEARCH_COVERAGE, DEEPENING_SELECTION, SYNTHESIS_SHAPE} <= set(steer_pauses)
        for name, payload in steer_pauses.items():
            assert payload["steer_point"] == name
            assert isinstance(payload["options"], list) and payload["options"]
            assert "triggers" in payload
        # P2/P3/P4 attach their deterministic bundle (the durable record).
        for name in (EVIDENCE_SEARCH_COVERAGE, DEEPENING_SELECTION, SYNTHESIS_SHAPE):
            assert steer_pauses[name].get("bundle", {}).get("bundle_version") == "v1"
    finally:
        _cleanup_task(engine, task_id)


# --- Minimal's named behaviour change: deepening_selection is fired-only ---


def _minimal_run_steer_points(
    engine: Engine, task_id: uuid.UUID, scope_id: uuid.UUID
) -> list[str]:
    plan = _base_plan(steering_mode="minimal")
    plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
    io = ScriptedIO()
    run_plan(
        engine,
        task_id=task_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=_runner_backends(),
        io=io,
    )
    return [
        point["steer_point"]
        for point, _ in io.pauses
        if point.get("kind") == "steer_point"
    ]


def test_minimal_deepening_selection_is_fired_only(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Named change: pre-024 Minimal always paused at deepening_selection; now it
    pauses there only when the S0 select triggers fire."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        # No S0 triggers -> Minimal does NOT pause at deepening_selection.
        monkeypatch.setattr(runner_module, "steer_point_triggers", lambda *a, **k: [])
        without = _minimal_run_steer_points(engine, task_id, scope_id)
        assert DEEPENING_SELECTION not in without
    finally:
        _cleanup_task(engine, task_id)


def test_minimal_deepening_selection_pauses_when_fired(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        # A fired S0 trigger -> Minimal pauses at deepening_selection.
        monkeypatch.setattr(
            runner_module,
            "steer_point_triggers",
            lambda *a, **k: [{"trigger": "thin_base", "detail": {}}],
        )
        fired = _minimal_run_steer_points(engine, task_id, scope_id)
        assert DEEPENING_SELECTION in fired
    finally:
        _cleanup_task(engine, task_id)


# --- Authority order: user answer beats a standing declared rule (review m1) -


def test_user_answer_beats_standing_declared_rule(engine: Engine) -> None:
    """At an attended pause a live user answer applies; the standing
    steer_point_defaults rule for that point does not decide (Task 12 pins
    rules > agent; here user > declared rules)."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id = _seed_task(engine)
        # A standing rule for deepening_selection is present in the plan.
        plan = _base_plan(
            steering_mode="moderate",
            steer_point_defaults=[
                {"steer_point": "deepening_selection", "action": "proceed_flag"}
            ],
        )
        assert plan.steer_point_defaults  # the rule stands in the plan
        plan_id = _insert_plan_row(engine, task_id=task_id, scope_id=scope_id, plan=plan)
        # The user answers differently at the P3 pause: a reselect.
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
            task_id=task_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=1,
            plan_row_id=plan_id,
            backends=_runner_backends(),
            io=io,
        )
        assert outcome.status == "succeeded"
        # The user's reselect applied — a new user-attributed plan version.
        with engine.connect() as conn:
            versions = conn.execute(
                select(task_plan.c.version, task_plan.c.created_by)
                .where(task_plan.c.task_id == task_id)
                .order_by(task_plan.c.version)
            ).all()
        assert (2, "user") in [(row.version, row.created_by) for row in versions]
        # The decision was decided_by the user, not the standing default.
        with engine.connect() as conn:
            decisions = [
                entry["payload"]
                for entry in events.read(conn, task_id)
                if entry["event_type"] == "steering.decision"
            ]
        reselect = next(d for d in decisions if d.get("rerun_mode") == "replacement")
        assert reselect["decided_by"] == "user"
        assert reselect["authored_by"] == "user"
        # The standing rule never decided: attended mode consults no default
        # (auto_resolved flags are the unattended-only signature of rule use).
        assert not any(
            flag.get("status") == "auto_resolved" for flag in outcome.flagged_events
        )
    finally:
        _cleanup_task(engine, task_id)
