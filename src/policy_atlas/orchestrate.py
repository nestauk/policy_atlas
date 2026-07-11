"""The orchestrator CLI — the one new public interface of slice 017.

Runnable as ``python -m policy_atlas.orchestrate``. It owns the whole
user-facing product path: a planning conversation (intent -> refined,
depth-graded orchestration plan), plan review and approval, and driving the EB
capability-runner with steering check-ins. Sub-agents never address the user;
the orchestrator relays deterministic runner check-ins and steering pauses
through a small, injectable console seam.

Live switch mirrors ``skeleton.py``: a configured ``OPENAI_API_KEY`` selects the
live planner + live backend set (with Langfuse tracing); its absence selects the
deterministic stubs and an egress-free fixture corpus, so the demo/dev path
never leaves the machine.
"""

from __future__ import annotations

import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

import structlog
from pydantic import ValidationError
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Engine

from policy_atlas import search_generation, search_live, tracing
from policy_atlas.acquire import SearchBackend
from policy_atlas.classification_backend import OpenAIClassificationBackend
from policy_atlas.db import get_engine
from policy_atlas.embeddings import EmbeddingBackend, OpenAIEmbeddingBackend
from policy_atlas.extraction_backend import OpenAIExtractionBackend
from policy_atlas.facet_grouping import OpenAIFacetGroupingBackend
from policy_atlas.fetch_live import LiveDocumentFetcher
from policy_atlas.finding_vetter import OpenAIFindingVetterBackend
from policy_atlas.fixtures import get_source
from policy_atlas.grounding_judge import OpenAIGroundingJudgeBackend
from policy_atlas.grouping import OpenAIThemeGroupingBackend, ThemeGroupingBackend
from policy_atlas.ingest import ingest_upload
from policy_atlas.logging import configure_logging
from policy_atlas.orchestration_plan import OrchestrationPlan
from policy_atlas.planner import OpenAIPlannerBackend, PlannerBackend, StubPlannerBackend
from policy_atlas.planner_prompt import PLANNER_HISTORY_TURNS_MAX, PlanDraftWire
from policy_atlas.ranking import OpenAIRankingBackend
from policy_atlas.runner import RunnerBackends, RunPlanOutcome, run_plan
from policy_atlas.schema import artefact, evidence_scope, orchestration_plan, project
from policy_atlas.screening_backend import OpenAIScreeningBackend
from policy_atlas.steering import (
    Abort,
    Adjust,
    Continue,
    SteeringResponse,
    refuse_inexpressible,
    render_check_in,
)
from policy_atlas.synthesis_backend import OpenAISynthesisBackend

log = structlog.get_logger()

# Cap the planning conversation so a planner that never returns ``ready`` (or a
# plan that never validates) fails honestly instead of looping forever.
MAX_PLANNER_TURNS = 10

# The prompt's history window must hold every turn a conversation can have
# accumulated when the planner is called (1 intent + 2 per completed
# iteration): if it rotated, the original intent would silently drop and the
# intent-sized first-turn cap would land on a mid-conversation turn.
assert (MAX_PLANNER_TURNS - 1) * 2 + 1 <= PLANNER_HISTORY_TURNS_MAX

# Exit codes. No token/cost surface — time only (contract decision 11).
EXIT_SUCCESS = 0
EXIT_RUN_FAILED = 2
EXIT_ABORTED = 3
EXIT_ABANDONED = 4
EXIT_NO_PLAN = 2  # planner never converged on an approved, valid plan

_EXIT_BY_STATUS: dict[str, int] = {
    "succeeded": EXIT_SUCCESS,
    "degraded": EXIT_SUCCESS,
    "failed": EXIT_RUN_FAILED,
    "aborted": EXIT_ABORTED,
}

_STEERING_MODES = frozenset({"frequent", "moderate", "minimal", "unattended"})

