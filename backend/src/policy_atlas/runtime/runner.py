"""EB capability-runner for executing approved orchestration plans.

The runner is the deterministic sub-agent boundary for task 017: it walks a
composed orchestration plan, owns per-component commits, applies component
directive deltas to the scope context, and delegates one component at a time to
the existing harness.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast, runtime_checkable

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
from policy_atlas.core.usage import UsageAccumulator
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
from policy_atlas.evidence_base.sourcing.search_loop import (
    DEPTH_CONSTANTS,
    THIN_CONFIDENT_RELEVANT,
    confident_relevant_count,
    count_existing_rounds,
    docs_screened_from_payload,
    evaluate_deep_stop,
    finalise_deep_stop,
    new_confident_relevant_for_run,
)
from policy_atlas.evidence_base.synthesis.grounding_judge import GroundingJudgeBackend
from policy_atlas.evidence_base.synthesis.synthesis_backend import (
    StubSynthesisBackend,
    SynthesisBackend,
)
from policy_atlas.evidence_base.synthesis.synthesis_tools import (
    DIRECTIVE_SECTION_TEXT_MAX,
    SECTION_CAP,
)
from policy_atlas.evidence_base.synthesis.synthesise import (
    SynthesiseContext,
    write_summaries_after_commit,
)
from policy_atlas.runtime import steering_events
from policy_atlas.runtime.continuation_state import ContinuationState, ResumeDecision
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.orchestration_plan import (
    SPINE,
    ComponentStep,
    ComposedChain,
    OrchestrationPlan,
    compose,
    registry_component_for,
)
from policy_atlas.runtime.orchestrator_backend import (
    OrchestratorBackend,
    build_watch_discretion_hook,
    classify_boundary,
    run_watch_decision,
)
from policy_atlas.runtime.orchestrator_prompt import WATCH_AUTHORING_PROMPT_VERSION
from policy_atlas.runtime.progress import ProgressEmitter
from policy_atlas.runtime.run_spec import Plan, compile
from policy_atlas.runtime.steering import (
    DEEPENING_SELECTION,
    EVIDENCE_BASE_COVERAGE,
    FINDING_GROUPS,
    SEARCH_EXCEPTION,
    SHIPPED_SEGMENT_START,
    SYNTHESIS_SHAPE,
    Abort,
    Adjust,
    CompiledFragment,
    Continue,
    FanOut,
    FreeText,
    PausePoint,
    ReEnterSegment,
    RerunSurface,
    SteeringAdjustmentError,
    SteeringDeltaInvalid,
    SteeringResponse,
    SteeringValidationCtx,
    apply_adjustment,
    apply_replacement_rerun,
    apply_segment_reentry,
    build_steer_point_options,
    commit_layer_overlay,
    compile_fanout,
    deep_merge_delta,
    generic_floor_options,
    lattice_name_for,
    lattice_policy,
    pause_points,
    render_authored_replacement_confirmation,
    render_check_in,
    render_collation,
    render_fanout_confirmation,
    render_refused_fragment,
    steer_point_triggers,
    validate_steering_delta,
)
from policy_atlas.runtime.steering_bundles import (
    groups_bundle,
    p1_bundle,
    p2_bundle,
    p3_bundle,
    p4_bundle,
)
from policy_atlas.runtime.steering_triggers import (
    FLOOR_BOUNDARY_FOR_COMPONENT,
    FloorBoundary,
    floor_triggers,
    grouping_flag_triggers,
    p1_coverage_triggers,
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

# Run-scoped replacement components (Task 15b): re-running any of these
# ADDITIVELY (a segment re-walk) is semantically wrong — their outputs are
# referenced downstream by one run id. A before_component segment re-entry is
# therefore only offered when none of these has completed (P2 qualifies — only
# the assess segment has run; P4 does not — select/extract/group all ran).
_REPLACEMENT_SCOPED = frozenset({"select", "extract", "group"})

RunPlanStatus = Literal["succeeded", "degraded", "failed", "aborted", "paused"]
StepStatus = Literal["succeeded", "failed", "skipped"]


class WalkParked(Exception):
    """Raised by a park-disposition IO at an attended pause.

    The walk thread ends; the durable pause record carries the boundary and an
    answer dispatches a boundary continuation walk.
    """


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
    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse: ...


@runtime_checkable
class _ConfirmCapable(Protocol):
    def confirm(self, render: str) -> bool: ...


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
    # Pending commit-layer overlays (task 024, 15c): per not-yet-run component,
    # a directive delta that validates but has no plan-field mapping (appraise
    # rubric, characterise themes/guidance, synthesise sections/boosts). Merged
    # over the component's composed directive when it executes so the run
    # actually consumes it; carried forward across plan-version transitions.
    pending_overlays: dict[str, dict[str, Any]] = field(default_factory=dict)


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
class _WatchObservation:
    """What the gated watch observed at one boundary (FIX 2).

    Args:
        authored_options: Watch-authored decision-point options (or ``None`` when
            the watch triaged, authoring failed, or no orchestrator ran).
        promoted: Whether a triage verdict PROMOTED — the m6 rule; an attended
            non-decision boundary then escalates to a generic-floor pause.
        promoted_reason: The triage's reason, surfaced in the escalation render.
        bundle: The P2/P3/P4 decision-point bundle the watch built for authoring,
            threaded back so the pause reuses it (FIX 2b — built once per boundary).
    """

    authored_options: list[dict[str, Any]] | None = None
    promoted: bool = False
    promoted_reason: str | None = None
    bundle: dict[str, Any] | None = None


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


@dataclass(frozen=True)
class _DiscretionContext:
    """The boundary state a discretion decision is taken over (the watch seam).

    Passed to the injected discretion hook at an Unattended lattice boundary that
    has NO pinned standing rule. The deterministic floor ignores it and proceeds;
    the Phase-5 LLM watch (built later) reads it to author an in-loco decision.
    This is a read-only snapshot — the hook never mutates it.

    Args:
        steer_point: The lattice point name.
        boundary: ``after_component`` / ``before_component``.
        component: The component the boundary concerns.
        triggers: The fired floor triggers at this boundary (never suppressible —
            the watch can add to the floor, never remove from it).
        plan: The current orchestration plan.
        bundle: The pre-fetched decision bundle (P2/P3/P4), or ``None`` (Task 14 —
            the watch decides over the same option-complete state a pause shows).
        header: Orienting header — refined question, plan summary, mode, standing
            instructions (Task 14; empty for the deterministic floor).
        digest: Run-so-far digest — prior steering decisions (Task 14).
        read_tools: Allowlisted read-tool executors for the fallback loop, or
            ``None`` (Task 14). The deterministic floor ignores all four extras.
    """

    steer_point: str
    boundary: str
    component: str
    triggers: list[dict[str, Any]]
    plan: OrchestrationPlan
    bundle: dict[str, Any] | None = None
    header: dict[str, Any] = field(default_factory=dict)
    digest: dict[str, Any] = field(default_factory=dict)
    read_tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None


@dataclass(frozen=True)
class _DiscretionOutcome:
    """A discretion decision for a no-pinned-rule Unattended boundary.

    The shipped deterministic floor always returns proceed / ``unconfigured_default``
    (the loudest flag class). A future watch hook returns the same shape carrying
    its in-loco decision; Task 12 builds only the floor.

    Args:
        interpreted_action: The action taken — ``"proceed"`` for the floor, or
            ``"apply"`` when the watch authored a delta to apply (Task 14).
        rule: The flag/rule label — ``"unconfigured_default"`` for the floor,
            ``"orchestrator_decision"``/``"orchestrator_escalation"`` for the watch.
        delta: The watch-authored directive delta to apply (``interpreted_action``
            ``"apply"`` only), or ``None``.
        component: Target component for an authored delta, or ``None``.
        rerun_mode: ``additive``/``replacement``/``None`` for an authored action.
        reasoning: The watch's verbatim reasoning for the record, or ``None``.
        deliberation: The read-tool deliberation trail (``{tool, args_digest,
            result_digest}`` steps) evented on the decision, or empty.
        profile: The watch execution profile (model, prompt version), or ``None``.
    """

    interpreted_action: str
    rule: str
    delta: dict[str, Any] | None = None
    component: str | None = None
    rerun_mode: str | None = None
    reasoning: str | None = None
    deliberation: list[dict[str, Any]] = field(default_factory=list)
    profile: dict[str, Any] | None = None


# The Phase-5 watch plugs in here: a callable that, given the boundary snapshot,
# returns a discretion decision. Default = the deterministic floor (proceed +
# loudest flag). Threaded through run_plan so a test/watch can inject it; a
# pinned standing rule is resolved BEFORE the hook is ever consulted (authority
# order: declared rules > orchestrator).
DiscretionHook = Callable[[_DiscretionContext], _DiscretionOutcome]

UNCONFIGURED_DEFAULT_RULE = "unconfigured_default"


def _deterministic_discretion_floor(context: _DiscretionContext) -> _DiscretionOutcome:
    """The no-pinned-rule floor: proceed, flagged loudest (``unconfigured_default``)."""
    del context
    return _DiscretionOutcome(interpreted_action="proceed", rule=UNCONFIGURED_DEFAULT_RULE)


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


def _extend_overlays(
    existing: dict[str, dict[str, Any]],
    directive_deltas: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Fold commit-layer pending deltas into the overlay map (task 024, 15c).

    Only the commit-layer part of a delta is overlaid (:func:`commit_layer_overlay`):
    a pure commit-layer component whole, a mixed component's commit-layer keys only
    (extract refresh / relevance_emphasis; group granularity / guidance). The
    plan-mappable part (screening criteria, select budget, extract profiles, group
    facets) takes the existing plan path and is never overlaid (no double-apply).
    Repeat adjustments merge-over per key.

    Args:
        existing: The prior overlay map (not mutated).
        directive_deltas: The confirmed adjustment's per-component deltas.

    Returns:
        A new overlay map.
    """
    overlays = {component: dict(delta) for component, delta in existing.items()}
    for component, delta in directive_deltas.items():
        part = commit_layer_overlay(component, delta)
        if part:
            overlays[component] = deep_merge_delta(overlays.get(component, {}), part)
    return overlays


