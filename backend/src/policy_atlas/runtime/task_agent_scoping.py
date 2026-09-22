"""Task Agent backend seam for the ``task_agent_scoping_v3`` planning call.

The Evidence search seam (``task_agent.py``) one capability over. Same three
pieces: a Protocol, a live OpenAI structured-output backend with tracing inside
it, and a deterministic zero-egress stub for tests and CI. The scoping turn
carries two inputs the Evidence search turn does not — the fenced linked-task
context and the baseline state — so it gets its own method rather than a
widened ``plan_turn``.
"""

from __future__ import annotations

import uuid
from typing import Any, Protocol

import structlog
from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.prompt_fields import scrub_nul
from policy_atlas.core.usage import UsageResult, usage_metadata
from policy_atlas.evidence_search.extract.extract import _scrub_nul
from policy_atlas.runtime.task_agent import TASK_AGENT_MODEL
from policy_atlas.runtime.task_agent_prompt import (
    CountryGroupDraft,
    PartOptionWire,
    PartProposalWire,
)
from policy_atlas.runtime.task_agent_scoping_prompt import (
    DEPTH_OPTION_IDS,
    SCOPING_MAX_OUTPUT_TOKENS,
    TASK_AGENT_SCOPING_PROMPT_VERSION,
    LinkedTaskContext,
    ScopingConstraintWire,
    ScopingPlanDraftWire,
    ScopingSteerPointDefaultDraft,
    ScopingTurnWire,
    TaggedText,
    build_scoping_messages,
)

log = structlog.get_logger()

#: The code-authored line the prompt reads as data when nothing has run yet.
NO_BASELINE_STATE = "no baseline built yet"


class ScopingTaskAgentBackend(Protocol):
    """The scoping Task Agent seam for one conversation turn."""

    def scope_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        linked_context: list[LinkedTaskContext],
        baseline_state: str = NO_BASELINE_STATE,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> ScopingTurnWire:
        """Advance the scoping Task Agent conversation by one turn.

        Args:
            turns: Conversation turns so far, oldest first, as
                ``{"role": "user"|"planner", "text": ...}`` dicts.
            previous_draft: The prior turn's draft dump, or ``None``.
            linked_context: One entry per ``task_link``, in link order.
            baseline_state: A short code-authored line about whether a
                baseline exists, and from which plan version.
            session_id: Optional Langfuse session id shared by the task's traces.
            conversation_id: Optional conversation id for trace metadata.

        Returns:
            One parsed scoping turn.

        Raises:
            RuntimeError: If the backend cannot produce a usable turn.
        """
        ...


def _scrub_turn(turn: ScopingTurnWire) -> ScopingTurnWire:
    """Strip NULs from every model-authored string before it reaches JSONB."""
    updates: dict[str, Any] = {"reply": scrub_nul(turn.reply)}
    if turn.question is not None:
        updates["question"] = scrub_nul(turn.question)
    updates["plan_draft"] = ScopingPlanDraftWire.model_validate(
        _scrub_nul(turn.plan_draft.model_dump())
    )
    if turn.part is not None:
        updates["part"] = type(turn.part).model_validate(_scrub_nul(turn.part.model_dump()))
    return turn.model_copy(update=updates)