# The egress-free demo/dev corpus, mirroring skeleton.py's ingest_upload seed:
# two synthetic full-text reviews the stub classify/appraise path scores so the
# chain has an appraised, screened-in corpus to run over.
_STUB_CORPUS: tuple[tuple[str, str], ...] = (
    ("syn-001", "Synthetic policy review"),
    ("syn-002", "Synthetic review of housing affordability policies"),
)


def _now() -> datetime:
    return datetime.now(UTC)


class ConsoleIO(Protocol):
    """Console seam for the planning conversation and steering menus.

    The ``python -m`` entrypoint injects a stdin/stdout implementation;
    scripted tests inject a deterministic double.
    """

    def prompt(self, message: str) -> str:
        """Print ``message`` and return one line of user input."""
        ...

    def print(self, message: str) -> None:
        """Print one line of orchestrator output."""
        ...


def _strip_control(text: str) -> str:
    return "".join(
        ch
        for ch in text
        if ch in ("\n", "\t") or (ch >= " " and ch != "\x7f" and not ("\x80" <= ch <= "\x9f"))
    )


class StdConsole:
    """Real stdin/stdout console used by ``python -m policy_atlas.orchestrate``."""

    def prompt(self, message: str) -> str:
        """Print ``message`` and read one line from stdin.

        Args:
            message: The prompt to display.

        Returns:
            The user's line, without the trailing newline.
        """
        return input(message)

    def print(self, message: str) -> None:
        """Write one line to stdout, stripped of terminal control characters.

        Planner output is untrusted model text; escape sequences could rewrite
        or hide the very plan lines the user is approving, so everything but
        newlines and tabs in the C0/C1/DEL ranges is dropped at this seam.

        Args:
            message: The text to print.
        """
        print(_strip_control(message))


@dataclass
class OrchestrateResult:
    """Structured result of one orchestrator session (testability seam).

    Args:
        exit_code: Process exit code the ``python -m`` entrypoint returns.
        plan: The approved orchestration plan, or ``None`` if none was approved.
        plan_id: The persisted orchestration-plan row id, or ``None``.
        project_id: The created project id, or ``None`` if nothing was created.
        evidence_scope_id: The created evidence-scope id, or ``None``.
        outcome: The runner outcome, or ``None`` if no run was launched.
        turns: The full planning-conversation turn log.
        runner_io: The steering IO used for the run (``CliIO``/``UnattendedIO``),
            or ``None`` if no run was launched.
        artefact_present: Whether a synthesis artefact row exists for the project.
        conversation_id: Langfuse session id minted for this orchestrator conversation.
    """

    exit_code: int
    plan: OrchestrationPlan | None = None
    plan_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    evidence_scope_id: uuid.UUID | None = None
    outcome: RunPlanOutcome | None = None
    turns: list[dict[str, str]] = field(default_factory=list)
    runner_io: CliIO | UnattendedIO | None = None
    artefact_present: bool = False
    conversation_id: uuid.UUID | None = None


