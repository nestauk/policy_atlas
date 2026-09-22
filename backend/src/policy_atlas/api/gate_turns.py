"""The Task Agent turn taken while a scoping walk is paused on its gate.

The chat stays open at the baseline gate (task 044, deliverable 8, D9). A turn
arriving while an options-scoping walk is **paused** is admitted, reserved as an
ordinary transcript row, and then *sorted* by the lead-authored gate sort into
one of three shapes:

- **question** — answered from the paused walk's own pinned evidence through
  the shared answer core, with citations; the walk stays paused and nothing is
  applied;
- **decision** — committed through the existing check-in response transaction,
  so a decision taken in words and a decision taken on the card land in exactly
  one place, bound to the run, the check-in and the plan version (A13, C5);
- **unsure** — asked back, in the product's own words, with the two options
  offered as quick replies.

The sort decides; this module dispatches. Nothing here infers a decision from a
question: a turn that asks and decides at once is answered, and the decision is
offered back for the user to take.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api import continuation
from policy_atlas.api.answer_core import AnswerBackends, AnswerPayload, answer_over_scope
from policy_atlas.api.chat_scope import resolve_run_components
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.evidence_search.synthesis.synthesis_tools import build_section_tools
from policy_atlas.runtime.agent_backend import AgentBackend
from policy_atlas.runtime.chat_backend import ChatBackend
from policy_atlas.runtime.gate_sort_prompt import GateSortWire

log = structlog.get_logger()

#: The gate option that ends the walk and leaves the plan editable.
CHANGE_PLAN = "change_plan"

#: What the turn says once each decision is durable. Code-authored: a recorded
#: decision must read the same however it was taken, so it is never a model's
#: sentence.
CONFIRM_REPLY = "Plan confirmed. Building the longlist now."
CHANGE_REPLY = "The run has stopped so you can change the plan."

#: The loser of a decision race. The decision is durable — the other surface
#: committed it — and this turn is durable too, saying so.
ALREADY_ANSWERED_REPLY = "This check-in was already answered."

#: What the product says when the sort cannot tell. It names what is available
#: rather than guessing, and it is honest about what is not (D10).
ASK_BACK_REPLY = (
    "I could not tell whether that is a question about the baseline or a "
    "decision. You can ask about the baseline, confirm the plan and build the "
    "longlist, or change the plan. Searching further is not available yet."
)

#: Appended to every answer at the gate: the decision stays the user's to take,
#: including on a turn that asked and decided at once.
OFFER_SENTENCE = (
    "When you are ready, you can confirm the plan and build the longlist, or "
    "change the plan."
)


@dataclass(frozen=True)
class PausedGate:
    """The pause a Task Agent turn arrived at, read once at reservation time.

    Args:
        capability_run_id: The parked walk.
        check_in_id: The pause the walk is waiting on.
        plan_version: The plan version the walk ran from — the version any
            decision is recorded against.
        options: The offered options as ``(id, label)`` pairs, in card order.
        artefact_id: The baseline artefact the card showed, when the bundle
            carried one; the answer's entry context.
    """

    capability_run_id: uuid.UUID
    check_in_id: uuid.UUID
    plan_version: int
    options: tuple[tuple[str, str], ...]
    artefact_id: uuid.UUID | None

    def label_for(self, option_id: str) -> str | None:
        """Return the offered label for one option id, or ``None`` if unoffered."""
        return next((label for oid, label in self.options if oid == option_id), None)

    def as_offered(self) -> list[dict[str, str]]:
        """Return the options in the shape the gate-sort prompt reads."""
        return [{"id": option_id, "label": label} for option_id, label in self.options]

    @property
    def option_labels(self) -> list[str]:
        """The offered labels, for quick replies."""
        return [label for _id, label in self.options]


@dataclass(frozen=True)
class GateAnswer:
    """One grounded answer produced at the gate.

    Args:
        prose: The answer, with the offer sentence appended.
        payload: The citation-bearing half of the answer.
    """

    prose: str
    payload: AnswerPayload


def read_paused_gate(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    capability_run_id: uuid.UUID,
    plan_version: int,
) -> PausedGate | None:
    """Read the pause a paused walk is waiting on, fail-closed.

    Args:
        conn: Open read connection (the caller's phase-one transaction).
        task_id: Task owning the walk.
        capability_run_id: The parked walk.
        plan_version: The walk's plan version.

    Returns:
        The gate, or ``None`` when the walk has no undecided pause or the pause
        offers no options — in which case the caller keeps the ordinary
        ``run_active`` refusal rather than admitting a turn it cannot dispatch.
    """
    found = continuation.pending_pause_for_walk(
        conn, task_id=task_id, capability_run_id=capability_run_id
    )
    if found is None:
        return None
    check_in_id, payload = found
    options = tuple(
        (str(option["id"]), str(option.get("label") or option["id"]))
        for option in payload.get("options", [])
        if isinstance(option, dict) and isinstance(option.get("id"), str)
    )
    if not options:
        return None
    bundle = payload.get("bundle")
    raw_artefact = bundle.get("artefact_id") if isinstance(bundle, dict) else None
    artefact_id: uuid.UUID | None = None
    if isinstance(raw_artefact, str):
        try:
            artefact_id = uuid.UUID(raw_artefact)
        except ValueError:
            artefact_id = None
    return PausedGate(
        capability_run_id=capability_run_id,
        check_in_id=check_in_id,
        plan_version=plan_version,
        options=options,
        artefact_id=artefact_id,
    )


def sort_turn(
    agent: AgentBackend,
    *,
    utterance: str,
    gate: PausedGate,
    session_id: uuid.UUID | None = None,
) -> GateSortWire:
    """Sort one gate turn, failing safe to ``unsure``.

    A backend error, an unknown kind, a decision naming an option the card did
    not offer, and a decision naming no option at all all resolve the same way:
    the product asks back. Guessing here would end a run in a state the user
    did not choose — the one failure this gate must not have (A4, C1).

    Args:
        agent: The agent backend seam.
        utterance: The user's verbatim turn text.
        gate: The pause the turn arrived at.
        session_id: Optional Langfuse session id (the task).

    Returns:
        A verdict whose ``kind`` is one of ``question``, ``decision`` or
        ``unsure``; a ``decision`` always names an offered option.
    """
    try:
        sort = agent.sort_gate_turn(utterance, gate.as_offered(), session_id=session_id)
    except Exception:
        log.warning("gate_sort_failed", check_in_id=str(gate.check_in_id), exc_info=True)
        return GateSortWire(kind="unsure", reason="The gate sort could not be read.")
    if sort.kind == "question":
        return sort
    if sort.kind == "decision" and gate.label_for(sort.option_id or "") is not None:
        return sort
    if sort.kind != "unsure":
        log.warning(
            "gate_sort_unusable",
            check_in_id=str(gate.check_in_id),
            kind=sort.kind,
            offered=sort.option_id is not None,
        )
    return GateSortWire(kind="unsure", reason=sort.reason)


def answer_at_gate(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    gate: PausedGate,
    question: str,
    window: list[tuple[str, str]],
    chat_backend: ChatBackend,
    embedding_backend: EmbeddingBackend | None,
    langfuse_client: Any,
    trace_run_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
) -> GateAnswer | None:
    """Answer one question over the paused walk's pinned evidence.

    Args:
        engine: Database engine; the answer core writes nothing.
        task_id: Task owning the walk and its evidence.
        gate: The pause the turn arrived at.
        question: The user's turn text.
        window: Prior ``(user_message, reply)`` pairs from this conversation.
        chat_backend: The chat writer seam.
        embedding_backend: The retrieval embedder seam.
        langfuse_client: Tracing client, or ``None``.
        trace_run_id: The transcript row this answer is traced under.
        conversation_id: The owning Task Agent conversation.

    Returns:
        The prose (with the offer sentence) and its citation payload, or
        ``None`` when the walk this question was admitted at no longer offers
        a scope to answer over — the card resumed it while the sort was
        running (C7). That is a race the user lost, not a server fault: the
        caller completes the turn saying the check-in was already answered.
    """
    scope = resolve_run_components(engine, task_id, capability_run_id=gate.capability_run_id)
    if scope is None:
        log.info(
            "gate_turn_answer_scope_gone",
            task_id=str(task_id),
            capability_run_id=str(gate.capability_run_id),
        )
        return None
    prose, payload = answer_over_scope(
        engine,
        task_id=task_id,
        scope=scope,
        entry_artefact_id=gate.artefact_id,
        window=window,
        question=question,
        backends=AnswerBackends(
            chat=chat_backend,
            embedding=embedding_backend,
            langfuse=langfuse_client,
            # Resolved from this module at call time, as the chat route
            # resolves its own tool set.
            tools_builder=build_section_tools,
        ),
        trace_run_id=trace_run_id,
        # A Task Agent turn keeps the task's session, like every planning
        # turn and run (ADR 0038); only the chat route keys on its conversation.
        trace_session_id=task_id,
        conversation_id=conversation_id,
    )
    return GateAnswer(prose=f"{prose}\n\n{OFFER_SENTENCE}", payload=payload)


@dataclass(frozen=True)
class DecisionOutcome:
    """What committing a decision at the gate did.

    Args:
        recorded: Whether this turn wrote the decision (``False`` when another
            surface had already answered the check-in).
        reply: The code-authored sentence the turn carries.
        carried_text: The planning instruction a "change the plan" decision
            carried, when it had one — the second half of the same turn.
        continue_walk: The walk to resume, when the decision asked for one; the
            caller dispatches it after its own turn row is durable.
        follow_on: The walk the caller opens after the commit, or ``None``
            (task 045): ``"longlist"`` for "Confirm plan and build longlist".
    """

    recorded: bool
    reply: str
    carried_text: str | None = None
    continue_walk: uuid.UUID | None = None
    follow_on: str | None = None


def _collapsed(text: str) -> str:
    """Return one text with its whitespace collapsed, for comparison only."""
    return " ".join(text.split()).casefold()


def verbatim_carried_text(
    carried_text: str | None, *, utterance: str, check_in_id: uuid.UUID
) -> str | None:
    """Keep the sort's carried instruction only when the user actually said it (S2).

    ``carried_text`` becomes the **planner's message** on a "change the plan"
    turn, so it is the one piece of the sort's output that is treated as the
    user speaking. Model output is not the user speaking: a sort that
    paraphrased, expanded or invented an instruction would put words the user
    never typed into the plan the next version is built from.

    So it is accepted only when it appears verbatim inside the utterance
    (whitespace collapsed, case-insensitively — the sort may quote across a
    line break or lowercase a sentence start, and neither changes the words).
    Anything else falls back to the **whole utterance**, which is always the
    user's own words, at the cost of giving the planner a little more context
    than the sort wanted to.

    Args:
        carried_text: The instruction the sort carried, if any.
        utterance: The user's verbatim turn text.
        check_in_id: The pause, for the warning line.

    Returns:
        The instruction to hand the planner, or ``None`` when the turn carried
        no instruction at all (an ordinary decision, with no second half).
    """
    if carried_text is None or not carried_text.strip():
        return None
    if _collapsed(carried_text) in _collapsed(utterance):
        return carried_text.strip()
    log.warning(
        "gate_sort_carried_text_not_verbatim",
        check_in_id=str(check_in_id),
        carried_chars=len(carried_text),
    )
    return utterance.strip() or None


def commit_decision(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    gate: PausedGate,
    option_id: str,
    carried_text: str | None,
    utterance: str,
    actor: str,
) -> DecisionOutcome:
    """Commit one decision taken in words through the check-in transaction.

    The card and the chat share one transaction and one durability rule, so the
    loser of a race is refused there (``AlreadyAnsweredError``) rather than
    writing a second decision. That refusal does **not** fail the turn: the turn
    itself is durable and says the check-in was already answered, which is what
    the user needs to read in the thread.

    Args:
        engine: Database engine.
        task_id: Task owning the walk.
        gate: The pause being answered.
        option_id: The offered option the sort chose.
        carried_text: The instruction a "change the plan" turn carried, kept
            only when it is the user's own words
            (:func:`verbatim_carried_text`).
        utterance: The user's verbatim turn text, which that check is against.
        actor: Authenticated actor recorded in logs.

    Returns:
        What was committed and what the turn should say.
    """
    try:
        result = continuation.answer_check_in(
            engine,
            task_id=task_id,
            check_in_id=gate.check_in_id,
            response={"kind": "option", "option_id": option_id},
            actor=actor,
        )
    except continuation.AlreadyAnsweredError:
        log.info(
            "gate_turn_decision_already_answered",
            task_id=str(task_id),
            check_in_id=str(gate.check_in_id),
        )
        return DecisionOutcome(recorded=False, reply=ALREADY_ANSWERED_REPLY)
    continue_walk = result.capability_run_id if result.continuation_requested else None
    if option_id == CHANGE_PLAN:
        return DecisionOutcome(
            recorded=True,
            reply=CHANGE_REPLY,
            carried_text=verbatim_carried_text(
                carried_text, utterance=utterance, check_in_id=gate.check_in_id
            ),
            continue_walk=continue_walk,
        )
    return DecisionOutcome(
        recorded=True,
        reply=CONFIRM_REPLY,
        continue_walk=continue_walk,
        follow_on=result.follow_on,
    )