def _run_plan_impl(
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
    discretion_hook: DiscretionHook | None = None,
    orchestrator: OrchestratorBackend | None = None,
    resume_from: ContinuationState | None = None,
    resume_decision: ResumeDecision | None = None,
    park_context: dict[str, Any] | None = None,
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
        discretion_hook: Optional Unattended-mode discretion hook consulted only
            at a lattice boundary with NO pinned standing rule (the Phase-5 watch
            seam). ``None`` uses the deterministic floor (proceed +
            ``unconfigured_default``). A pinned rule is always resolved before the
            hook is consulted (authority order: declared rules > orchestrator).
            An explicit hook takes precedence over one derived from ``orchestrator``.
        orchestrator: Optional orchestrator backend (Task 14). ``None`` = no watch:
            today's deterministic behaviour, no LLM calls, no judgement events. When
            provided, the watch authors options at attended lattice pauses, triages
            anomalous/trigger-fired boundaries, decides in loco user at Unattended
            no-rule boundaries (via the discretion hook), and every boundary emits an
            ``agent_judgement_routed`` event (clean boundaries deterministically, no
            LLM). ANY backend exception degrades to the deterministic floor.

    Returns:
        Overall status, ordered step outcomes and collated flags.
    """
    backend_bundle = backends if backends is not None else RunnerBackends()
    io_sink = io if io is not None else NullIO()
    if discretion_hook is not None:
        discretion = discretion_hook
    elif orchestrator is not None:
        discretion = build_watch_discretion_hook(orchestrator, session_id=session_id)
    else:
        discretion = _deterministic_discretion_floor
    if resume_from is None:
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
        attempted_runs: dict[str, uuid.UUID] = {}
        blocked_discretionary: dict[str, str] = {}
        completed_components: set[str] = set()
        last_check_in_payload: dict[str, Any] | None = None
        most_recent_attempted_run_id: uuid.UUID | None = None
    else:
        capability_run_id = resume_from.capability_run_id
        session_id = resume_from.session_id
        steering_state = _SteeringState(
            plan=resume_from.plan,
            plan_id=resume_from.plan_id,
            plan_version=resume_from.plan_version,
            plan_row_id=resume_from.plan_row_id,
            chain=resume_from.chain,
            pause_points=resume_from.pause_points,
            pending_overlays=resume_from.pending_overlays,
        )
        step_outcomes = list(resume_from.step_outcomes)
        flagged_events = list(resume_from.flagged_events)
        successful_runs = dict(resume_from.successful_runs)
        attempted_runs = dict(resume_from.attempted_runs)
        blocked_discretionary = dict(resume_from.blocked_discretionary)
        completed_components = set(resume_from.completed_components)
        last_check_in_payload = resume_from.last_check_in_payload
        most_recent_attempted_run_id = resume_from.most_recent_attempted_run_id
        remaining_steps = _remaining_steps(
            steering_state.chain, completed_components=completed_components
        )
        if resume_decision is None:
            raise ValueError("resume_decision is required with resume_from")
    # The most-recent ATTEMPTED run id per registry component, INCLUDING failed
    # attempts (FIX 1): un-blinds class 9 (downstream_capability_reduced), which
    # scans the walk's attempted run ids for component.failed/skipped events — a
    # failed run is never threaded into ``successful_runs`` (it is popped), so the
    # floor would otherwise never see it. Keyed by registry component so the floor
    # readers' ``run_ids["screen"]`` etc. resolve (screen_abstract/screen_full both
    # register as ``"screen"``).
    if park_context is not None:
        park_context.update(
            capability_run_id=capability_run_id,
            project_id=project_id,
            step_outcomes=step_outcomes,
            flagged_events=flagged_events,
            # Snapshot, don't let the reducer re-derive: completed_components
            # drives remaining_steps (what re-executes after a park) — it gets
            # the same read-back treatment as step_outcomes/flagged_events
            # (G2 pattern; review finding adv-m4, 2026-07-21).
            completed_components=completed_components,
        )

    if resume_from is not None and resume_decision is not None:
        if resume_decision.response == "rerun":
            if resume_decision.component is None or resume_decision.directive_delta is None:
                raise ValueError("rerun continuation requires component and directive_delta")
            last_check_in_payload, most_recent_attempted_run_id = _run_component_rerun(
                engine,
                io_sink,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                state=steering_state,
                component=resume_decision.component,
                directive_delta=resume_decision.directive_delta,
                backends=backend_bundle,
                session_id=session_id,
                successful_runs=successful_runs,
                attempted_runs=attempted_runs,
                blocked_discretionary=blocked_discretionary,
                step_outcomes=step_outcomes,
                flagged_events=flagged_events,
                capability_run_id=capability_run_id,
            )
        elif resume_decision.response == "segment_reentry":
            if (
                resume_decision.component is None
                or resume_decision.segment_start is None
                or resume_decision.directive_deltas is None
                or resume_decision.boundary is None
            ):
                raise ValueError("segment continuation requires its complete boundary payload")
            boundary_step = next(
                step
                for step in steering_state.chain.steps
                if step.component == resume_decision.component
            )
            segment_reentry = {
                "segment_start": resume_decision.segment_start,
                "boundary_component": resume_decision.component,
                "directive_deltas": resume_decision.directive_deltas,
            }
            if resume_decision.boundary == "after_component":
                segment_result = _run_plan_segment_reentry(
                    engine,
                    io_sink,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    boundary_step=boundary_step,
                    segment_reentry=segment_reentry,
                    state=steering_state,
                    backends=backend_bundle,
                    session_id=session_id,
                    successful_runs=successful_runs,
                    attempted_runs=attempted_runs,
                    blocked_discretionary=blocked_discretionary,
                    completed_components=completed_components,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                    capability_run_id=capability_run_id,
                )
            else:
                segment_result = _run_plan_before_segment_reentry(
                    engine,
                    io_sink,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    boundary_step=boundary_step,
                    segment_reentry=segment_reentry,
                    state=steering_state,
                    backends=backend_bundle,
                    session_id=session_id,
                    successful_runs=successful_runs,
                    attempted_runs=attempted_runs,
                    blocked_discretionary=blocked_discretionary,
                    completed_components=completed_components,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                    capability_run_id=capability_run_id,
                    orchestrator=orchestrator,
                    discretion_hook=discretion,
                )
            steering_state = segment_result.state
            last_check_in_payload = segment_result.last_check_in_payload
            most_recent_attempted_run_id = segment_result.most_recent_attempted_run_id
            if segment_result.run_status is not None:
                return _finish_run(
                    engine,
                    step_outcomes,
                    flagged_events,
                    status=segment_result.run_status,
                    capability_run_id=capability_run_id,
                    project_id=project_id,
                )
        elif (
            resume_decision.response in {"continue", "adjust", "mode_change"}
            and resume_from.parked_boundary == "before_component"
            and remaining_steps
            and remaining_steps[0].component == resume_from.parked_component
        ):
            # The parked before-boundary was decided by the recorded steering.decision;
            # re-presenting it re-asks a decided question (live-path parity — a continue
            # at a before-boundary runs the step).
            last_check_in_payload = None

    while remaining_steps:
        step = remaining_steps.pop(0)
        # Multi-round search gate (task 029): the walk is about to leave the
        # acquire→screen_abstract pair for the first post-screen component.
        # Standard/deep repeat the pair until the depth's round_cap or a yield
        # collapse; re-opening the two components hands the next round to the
        # ordinary step machinery (fresh run rows, boundaries, check-ins, SSE).
        # Gating on the classify pop — the fixed successor in every composed
        # chain — makes the check stateless and park/resume-safe: a resumed
        # walk re-derives everything from coverage rows and screen provenance.
        if (
            step.component == "classify"
            and steering_state.plan.search_effort in ("standard", "deep")
            and "screen_abstract" in completed_components
            and _search_round_continues(
                engine,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                plan=steering_state.plan,
                successful_runs=successful_runs,
            )
        ):
            completed_components.discard("acquire")
            completed_components.discard("screen_abstract")
            remaining_steps = _remaining_steps(
                steering_state.chain,
                completed_components=completed_components,
            )
            continue
        if last_check_in_payload is not None:
            pause_result = _handle_before_component_boundary(
                engine,
                io_sink,
                step=step,
                render=render_check_in(last_check_in_payload),
                state=steering_state,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                successful_runs=successful_runs,
                backends=backend_bundle,
                completed_components=completed_components,
                capability_run_id=capability_run_id,
                most_recent_attempted_run_id=most_recent_attempted_run_id,
                attempted_runs=attempted_runs,
                flagged_events=flagged_events,
                discretion_hook=discretion,
                orchestrator=orchestrator,
                session_id=session_id,
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
            # P2/P4 re-runs steered at a before_component boundary execute here,
            # then the walk falls through to run the pending step referencing the
            # re-run's new run id (Task 15b). A replacement re-run re-threads the
            # reference and does not re-present; an additive P2 segment re-entry
            # re-walks acquire→last-completed and re-presents the SAME boundary
            # once (one cycle). The plan payload carries forward, so the pending
            # step and remaining tail stay valid — no chain recompute needed.
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
                    attempted_runs=attempted_runs,
                    blocked_discretionary=blocked_discretionary,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                    capability_run_id=capability_run_id,
                )
            elif pause_result.segment_reentry is not None:
                segment_result = _run_plan_before_segment_reentry(
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
                    attempted_runs=attempted_runs,
                    blocked_discretionary=blocked_discretionary,
                    completed_components=completed_components,
                    step_outcomes=step_outcomes,
                    flagged_events=flagged_events,
                    capability_run_id=capability_run_id,
                    orchestrator=orchestrator,
                    discretion_hook=discretion,
                )
                steering_state = segment_result.state
                if segment_result.last_check_in_payload is not None:
                    last_check_in_payload = segment_result.last_check_in_payload
                if segment_result.most_recent_attempted_run_id is not None:
                    most_recent_attempted_run_id = segment_result.most_recent_attempted_run_id
                if segment_result.run_status is not None:
                    return _finish_run(
                        engine,
                        step_outcomes,
                        flagged_events,
                        status=segment_result.run_status,
                        capability_run_id=capability_run_id,
                        project_id=project_id,
                    )
            elif pause_result.changed:
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
                evidence_scope_id=evidence_scope_id,
                successful_runs=successful_runs,
                backends=backend_bundle,
                completed_components=completed_components,
                flagged_events=flagged_events,
                capability_run_id=capability_run_id,
                most_recent_attempted_run_id=most_recent_attempted_run_id,
                attempted_runs=attempted_runs,
                boundary_run_id=None,
                discretion_hook=discretion,
                orchestrator=orchestrator,
                session_id=session_id,
                anomalous=True,
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
        # Fold a pending commit-layer overlay into this first-run directive so the
        # component consumes it (task 024, 15c). One-shot: re-runs (replacement /
        # segment re-walk) drive their own directive path and never come here.
        overlay = steering_state.pending_overlays.get(step.component)
        if overlay:
            directive_delta = deep_merge_delta(directive_delta, overlay)
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
                overlay=overlay,
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
        # Record the final attempted run (succeeded OR failed) so class 9 is never
        # blind to a discretionary failure that the walk continues past (FIX 1).
        attempted_runs[registry_component_for(step.component)] = final_attempt.run_id
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
                evidence_scope_id=evidence_scope_id,
                successful_runs=successful_runs,
                backends=backend_bundle,
                completed_components=completed_components,
                flagged_events=flagged_events,
                capability_run_id=capability_run_id,
                most_recent_attempted_run_id=most_recent_attempted_run_id,
                attempted_runs=attempted_runs,
                boundary_run_id=final_attempt.run_id,
                selection_run_id=(final_attempt.run_id if step.component == "select" else None),
                allow_segment_reentry=True,
                discretion_hook=discretion,
                orchestrator=orchestrator,
                session_id=session_id,
                anomalous=retried,
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
                    attempted_runs=attempted_runs,
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
                    attempted_runs=attempted_runs,
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
                    most_recent_attempted_run_id = segment_result.most_recent_attempted_run_id
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
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            backends=backend_bundle,
            completed_components=completed_components,
            flagged_events=flagged_events,
            capability_run_id=capability_run_id,
            most_recent_attempted_run_id=most_recent_attempted_run_id,
            attempted_runs=attempted_runs,
            boundary_run_id=final_attempt.run_id,
            discretion_hook=discretion,
            orchestrator=orchestrator,
            session_id=session_id,
            anomalous=True,
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
    discretion_hook: DiscretionHook | None = None,
    orchestrator: OrchestratorBackend | None = None,
    resume_from: ContinuationState | None = None,
    resume_decision: ResumeDecision | None = None,
) -> RunPlanOutcome:
    """Execute or resume an approved orchestration-plan walk.

    A park-disposition IO raises :class:`WalkParked`. This single boundary
    converts that control flow into the durable paused state and snapshot; the
    normal blocking CLI path never raises and is otherwise unchanged.

    Args:
        engine: SQLAlchemy engine used by the walk.
        project_id: Owning project.
        evidence_scope_id: Evidence scope executed by components.
        plan: Approved plan for a new walk (ignored for durable resume state).
        plan_id: Current plan id for a new walk.
        plan_version: Current plan version for a new walk.
        plan_row_id: Current plan row for amendment persistence.
        backends: Optional component backend seams.
        io: Optional check-in and pause IO seam.
        session_id: Optional tracing session id.
        discretion_hook: Optional unattended discretion seam.
        orchestrator: Optional watch backend.
        resume_from: Durable state of a previously parked capability run.
        resume_decision: Persisted answer to apply before resuming.

    Returns:
        The completed, aborted, or parked plan outcome.
    """
    park_context: dict[str, Any] = {}
    try:
        return _run_plan_impl(
            engine,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            plan=plan,
            plan_id=plan_id,
            plan_version=plan_version,
            plan_row_id=plan_row_id,
            backends=backends,
            io=io,
            session_id=session_id,
            discretion_hook=discretion_hook,
            orchestrator=orchestrator,
            resume_from=resume_from,
            resume_decision=resume_decision,
            park_context=park_context,
        )
    except WalkParked:
        capability_run_id = park_context["capability_run_id"]
        step_outcomes = park_context["step_outcomes"]
        flagged_events = park_context["flagged_events"]
        _park_capability_run(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            step_outcomes=step_outcomes,
            flagged_events=flagged_events,
            completed_components=sorted(park_context.get("completed_components", ())),
        )
        return RunPlanOutcome(
            status="paused",
            steps=step_outcomes,
            flagged_events=flagged_events,
            capability_run_id=capability_run_id,
        )


def _park_capability_run(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    step_outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    completed_components: list[str],
) -> uuid.UUID:
    """Atomically mark a parked walk and snapshot parity-sensitive state."""
    with engine.begin() as conn:
        pause_rows = conn.execute(
            select(event_log)
            .where(event_log.c.project_id == project_id)
            .where(event_log.c.event_type == steering_events.STEERING_PAUSE)
            .order_by(event_log.c.sequence.desc())
        )
        attachment_run_id = next(
            (
                row.run_id
                for row in pause_rows
                if isinstance(row.payload, dict)
                and row.payload.get("capability_run_id") == str(capability_run_id)
            ),
            None,
        )
        if attachment_run_id is None:
            raise AssertionError("parked walk has no attached steering.pause event")
        conn.execute(
            capability_run.update()
            .where(capability_run.c.capability_run_id == capability_run_id)
            .where(capability_run.c.project_id == project_id)
            .values(status="paused")
        )
        events.append(
            conn,
            project_id=project_id,
            run_id=attachment_run_id,
            event_type="run.parked",
            payload={
                "capability_run_id": str(capability_run_id),
                "flagged_events": flagged_events,
                "step_outcomes": [_serialise_step_outcome(outcome) for outcome in step_outcomes],
                "completed_components": completed_components,
            },
        )
    if not isinstance(attachment_run_id, uuid.UUID):
        raise AssertionError("parked pause attachment must be a UUID")
    return attachment_run_id


def _serialise_step_outcome(outcome: RunStepOutcome) -> dict[str, Any]:
    """Return the JSONB representation of a step outcome snapshot."""
    return {
        "component": outcome.component,
        "run_id": str(outcome.run_id) if outcome.run_id is not None else None,
        "status": outcome.status,
        "wall_clock_s": outcome.wall_clock_s,
        "retried": outcome.retried,
        "skipped": outcome.skipped,
        "reason": outcome.reason,
        "attempt_run_ids": [str(run_id) for run_id in outcome.attempt_run_ids],
    }


def _after_boundary_rerun_component(
    steer_point_name: str | None,
    *,
    selection_run_id: uuid.UUID | None,
    successful_runs: dict[str, uuid.UUID],
) -> str | None:
    """The replacement re-run an after-boundary steer point wires from its pause.

    P3 re-runs select; the finding-groups point re-runs group (its regroup floor
    options are dead without this — review 028 M1). Either requires a persisted
    run to replace; a failed component degrades the point instead (caller).
    """
    if steer_point_name == DEEPENING_SELECTION and selection_run_id is not None:
        return "select"
    if steer_point_name == FINDING_GROUPS and successful_runs.get("group") is not None:
        return "group"
    return None


def _handle_after_component_boundary(
    engine: Engine,
    io: CheckInIO,
    *,
    step: ComponentStep,
    render: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    backends: RunnerBackends,
    completed_components: set[str],
    flagged_events: list[dict[str, Any]],
    capability_run_id: uuid.UUID,
    most_recent_attempted_run_id: uuid.UUID | None,
    boundary_run_id: uuid.UUID | None,
    attempted_runs: dict[str, uuid.UUID] | None = None,
    selection_run_id: uuid.UUID | None = None,
    allow_segment_reentry: bool = False,
    discretion_hook: DiscretionHook = _deterministic_discretion_floor,
    orchestrator: OrchestratorBackend | None = None,
    session_id: uuid.UUID | None = None,
    anomalous: bool = False,
) -> _PauseApplied:
    point = PausePoint("after_component", step.component)
    floor_run_ids = (
        attempted_runs if attempted_runs is not None else _registry_run_ids(successful_runs)
    )
    # Unattended = discretion-is-the-mode: at every lattice boundary the walk
    # never pauses — a pinned standing rule decides, else the discretion floor
    # (Task 12). Reuses the lattice detection; select's P3 replacement re-run and
    # additive segment re-entry are applied through the same machinery a pause
    # would use.
    name = lattice_name_for(point)
    if state.plan.steering_mode == "unattended" and name is not None:
        return _resolve_unattended_boundary(
            engine,
            point=point,
            name=name,
            state=state,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            attempted_runs=floor_run_ids,
            completed_components=completed_components,
            flagged_events=flagged_events,
            capability_run_id=capability_run_id,
            event_run_id=(
                boundary_run_id if boundary_run_id is not None else most_recent_attempted_run_id
            ),
            selection_run_id=selection_run_id,
            allow_segment_reentry=allow_segment_reentry,
            rerun_component=_after_boundary_rerun_component(
                name, selection_run_id=selection_run_id, successful_runs=successful_runs
            ),
            discretion_hook=discretion_hook,
            backends=backends,
        )

    should_pause, steer_point_name, triggers = _evaluate_boundary(
        engine,
        point=point,
        state=state,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        attempted_runs=floor_run_ids,
    )
    # The deepening-selection (P3) steer point only offers its bundle/re-run when
    # select actually produced a persisted selection; a failed select degrades to
    # a generic check-in pause (the pre-024 behaviour). The finding-groups point
    # degrades the same way when group has no persisted run to re-run.
    if steer_point_name == DEEPENING_SELECTION and selection_run_id is None:
        steer_point_name = None
        triggers = None
    if steer_point_name == FINDING_GROUPS and successful_runs.get("group") is None:
        steer_point_name = None
        triggers = None
    # Run-id attachment (plan pin, review M2): an after_component event attaches
    # to the run it is about; a skipped component has no run of its own, so it
    # falls back to the most-recent attempted run id.
    event_run_id = boundary_run_id if boundary_run_id is not None else most_recent_attempted_run_id
    # Gated watch invocation (Task 14): the watch observes EVERY attended boundary
    # — authoring at a decision-point pause, triaging an anomalous/trigger-fired
    # boundary, or emitting a deterministic clean_boundary event. No orchestrator =
    # no watch = today's behaviour (no judgement events).
    observation = _WatchObservation()
    if orchestrator is not None and event_run_id is not None:
        observation = _watch_observe_boundary(
            engine,
            orchestrator=orchestrator,
            point=point,
            state=state,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            backends=backends,
            capability_run_id=capability_run_id,
            event_run_id=event_run_id,
            steer_point_name=steer_point_name,
            triggers=triggers or [],
            is_decision_point=should_pause and steer_point_name is not None,
            anomalous=anomalous,
        )
    authored_options = observation.authored_options
    # FIX 2: a watch triage that PROMOTES escalates an otherwise-non-pausing
    # attended boundary to a generic-floor pause (the m6 rule / "watch-escalated
    # substance"). Unattended never pauses (mode table), so a promotion there is
    # recorded only. A promotion cannot add a pause where one already happens.
    promoted_escalation = (
        observation.promoted and not should_pause and state.plan.steering_mode != "unattended"
    )
    if not should_pause and not promoted_escalation:
        # FIX 1: a fired non-lattice floor trigger that did not pause (Unattended)
        # still flows to the collation so review sees it (the floor is never silent).
        if triggers:
            flagged_events.append(_trigger_fired_flag(point, triggers))
        return _PauseApplied(state=state)
    if promoted_escalation:
        # A promoted lattice boundary keeps its identity: its canonical floor
        # and bundle are the actual decision surface, not a generic substitute.
        render = f"{render}\nThe orchestrator flagged this boundary: {observation.promoted_reason}"
    options, bundle = _pause_options_and_bundle(
        engine,
        steer_point_name=steer_point_name,
        state=state,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        backends=backends,
        triggers=triggers,
        prebuilt_bundle=observation.bundle,
    )
    # The P3 select and FG group steer points wire a replacement re-run from
    # their pause (their floors offer re-run options at an after-boundary);
    # P2/P4 sit at before-boundaries and get theirs from
    # :func:`_before_boundary_surface`.
    rerun_component = _after_boundary_rerun_component(
        steer_point_name, selection_run_id=selection_run_id, successful_runs=successful_runs
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
        steer_point_name=steer_point_name,
        options=options,
        bundle=bundle,
        triggers=triggers,
        rerun_component=rerun_component,
        segment_reentry_allowed=segment_reentry_allowed,
        authored_options=authored_options,
        orchestrator=orchestrator,
        session_id=session_id,
    )


def _before_boundary_surface(
    state: _SteeringState,
    completed_components: set[str],
    *,
    allow_segment_reentry: bool,
) -> tuple[str | None, bool]:
    """The re-run surface a before_component boundary offers (Task 15b).

    Returns ``(replacement_component, segment_reentry_allowed)``. The replacement
    component is the last-completed component that is a replacement re-run target
    (characterise at P2 before select; group at P4 before synthesise) with its
    upstream reference satisfied — mirroring the point's canonical re-run option.
    Additive segment re-entry is offered only when acquire has completed and no
    run-scoped component (select/extract/group) has — so P2 qualifies and P4 does
    not (a P4 re-walk would additively re-run replacement-scoped outputs).

    Args:
        state: Current steering state (chain order).
        completed_components: Components whose boundary has passed.
        allow_segment_reentry: Caller gate (``False`` on a re-presentation to hold
            the one-cycle rule).
    """
    chain_index = {component: index for index, component in enumerate(state.chain.components)}
    completed_reruns = [
        component
        for component in completed_components
        if component in REPLACEMENT_RERUNS and component in chain_index
    ]
    replacement_component: str | None = (
        max(completed_reruns, key=lambda component: chain_index[component])
        if completed_reruns
        else None
    )
    if replacement_component is not None:
        upstream = REPLACEMENT_RERUNS[replacement_component].reference_upstream
        if upstream is not None and upstream not in completed_components:
            replacement_component = None
    segment_reentry_allowed = (
        allow_segment_reentry
        and SHIPPED_SEGMENT_START in completed_components
        and not (_REPLACEMENT_SCOPED & completed_components)
    )
    return replacement_component, segment_reentry_allowed


def _handle_before_component_boundary(
    engine: Engine,
    io: CheckInIO,
    *,
    step: ComponentStep,
    render: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    backends: RunnerBackends,
    completed_components: set[str],
    capability_run_id: uuid.UUID,
    most_recent_attempted_run_id: uuid.UUID | None,
    flagged_events: list[dict[str, Any]],
    attempted_runs: dict[str, uuid.UUID] | None = None,
    discretion_hook: DiscretionHook = _deterministic_discretion_floor,
    orchestrator: OrchestratorBackend | None = None,
    session_id: uuid.UUID | None = None,
    allow_segment_reentry: bool = True,
    anomalous: bool = False,
) -> _PauseApplied:
    """Evaluate a before-component boundary (P2 before select, P4 before synthesise).

    Before-lattice points carry a bundle/options/triggers exactly as after-points
    do, and (Task 15b) APPLY their canonical re-run surface: at P2 a re-characterise
    replacement re-run or an additive segment re-entry (re-search / criteria
    re-screen), at P4 a re-group replacement re-run. A not-yet-run component
    adjustment (P4 synthesis section edits / boosts) still applies through the
    generic pending-component path. Segment re-entry is refused at P4 (the re-walk
    would re-run replacement-scoped outputs).

    In Unattended mode the point never pauses: a pinned standing rule decides
    (hard stop honoured; the point's re-run surface applied through the same
    machinery), else the discretion floor (Task 12).
    """
    point = PausePoint("before_component", step.component)
    floor_run_ids = (
        attempted_runs if attempted_runs is not None else _registry_run_ids(successful_runs)
    )
    name = lattice_name_for(point)
    rerun_component, segment_reentry_allowed = _before_boundary_surface(
        state, completed_components, allow_segment_reentry=allow_segment_reentry
    )
    if state.plan.steering_mode == "unattended" and name is not None:
        return _resolve_unattended_boundary(
            engine,
            point=point,
            name=name,
            state=state,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            attempted_runs=floor_run_ids,
            completed_components=completed_components,
            flagged_events=flagged_events,
            capability_run_id=capability_run_id,
            event_run_id=most_recent_attempted_run_id,
            selection_run_id=None,
            allow_segment_reentry=segment_reentry_allowed,
            rerun_component=rerun_component,
            discretion_hook=discretion_hook,
            backends=backends,
        )
    should_pause, steer_point_name, triggers = _evaluate_boundary(
        engine,
        point=point,
        state=state,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        attempted_runs=floor_run_ids,
    )
    observation = _WatchObservation()
    if orchestrator is not None and most_recent_attempted_run_id is not None:
        observation = _watch_observe_boundary(
            engine,
            orchestrator=orchestrator,
            point=point,
            state=state,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            backends=backends,
            capability_run_id=capability_run_id,
            event_run_id=most_recent_attempted_run_id,
            steer_point_name=steer_point_name,
            triggers=triggers or [],
            is_decision_point=should_pause and steer_point_name is not None,
            anomalous=anomalous,
        )
    authored_options = observation.authored_options
    promoted_escalation = (
        observation.promoted and not should_pause and state.plan.steering_mode != "unattended"
    )
    if not should_pause and not promoted_escalation:
        if triggers:
            flagged_events.append(_trigger_fired_flag(point, triggers))
        return _PauseApplied(state=state)
    if promoted_escalation:
        render = f"{render}\nThe orchestrator flagged this boundary: {observation.promoted_reason}"
    options, bundle = _pause_options_and_bundle(
        engine,
        steer_point_name=steer_point_name,
        state=state,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        backends=backends,
        triggers=triggers,
        prebuilt_bundle=observation.bundle,
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
        event_run_id=most_recent_attempted_run_id,
        steer_point_name=steer_point_name,
        options=options,
        bundle=bundle,
        triggers=triggers,
        rerun_component=rerun_component,
        segment_reentry_allowed=segment_reentry_allowed,
        authored_options=authored_options,
        orchestrator=orchestrator,
        session_id=session_id,
    )


def _registry_run_ids(runs: dict[str, uuid.UUID]) -> dict[str, uuid.UUID]:
    """Re-key a component→run map by registry component (screen_abstract → screen).

    The floor readers address a boundary's own run by registry name
    (``run_ids["screen"]``); ``successful_runs`` is keyed by composed-step name, so
    a screen run lives under ``screen_abstract``/``screen_full``. Used as the
    attempted-run fallback at the re-walk re-presentation call sites, which do not
    thread the main loop's ``attempted_runs`` map.
    """
    return {registry_component_for(component): run_id for component, run_id in runs.items()}


def _floor_boundary_triggers(
    engine: Engine,
    *,
    boundary: FloorBoundary,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    attempted_runs: dict[str, uuid.UUID],
) -> list[dict[str, Any]]:
    """Read the floor triggers for one non-lattice after_component boundary (FIX 1).

    Threads the attempted-run map (including failed attempts) so class 9
    (downstream_capability_reduced) is un-blinded. Returns ``[]`` when the
    boundary's own run id is absent (e.g. a skipped discretionary component leaves
    no run to key on — the skip is caught as class 9 at a later boundary).
    """
    required = {"after_screen": "screen", "after_group": "group", "after_extract": "extract"}
    key = required.get(boundary)
    if key is not None and key not in attempted_runs:
        return []
    with engine.connect() as conn:
        return floor_triggers(
            conn,
            project_id=project_id,
            boundary_component=boundary,
            evidence_scope_id=evidence_scope_id,
            run_ids=dict(attempted_runs),
        )


def _evaluate_boundary(
    engine: Engine,
    *,
    point: PausePoint,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    attempted_runs: dict[str, uuid.UUID],
) -> tuple[bool, str | None, list[dict[str, Any]] | None]:
    """Decide whether a boundary pauses, per the annex mode table.

    Returns ``(should_pause, steer_point_name, triggers)``. A lattice point pauses
    on ``always`` or on ``fired`` with non-empty triggers (read through Task 10
    readers at the boundary, never recomputed); triggers are attached to the
    payload either way. A non-lattice after_component boundary that carries its own
    floor classes (:data:`FLOOR_BOUNDARY_FOR_COMPONENT`, FIX 1) reads them here:
    when they fire it pauses (attended) or flows them to the watch/collation only
    (Unattended), with no steer point. A boundary that fires nothing pauses only
    when it is a Frequent generic pause (present in the static pause set).
    """
    name = lattice_name_for(point)
    if name is not None:
        policy = lattice_policy(state.plan.steering_mode, name)
        if policy == "off":
            return (False, None, None)
        triggers = _lattice_triggers(
            engine,
            name=name,
            state=state,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            attempted_runs=attempted_runs,
        )
        if policy == "fired" and not triggers:
            return (False, name, triggers)
        return (True, name, triggers)
    # FIX 1: a non-lattice after_component boundary with its own floor classes.
    floor_boundary = FLOOR_BOUNDARY_FOR_COMPONENT.get(point.component)
    if point.boundary == "after_component" and floor_boundary is not None:
        floor = _floor_boundary_triggers(
            engine,
            boundary=floor_boundary,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            attempted_runs=attempted_runs,
        )
        if floor:
            # Unattended never pauses (mode table); the fired floor still flows to
            # the watch and the collation. Every attended mode pauses on the
            # generic non-lattice floor menu.
            if state.plan.steering_mode == "unattended":
                return (False, None, floor)
            return (True, None, floor)
    if point in state.pause_points:
        return (True, None, None)
    return (False, None, None)


def _lattice_triggers(
    engine: Engine,
    *,
    name: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    attempted_runs: dict[str, uuid.UUID],
) -> list[dict[str, Any]]:
    """Read a lattice point's floor triggers from persisted state (Task 10)."""
    with engine.connect() as conn:
        if name == SEARCH_EXCEPTION:
            acquire_run_id = successful_runs.get("acquire")
            if acquire_run_id is None:
                return []
            return p1_coverage_triggers(conn, project_id=project_id, acquire_run_id=acquire_run_id)
        if name == EVIDENCE_BASE_COVERAGE:
            return floor_triggers(
                conn,
                project_id=project_id,
                boundary_component="pre_select",
                evidence_scope_id=evidence_scope_id,
                run_ids=dict(attempted_runs),
            )
        if name == DEEPENING_SELECTION:
            selection_run_id = successful_runs.get("select")
            if selection_run_id is None:
                return []
            return steer_point_triggers(
                conn,
                project_id=project_id,
                selection_run_id=selection_run_id,
                plan=state.plan,
            )
        if name == FINDING_GROUPS:
            group_run_id = successful_runs.get("group")
            if group_run_id is None:
                return []
            return grouping_flag_triggers(conn, project_id=project_id, group_run_id=group_run_id)
    return []