class CliIO:
    """Attended steering IO: relays check-ins and blocks for pause decisions.

    Args:
        console: The console seam the pauses render through.
    """

    def __init__(self, console: ConsoleIO) -> None:
        self._console = console
        self.pause_calls = 0

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Relay one deterministic runner check-in to the console.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload.
        """
        del component
        self._console.print(render_check_in(payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """Render a steering boundary as a numbered menu and map the answer.

        Continue / the intent-vocabulary steer-point options / change mode /
        abort are numbered; free text matching nothing is answered with the
        honest not-yet-expressible refusal and re-prompted.

        Args:
            point: Pause-point payload (``options`` present at a steer point).
            render: Deterministic pause render.

        Returns:
            The mapped steering response.
        """
        self.pause_calls += 1
        options = cast(list[dict[str, Any]], point.get("options") or [])
        while True:
            lines = [render, "Steering options:", "  1) Continue"]
            option_by_num: dict[int, dict[str, Any]] = {}
            num = 2
            for option in options:
                lines.append(f"  {num}) {option['label']} — {option['description']}")
                option_by_num[num] = option
                num += 1
            mode_num = num
            lines.append(f"  {num}) Change steering mode")
            num += 1
            abort_num = num
            lines.append(f"  {num}) Abort")
            self._console.print("\n".join(lines))

            raw = self._console.prompt("Choose an option: ").strip()
            key = raw.lower()
            if key in ("1", "continue"):
                return Continue()
            if key in (str(abort_num), "abort"):
                return Abort()
            if key in (str(mode_num), "mode"):
                return self._prompt_mode()
            if raw.isdigit() and int(raw) in option_by_num:
                response = self._option_to_response(option_by_num[int(raw)])
                if response is not None:
                    return response
                continue
            self._console.print(refuse_inexpressible(raw))

    def _prompt_mode(self) -> SteeringResponse:
        raw = self._console.prompt(
            "New steering mode [frequent/moderate/minimal/unattended]: "
        ).strip().lower()
        return Adjust(new_mode=raw)

    def _option_to_response(self, option: dict[str, Any]) -> SteeringResponse | None:
        delta = cast(dict[str, Any], option.get("delta") or {})
        if not delta:
            # "As proposed" — continue with the current selection unchanged.
            return Continue()
        if option.get("requires_user_input"):
            filled = self._fill_option_delta(option)
            if filled is None:
                return None
            delta = filled
        return Adjust(directive_deltas={"select": delta})

    def _fill_option_delta(self, option: dict[str, Any]) -> dict[str, Any] | None:
        if option["id"] == "adjust_budget":
            raw = self._console.prompt("New selection budget: ").strip()
            if not raw.isdigit():
                self._console.print(refuse_inexpressible(raw))
                return None
            return {"selection": {"budget": int(raw)}}
        if option["id"] == "deepen_clusters":
            strata = _split_ids(self._console.prompt("Cluster ids (comma-separated): "))
            docs = _split_ids(self._console.prompt("Document ids to force-include: "))
            return {"selection": {"priority_strata": strata, "must_include_ids": docs}}
        return cast(dict[str, Any], option["delta"])


class UnattendedIO:
    """Unattended steering IO: relays check-ins; a pause is a honesty violation.

    Unattended plans have no pause points, so the runner never calls ``pause``.
    If it ever does, that is a runner regression — this implementation raises.

    Args:
        console: The console seam check-ins render through.
    """

    def __init__(self, console: ConsoleIO) -> None:
        self._console = console
        self.pause_calls = 0

    def check_in(self, component: str, payload: dict[str, Any]) -> None:
        """Relay one deterministic runner check-in to the console.

        Args:
            component: Orchestration step name.
            payload: Deterministic outcome payload.
        """
        del component
        self._console.print(render_check_in(payload))

    def pause(self, point: dict[str, Any], render: str) -> SteeringResponse:
        """Raise: an unattended run must never reach a steering pause.

        Args:
            point: Pause-point payload.
            render: Deterministic pause render.

        Returns:
            Never returns.

        Raises:
            AssertionError: Always — unattended mode compiles no pause points.
        """
        del point, render
        self.pause_calls += 1
        raise AssertionError("UnattendedIO.pause called: unattended runs must not pause")


def _split_ids(raw: str) -> list[str]:
    return [token.strip() for token in raw.split(",") if token.strip()]


def _build_plan(draft: PlanDraftWire) -> OrchestrationPlan:
    """Build the executable plan from a ready draft, fail-closed.

    Drops null draft fields, folds the flat scope-constraint fields into the
    nested ``scope_constraints`` object, and lets the model validate and fill
    the derived fields (expected artefact shape, time band).

    Args:
        draft: The planner's ready plan draft.

    Returns:
        The validated orchestration plan.

    Raises:
        ValidationError: If the draft is not a valid orchestration plan.
    """
    data = draft.model_dump(exclude_none=True)
    constraints = {
        key: data.pop(key)
        for key in (
            "published_after",
            "published_before",
            "publisher_country",
            "author_affiliation_countries",
        )
        if key in data
    }
    if constraints:
        data["scope_constraints"] = constraints
    return OrchestrationPlan.model_validate(data)


def _render_draft(draft: PlanDraftWire) -> str:
    parts = ["Current plan draft:"]
    for label, value in (
        ("title", draft.title),
        ("question", draft.question),
        ("search_effort", draft.search_effort),
        ("analysis_depth", draft.analysis_depth),
        ("components", draft.components),
        ("steering_mode", draft.steering_mode),
    ):
        if value:
            parts.append(f"  {label}: {value}")
    return "\n".join(parts)


def _render_full_plan(plan: OrchestrationPlan) -> str:
    lines = [
        "Proposed orchestration plan:",
        f"  title: {plan.title}",
        f"  question: {plan.question}",
        f"  backend_scope: {plan.backend_scope}",
        f"  search_effort: {plan.search_effort}",
        f"  analysis_depth: {plan.analysis_depth}",
        f"  components: {plan.components}",
        f"  grouping_facet: {plan.grouping_facet}",
        f"  steering_mode: {plan.steering_mode}",
        f"  expected_artefact_shape: {plan.expected_artefact_shape}",
        f"  time_band: {plan.time_band}",
    ]
    if plan.scoping_notes:
        lines.append(f"  scoping_notes: {plan.scoping_notes}")
    if plan.screening_criteria:
        lines.append(f"  screening_criteria: {plan.screening_criteria}")
    if plan.scope_constraints.to_filters():
        lines.append(f"  scope_constraints: {plan.scope_constraints.model_dump(exclude_none=True)}")
    if plan.component_rationale:
        lines.append("  component_rationale:")
        for component, rationale in plan.component_rationale.items():
            lines.append(f"    - {component}: {rationale}")
    if plan.steer_point_defaults:
        lines.append(
            f"  steer_point_defaults: {[d.model_dump() for d in plan.steer_point_defaults]}"
        )
    if plan.assumptions:
        lines.append(f"  assumptions: {plan.assumptions}")
    return "\n".join(lines)


def _ask(console: ConsoleIO, question: str, suggestions: list[str] | None) -> str:
    """Render a planner question with numbered suggestions and read the answer.

    A numeric answer within range picks that suggestion; any other text is
    accepted verbatim (free text is always allowed).

    Args:
        console: The console seam.
        question: The planner's clarifying question.
        suggestions: Ordered suggested answers, or ``None``.

    Returns:
        The resolved answer text.
    """
    lines = [question]
    if suggestions:
        for index, suggestion in enumerate(suggestions, start=1):
            lines.append(f"  {index}) {suggestion}")
        lines.append("  (or type your own answer)")
    console.print("\n".join(lines))
    raw = console.prompt("> ")
    stripped = raw.strip()
    if suggestions and stripped.isdigit():
        index = int(stripped)
        if 1 <= index <= len(suggestions):
            return suggestions[index - 1]
    return raw


def _live_planner_and_backends(
    langfuse_client: Any,
) -> tuple[PlannerBackend, RunnerBackends]:
    """Build the live planner + full live backend set, mirroring skeleton.py.

    Args:
        langfuse_client: The resolved Langfuse client (tracing lives inside the
            backends, as in ``skeleton.py``).

    Returns:
        The live planner backend and the live runner backend bundle.
    """
    embedding: EmbeddingBackend = OpenAIEmbeddingBackend()
    theme_grouping: ThemeGroupingBackend = OpenAIThemeGroupingBackend()
    if langfuse_client is not None:
        embedding = tracing.TracedEmbeddingBackend(embedding, langfuse_client)
        theme_grouping = tracing.TracedThemeGroupingBackend(theme_grouping, langfuse_client)
    fetcher = LiveDocumentFetcher()
    assert fetcher.mode == "live"
    backends = RunnerBackends(
        embedding=embedding,
        theme_grouping=theme_grouping,
        screening=OpenAIScreeningBackend(langfuse_client=langfuse_client),
        classification=OpenAIClassificationBackend(langfuse_client=langfuse_client),
        ranking=OpenAIRankingBackend(langfuse_client=langfuse_client),
        extraction=OpenAIExtractionBackend(langfuse_client=langfuse_client),
        finding_vetter=OpenAIFindingVetterBackend(langfuse_client=langfuse_client),
        facet_grouping=OpenAIFacetGroupingBackend(langfuse_client=langfuse_client),
        synthesis=OpenAISynthesisBackend(langfuse_client=langfuse_client),
        grounding_judge=OpenAIGroundingJudgeBackend(langfuse_client=langfuse_client),
        search_backends=cast(list[SearchBackend], search_live.live_search_backends()),
        search_generation=search_generation.OpenAISearchGenerationBackend(
            langfuse_client=langfuse_client
        ),
        document_fetcher=fetcher,
        langfuse_client=langfuse_client,
    )
    planner = OpenAIPlannerBackend(langfuse_client=langfuse_client)
    return planner, backends


def _seed_stub_corpus(engine: Engine, project_id: uuid.UUID) -> None:
    """Seed the egress-free demo/dev corpus for a stub run.

    Mirrors skeleton.py's ingest_upload seed: synthetic full-text reviews the
    stub classify/appraise path scores, so the chain has an appraised,
    screened-in corpus to run over without any network egress.

    Args:
        engine: SQLAlchemy engine.
        project_id: The project the corpus is ingested into.
    """
    with engine.begin() as conn:
        for locator, title in _STUB_CORPUS:
            source = get_source(locator)
            ingest_upload(
                conn,
                project_id=project_id,
                chunks=list(source.chunks),
                source_locator=locator,
                metadata={
                    "synthetic": True,
                    "title": title,
                    "abstract": f"A synthetic systematic review ({locator}).",
                    "_stub_systematic_review": True,
                },
                text_basis="full_text",
            )


def _write_plan_row(
    engine: Engine,
    *,
    plan: OrchestrationPlan,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Create project + evidence scope and insert the approved plan row.

    Approval is the user's act: the row is written ``status='approved'``,
    ``created_by='user'``, ``version=1`` in one short transaction.

    Args:
        engine: SQLAlchemy engine.
        plan: The approved orchestration plan.

    Returns:
        ``(project_id, evidence_scope_id, plan_id)``.
    """
    project_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    now = _now()
    with engine.begin() as conn:
        conn.execute(project.insert().values(project_id=project_id, created_at=now))
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=project_id,
                intent=plan.question,
                context={},
                created_at=now,
            )
        )
        conn.execute(
            orchestration_plan.insert().values(
                plan_id=plan_id,
                project_id=project_id,
                evidence_scope_id=scope_id,
                version=1,
                status="approved",
                payload=plan.model_dump(mode="json"),
                created_at=now,
                created_by="user",
                approved_at=now,
            )
        )
    return project_id, scope_id, plan_id


