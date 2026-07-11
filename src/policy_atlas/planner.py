"""Planner backend seam for the ``planner_v1`` orchestration-planning call.

Mirrors the ``screening_backend.py`` / ``classification_backend.py`` pattern:
a live OpenAI structured-output backend with tracing inside the backend, and a
deterministic zero-egress stub for tests and the CLI. The planner completes
before acquire begins — this seam is never invoked mid-run (contract
decision 5, sequencing invariant).
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Protocol

import structlog
from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from openai.types.completion_usage import CompletionUsage

from policy_atlas import tracing
from policy_atlas.embeddings import log_usage, resolve_openai_client, usage_metadata
from policy_atlas.extract import _scrub_nul
from policy_atlas.planner_prompt import (
    PLANNER_MAX_OUTPUT_TOKENS,
    PLANNER_PROMPT_VERSION,
    PlanDraftWire,
    PlannerTurnWire,
    build_planner_messages,
)
from policy_atlas.prompt_fields import scrub_nul

log = structlog.get_logger()

# Judgment-class model; env-overridable so ops can pin a different model
# without a code change (the `SYNTHESIS_MODEL` pattern).
PLANNER_MODEL = os.environ.get("POLICY_ATLAS_PLANNER_MODEL", "gpt-5.5")

# The planner turn as emitted by any backend; the wire model IS the turn
# shape, code-side and model-side — no separate dataclass to keep in sync.
PlannerTurn = PlannerTurnWire


class PlannerBackend(Protocol):
    """The planner seam for one conversation turn.

    Backends return one structurally parsed turn per call; transport, parse,
    and code-side validation failures raise so the caller can apply retry
    policy.
    """

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so wrappers can proxy it."""
        ...

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Advance the planning conversation by one turn.

        Args:
            turns: Conversation turns so far, oldest first, as
                ``{"role": "user"|"planner", "text": ...}`` dicts.
            previous_draft: The prior turn's plan draft dump, or ``None`` on
                the first turn.
            session_id: Optional Langfuse session id shared by the conversation.

        Returns:
            One parsed planner turn.

        Raises:
            RuntimeError: If the backend cannot produce a usable turn.
        """
        ...


def _degrade_suggestions(turn: PlannerTurnWire) -> PlannerTurnWire:
    """Degrade a malformed ``suggested_answers`` list to a plain question.

    Never blocks or raises: a bad suggestion list is a UX shortfall, not a
    plan-breaking failure. Applies the shape contract from the prompt
    (2-5 non-empty entries, only ever alongside a question).

    Args:
        turn: The candidate planner turn.

    Returns:
        The turn, with ``suggested_answers`` forced to ``None`` if it is
        absent a question or fails the shape contract.
    """
    if turn.question is None:
        if turn.suggested_answers is not None:
            log.warning(
                "planner.suggestions_degraded",
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
            "planner.suggestions_degraded",
            reason="shape_contract_violated",
            suggestion_count=len(suggestions),
        )
        return turn.model_copy(update={"suggested_answers": None})
    return turn


def _scrub_turn(turn: PlannerTurnWire) -> PlannerTurnWire:
    updates: dict[str, Any] = {"reply": scrub_nul(turn.reply)}
    if turn.question is not None:
        updates["question"] = scrub_nul(turn.question)
    updates["plan_draft"] = PlanDraftWire.model_validate(
        _scrub_nul(turn.plan_draft.model_dump())
    )
    return turn.model_copy(update=updates)


class OpenAIPlannerBackend:
    """Live OpenAI implementation of the planner seam.

    Args:
        api_key: Optional OpenAI API key. If omitted, ``OPENAI_API_KEY`` is read
            from the environment; keys are never read from persistent config.
        langfuse_client: Optional Langfuse client. When omitted, tracing is a
            no-op and no Langfuse object is created.

    Raises:
        RuntimeError: If no OpenAI API key is provided or configured.
    """

    mode = "live"

    def __init__(
        self,
        api_key: str | None = None,
        langfuse_client: Langfuse | None = None,
    ) -> None:
        self._client = resolve_openai_client(
            api_key,
            backend_name="OpenAIPlannerBackend",
            timeout=180.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _parse_once(
        self,
        messages: list[ChatCompletionMessageParam],
    ) -> tuple[PlannerTurnWire, CompletionUsage | None]:
        response = self._client.chat.completions.parse(
            model=PLANNER_MODEL,
            messages=messages,
            response_format=PlannerTurnWire,
            max_completion_tokens=PLANNER_MAX_OUTPUT_TOKENS,
        )
        log_usage("planner.turn.usage", response.usage)
        if not response.choices:
            raise RuntimeError("OpenAI planner response had no choices.")
        parsed = response.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("OpenAI planner response was not parsed.")
        parsed_model: PlannerTurnWire = parsed
        return _scrub_turn(parsed_model), response.usage

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Advance the planning conversation through structured OpenAI output.

        Args:
            turns: Conversation turns so far, oldest first, as
                ``{"role": "user"|"planner", "text": ...}`` dicts.
            previous_draft: The prior turn's plan draft dump, or ``None`` on
                the first turn.
            session_id: Optional Langfuse session id shared by the conversation.

        Returns:
            One parsed planner turn, with suggestions degraded if malformed.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        messages = build_planner_messages(turns, previous_draft)
        langfuse_client = self._langfuse_client
        turn_number = len(turns)

        def _update(
            span: Any,
            result: tuple[PlannerTurnWire, CompletionUsage | None],
        ) -> None:
            turn, usage = result
            span.update(
                input={"messages": messages},
                output=turn.model_dump(),
                model=PLANNER_MODEL,
                metadata={
                    "prompt_version": PLANNER_PROMPT_VERSION,
                    **usage_metadata(usage),
                },
            )

        turn, _usage = tracing.traced_call(
            langfuse_client,
            name=f"planner:turn{turn_number}",
            as_type="generation",
            call=lambda: self._parse_once(messages),
            session_id=session_id,
            update=_update,
        )
        return _degrade_suggestions(turn)


_STUB_SHAPE_QUESTION = "What decision should this evidence review inform?"
_STUB_SUGGESTED_ANSWERS: tuple[str, ...] = (
    "A one-off briefing to inform a specific decision",
    "An ongoing evidence base to monitor over time",
    "A comparison of intervention options",
)
_STUB_LANDSCAPE_SENTINEL = "landscape only"
_STUB_ASSUMPTIONS: tuple[str, ...] = ("Stub planner: deterministic fixture proposal.",)
_STUB_COMPONENT_RATIONALE: dict[str, str] = {
    "characterise": "Maps the corpus landscape before deeper analysis.",
    "screen_stage2": "Full-text re-screen improves precision once documents are fetched.",
    "select": "Selects documents for structured extraction.",
    "extract": "Pulls structured intervention-outcome findings from selected documents.",
    "group": "Organises findings by outcome for synthesis.",
}


class StubPlannerBackend:
    """Deterministic zero-egress planner backend for tests and the CLI."""

    mode = "stub"

    def plan_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        session_id: uuid.UUID | None = None,
    ) -> PlannerTurnWire:
        """Return a deterministic planner turn.

        Args:
            turns: Conversation turns so far, oldest first. On the first turn
                (a single user turn) a shape question is asked; on any later
                turn a complete, registry-valid draft is returned.
            previous_draft: Accepted for protocol compatibility; ignored by
                the stub, which derives its output from ``turns`` alone.
            session_id: Accepted for tracing compatibility; ignored by the stub.

        Returns:
            A deterministic planner turn.
        """
        del previous_draft, session_id
        if len(turns) <= 1:
            intent = turns[0]["text"] if turns else ""
            return PlannerTurnWire(
                reply=(
                    "Deterministic stub planner: before proposing a plan, I need "
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
                reply="Deterministic stub planner: landscape-only draft proposed.",
                plan_draft=PlanDraftWire(
                    title="Evidence review",
                    question=first_text,
                    backend_scope="both",
                    search_effort="standard",
                    analysis_depth="landscape",
                    components=["characterise"],
                    component_rationale={"characterise": _STUB_COMPONENT_RATIONALE["characterise"]},
                    steering_mode="moderate",
                    grouping_facet=None,
                    assumptions=list(_STUB_ASSUMPTIONS),
                ),
                question=None,
                suggested_answers=None,
                ready=True,
            )

        components = ["characterise", "screen_stage2", "select", "extract", "group"]
        return PlannerTurnWire(
            reply="Deterministic stub planner: complete draft proposed.",
            plan_draft=PlanDraftWire(
                title="Evidence review",
                question=first_text,
                backend_scope="both",
                search_effort="standard",
                # 018 regrade: select/extract/group are deep-only now, so this
                # full-chain stub draft (it requests all five discretionary
                # components, with grouping) must be depth "deep", not
                # "standard", to stay a valid OrchestrationPlan.
                analysis_depth="deep",
                components=components,
                component_rationale={
                    component: _STUB_COMPONENT_RATIONALE[component] for component in components
                },
                steering_mode="moderate",
                grouping_facet="outcome",
                assumptions=list(_STUB_ASSUMPTIONS),
            ),
            question=None,
            suggested_answers=None,
            ready=True,
        )
