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

from policy_atlas.core import events, tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    capability_run,
    event_log,
    evidence_scope,
    orchestration_plan,
    runs,
)
from policy_atlas.evidence_base.assess.classification_backend import ClassificationBackend
from policy_atlas.evidence_base.assess.screening_backend import ScreeningBackend
from policy_atlas.evidence_base.corpus.ranking import RankingBackend
from policy_atlas.evidence_base.corpus.theme_grouping import ThemeGroupingBackend
from policy_atlas.evidence_base.extract.extraction_backend import ExtractionBackend
from policy_atlas.evidence_base.extract.finding_vetter import (
    FindingVetterBackend,
    ICFFindingVetterBackend,
)
from policy_atlas.evidence_base.group.group import GroupClusteringBackendFactory
from policy_atlas.evidence_base.sourcing.acquire import SearchBackend
from policy_atlas.evidence_base.sourcing.ingest_full_text import DocumentFetcher
from policy_atlas.evidence_base.sourcing.search_generation import SearchGenerationBackend
from policy_atlas.evidence_base.synthesis.grounding_judge import GroundingJudgeBackend
from policy_atlas.evidence_base.synthesis.synthesis_backend import SynthesisBackend
from policy_atlas.runtime import steering_events
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.orchestration_plan import (
    SPINE,
    ComponentStep,
    ComposedChain,
    OrchestrationPlan,
    compose,
    registry_component_for,
)
from policy_atlas.runtime.run_spec import Plan, compile
from policy_atlas.runtime.steering import (
    DEEPENING_SELECTION_STEER_POINT,
    SHIPPED_SEGMENT_START,
    Abort,
    Adjust,
    Continue,
    PausePoint,
    ReEnterSegment,
    SteeringAdjustmentError,
    SteeringResponse,
    apply_adjustment,
    apply_replacement_rerun,
    apply_segment_reentry,
    build_steer_point_options,
    pause_points,
    render_check_in,
    render_collation,
    resolve_unattended,
    steer_point_triggers,
)

log = structlog.get_logger()