def _pause_options_and_bundle(
    engine: Engine,
    *,
    steer_point_name: str | None,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    backends: RunnerBackends,
    triggers: list[dict[str, Any]] | None = None,
    prebuilt_bundle: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return the canonical options + (P2/P3/P4) bundle for a pause.

    A non-lattice boundary gets the generic floor and no bundle. A lattice pause
    gets its point-keyed canonical options and, at P2/P3/P4, its deterministic
    bundle. Bundle building is fail-safe: a build error degrades to no bundle
    (the watch/authoring fail-safe discipline) rather than failing the pause.

    FIX 2b: when the watch already built this boundary's bundle for authoring, it
    is threaded in as ``prebuilt_bundle`` and reused — the P2/P3/P4 bundle is built
    once per decision point, not once for authoring and again for the pause.
    """
    if steer_point_name is None:
        return generic_floor_options(), None
    options = build_steer_point_options(plan=state.plan, point=steer_point_name)
    if steer_point_name == SEARCH_EXCEPTION and triggers:
        for option in options:
            if option.get("id") == "deepen_search":
                option["label"] = "Search harder"
            if option.get("id") == "continue":
                option["label"] = "Continue with what came back"
                option["description"] = (
                    "Proceed with the available results; the report will flag what was incomplete."
                )
    bundle = (
        prebuilt_bundle
        if prebuilt_bundle is not None
        else _build_bundle(
            engine,
            name=steer_point_name,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            backends=backends,
            section_budget=state.plan.section_budget,
        )
    )
    if steer_point_name == SYNTHESIS_SHAPE and isinstance(bundle, dict):
        proposal = bundle.get("proposal")
        sections = proposal.get("proposed_sections") if isinstance(proposal, dict) else None
        if isinstance(sections, list):
            # The proposal's bounds exceed the steering directive's in three
            # ways, so the displayed-list submit could 422/fail on submit or at
            # execution: focus length (SECTION_FOCUS_MAX=300 vs
            # DIRECTIVE_SECTION_TEXT_MAX=200, found live, 028 G.2), section
            # count (the budget clause is prompt-advisory, review 028 m1), and
            # the section→group bindings the directive grammar carries as
            # `group_ids` (dropping them silently unscoped grouped deep runs,
            # review 028 M2). Clamp ONCE here — in the bundle the card displays
            # AND the as_proposed delta — so displayed == submitted == valid
            # == executed.
            section_bound = state.plan.section_budget or SECTION_CAP
            clamped = []
            for row in sections[:section_bound]:
                if (
                    not isinstance(row, dict)
                    or not isinstance(row.get("title"), str)
                    or not isinstance(row.get("focus"), str)
                ):
                    continue
                clamped_row: dict[str, Any] = {
                    "title": cast(str, row.get("title")),
                    "focus": cast(str, row.get("focus"))[:DIRECTIVE_SECTION_TEXT_MAX],
                }
                group_ids = row.get("group_ids")
                if (
                    isinstance(group_ids, list)
                    and group_ids
                    and all(isinstance(group_id, str) for group_id in group_ids)
                ):
                    clamped_row["group_ids"] = list(group_ids)
                clamped.append(clamped_row)
            proposal["proposed_sections"] = clamped  # type: ignore[index]
            for option in options:
                if option.get("id") == "as_proposed":
                    option["delta"] = {
                        "synthesise": {"synthesis": {"sections": [dict(row) for row in clamped]}}
                    }
                    break
    return options, bundle


def _build_bundle(
    engine: Engine,
    *,
    name: str,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    backends: RunnerBackends,
    section_budget: int | None,
) -> dict[str, Any] | None:
    """Build the decision-point bundle for a lattice pause, fail-safe to None."""
    try:
        with engine.connect() as conn:
            if name == SEARCH_EXCEPTION:
                return p1_bundle(conn, project_id=project_id, evidence_scope_id=evidence_scope_id)
            if name == EVIDENCE_BASE_COVERAGE:
                return p2_bundle(
                    conn,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    characterisation_run_id=successful_runs.get("characterise"),
                )
            if name == DEEPENING_SELECTION:
                selection_run_id = successful_runs.get("select")
                if selection_run_id is None:
                    return None
                return p3_bundle(conn, project_id=project_id, selection_run_id=selection_run_id)
            if name == FINDING_GROUPS:
                group_run_id = successful_runs.get("group")
                return (
                    groups_bundle(conn, project_id=project_id, group_run_id=group_run_id)
                    if group_run_id is not None
                    else None
                )
            if name == SYNTHESIS_SHAPE:
                context = _synthesise_context(
                    conn,
                    project_id=project_id,
                    evidence_scope_id=evidence_scope_id,
                    successful_runs=successful_runs,
                )
                if context is None:
                    return None
                # Mirror the harness's synthesis default so the proposal uses the
                # same backend the synthesise component will (harness.py:731).
                synthesis_backend = (
                    backends.synthesis if backends.synthesis is not None else StubSynthesisBackend()
                )
                return p4_bundle(
                    conn,
                    project_id=project_id,
                    context=context,
                    synthesis_backend=synthesis_backend,
                    group_run_id=successful_runs.get("group"),
                    section_budget=section_budget,
                )
    except Exception as exc:  # noqa: BLE001 — fail-safe to no bundle (watch discipline 5)
        log.warning("runner.bundle_build_failed", steer_point=name, error=_bounded_error(exc))
        return None
    return None


def _synthesise_context(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
) -> SynthesiseContext | None:
    """Assemble the walk's real SynthesiseContext for the P4 proposal (harness parity)."""
    row = conn.execute(
        select(evidence_scope.c.intent, evidence_scope.c.context)
        .where(evidence_scope.c.evidence_scope_id == evidence_scope_id)
        .where(evidence_scope.c.project_id == project_id)
    ).first()
    if row is None:
        return None
    return SynthesiseContext(
        scope_id=evidence_scope_id,
        intent=row.intent,
        context=dict(row.context) if isinstance(row.context, dict) else {},
        characterisation_run_id=successful_runs.get("characterise"),
        selection_run_id=successful_runs.get("select"),
        extraction_run_id=successful_runs.get("extract"),
        grouping_run_id=successful_runs.get("group"),
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
    steer_point_name: str | None = None,
    options: list[dict[str, Any]] | None = None,
    bundle: dict[str, Any] | None = None,
    triggers: list[dict[str, Any]] | None = None,
    rerun_component: str | None = None,
    segment_reentry_allowed: bool = False,
    authored_options: list[dict[str, Any]] | None = None,
    orchestrator: OrchestratorBackend | None = None,
    session_id: uuid.UUID | None = None,
) -> _PauseApplied:
    pause_payload = _pause_payload(
        point,
        steer_point_name=steer_point_name,
        options=options,
        bundle=bundle,
        triggers=triggers,
        rerun_component=rerun_component,
        segment_reentry_allowed=segment_reentry_allowed,
        authored_options=authored_options,
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
    # The deterministic render rides the payload verbatim (task 025): it is the
    # check-in content of record, and the web API must serve exactly what the
    # runner presented — never a re-derivation.
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=event_run_id,
        event_type=steering_events.STEERING_PAUSE,
        payload={**base, **pause_payload, "render": render},
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
        if isinstance(response, FreeText):
            # Free text at a pause → compile through the router, validate
            # author-blind, confirm, apply (contract decision 3). A backend
            # error, an all-refused compile, or an unconfirmed fan-out all
            # degrade to re-presenting the canonical menu with an honest line
            # (watch discipline 5).
            result = _handle_free_text(
                engine,
                io,
                utterance=response.text,
                point=point,
                state=state,
                project_id=project_id,
                completed_components=completed_components,
                capability_run_id=capability_run_id,
                event_run_id=event_run_id,
                steer_point_name=steer_point_name,
                options=options,
                rerun_component=rerun_component,
                segment_reentry_allowed=segment_reentry_allowed,
                base=base,
                orchestrator=orchestrator,
                session_id=session_id,
            )
            if result.applied is not None:
                return result.applied
            current_render = f"{render}\n{result.note}"
            continue
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
            if rerun_component is not None and set(response.directive_deltas) == {rerun_component}:
                # FIX C: a picked watch-AUTHORED option whose delta re-runs the
                # steer point's component takes the same replacement-re-run apply
                # path a confirmed router fan-out does — so it gets the same
                # on-screen mode declaration + bounded delta render behind the
                # confirm gate before anything applies. A user-authored canonical
                # pick (authored_by None) keeps direct-apply — its label already
                # carries the replacement wording. Declined (or a non-confirm IO,
                # fail-closed) → nothing applies, the decision is recorded
                # confirmed=false, and the canonical menu is re-presented.
                if response.authored_by == "orchestrator" and not _confirm(
                    io,
                    render_authored_replacement_confirmation(
                        CompiledFragment(
                            "",
                            "replacement_rerun",
                            rerun_component,
                            response.directive_deltas[rerun_component],
                            "replacement",
                        )
                    ),
                ):
                    _emit_authored_declined(
                        engine,
                        project_id=project_id,
                        run_id=event_run_id,
                        base=base,
                        interpreted_action=_interpreted_action(response),
                    )
                    current_render = (
                        f"{render}\nNothing applied (not confirmed); please choose an option."
                    )
                    continue
                try:
                    rerun_state, merged_directive = _apply_replacement_rerun(
                        engine,
                        project_id=project_id,
                        state=state,
                        adjustment=response,
                        base=base,
                        event_run_id=event_run_id,
                        component=rerun_component,
                        authored_by=response.authored_by or "user",
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
                    authored_by=response.authored_by or "user",
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


def _confirm(io: CheckInIO, render: str) -> bool:
    """Ask a confirm-capable IO to gate the fan-out; default/NullIO is False.

    Nothing a router compiles applies until the user confirms the rendered
    fan-out (contract decision 3). An IO with no ``confirm`` method — ``NullIO``
    and the unattended default — declines, so nothing applies.
    """
    if isinstance(io, _ConfirmCapable):
        return io.confirm(render)
    return False


@dataclass(frozen=True)
class _FreeTextResult:
    """Outcome of compiling free text at a pause.

    Args:
        applied: The applied pause result, or ``None`` when nothing applied
            (a backend error, an all-refused compile, or an unconfirmed fan-out)
            and the canonical menu should be re-presented.
        note: The honest line appended to the re-presented render (only read when
            ``applied`` is ``None``).
    """

    applied: _PauseApplied | None
    note: str = ""


def _router_pause_context(
    point: PausePoint,
    *,
    state: _SteeringState,
    steer_point_name: str | None,
    options: list[dict[str, Any]] | None,
    completed_components: set[str],
    rerun_component: str | None,
    segment_reentry_allowed: bool,
) -> dict[str, Any]:
    """The deterministic pause context the router compiles against (data, not instructions)."""
    return {
        "point": steer_point_name,
        "boundary": point.boundary,
        "component": point.component,
        "steering_mode": state.plan.steering_mode,
        "canonical_options": options or [],
        "not_yet_run_components": [
            component
            for component in state.chain.components
            if component not in completed_components
        ],
        "rerun_surface": {
            "replacement_component": rerun_component,
            "additive_segment_reentry": segment_reentry_allowed,
        },
    }


def _handle_free_text(
    engine: Engine,
    io: CheckInIO,
    *,
    utterance: str,
    point: PausePoint,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    capability_run_id: uuid.UUID,
    event_run_id: uuid.UUID | None,
    steer_point_name: str | None,
    options: list[dict[str, Any]] | None,
    rerun_component: str | None,
    segment_reentry_allowed: bool,
    base: dict[str, Any],
    orchestrator: OrchestratorBackend | None,
    session_id: uuid.UUID | None,
) -> _FreeTextResult:
    """Compile free text into a confirmed fan-out and apply it (contract decision 3).

    Routes the utterance through ``orchestrator.route``, re-validates every
    fragment author-blind through :func:`compile_fanout`, renders the fan-out,
    gates it behind the IO's ``confirm``, and — only on confirmation — applies
    refusals, one merged plan adjustment and at most one re-run through the SAME
    apply machinery a canonical option choice uses. Any backend error degrades to
    the canonical menu (watch discipline 5).
    """
    if orchestrator is None:
        _emit_router_degrade(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            state=state,
            point=point,
            run_id=event_run_id,
            reason="no orchestrator backend — canonical menu re-presented",
        )
        return _FreeTextResult(None, "Free-text steering is unavailable here; choose an option.")

    pause_context = _router_pause_context(
        point,
        state=state,
        steer_point_name=steer_point_name,
        options=options,
        completed_components=completed_components,
        rerun_component=rerun_component,
        segment_reentry_allowed=segment_reentry_allowed,
    )
    try:
        compile_result = orchestrator.route(utterance, pause_context, session_id=session_id)
    except Exception as exc:  # noqa: BLE001 — fail-safe to the canonical floor (discipline 5)
        log.warning("orchestrator.route_failed", component=point.component, error=str(exc)[:200])
        _emit_router_degrade(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            state=state,
            point=point,
            run_id=event_run_id,
            reason="router compile failed — canonical menu re-presented",
        )
        return _FreeTextResult(None, "I could not interpret that; please choose an option.")

    fanout = compile_fanout(
        compile_result,
        backend_scope=state.plan.backend_scope,
        current_components=set(state.chain.components),
        completed_components=completed_components,
        rerun_surface=RerunSurface(
            replacement_component=rerun_component,
            segment_reentry_available=segment_reentry_allowed,
        ),
    )

    # Refusals are the demand meter: one steering.refused per refused fragment,
    # verbatim text + reason, emitted whether or not anything else applies.
    for refused in fanout.refused:
        _emit_refused(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            fragment_text=refused.fragment_text,
            reason=refused.reason,
        )

    if not fanout.compiled:
        # FIX B: when ALL fragments were refused, surface each fragment's
        # plain-language reason on the re-presented render — not only in the
        # event log — mirroring the per-fragment reasons a partial refusal
        # already shows at the confirm gate.
        if fanout.refused:
            note = "\n".join(
                [
                    "None of that could be applied:",
                    *(render_refused_fragment(refused) for refused in fanout.refused),
                    "…please choose an option.",
                ]
            )
        else:
            note = "None of that could be applied; please choose an option."
        return _FreeTextResult(None, note)

    confirmation = render_fanout_confirmation(fanout)
    if not _confirm(io, confirmation):
        # Unconfirmed: nothing applies; the record shows what was offered and declined.
        _emit_fanout_declined(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            fanout=fanout,
            utterance=utterance,
        )
        return _FreeTextResult(None, "Nothing applied (not confirmed); please choose an option.")

    return _apply_fanout(
        engine,
        fanout=fanout,
        utterance=utterance,
        point=point,
        state=state,
        project_id=project_id,
        completed_components=completed_components,
        base=base,
        event_run_id=event_run_id,
    )


def _apply_fanout(
    engine: Engine,
    *,
    fanout: FanOut,
    utterance: str,
    point: PausePoint,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
) -> _FreeTextResult:
    """Apply a confirmed fan-out: merged plan adjustment then at most one re-run.

    Refusals are already evented. Plan-adjustment fragments merge into ONE Adjust
    (one plan-version write, one decision event carrying the verbatim utterance
    and the fan-out as its interpreted action). A single re-run fragment then
    applies on the resulting state — the one the utterance leads with (the
    one-cycle rule was resolved in :func:`compile_fanout`).

    FIX 3a: each apply is guarded separately. A confirmed fan-out whose apply raises
    :class:`SteeringAdjustmentError` (e.g. a re-run that cannot re-thread, or a
    delta the plan fields cannot map) no longer crashes the walk: the failing part
    emits ``steering.rejected`` (verbatim utterance + reason) and the canonical menu
    is re-presented. Anything that already applied stays applied — its own
    decision/refused events remain truthful about what did and did not land.
    """
    interpreted = fanout.as_interpreted_action()
    changed = False
    rerun: dict[str, Any] | None = None
    segment_reentry: dict[str, Any] | None = None

    adjustments = fanout.plan_adjustments
    if adjustments:
        try:
            state = _apply_runner_adjustment(
                engine,
                project_id=project_id,
                state=state,
                adjustment=Adjust(
                    directive_deltas={frag.component: frag.delta for frag in adjustments}
                ),
                completed_components=completed_components,
                base=base,
                event_run_id=event_run_id,
                user_text=utterance,
                interpreted_action=interpreted,
            )
        except SteeringAdjustmentError as exc:
            return _fanout_apply_rejected(
                engine,
                project_id=project_id,
                event_run_id=event_run_id,
                base=base,
                exc=exc,
                interpreted=interpreted,
                utterance=utterance,
            )
        changed = True

    rerun_fragment = fanout.rerun
    if rerun_fragment is not None:
        try:
            state, rerun, segment_reentry = _apply_fanout_rerun(
                engine,
                fragment=rerun_fragment,
                utterance=utterance,
                interpreted=interpreted,
                point=point,
                state=state,
                project_id=project_id,
                completed_components=completed_components,
                base=base,
                event_run_id=event_run_id,
            )
        except SteeringAdjustmentError as exc:
            return _fanout_apply_rejected(
                engine,
                project_id=project_id,
                event_run_id=event_run_id,
                base=base,
                exc=exc,
                interpreted=interpreted,
                utterance=utterance,
            )

    return _FreeTextResult(
        _PauseApplied(state=state, changed=changed, rerun=rerun, segment_reentry=segment_reentry)
    )


def _fanout_apply_rejected(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    event_run_id: uuid.UUID | None,
    base: dict[str, Any],
    exc: SteeringAdjustmentError,
    interpreted: dict[str, Any],
    utterance: str,
) -> _FreeTextResult:
    """Event a confirmed-fan-out apply failure and re-present the menu (FIX 3a)."""
    _emit_rejected(
        engine,
        project_id=project_id,
        run_id=event_run_id,
        base=base,
        exc=exc,
        offending_delta=interpreted,
        user_text=utterance,
    )
    return _FreeTextResult(None, f"That could not be applied: {exc}; please choose an option.")


def _apply_fanout_rerun(
    engine: Engine,
    *,
    fragment: CompiledFragment,
    utterance: str,
    interpreted: dict[str, Any],
    point: PausePoint,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
) -> tuple[_SteeringState, dict[str, Any] | None, dict[str, Any] | None]:
    """Apply one confirmed re-run fragment (replacement or additive segment re-entry)."""
    if fragment.kind == "replacement_rerun":
        rerun_state, merged = _apply_replacement_rerun(
            engine,
            project_id=project_id,
            state=state,
            adjustment=Adjust(directive_deltas={fragment.component: fragment.delta}),
            base=base,
            event_run_id=event_run_id,
            component=fragment.component,
            user_text=utterance,
        )
        return rerun_state, {"component": fragment.component, "directive": merged}, None

    # segment_reentry (additive re-search or a criteria re-screen re-walk)
    response = ReEnterSegment(
        segment_start=SHIPPED_SEGMENT_START,
        directive_deltas={fragment.component: fragment.delta},
    )
    reentry_state = _apply_segment_reentry(
        engine,
        project_id=project_id,
        state=state,
        response=response,
        base=base,
        event_run_id=event_run_id,
        completed_components=completed_components,
        boundary_component=point.component,
        user_text=utterance,
    )
    return (
        reentry_state,
        None,
        {
            "segment_start": response.segment_start,
            "boundary_component": point.component,
            "directive_deltas": response.directive_deltas,
        },
    )


def _emit_refused(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    fragment_text: str,
    reason: str,
) -> None:
    """Append one standalone steering.refused for a refused fan-out fragment."""
    if run_id is None:
        return
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_REFUSED,
        payload={**base, "fragment_text": fragment_text, "reason": reason},
    )


def _emit_fanout_declined(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    fanout: FanOut,
    utterance: str,
) -> None:
    """Append a steering.decision with confirmed=false — the offered-and-declined record."""
    if run_id is None:
        return
    payload = steering_events.decision_payload(
        base,
        decided_by="user",
        authored_by="user",
        response="adjust",
        interpreted_action=fanout.as_interpreted_action(),
        confirmed=False,
        user_text=utterance,
        rerun_mode=None,
    )
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_DECISION,
        payload=payload,
    )


def _emit_authored_declined(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    interpreted_action: dict[str, Any],
) -> None:
    """Record a picked-then-declined watch-authored replacement (FIX C): confirmed=false.

    The user picked a watch-authored replacement option but declined its mode+delta
    confirm (or the IO cannot confirm), so nothing applied — but the decision still
    surfaces in the durable record as an offered-and-declined authored action
    (decided_by=user, authored_by=orchestrator).
    """
    if run_id is None:
        return
    payload = steering_events.decision_payload(
        base,
        decided_by="user",
        authored_by="orchestrator",
        response="adjust",
        interpreted_action=interpreted_action,
        confirmed=False,
        rerun_mode=None,
    )
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_DECISION,
        payload=payload,
    )


