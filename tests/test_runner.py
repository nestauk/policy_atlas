"""Runner tests for the task-017 EB capability-runner core."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

import policy_atlas.runner as runner_module
from policy_atlas import events, harness
from policy_atlas.characterise import CharacteriseFailure
from policy_atlas.fixtures import get_source
from policy_atlas.ingest import ingest_upload
from policy_atlas.orchestration_plan import OrchestrationPlan, compose
from policy_atlas.runner import RunnerBackends, run_plan
from policy_atlas.schema import (
    chunk,
    event_log,
    evidence_scope,
    project,
    runs,
    source_snapshot,
)
from policy_atlas.screen import ScreenContext, screen_sources
from tests.helpers import delete_project_data, now

FULL_COMPONENTS = ["screen_stage2", "characterise", "select", "extract", "group"]


class RecordingIO:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        self.calls.append((component, payload))


def _stat() -> dict[str, Any]:
    return {
        "effect_size": None,
        "effect_size_type": None,
        "ci_lower": None,
        "ci_upper": None,
        "standard_error": None,
        "p_value": None,
        "n": None,
        "k": None,
        "i_squared": None,
        "tau2": None,
    }


def _record(
    *,
    intervention: str,
    outcome: str,
    quote: str,
    segment_id: uuid.UUID,
) -> dict[str, Any]:
    return {
        "intervention": intervention,
        "outcome": outcome,
        "population": "low-income households",
        "comparator": None,
        "effect_direction": "increase",
        "estimate_level": "study",
        "study_design": "systematic review",
        "stratum_qualifiers": [],
        "statistics": _stat(),
        "causality_by_design": None,
        "is_primary": True,
        "is_prevalence_only": False,
        "anchors": [{"segment_id": str(segment_id), "quote": quote}],
    }


def _base_plan(**overrides: Any) -> OrchestrationPlan:
    payload: dict[str, Any] = {
        "title": "Housing affordability evidence",
        "question": "What policies address housing affordability?",
        "scoping_notes": ["Focus on policy-relevant evidence"],
        "screening_criteria": ["Include empirical or policy-analysis sources"],
        "backend_scope": "both",
        "scope_constraints": {},
        "search_effort": "rapid",
        # 018 regrade: select/extract/group are deep-only now, and this
        # default component set (FULL_COMPONENTS) exercises all of them, so
        # the default depth must be "deep", not "standard".
        "analysis_depth": "deep",
        "components": list(FULL_COMPONENTS),
        "component_rationale": {
            "screen_stage2": "Full-text confirmation is useful for this run",
            "characterise": "Maps themes and coverage before deeper work",
            "select": "Narrows the relevant corpus for extraction",
            "extract": "Captures intervention-outcome findings",
            "group": "Organises extracted findings by an approved facet",
        },
        "grouping_facet": "outcome",
        "steering_mode": "moderate",
        "steer_point_defaults": [
            {"steer_point": "deepening_selection", "action": "proceed_flag"}
        ],
        "assumptions": ["Publisher geography is publication geography"],
    }
    payload.update(overrides)
    return OrchestrationPlan.model_validate(payload)


def _seed_source_with_finding(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    source_locator: str,
    title: str,
    chunks: list[str],
    abstract: str,
    theme: str,
    intervention: str,
    outcome: str,
    quote: str,
) -> None:
    snapshot_id = ingest_upload(
        conn,
        project_id=project_id,
        chunks=chunks,
        source_locator=source_locator,
        metadata={
            "synthetic": True,
            "title": title,
            "abstract": f"{abstract} [stub-theme: {theme}]",
            "_stub_systematic_review": True,
            "_stub_tags": [theme],
        },
        text_basis="full_text",
    )
    segment_id = conn.execute(
        select(chunk.c.chunk_id)
        .where(chunk.c.source_snapshot_id == snapshot_id)
        .where(chunk.c.content.contains(quote))
        .order_by(chunk.c.sequence)
        .limit(1)
    ).scalar_one()
    metadata = dict(
        conn.execute(
            select(source_snapshot.c.metadata).where(
                source_snapshot.c.source_snapshot_id == snapshot_id
            )
        ).scalar_one()
    )
    metadata["_stub_iof"] = [
        _record(
            intervention=intervention,
            outcome=outcome,
            quote=quote,
            segment_id=segment_id,
        )
    ]
    conn.execute(
        update(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id == snapshot_id)
        .values(metadata=metadata)
    )


def _seed_project(
    engine: Engine,
    *,
    context: dict[str, Any] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    project_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(project.insert().values(project_id=project_id, created_at=now()))
        _seed_source_with_finding(
            conn,
            project_id=project_id,
            source_locator="syn-001",
            title="Synthetic audit-trail review",
            chunks=list(get_source("syn-001").chunks),
            abstract="A synthetic systematic review of provenance systems.",
            theme="audit trails",
            intervention="structured provenance tracking",
            outcome="audit trail quality",
            quote="structured provenance tracking improves audit trail quality",
        )
        _seed_source_with_finding(
            conn,
            project_id=project_id,
            source_locator="syn-002",
            title="Synthetic review of housing affordability policies",
            chunks=list(get_source("syn-002").chunks),
            abstract="A synthetic systematic review of housing affordability policies.",
            theme="housing affordability",
            intervention="inclusionary zoning",
            outcome="affordable housing supply",
            quote="inclusionary zoning requirements were associated with modest increases",
        )
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=project_id,
                intent="What policies address housing affordability?",
                context=context or {"theme": "housing"},
                created_at=now(),
            )
        )
    return project_id, scope_id


def _cleanup(engine: Engine, project_id: uuid.UUID | None) -> None:
    if project_id is None:
        return
    with engine.begin() as conn:
        delete_project_data(conn, project_id)


def _runner_backends() -> RunnerBackends:
    return RunnerBackends(search_backends=[])


def _plan_compiled_events(engine: Engine, project_id: uuid.UUID) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry
            for entry in events.read(conn, project_id)
            if entry["event_type"] == "plan.compiled"
        ]


def _payloads_by_component(
    engine: Engine,
    project_id: uuid.UUID,
) -> dict[str, list[dict[str, Any]]]:
    payloads: dict[str, list[dict[str, Any]]] = {}
    for entry in _plan_compiled_events(engine, project_id):
        payload = entry["payload"]
        payloads.setdefault(payload["component"], []).append(payload)
    return payloads


def _component_failed_payloads(
    engine: Engine,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry["payload"]
            for entry in events.read(conn, project_id)
            if entry["run_id"] == run_id and entry["event_type"] == "component.failed"
        ]


def _component_timing_payloads(
    engine: Engine,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            entry["payload"]
            for entry in events.read(conn, project_id)
            if entry["run_id"] == run_id and entry["event_type"] == "component.timing"
        ]


def _abort_current_transaction(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
) -> None:
    violated = False
    try:
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                project_id=project_id,
                status="running",
                started_at=now(),
            )
        )
    except Exception as exc:
        violated = True
        assert exc is not None
    assert violated


def _commit_existing_component_failed_event(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    component: str,
    sequence: int,
) -> None:
    with conn.engine.begin() as fresh_conn:
        fresh_conn.execute(
            event_log.insert().values(
                event_id=uuid.uuid4(),
                run_id=run_id,
                project_id=project_id,
                sequence=sequence,
                event_type="component.failed",
                occurred_at=datetime.now(UTC),
                payload={"component": component, "error": "pre-existing component failure"},
            )
        )


def test_full_stub_chain_commits_each_step_and_checks_in(engine: Engine) -> None:
    """Full step-by-step chain commits one run and check-in per step."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        # deep depth: the assertions below exercise select/extract/group,
        # which are deep-only after the 018 regrade.
        plan = _base_plan(search_effort="standard", analysis_depth="deep")
        plan_id = uuid.uuid4()
        session_id = uuid.uuid4()
        io = RecordingIO()

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=3,
            backends=_runner_backends(),
            io=io,
            session_id=session_id,
        )

        expected_components = compose(plan).components
        assert outcome.status == "succeeded"
        assert [step.component for step in outcome.steps] == expected_components
        assert all(step.status == "succeeded" for step in outcome.steps)
        assert all(step.wall_clock_s is not None for step in outcome.steps)
        assert [component for component, _ in io.calls] == expected_components

        with engine.connect() as conn:
            run_rows = conn.execute(
                select(runs.c.run_id, runs.c.status).where(runs.c.project_id == project_id)
            ).fetchall()
            log_entries = events.read(conn, project_id)
        assert len(run_rows) == len(expected_components)
        assert {row.status for row in run_rows} == {"succeeded"}

        event_types_by_run: dict[uuid.UUID, list[str]] = {}
        for entry in log_entries:
            event_types_by_run.setdefault(entry["run_id"], []).append(entry["event_type"])
        for step in outcome.steps:
            assert step.run_id is not None
            assert "run.started" in event_types_by_run[step.run_id]
            assert "plan.compiled" in event_types_by_run[step.run_id]
            timing_payloads = _component_timing_payloads(engine, project_id, step.run_id)
            assert len(timing_payloads) == 1
            timing_payload = timing_payloads[0]
            assert timing_payload["component"] == step.component
            assert timing_payload["status"] == "succeeded"
            assert timing_payload["wall_clock_s"] >= 0
            assert timing_payload["usage_totals"] == {
                "prompt": 0,
                "completion": 0,
                "total": 0,
            }
            assert isinstance(timing_payload["headline_counts"], dict)

        started_payloads = [
            entry["payload"] for entry in log_entries if entry["event_type"] == "run.started"
        ]
        assert {payload["session_id"] for payload in started_payloads} == {str(session_id)}

        payloads = _payloads_by_component(engine, project_id)
        assert payloads["acquire"][0]["plan_id"] == str(plan_id)
        assert payloads["acquire"][0]["plan_version"] == 3
        assert payloads["screen_stage2"][0]["registry_component"] == "screen"
        assert payloads["select"][0]["characterisation_run_id"] == str(
            next(step.run_id for step in outcome.steps if step.component == "characterise")
        )
        assert payloads["extract"][0]["selection_run_id"] == str(
            next(step.run_id for step in outcome.steps if step.component == "select")
        )
        assert payloads["group"][0]["extraction_run_id"] == str(
            next(step.run_id for step in outcome.steps if step.component == "extract")
        )
    finally:
        _cleanup(engine, project_id)


