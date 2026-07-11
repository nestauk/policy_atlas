"""EB capability-runner for executing approved orchestration plans.

The runner is the deterministic sub-agent boundary for task 017: it walks a
composed orchestration plan, owns per-component commits, applies component
directive deltas to the scope context, and delegates one component at a time to
the existing harness.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, runtime_checkable

import structlog
from langfuse import Langfuse
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas import events, tracing
from policy_atlas.acquire import SearchBackend
from policy_atlas.classification_backend import ClassificationBackend
from policy_atlas.embeddings import EmbeddingBackend
from policy_atlas.extraction_backend import ExtractionBackend
from policy_atlas.facet_grouping import FacetGroupingBackend
from policy_atlas.grounding_judge import GroundingJudgeBackend
from policy_atlas.grouping import ThemeGroupingBackend
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest_full_text import DocumentFetcher
from policy_atlas.junk_judge import JunkJudgeBackend
from policy_atlas.orchestration_plan import (
    _REGISTRY_COMPONENT_BY_STEP,
    SPINE,
    ComponentStep,
    ComposedChain,
    OrchestrationPlan,
    compose,
)
from policy_atlas.plan import Plan, compile
from policy_atlas.ranking import RankingBackend
from policy_atlas.schema import event_log, evidence_scope, orchestration_plan, runs
from policy_atlas.screening_backend import ScreeningBackend
from policy_atlas.search_generation import SearchGenerationBackend
from policy_atlas.steering import (
    DEEPENING_SELECTION_STEER_POINT,
    Abort,
    Adjust,
    Continue,
    PausePoint,
    SteeringAdjustmentError,
    SteeringResponse,
    apply_adjustment,
    apply_reselect,
    build_steer_point_options,
    pause_points,
    render_check_in,
    render_collation,
    resolve_unattended,
    steer_point_triggers,
)
from policy_atlas.synthesis_backend import SynthesisBackend

log = structlog.get_logger()

COMPONENT_RETRY_CAP = 1
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed"})
LLM_BEARING_COMPONENTS = frozenset(
    {
        "screen",
        "screen_stage2",
        "classify",
        "characterise",
        "select",
        "extract",
        "group",
        "synthesise",
    }
)
SPINE_COMPONENTS = frozenset(SPINE)
DISCRETIONARY_REQUIREMENTS = {
    "select": "characterise",
    "extract": "select",
    "group": "extract",
}

RunPlanStatus = Literal["succeeded", "degraded", "failed", "aborted"]
StepStatus = Literal["succeeded", "failed", "skipped"]


@dataclass
class RunnerBackends:
    """Backend seams threaded into ``run_harness`` for every component.

    Args:
        embedding: Optional embedding backend. ``None`` lets the harness resolve
            its deterministic stub.
        theme_grouping: Optional characterisation theme-grouping backend.
        screening: Optional screening backend.
        classification: Optional classification backend.
        ranking: Optional selection reranking backend.
        extraction: Optional extraction backend.
        junk_judge: Optional extraction junk-judge backend (``None`` = off).
        facet_grouping: Optional facet-grouping backend.
        synthesis: Optional synthesis backend.
        grounding_judge: Optional grounding-judge backend.
        search_backends: Optional acquire search backends.
        search_generation: Optional search-generation backend.
        document_fetcher: Optional full-text document fetcher.
        langfuse_client: Optional tracing client used for component spans.
    """

    embedding: EmbeddingBackend | None = None
    theme_grouping: ThemeGroupingBackend | None = None
    screening: ScreeningBackend | None = None
    classification: ClassificationBackend | None = None
    ranking: RankingBackend | None = None
    extraction: ExtractionBackend | None = None
    junk_judge: JunkJudgeBackend | None = None
    facet_grouping: FacetGroupingBackend | None = None
    synthesis: SynthesisBackend | None = None
    grounding_judge: GroundingJudgeBackend | None = None
    search_backends: list[SearchBackend] | None = None
    search_generation: SearchGenerationBackend | None = None
    document_fetcher: DocumentFetcher | None = None
    langfuse_client: Langfuse | None = None


class CheckInIO(Protocol):
    """Minimal check-in sink accepted by the runner.

    Sub-agents do not address users directly. The runner reports deterministic
    component boundary outcomes through this protocol.
    """

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Report a component boundary outcome.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload containing status and
                headline counts.
        """
        ...


class OrchestratorIO(CheckInIO, Protocol):
    """Full runner-to-orchestrator IO seam with blocking steering pauses."""

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """Request a steering response at a deterministic pause point.

        Args:
            point: Boundary payload with kind, boundary and component fields.
            render: Deterministic human-readable check-in text.

        Returns:
            The steering response to apply.
        """
        ...


@runtime_checkable
class _PauseCapable(Protocol):
    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        ...