def _emit_router_degrade(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    state: _SteeringState,
    point: PausePoint,
    run_id: uuid.UUID | None,
    reason: str,
) -> None:
    """Event a router degrade as a watch_error-style judgement (discipline 5)."""
    if run_id is None:
        return
    _emit_judgement_routed(
        engine,
        project_id=project_id,
        capability_run_id=capability_run_id,
        state=state,
        point=point,
        run_id=run_id,
        verdict="watch_error",
        reason=reason,
    )


def _pause_payload(
    point: PausePoint,
    *,
    steer_point_name: str | None = None,
    options: list[dict[str, Any]] | None = None,
    bundle: dict[str, Any] | None = None,
    triggers: list[dict[str, Any]] | None = None,
    rerun_component: str | None = None,
    segment_reentry_allowed: bool = False,
    authored_options: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the pause payload for a lattice or generic-floor boundary.

    A lattice pause carries ``kind="steer_point"`` + the point name + its
    canonical options + fired triggers + (P2/P3/P4) its deterministic bundle —
    the durable record of what the user saw. A generic non-lattice pause carries
    ``kind="check_in"`` + the generic floor options (finding M6). When the watch
    authored run-specific options (Task 14) they ride the pause alongside the
    canonical floor under ``authored_options`` with authorship attribution — the
    canonical options remain the floor and the degrade target.
    """
    payload: dict[str, Any] = {
        "kind": "check_in",
        "boundary": point.boundary,
        "component": point.component,
        "rerun_component": rerun_component,
        "segment_reentry_allowed": segment_reentry_allowed,
    }
    if steer_point_name is not None:
        payload["kind"] = "steer_point"
        payload["steer_point"] = steer_point_name
    if options is not None:
        projected = [dict(option) for option in options]
        for authored in authored_options or []:
            endorsed = authored.get("endorses_option_id")
            why = authored.get("why")
            if isinstance(endorsed, str):
                canonical = next((item for item in projected if item.get("id") == endorsed), None)
                if canonical is not None:
                    canonical["endorsement"] = why if isinstance(why, str) else None
                    continue
            component, delta = authored.get("component"), authored.get("delta")
            if not isinstance(component, str) or not isinstance(delta, dict):
                continue
            projected.append(
                {
                    "id": authored.get("id"),
                    "label": authored.get("label"),
                    "description": why if isinstance(why, str) else "",
                    "why": why,
                    "suggested": True,
                    "authored": True,
                    "delta": {component: delta},
                    "requires_user_input": False,
                }
            )
        payload["options"] = projected
    if triggers is not None:
        payload["triggers"] = triggers
    if bundle is not None:
        payload["bundle"] = bundle
    if authored_options is not None:
        payload["authored_by"] = "orchestrator"
        # Retained for the terminal adapter's compatibility; HTTP reads the
        # projected ``options`` list above.
        payload["authored_options"] = authored_options
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

    Names the segment (start component, boundary) and records the full amended
    directive deltas — parity with the adjustment path (which records
    ``directive_deltas``, not just key names), so ``steering_history`` alone can
    show what a re-search was steered to (FIX D). The delta payload is already
    bounded/scrubbed at the parser layer.
    """
    return {
        "segment_start": response.segment_start,
        "boundary": boundary_component,
        "directive_deltas": response.directive_deltas,
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
    user_text: str | None = None,
) -> None:
    """Append a standalone steering.rejected with the reason and offending delta.

    ``user_text`` records the verbatim steering utterance when the rejection comes
    from a confirmed router fan-out apply (FIX 3a).
    """
    payload = {
        **base,
        "reason": str(exc),
        "offending_delta": offending_delta,
    }
    if user_text is not None:
        payload["user_text"] = user_text
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
    decided_by: steering_events.DecidedBy = "user",
    authored_by: str = "user",
    extra_payload: dict[str, Any] | None = None,
) -> None:
    """Flip the plan to abandoned and record the abort decision atomically.

    Contract decision 1 (finding m1): the abort decision commits on the same
    transaction as the abandon flip. When there is no plan row to flip
    (``plan_row_id`` is None — a run-local stop), the decision is a standalone
    append with no state-change partner. ``decided_by``/``authored_by`` default
    to the live-user path; the Unattended standing-default hard stop passes
    ``standing_default`` and rides the fired triggers + rule echo on
    ``extra_payload``.
    """
    decision = steering_events.decision_payload(
        base,
        decided_by=decided_by,
        authored_by=authored_by,
        response="abort",
        interpreted_action=None,
        confirmed=True,
        rerun_mode=None,
    )
    if extra_payload:
        decision.update(extra_payload)
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
    decided_by: steering_events.DecidedBy = "user",
    authored_by: str = "user",
    extra_payload: dict[str, Any] | None = None,
    user_text: str | None = None,
    interpreted_action: Any = None,
) -> _SteeringState:
    if state.plan_row_id is None:
        raise SteeringAdjustmentError("plan_row_id is required to persist an adjustment")
    with engine.begin() as conn:
        plan_row = conn.execute(
            select(orchestration_plan).where(orchestration_plan.c.plan_id == state.plan_row_id)
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
        # A router fan-out overrides interpreted_action with the whole fan-out and
        # threads the verbatim utterance as user_text (contract decision 3).
        decision = steering_events.decision_payload(
            base,
            decided_by=decided_by,
            authored_by=authored_by,
            response=_decision_response(adjustment),
            interpreted_action=(
                interpreted_action
                if interpreted_action is not None
                else _interpreted_action(adjustment)
            ),
            confirmed=True,
            user_text=user_text,
            rerun_mode=None,
        )
        if extra_payload:
            decision.update(extra_payload)
        steering_events.emit(
            conn,
            project_id=project_id,
            run_id=event_run_id,
            event_type=steering_events.STEERING_DECISION,
            payload=decision,
        )
    amended_chain = compose(amended_plan)
    # Commit-layer deltas for not-yet-run components have no plan-field mapping
    # (validated + recorded above, but the payload carries them forward
    # unchanged): stash them as a pending overlay so the component actually
    # consumes them when it runs (task 024, 15c). Merge-over on repeat adjustments.
    new_overlays = _extend_overlays(state.pending_overlays, adjustment.directive_deltas)
    return _SteeringState(
        plan=amended_plan,
        plan_id=amended_plan_id,
        plan_version=amended_version,
        plan_row_id=amended_plan_id,
        chain=amended_chain,
        pause_points=pause_points(amended_plan.steering_mode, amended_chain),
        pending_overlays=new_overlays,
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
    decided_by: steering_events.DecidedBy = "user",
    authored_by: str = "user",
    extra_payload: dict[str, Any] | None = None,
    user_text: str | None = None,
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
        raise SteeringAdjustmentError(f"{component} re-run directive must contain a {key!r} object")
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
            decided_by=decided_by,
            authored_by=authored_by,
            response=_decision_response(adjustment),
            interpreted_action=_interpreted_action(adjustment),
            confirmed=True,
            user_text=user_text,
            rerun_mode="replacement",
        )
        if extra_payload:
            decision.update(extra_payload)
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
        pending_overlays=state.pending_overlays,
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
    attempted_runs: dict[str, uuid.UUID] | None = None,
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
    if attempted_runs is not None:
        attempted_runs[registry_component_for(component)] = final_attempt.run_id
    retried = len(attempts) > 1
    attempt_run_ids = [attempt.run_id for attempt in attempts]
    if final_attempt.status == "succeeded":
        successful_runs[component] = final_attempt.run_id
        blocked_discretionary.pop(component, None)
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
    decided_by: steering_events.DecidedBy = "user",
    authored_by: str = "user",
    extra_payload: dict[str, Any] | None = None,
    user_text: str | None = None,
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
            decided_by=decided_by,
            authored_by=authored_by,
            response="adjust",
            interpreted_action=_reentry_interpreted_action(response, boundary_component),
            confirmed=True,
            user_text=user_text,
            rerun_mode="additive",
        )
        if extra_payload:
            decision.update(extra_payload)
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
        pending_overlays=state.pending_overlays,
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
    attempted_runs: dict[str, uuid.UUID] | None = None,
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
        if attempted_runs is not None:
            attempted_runs[registry_component_for(component)] = final_attempt.run_id
        retried = len(attempts) > 1
        attempt_run_ids = [attempt.run_id for attempt in attempts]
        if final_attempt.status == "succeeded":
            successful_runs[component] = final_attempt.run_id
            blocked_discretionary.pop(component, None)
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
    attempted_runs: dict[str, uuid.UUID],
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
        attempted_runs=attempted_runs,
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
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        backends=backends,
        completed_components=completed_components,
        flagged_events=flagged_events,
        capability_run_id=capability_run_id,
        most_recent_attempted_run_id=most_recent_attempted_run_id,
        boundary_run_id=successful_runs.get(boundary_component),
        selection_run_id=(
            successful_runs.get("select") if boundary_component == "select" else None
        ),
        allow_segment_reentry=False,
        session_id=session_id,
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
            attempted_runs=attempted_runs,
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


