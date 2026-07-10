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
from typing import Any, Literal, Protocol

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
from policy_atlas.orchestration_plan import (
    _REGISTRY_COMPONENT_BY_STEP,
    ComponentStep,
    OrchestrationPlan,
    compose,
)
from policy_atlas.plan import Plan, compile
from policy_atlas.ranking import RankingBackend
from policy_atlas.schema import event_log, evidence_scope, runs
from policy_atlas.screening_backend import ScreeningBackend
from policy_atlas.search_generation import SearchGenerationBackend
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
SPINE_COMPONENTS = frozenset(
    {"acquire", "screen", "classify", "appraise", "ingest_full_text", "synthesise"}
)
DISCRETIONARY_REQUIREMENTS = {
    "select": "characterise",
    "extract": "select",
    "group": "extract",
}

RunPlanStatus = Literal["succeeded", "degraded", "failed"]
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
    facet_grouping: FacetGroupingBackend | None = None
    synthesis: SynthesisBackend | None = None
    grounding_judge: GroundingJudgeBackend | None = None
    search_backends: list[SearchBackend] | None = None
    search_generation: SearchGenerationBackend | None = None
    document_fetcher: DocumentFetcher | None = None
    langfuse_client: Langfuse | None = None


class OrchestratorIO(Protocol):
    """Minimal runner-to-orchestrator IO seam.

    Sub-agents do not address users directly. The runner reports deterministic
    component boundary outcomes through this protocol; later steering work can
    extend this seam without changing the harness contract.
    """

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Report a component boundary outcome.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload containing status and
                headline counts.
        """
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
    """

    status: RunPlanStatus
    steps: list[RunStepOutcome]
    flagged_events: list[dict[str, Any]]


@dataclass
class _AttemptOutcome:
    run_id: uuid.UUID
    status: Literal["succeeded", "failed"]
    wall_clock_s: float
    headline_counts: dict[str, Any]
    error: str | None


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
    backends: RunnerBackends | None = None,
    io: OrchestratorIO | None = None,
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
        backends: Optional backend seam bundle. ``None`` uses harness defaults.
        io: Optional orchestrator IO seam. ``None`` uses ``NullIO``.

    Returns:
        Overall status, ordered step outcomes and collated flags.
    """
    backend_bundle = backends if backends is not None else RunnerBackends()
    io_sink = io if io is not None else NullIO()
    chain = compose(plan)
    step_outcomes: list[RunStepOutcome] = []
    flagged_events: list[dict[str, Any]] = []
    successful_runs: dict[str, uuid.UUID] = {}
    blocked_discretionary: dict[str, str] = {}

    for step in chain.steps:
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
            _check_in(io_sink, outcome, headline_counts={"reason": skip_reason})
            continue

        upstream_state = {"successful_run_ids": dict(successful_runs)}
        directive_delta = leg_directive(plan, step, upstream_state)
        reference_kwargs = _reference_kwargs(step.component, successful_runs)
        retry_cap = COMPONENT_RETRY_CAP if step.component in LLM_BEARING_COMPONENTS else 0

        attempts: list[_AttemptOutcome] = []
        for attempt_index in range(retry_cap + 1):
            attempt = _run_step_attempt(
                engine,
                project_id=project_id,
                evidence_scope_id=evidence_scope_id,
                plan=plan,
                plan_id=plan_id,
                plan_version=plan_version,
                step=step,
                directive_delta=directive_delta,
                reference_kwargs=reference_kwargs,
                backends=backend_bundle,
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
            _check_in(io_sink, outcome, headline_counts=final_attempt.headline_counts)
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
        _check_in(io_sink, outcome, headline_counts=final_attempt.headline_counts)

        if step.component in SPINE_COMPONENTS:
            summary_status: RunPlanStatus = "failed"
            _log_run_summary(step_outcomes, status=summary_status)
            return RunPlanOutcome(
                status=summary_status,
                steps=step_outcomes,
                flagged_events=flagged_events,
            )
        blocked_discretionary[step.component] = reason

    summary_status = (
        "degraded"
        if any(outcome.status in {"failed", "skipped"} for outcome in step_outcomes)
        else "succeeded"
    )
    _log_run_summary(step_outcomes, status=summary_status)
    return RunPlanOutcome(
        status=summary_status,
        steps=step_outcomes,
        flagged_events=flagged_events,
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
            log_entries = events.read(conn, project_id)
        return _AttemptOutcome(
            run_id=run_id,
            status="failed",
            wall_clock_s=wall_clock_s,
            headline_counts=_headline_counts(log_entries, registry_component, run_id=run_id),
            error=error,
        )
    wall_clock_s = time.monotonic() - started

    with engine.connect() as conn:
        status = conn.execute(select(runs.c.status).where(runs.c.run_id == run_id)).scalar_one()
        log_entries = events.read(conn, project_id)

    headline_counts = _headline_counts(log_entries, registry_component, run_id=run_id)
    failure_error = _failure_error(log_entries, registry_component, run_id=run_id)
    if status == "succeeded":
        return _AttemptOutcome(
            run_id=run_id,
            status="succeeded",
            wall_clock_s=wall_clock_s,
            headline_counts=headline_counts,
            error=None,
        )
    return _AttemptOutcome(
        run_id=run_id,
        status="failed",
        wall_clock_s=wall_clock_s,
        headline_counts=headline_counts,
        error=failure_error,
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
    io: OrchestratorIO,
    outcome: RunStepOutcome,
    *,
    headline_counts: dict[str, Any],
) -> None:
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