class NullIO:
    """No-op orchestrator IO implementation."""

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Ignore a component boundary outcome.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload.
        """
        del component, payload

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """Continue through a steering pause without interaction.

        Args:
            point: Pause-point payload.
            render: Deterministic pause render.

        Returns:
            ``Continue()``.
        """
        del point, render
        return Continue()


@dataclass
class RunStepOutcome:
    """Outcome for one composed orchestration step.

    Args:
        component: Orchestration step name.
        run_id: Final attempted run id, or ``None`` for skipped steps.
        status: Final step status.
        wall_clock_s: Final attempt wall-clock seconds, or ``None`` for skips.
        retried: Whether the step used its single runner retry.
        skipped: Whether the step was skipped without a harness run.
        reason: Failure or skip reason, when available.
        attempt_run_ids: Run ids created for this step, including retry attempts.
    """

    component: str
    run_id: uuid.UUID | None
    status: StepStatus
    wall_clock_s: float | None
    retried: bool = False
    skipped: bool = False
    reason: str | None = None
    attempt_run_ids: list[uuid.UUID] = field(default_factory=list)


@dataclass
class RunPlanOutcome:
    """End-of-run outcome for an orchestration plan walk.

    Args:
        status: Overall plan-run status.
        steps: Ordered per-step outcomes.
        flagged_events: Collated retry, failure and skip flags for review.
        collation_render: Deterministic end-of-run flagged-event render.
    """

    status: RunPlanStatus
    steps: list[RunStepOutcome]
    flagged_events: list[dict[str, Any]]
    collation_render: str = ""


@dataclass
class _AttemptOutcome:
    run_id: uuid.UUID
    status: Literal["succeeded", "failed"]
    wall_clock_s: float
    headline_counts: dict[str, Any]
    error: str | None


@dataclass
class _SteeringState:
    plan: OrchestrationPlan
    plan_id: uuid.UUID
    plan_version: int
    plan_row_id: uuid.UUID | None
    chain: ComposedChain
    pause_points: set[PausePoint]


@dataclass(frozen=True)
class _PauseApplied:
    state: _SteeringState
    aborted: bool = False
    changed: bool = False
    reselect: dict[str, Any] | None = None


def leg_directive(
    plan: OrchestrationPlan,
    step: ComponentStep,
    upstream_state: dict[str, Any],
) -> dict[str, Any]:
    """Return the directive delta for the next component.

    This is the named directive-authoring seam for a future EB-expert agent:
    given the approved orchestration plan, the next component step and the
    successful upstream state, that agent can author the component's context
    delta. V1 is intentionally deterministic and returns the composer-emitted
    directive unchanged.

    Args:
        plan: Approved orchestration plan.
        step: Composed component step.
        upstream_state: Successful predecessor state accumulated by the runner.

    Returns:
        The scope-context directive delta for this component.
    """
    del plan, upstream_state
    return dict(step.directive_delta)


def run_plan(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    plan: OrchestrationPlan,
    plan_id: uuid.UUID,
    plan_version: int,
    plan_row_id: uuid.UUID | None = None,
    backends: RunnerBackends | None = None,
    io: CheckInIO | None = None,
    session_id: uuid.UUID | None = None,
) -> RunPlanOutcome:
    """Execute an approved orchestration plan with per-component commits.

    Args:
        engine: SQLAlchemy engine. The runner owns short transactions and
            commits component work as it completes.
        project_id: Project owning the scope and runs.
        evidence_scope_id: Evidence scope all components execute over.
        plan: Approved orchestration plan to compose and walk.
        plan_id: Persisted orchestration-plan id carried into compile events.
        plan_version: Persisted orchestration-plan version carried into events.
        plan_row_id: Current orchestration-plan row id for steering amendments
            and abort status flips. ``None`` rejects adjustment persistence and
            makes abort a run-local stop only.
        backends: Optional backend seam bundle. ``None`` uses harness defaults.
        io: Optional orchestrator IO seam. ``None`` uses ``NullIO``.
        session_id: Optional Langfuse session id shared by the planner and all
            component attempts for one orchestrator conversation.

    Returns:
        Overall status, ordered step outcomes and collated flags.
    """
    backend_bundle = backends if backends is not None else RunnerBackends()
    io_sink = io if io is not None else NullIO()
    initial_chain = compose(plan)
    steering_state = _SteeringState(
        plan=plan,
        plan_id=plan_id,
        plan_version=plan_version,
        plan_row_id=plan_row_id,
        chain=initial_chain,
        pause_points=pause_points(plan.steering_mode, initial_chain),
    )
    remaining_steps = list(initial_chain.steps)
    step_outcomes: list[RunStepOutcome] = []
    flagged_events: list[dict[str, Any]] = []
    successful_runs: dict[str, uuid.UUID] = {}
    blocked_discretionary: dict[str, str] = {}
    completed_components: set[str] = set()
    last_check_in_payload: dict[str, Any] | None = None

    while remaining_steps:
        step = remaining_steps.pop(0)
        before_point = PausePoint("before_component", step.component)
        if before_point in steering_state.pause_points and last_check_in_payload is not None:
            pause_result = _handle_pause(
                engine,
                io_sink,
                point=before_point,
                render=render_check_in(last_check_in_payload),
                state=steering_state,
                project_id=project_id,
                completed_components=completed_components,
            )
            steering_state = pause_result.state
            if pause_result.aborted:
                return _finish_run(
                    step_outcomes,
                    flagged_events,
                    status="aborted",
                )
            if pause_result.changed:
                remaining_steps = _remaining_steps(
                    steering_state.chain,
                    completed_components=completed_components,
                )
                continue

        skip_reason = _skip_reason(step.component, blocked_discretionary)
        if skip_reason is not None:
            outcome = RunStepOutcome(
                component=step.component,
                run_id=None,
                status="skipped",
                wall_clock_s=None,
                skipped=True,
                reason=skip_reason,
            )
            step_outcomes.append(outcome)
            blocked_discretionary[step.component] = skip_reason
            flag = {"component": step.component, "status": "skipped", "reason": skip_reason}
            flagged_events.append(flag)
            last_check_in_payload = _check_in(
                io_sink,
                outcome,
                headline_counts={"reason": skip_reason},
            )
            completed_components.add(step.component)
            pause_result = _handle_after_component_boundary(
                engine,
                io_sink,
                step=step,
                render=render_check_in(last_check_in_payload),
                state=steering_state,
                project_id=project_id,
                completed_components=completed_components,
                flagged_events=flagged_events,
            )
            steering_state = pause_result.state
            if pause_result.aborted:
                return _finish_run(step_outcomes, flagged_events, status="aborted")
            remaining_steps = _remaining_steps(
                steering_state.chain,
                completed_components=completed_components,
            )
            continue

        upstream_state = {"successful_run_ids": dict(successful_runs)}
        directive_delta = leg_directive(steering_state.plan, step, upstream_state)
        reference_kwargs = _reference_kwargs(step.component, successful_runs)
        retry_cap = COMPONENT_RETRY_CAP if step.component in LLM_BEARING_COMPONENTS else 0

        attempts: list[_AttemptOutcome] = []
        for attempt_index in range(retry_cap + 1):
            attempt = _run_step_attempt(
                engine,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                plan=steering_state.plan,
                plan_id=steering_state.plan_id,
                plan_version=steering_state.plan_version,
                step=step,
                directive_delta=directive_delta,
                reference_kwargs=reference_kwargs,
                backends=backend_bundle,
                session_id=session_id,
            )
            attempts.append(attempt)
            if attempt.status == "succeeded":
                break
            if attempt_index < retry_cap:
                flagged_events.append(
                    {
                        "component": step.component,
                        "status": "retrying",
                        "run_id": str(attempt.run_id),
                        "reason": attempt.error,
                    }
                )

        final_attempt = attempts[-1]
        retried = len(attempts) > 1
        if final_attempt.status == "succeeded":
            successful_runs[step.component] = final_attempt.run_id
            outcome = RunStepOutcome(
                component=step.component,
                run_id=final_attempt.run_id,
                status="succeeded",
                wall_clock_s=final_attempt.wall_clock_s,
                retried=retried,
                attempt_run_ids=[attempt.run_id for attempt in attempts],
            )
            step_outcomes.append(outcome)
            if retried:
                flagged_events.append(
                    {
                        "component": step.component,
                        "status": "retried",
                        "run_id": str(final_attempt.run_id),
                    }
                )
            last_check_in_payload = _check_in(
                io_sink,
                outcome,
                headline_counts=final_attempt.headline_counts,
            )
            completed_components.add(step.component)
            pause_result = _handle_after_component_boundary(
                engine,
                io_sink,
                step=step,
                render=render_check_in(last_check_in_payload),
                state=steering_state,
                project_id=project_id,
                completed_components=completed_components,
                flagged_events=flagged_events,
                selection_run_id=(
                    final_attempt.run_id if step.component == "select" else None
                ),
            )
            steering_state = pause_result.state
            if pause_result.aborted:
                return _finish_run(step_outcomes, flagged_events, status="aborted")
            if pause_result.reselect is not None:
                last_check_in_payload = _run_select_rerun(
                    engine,
                    io_sink,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    state=steering_state,
                    directive_delta=pause_result.reselect["directive"],
                    backends=backend_bundle,
                    session_id=session_id,
                    successful_runs=successful_runs,
                    blocked_discretionary=blocked_discretionary,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                )
            remaining_steps = _remaining_steps(
                steering_state.chain,
                completed_components=completed_components,
            )
            continue

        reason = final_attempt.error or "component failed"
        outcome = RunStepOutcome(
            component=step.component,
            run_id=final_attempt.run_id,
            status="failed",
            wall_clock_s=final_attempt.wall_clock_s,
            retried=retried,
            reason=reason,
            attempt_run_ids=[attempt.run_id for attempt in attempts],
        )
        step_outcomes.append(outcome)
        flagged_events.append(
            {
                "component": step.component,
                "status": "failed",
                "run_id": str(final_attempt.run_id),
                "reason": reason,
            }
        )
        last_check_in_payload = _check_in(
            io_sink,
            outcome,
            headline_counts=final_attempt.headline_counts,
        )
        completed_components.add(step.component)
        pause_result = _handle_after_component_boundary(
            engine,
            io_sink,
            step=step,
            render=render_check_in(last_check_in_payload),
            state=steering_state,
            project_id=project_id,
            completed_components=completed_components,
            flagged_events=flagged_events,
        )
        steering_state = pause_result.state
        if pause_result.aborted:
            return _finish_run(step_outcomes, flagged_events, status="aborted")
        remaining_steps = _remaining_steps(
            steering_state.chain,
            completed_components=completed_components,
        )

        if step.component in SPINE_COMPONENTS:
            summary_status: RunPlanStatus = "failed"
            return _finish_run(step_outcomes, flagged_events, status=summary_status)
        blocked_discretionary[step.component] = reason

    summary_status = (
        "degraded"
        if any(outcome.status in {"failed", "skipped"} for outcome in step_outcomes)
        else "succeeded"
    )
    return _finish_run(step_outcomes, flagged_events, status=summary_status)


def _handle_after_component_boundary(
    engine: Engine,
    io: CheckInIO,
    *,
    step: ComponentStep,
    render: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    flagged_events: list[dict[str, Any]],
    selection_run_id: uuid.UUID | None = None,
) -> _PauseApplied:
    if step.component == "select" and state.plan.steering_mode == "unattended":
        return _resolve_unattended_boundary(
            engine,
            state=state,
            project_id=project_id,
            component=step.component,
            flagged_events=flagged_events,
        )

    point = PausePoint("after_component", step.component)
    if point not in state.pause_points:
        return _PauseApplied(state=state)
    # The deepening-selection steer point only offers re-run options when select
    # actually produced a persisted selection to steer over.
    is_steer_point = step.component == "select" and selection_run_id is not None
    triggers: list[dict[str, Any]] | None = None
    if is_steer_point and selection_run_id is not None:
        with engine.connect() as conn:
            triggers = steer_point_triggers(
                conn,
                project_id=project_id,
                selection_run_id=selection_run_id,
                plan=state.plan,
            )
    return _handle_pause(
        engine,
        io,
        point=point,
        render=render,
        state=state,
        project_id=project_id,
        completed_components=completed_components,
        steer_point=is_steer_point,
        triggers=triggers,
    )


def _handle_pause(
    engine: Engine,
    io: CheckInIO,
    *,
    point: PausePoint,
    render: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    steer_point: bool = False,
    triggers: list[dict[str, Any]] | None = None,
) -> _PauseApplied:
    pause_payload = _pause_payload(
        point, plan=state.plan, steer_point=steer_point, triggers=triggers
    )
    current_render = render
    while True:
        response = _pause_response(io, pause_payload, current_render)
        if isinstance(response, Continue):
            return _PauseApplied(state=state)
        if isinstance(response, Abort):
            _abandon_plan(engine, project_id=project_id, plan_row_id=state.plan_row_id)
            return _PauseApplied(state=state, aborted=True)
        if isinstance(response, Adjust):
            # At the deepening-selection steer point a select delta means re-run
            # select (it has already run); everywhere else a select delta is a
            # rejected already-run adjustment via the generic path below.
            if steer_point and set(response.directive_deltas) == {"select"}:
                try:
                    reselect_state, merged_directive = _apply_reselect(
                        engine,
                        project_id=project_id,
                        state=state,
                        adjustment=response,
                    )
                except SteeringAdjustmentError as exc:
                    current_render = f"{render}\nRe-selection rejected: {exc}"
                    continue
                return _PauseApplied(
                    state=reselect_state,
                    reselect={"directive": merged_directive},
                )
            try:
                amended_state = _apply_runner_adjustment(
                    engine,
                    project_id=project_id,
                    state=state,
                    adjustment=response,
                    completed_components=completed_components,
                )
            except SteeringAdjustmentError as exc:
                current_render = f"{render}\nAdjustment rejected: {exc}"
                continue
            return _PauseApplied(state=amended_state, changed=True)
        current_render = f"{render}\nSteering response rejected: unknown response type"


def _pause_response(
    io: CheckInIO,
    point: dict[str, Any],
    render: str,
) -> SteeringResponse:
    if isinstance(io, _PauseCapable):
        return io.pause(point, render)
    return Continue()


def _pause_payload(
    point: PausePoint,
    *,
    plan: OrchestrationPlan,
    steer_point: bool = False,
    triggers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "kind": "check_in",
        "boundary": point.boundary,
        "component": point.component,
    }
    if steer_point:
        payload["kind"] = "steer_point"
        payload["steer_point"] = DEEPENING_SELECTION_STEER_POINT
        payload["options"] = build_steer_point_options(
            plan=plan,
            point=DEEPENING_SELECTION_STEER_POINT,
        )
        if triggers is not None:
            payload["triggers"] = triggers
    return payload


def _apply_runner_adjustment(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    state: _SteeringState,
    adjustment: Adjust,
    completed_components: set[str],
) -> _SteeringState:
    if state.plan_row_id is None:
        raise SteeringAdjustmentError("plan_row_id is required to persist an adjustment")
    with engine.begin() as conn:
        plan_row = conn.execute(
            select(orchestration_plan).where(
                orchestration_plan.c.plan_id == state.plan_row_id
            )
        ).one()
        amended_plan, amended_plan_id, amended_version = apply_adjustment(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            adjustment=adjustment,
            completed_components=completed_components,
        )
    amended_chain = compose(amended_plan)
    return _SteeringState(
        plan=amended_plan,
        plan_id=amended_plan_id,
        plan_version=amended_version,
        plan_row_id=amended_plan_id,
        chain=amended_chain,
        pause_points=pause_points(amended_plan.steering_mode, amended_chain),
    )


def _apply_reselect(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    state: _SteeringState,
    adjustment: Adjust,
) -> tuple[_SteeringState, dict[str, Any]]:
    """Persist a re-selection version row and return the merged select directive.

    Merges the chosen steer-point option's select delta over the plan-compiled
    select directive (so the re-run keeps the plan's budget while gaining the
    option's emphasis/nominations), records a new user-attributed plan version
    row, and returns steering state advanced to that version. The chain and plan
    payload are unchanged — the fine directive lives at the commit layer.
    """
    if state.plan_row_id is None:
        raise SteeringAdjustmentError("plan_row_id is required to persist a re-selection")
    select_step = next(
        (step for step in state.chain.steps if step.component == "select"),
        None,
    )
    if select_step is None:
        raise SteeringAdjustmentError("composed chain has no select step to re-run")
    base_selection = select_step.directive_delta.get("selection", {})
    option_delta = adjustment.directive_deltas["select"]
    option_selection = option_delta.get("selection") if isinstance(option_delta, dict) else None
    if not isinstance(option_selection, dict) or not isinstance(base_selection, dict):
        raise SteeringAdjustmentError("select re-run directive must contain a selection object")
    merged_directive = {"selection": {**base_selection, **option_selection}}
    with engine.begin() as conn:
        plan_row = conn.execute(
            select(orchestration_plan).where(orchestration_plan.c.plan_id == state.plan_row_id)
        ).one()
        new_plan_id, new_version = apply_reselect(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            select_directive=merged_directive,
        )
    reselect_state = _SteeringState(
        plan=state.plan,
        plan_id=new_plan_id,
        plan_version=new_version,
        plan_row_id=new_plan_id,
        chain=state.chain,
        pause_points=state.pause_points,
    )
    return reselect_state, merged_directive


def _run_select_rerun(
    engine: Engine,
    io: CheckInIO,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    state: _SteeringState,
    directive_delta: dict[str, Any],
    backends: RunnerBackends,
    session_id: uuid.UUID | None,
    successful_runs: dict[str, uuid.UUID],
    blocked_discretionary: dict[str, str],
    step_outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Re-run ``select`` after a deepening-selection steer with a new directive.

    Creates a second ``select`` run under the amended plan version, applies the
    merged directive to the scope context and threads the new selection run id
    into ``successful_runs`` so downstream ``extract``/``group``/``synthesise``
    reference it. The steer point is not re-entered (one adjustment cycle per
    boundary). A failed re-run blocks the downstream deep chain, mirroring a
    discretionary failure. Extraction has not yet spent, so this is cheap.

    Returns:
        The check-in payload for the re-run outcome (the new most-recent render).
    """
    rerun_step = ComponentStep(
        component="select",
        directive_delta=directive_delta,
        reference_rule="characterisation_run_id <- characterise",
    )
    reference_kwargs = {"characterisation_run_id": successful_runs["characterise"]}
    retry_cap = COMPONENT_RETRY_CAP
    attempts: list[_AttemptOutcome] = []
    for attempt_index in range(retry_cap + 1):
        attempt = _run_step_attempt(
            engine,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            plan=state.plan,
            plan_id=state.plan_id,
            plan_version=state.plan_version,
            step=rerun_step,
            directive_delta=directive_delta,
            reference_kwargs=reference_kwargs,
            backends=backends,
            session_id=session_id,
        )
        attempts.append(attempt)
        if attempt.status == "succeeded":
            break
        if attempt_index < retry_cap:
            flagged_events.append(
                {
                    "component": "select",
                    "status": "retrying",
                    "run_id": str(attempt.run_id),
                    "reason": attempt.error,
                }
            )

    final_attempt = attempts[-1]
    retried = len(attempts) > 1
    attempt_run_ids = [attempt.run_id for attempt in attempts]
    if final_attempt.status == "succeeded":
        successful_runs["select"] = final_attempt.run_id
        outcome = RunStepOutcome(
            component="select",
            run_id=final_attempt.run_id,
            status="succeeded",
            wall_clock_s=final_attempt.wall_clock_s,
            retried=retried,
            attempt_run_ids=attempt_run_ids,
        )
    else:
        reason = final_attempt.error or "select re-run failed"
        successful_runs.pop("select", None)
        blocked_discretionary["select"] = reason
        outcome = RunStepOutcome(
            component="select",
            run_id=final_attempt.run_id,
            status="failed",
            wall_clock_s=final_attempt.wall_clock_s,
            retried=retried,
            reason=reason,
            attempt_run_ids=attempt_run_ids,
        )
        flagged_events.append(
            {
                "component": "select",
                "status": "failed",
                "run_id": str(final_attempt.run_id),
                "reason": reason,
            }
        )
    step_outcomes.append(outcome)
    return _check_in(io, outcome, headline_counts=final_attempt.headline_counts)


def _resolve_unattended_boundary(
    engine: Engine,
    *,
    state: _SteeringState,
    project_id: uuid.UUID,
    component: str,
    flagged_events: list[dict[str, Any]],
) -> _PauseApplied:
    action = resolve_unattended(state.plan, DEEPENING_SELECTION_STEER_POINT)
    rule = (
        DEEPENING_SELECTION_STEER_POINT
        if any(
            default.steer_point == DEEPENING_SELECTION_STEER_POINT
            for default in state.plan.steer_point_defaults
        )
        else "unconfigured_default"
    )
    flagged_events.append(
        {
            "component": component,
            "status": "auto_resolved",
            "rule": rule,
            "action": action,
        }
    )
    if action == "stop":
        _abandon_plan(engine, project_id=project_id, plan_row_id=state.plan_row_id)
        return _PauseApplied(state=state, aborted=True)
    return _PauseApplied(state=state)


def _remaining_steps(
    chain: ComposedChain,
    *,
    completed_components: set[str],
) -> list[ComponentStep]:
    return [step for step in chain.steps if step.component not in completed_components]


def _abandon_plan(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    plan_row_id: uuid.UUID | None,
) -> None:
    if plan_row_id is None:
        return
    with engine.begin() as conn:
        conn.execute(
            orchestration_plan.update()
            .where(orchestration_plan.c.plan_id == plan_row_id)
            .where(orchestration_plan.c.project_id == project_id)
            .values(status="abandoned")
        )


def _finish_run(
    outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    *,
    status: RunPlanStatus,
) -> RunPlanOutcome:
    collation = render_collation(flagged_events)
    log.info("runner.collation", render=collation)
    _log_run_summary(outcomes, status=status)
    return RunPlanOutcome(
        status=status,
        steps=outcomes,
        flagged_events=flagged_events,
        collation_render=collation,
    )


def _skip_reason(component: str, blocked_discretionary: dict[str, str]) -> str | None:
    required = DISCRETIONARY_REQUIREMENTS.get(component)
    if required is None:
        return None
    if required not in blocked_discretionary:
        return None
    reason = blocked_discretionary[required]
    return f"requires skipped/failed discretionary component {required}: {reason}"


def _reference_kwargs(
    component: str,
    successful_runs: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    if component == "select":
        return {"characterisation_run_id": successful_runs["characterise"]}
    if component == "extract":
        return {"selection_run_id": successful_runs["select"]}
    if component == "group":
        return {"extraction_run_id": successful_runs["extract"]}
    if component == "synthesise":
        for step_name, key in (
            ("group", "grouping_run_id"),
            ("extract", "extraction_run_id"),
            ("select", "selection_run_id"),
            ("characterise", "characterisation_run_id"),
        ):
            run_id = successful_runs.get(step_name)
            if run_id is not None:
                return {key: run_id}
    return {}


def _run_step_attempt(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    plan: OrchestrationPlan,
    plan_id: uuid.UUID,
    plan_version: int,
    step: ComponentStep,
    directive_delta: dict[str, Any],
    reference_kwargs: dict[str, uuid.UUID],
    backends: RunnerBackends,
    session_id: uuid.UUID | None,
) -> _AttemptOutcome:
    registry_component = _REGISTRY_COMPONENT_BY_STEP[step.component]
    run_id = uuid.uuid4()
    plan_payload = _plan_compiled_payload(
        step=step,
        registry_component=registry_component,
        evidence_scope_id=evidence_scope_id,
        plan_id=plan_id,
        plan_version=plan_version,
        reference_kwargs=reference_kwargs,
    )

    with engine.begin() as conn:
        conn.execute(
            runs.insert().values(
                run_id=run_id,
                project_id=project_id,
                status="running",
                started_at=datetime.now(UTC),
            )
        )
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="run.started",
            payload={
                "component": step.component,
                "registry_component": registry_component,
                "plan_id": str(plan_id),
                "plan_version": plan_version,
                # The Langfuse session key, persisted so a DB row joins
                # straight to its trace session (018 A2; None on session-less
                # paths, e.g. replay drivers).
                "session_id": str(session_id) if session_id is not None else None,
            },
        )
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="plan.compiled",
            payload=plan_payload,
        )

    started = time.monotonic()
    try:
        with engine.begin() as conn:
            _apply_directive(
                conn,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                directive_delta=directive_delta,
            )
            config = compile(
                Plan(
                    component=registry_component,
                    search_backend_scope=plan.backend_scope,
                    evidence_scope_id=evidence_scope_id,
                    **reference_kwargs,
                )
            )
            with tracing.component_span(
                backends.langfuse_client,
                run_id=run_id,
                project_id=project_id,
                component=step.component,
                session_id=session_id,
            ):
                run_harness(
                    conn,
                    config=config,
                    project_id=project_id,
                    run_id=run_id,
                    provider=StubEchoProvider(),
                    embedding_backend=backends.embedding,
                    theme_grouping_backend=backends.theme_grouping,
                    screening_backend=backends.screening,
                    classification_backend=backends.classification,
                    ranking_backend=backends.ranking,
                    extraction_backend=backends.extraction,
                    junk_judge_backend=backends.junk_judge,
                    facet_grouping_backend=backends.facet_grouping,
                    synthesis_backend=backends.synthesis,
                    grounding_judge_backend=backends.grounding_judge,
                    search_backends=backends.search_backends,
                    search_generation_backend=backends.search_generation,
                    document_fetcher=backends.document_fetcher,
                )
    except Exception as exc:
        wall_clock_s = time.monotonic() - started
        error = _bounded_error(exc)
        log.warning(
            "runner.component_failure_backstop",
            component=step.component,
            registry_component=registry_component,
            run_id=str(run_id),
            error=error,
        )
        _record_failure_backstop(
            engine,
            project_id=project_id,
            run_id=run_id,
            registry_component=registry_component,
            error=error,
        )
        with engine.connect() as conn:
            log_entries = events.read_for_run(conn, project_id, run_id)
        headline_counts = _headline_counts(log_entries, registry_component, run_id=run_id)
        usage_totals = _usage_totals(log_entries, registry_component, run_id=run_id)
        _record_component_timing(
            engine,
            project_id=project_id,
            run_id=run_id,
            component=step.component,
            registry_component=registry_component,
            wall_clock_s=wall_clock_s,
            status="failed",
            usage_totals=usage_totals,
            headline_counts=headline_counts,
        )
        return _AttemptOutcome(
            run_id=run_id,
            status="failed",
            wall_clock_s=wall_clock_s,
            headline_counts=headline_counts,
            error=error,
        )
    wall_clock_s = time.monotonic() - started

    with engine.connect() as conn:
        status = conn.execute(select(runs.c.status).where(runs.c.run_id == run_id)).scalar_one()
        log_entries = events.read_for_run(conn, project_id, run_id)

    headline_counts = _headline_counts(log_entries, registry_component, run_id=run_id)
    usage_totals = _usage_totals(log_entries, registry_component, run_id=run_id)
    failure_error = _failure_error(log_entries, registry_component, run_id=run_id)
    if status == "succeeded":
        _record_component_timing(
            engine,
            project_id=project_id,
            run_id=run_id,
            component=step.component,
            registry_component=registry_component,
            wall_clock_s=wall_clock_s,
            status="succeeded",
            usage_totals=usage_totals,
            headline_counts=headline_counts,
        )
        return _AttemptOutcome(
            run_id=run_id,
            status="succeeded",
            wall_clock_s=wall_clock_s,
            headline_counts=headline_counts,
            error=None,
        )
    _record_component_timing(
        engine,
        project_id=project_id,
        run_id=run_id,
        component=step.component,
        registry_component=registry_component,
        wall_clock_s=wall_clock_s,
        status="failed",
        usage_totals=usage_totals,
        headline_counts=headline_counts,
    )
    return _AttemptOutcome(
        run_id=run_id,
        status="failed",
        wall_clock_s=wall_clock_s,
        headline_counts=headline_counts,
        error=failure_error,
    )


