"""Agent backend seam (task 024, decision 3) — router + watch moments.

Mirrors :mod:`policy_atlas.runtime.planner`: a live OpenAI structured-output
backend with tracing inside the backend, and a deterministic zero-egress stub for
tests and the CLI. One backend, three moments (contract decision 3): the planning
moment lives in the planner seam; this module owns the two mid-run moments —

- **route**: compiles a user's free-text steering prose at a pause into a fan-out
  plan of bounded directive deltas (Task 15 wires its APPLY path; Task 14 only
  ships the seam + stub + wire-shape);
- **triage**: the mini-class notable-or-not verdict on an anomalous / trigger-fired
  boundary (push-only, no tools);
- **decide**: the judgment-class in-loco-user decision at a delegated decision
  point, and — with ``framing="authoring"`` — the authored-options composition
  that rides an attended pause alongside the canonical floor.

This module also owns the **structurally-gated invocation** classifier, the
**single-shot decide + bounded fallback deliberation loop** (contract decision 3's
information+cost model), and the fail-safe **discretion-hook adapter** that bridges
``decide`` into the runner's Task-12 :data:`DiscretionHook` seam for the Unattended
path. Every LLM moment fails safe: the runner catches any backend exception and
degrades to the deterministic floor (watch discipline 5).
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import structlog
from langfuse import Langfuse
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import parse_structured, resolve_openai_client
from policy_atlas.core.prompt_fields import scrub_nul
from policy_atlas.core.usage import UsageResult, usage_metadata
from policy_atlas.evidence_search.assess.screen_prompt import SCREEN_MODEL
from policy_atlas.runtime.agent_prompt import (
    ROUTER_MAX_OUTPUT_TOKENS,
    ROUTER_PROMPT_VERSION,
    WATCH_DECISION_MAX_OUTPUT_TOKENS,
    WATCH_PROMPT_VERSION,
    WATCH_TRIAGE_MAX_OUTPUT_TOKENS,
    RouterCompileTransport,
    RouterCompileWire,
    WatchDecisionTransport,
    WatchDecisionWire,
    WatchTriageWire,
    build_router_messages,
    build_watch_messages,
)

if TYPE_CHECKING:
    from policy_atlas.runtime.runner import _DiscretionContext, _DiscretionOutcome

log = structlog.get_logger()

# Model routing by moment (contract decision 3 — cost tiering, not agent identity).
# route/decide are judgment-class (the planner's default judgment model); triage is
# mini-class (the screen/vetter mini default). Both env-overridable so ops can pin a
# different model without a code change (the SYNTHESIS_MODEL/PLANNER_MODEL pattern).
AGENT_MODEL = os.environ.get("POLICY_ATLAS_AGENT_MODEL", "gpt-5.5")
AGENT_TRIAGE_MODEL = os.environ.get(
    "POLICY_ATLAS_AGENT_TRIAGE_MODEL", SCREEN_MODEL
)

# Fallback deliberation loop cap (internal constant + telemetry, never plan content
# — costs are dev-side only, contract decision 3). At most this many
# lookup/query_findings round-trips answer a decide's 'insufficient'.
WATCH_FALLBACK_TOOL_CALLS = 2
# The hard-coded read-tool allowlist for the deliberation loop: NEVER ``retrieve``,
# NEVER ``search`` (contract decision 3). An insufficient naming anything else is
# rejected and biases to escalate.
WATCH_READ_TOOLS: tuple[str, ...] = ("lookup", "query_findings")

# The wire models ARE the moment shapes, code-side and model-side — no separate
# dataclass to keep in sync (the planner pattern).
RouterCompile = RouterCompileWire
WatchTriage = WatchTriageWire
WatchDecision = WatchDecisionWire


# --- The backend protocol --------------------------------------------------


class AgentBackend(Protocol):
    """The agent seam for the router and watch moments.

    Backends return one structurally parsed wire model per call; transport, parse
    and code-side validation failures raise so the CALLER (the runner) can catch
    them and degrade to the deterministic floor (watch discipline 5). The backend
    itself never swallows an error into a silent floor — fail-safe is the caller's
    contract, so the seam stays honest about failure.
    """

    def route(
        self,
        utterance: str,
        pause_context: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
    ) -> RouterCompileWire:
        """Compile a free-text steering utterance into a fan-out plan.

        Args:
            utterance: The user's verbatim free-text steering prose.
            pause_context: Deterministic pause state — point, canonical options,
                not-yet-run components, re-run surface.
            session_id: Optional Langfuse session id shared by the conversation.

        Returns:
            One parsed router compile.

        Raises:
            RuntimeError: If the backend cannot produce a usable compile.
        """
        ...

    def triage(
        self,
        request: str,
        header: dict[str, Any],
        payload: dict[str, Any],
        digest: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
    ) -> WatchTriageWire:
        """Return the mini-class notable-or-not verdict for a boundary check-in.

        Args:
            request: The concrete ask for this triage call.
            header: Orienting header — refined question, plan summary, mode.
            payload: Boundary payload — check-in render, fired triggers, options.
            digest: Run-so-far digest incl. prior steering decisions.
            session_id: Optional Langfuse session id.

        Returns:
            One parsed triage verdict.

        Raises:
            RuntimeError: If the backend cannot produce a usable verdict.
        """
        ...

    def decide(
        self,
        request: str,
        header: dict[str, Any],
        payload: dict[str, Any],
        digest: dict[str, Any],
        *,
        framing: str = "decision",
        session_id: uuid.UUID | None = None,
    ) -> WatchDecisionWire:
        """Decide in loco user (``framing="decision"``) or author options.

        The authoring framing rides ``decide`` with a request that asks for
        ``authored_options`` — one method, ``framing`` selects the system prompt
        (:func:`build_watch_messages`).

        Args:
            request: The concrete ask for this call.
            header: Orienting header.
            payload: Boundary payload — includes the pre-fetched decision bundle.
            digest: Run-so-far digest.
            framing: ``"decision"`` | ``"authoring"``.
            session_id: Optional Langfuse session id.

        Returns:
            One parsed watch decision (its ``authored_options`` populated under the
            authoring framing).

        Raises:
            RuntimeError: If the backend cannot produce a usable decision.
        """
        ...


# --- Live OpenAI implementation --------------------------------------------


def _scrub_router(compile_result: RouterCompileWire) -> RouterCompileWire:
    fragments = [
        fragment.model_copy(
            update={
                "fragment_text": scrub_nul(fragment.fragment_text),
                "refusal_reason": (
                    scrub_nul(fragment.refusal_reason)
                    if fragment.refusal_reason is not None
                    else None
                ),
            }
        )
        for fragment in compile_result.fragments
    ]
    return compile_result.model_copy(
        update={"fragments": fragments, "summary": scrub_nul(compile_result.summary)}
    )


def _scrub_triage(triage: WatchTriageWire) -> WatchTriageWire:
    return triage.model_copy(update={"reason": scrub_nul(triage.reason)})


def _scrub_decision(decision: WatchDecisionWire) -> WatchDecisionWire:
    updates: dict[str, Any] = {"reasoning": scrub_nul(decision.reasoning)}
    if decision.needs is not None:
        updates["needs"] = scrub_nul(decision.needs)
    if decision.authored_options is not None:
        updates["authored_options"] = [
            option.model_copy(
                update={"label": scrub_nul(option.label), "why": scrub_nul(option.why)}
            )
            for option in decision.authored_options
        ]
    return decision.model_copy(update=updates)


class OpenAIAgentBackend:
    """Live OpenAI implementation of the agent seam.

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
            backend_name="OpenAIAgentBackend",
            timeout=180.0,
            max_retries=2,
        )
        self._langfuse_client = langfuse_client

    def route(
        self,
        utterance: str,
        pause_context: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
    ) -> RouterCompileWire:
        """Compile a steering utterance through structured OpenAI output."""
        messages = build_router_messages(utterance, pause_context)
        parsed = self._parse(
            messages,
            response_format=RouterCompileTransport,
            model=AGENT_MODEL,
            max_output_tokens=ROUTER_MAX_OUTPUT_TOKENS,
            usage_event="agent.route.usage",
            label="agent-route",
            prompt_version=ROUTER_PROMPT_VERSION,
            name="agent:route",
            session_id=session_id,
        )
        return _scrub_router(parsed.to_wire())

    def triage(
        self,
        request: str,
        header: dict[str, Any],
        payload: dict[str, Any],
        digest: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
    ) -> WatchTriageWire:
        """Return a mini-class triage verdict through structured OpenAI output."""
        messages = build_watch_messages(
            framing="triage", request=request, header=header, payload=payload, digest=digest
        )
        parsed = self._parse(
            messages,
            response_format=WatchTriageWire,
            model=AGENT_TRIAGE_MODEL,
            max_output_tokens=WATCH_TRIAGE_MAX_OUTPUT_TOKENS,
            usage_event="agent.triage.usage",
            label="agent-triage",
            prompt_version=WATCH_PROMPT_VERSION,
            name="agent:triage",
            session_id=session_id,
        )
        return _scrub_triage(parsed)

    def decide(
        self,
        request: str,
        header: dict[str, Any],
        payload: dict[str, Any],
        digest: dict[str, Any],
        *,
        framing: str = "decision",
        session_id: uuid.UUID | None = None,
    ) -> WatchDecisionWire:
        """Decide / author through structured OpenAI output (judgment-class)."""
        messages = build_watch_messages(
            framing=framing, request=request, header=header, payload=payload, digest=digest
        )
        parsed = self._parse(
            messages,
            response_format=WatchDecisionTransport,
            model=AGENT_MODEL,
            max_output_tokens=WATCH_DECISION_MAX_OUTPUT_TOKENS,
            usage_event="agent.decide.usage",
            label="agent-decide",
            prompt_version=WATCH_PROMPT_VERSION,
            name=f"agent:{framing}",
            session_id=session_id,
        )
        return _scrub_decision(parsed.to_wire())

    def _parse[T: BaseModel](
        self,
        messages: list[ChatCompletionMessageParam],
        *,
        response_format: type[T],
        model: str,
        max_output_tokens: int,
        usage_event: str,
        label: str,
        prompt_version: str,
        name: str,
        session_id: uuid.UUID | None,
    ) -> T:
        def _call() -> UsageResult[T]:
            return parse_structured(
                self._client,
                messages=messages,
                response_format=response_format,
                usage_event=usage_event,
                label=label,
                model=model,
                max_completion_tokens=max_output_tokens,
            )

        def _update(span: Any, result: UsageResult[T]) -> None:
            parsed, usage = result
            span.update(
                input={"messages": messages},
                output=parsed.model_dump(),
                model=model,
                metadata={"prompt_version": prompt_version, **usage_metadata(usage)},
            )

        parsed, _usage = tracing.traced_call(
            self._langfuse_client,
            name=name,
            as_type="generation",
            call=_call,
            session_id=session_id,
            update=_update,
        )
        return parsed