def test_landscape_chain_omits_deep_components_and_synthesises_from_characterisation(
    engine: Engine,
) -> None:
    """Landscape plan omits select/extract/group and synthesises from characterise."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facet=None,
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        components = [step.component for step in outcome.steps]
        assert outcome.status == "succeeded"
        assert "characterise" in components
        assert "select" not in components
        assert "extract" not in components
        assert "group" not in components
        synth_payload = _payloads_by_component(engine, project_id)["synthesise"][0]
        char_run_id = next(
            step.run_id for step in outcome.steps if step.component == "characterise"
        )
        assert synth_payload["characterisation_run_id"] == str(char_run_id)
    finally:
        _cleanup(engine, project_id)


def test_reference_threading_uses_group_then_deepest_available_reference(
    engine: Engine,
) -> None:
    """Synthesise references group when present, else the deepest successful run."""
    full_project: uuid.UUID | None = None
    drop_project: uuid.UUID | None = None
    try:
        full_project, full_scope = _seed_project(engine)
        full_plan = _base_plan()
        full_outcome = run_plan(
            engine,
            project_id=full_project,
            evidence_scope_id=full_scope,
            plan=full_plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        full_synth = _payloads_by_component(engine, full_project)["synthesise"][0]
        group_run_id = next(step.run_id for step in full_outcome.steps if step.component == "group")
        assert full_synth["grouping_run_id"] == str(group_run_id)
        assert "extraction_run_id" not in full_synth

        drop_project, drop_scope = _seed_project(engine)
        drop_plan = _base_plan(
            components=["characterise", "select", "extract"],
            grouping_facet=None,
        )
        drop_outcome = run_plan(
            engine,
            project_id=drop_project,
            evidence_scope_id=drop_scope,
            plan=drop_plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        drop_synth = _payloads_by_component(engine, drop_project)["synthesise"][0]
        extract_run_id = next(
            step.run_id for step in drop_outcome.steps if step.component == "extract"
        )
        assert drop_synth["extraction_run_id"] == str(extract_run_id)
        assert "selection_run_id" not in drop_synth
    finally:
        _cleanup(engine, full_project)
        _cleanup(engine, drop_project)


def test_spine_component_retries_once_then_continues(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient screen component failure creates a fresh retry run and succeeds."""
    project_id: uuid.UUID | None = None
    calls = 0

    def scripted_screen_sources(
        conn: Connection,
        *,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: ScreenContext,
        screening_backend: Any = None,
    ) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("forced transient screen failure")
        return screen_sources(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=context,
            screening_backend=screening_backend,
        )

    monkeypatch.setattr(harness, "screen_sources", scripted_screen_sources)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facet=None,
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        screen_outcome = next(step for step in outcome.steps if step.component == "screen")
        assert outcome.status == "succeeded"
        assert screen_outcome.status == "succeeded"
        assert screen_outcome.retried is True
        assert len(screen_outcome.attempt_run_ids) == 2

        with engine.connect() as conn:
            statuses = conn.execute(
                select(runs.c.status)
                .where(runs.c.run_id.in_(screen_outcome.attempt_run_ids))
                .order_by(runs.c.started_at)
            ).scalars().all()
        assert statuses == ["failed", "succeeded"]
    finally:
        _cleanup(engine, project_id)