def _record_component_timing(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    component: str,
    registry_component: str,
    wall_clock_s: float,
    status: Literal["succeeded", "failed"],
    usage_totals: dict[str, int] | None,
    headline_counts: dict[str, Any],
) -> None:
    payload = {
        "component": component,
        "registry_component": registry_component,
        "wall_clock_s": wall_clock_s,
        "status": status,
        "usage_totals": usage_totals,
        "headline_counts": headline_counts,
    }
    with engine.begin() as conn:
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="component.timing",
            payload=payload,
        )
    log.info(
        "runner.component_usage",
        component=component,
        registry_component=registry_component,
        run_id=str(run_id),
        status=status,
        usage_totals=usage_totals,
        headline_counts=headline_counts,
    )


def _bounded_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {str(exc)[:200]}"


def _record_failure_backstop(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    registry_component: str,
    error: str,
) -> None:
    with engine.begin() as conn:
        run_row = conn.execute(
            select(runs.c.status, runs.c.ended_at)
            .where(runs.c.project_id == project_id)
            .where(runs.c.run_id == run_id)
        ).one()
        component_failed_exists = (
            conn.execute(
                select(event_log.c.event_id)
                .where(event_log.c.project_id == project_id)
                .where(event_log.c.run_id == run_id)
                .where(event_log.c.event_type == "component.failed")
                .limit(1)
            ).first()
            is not None
        )
        if not component_failed_exists:
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="component.failed",
                payload={"component": registry_component, "error": error},
            )

        run_failed_exists = (
            conn.execute(
                select(event_log.c.event_id)
                .where(event_log.c.project_id == project_id)
                .where(event_log.c.run_id == run_id)
                .where(event_log.c.event_type == "run.failed")
                .limit(1)
            ).first()
            is not None
        )
        if not run_failed_exists and run_row.status != "succeeded":
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="run.failed",
                payload={"error": error},
            )

        if run_row.status not in TERMINAL_RUN_STATUSES:
            now = datetime.now(UTC)
            conn.execute(
                runs.update()
                .where(runs.c.project_id == project_id)
                .where(runs.c.run_id == run_id)
                .values(status="failed", ended_at=now)
            )
        elif run_row.status == "failed" and run_row.ended_at is None:
            now = datetime.now(UTC)
            conn.execute(
                runs.update()
                .where(runs.c.project_id == project_id)
                .where(runs.c.run_id == run_id)
                .values(ended_at=now)
            )