# --- Deterministic zero-egress stub ----------------------------------------


def _refuse_all_router() -> RouterCompileWire:
    """The stub default: an honest whole-utterance refusal, no delta (fail-closed)."""
    from policy_atlas.runtime.agent_prompt import RouterFragmentWire

    return RouterCompileWire(
        fragments=[
            RouterFragmentWire(
                fragment_text="(stub) the whole utterance",
                compiles=False,
                refusal_reason="Deterministic stub router: refuses every intent honestly.",
            )
        ],
        summary="Deterministic stub router: nothing compiled.",
    )


def _not_notable() -> WatchTriageWire:
    return WatchTriageWire(notable=False, reason="Deterministic stub triage: not notable.")


def _proceed() -> WatchDecisionWire:
    return WatchDecisionWire(
        action="proceed", reasoning="Deterministic stub decide: nothing to change."
    )


class StubAgentBackend:
    """Deterministic, zero-egress, scriptable agent backend for tests/CLI.

    Every moment is scriptable through a queue of canned responses consumed FIFO,
    with the last entry repeating once the queue drains — so a single canned value
    or a scripted sequence (e.g. insufficient → proceed for the fallback loop) both
    work. The defaults honour the contract's fail-closed floor: route refuses
    everything honestly, triage is not-notable, decide proceeds. Call counts are
    exposed so a test can assert a boundary made no backend call.

    Args:
        route_responses: Canned :class:`RouterCompileWire` value(s), or ``None``.
        triage_responses: Canned :class:`WatchTriageWire` value(s), or ``None``.
        decide_responses: Canned :class:`WatchDecisionWire` value(s), or ``None``.
    """

    def __init__(
        self,
        *,
        route_responses: RouterCompileWire | list[RouterCompileWire] | None = None,
        triage_responses: WatchTriageWire | list[WatchTriageWire] | None = None,
        decide_responses: WatchDecisionWire | list[WatchDecisionWire] | None = None,
    ) -> None:
        self._route_queue = _as_queue(route_responses)
        self._triage_queue = _as_queue(triage_responses)
        self._decide_queue = _as_queue(decide_responses)
        self.route_calls = 0
        self.triage_calls = 0
        self.decide_calls = 0

    def route(
        self,
        utterance: str,
        pause_context: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
    ) -> RouterCompileWire:
        del utterance, pause_context, session_id
        self.route_calls += 1
        return _next(self._route_queue, _refuse_all_router)

    def triage(
        self,
        request: str,
        header: dict[str, Any],
        payload: dict[str, Any],
        digest: dict[str, Any],
        *,
        session_id: uuid.UUID | None = None,
    ) -> WatchTriageWire:
        del request, header, payload, digest, session_id
        self.triage_calls += 1
        return _next(self._triage_queue, _not_notable)

    def decide(
        self,
        request: str,
        header: dict[str, Any],
        payload: dict[str, Any],
        digest: dict[str, Any],
        *,
        framing: str = "decision",
        session_id: uuid.UUID | None = None,
    ) -> WatchDecisionWire:
        del request, header, payload, digest, framing, session_id
        self.decide_calls += 1
        return _next(self._decide_queue, _proceed)