def test_spine_failure_after_retry_stops_without_downstream_runs(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A persistent spine failure fails honestly and creates no downstream runs."""
    project_id: uuid.UUID | None = None

    def failing_screen_sources(
        conn: Connection,
        *,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        context: ScreenContext,
        screening_backend: Any = None,
    ) -> dict[str, Any]:
        del conn, project_id, run_id, context, screening_backend
        raise RuntimeError("forced persistent screen failure")

    monkeypatch.setattr(harness, "screen_sources", failing_screen_sources)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facet=None,
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        assert outcome.status == "failed"
        assert [step.component for step in outcome.steps] == ["acquire", "screen"]
        screen_outcome = outcome.steps[-1]
        assert screen_outcome.status == "failed"
        assert screen_outcome.retried is True
        assert len(screen_outcome.attempt_run_ids) == 2
        for attempt_run_id in screen_outcome.attempt_run_ids:
            timing_payloads = _component_timing_payloads(engine, project_id, attempt_run_id)
            assert len(timing_payloads) == 1
            assert timing_payloads[0]["component"] == "screen"
            assert timing_payloads[0]["registry_component"] == "screen"
            assert timing_payloads[0]["status"] == "failed"
            assert timing_payloads[0]["wall_clock_s"] >= 0
            assert timing_payloads[0]["usage_totals"] == {
                "prompt": 0,
                "completion": 0,
                "total": 0,
            }
        compiled_components = [
            event["payload"]["component"] for event in _plan_compiled_events(engine, project_id)
        ]
        assert compiled_components == [
            "acquire",
            "screen",
            "screen",
        ]
    finally:
        _cleanup(engine, project_id)


def test_db_abort_backstop_records_failure_event_and_fails_spine_plan(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An escaped DB-abort screen failure is repaired in a fresh transaction."""
    project_id: uuid.UUID | None = None
    original_run_harness = harness.run_harness
    escaped_message = f"forced db abort {'x' * 250} tail-marker"

    def aborting_screen_harness(
        conn: Connection,
        *,
        config: Any,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if config.component == "screen":
            _abort_current_transaction(conn, project_id=project_id, run_id=run_id)
            raise RuntimeError(escaped_message)
        return original_run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            **kwargs,
        )

    monkeypatch.setattr(runner_module, "run_harness", aborting_screen_harness)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facet=None,
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        assert outcome.status == "failed"
        assert [step.component for step in outcome.steps] == ["acquire", "screen"]
        screen_outcome = outcome.steps[-1]
        assert screen_outcome.status == "failed"
        assert screen_outcome.retried is True
        assert screen_outcome.reason is not None
        assert screen_outcome.reason.startswith("RuntimeError: forced db abort ")
        assert "tail-marker" not in screen_outcome.reason

        assert screen_outcome.run_id is not None
        with engine.connect() as conn:
            run_row = conn.execute(
                select(runs.c.status, runs.c.ended_at).where(
                    runs.c.run_id == screen_outcome.run_id
                )
            ).one()
        assert run_row.status == "failed"
        assert run_row.ended_at is not None

        failed_payloads = _component_failed_payloads(
            engine, project_id, screen_outcome.run_id
        )
        assert len(failed_payloads) == 1
        assert failed_payloads[0]["component"] == "screen"
        assert failed_payloads[0]["error"].startswith("RuntimeError: forced db abort ")
        assert "tail-marker" not in failed_payloads[0]["error"]
    finally:
        _cleanup(engine, project_id)


def test_backstop_idempotent_after_harness_component_failed_then_crash(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A later crash does not duplicate an already-present component.failed event."""
    project_id: uuid.UUID | None = None
    original_run_harness = harness.run_harness
    committed_failures = 0

    def failing_characterise_scope(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        raise CharacteriseFailure(coverage={"base_counts": {}}, error="forced characterise failure")

    def crash_after_failed_harness(
        conn: Connection,
        *,
        config: Any,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal committed_failures
        result = original_run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            **kwargs,
        )
        if config.component == "characterise":
            committed_failures += 1
            _commit_existing_component_failed_event(
                conn,
                project_id=project_id,
                run_id=run_id,
                component="characterise",
                sequence=1_000_000 + committed_failures * 100,
            )
            raise RuntimeError("post-harness crash after component.failed")
        return result

    monkeypatch.setattr(harness, "characterise_scope", failing_characterise_scope)
    monkeypatch.setattr(runner_module, "run_harness", crash_after_failed_harness)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(components=["characterise", "select", "extract", "group"])

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        characterise_outcome = next(
            step for step in outcome.steps if step.component == "characterise"
        )
        assert outcome.status == "degraded"
        assert characterise_outcome.status == "failed"
        assert characterise_outcome.run_id is not None
        failed_payloads = _component_failed_payloads(
            engine, project_id, characterise_outcome.run_id
        )
        assert len(failed_payloads) == 1
        assert failed_payloads[0]["component"] == "characterise"

        with engine.connect() as conn:
            run_row = conn.execute(
                select(runs.c.status).where(runs.c.run_id == characterise_outcome.run_id)
            ).one()
        assert run_row.status == "failed"
    finally:
        _cleanup(engine, project_id)


def test_backstop_failure_attempt_retries_and_succeeds(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient DB-abort failure consumes one retry, then the next screen run succeeds."""
    project_id: uuid.UUID | None = None
    original_run_harness = harness.run_harness
    screen_calls = 0

    def abort_first_screen_harness(
        conn: Connection,
        *,
        config: Any,
        project_id: uuid.UUID,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> dict[str, Any]:
        nonlocal screen_calls
        if config.component == "screen":
            screen_calls += 1
            if screen_calls == 1:
                _abort_current_transaction(conn, project_id=project_id, run_id=run_id)
                raise RuntimeError("transient db abort on screen")
        return original_run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            **kwargs,
        )

    monkeypatch.setattr(runner_module, "run_harness", abort_first_screen_harness)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(
            analysis_depth="landscape",
            components=["characterise"],
            grouping_facet=None,
        )

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        screen_outcome = next(step for step in outcome.steps if step.component == "screen")
        assert outcome.status == "succeeded"
        assert screen_outcome.status == "succeeded"
        assert screen_outcome.retried is True
        assert len(screen_outcome.attempt_run_ids) == 2
        assert screen_calls == 2

        with engine.connect() as conn:
            statuses = conn.execute(
                select(runs.c.status)
                .where(runs.c.run_id.in_(screen_outcome.attempt_run_ids))
                .order_by(runs.c.started_at)
            ).scalars().all()
        assert statuses == ["failed", "succeeded"]
    finally:
        _cleanup(engine, project_id)


def test_discretionary_failure_degrades_and_synthesises_without_reference(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A characterise failure skips dependent discretionary steps but still synthesises."""
    project_id: uuid.UUID | None = None

    def failing_characterise_scope(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        raise CharacteriseFailure(coverage={"base_counts": {}}, error="forced characterise failure")

    monkeypatch.setattr(harness, "characterise_scope", failing_characterise_scope)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(components=["characterise", "select", "extract", "group"])

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        by_component = {step.component: step for step in outcome.steps}
        assert outcome.status == "degraded"
        assert by_component["characterise"].status == "failed"
        assert by_component["characterise"].retried is True
        assert by_component["select"].skipped is True
        assert by_component["extract"].skipped is True
        assert by_component["group"].skipped is True
        assert by_component["synthesise"].status == "succeeded"
        assert any(flag["status"] == "failed" for flag in outcome.flagged_events)
        assert sum(1 for flag in outcome.flagged_events if flag["status"] == "skipped") == 3

        synth_payload = _payloads_by_component(engine, project_id)["synthesise"][0]
        for key in (
            "characterisation_run_id",
            "selection_run_id",
            "extraction_run_id",
            "grouping_run_id",
        ):
            assert key not in synth_payload
    finally:
        _cleanup(engine, project_id)


def test_failed_discretionary_run_id_never_feeds_downstream(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed characterise attempts are not threaded into downstream reference payloads."""
    project_id: uuid.UUID | None = None

    def failing_characterise_scope(*args: Any, **kwargs: Any) -> dict[str, Any]:
        del args, kwargs
        raise CharacteriseFailure(coverage={"base_counts": {}}, error="forced characterise failure")

    monkeypatch.setattr(harness, "characterise_scope", failing_characterise_scope)
    try:
        project_id, scope_id = _seed_project(engine)
        plan = _base_plan(components=["characterise", "select", "extract", "group"])

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        by_component = {step.component: step for step in outcome.steps}
        failed_run_ids = {
            str(run_id) for run_id in by_component["characterise"].attempt_run_ids
        }
        assert outcome.status == "degraded"
        assert by_component["characterise"].status == "failed"
        assert by_component["select"].skipped is True
        assert by_component["extract"].skipped is True
        assert by_component["group"].skipped is True

        synth_payload = _payloads_by_component(engine, project_id)["synthesise"][0]
        reference_keys = (
            "characterisation_run_id",
            "selection_run_id",
            "extraction_run_id",
            "grouping_run_id",
        )
        for key in reference_keys:
            assert key not in synth_payload

        with engine.connect() as conn:
            payloads = [entry["payload"] for entry in events.read(conn, project_id)]
        for payload in payloads:
            for key in reference_keys:
                assert payload.get(key) not in failed_run_ids
    finally:
        _cleanup(engine, project_id)


def test_directive_application_replaces_only_top_level_delta_keys(
    engine: Engine,
) -> None:
    """Applied directives survive in scope context while unrelated keys remain."""
    project_id: uuid.UUID | None = None
    try:
        project_id, scope_id = _seed_project(
            engine,
            context={
                "preexisting": {"survives": True},
                "selection": {"old": "removed by top-level replacement"},
            },
        )
        plan = _base_plan(grouping_facet="population")

        outcome = run_plan(
            engine,
            project_id=project_id,
            evidence_scope_id=scope_id,
            plan=plan,
            plan_id=uuid.uuid4(),
            plan_version=1,
            backends=_runner_backends(),
            io=RecordingIO(),
        )

        assert outcome.status == "succeeded"
        with engine.connect() as conn:
            context = conn.execute(
                select(evidence_scope.c.context).where(
                    evidence_scope.c.evidence_scope_id == scope_id
                )
            ).scalar_one()

        assert context["preexisting"] == {"survives": True}
        assert context["search"] == {"depth": "rapid"}
        assert context["screening"] == {
            "stage": 2,
            "criteria": ["Include empirical or policy-analysis sources"],
        }
        assert context["selection"] == {"budget": 25}
        assert context["grouping"] == {"facet": "population"}
    finally:
        _cleanup(engine, project_id)