def _run_plan_before_segment_reentry(
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
    attempted_runs: dict[str, uuid.UUID],
    blocked_discretionary: dict[str, str],
    completed_components: set[str],
    step_outcomes: list[RunStepOutcome],
    flagged_events: list[dict[str, Any]],
    capability_run_id: uuid.UUID,
    orchestrator: OrchestratorBackend | None,
    discretion_hook: DiscretionHook,
) -> _PlanSegmentReentryResult:
    """Additive segment re-entry at a before_component boundary (Task 15b, P2).

    Mirrors :func:`_run_plan_segment_reentry` but re-presents the SAME *before*
    boundary once (segment re-entry withheld — the one-cycle rule). The re-walk
    runs acquire→last-completed (``boundary_component`` is the pending step, whose
    own run is naturally excluded because it has not completed), then the walk
    falls through in ``run_plan`` to run the pending step referencing the re-walk's
    fresh upstream runs.
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
        attempted_runs=attempted_runs,
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

    # Re-present the SAME before boundary ONCE, segment re-entry withheld.
    reentry = _handle_before_component_boundary(
        engine,
        io,
        step=boundary_step,
        render=render_check_in(last_check_in_payload),
        state=state,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        backends=backends,
        completed_components=completed_components,
        capability_run_id=capability_run_id,
        most_recent_attempted_run_id=most_recent_attempted_run_id,
        flagged_events=flagged_events,
        discretion_hook=discretion_hook,
        orchestrator=orchestrator,
        session_id=session_id,
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
            attempted_runs=attempted_runs,
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
    point: PausePoint,
    name: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    attempted_runs: dict[str, uuid.UUID],
    completed_components: set[str],
    flagged_events: list[dict[str, Any]],
    capability_run_id: uuid.UUID,
    event_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    allow_segment_reentry: bool,
    discretion_hook: DiscretionHook,
    backends: RunnerBackends,
    rerun_component: str | None = None,
) -> _PauseApplied:
    """Resolve one Unattended lattice boundary — discretion is the mode.

    Never pauses (ADR 0021 decision 4). The fired floor triggers are read first
    and ride every emitted decision (discipline 1 — the floor is never
    suppressible). Then, in authority order (declared rules > orchestrator):

    * P1 (search_exception) is exception-only — no fired triggers means nothing
      to decide, so the walk proceeds silently;
    * a **pinned standing rule** for the point decides — a hard ``stop`` is always
      honoured (abandon + abort, ``standing_default``); a ``proceed_flag`` with an
      option/delta applies it through the SAME apply machinery a pause would use;
      a bare ``proceed_flag`` proceeds;
    * with **no pinned rule**, the deterministic discretion floor (the injected
      hook, defaulting to proceed + ``unconfigured_default`` — the loudest flag
      class) decides. This is the seam the Phase-5 watch replaces; the hook is
      consulted ONLY here, never when a rule is present.

    Every branch that decides emits a ``steering.decision`` with
    ``decided_by="standing_default"`` and appends an ``auto_resolved`` flag for
    the loudest-first collation.
    """
    triggers = _lattice_triggers(
        engine,
        name=name,
        state=state,
        project_id=project_id,
        evidence_scope_id=evidence_scope_id,
        successful_runs=successful_runs,
        attempted_runs=attempted_runs,
    )
    # P1 is exception-only: with nothing fired there is no decision to take.
    if name == SEARCH_EXCEPTION and not triggers:
        return _PauseApplied(state=state)

    base = steering_events.base_payload(
        capability_run_id=capability_run_id,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        boundary=point.boundary,
        component=point.component,
    )
    rule = next(
        (default for default in state.plan.steer_point_defaults if default.steer_point == name),
        None,
    )
    if rule is None:
        # No pinned rule → the discretion floor / watch. The hook is consulted only
        # on this branch (a pinned rule is resolved above), pinning the authority
        # order structurally: declared rules > orchestrator. The runner pre-fetches
        # the bundle/header/digest so the watch decides over the same option-complete
        # state a pause shows (Task 14); the deterministic floor ignores them.
        bundle = _build_bundle(
            engine,
            name=name,
            project_id=project_id,
            evidence_scope_id=evidence_scope_id,
            successful_runs=successful_runs,
            backends=backends,
            section_budget=state.plan.section_budget,
        )
        outcome = discretion_hook(
            _DiscretionContext(
                steer_point=name,
                boundary=point.boundary,
                component=point.component,
                triggers=triggers,
                plan=state.plan,
                bundle=bundle,
                header=_watch_header(state),
                digest=_watch_digest(
                    engine, project_id=project_id, capability_run_id=capability_run_id
                ),
                read_tools=None,
            )
        )
        return _apply_discretion_outcome(
            engine,
            outcome=outcome,
            point=point,
            name=name,
            state=state,
            project_id=project_id,
            completed_components=completed_components,
            flagged_events=flagged_events,
            base=base,
            event_run_id=event_run_id,
            selection_run_id=selection_run_id,
            allow_segment_reentry=allow_segment_reentry,
            triggers=triggers,
            rerun_component=rerun_component,
        )

    if rule.action == "stop":
        # A hard stop is ALWAYS honoured — no code path routes around it.
        _abort_and_record(
            engine,
            project_id=project_id,
            state=state,
            base=base,
            event_run_id=event_run_id,
            decided_by="standing_default",
            authored_by="standing_default",
            extra_payload={"triggers": triggers, "standing_rule": _rule_echo(rule)},
        )
        flagged_events.append(_standing_flag(point.component, name, rule=name, action="stop"))
        return _PauseApplied(state=state, aborted=True)

    return _apply_standing_proceed(
        engine,
        point=point,
        name=name,
        rule=rule,
        state=state,
        project_id=project_id,
        completed_components=completed_components,
        flagged_events=flagged_events,
        base=base,
        event_run_id=event_run_id,
        selection_run_id=selection_run_id,
        allow_segment_reentry=allow_segment_reentry,
        triggers=triggers,
        rerun_component=rerun_component,
    )


def _match_replacement_delta(
    rerun_component: str | None, effective: dict[str, Any]
) -> dict[str, dict[str, Any]] | None:
    """Normalise a rule/watch delta to a replacement-rerun ``directive_deltas`` or ``None``.

    Canonical option deltas are shaped two ways: bare context-key (P3 select's
    ``{"selection": ...}``) and component-keyed (P2 recharacterise's
    ``{"characterise": {"characterise": ...}}``, P4 regroup's ``{"group":
    {"grouping": ...}}``). Both normalise to the component-keyed
    ``{rerun_component: {context_key: ...}}`` shape :func:`_apply_replacement_rerun`
    consumes. Returns ``None`` when ``effective`` does not target the point's
    re-run component (it is then a segment re-entry or a plan adjustment).
    """
    if rerun_component is None:
        return None
    context_key = REPLACEMENT_RERUNS[rerun_component].context_key
    keys = set(effective)
    if keys == {rerun_component} and isinstance(effective.get(rerun_component), dict):
        return effective  # already component-keyed
    if keys == {context_key}:
        return {rerun_component: effective}  # bare context-key → wrap
    return None


def _apply_standing_proceed(
    engine: Engine,
    *,
    point: PausePoint,
    name: str,
    rule: Any,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    flagged_events: list[dict[str, Any]],
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    allow_segment_reentry: bool,
    triggers: list[dict[str, Any]],
    rerun_component: str | None = None,
) -> _PauseApplied:
    """Apply a pinned ``proceed_flag`` standing rule through the existing machinery.

    The effective delta is the rule's own delta, else the option's canonical
    template (validation guarantees a requires-input option's rule carries its own
    delta). An empty delta proceeds. A delta targeting the point's re-run
    component re-runs it (replacement): select at P3, characterise at P2, group at
    P4 (Task 15b). An ``{"acquire": ...}`` delta where segment re-entry is allowed
    (P2 / an after-boundary before the run-scoped components) re-enters the
    additive segment; anything else is a plan adjustment of a pending component. A
    delta the wiring genuinely cannot execute here degrades fail-safe to
    proceed-and-flag with a ``steering.rejected`` on the record (watch
    discipline 5) — never crashing the run.
    """
    effective = rule.delta
    if effective is None and rule.option_id is not None:
        options = build_steer_point_options(plan=state.plan, point=name)
        template = next((o["delta"] for o in options if o["id"] == rule.option_id), None)
        effective = template
    effective = effective or {}
    echo = _rule_echo(rule)
    extra = {"triggers": triggers, "standing_rule": echo}

    if not effective:
        _emit_standing_proceed_decision(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            interpreted_action="proceed",
            standing_rule=echo,
            triggers=triggers,
        )
        flagged_events.append(
            _standing_flag(point.component, name, rule=name, action="proceed_flag")
        )
        return _PauseApplied(state=state)

    keys = set(effective)
    replacement_deltas = _match_replacement_delta(rerun_component, effective)
    try:
        if replacement_deltas is not None:
            assert rerun_component is not None
            rerun_state, merged = _apply_replacement_rerun(
                engine,
                project_id=project_id,
                state=state,
                adjustment=Adjust(directive_deltas=replacement_deltas),
                base=base,
                event_run_id=event_run_id,
                component=rerun_component,
                decided_by="standing_default",
                authored_by="standing_default",
                extra_payload=extra,
            )
            flagged_events.append(
                _standing_flag(rerun_component, name, rule=name, action="proceed_flag")
            )
            return _PauseApplied(
                state=rerun_state, rerun={"component": rerun_component, "directive": merged}
            )
        if (
            allow_segment_reentry
            and keys == {SHIPPED_SEGMENT_START}
            and SHIPPED_SEGMENT_START in completed_components
        ):
            response = ReEnterSegment(directive_deltas=effective)
            reentry_state = _apply_segment_reentry(
                engine,
                project_id=project_id,
                state=state,
                response=response,
                base=base,
                event_run_id=event_run_id,
                completed_components=completed_components,
                boundary_component=point.component,
                decided_by="standing_default",
                authored_by="standing_default",
                extra_payload=extra,
            )
            flagged_events.append(
                _standing_flag(point.component, name, rule=name, action="proceed_flag")
            )
            return _PauseApplied(
                state=reentry_state,
                segment_reentry={
                    "segment_start": response.segment_start,
                    "boundary_component": point.component,
                    "directive_deltas": response.directive_deltas,
                },
            )
        amended_state = _apply_runner_adjustment(
            engine,
            project_id=project_id,
            state=state,
            adjustment=Adjust(directive_deltas=effective),
            completed_components=completed_components,
            base=base,
            event_run_id=event_run_id,
            decided_by="standing_default",
            authored_by="standing_default",
            extra_payload=extra,
        )
        flagged_events.append(
            _standing_flag(point.component, name, rule=name, action="proceed_flag")
        )
        return _PauseApplied(state=amended_state, changed=True)
    except SteeringAdjustmentError as exc:
        # Fail-safe floor: a standing rule whose re-run is not wired at this
        # boundary this slice degrades to proceed-and-flag with the reason on
        # the record, rather than failing the run.
        _emit_rejected(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            exc=exc,
            offending_delta=effective,
        )
        _emit_standing_proceed_decision(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            interpreted_action="proceed",
            standing_rule=echo,
            triggers=triggers,
        )
        flagged_events.append(_standing_flag(point.component, name, rule=name, action="rejected"))
        return _PauseApplied(state=state)


def _standing_flag(component: str, steer_point: str, *, rule: str, action: str) -> dict[str, Any]:
    """One auto-resolution flag for the Unattended collation (loudest-first)."""
    return {
        "component": component,
        "status": "auto_resolved",
        "steer_point": steer_point,
        "rule": rule,
        "action": action,
    }


def _trigger_fired_flag(point: PausePoint, triggers: list[dict[str, Any]]) -> dict[str, Any]:
    """One collation flag for a fired non-lattice floor trigger that did not pause (FIX 1).

    Unattended never pauses, so a fired floor trigger there rides the collation
    (and the watch's trigger-fired triage) instead of a user pause — review still
    sees the floor fired.
    """
    return {
        "component": point.component,
        "status": "triggers_fired",
        "boundary": point.boundary,
        "triggers": triggers,
    }


def _rule_echo(rule: Any) -> dict[str, Any]:
    """Echo a standing rule onto its decision event (attribution, decision 9)."""
    echo: dict[str, Any] = {"steer_point": rule.steer_point, "action": rule.action}
    if rule.option_id is not None:
        echo["option_id"] = rule.option_id
    return echo


def _emit_standing_proceed_decision(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    interpreted_action: Any,
    standing_rule: dict[str, Any],
    triggers: list[dict[str, Any]],
) -> None:
    """Append a standing-default proceed decision (no adjacent state change)."""
    payload = steering_events.decision_payload(
        base,
        decided_by="standing_default",
        authored_by="standing_default",
        response="continue",
        interpreted_action=interpreted_action,
        confirmed=True,
        rerun_mode=None,
    )
    payload["standing_rule"] = standing_rule
    payload["triggers"] = triggers
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_DECISION,
        payload=payload,
    )


def _emit_judgement_routed(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    state: _SteeringState,
    point: PausePoint,
    run_id: uuid.UUID | None,
    verdict: str,
    reason: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one ``agent_judgement_routed`` event (the rebuild's observed marker)."""
    base = steering_events.base_payload(
        capability_run_id=capability_run_id,
        plan_id=state.plan_id,
        plan_version=state.plan_version,
        boundary=point.boundary,
        component=point.component,
    )
    payload = {**base, "verdict": verdict, "reason": reason}
    if extra:
        payload.update(extra)
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.AGENT_JUDGEMENT_ROUTED,
        payload=payload,
    )