COMPONENT_RETRY_CAP = 1
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed"})
LLM_BEARING_COMPONENTS = frozenset(
    {
        "screen_abstract",
        "screen_full",
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


@dataclass(frozen=True)
class _ReplacementRerun:
    """Component-parameterised rule for a reference-moving replacement re-run.

    Args:
        context_key: The single fine-directive context key the component's parser
            validates (select ``selection`` / characterise ``characterise`` /
            group ``grouping``).
        reference_upstream: The upstream component whose successful run this
            re-run references, or ``None`` when it references nothing upstream.
        reference_kwarg: The reference-threading kwarg name for the harness, or
            ``None`` when there is no upstream reference.
        reference_rule: Human-readable reference rule recorded in the compiled
            payload, or ``None``.
    """

    context_key: str
    reference_upstream: str | None
    reference_kwarg: str | None
    reference_rule: str | None


# Contract decision 7: the three reference-moving replacement re-runs. Old result
# rows persist immutably; the walk's reference moves — the new run id replaces the
# old in ``successful_runs`` so every downstream component references it. Only the
# select (deepening-selection) steer point ENTERS this from a wired pause today;
# P2 (re-characterise) and P4 (re-group) steer points land in Phase 4. The
# machinery is component-generic so those can call it without change.
REPLACEMENT_RERUNS: dict[str, _ReplacementRerun] = {
    "select": _ReplacementRerun(
        context_key="selection",
        reference_upstream="characterise",
        reference_kwarg="characterisation_run_id",
        reference_rule="characterisation_run_id <- characterise",
    ),
    "characterise": _ReplacementRerun(
        context_key="characterise",
        reference_upstream=None,
        reference_kwarg=None,
        reference_rule=None,
    ),
    "group": _ReplacementRerun(
        context_key="grouping",
        reference_upstream="extract",
        reference_kwarg="extraction_run_id",
        reference_rule="extraction_run_id <- extract",
    ),
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
        finding_vetter: Optional post-extract finding vetter (``None`` = off).
        icf_extraction: Optional ICF extraction backend.
        icf_finding_vetter: Optional ICF post-extract finding vetter.
        group_clustering: Optional group clustering backend factory.
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
    finding_vetter: FindingVetterBackend | None = None
    icf_extraction: Any | None = None
    icf_finding_vetter: ICFFindingVetterBackend | None = None
    group_clustering: GroupClusteringBackendFactory | None = None
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
        capability_run_id: The walk identity opened for this run (task 024).
    """

    status: RunPlanStatus
    steps: list[RunStepOutcome]
    flagged_events: list[dict[str, Any]]
    collation_render: str = ""
    capability_run_id: uuid.UUID | None = None


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
    # A triggered replacement re-run: ``{"component": str, "directive": dict}``.
    rerun: dict[str, Any] | None = None
    # A triggered additive segment re-entry (contract decision 7a):
    # ``{"segment_start": str, "boundary_component": str, "directive_deltas":
    # dict}``.
    segment_reentry: dict[str, Any] | None = None


@dataclass(frozen=True)
class _SegmentReentryResult:
    """Outcome of one bounded additive segment re-walk.

    Args:
        last_check_in_payload: Check-in payload of the last re-walked component,
            or ``None`` when the segment was empty.
        most_recent_attempted_run_id: The last re-walked run id, or ``None``.
        reenter_boundary: Whether the segment completed cleanly through the
            boundary and the boundary should be re-presented once.
        run_failed: Whether a spine component failed mid-segment (the run ends
            failed; the boundary is never re-entered).
    """

    last_check_in_payload: dict[str, Any] | None
    most_recent_attempted_run_id: uuid.UUID | None
    reenter_boundary: bool
    run_failed: bool


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
    capability_run_id = uuid.uuid4()
    _open_capability_run(
        engine,
        capability_run_id=capability_run_id,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        plan_id=plan_id,
        plan_version=plan_version,
        session_id=session_id,
    )
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
    most_recent_attempted_run_id: uuid.UUID | None = None

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
                capability_run_id=capability_run_id,
                event_run_id=most_recent_attempted_run_id,
            )
            steering_state = pause_result.state
            if pause_result.aborted:
                return _finish_run(
                    engine,
                    step_outcomes,
                    flagged_events,
                    status="aborted",
                    capability_run_id=capability_run_id,
                    project_id=project_id,
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
            # A skip can never precede the first run — _skip_reason requires a
            # prior discretionary failure — so most_recent is set; the chassis
            # asserts the invariant regardless.
            _emit_component_skipped(
                engine,
                capability_run_id=capability_run_id,
                project_id=project_id,
                state=steering_state,
                component=step.component,
                reason=skip_reason,
                run_id=most_recent_attempted_run_id,
            )
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
                capability_run_id=capability_run_id,
                most_recent_attempted_run_id=most_recent_attempted_run_id,
                boundary_run_id=None,
            )
            steering_state = pause_result.state
            if pause_result.aborted:
                return _finish_run(
                    engine,
                    step_outcomes,
                    flagged_events,
                    status="aborted",
                    capability_run_id=capability_run_id,
                    project_id=project_id,
                )
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
                capability_run_id=capability_run_id,
            )
            attempts.append(attempt)
            most_recent_attempted_run_id = attempt.run_id
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
                capability_run_id=capability_run_id,
                most_recent_attempted_run_id=most_recent_attempted_run_id,
                boundary_run_id=final_attempt.run_id,
                selection_run_id=(
                    final_attempt.run_id if step.component == "select" else None
                ),
                allow_segment_reentry=True,
            )
            steering_state = pause_result.state
            if pause_result.aborted:
                return _finish_run(
                    engine,
                    step_outcomes,
                    flagged_events,
                    status="aborted",
                    capability_run_id=capability_run_id,
                    project_id=project_id,
                )
            if pause_result.rerun is not None:
                last_check_in_payload, most_recent_attempted_run_id = _run_component_rerun(
                    engine,
                    io_sink,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    state=steering_state,
                    component=pause_result.rerun["component"],
                    directive_delta=pause_result.rerun["directive"],
                    backends=backend_bundle,
                    session_id=session_id,
                    successful_runs=successful_runs,
                    blocked_discretionary=blocked_discretionary,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                    capability_run_id=capability_run_id,
                )
            if pause_result.segment_reentry is not None:
                segment_result = _run_plan_segment_reentry(
                    engine,
                    io_sink,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    boundary_step=step,
                    segment_reentry=pause_result.segment_reentry,
                    state=steering_state,
                    backends=backend_bundle,
                    session_id=session_id,
                    successful_runs=successful_runs,
                    blocked_discretionary=blocked_discretionary,
                    completed_components=completed_components,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                    capability_run_id=capability_run_id,
                )
                steering_state = segment_result.state
                if segment_result.last_check_in_payload is not None:
                    last_check_in_payload = segment_result.last_check_in_payload
                if segment_result.most_recent_attempted_run_id is not None:
                    most_recent_attempted_run_id = (
                        segment_result.most_recent_attempted_run_id
                    )
                if segment_result.run_status is not None:
                    return _finish_run(
                        engine,
                        step_outcomes,
                        flagged_events,
                        status=segment_result.run_status,
                        capability_run_id=capability_run_id,
                        project_id=project_id,
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
            capability_run_id=capability_run_id,
            most_recent_attempted_run_id=most_recent_attempted_run_id,
            boundary_run_id=final_attempt.run_id,
        )
        steering_state = pause_result.state
        if pause_result.aborted:
            return _finish_run(
                engine,
                step_outcomes,
                flagged_events,
                status="aborted",
                capability_run_id=capability_run_id,
                project_id=project_id,
            )
        remaining_steps = _remaining_steps(
            steering_state.chain,
            completed_components=completed_components,
        )

        if step.component in SPINE_COMPONENTS:
            summary_status: RunPlanStatus = "failed"
            return _finish_run(
                engine,
                step_outcomes,
                flagged_events,
                status=summary_status,
                capability_run_id=capability_run_id,
                project_id=project_id,
            )
        blocked_discretionary[step.component] = reason

    summary_status = (
        "degraded"
        if any(outcome.status in {"failed", "skipped"} for outcome in step_outcomes)
        else "succeeded"
    )
    return _finish_run(
        engine,
        step_outcomes,
        flagged_events,
        status=summary_status,
        capability_run_id=capability_run_id,
        project_id=project_id,
    )


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
    capability_run_id: uuid.UUID,
    most_recent_attempted_run_id: uuid.UUID | None,
    boundary_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None = None,
    allow_segment_reentry: bool = False,
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
    # Run-id attachment (plan pin, review M2): an after_component event attaches
    # to the run it is about; a skipped component has no run of its own, so it
    # falls back to the most-recent attempted run id.
    event_run_id = boundary_run_id if boundary_run_id is not None else most_recent_attempted_run_id
    # The deepening-selection steer point only offers re-run options when select
    # actually produced a persisted selection to steer over.
    is_steer_point = step.component == "select" and selection_run_id is not None
    # The component this steer point offers a replacement re-run of. Today only
    # select is wired; P2 (characterise) and P4 (group) steer points land in
    # Phase 4 and reuse the same generic re-run machinery.
    rerun_component = (
        step.component
        if is_steer_point and step.component in REPLACEMENT_RERUNS
        else None
    )
    triggers: list[dict[str, Any]] | None = None
    if is_steer_point and selection_run_id is not None:
        with engine.connect() as conn:
            triggers = steer_point_triggers(
                conn,
                project_id=project_id,
                selection_run_id=selection_run_id,
                plan=state.plan,
            )
    # Additive segment re-entry (contract decision 7a) is offered at an
    # after_component boundary once acquire has run; the caller withholds it on
    # the single re-presentation after a re-walk (one cycle per boundary).
    segment_reentry_allowed = (
        allow_segment_reentry and SHIPPED_SEGMENT_START in completed_components
    )
    return _handle_pause(
        engine,
        io,
        point=point,
        render=render,
        state=state,
        project_id=project_id,
        completed_components=completed_components,
        capability_run_id=capability_run_id,
        event_run_id=event_run_id,
        steer_point=is_steer_point,
        triggers=triggers,
        rerun_component=rerun_component,
        segment_reentry_allowed=segment_reentry_allowed,
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
    capability_run_id: uuid.UUID,
    event_run_id: uuid.UUID | None,
    steer_point: bool = False,
    triggers: list[dict[str, Any]] | None = None,
    rerun_component: str | None = None,
    segment_reentry_allowed: bool = False,
) -> _PauseApplied:
    pause_payload = _pause_payload(
        point, plan=state.plan, steer_point=steer_point, triggers=triggers
    )
    base = steering_events.base_payload(
        capability_run_id=capability_run_id,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        boundary=point.boundary,
        component=point.component,
    )
    # One pause event per presentation; the re-prompt loop below marks each
    # rejected retry with steering.rejected rather than a fresh pause.
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=event_run_id,
        event_type=steering_events.STEERING_PAUSE,
        payload={**base, **pause_payload},
    )
    current_render = render
    while True:
        response = _pause_response(io, pause_payload, current_render)
        if isinstance(response, Continue):
            _emit_decision_standalone(
                engine,
                project_id=project_id,
                run_id=event_run_id,
                base=base,
                response="continue",
                interpreted_action=None,
                rerun_mode=None,
            )
            return _PauseApplied(state=state)
        if isinstance(response, Abort):
            _abort_and_record(
                engine,
                project_id=project_id,
                state=state,
                base=base,
                event_run_id=event_run_id,
            )
            return _PauseApplied(state=state, aborted=True)
        if isinstance(response, ReEnterSegment):
            # Fail-closed at the surface: additive segment re-entry is offered
            # only at an after_component boundary with acquire completed, and
            # never on the one re-presentation after a re-walk (the one
            # re-entry cycle per boundary rule).
            offending = _reentry_interpreted_action(response, point.component)
            if not segment_reentry_allowed:
                exc = SteeringAdjustmentError(
                    "segment re-entry is not available at this boundary presentation"
                )
                _emit_rejected(
                    engine,
                    project_id=project_id,
                    run_id=event_run_id,
                    base=base,
                    exc=exc,
                    offending_delta=offending,
                )
                current_render = f"{render}\nSegment re-entry rejected: {exc}"
                continue
            try:
                reentry_state = _apply_segment_reentry(
                    engine,
                    project_id=project_id,
                    state=state,
                    response=response,
                    base=base,
                    event_run_id=event_run_id,
                    completed_components=completed_components,
                    boundary_component=point.component,
                )
            except SteeringAdjustmentError as exc:
                _emit_rejected(
                    engine,
                    project_id=project_id,
                    run_id=event_run_id,
                    base=base,
                    exc=exc,
                    offending_delta=offending,
                )
                current_render = f"{render}\nSegment re-entry rejected: {exc}"
                continue
            return _PauseApplied(
                state=reentry_state,
                segment_reentry={
                    "segment_start": response.segment_start,
                    "boundary_component": point.component,
                    "directive_deltas": response.directive_deltas,
                },
            )
        if isinstance(response, Adjust):
            # At a replacement-rerun steer point a delta naming exactly the
            # steer-point's own component means re-run it (it has already run);
            # everywhere else naming an already-run component is a rejected
            # adjustment via the generic path below.
            if (
                rerun_component is not None
                and set(response.directive_deltas) == {rerun_component}
            ):
                try:
                    rerun_state, merged_directive = _apply_replacement_rerun(
                        engine,
                        project_id=project_id,
                        state=state,
                        adjustment=response,
                        base=base,
                        event_run_id=event_run_id,
                        component=rerun_component,
                    )
                except SteeringAdjustmentError as exc:
                    _emit_rejected(
                        engine,
                        project_id=project_id,
                        run_id=event_run_id,
                        base=base,
                        exc=exc,
                        offending_delta=_interpreted_action(response),
                    )
                    current_render = f"{render}\nRe-run rejected: {exc}"
                    continue
                return _PauseApplied(
                    state=rerun_state,
                    rerun={"component": rerun_component, "directive": merged_directive},
                )
            try:
                amended_state = _apply_runner_adjustment(
                    engine,
                    project_id=project_id,
                    state=state,
                    adjustment=response,
                    completed_components=completed_components,
                    base=base,
                    event_run_id=event_run_id,
                )
            except SteeringAdjustmentError as exc:
                _emit_rejected(
                    engine,
                    project_id=project_id,
                    run_id=event_run_id,
                    base=base,
                    exc=exc,
                    offending_delta=_interpreted_action(response),
                )
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


def _decision_response(adjustment: Adjust) -> steering_events.DecisionResponse:
    """An Adjust carrying a new mode surfaces as ``mode_change`` (review N3)."""
    return "mode_change" if adjustment.new_mode is not None else "adjust"


def _interpreted_action(adjustment: Adjust) -> dict[str, Any]:
    """Summarise an Adjust as the bounded delta / action recorded on the event."""
    summary: dict[str, Any] = {}
    if adjustment.directive_deltas:
        summary["directive_deltas"] = adjustment.directive_deltas
    if adjustment.new_mode is not None:
        summary["new_mode"] = adjustment.new_mode
    if adjustment.nudge is not None:
        summary["nudge"] = adjustment.nudge
    return summary


def _reentry_interpreted_action(
    response: ReEnterSegment,
    boundary_component: str,
) -> dict[str, Any]:
    """Summarise an additive segment re-entry for the decision/rejected event.

    Names the segment (start component, boundary, amended directive keys) — the
    contract's interpreted-action requirement for a re-run event.
    """
    return {
        "segment_start": response.segment_start,
        "boundary": boundary_component,
        "amended_directive_keys": sorted(response.directive_deltas),
    }


def _emit_decision_standalone(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    response: steering_events.DecisionResponse,
    interpreted_action: Any,
    rerun_mode: steering_events.RerunMode | None,
) -> None:
    """Append a user decision that has no adjacent state change (a Continue)."""
    payload = steering_events.decision_payload(
        base,
        decided_by="user",
        authored_by="user",
        response=response,
        interpreted_action=interpreted_action,
        confirmed=True,
        rerun_mode=rerun_mode,
    )
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_DECISION,
        payload=payload,
    )


def _emit_rejected(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    exc: SteeringAdjustmentError,
    offending_delta: dict[str, Any],
) -> None:
    """Append a standalone steering.rejected with the reason and offending delta."""
    payload = {
        **base,
        "reason": str(exc),
        "offending_delta": offending_delta,
    }
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_REJECTED,
        payload=payload,
    )


def _emit_component_skipped(
    engine: Engine,
    *,
    capability_run_id: uuid.UUID,
    project_id: uuid.UUID,
    state: _SteeringState,
    component: str,
    reason: str,
    run_id: uuid.UUID | None,
) -> None:
    """Append a standalone component.skipped attached to the most-recent run."""
    base = steering_events.base_payload(
        capability_run_id=capability_run_id,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        boundary="after_component",
        component=component,
    )
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.COMPONENT_SKIPPED,
        payload={**base, "reason": reason},
    )


def _abort_and_record(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    state: _SteeringState,
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
) -> None:
    """Flip the plan to abandoned and record the abort decision atomically.

    Contract decision 1 (finding m1): the abort decision commits on the same
    transaction as the abandon flip. When there is no plan row to flip
    (``plan_row_id`` is None — a run-local stop), the decision is a standalone
    append with no state-change partner.
    """
    decision = steering_events.decision_payload(
        base,
        decided_by="user",
        authored_by="user",
        response="abort",
        interpreted_action=None,
        confirmed=True,
        rerun_mode=None,
    )
    if state.plan_row_id is None:
        steering_events.emit_standalone(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            event_type=steering_events.STEERING_DECISION,
            payload=decision,
        )
        return
    with engine.begin() as conn:
        conn.execute(
            orchestration_plan.update()
            .where(orchestration_plan.c.plan_id == state.plan_row_id)
            .where(orchestration_plan.c.project_id == project_id)
            .values(status="abandoned")
        )
        steering_events.emit(
            conn,
            project_id=project_id,
            run_id=event_run_id,
            event_type=steering_events.STEERING_DECISION,
            payload=decision,
        )


def _apply_runner_adjustment(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    state: _SteeringState,
    adjustment: Adjust,
    completed_components: set[str],
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
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
        # The decision commits on the plan-version transaction (finding m1). The
        # base carries the version decided-over (pre-adjustment), matching pause.
        decision = steering_events.decision_payload(
            base,
            decided_by="user",
            authored_by="user",
            response=_decision_response(adjustment),
            interpreted_action=_interpreted_action(adjustment),
            confirmed=True,
            rerun_mode=None,
        )
        steering_events.emit(
            conn,
            project_id=project_id,
            run_id=event_run_id,
            event_type=steering_events.STEERING_DECISION,
            payload=decision,
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


def _apply_replacement_rerun(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    state: _SteeringState,
    adjustment: Adjust,
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
    component: str,
) -> tuple[_SteeringState, dict[str, Any]]:
    """Persist a replacement re-run version row and return the merged directive.

    Merges the chosen steer-point option's component delta over the plan-compiled
    directive for that component (so the re-run keeps the plan's compiled content
    — select budget, group facets — while gaining the option's fine directive),
    records a new user-attributed plan version row, and returns steering state
    advanced to that version. The chain and plan payload are unchanged — the fine
    directive lives at the commit layer (contract decision 7). The decision pairs
    transactionally with the plan-version row and stamps ``rerun_mode`` =
    ``replacement``.
    """
    spec = REPLACEMENT_RERUNS[component]
    if state.plan_row_id is None:
        raise SteeringAdjustmentError("plan_row_id is required to persist a replacement re-run")
    target_step = next(
        (step for step in state.chain.steps if step.component == component),
        None,
    )
    if target_step is None:
        raise SteeringAdjustmentError(f"composed chain has no {component} step to re-run")
    key = spec.context_key
    base_directive = target_step.directive_delta.get(key, {})
    option_delta = adjustment.directive_deltas[component]
    option_value = option_delta.get(key) if isinstance(option_delta, dict) else None
    if not isinstance(option_value, dict) or not isinstance(base_directive, dict):
        raise SteeringAdjustmentError(
            f"{component} re-run directive must contain a {key!r} object"
        )
    merged_directive = {key: {**base_directive, **option_value}}
    with engine.begin() as conn:
        plan_row = conn.execute(
            select(orchestration_plan).where(orchestration_plan.c.plan_id == state.plan_row_id)
        ).one()
        new_plan_id, new_version = apply_replacement_rerun(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            component=component,
            directive=merged_directive,
        )
        # Every replacement re-run pairs its decision with the new plan-version
        # row and stamps rerun_mode "replacement" (component-generic emission).
        decision = steering_events.decision_payload(
            base,
            decided_by="user",
            authored_by="user",
            response=_decision_response(adjustment),
            interpreted_action=_interpreted_action(adjustment),
            confirmed=True,
            rerun_mode="replacement",
        )
        steering_events.emit(
            conn,
            project_id=project_id,
            run_id=event_run_id,
            event_type=steering_events.STEERING_DECISION,
            payload=decision,
        )
    rerun_state = _SteeringState(
        plan=state.plan,
        plan_id=new_plan_id,
        plan_version=new_version,
        plan_row_id=new_plan_id,
        chain=state.chain,
        pause_points=state.pause_points,
    )
    return rerun_state, merged_directive


def _run_component_rerun(
    engine: Engine,
    io: CheckInIO,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    state: _SteeringState,
    component: str,
    directive_delta: dict[str, Any],
    backends: RunnerBackends,
    session_id: uuid.UUID | None,
    successful_runs: dict[str, uuid.UUID],
    blocked_discretionary: dict[str, str],
    step_outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    capability_run_id: uuid.UUID,
) -> tuple[dict[str, Any], uuid.UUID]:
    """Re-run a component after a replacement-rerun steer with a new directive.

    Creates a second run of ``component`` under the amended plan version, applies
    the merged directive to the scope context and threads the new run id into
    ``successful_runs`` so every downstream component references it (contract
    decision 7 — the reference moves; old result rows persist immutably). The
    upstream reference is component-parameterised: select references
    characterise's run, group references extract's run, characterise references
    nothing upstream. The steer point is not re-entered (one adjustment cycle per
    boundary). A failed re-run marks the component blocked so downstream
    discretionary dependents skip, mirroring a discretionary failure
    (``DISCRETIONARY_REQUIREMENTS`` maps select→characterise, group→extract).

    Returns:
        The check-in payload for the re-run outcome (the new most-recent render)
        and the re-run's run id (the new most-recent attempted run).
    """
    spec = REPLACEMENT_RERUNS[component]
    reference_kwargs: dict[str, uuid.UUID] = {}
    if spec.reference_upstream is not None and spec.reference_kwarg is not None:
        reference_kwargs = {spec.reference_kwarg: successful_runs[spec.reference_upstream]}
    rerun_step = ComponentStep(
        component=component,
        directive_delta=directive_delta,
        reference_rule=spec.reference_rule,
    )
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
            capability_run_id=capability_run_id,
        )
        attempts.append(attempt)
        if attempt.status == "succeeded":
            break
        if attempt_index < retry_cap:
            flagged_events.append(
                {
                    "component": component,
                    "status": "retrying",
                    "run_id": str(attempt.run_id),
                    "reason": attempt.error,
                }
            )

    final_attempt = attempts[-1]
    retried = len(attempts) > 1
    attempt_run_ids = [attempt.run_id for attempt in attempts]
    if final_attempt.status == "succeeded":
        successful_runs[component] = final_attempt.run_id
        outcome = RunStepOutcome(
            component=component,
            run_id=final_attempt.run_id,
            status="succeeded",
            wall_clock_s=final_attempt.wall_clock_s,
            retried=retried,
            attempt_run_ids=attempt_run_ids,
        )
    else:
        reason = final_attempt.error or f"{component} re-run failed"
        successful_runs.pop(component, None)
        blocked_discretionary[component] = reason
        outcome = RunStepOutcome(
            component=component,
            run_id=final_attempt.run_id,
            status="failed",
            wall_clock_s=final_attempt.wall_clock_s,
            retried=retried,
            reason=reason,
            attempt_run_ids=attempt_run_ids,
        )
        flagged_events.append(
            {
                "component": component,
                "status": "failed",
                "run_id": str(final_attempt.run_id),
                "reason": reason,
            }
        )
    step_outcomes.append(outcome)
    return (
        _check_in(io, outcome, headline_counts=final_attempt.headline_counts),
        final_attempt.run_id,
    )


def _segment_components(
    chain: ComposedChain,
    *,
    segment_start: str,
    boundary_component: str,
    completed_components: set[str],
) -> list[str]:
    """Completed components from ``segment_start`` to ``boundary_component`` inclusive.

    Chain order, both ends inclusive, filtered to already-completed components —
    the set the additive re-walk re-runs.
    """
    components = chain.components
    start_idx = components.index(segment_start)
    end_idx = components.index(boundary_component)
    return [
        component
        for component in components[start_idx : end_idx + 1]
        if component in completed_components
    ]


def _merge_amendment(
    base_directive: dict[str, Any],
    amendment: dict[str, Any],
) -> dict[str, Any]:
    """Merge an amendment delta over a component's plan-compiled directive.

    Shallow-merges one level under each shared top key (so an acquire amendment
    ``{"search": {"guidance": [...]}}`` merges into the compiled ``{"search":
    {"depth": ..., "filters": ...}}`` rather than replacing it).
    """
    merged = dict(base_directive)
    for key, value in amendment.items():
        existing = merged.get(key)
        if isinstance(value, dict) and isinstance(existing, dict):
            merged[key] = {**existing, **value}
        else:
            merged[key] = value
    return merged


def _apply_segment_reentry(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    state: _SteeringState,
    response: ReEnterSegment,
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
    completed_components: set[str],
    boundary_component: str,
) -> _SteeringState:
    """Persist an additive segment re-entry version row and advance steering state.

    Validates the segment (start component + per-component amendment grammar via
    :func:`apply_segment_reentry`) and that every amendment delta names a
    component inside the re-walked segment, records a new user-attributed plan
    version row (plan payload carries forward — the amendment is commit-layer),
    and pairs the decision event with the version row transactionally, stamping
    ``rerun_mode`` = ``additive`` (contract decision 7a).
    """
    if state.plan_row_id is None:
        raise SteeringAdjustmentError("plan_row_id is required to persist a segment re-entry")
    segment = set(
        _segment_components(
            state.chain,
            segment_start=response.segment_start,
            boundary_component=boundary_component,
            completed_components=completed_components,
        )
    )
    for component in response.directive_deltas:
        if component not in segment:
            raise SteeringAdjustmentError(
                f"segment re-entry amendment names component {component!r} outside the "
                "re-walked segment"
            )
    with engine.begin() as conn:
        plan_row = conn.execute(
            select(orchestration_plan).where(orchestration_plan.c.plan_id == state.plan_row_id)
        ).one()
        new_plan_id, new_version = apply_segment_reentry(
            conn,
            project_id=project_id,
            plan_row=plan_row,
            plan=state.plan,
            segment_start=response.segment_start,
            directive_deltas=response.directive_deltas,
        )
        decision = steering_events.decision_payload(
            base,
            decided_by="user",
            authored_by="user",
            response="adjust",
            interpreted_action=_reentry_interpreted_action(response, boundary_component),
            confirmed=True,
            rerun_mode="additive",
        )
        steering_events.emit(
            conn,
            project_id=project_id,
            run_id=event_run_id,
            event_type=steering_events.STEERING_DECISION,
            payload=decision,
        )
    return _SteeringState(
        plan=state.plan,
        plan_id=new_plan_id,
        plan_version=new_version,
        plan_row_id=new_plan_id,
        chain=state.chain,
        pause_points=state.pause_points,
    )


def _run_segment_reentry(
    engine: Engine,
    io: CheckInIO,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    state: _SteeringState,
    segment_start: str,
    boundary_component: str,
    directive_deltas: dict[str, dict[str, Any]],
    backends: RunnerBackends,
    session_id: uuid.UUID | None,
    successful_runs: dict[str, uuid.UUID],
    blocked_discretionary: dict[str, str],
    completed_components: set[str],
    step_outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    capability_run_id: uuid.UUID,
) -> _SegmentReentryResult:
    """Re-walk a bounded additive segment, then signal whether to re-enter the boundary.

    Contract decision 7a: from ``segment_start`` the walk re-runs every
    already-completed component up to ``boundary_component`` in chain order. Each
    re-walked component gets a FRESH run threaded with ``capability_run_id`` (the
    normal ``_run_step_attempt`` path), and ``successful_runs`` moves to each new
    run so provenance records all contributing runs (union coverage). Incremental
    behaviour is the components' own (acquire dedups; screen/classify/appraise
    skip already-processed docs) — nothing already processed is reprocessed. The
    amendment is applied per component by merging it over the plan-compiled
    directive.

    Honest degrade on a mid-segment failure (normal component-failure semantics):
    a spine-component failure ends the run (``run_failed=True``) and never
    re-enters the boundary; a discretionary-component failure blocks that
    component (downstream dependents skip) and does not re-enter the boundary.
    Only a clean re-walk through the boundary component signals
    ``reenter_boundary=True``.
    """
    components = state.chain.components
    end_idx = components.index(boundary_component)
    # Invariant (contract decision 7a, downstream-invalidation guard): a boundary
    # pause means nothing beyond it ran, so no completed component may sit after
    # the boundary. Assert rather than handle.
    for component in completed_components:
        if component in components and components.index(component) > end_idx:
            raise AssertionError(
                f"segment re-entry invariant violated: completed component {component!r} "
                f"is downstream of boundary {boundary_component!r}"
            )
    segment = _segment_components(
        state.chain,
        segment_start=segment_start,
        boundary_component=boundary_component,
        completed_components=completed_components,
    )
    steps_by_component = {step.component: step for step in state.chain.steps}

    last_check_in_payload: dict[str, Any] | None = None
    most_recent_attempted_run_id: uuid.UUID | None = None
    for component in segment:
        step = steps_by_component[component]
        upstream_state = {"successful_run_ids": dict(successful_runs)}
        base_directive = leg_directive(state.plan, step, upstream_state)
        amendment = directive_deltas.get(component)
        directive_delta = (
            _merge_amendment(base_directive, amendment) if amendment else base_directive
        )
        reference_kwargs = _reference_kwargs(component, successful_runs)
        retry_cap = COMPONENT_RETRY_CAP if component in LLM_BEARING_COMPONENTS else 0

        attempts: list[_AttemptOutcome] = []
        for attempt_index in range(retry_cap + 1):
            attempt = _run_step_attempt(
                engine,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                plan=state.plan,
                plan_id=state.plan_id,
                plan_version=state.plan_version,
                step=step,
                directive_delta=directive_delta,
                reference_kwargs=reference_kwargs,
                backends=backends,
                session_id=session_id,
                capability_run_id=capability_run_id,
            )
            attempts.append(attempt)
            most_recent_attempted_run_id = attempt.run_id
            if attempt.status == "succeeded":
                break
            if attempt_index < retry_cap:
                flagged_events.append(
                    {
                        "component": component,
                        "status": "retrying",
                        "run_id": str(attempt.run_id),
                        "reason": attempt.error,
                    }
                )

        final_attempt = attempts[-1]
        retried = len(attempts) > 1
        attempt_run_ids = [attempt.run_id for attempt in attempts]
        if final_attempt.status == "succeeded":
            successful_runs[component] = final_attempt.run_id
            outcome = RunStepOutcome(
                component=component,
                run_id=final_attempt.run_id,
                status="succeeded",
                wall_clock_s=final_attempt.wall_clock_s,
                retried=retried,
                attempt_run_ids=attempt_run_ids,
            )
            step_outcomes.append(outcome)
            if retried:
                flagged_events.append(
                    {
                        "component": component,
                        "status": "retried",
                        "run_id": str(final_attempt.run_id),
                    }
                )
            last_check_in_payload = _check_in(
                io, outcome, headline_counts=final_attempt.headline_counts
            )
            continue

        # Mid-segment failure — honest degrade; the boundary is not re-entered.
        reason = final_attempt.error or f"{component} re-walk failed"
        outcome = RunStepOutcome(
            component=component,
            run_id=final_attempt.run_id,
            status="failed",
            wall_clock_s=final_attempt.wall_clock_s,
            retried=retried,
            reason=reason,
            attempt_run_ids=attempt_run_ids,
        )
        step_outcomes.append(outcome)
        flagged_events.append(
            {
                "component": component,
                "status": "failed",
                "run_id": str(final_attempt.run_id),
                "reason": reason,
            }
        )
        last_check_in_payload = _check_in(
            io, outcome, headline_counts=final_attempt.headline_counts
        )
        if component in SPINE_COMPONENTS:
            # Spine failure ends the run (run_plan's spine-failure semantics).
            return _SegmentReentryResult(
                last_check_in_payload=last_check_in_payload,
                most_recent_attempted_run_id=most_recent_attempted_run_id,
                reenter_boundary=False,
                run_failed=True,
            )
        # Discretionary failure: un-thread and block so downstream dependents skip.
        successful_runs.pop(component, None)
        blocked_discretionary[component] = reason
        return _SegmentReentryResult(
            last_check_in_payload=last_check_in_payload,
            most_recent_attempted_run_id=most_recent_attempted_run_id,
            reenter_boundary=False,
            run_failed=False,
        )

    return _SegmentReentryResult(
        last_check_in_payload=last_check_in_payload,
        most_recent_attempted_run_id=most_recent_attempted_run_id,
        reenter_boundary=True,
        run_failed=False,
    )


@dataclass(frozen=True)
class _PlanSegmentReentryResult:
    """Result of running a segment re-walk plus its single boundary re-presentation.

    Args:
        state: The steering state after the re-walk and re-presentation.
        last_check_in_payload: Most recent check-in payload, or ``None``.
        most_recent_attempted_run_id: Most recent attempted run id, or ``None``.
        run_status: A terminal status (``failed``/``aborted``) that ends the run,
            or ``None`` to continue the outer walk past the boundary.
    """

    state: _SteeringState
    last_check_in_payload: dict[str, Any] | None
    most_recent_attempted_run_id: uuid.UUID | None
    run_status: RunPlanStatus | None


def _run_plan_segment_reentry(
    engine: Engine,
    io: CheckInIO,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    boundary_step: ComponentStep,
    segment_reentry: dict[str, Any],
    state: _SteeringState,
    backends: RunnerBackends,
    session_id: uuid.UUID | None,
    successful_runs: dict[str, uuid.UUID],
    blocked_discretionary: dict[str, str],
    completed_components: set[str],
    step_outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    capability_run_id: uuid.UUID,
) -> _PlanSegmentReentryResult:
    """Run the additive re-walk, then re-present the boundary once (one cycle).

    Drives :func:`_run_segment_reentry`; on a clean re-walk it re-presents the
    boundary pause exactly once with segment re-entry disallowed (the one
    re-entry cycle per boundary rule), handling Abort/Adjust/replacement-rerun on
    that re-presentation. A spine failure mid-segment ends the run without any
    re-presentation.
    """
    boundary_component = segment_reentry["boundary_component"]
    result = _run_segment_reentry(
        engine,
        io,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        state=state,
        segment_start=segment_reentry["segment_start"],
        boundary_component=boundary_component,
        directive_deltas=segment_reentry["directive_deltas"],
        backends=backends,
        session_id=session_id,
        successful_runs=successful_runs,
        blocked_discretionary=blocked_discretionary,
        completed_components=completed_components,
        step_outcomes=step_outcomes,
        flagged_events=flagged_events,
        capability_run_id=capability_run_id,
    )
    last_check_in_payload = result.last_check_in_payload
    most_recent_attempted_run_id = result.most_recent_attempted_run_id
    if result.run_failed:
        return _PlanSegmentReentryResult(
            state=state,
            last_check_in_payload=last_check_in_payload,
            most_recent_attempted_run_id=most_recent_attempted_run_id,
            run_status="failed",
        )
    if not result.reenter_boundary or last_check_in_payload is None:
        return _PlanSegmentReentryResult(
            state=state,
            last_check_in_payload=last_check_in_payload,
            most_recent_attempted_run_id=most_recent_attempted_run_id,
            run_status=None,
        )

    # Re-present the boundary ONCE, segment re-entry withheld (one cycle rule).
    reentry = _handle_after_component_boundary(
        engine,
        io,
        step=boundary_step,
        render=render_check_in(last_check_in_payload),
        state=state,
        project_id=project_id,
        completed_components=completed_components,
        flagged_events=flagged_events,
        capability_run_id=capability_run_id,
        most_recent_attempted_run_id=most_recent_attempted_run_id,
        boundary_run_id=successful_runs.get(boundary_component),
        selection_run_id=(
            successful_runs.get("select") if boundary_component == "select" else None
        ),
        allow_segment_reentry=False,
    )
    state = reentry.state
    if reentry.aborted:
        return _PlanSegmentReentryResult(
            state=state,
            last_check_in_payload=last_check_in_payload,
            most_recent_attempted_run_id=most_recent_attempted_run_id,
            run_status="aborted",
        )
    if reentry.rerun is not None:
        last_check_in_payload, most_recent_attempted_run_id = _run_component_rerun(
            engine,
            io,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            state=state,
            component=reentry.rerun["component"],
            directive_delta=reentry.rerun["directive"],
            backends=backends,
            session_id=session_id,
            successful_runs=successful_runs,
            blocked_discretionary=blocked_discretionary,
            step_outcomes=step_outcomes,
            flagged_events=flagged_events,
            capability_run_id=capability_run_id,
        )
    return _PlanSegmentReentryResult(
        state=state,
        last_check_in_payload=last_check_in_payload,
        most_recent_attempted_run_id=most_recent_attempted_run_id,
        run_status=None,
    )


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


def _open_capability_run(
    engine: Engine,
    *,
    capability_run_id: uuid.UUID,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    plan_id: uuid.UUID,
    plan_version: int,
    session_id: uuid.UUID | None,
) -> None:
    """Open the walk-identity row before the step loop (contract decision 2)."""
    with engine.begin() as conn:
        conn.execute(
            capability_run.insert().values(
                capability_run_id=capability_run_id,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                capability="evidence_base",
                plan_id=plan_id,
                plan_version=plan_version,
                status="running",
                session_id=session_id,
                started_at=datetime.now(UTC),
            )
        )


def _finish_run(
    engine: Engine,
    outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    *,
    status: RunPlanStatus,
    capability_run_id: uuid.UUID,
    project_id: uuid.UUID,
) -> RunPlanOutcome:
    with engine.begin() as conn:
        conn.execute(
            capability_run.update()
            .where(capability_run.c.capability_run_id == capability_run_id)
            .where(capability_run.c.project_id == project_id)
            .values(status=status, ended_at=datetime.now(UTC))
        )
    collation = render_collation(flagged_events)
    log.info("runner.collation", render=collation)
    _log_run_summary(outcomes, status=status)
    return RunPlanOutcome(
        status=status,
        steps=outcomes,
        flagged_events=flagged_events,
        collation_render=collation,
        capability_run_id=capability_run_id,
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
    capability_run_id: uuid.UUID,
) -> _AttemptOutcome:
    registry_component = registry_component_for(step.component)
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
                capability_run_id=capability_run_id,
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
                    finding_vetter_backend=backends.finding_vetter,
                    icf_extraction_backend=backends.icf_extraction,
                    icf_finding_vetter_backend=backends.icf_finding_vetter,
                    group_clustering_backend=backends.group_clustering,
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


def _find_component_payload(
    log_entries: list[dict[str, Any]],
    registry_component: str,
    *,
    event_type: str,
    run_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Last-matching payload for one run/component/event_type triple, or ``None``."""
    return next(
        (
            entry["payload"]
            for entry in reversed(log_entries)
            if entry["event_type"] == event_type
            and entry["run_id"] == run_id
            and entry["payload"].get("component") == registry_component
        ),
        None,
    )


def _headline_counts(
    log_entries: list[dict[str, Any]],
    registry_component: str,
    *,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    payload = _find_component_payload(
        log_entries, registry_component, event_type="component.completed", run_id=run_id
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
    payload = _find_component_payload(
        log_entries, registry_component, event_type="component.completed", run_id=run_id
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
    payload = _find_component_payload(
        log_entries, registry_component, event_type="component.failed", run_id=run_id
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
