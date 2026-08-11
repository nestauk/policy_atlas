"""Read-only reconstruction of a parked runner walk's continuation state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import capability_run, orchestration_plan, runs
from policy_atlas.runtime.orchestration_plan import ComposedChain, OrchestrationPlan, compose
from policy_atlas.runtime.steering import PausePoint, pause_points


@dataclass(frozen=True)
class ResumeDecision:
    """A persisted answer applied when a parked walk resumes.

    Args:
        response: Durable decision disposition.
        component: Replacement re-run target or additive boundary component.
        directive_delta: Merged replacement directive.
        segment_start: Additive re-entry segment start.
        directive_deltas: Per-component additive amendments.
        boundary: Boundary that accepted the additive re-entry.
    """

    response: Literal["continue", "adjust", "mode_change", "rerun", "segment_reentry"]
    component: str | None = None
    directive_delta: dict[str, Any] | None = None
    segment_start: str | None = None
    directive_deltas: dict[str, dict[str, Any]] | None = None
    boundary: Literal["after_component", "before_component"] | None = None


@dataclass(frozen=True)
class ContinuationState:
    """The runner loop fields reconstructed from durable state.

    Args:
        capability_run_id: Identity of the parked capability walk.
        plan: Version-max approved plan.
        plan_id: Persisted plan id.
        plan_version: Persisted plan version.
        plan_row_id: Current plan row id.
        chain: Recomposed component chain.
        pause_points: Pause points derived from the plan and chain.
        pending_overlays: Replayed commit-layer overlay map.
        remaining_steps: Uncompleted chain steps.
        step_outcomes: Park snapshot outcomes.
        flagged_events: Park snapshot collation flags.
        successful_runs: Latest successful component run map.
        attempted_runs: Latest attempted registry-run map.
        blocked_discretionary: Components blocked by their latest attempt.
        completed_components: Terminal component names.
        last_check_in_payload: Rebuilt latest check-in payload.
        parked_boundary: Boundary of the parked steering pause.
        parked_component: Component of the parked steering pause.
        most_recent_attempted_run_id: Latest attempted run id.
        session_id: Persisted trace-session id.
    """

    capability_run_id: uuid.UUID
    plan: OrchestrationPlan
    plan_id: uuid.UUID
    plan_version: int
    plan_row_id: uuid.UUID | None
    chain: ComposedChain
    pause_points: set[PausePoint]
    pending_overlays: dict[str, dict[str, Any]]
    remaining_steps: list[Any]
    step_outcomes: list[Any]
    flagged_events: list[dict[str, Any]]
    successful_runs: dict[str, uuid.UUID]
    attempted_runs: dict[str, uuid.UUID]
    blocked_discretionary: dict[str, str]
    completed_components: set[str]
    last_check_in_payload: dict[str, Any] | None
    parked_boundary: str | None
    parked_component: str | None
    most_recent_attempted_run_id: uuid.UUID | None
    session_id: uuid.UUID | None


def build(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
) -> ContinuationState:
    """Build a continuation state using only persisted plan, run, and event rows.

    Ordering is solely ``event_log.sequence``. Steering records are scoped by
    their payload capability-run key, never by their run-id attachment.

    Args:
        engine: Engine used for read-only durable reconstruction.
        project_id: Project owning the parked run.
        capability_run_id: Parked capability-run identity.

    Returns:
        Complete state suitable for ``runner.run_plan(resume_from=...)``.

    Raises:
        LookupError: If the capability run, approved plan, or park snapshot is absent.
    """
    # Local imports intentionally avoid a runner -> reducer import cycle.
    from policy_atlas.runtime.runner import (
        DISCRETIONARY_REQUIREMENTS,
        NullIO,
        RunStepOutcome,
        _check_in,
        _extend_overlays,
        _remaining_steps,
    )

    with engine.connect() as conn:
        cap_row = conn.execute(
            select(capability_run)
            .where(capability_run.c.project_id == project_id)
            .where(capability_run.c.capability_run_id == capability_run_id)
        ).one_or_none()
        if cap_row is None:
            raise LookupError(f"capability run {capability_run_id} does not exist")
        # Latest-approved is the walk's own lineage BY CONSTRUCTION, not by
        # accident (review finding codex-2, 2026-07-21): steering amendments
        # supersede within the walk's lineage, and the planning router 409s
        # any turn while a walk is running or parked — so no unrelated plan
        # can become latest-approved between park and continuation.
        plan_row = conn.execute(
            select(orchestration_plan)
            .where(orchestration_plan.c.project_id == project_id)
            .where(orchestration_plan.c.status == "approved")
            .order_by(orchestration_plan.c.version.desc())
        ).first()
        if plan_row is None:
            raise LookupError("parked walk has no approved orchestration plan")
        event_rows = events.read(conn, project_id)
        run_rows = [
            dict(row._mapping)
            for row in conn.execute(
                select(runs)
                .where(runs.c.project_id == project_id)
                .where(runs.c.capability_run_id == capability_run_id)
            )
        ]

    cap = dict(cap_row._mapping)
    plan_data = dict(plan_row._mapping)
    plan = OrchestrationPlan.model_validate(plan_data["payload"])
    chain = compose(plan)
    scoped_events = [
        entry
        for entry in event_rows
        if isinstance(entry["payload"], dict)
        and entry["payload"].get("capability_run_id") == str(capability_run_id)
    ]
    parked = next(
        (entry for entry in reversed(scoped_events) if entry["event_type"] == "run.parked"),
        None,
    )
    if parked is None:
        raise LookupError("parked walk has no run.parked snapshot")
    pause = next(
        (entry for entry in reversed(scoped_events) if entry["event_type"] == "steering.pause"),
        None,
    )
    pause_payload = pause["payload"] if pause is not None else {}
    parked_boundary = pause_payload.get("boundary") if isinstance(pause_payload, dict) else None
    parked_component = pause_payload.get("component") if isinstance(pause_payload, dict) else None
    if not isinstance(parked_boundary, str):
        parked_boundary = None
    if not isinstance(parked_component, str):
        parked_component = None
    snapshot = parked["payload"]
    outcomes = [
        _outcome_from_snapshot(value, RunStepOutcome) for value in snapshot["step_outcomes"]
    ]
    flagged_events = [dict(value) for value in snapshot["flagged_events"]]

    started_by_run = {
        entry["run_id"]: entry
        for entry in event_rows
        if entry["event_type"] == "run.started" and entry["run_id"] is not None
    }
    run_rows_by_id = {row["run_id"]: row for row in run_rows}
    attempts = sorted(
        (
            (started_by_run[run_id], row)
            for run_id, row in run_rows_by_id.items()
            if run_id in started_by_run
        ),
        key=lambda item: item[0]["sequence"],
    )
    latest_component: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    latest_registry: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for started, row in attempts:
        payload = started["payload"]
        component = payload.get("component")
        registry = payload.get("registry_component")
        if isinstance(component, str):
            latest_component[component] = (started, row)
        if isinstance(registry, str):
            latest_registry[registry] = (started, row)
    successful_runs = {
        component: row["run_id"]
        for component, (_, row) in latest_component.items()
        if row["status"] == "succeeded"
    }
    attempted_runs = {
        registry: row["run_id"] for registry, (_, row) in latest_registry.items()
    }
    # Read back from the park snapshot (G2 pattern), never re-derive: this set
    # drives remaining_steps — what re-executes after the park. The derived
    # fallback covers snapshots written before the field existed (adv-m4).
    snapshot_completed = snapshot.get("completed_components")
    completed_components = (
        set(snapshot_completed)
        if isinstance(snapshot_completed, list)
        else {outcome.component for outcome in outcomes}
    )
    blocked_discretionary: dict[str, str] = {}
    for component, (started, row) in latest_component.items():
        if component not in DISCRETIONARY_REQUIREMENTS:
            continue
        if row["status"] == "succeeded":
            continue
        blocked_discretionary[component] = _failure_reason(
            event_rows, started, row["run_id"]
        )
    for outcome in outcomes:
        if outcome.skipped and outcome.component in DISCRETIONARY_REQUIREMENTS:
            blocked_discretionary[outcome.component] = outcome.reason or "component skipped"

    overlays: dict[str, dict[str, Any]] = {}
    for entry in scoped_events:
        if entry["event_type"] != "steering.decision":
            continue
        payload = entry["payload"]
        if payload.get("rerun_mode") is not None or payload.get("response") not in {
            "adjust",
            "mode_change",
        }:
            continue
        action = payload.get("interpreted_action")
        if not isinstance(action, dict):
            continue
        deltas = action.get("directive_deltas")
        if isinstance(deltas, dict):
            overlays = _extend_overlays(overlays, deltas)
        compiled = action.get("compiled")
        if isinstance(compiled, list):
            for fragment in compiled:
                if not isinstance(fragment, dict) or fragment.get("kind") != "plan_adjustment":
                    continue
                if fragment.get("rerun_mode") is not None:
                    continue
                component = fragment.get("component")
                delta = fragment.get("delta")
                if isinstance(component, str) and isinstance(delta, dict):
                    overlays = _extend_overlays(overlays, {component: delta})

    last_check_in_payload: dict[str, Any] | None = None
    if outcomes:
        outcome = outcomes[-1]
        headline_counts = _headline_counts_for_outcome(event_rows, outcome)
        last_check_in_payload = _check_in(NullIO(), outcome, headline_counts=headline_counts)
    most_recent = parked["run_id"]
    if not isinstance(most_recent, uuid.UUID):
        most_recent = attempts[-1][1]["run_id"] if attempts else None
    return ContinuationState(
        capability_run_id=capability_run_id,
        plan=plan,
        plan_id=plan_data["plan_id"],
        plan_version=plan_data["version"],
        plan_row_id=plan_data["plan_id"],
        chain=chain,
        pause_points=pause_points(plan.steering_mode, chain),
        pending_overlays=overlays,
        remaining_steps=_remaining_steps(chain, completed_components=completed_components),
        step_outcomes=outcomes,
        flagged_events=flagged_events,
        successful_runs=successful_runs,
        attempted_runs=attempted_runs,
        blocked_discretionary=blocked_discretionary,
        completed_components=completed_components,
        last_check_in_payload=last_check_in_payload,
        parked_boundary=parked_boundary,
        parked_component=parked_component,
        most_recent_attempted_run_id=most_recent,
        session_id=cap["session_id"],
    )


def _outcome_from_snapshot(value: object, outcome_type: Any) -> Any:
    """Deserialize the JSONB park snapshot symmetrically with the runner."""
    if not isinstance(value, dict):
        raise LookupError("run.parked contains a malformed step outcome")
    run_id = value.get("run_id")
    attempt_ids = value.get("attempt_run_ids", [])
    return outcome_type(
        component=value["component"],
        run_id=uuid.UUID(run_id) if isinstance(run_id, str) else None,
        status=value["status"],
        wall_clock_s=value.get("wall_clock_s"),
        retried=bool(value.get("retried", False)),
        skipped=bool(value.get("skipped", False)),
        reason=value.get("reason") if isinstance(value.get("reason"), str) else None,
        attempt_run_ids=[uuid.UUID(item) for item in attempt_ids if isinstance(item, str)],
    )


def _failure_reason(
    event_rows: list[dict[str, Any]], started: dict[str, Any], run_id: uuid.UUID
) -> str:
    """Read the terminal failed-event reason for an attempt, when present."""
    registry = started["payload"].get("registry_component")
    for entry in reversed(event_rows):
        if entry["run_id"] != run_id or entry["event_type"] != "component.failed":
            continue
        payload = entry["payload"]
        if payload.get("component") == registry:
            error = payload.get("error", payload.get("reason"))
            if error is not None:
                return str(error)
    return "component failed"


def _headline_counts_for_outcome(
    event_rows: list[dict[str, Any]], outcome: Any
) -> dict[str, Any]:
    """Rebuild the latest check-in's scalar completed-event summary."""
    if outcome.run_id is None:
        return {"reason": outcome.reason} if outcome.reason is not None else {}
    started = next(
        (
            entry for entry in event_rows
            if entry["event_type"] == "run.started" and entry["run_id"] == outcome.run_id
        ),
        None,
    )
    registry = started["payload"].get("registry_component") if started else None
    for entry in reversed(event_rows):
        if entry["run_id"] != outcome.run_id or entry["event_type"] != "component.completed":
            continue
        payload = entry["payload"]
        if payload.get("component") != registry:
            continue
        return {
            key: value for key, value in payload.items()
            if key not in {"component", "flags", "provenance"}
            and isinstance(value, (int, float, str, bool))
        }
    return {}