def _watch_observe_boundary(
    engine: Engine,
    *,
    orchestrator: OrchestratorBackend,
    point: PausePoint,
    state: _SteeringState,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    successful_runs: dict[str, uuid.UUID],
    backends: RunnerBackends,
    capability_run_id: uuid.UUID,
    event_run_id: uuid.UUID | None,
    steer_point_name: str | None,
    triggers: list[dict[str, Any]],
    is_decision_point: bool,
    anomalous: bool,
) -> _WatchObservation:
    """Observe one attended boundary under the gated-invocation model (Task 14).

    Classifies the boundary (:func:`classify_boundary`) and emits the matching
    ``agent_judgement_routed`` event:

    - **decision_point** (a lattice pause the user will see): the watch AUTHORS 2–5
      run-specific options on the canonical floor, returned in the observation (or
      ``None`` on authoring failure — the canonical menu is then unchanged, never
      blocked). The built bundle rides back for the pause to reuse (FIX 2b).
    - **triage** (trigger-fired or anomalous, not a decision point): a mini-class
      notable-or-not verdict — ``triaged_not_notable`` proceeds; notable PROMOTES
      (the m6 rule), and the observation carries ``promoted=True`` so an attended
      caller escalates to a pause (FIX 2). Triage makes no tool calls.
    - **clean_boundary**: a deterministic no-LLM event.

    ANY backend exception degrades to the deterministic floor (watch discipline 5):
    a ``watch_error`` verdict is recorded and the run proceeds exactly as it would
    with no orchestrator.
    """
    verdict = classify_boundary(
        is_decision_point=is_decision_point,
        triggers_fired=bool(triggers),
        anomalous=anomalous,
    )
    if verdict == "clean_boundary":
        _emit_judgement_routed(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            state=state,
            point=point,
            run_id=event_run_id,
            verdict="clean_boundary",
            reason="structurally resolved",
        )
        return _WatchObservation()

    header = _watch_header(state)
    digest = _watch_digest(engine, project_id=project_id, capability_run_id=capability_run_id)

    if verdict == "decision_point":
        bundle = (
            _build_bundle(
                engine,
                name=steer_point_name,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                successful_runs=successful_runs,
                backends=backends,
                section_budget=state.plan.section_budget,
            )
            if steer_point_name is not None
            else None
        )
        try:
            result = run_watch_decision(
                orchestrator,
                request=f"author suggested options at {steer_point_name}",
                header=header,
                payload={"steer_point": steer_point_name, "triggers": triggers, "bundle": bundle},
                digest=digest,
                framing="authoring",
                read_tools=None,
            )
            authored = result.decision.authored_options
        except Exception as exc:  # noqa: BLE001 — authoring failure degrades to the floor
            log.warning(
                "orchestrator.authoring_failed",
                steer_point=steer_point_name,
                error=str(exc)[:200],
            )
            _emit_judgement_routed(
                engine,
                project_id=project_id,
                capability_run_id=capability_run_id,
                state=state,
                point=point,
                run_id=event_run_id,
                verdict="decision_point",
                reason="authoring failed — canonical menu unchanged",
                extra={"authored": False},
            )
            # The bundle still rides back so the pause reuses it (FIX 2b).
            return _WatchObservation(bundle=bundle)
        authored_dicts = _validated_authored_options(
            engine,
            authored=authored,
            state=state,
            point=point,
            steer_point_name=steer_point_name,
            project_id=project_id,
            capability_run_id=capability_run_id,
            run_id=event_run_id,
        )
        _emit_judgement_routed(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            state=state,
            point=point,
            run_id=event_run_id,
            verdict="decision_point",
            reason="watch authored options on the canonical floor",
            extra={
                "authored": bool(authored_dicts),
                "authored_by": "orchestrator",
                "authored_options": authored_dicts,
                "execution_profile": {
                    "prompt_version": WATCH_AUTHORING_PROMPT_VERSION,
                },
            },
        )
        return _WatchObservation(authored_options=authored_dicts, bundle=bundle)

    # triage
    try:
        triage = orchestrator.triage(
            f"triage this boundary at {point.component}",
            header,
            {"steer_point": steer_point_name, "triggers": triggers, "anomalous": anomalous},
            digest,
        )
    except Exception as exc:  # noqa: BLE001 — triage failure degrades to the floor
        log.warning("orchestrator.triage_failed", component=point.component, error=str(exc)[:200])
        _emit_judgement_routed(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            state=state,
            point=point,
            run_id=event_run_id,
            verdict="watch_error",
            reason="triage failed — proceeding on the deterministic floor",
        )
        return _WatchObservation()
    if triage.notable:
        _emit_judgement_routed(
            engine,
            project_id=project_id,
            capability_run_id=capability_run_id,
            state=state,
            point=point,
            run_id=event_run_id,
            verdict="promoted",
            reason=triage.reason,
        )
        # FIX 2: the promotion escalates an attended non-decision boundary to a pause.
        return _WatchObservation(promoted=True, promoted_reason=triage.reason)
    _emit_judgement_routed(
        engine,
        project_id=project_id,
        capability_run_id=capability_run_id,
        state=state,
        point=point,
        run_id=event_run_id,
        verdict="triaged_not_notable",
        reason=triage.reason,
    )
    return _WatchObservation()