def _as_queue[T](value: T | list[T] | None) -> list[T]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _next[T](queue: list[T], default: Callable[[], T]) -> T:
    if not queue:
        return default()
    if len(queue) == 1:
        return queue[0]
    return queue.pop(0)


# --- Structurally-gated invocation classifier (contract decision 3) --------

BoundaryClass = str  # "clean_boundary" | "triage" | "decision_point"


def classify_boundary(
    *,
    is_decision_point: bool,
    triggers_fired: bool,
    anomalous: bool,
) -> BoundaryClass:
    """Classify a boundary for the gated invocation model.

    The watch is called only at (i) decision points, (ii) trigger-fired boundaries,
    (iii) anomalous check-ins. A boundary matching none of those is CLEAN and
    resolves with no LLM call (contract decision 3 — structure first, judgement for
    the residual).

    Args:
        is_decision_point: True when the mode routes this lattice boundary to the
            watch to decide (Unattended, no pinned rule) or author (attended pause).
        triggers_fired: True when the floor triggers fired at this boundary.
        anomalous: True when the check-in is a failure / retry / skip / degrade.

    Returns:
        ``"decision_point"``, ``"triage"``, or ``"clean_boundary"``.
    """
    if is_decision_point:
        return "decision_point"
    if triggers_fired or anomalous:
        return "triage"
    return "clean_boundary"