def _plan_compiled_payload(
    *,
    step: ComponentStep,
    registry_component: str,
    evidence_scope_id: uuid.UUID,
    plan_id: uuid.UUID,
    plan_version: int,
    reference_kwargs: dict[str, uuid.UUID],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "component": step.component,
        "registry_component": registry_component,
        "evidence_scope_id": str(evidence_scope_id),
        "plan_id": str(plan_id),
        "plan_version": plan_version,
    }
    if step.reference_rule is not None:
        payload["reference_rule"] = step.reference_rule
    for key, value in reference_kwargs.items():
        payload[key] = str(value)
    return payload


def _apply_directive(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    directive_delta: dict[str, Any],
) -> None:
    row = conn.execute(
        select(evidence_scope.c.context)
        .where(evidence_scope.c.evidence_scope_id == evidence_scope_id)
        .where(evidence_scope.c.project_id == project_id)
    ).one()
    scope_context = dict(row.context)
    directed_context = {**scope_context, **directive_delta}
    conn.execute(
        evidence_scope.update()
        .where(evidence_scope.c.evidence_scope_id == evidence_scope_id)
        .where(evidence_scope.c.project_id == project_id)
        .values(context=directed_context)
    )


def _headline_counts(
    log_entries: list[dict[str, Any]],
    registry_component: str,
    *,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    payload = next(
        (
            entry["payload"]
            for entry in reversed(log_entries)
            if entry["event_type"] == "component.completed"
            and entry["run_id"] == run_id
            and entry["payload"].get("component") == registry_component
        ),
        None,
    )
    if payload is None:
        return {}
    return {
        key: value
        for key, value in payload.items()
        if key not in {"component", "flags", "provenance"}
        and isinstance(value, (int, float, str, bool))
    }


def _usage_totals(
    log_entries: list[dict[str, Any]],
    registry_component: str,
    *,
    run_id: uuid.UUID,
) -> dict[str, int] | None:
    """Usage totals from the run's ``component.completed`` payload.

    ``None`` when no completed payload carries usage — a failed attempt spent
    tokens the summary never recorded, so absent stays absent, never zero.
    """
    payload = next(
        (
            entry["payload"]
            for entry in reversed(log_entries)
            if entry["event_type"] == "component.completed"
            and entry["run_id"] == run_id
            and entry["payload"].get("component") == registry_component
        ),
        None,
    )
    usage = payload.get("usage_totals") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return None
    return {
        "prompt": usage["prompt"] if isinstance(usage.get("prompt"), int) else 0,
        "completion": usage["completion"]
        if isinstance(usage.get("completion"), int)
        else 0,
        "total": usage["total"] if isinstance(usage.get("total"), int) else 0,
        "cached": usage["cached"] if isinstance(usage.get("cached"), int) else 0,
    }


def _failure_error(
    log_entries: list[dict[str, Any]],
    registry_component: str,
    *,
    run_id: uuid.UUID,
) -> str | None:
    payload = next(
        (
            entry["payload"]
            for entry in reversed(log_entries)
            if entry["event_type"] == "component.failed"
            and entry["run_id"] == run_id
            and entry["payload"].get("component") == registry_component
        ),
        None,
    )
    if payload is None:
        return None
    error = payload.get("error")
    return str(error) if error is not None else None


def _check_in(
    io: CheckInIO,
    outcome: RunStepOutcome,
    *,
    headline_counts: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "component": outcome.component,
        "status": outcome.status,
        "headline_counts": headline_counts,
    }
    if outcome.run_id is not None:
        payload["run_id"] = str(outcome.run_id)
    if outcome.wall_clock_s is not None:
        payload["wall_clock_s"] = outcome.wall_clock_s
    if outcome.retried:
        payload["retried"] = True
    if outcome.skipped:
        payload["skipped"] = True
    if outcome.reason is not None:
        payload["reason"] = outcome.reason
    io.check_in(outcome.component, payload)
    return payload


def _log_run_summary(
    outcomes: list[RunStepOutcome],
    *,
    status: RunPlanStatus,
) -> None:
    wall_clocks = {
        outcome.component: outcome.wall_clock_s
        for outcome in outcomes
        if outcome.wall_clock_s is not None
    }
    log.info("runner.plan_completed", status=status, wall_clocks=wall_clocks)