def _validated_authored_options(
    engine: Engine,
    *,
    authored: list[Any] | None,
    state: _SteeringState,
    point: PausePoint,
    steer_point_name: str | None,
    project_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    run_id: uuid.UUID | None,
) -> list[dict[str, Any]] | None:
    """Validate and cap watch suggestions before they enter a durable pause."""
    if not authored:
        return None
    ctx = SteeringValidationCtx(
        backend_scope=state.plan.backend_scope,
        current_components=set(state.chain.components),
        completed_components=set(),
        rerun_surface=RerunSurface(replacement_component=None, segment_reentry_available=False),
    )
    kept: list[dict[str, Any]] = []
    for index, wire in enumerate(authored):
        raw = wire.model_dump() if hasattr(wire, "model_dump") else dict(wire)
        if len(kept) >= 2:
            reason = "authored option cap is two per pause"
        elif isinstance(raw.get("endorses_option_id"), str) and raw.get("endorses_option_id"):
            # An endorsement picks an existing canonical option; its own
            # component/delta are discarded at projection, so none is required
            # (review 028 C4 — requiring one made honest endorsements
            # unserialisable). Strip any padding so nothing unvalidated rides
            # into the durable pause payload.
            raw["component"] = None
            raw["delta"] = None
            reason = None
        else:
            component, delta = raw.get("component"), raw.get("delta")
            try:
                if not isinstance(component, str) or not isinstance(delta, dict):
                    raise SteeringDeltaInvalid(
                        "authored option must name a component and object delta"
                    )
                validate_steering_delta(delta, component, ctx)
                reason = None
            except SteeringDeltaInvalid as exc:
                reason = str(exc)
        if reason is not None:
            log.warning(
                "steering.authored_option_dropped", steer_point=steer_point_name, reason=reason
            )
            if run_id is not None:
                steering_events.emit_standalone(
                    engine,
                    project_id=project_id,
                    run_id=run_id,
                    event_type="authored_option_dropped",
                    payload={
                        **steering_events.base_payload(
                            capability_run_id=capability_run_id,
                            plan_id=state.plan_id,
                            plan_version=state.plan_version,
                            boundary=point.boundary,
                            component=point.component,
                        ),
                        "reason": reason,
                        "option_index": index,
                    },
                )
            continue
        raw["id"] = f"suggested_{index + 1}"
        kept.append(raw)
    return kept or None


def _watch_header(state: _SteeringState) -> dict[str, Any]:
    """The orienting header the watch decides against (data, never instructions)."""
    plan = state.plan
    return {
        "question": plan.question,
        "steering_mode": plan.steering_mode,
        "components": list(plan.components),
        "standing_instructions": [
            {"steer_point": default.steer_point, "action": default.action}
            for default in plan.steer_point_defaults
        ],
    }


def _watch_digest(
    engine: Engine, *, project_id: uuid.UUID, capability_run_id: uuid.UUID
) -> dict[str, Any]:
    """The run-so-far digest — prior steering decisions for this walk (decision memory)."""
    walk_key = str(capability_run_id)
    with engine.connect() as conn:
        prior = [
            {
                "boundary": entry["payload"].get("boundary"),
                "component": entry["payload"].get("component"),
                "decided_by": entry["payload"].get("decided_by"),
                "response": entry["payload"].get("response"),
            }
            for entry in events.read(
                conn, project_id, event_types=[steering_events.STEERING_DECISION]
            )
            if entry["payload"].get("capability_run_id") == walk_key
        ]
    return {"prior_decisions": prior}


def _watch_flag(component: str, steer_point: str, *, rule: str, action: str) -> dict[str, Any]:
    """One auto-resolution flag for a watch (orchestrator) decision in the collation."""
    return {
        "component": component,
        "status": "auto_resolved",
        "steer_point": steer_point,
        "rule": rule,
        "action": action,
        "authored_by": "orchestrator",
    }


def _watch_extra(outcome: _DiscretionOutcome, *, triggers: list[dict[str, Any]]) -> dict[str, Any]:
    """The attribution payload a watch decision carries (reasoning, trail, profile)."""
    extra: dict[str, Any] = {"triggers": triggers}
    if outcome.reasoning is not None:
        extra["reasoning"] = outcome.reasoning
    if outcome.deliberation:
        extra["deliberation"] = outcome.deliberation
    if outcome.profile is not None:
        extra["execution_profile"] = outcome.profile
    return extra


