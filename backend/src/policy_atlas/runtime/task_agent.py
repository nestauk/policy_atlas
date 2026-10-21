"""Task Agent backend seam: one live OpenAI backend for every capability.

Mirrors the ``screening_backend.py`` / ``classification_backend.py`` pattern:
a live OpenAI structured-output backend with tracing inside the backend, and a
deterministic zero-egress stub for tests and the CLI. What differs between
capabilities (the wire type, the prompt, the model, the plan builder, the
draft projections) lives on each capability's ``TaskAgentProfile`` in the
registry; this module holds the Evidence search profile. The task_agent
completes before acquire begins — this seam is never invoked mid-run
(contract decision 5, sequencing invariant).
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol, cast

import structlog
from langfuse import Langfuse

from policy_atlas.api.contract import PlanDraft, PlanStep
from policy_atlas.api.stage_vocabulary import STAGE_BY_REGISTRY, STAGE_PRESENTATION
from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import resolve_openai_client, traced_parse
from policy_atlas.core.prompt_fields import scrub_nul
from policy_atlas.evidence_search.extract.extract import _scrub_nul
from policy_atlas.runtime.capability_registry import (
    EVIDENCE_SEARCH,
    TaskAgentProfile,
    compose_plan,
    expect_task_plan,
)
from policy_atlas.runtime.conversation_lifecycle import seed_draft_from_executed_plan
from policy_atlas.runtime.task_agent_prompt import (
    PLANNER_MAX_OUTPUT_TOKENS,
    PLANNER_PROMPT_VERSION,
    PlanDraftWire,
    PlannerTurnWire,
    build_planner_messages,
)
from policy_atlas.runtime.task_agent_scoping_prompt import ScopingTurnWire
from policy_atlas.runtime.task_plan import TaskPlan, registry_component_for, time_band_for

log = structlog.get_logger()

# Model from the route file (task 053); see core/model_routes.py.
TASK_AGENT_MODEL = route().model_for("task_agent")

# The Task Agent turn as emitted by any backend; the wire model IS the turn
# shape, code-side and model-side — no separate dataclass to keep in sync.
TaskAgentTurn = PlannerTurnWire

#: A turn of either capability's Task Agent.
TaskAgentTurnWire = PlannerTurnWire | ScopingTurnWire


class TaskAgentBackend(Protocol):
    """The Evidence search task_agent seam for one conversation turn (the CLI's).

    Backends return one structurally parsed turn per call; transport, parse,
    and code-side validation failures raise so the caller can apply retry
    policy.
    """

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Advance the task_agent conversation by one turn.

        Args:
            turns: Conversation turns so far, oldest first, as
                ``{"role": "user"|"planner", "text": ...}`` dicts.
            previous_draft: The prior turn's plan draft dump, or ``None`` on
                the first turn.
            session_id: Optional Langfuse session id shared by the Task's
                traces (task 038, V9: no longer the conversation id).
            conversation_id: Optional task_agent-conversation id recorded in
                trace metadata, so one chat is still filterable now that
                ``session_id`` groups by task.

        Returns:
            One parsed Task Agent turn.

        Raises:
            RuntimeError: If the backend cannot produce a usable turn.
        """
        ...


class TaskAgentTurnBackend(Protocol):
    """The Task Agent seam the turn route calls, for any capability."""

    def turn(
        self,
        profile: TaskAgentProfile,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        inputs: Any = None,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> TaskAgentTurnWire:
        """Advance one capability's Task Agent conversation by one turn.

        Args:
            profile: The task's capability profile.
            turns: Conversation turns so far, oldest first.
            previous_draft: The prior turn's draft dump, or ``None``.
            inputs: What ``profile.load_inputs`` returned.
            session_id: Optional Langfuse session id (the task id).
            conversation_id: Optional conversation id for trace metadata.

        Returns:
            One parsed turn of ``profile.wire``.

        Raises:
            RuntimeError: If the backend cannot produce a usable turn.
        """
        ...


def _degrade_suggestions[W: (PlannerTurnWire, ScopingTurnWire)](turn: W) -> W:
    """Degrade a malformed ``suggested_answers`` list to a plain question.

    Never blocks or raises: a bad suggestion list is a UX shortfall, not a
    plan-breaking failure. Applies the shape contract from the prompt
    (2-5 non-empty entries, only ever alongside a question).

    Args:
        turn: The candidate Task Agent turn.

    Returns:
        The turn, with ``suggested_answers`` forced to ``None`` if it is
        absent a question or fails the shape contract.
    """
    if turn.question is None:
        if turn.suggested_answers is not None:
            log.warning(
                "task_agent.suggestions_degraded",
                reason="suggestions_without_question",
                suggestion_count=len(turn.suggested_answers),
            )
            return turn.model_copy(update={"suggested_answers": None})
        return turn

    suggestions = turn.suggested_answers
    if suggestions is None:
        return turn

    invalid = (
        len(suggestions) < 2
        or len(suggestions) > 5
        or any(not isinstance(entry, str) or not entry.strip() for entry in suggestions)
    )
    if invalid:
        log.warning(
            "task_agent.suggestions_degraded",
            reason="shape_contract_violated",
            suggestion_count=len(suggestions),
        )
        return turn.model_copy(update={"suggested_answers": None})
    return turn


def _scrub_turn[W: (PlannerTurnWire, ScopingTurnWire)](turn: W) -> W:
    """Strip NULs from every model-authored string before it reaches JSONB."""
    updates: dict[str, Any] = {"reply": scrub_nul(turn.reply)}
    if turn.question is not None:
        updates["question"] = scrub_nul(turn.question)
    updates["plan_draft"] = type(turn.plan_draft).model_validate(
        _scrub_nul(turn.plan_draft.model_dump())
    )
    if turn.part is not None:
        # Postgres JSONB rejects \u0000; an unscrubbed part would wedge the
        # phase-two transcript write instead of degrading (review 028, security
        # lane).
        updates["part"] = type(turn.part).model_validate(_scrub_nul(turn.part.model_dump()))
    return turn.model_copy(update=updates)


class OpenAITaskAgentBackend:
    """Live OpenAI implementation of the Task Agent seam, for any capability.

    Args:
        api_key: Optional OpenAI API key. If omitted, ``OPENAI_API_KEY`` is read
            from the environment; keys are never read from persistent config.
        langfuse_client: Optional Langfuse client. When omitted, tracing is a
            no-op and no Langfuse object is created.

    Raises:
        RuntimeError: If no OpenAI API key is provided or configured.
    """

    def __init__(
        self,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
    ) -> None:
        self._client = resolve_openai_client(
            api_key,
            backend_name="OpenAITaskAgentBackend",
            timeout=180.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def turn(
        self,
        profile: TaskAgentProfile,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        inputs: Any = None,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> TaskAgentTurnWire:
        """Advance the conversation through structured OpenAI output.

        Args:
            profile: The task's capability profile.
            turns: Conversation turns so far, oldest first.
            previous_draft: The prior turn's draft dump, or ``None``.
            inputs: What ``profile.load_inputs`` returned.
            session_id: Optional Langfuse session id (the task id).
            conversation_id: Optional conversation id for trace metadata.

        Returns:
            One parsed turn, NUL-scrubbed.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        parsed, _usage = traced_parse(
            self._client,
            self._langfuse_client,
            messages=profile.build_messages(turns, previous_draft, inputs),
            response_format=profile.wire,
            model=profile.model,
            max_output_tokens=profile.max_output_tokens,
            usage_event=profile.usage_event,
            label=profile.label,
            name=profile.trace_name,
            prompt_version=profile.prompt_version,
            session_id=session_id,
            metadata={
                "conversation_id": str(conversation_id) if conversation_id is not None else None,
                "turn_number": len(turns),
            },
            clean=lambda model: _scrub_turn(cast(Any, model)),
        )
        turn: Any = parsed
        return cast(
            TaskAgentTurnWire,
            _degrade_suggestions(turn) if profile.degrade_suggestions else turn,
        )

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Advance an Evidence search conversation (the CLI seam).

        Args:
            turns: Conversation turns so far, oldest first.
            previous_draft: The prior turn's plan draft dump, or ``None``.
            session_id: Optional Langfuse session id.
            conversation_id: Optional conversation id for trace metadata.

        Returns:
            One parsed Task Agent turn, with suggestions degraded if malformed.
        """
        return cast(
            PlannerTurnWire,
            self.turn(
                EVIDENCE_SEARCH_TASK_AGENT,
                turns,
                previous_draft,
                session_id=session_id,
                conversation_id=conversation_id,
            ),
        )


_STUB_SHAPE_QUESTION = "What decision should this evidence review inform?"
_STUB_SUGGESTED_ANSWERS: tuple[str, ...] = (
    "A one-off briefing to inform a specific decision",
    "An ongoing evidence base to monitor over time",
    "A comparison of intervention options",
)
_STUB_LANDSCAPE_SENTINEL = "landscape only"
_STUB_ASSUMPTIONS: tuple[str, ...] = ("Stub task_agent: deterministic fixture proposal.",)
_STUB_COMPONENT_RATIONALE: dict[str, str] = {
    "characterise": "Maps the corpus landscape before deeper analysis.",
    "screen_full": "Full-text re-screen improves precision once documents are fetched.",
    "select": "Selects documents for structured extraction.",
    "extract": "Pulls structured intervention-outcome findings from selected documents.",
    "group": "Organises findings by outcome for synthesis.",
}


def _stub_turn(turns: list[dict[str, str]]) -> PlannerTurnWire:
    """A deterministic Evidence search turn derived from ``turns`` alone.

    On the first turn (a single user turn) a shape question is asked; on any
    later turn a complete, registry-valid draft is returned.
    """
    if len(turns) <= 1:
        intent = turns[0]["text"] if turns else ""
        return PlannerTurnWire(
            reply=(
                "Deterministic stub Task Agent: before proposing a plan, I need "
                "to know what decision this evidence review should inform."
            ),
            plan_draft=PlanDraftWire(question=intent, backend_scope="both"),
            question=_STUB_SHAPE_QUESTION,
            suggested_answers=list(_STUB_SUGGESTED_ANSWERS),
            ready=False,
        )

    first_text = turns[0]["text"]
    latest_text = turns[-1]["text"]
    if _STUB_LANDSCAPE_SENTINEL in latest_text:
        return PlannerTurnWire(
            reply="Deterministic stub Task Agent: landscape-only draft proposed.",
            plan_draft=PlanDraftWire(
                title="Evidence review",
                question=first_text,
                backend_scope="both",
                search_effort="standard",
                analysis_depth="landscape",
                components=["characterise"],
                component_rationale={"characterise": _STUB_COMPONENT_RATIONALE["characterise"]},
                steering_mode="unattended",
                grouping_facets=None,
                assumptions=list(_STUB_ASSUMPTIONS),
            ),
            question=None,
            suggested_answers=None,
            ready=True,
        )

    components = ["characterise", "screen_full", "select", "extract", "group"]
    return PlannerTurnWire(
        reply="Deterministic stub Task Agent: complete draft proposed.",
        plan_draft=PlanDraftWire(
            title="Evidence review",
            question=first_text,
            backend_scope="both",
            search_effort="standard",
            # 018 regrade: select/extract/group are deep-only now, so this
            # full-chain stub draft (it requests all five discretionary
            # components, with grouping) must be depth "deep", not
            # "standard", to stay a valid TaskPlan.
            analysis_depth="deep",
            components=components,
            component_rationale={
                component: _STUB_COMPONENT_RATIONALE[component] for component in components
            },
            steering_mode="unattended",
            grouping_facets=["outcome"],
            assumptions=list(_STUB_ASSUMPTIONS),
        ),
        question=None,
        suggested_answers=None,
        ready=True,
    )


class StubTaskAgentBackend:
    """Deterministic zero-egress Task Agent backend for tests and the CLI."""

    def turn(
        self,
        profile: TaskAgentProfile,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        inputs: Any = None,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> TaskAgentTurnWire:
        """Return the profile's deterministic turn, derived from ``turns`` alone.

        Args:
            profile: The task's capability profile.
            turns: Conversation turns so far, oldest first.
            previous_draft: Accepted for protocol compatibility; ignored.
            inputs: Accepted for protocol compatibility; ignored.
            session_id: Accepted for tracing compatibility; ignored.
            conversation_id: Accepted for tracing compatibility; ignored.

        Returns:
            A deterministic turn of ``profile.wire``.
        """
        del previous_draft, inputs, session_id, conversation_id
        return cast(TaskAgentTurnWire, profile.stub_turn(turns))

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Return a deterministic Evidence search turn (the CLI seam).

        Args:
            turns: Conversation turns so far, oldest first. On the first turn
                (a single user turn) a shape question is asked; on any later
                turn a complete, registry-valid draft is returned.
            previous_draft: Accepted for protocol compatibility; ignored.
            session_id: Accepted for tracing compatibility; ignored.
            conversation_id: Accepted for tracing compatibility; ignored.

        Returns:
            A deterministic Task Agent turn.
        """
        del previous_draft, session_id, conversation_id
        return _stub_turn(turns)


# --- The Evidence search profile --------------------------------------------


def draft_from_wire(draft: PlanDraftWire, *, ready: bool) -> PlanDraft:
    """Translate the runtime task_agent wire into the standalone API draft model.

    Args:
        draft: The Task Agent's loose draft.
        ready: Whether the draft validated into a plan.

    Returns:
        The API draft.
    """
    values = draft.model_dump(exclude_none=True)
    constraints: dict[str, Any] = {}
    for key in (
        "published_after",
        "published_before",
        "publisher_country",
        "publisher_source",
        "author_affiliation_countries",
        "country_group",
    ):
        value = values.pop(key, None)
        if value is not None:
            constraints[key] = value
    # The wire's publisher_source is a loose str (task_agent output) while the
    # draft narrows to Literal["apo"]. Normalise the taught spellings and drop
    # anything else — the turn must degrade (ready=false), never 500.
    source = constraints.pop("publisher_source", None)
    if isinstance(source, str) and source.strip().casefold() in {
        "apo",
        "australian policy online",
    }:
        constraints["publisher_source"] = "apo"
    if constraints:
        values["scope_constraints"] = constraints
    values.pop("steer_point_defaults", None)
    effort, depth = values.get("search_effort"), values.get("analysis_depth")
    if effort in {"rapid", "standard", "deep"} and depth in {"landscape", "standard", "deep"}:
        values["time_band"] = time_band_for(
            effort, depth, values.get("section_budget")
        )
    values["ready"] = ready
    return PlanDraft.model_validate(values)


def draft_from_plan(plan: TaskPlan) -> PlanDraft:
    """Project a validated runtime plan into the API's approved draft shape.

    Args:
        plan: An approved Evidence search plan.

    Returns:
        The API draft, with its public steps.
    """
    values = plan.model_dump(mode="json")
    values.pop("steer_point_defaults", None)
    # This links an approved payload to its transcript turn; it is not a
    # user-visible plan-draft field.
    values.pop("source_turn_index", None)
    steps: list[PlanStep] = []
    seen_stages: set[str] = set()
    for step in compose_plan(EVIDENCE_SEARCH, plan).steps:
        registry_component = registry_component_for(step.component)
        # Ingest is unmapped from public acquire so Searching is not overwritten
        # by full-text fetch (033 S5). Skip any registry component with no
        # public stage rather than crashing the draft projection.
        stage = STAGE_BY_REGISTRY.get(registry_component)
        if stage is None:
            continue
        if stage in seen_stages:
            continue
        seen_stages.add(stage)
        label, blurb = STAGE_PRESENTATION[stage]
        steps.append(PlanStep(label=label, blurb=blurb, stage=stage))
    values["steps"] = steps
    values["ready"] = True
    return PlanDraft.model_validate(values)


def _build_plan(draft: PlanDraftWire, inputs: None, turn_index: int) -> TaskPlan:
    del inputs, turn_index
    # runtime.agent imports this module, so its builder is imported on use.
    from policy_atlas.runtime.agent import build_plan

    return build_plan(draft)


def _seed_draft(plan: TaskPlan) -> dict[str, object]:
    return cast(
        "dict[str, object]",
        seed_draft_from_executed_plan(expect_task_plan(plan)).model_dump(mode="json"),
    )


EVIDENCE_SEARCH_TASK_AGENT = TaskAgentProfile(
    capability=EVIDENCE_SEARCH,
    wire=PlannerTurnWire,
    build_messages=lambda turns, previous, _inputs: build_planner_messages(turns, previous),
    model=TASK_AGENT_MODEL,
    max_output_tokens=PLANNER_MAX_OUTPUT_TOKENS,
    prompt_version=PLANNER_PROMPT_VERSION,
    trace_name="task_agent:turn",
    usage_event="task_agent.turn.usage",
    label="task_agent",
    load_inputs=lambda _conn, _task_id: None,
    build_plan=_build_plan,
    draft_from_plan=draft_from_plan,
    draft_from_wire=lambda draft, ready, _inputs: draft_from_wire(draft, ready=ready),
    seed_draft=_seed_draft,
    stub_turn=_stub_turn,
    part_ids=frozenset({"question", "scope", "thoroughness"}),
    degrade_suggestions=True,
)