class OpenAIScopingTaskAgentBackend:
    """Live OpenAI implementation of the scoping Task Agent seam.

    Args:
        api_key: Optional OpenAI API key. If omitted, ``OPENAI_API_KEY`` is
            read from the environment; keys are never read from persistent
            config.
        langfuse_client: Optional Langfuse client. When omitted, tracing is a
            no-op.

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
            backend_name="OpenAIScopingTaskAgentBackend",
            timeout=180.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def _parse_once(
        self,
        messages: list[ChatCompletionMessageParam],
    ) -> UsageResult[ScopingTurnWire]:
        parsed, usage = parse_structured(
            self._client,
            messages=messages,
            response_format=ScopingTurnWire,
            usage_event="task_agent.scoping.turn.usage",
            label="task-agent-scoping",
            model=TASK_AGENT_MODEL,
            max_completion_tokens=SCOPING_MAX_OUTPUT_TOKENS,
        )
        return _scrub_turn(parsed), usage

    def scope_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        linked_context: list[LinkedTaskContext],
        baseline_state: str = NO_BASELINE_STATE,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> ScopingTurnWire:
        """Advance the scoping conversation through structured OpenAI output.

        Args:
            turns: Conversation turns so far, oldest first.
            previous_draft: The prior turn's draft dump, or ``None``.
            linked_context: One entry per ``task_link``, in link order.
            baseline_state: The code-authored baseline-state line.
            session_id: Optional Langfuse session id.
            conversation_id: Optional conversation id for trace metadata.

        Returns:
            One parsed scoping turn.

        Raises:
            RuntimeError: If the response cannot be parsed.
        """
        messages = build_scoping_messages(
            turns,
            previous_draft,
            linked_context=linked_context,
            baseline_state=baseline_state,
        )
        turn_number = len(turns)

        def _update(span: Any, result: UsageResult[ScopingTurnWire]) -> None:
            parsed, usage = result
            span.update(
                input={"messages": messages},
                output=parsed.model_dump(),
                model=TASK_AGENT_MODEL,
                metadata={
                    "prompt_version": TASK_AGENT_SCOPING_PROMPT_VERSION,
                    "conversation_id": (
                        str(conversation_id) if conversation_id is not None else None
                    ),
                    **usage_metadata(usage),
                },
            )

        turn, _usage = tracing.traced_call(
            self._langfuse_client,
            name=f"task_agent_scoping:turn{turn_number}",
            as_type="generation",
            call=lambda: self._parse_once(messages),
            session_id=session_id,
            update=_update,
        )
        return turn


# --- The deterministic stub -------------------------------------------------
#
# Zero egress, and every branch keyed off the user's own text so a test reads
# as a conversation rather than as a turn counter. The words below are the
# stub's, not the prompt's: the prompt module is lead-owned and hash-pinned,
# and the stub must never become a second place where product copy lives. The
# two depth labels are the exception — they are the ids and screen words the
# prompt fixes (OS ruling 25), so the stub copies them rather than inventing a
# third spelling.

_STUB_SETTINGS_QUESTION = "Who or what should change?"
_STUB_CONSTRAINT_QUESTION = (
    "Does that limit the evidence I read, or the options you would consider?"
)
_STUB_DEPTH_OPTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "rapid_pass",
        "Rapid scoping",
        "A smaller reading set for each option when you assess. The shorter path.",
    ),
    (
        "standard_pass",
        "Standard scoping",
        "A broader reading set for each option when you assess. The fuller path.",
    ),
)
_STUB_OECD_GROUP = "OECD members"


def _confirmed_option(text: str, part_id: str) -> str | None:
    """Return the option id a ``[confirm part=… option=…]`` marker names, if any."""
    marker = f"[confirm part={part_id} option="
    start = text.find(marker)
    if start == -1:
        return None
    end = text.find("]", start)
    if end == -1:
        return None
    return text[start + len(marker) : end].strip()


def _depth_from(text: str) -> str | None:
    """Resolve a depth choice from a user turn, by marker or in their own words."""
    option_id = _confirmed_option(text, "depth")
    if option_id in DEPTH_OPTION_IDS:
        return DEPTH_OPTION_IDS[option_id]
    lowered = text.lower()
    if "standard" in lowered:
        return "standard"
    if "rapid" in lowered or "quick" in lowered:
        return "rapid"
    return None


def _part(
    part_id: str, step_label: str, title: str, options: list[PartOptionWire]
) -> PartProposalWire:
    return PartProposalWire(id=part_id, step_label=step_label, title=title, options=options)


class StubScopingTaskAgentBackend:
    """Deterministic zero-egress scoping Task Agent for tests and the CLI."""

    def scope_turn(
        self,
        turns: list[dict[str, str]],
        previous_draft: dict[str, object] | None,
        *,
        linked_context: list[LinkedTaskContext] | None = None,
        baseline_state: str = NO_BASELINE_STATE,
        session_id: uuid.UUID | None = None,
        conversation_id: uuid.UUID | None = None,
    ) -> ScopingTurnWire:
        """Return a deterministic scoping turn derived from ``turns`` alone.

        Args:
            turns: Conversation turns so far, oldest first.
            previous_draft: Accepted for protocol compatibility; ignored.
            linked_context: Accepted for protocol compatibility; ignored.
            baseline_state: Accepted for protocol compatibility; ignored.
            session_id: Accepted for tracing compatibility; ignored.
            conversation_id: Accepted for tracing compatibility; ignored.

        Returns:
            One deterministic scoping turn.
        """
        del previous_draft, linked_context, baseline_state, session_id, conversation_id
        user_turns = [turn["text"] for turn in turns if turn["role"] == "user"]
        question = user_turns[0] if user_turns else ""
        latest = user_turns[-1] if user_turns else ""

        draft = ScopingPlanDraftWire(
            title="Options scoping",
            question=question,
            intended_change=TaggedText(text=question, origin="from_your_question"),
            where=TaggedText(text="United Kingdom", origin="assumed"),
            outcomes=[
                TaggedText(text="the outcomes named in the question", origin="assumed")
            ],
            steering_mode="moderate",
        )

        if any("unattended" in text.lower() for text in user_turns):
            draft.steering_mode = "unattended"
            draft.steer_point_defaults = [
                ScopingSteerPointDefaultDraft(
                    steer_point="baseline_confirm", action="proceed_flag"
                )
            ]

        # Constraints, in the order the conversation can settle them: the kind
        # question first, then the answer.
        constraint_kind = _confirmed_option(latest, "constraints")
        settled_kind = next(
            (
                _confirmed_option(text, "constraints")
                for text in reversed(user_turns)
                if _confirmed_option(text, "constraints") is not None
            ),
            None,
        )
        if settled_kind == "evidence_only":
            draft.constraints = [
                ScopingConstraintWire(
                    text="OECD evidence only",
                    kind="evidence_restriction",
                    origin="your_call",
                    checked_at="retrieval",
                    country_group=CountryGroupDraft(
                        label=_STUB_OECD_GROUP, countries=None
                    ),
                )
            ]

        target_seen = len(user_turns) >= 2
        if target_seen:
            draft.target_unit = TaggedText(text=user_turns[1], origin="your_call")

        depth = next((d for text in user_turns if (d := _depth_from(text))), None)
        if depth is not None:
            draft.depth = depth

        if len(user_turns) <= 1:
            return ScopingTurnWire(
                reply=(
                    "Deterministic stub Task Agent: I have the question. "
                    "Who or what should change?"
                ),
                plan_draft=draft,
                part=_part(
                    "settings",
                    "Plan · settings",
                    _STUB_SETTINGS_QUESTION,
                    [
                        PartOptionWire(
                            id="whole_group",
                            label="The whole group the question names",
                            primary=True,
                        ),
                        PartOptionWire(
                            id="subgroup",
                            label="A subgroup the question hints at",
                            primary=False,
                        ),
                    ],
                ),
                ready=False,
            )

        if (
            "only" in latest.lower()
            and "evidence" in latest.lower()
            and constraint_kind is None
            and settled_kind is None
        ):
            return ScopingTurnWire(
                reply="Deterministic stub Task Agent: I need to know what that limits.",
                plan_draft=draft,
                part=_part(
                    "constraints",
                    "Plan · constraints",
                    _STUB_CONSTRAINT_QUESTION,
                    [
                        PartOptionWire(
                            id="evidence_only",
                            label="It limits the evidence I read",
                            primary=True,
                        ),
                        PartOptionWire(
                            id="options_only",
                            label="It limits the options you would consider",
                            primary=False,
                        ),
                    ],
                ),
                ready=False,
            )

        if depth is None:
            return ScopingTurnWire(
                reply="Deterministic stub Task Agent: choose how deep the scoping goes.",
                plan_draft=draft,
                part=_part(
                    "depth",
                    "Plan · depth",
                    "How deep should the scoping go?",
                    [
                        PartOptionWire(id=option_id, label=label, sub=sub, primary=False)
                        for option_id, label, sub in _STUB_DEPTH_OPTIONS
                    ],
                ),
                ready=False,
            )

        return ScopingTurnWire(
            reply=(
                "Deterministic stub Task Agent: check the plan; nothing runs "
                "until you confirm it."
            ),
            plan_draft=draft,
            part=None,
            ready=True,
        )


def resolve_scoping_task_agent_backend(
    *, live: bool, langfuse_client: Any = None
) -> ScopingTaskAgentBackend:
    """Return the live or stub scoping backend.

    Args:
        live: Whether provider egress is configured and wanted.
        langfuse_client: The resolved Langfuse client, when live.

    Returns:
        The chosen backend.
    """
    if live:
        return OpenAIScopingTaskAgentBackend(langfuse_client=langfuse_client)
    return StubScopingTaskAgentBackend()