def _emit_orchestrator_proceed_decision(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID | None,
    base: dict[str, Any],
    outcome: _DiscretionOutcome,
    triggers: list[dict[str, Any]],
) -> None:
    """Append an orchestrator-attributed proceed/escalate decision (no state partner)."""
    payload = steering_events.decision_payload(
        base,
        decided_by="orchestrator",
        authored_by="orchestrator",
        response="continue",
        interpreted_action=outcome.interpreted_action,
        confirmed=True,
        rerun_mode=None,
    )
    payload.update(_watch_extra(outcome, triggers=triggers))
    payload["orchestrator_rule"] = outcome.rule
    steering_events.emit_standalone(
        engine,
        project_id=project_id,
        run_id=run_id,
        event_type=steering_events.STEERING_DECISION,
        payload=payload,
    )


def _apply_discretion_outcome(
    engine: Engine,
    *,
    outcome: _DiscretionOutcome,
    point: PausePoint,
    name: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    flagged_events: list[dict[str, Any]],
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    allow_segment_reentry: bool,
    triggers: list[dict[str, Any]],
    rerun_component: str | None = None,
) -> _PauseApplied:
    """Route a no-pinned-rule discretion outcome — deterministic floor OR watch.

    ``outcome.profile is not None`` marks an outcome the watch actually decided
    (attributed to the orchestrator); its absence is the deterministic floor (or a
    fail-safe degrade to it), attributed to ``standing_default`` — byte-identical to
    the Task-12 behaviour. An ``apply`` action routes the watch's authored delta
    through the SAME apply machinery a standing rule uses.
    """
    watch_decided = outcome.profile is not None
    if outcome.interpreted_action == "apply" and outcome.delta:
        return _apply_watch_delta(
            engine,
            outcome=outcome,
            point=point,
            name=name,
            state=state,
            project_id=project_id,
            completed_components=completed_components,
            flagged_events=flagged_events,
            base=base,
            event_run_id=event_run_id,
            selection_run_id=selection_run_id,
            allow_segment_reentry=allow_segment_reentry,
            triggers=triggers,
            rerun_component=rerun_component,
        )
    if watch_decided:
        _emit_orchestrator_proceed_decision(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            outcome=outcome,
            triggers=triggers,
        )
        flagged_events.append(
            _watch_flag(point.component, name, rule=outcome.rule, action="proceed")
        )
        return _PauseApplied(state=state)
    _emit_standing_proceed_decision(
        engine,
        project_id=project_id,
        run_id=event_run_id,
        base=base,
        interpreted_action=outcome.interpreted_action,
        standing_rule={"rule": outcome.rule},
        triggers=triggers,
    )
    flagged_events.append(
        _standing_flag(point.component, name, rule=outcome.rule, action="proceed")
    )
    return _PauseApplied(state=state)


def _apply_watch_delta(
    engine: Engine,
    *,
    outcome: _DiscretionOutcome,
    point: PausePoint,
    name: str,
    state: _SteeringState,
    project_id: uuid.UUID,
    completed_components: set[str],
    flagged_events: list[dict[str, Any]],
    base: dict[str, Any],
    event_run_id: uuid.UUID | None,
    selection_run_id: uuid.UUID | None,
    allow_segment_reentry: bool,
    triggers: list[dict[str, Any]],
    rerun_component: str | None = None,
) -> _PauseApplied:
    """Apply a watch-authored delta through the standing-rule apply machinery.

    Mirrors :func:`_apply_standing_proceed`'s routing (replacement re-run of the
    point's re-run component · additive segment re-entry · pending-component
    adjustment) but takes the raw authored delta and attributes the decision to
    the orchestrator (``decided_by``/``authored_by`` = ``orchestrator``), carrying
    the verbatim reasoning + deliberation trail + execution profile. The watch's
    delta is author-blind-validated by the SAME fail-closed grammars user input
    takes: an out-of-grammar delta raises :class:`SteeringAdjustmentError`, is
    evented as ``steering.rejected`` and degrades to proceed-and-flag (watch
    discipline 5) — never crashing the run.
    """
    effective = outcome.delta or {}
    extra = _watch_extra(outcome, triggers=triggers)
    if not effective:
        _emit_orchestrator_proceed_decision(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            outcome=outcome,
            triggers=triggers,
        )
        flagged_events.append(
            _watch_flag(point.component, name, rule=outcome.rule, action="proceed")
        )
        return _PauseApplied(state=state)

    keys = set(effective)
    # A watch-authored delta is single-nested in the component's own grammar
    # ({"selection": ...} / {"characterise": ...} / {"grouping": ...}); it is a
    # replacement re-run when it targets the point's re-run component's context
    # key (select at P3, characterise at P2, group at P4 — Task 15b).
    watch_replacement = rerun_component is not None and keys == {
        REPLACEMENT_RERUNS[rerun_component].context_key
    }
    try:
        if watch_replacement:
            assert rerun_component is not None
            rerun_state, merged = _apply_replacement_rerun(
                engine,
                project_id=project_id,
                state=state,
                adjustment=Adjust(directive_deltas={rerun_component: effective}),
                base=base,
                event_run_id=event_run_id,
                component=rerun_component,
                decided_by="orchestrator",
                authored_by="orchestrator",
                extra_payload=extra,
            )
            flagged_events.append(
                _watch_flag(rerun_component, name, rule=outcome.rule, action="apply")
            )
            return _PauseApplied(
                state=rerun_state, rerun={"component": rerun_component, "directive": merged}
            )
        if (
            allow_segment_reentry
            and keys == {SHIPPED_SEGMENT_START}
            and SHIPPED_SEGMENT_START in completed_components
        ):
            response = ReEnterSegment(directive_deltas=effective)
            reentry_state = _apply_segment_reentry(
                engine,
                project_id=project_id,
                state=state,
                response=response,
                base=base,
                event_run_id=event_run_id,
                completed_components=completed_components,
                boundary_component=point.component,
                decided_by="orchestrator",
                authored_by="orchestrator",
                extra_payload=extra,
            )
            flagged_events.append(
                _watch_flag(point.component, name, rule=outcome.rule, action="apply")
            )
            return _PauseApplied(
                state=reentry_state,
                segment_reentry={
                    "segment_start": response.segment_start,
                    "boundary_component": point.component,
                    "directive_deltas": response.directive_deltas,
                },
            )
        amended_state = _apply_runner_adjustment(
            engine,
            project_id=project_id,
            state=state,
            adjustment=Adjust(directive_deltas=effective),
            completed_components=completed_components,
            base=base,
            event_run_id=event_run_id,
            decided_by="orchestrator",
            authored_by="orchestrator",
            extra_payload=extra,
        )
        flagged_events.append(_watch_flag(point.component, name, rule=outcome.rule, action="apply"))
        return _PauseApplied(state=amended_state, changed=True)
    except SteeringAdjustmentError as exc:
        # Author-blind fail-safe: an out-of-grammar or unexecutable watch delta is
        # rejected on the record and degrades to proceed-and-flag (watch discipline 5).
        _emit_rejected(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            exc=exc,
            offending_delta=effective,
        )
        _emit_orchestrator_proceed_decision(
            engine,
            project_id=project_id,
            run_id=event_run_id,
            base=base,
            outcome=outcome,
            triggers=triggers,
        )
        flagged_events.append(
            _watch_flag(point.component, name, rule=outcome.rule, action="rejected")
        )
        return _PauseApplied(state=state)


def _remaining_steps(
    chain: ComposedChain,
    *,
    completed_components: set[str],
) -> list[ComponentStep]:
    return [step for step in chain.steps if step.component not in completed_components]


def _search_round_continues(
    engine: Engine,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    plan: OrchestrationPlan,
    successful_runs: dict[str, uuid.UUID],
) -> bool:
    """Evaluate the multi-round search gate after a completed screen round.

    Standard and deep runs repeat the acquire → screen_abstract pair until the
    depth's ``round_cap`` (standard 2 / deep 3) or a yield collapse
    (``short_circuit``). ``run_search`` derives each round's index from the
    scope's coverage rows, so a second acquire run is automatically round 2 and
    unlocks the reformulate/snowball/suggest/diversity arms — the gate only
    decides whether to run it.

    Every input is recomputed from persisted state (coverage rows, the screen
    run's own screening rows and completed payload), never from walk-local
    memory, so a run parked mid-loop resumes at the correct round.

    On a stop, writes the loop-level stop condition onto the final round's
    coverage row (``finalise_deep_stop``), with the thin-evidence overlay keyed
    to ``THIN_CONFIDENT_RELEVANT``.

    Args:
        engine: Engine for the short evaluation reads and the stop write.
        project_id: Owning project.
        evidence_scope_id: Scope being searched.
        plan: Current orchestration plan; ``search_effort`` picks the budget.
        successful_runs: Per-component last successful run ids.

    Returns:
        ``True`` when another acquire+screen round should run.
    """
    round_cap = DEPTH_CONSTANTS[plan.search_effort]["round_cap"]
    screen_run_id = successful_runs.get("screen_abstract")
    if screen_run_id is None:
        # No completed screen round to evaluate — nothing to loop on.
        return False
    with engine.connect() as conn:
        rounds_done = count_existing_rounds(
            conn, project_id=project_id, scope_id=evidence_scope_id
        )
        confident = confident_relevant_count(
            conn, project_id=project_id, scope_id=evidence_scope_id
        )
        new_confident = new_confident_relevant_for_run(
            conn,
            project_id=project_id,
            scope_id=evidence_scope_id,
            run_id=screen_run_id,
        )
        screen_payload = _find_component_payload(
            events.read_for_run(conn, project_id, screen_run_id),
            "screen",
            event_type="component.completed",
            run_id=screen_run_id,
        )
    if rounds_done == 0 or screen_payload is None:
        # Acquire never produced a coverage row, or the screen summary is
        # missing — no honest denominator, so no loop. The chain proceeds.
        return False
    decision = evaluate_deep_stop(
        round_index=rounds_done,
        new_confident_relevant=new_confident,
        docs_screened_this_round=docs_screened_from_payload(screen_payload),
        round_cap=round_cap,
    )
    if not decision.stop:
        log.info(
            "search.round_continue",
            project_id=str(project_id),
            round_completed=rounds_done,
            round_cap=round_cap,
            confident_relevant=confident,
        )
        return True
    if decision.stop_condition is None:  # pragma: no cover - StopDecision invariant
        raise RuntimeError("round stop decision missing stop_condition")
    with engine.begin() as conn:
        final = finalise_deep_stop(
            conn,
            project_id=project_id,
            scope_id=evidence_scope_id,
            stop_condition=decision.stop_condition,
            thin=confident < THIN_CONFIDENT_RELEVANT,
        )
    log.info(
        "search.rounds_stopped",
        project_id=str(project_id),
        rounds=rounds_done,
        stop_condition=final,
        confident_relevant=confident,
    )
    return False


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
        events.append(
            conn,
            project_id=project_id,
            run_id=None,
            event_type="run.opened",
            payload={
                "capability_run_id": str(capability_run_id),
                "plan_id": str(plan_id),
                "plan_version": plan_version,
            },
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
        events.append(
            conn,
            project_id=project_id,
            run_id=None,
            event_type="run.finished",
            payload={"capability_run_id": str(capability_run_id), "status": status},
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
    overlay: dict[str, Any] | None = None,
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
        overlay=overlay,
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

    # Lifecycle events deliberately bracket, rather than participate in, the
    # component transaction. This makes stage.started visible to the live SSE
    # tail while work is in flight and leaves started->failed coherent if the
    # component transaction is rolled back before its node can record failure.
    with engine.begin() as conn:
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="component.started",
            payload={"component": registry_component},
        )
    log.info(
        "component.started",
        component=step.component,
        registry_component=registry_component,
        run_id=str(run_id),
    )

    started = time.monotonic()
    component_summary: dict[str, Any] | None = None
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
                harness_outcome = run_harness(
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
                    progress_emitter=(
                        ProgressEmitter(engine, project_id=project_id, run_id=run_id)
                        if registry_component == "synthesise"
                        else None
                    ),
                )
                summary = harness_outcome.get("summary")
                component_summary = summary if isinstance(summary, dict) else None
        if registry_component == "synthesise" and component_summary is not None:
            try:
                summary_accounting = write_summaries_after_commit(
                    engine,
                    project_id=project_id,
                    run_id=run_id,
                    synthesis_backend=(
                        backends.synthesis
                        if backends.synthesis is not None
                        else StubSynthesisBackend()
                    ),
                )
                component_usage = component_summary.get("usage_totals")
                if isinstance(component_usage, dict):
                    merged_usage = UsageAccumulator()
                    merged_usage.add_payload(component_usage)
                    summary_usage = summary_accounting.get("usage_totals")
                    if isinstance(summary_usage, dict):
                        merged_usage.add_payload(summary_usage)
                    component_summary["usage_totals"] = merged_usage.payload()
                component_summary["summary_usage_totals"] = summary_accounting.get(
                    "usage_totals", UsageAccumulator().payload()
                )
            except Exception as exc:  # noqa: BLE001 - summaries never fail a component
                log.warning(
                    "runner.summaries_degraded",
                    project_id=str(project_id),
                    run_id=str(run_id),
                    error=_bounded_error(exc),
                )
        # A successful harness result has committed with the component work;
        # append its terminal lifecycle event separately so the payload remains
        # byte-identical to the former node-level append.
        if component_summary is not None:
            with engine.begin() as conn:
                events.append(
                    conn,
                    project_id=project_id,
                    run_id=run_id,
                    event_type="component.completed",
                    payload={"component": registry_component, **component_summary},
                )
            log.info(
                "component.completed",
                component=step.component,
                registry_component=registry_component,
                run_id=str(run_id),
                **component_summary,
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
    overlay: dict[str, Any] | None = None,
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
    # Provenance echo (task 024, 15c): when a pending commit-layer overlay was
    # merged into the executed directive, record it so replay shows the merge.
    if overlay:
        payload["pending_overlay"] = overlay
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
        "completion": usage["completion"] if isinstance(usage.get("completion"), int) else 0,
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