def _artefact_present(engine: Engine, project_id: uuid.UUID) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            sa_select(artefact.c.artefact_id)
            .where(artefact.c.project_id == project_id)
            .limit(1)
        ).first()
    return row is not None


def _plan_conversation(
    console: ConsoleIO,
    planner: PlannerBackend,
    turns: list[dict[str, str]],
    *,
    session_id: uuid.UUID,
) -> OrchestrationPlan | Literal["abandoned", "no_plan"]:
    """Drive the planning conversation to an approved plan, or abandonment.

    Returns:
        The approved plan, ``"abandoned"`` if the user abandoned, or
        ``"no_plan"`` if the planner never converged within the turn cap.
    """
    previous_draft: dict[str, object] | None = None
    for _ in range(MAX_PLANNER_TURNS):
        turn = planner.plan_turn(turns, previous_draft, session_id=session_id)
        console.print(turn.reply)
        console.print(_render_draft(turn.plan_draft))
        previous_draft = turn.plan_draft.model_dump()
        turns.append({"role": "planner", "text": turn.reply})

        if not turn.ready:
            answer = _ask(console, turn.question or "Anything to add?", turn.suggested_answers)
            turns.append({"role": "user", "text": answer})
            continue

        try:
            plan = _build_plan(turn.plan_draft)
        except ValidationError as exc:
            console.print(f"The proposed plan failed validation and was not run:\n{exc}")
            response = console.prompt(
                "Describe a revision, or type 'abandon' to stop: "
            ).strip()
            if response.lower() == "abandon":
                return "abandoned"
            turns.append(
                {"role": "user", "text": f"The plan failed validation ({exc}). {response}"}
            )
            continue

        console.print(_render_full_plan(plan))
        decision = console.prompt("Approve, edit, or abandon? [approve/edit/abandon]: ")
        normalised = decision.strip().lower()
        if normalised == "approve":
            return plan
        if normalised == "abandon":
            return "abandoned"
        change = console.prompt("What would you like to change? ")
        turns.append({"role": "user", "text": change})

    console.print("Planner did not reach an approved plan within the turn cap.")
    return "no_plan"