# --- The single-shot decide + bounded fallback deliberation loop -----------


@dataclass(frozen=True)
class DeliberationStep:
    """One read-tool round-trip in the watch's bounded fallback loop.

    Args:
        tool: The read tool called (always inside :data:`WATCH_READ_TOOLS`).
        args_digest: A bounded digest of the arguments passed.
        result_digest: A bounded digest of the tool result.
    """

    tool: str
    args_digest: str
    result_digest: str

    def as_payload(self) -> dict[str, str]:
        """Return the JSON-safe event payload for this step (replay substrate)."""
        return {
            "tool": self.tool,
            "args_digest": self.args_digest,
            "result_digest": self.result_digest,
        }


@dataclass
class WatchDecisionResult:
    """The normalised outcome of a gated single-shot decide (+ any deliberation).

    Args:
        decision: The final parsed :class:`WatchDecisionWire` the watch settled on
            (its ``action`` may be ``escalate`` when the loop capped without one).
        deliberation: The ordered read-tool steps taken, each ``{tool, args_digest,
            result_digest}`` — every step lands in the decision event's
            ``deliberation`` key so replay shows what the watch looked at.
        escalated_reason: When the loop biased to escalate, the reason (evented);
            ``None`` when the watch decided within its budget.
    """

    decision: WatchDecisionWire
    deliberation: list[DeliberationStep] = field(default_factory=list)
    escalated_reason: str | None = None

    @property
    def deliberation_payload(self) -> list[dict[str, str]]:
        return [step.as_payload() for step in self.deliberation]


# Cap on a folded deliberation-loop tool result (distinct from the smaller
# event-record digest default): bounds a hostile oversized read result so it
# cannot crowd steer_point/triggers out of the payload's own truncation prefix
# (see run_watch_decision).
FOLDED_RESULT_MAX = 2000