def main(
    console: ConsoleIO | None = None,
    engine: Engine | None = None,
    planner: PlannerBackend | None = None,
    backends: RunnerBackends | None = None,
) -> OrchestrateResult:
    """Run one orchestrator session: plan -> approve -> run -> report.

    Args:
        console: Console seam; defaults to real stdin/stdout.
        engine: SQLAlchemy engine; defaults to the configured engine.
        planner: Planner backend; defaults to the live/stub choice by key.
        backends: Runner backend bundle; defaults to the live/stub choice by key.

    Returns:
        The structured session result, including the process exit code.
    """
    configure_logging()
    conversation_id = uuid.uuid4()
    console = console if console is not None else StdConsole()
    engine = engine if engine is not None else get_engine()

    live = bool(os.environ.get("OPENAI_API_KEY"))
    langfuse_client = tracing.get_langfuse() if live else None
    if live:
        default_planner, default_backends = _live_planner_and_backends(langfuse_client)
    else:
        default_planner = StubPlannerBackend()
        default_backends = RunnerBackends()
    planner = planner if planner is not None else default_planner
    backends = backends if backends is not None else default_backends
    log.info(
        "orchestrate.start",
        mode="live" if live else "stub",
        session_id=str(conversation_id),
    )

    intent = console.prompt("Describe the evidence review you want: ")
    turns: list[dict[str, str]] = [{"role": "user", "text": intent}]

    plan = _plan_conversation(console, planner, turns, session_id=conversation_id)
    if isinstance(plan, str):
        console.print("No plan approved; nothing was run.")
        exit_code = EXIT_NO_PLAN if plan == "no_plan" else EXIT_ABANDONED
        return OrchestrateResult(
            exit_code=exit_code,
            turns=turns,
            conversation_id=conversation_id,
        )

    project_id, scope_id, plan_id = _write_plan_row(engine, plan=plan)
    if not live:
        _seed_stub_corpus(engine, project_id)

    runner_io: CliIO | UnattendedIO = (
        UnattendedIO(console) if plan.steering_mode == "unattended" else CliIO(console)
    )
    outcome = run_plan(
        engine,
        project_id=project_id,
        evidence_scope_id=scope_id,
        plan=plan,
        plan_id=plan_id,
        plan_version=1,
        plan_row_id=plan_id,
        backends=backends,
        io=runner_io,
        session_id=conversation_id,
    )

    console.print(outcome.collation_render)
    console.print(f"Run status: {outcome.status}")
    artefact_present = _artefact_present(engine, project_id)
    console.print(f"Artefact minted: {artefact_present}")

    return OrchestrateResult(
        exit_code=_EXIT_BY_STATUS[outcome.status],
        plan=plan,
        plan_id=plan_id,
        project_id=project_id,
        evidence_scope_id=scope_id,
        outcome=outcome,
        turns=turns,
        runner_io=runner_io,
        artefact_present=artefact_present,
        conversation_id=conversation_id,
    )


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main().exit_code)