def _digest(value: Any, *, max_chars: int = 500) -> str:
    """A bounded, deterministic digest of tool args / results for the event record."""
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def _parse_needs(
    needs: str | None,
    needs_tool: str | None = None,
    needs_arguments: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Resolve a decide's insufficient-context read request, fail-closed.

    The structured wire fields (``needs_tool`` + ``needs_arguments``) are the
    primary channel; the legacy JSON-in-``needs`` shape (``{"tool": ...,
    "arguments": {...}}``) survives as a fallback. Anything that resolves to
    neither — or names a tool outside the read allowlist (checked by the
    caller) — returns ``None``, so the caller biases to escalate rather than
    guessing an unbounded read (honest absence).
    """
    if isinstance(needs_tool, str) and needs_tool:
        return needs_tool, needs_arguments if isinstance(needs_arguments, dict) else {}
    if not needs:
        return None
    try:
        parsed = json.loads(needs)
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    tool = parsed.get("tool")
    arguments = parsed.get("arguments", {})
    if not isinstance(tool, str) or not isinstance(arguments, dict):
        return None
    return tool, arguments


def run_watch_decision(
    backend: AgentBackend,
    *,
    request: str,
    header: dict[str, Any],
    payload: dict[str, Any],
    digest: dict[str, Any],
    framing: str = "decision",
    read_tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
    session_id: uuid.UUID | None = None,
) -> WatchDecisionResult:
    """Run the single-shot decide plus the bounded fallback deliberation loop.

    The watch decides in one turn. Only when it returns ``action='insufficient'``
    does the loop issue the named read via ``lookup``/``query_findings`` ONLY
    (never ``retrieve``, never ``search`` — the allowlist is hard-coded), append the
    ``{tool, args_digest, result_digest}`` to the deliberation record, and re-invoke
    ``decide`` with the result folded into a mutated payload copy. At most
    :data:`WATCH_FALLBACK_TOOL_CALLS` round-trips run; still insufficient (or a read
    outside the allowlist / unparseable) biases to escalate, reason evented.

    Backend exceptions are NOT caught here — the runner catches them and degrades to
    the floor (watch discipline 5). This function owns only the deliberation bound
    and the allowlist, both dev-side constants.

    Args:
        backend: The agent backend.
        request: The decide request line.
        header: Orienting header.
        payload: Boundary payload incl. the pre-fetched bundle.
        digest: Run-so-far digest.
        framing: ``"decision"`` | ``"authoring"``.
        read_tools: Executable read tools keyed by name; only allowlisted keys are
            ever invoked. ``None`` means no reads are possible — an insufficient
            then escalates immediately.
        session_id: Optional Langfuse session id.

    Returns:
        The normalised :class:`WatchDecisionResult`.
    """
    steps: list[DeliberationStep] = []
    working_payload = dict(payload)
    decision = backend.decide(
        request, header, working_payload, digest, framing=framing, session_id=session_id
    )
    for _round in range(WATCH_FALLBACK_TOOL_CALLS):
        if decision.action != "insufficient":
            return WatchDecisionResult(decision=decision, deliberation=steps)
        parsed = _parse_needs(
            decision.needs,
            getattr(decision, "needs_tool", None),
            getattr(decision, "needs_arguments", None),
        )
        if parsed is None:
            return _escalate(
                decision, steps, "insufficient request could not be resolved to a read tool"
            )
        tool, arguments = parsed
        if tool not in WATCH_READ_TOOLS:
            return _escalate(
                decision, steps, f"requested tool {tool!r} is outside the read allowlist"
            )
        executor = (read_tools or {}).get(tool)
        if executor is None:
            return _escalate(
                decision, steps, f"read tool {tool!r} is unavailable at this boundary"
            )
        try:
            result = executor(arguments)
        except Exception as exc:  # noqa: BLE001 — a read failure biases to escalate
            log.warning("agent.deliberation_read_failed", tool=tool, error=str(exc)[:200])
            return _escalate(decision, steps, f"read tool {tool!r} failed")
        step = DeliberationStep(
            tool=tool, args_digest=_digest(arguments), result_digest=_digest(result)
        )
        steps.append(step)
        # Fold the read result into a bounded deliberation record on the payload copy
        # so the re-invoked decide sees what it asked for (data, not instructions).
        # The result is untrusted tool output (e.g. a hostile oversized
        # query_findings hit) — bound it here too, not just the evented digest,
        # so it cannot push steer_point/triggers out of the sort_keys=True
        # truncation prefix applied to the whole payload downstream.
        deliberation_record = list(working_payload.get("deliberation", []))
        deliberation_record.append(
            step.as_payload() | {"result": _digest(result, max_chars=FOLDED_RESULT_MAX)}
        )
        working_payload = {**working_payload, "deliberation": deliberation_record}
        decision = backend.decide(
            request, header, working_payload, digest, framing=framing, session_id=session_id
        )
    if decision.action == "insufficient":
        return _escalate(
            decision, steps, "still insufficient after the deliberation cap — biasing to escalate"
        )
    return WatchDecisionResult(decision=decision, deliberation=steps)


def _escalate(
    decision: WatchDecisionWire, steps: list[DeliberationStep], reason: str
) -> WatchDecisionResult:
    """Force an escalate outcome, preserving the deliberation trail and reason."""
    escalated = decision.model_copy(update={"action": "escalate"})
    return WatchDecisionResult(
        decision=escalated, deliberation=steps, escalated_reason=reason
    )


# --- Discretion-hook adapter (bridges decide into the Task-12 seam) --------


def build_watch_discretion_hook(
    backend: AgentBackend,
    *,
    session_id: uuid.UUID | None = None,
) -> Callable[[_DiscretionContext], _DiscretionOutcome]:
    """Build a runner :data:`DiscretionHook` that decides via the watch backend.

    Consulted by the runner ONLY at an Unattended lattice boundary with NO pinned
    rule (the authority order — declared rules > agent — is enforced in the
    runner, which resolves a pinned rule before ever calling the hook). The runner
    populates the :class:`_DiscretionContext` with the pre-fetched ``bundle``, the
    orienting ``header``, the run-so-far ``digest`` and the boundary's allowlisted
    ``read_tools``; the hook runs the single-shot decide + bounded fallback loop and
    maps the watch's action onto a :class:`_DiscretionOutcome`:

    - ``proceed`` / ``escalate`` / insufficient-after-cap → proceed + a loud rule
      label (there is no user to escalate to in Unattended — proceed + loudest flag,
      reason on the outcome), the deliberation trail attached for the event;
    - ``choose_option`` / ``author`` → the watch's delta applied through the SAME
      apply machinery a standing rule uses, attributed to the agent.

    ANY backend exception degrades to the deterministic floor (watch discipline 5):
    the hook never raises, so the run never depends on the judgement layer.
    """
    from policy_atlas.runtime.runner import (  # local import avoids a cycle
        UNCONFIGURED_DEFAULT_RULE,
        _DiscretionOutcome,
    )

    def _hook(context: _DiscretionContext) -> _DiscretionOutcome:
        try:
            payload: dict[str, Any] = {
                "steer_point": context.steer_point,
                "boundary": context.boundary,
                "component": context.component,
                "triggers": context.triggers,
                "bundle": context.bundle,
            }
            result = run_watch_decision(
                backend,
                request=f"decide at {context.steer_point}",
                header=context.header,
                payload=payload,
                digest=context.digest,
                framing="decision",
                read_tools=context.read_tools,
                session_id=session_id,
            )
        except Exception as exc:  # noqa: BLE001 — fail-safe to the deterministic floor
            log.warning(
                "agent.watch_hook_failed",
                steer_point=context.steer_point,
                error=str(exc)[:200],
            )
            return _DiscretionOutcome(
                interpreted_action="proceed", rule=UNCONFIGURED_DEFAULT_RULE
            )

        decision = result.decision
        deliberation = result.deliberation_payload
        profile = {"model": AGENT_MODEL, "prompt_version": WATCH_PROMPT_VERSION}
        if decision.action in {"choose_option", "author"} and decision.delta:
            return _DiscretionOutcome(
                interpreted_action="apply",
                rule="agent_decision",
                delta=decision.delta,
                component=decision.component,
                rerun_mode=decision.rerun_mode,
                reasoning=decision.reasoning,
                deliberation=deliberation,
                profile=profile,
            )
        # proceed / escalate / insufficient-after-cap: there is no user to escalate
        # to in Unattended, so proceed + the loudest flag, with the reason evented.
        rule = (
            "agent_escalation"
            if decision.action == "escalate"
            else UNCONFIGURED_DEFAULT_RULE
        )
        return _DiscretionOutcome(
            interpreted_action="proceed",
            rule=rule,
            reasoning=result.escalated_reason or decision.reasoning,
            deliberation=deliberation,
            profile=profile,
        )

    return _hook
