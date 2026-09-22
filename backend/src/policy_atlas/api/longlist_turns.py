"""The Task Agent turn taken while a longlist exists and no walk is active.

Task 045, deliverable 10 (D13, A8, A14; ADR 0039 decision 11). While an
options-scoping task has a longlist and no parentless walk is running or
paused, a Task Agent turn is admitted, reserved as an ordinary transcript row
and then *sorted* by the lead-authored ``longlist_verbs_v1`` surface into one
of five shapes:

- **question** — answered by the shared answer core over the longlist walk
  and every option search's targeted scope (``chat_scope``'s scoping
  branch), with citations; nothing is applied, and an action awaiting
  confirmation stays waiting;
- **add** · **exclude** · **include again** — a verb, which is **never
  applied on the turn that names it**: the turn proposes the action back in
  words (for *add*, with the design ``option_design_v1`` proposes back) and
  stores it as the conversation's pending action;
- **other** — the product says what the longlist chat can do.

The **next** turn applies the pending action when it confirms it: the
proposal's button (a ``[confirm part=longlist_action option=confirm]``
marker on the message's final line, the 044 button-confirm pattern) or a
turn the sort reads as plain assent. A turn naming a different verb replaces
the pending action and says so. Applying calls the apply functions the
buttons call (:mod:`policy_atlas.api.longlist_actions`), which write the
option state and one History event as the user's turn.

**Where the pending action lives.** In the transcript row's
``task_agent_state``, as ``{"pending": {...}}`` — the latest *completed* row
of the conversation carries it forward; only an applied action, a replacing
verb, or the button or assent clears it. The
planner never reads such a state as a plan draft
(:func:`is_longlist_state`).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import structlog
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.answer_core import AnswerBackends, answer_over_scope
from policy_atlas.api.chat_scope import resolve_terminal_run_components
from policy_atlas.api.contract import (
    AnswerPayloadOut,
    PartOptionOut,
    PartProposalOut,
    TaskAgentTurnOut,
    TurnActionOut,
)
from policy_atlas.api.locks import task_lock
from policy_atlas.api.longlist_actions import (
    LonglistActionRefused,
    OptionNotFound,
    add_option,
    current_plan_row,
    exclude_option,
    include_option,
    propose_design,
)
from policy_atlas.core import tracing
from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.core.schema import longlist_result, option, task_agent_transcript
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    RetrievalUnitCapError,
    build_section_tools,
)
from policy_atlas.options_scoping.design import OptionDesign
from policy_atlas.runtime.agent_backend import AgentBackend
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, capability_of_task
from policy_atlas.runtime.chat_backend import ChatBackend
from policy_atlas.runtime.longlist_verbs_prompt import LonglistVerbWire
from policy_atlas.runtime.runner import RunnerBackends

log = structlog.get_logger()

Verb = Literal["add", "exclude", "include_again"]

_KINDS = frozenset({"question", "add", "exclude", "include_again", "other"})

#: The part id of the proposal's confirm button, and its one option.
ACTION_PART_ID = "longlist_action"
CONFIRM_OPTION_ID = "confirm"

#: The 044 button-confirm marker (the client's ``confirmTarget`` grammar), read
#: off the message's final line.
_CONFIRM_MARKER = re.compile(r"^\[confirm part=([a-z_]+) option=([a-z0-9_]+)\]$")

# --- The reply strings (the lead's copy pass polishes these) -----------------

OTHER_REPLY = (
    "Here you can ask about the longlist, add an option, exclude an option, or "
    "include an excluded option again. Assessing options, searching further and "
    "changing the plan are done elsewhere: change the plan in the plan document."
)
NOTHING_PENDING_REPLY = "There is nothing waiting to be confirmed."
WHICH_OPTION_REPLY = "Which option do you mean? Name it as it appears on the longlist."
WHAT_TO_ADD_REPLY = "What option would you like to add? Describe it in a few words."
DESIGN_UNAVAILABLE_REPLY = "Policy Atlas could not read a design from those words; try again."
TOO_MANY_DOCUMENTS_REPLY = "There are too many documents to search at once; ask about one option."
NO_SCOPE_REPLY = "There is no finished longlist to answer from yet."
OPTION_GONE_REPLY = "That option is no longer on the longlist."

_VERB_PHRASE: dict[str, str] = {
    "add": "add",
    "exclude": "exclude",
    "include_again": "include again",
}


def exclude_proposal(name: str, reason: str | None) -> str:
    """The sorting turn's words for a proposed *exclude*."""
    return f"Exclude *{name}*? Reason: *{reason or 'none given'}*. Confirm to apply."


def include_proposal(name: str) -> str:
    """The sorting turn's words for a proposed *include again*."""
    return f"Include *{name}* again? Confirm to apply."


def add_proposal(design: OptionDesign) -> str:
    """The sorting turn's words for a proposed *add*, with the design proposed back."""
    description = design.description.rstrip(" .")
    features = "; ".join(feature.rstrip(" .;") for feature in design.design_features)
    return (
        f"Add *{design.name}* — {description}? Design: {features}. "
        "Confirm to add it and search for it."
    )


def proposal_sentence(pending: PendingAction) -> str:
    """The words a pending action was proposed with, re-rendered from its state."""
    if pending.verb == "add" and pending.design is not None:
        return add_proposal(pending.design)
    if pending.verb == "exclude":
        return exclude_proposal(pending.label, pending.reason)
    return include_proposal(pending.label)


def still_waiting(pending: PendingAction) -> str:
    """The reminder an ``other`` turn carries while an action awaits confirmation."""
    return f"Still waiting: {proposal_sentence(pending)}"


def _applied_reply(verb: Verb, name: str) -> str:
    if verb == "exclude":
        return f"Excluded *{name}*."
    if verb == "include_again":
        return f"Included *{name}* again."
    return f"Added *{name}*. Searching for its evidence now."


def _already_reply(name: str, state: str) -> str:
    return f"*{name}* is already {state}."


def _replaced_prefix(previous: PendingAction) -> str:
    return (
        f"This replaces the earlier proposal to {_VERB_PHRASE[previous.verb]} *{previous.label}*."
    )


# --- The surface read at reservation -----------------------------------------


@dataclass(frozen=True)
class LonglistOption:
    """One option as the sort sees it.

    Args:
        option_id: The option.
        name: Its name.
        state: ``included`` or ``excluded``.
    """

    option_id: uuid.UUID
    name: str
    state: str


@dataclass(frozen=True)
class LonglistSurface:
    """The longlist a turn arrived at, read once in the reservation transaction.

    Args:
        options: The task's options, in creation order.
    """

    options: tuple[LonglistOption, ...]

    def find(self, option_id: str | None) -> LonglistOption | None:
        """Return the option an id names, or ``None`` when it names none."""
        if option_id is None:
            return None
        return next((o for o in self.options if str(o.option_id) == option_id.strip()), None)

    def as_prompt(self) -> list[dict[str, str]]:
        """Return the options in the shape ``longlist_verbs_v1`` reads."""
        return [{"id": str(o.option_id), "name": o.name, "state": o.state} for o in self.options]


def read_longlist_surface(conn: Connection, *, task_id: uuid.UUID) -> LonglistSurface | None:
    """Return the longlist surface when a turn should be sorted against it.

    Call only when no parentless walk is active (the caller's fence). The
    surface exists for an options-scoping task with a ``longlist_result``;
    every other task — an Evidence search above all — gets ``None`` and keeps
    its ordinary planning turn.

    Args:
        conn: The caller's phase-one transaction.
        task_id: The task.

    Returns:
        The surface, or ``None``.
    """
    if capability_of_task(conn, task_id) != OPTIONS_SCOPING:
        return None
    built = conn.execute(
        select(longlist_result.c.longlist_result_id)
        .where(longlist_result.c.task_id == task_id)
        .limit(1)
    ).first()
    if built is None:
        return None
    rows = conn.execute(
        select(option.c.option_id, option.c.name, option.c.state)
        .where(option.c.task_id == task_id)
        .order_by(option.c.created_at, option.c.option_id)
    ).all()
    return LonglistSurface(
        options=tuple(LonglistOption(row.option_id, row.name, row.state) for row in rows)
    )


# --- The pending action --------------------------------------------------------


@dataclass(frozen=True)
class PendingAction:
    """An action proposed on one turn and awaiting the user's confirmation.

    Args:
        verb: ``add``, ``exclude`` or ``include_again``.
        option_id: The option, for ``exclude`` / ``include_again``; ``None``
            for ``add`` (the option is minted on confirmation).
        label: The option's name (for ``add``, the proposed design's).
        reason: The user's reason, verbatim, for ``exclude``.
        design: The design ``option_design_v1`` proposed, for ``add``.
        words: The user's own words for the option, for ``add`` (the History
            event records them).
    """

    verb: Verb
    option_id: uuid.UUID | None
    label: str
    reason: str | None = None
    design: OptionDesign | None = None
    words: str | None = None

    def as_state(self) -> dict[str, Any]:
        """Return the ``task_agent_state`` that carries this action."""
        return {
            "pending": {
                "verb": self.verb,
                "option_id": str(self.option_id) if self.option_id is not None else None,
                "label": self.label,
                "reason": self.reason,
                "design": self.design.model_dump(mode="json") if self.design else None,
                "words": self.words,
            }
        }

    def as_prompt(self) -> dict[str, str]:
        """Return the pending action in the shape ``longlist_verbs_v1`` reads."""
        return {"verb": self.verb, "label": self.label}


def is_longlist_state(state: object) -> bool:
    """Whether a stored ``task_agent_state`` is a longlist turn's, not a plan draft.

    Args:
        state: A transcript row's ``task_agent_state``.

    Returns:
        ``True`` for ``{"pending": ...}``.
    """
    return isinstance(state, dict) and set(state) == {"pending"}


def _pending_from_state(state: object) -> PendingAction | None:
    if not is_longlist_state(state):
        return None
    raw = cast("dict[str, Any]", state)["pending"]
    if not isinstance(raw, dict):
        return None
    try:
        verb = raw["verb"]
        if verb not in _VERB_PHRASE:
            return None
        option_id = uuid.UUID(raw["option_id"]) if raw.get("option_id") else None
        design = OptionDesign.model_validate(raw["design"]) if raw.get("design") else None
        if verb == "add" and design is None:
            return None
        if verb != "add" and option_id is None:
            return None
        return PendingAction(
            verb=cast(Verb, verb),
            option_id=option_id,
            label=str(raw["label"]),
            reason=raw.get("reason"),
            design=design,
            words=raw.get("words"),
        )
    except (KeyError, TypeError, ValueError, ValidationError):
        log.warning("longlist_turn_pending_unreadable")
        return None


def read_pending(
    conn: Connection, *, task_id: uuid.UUID, conversation_id: uuid.UUID
) -> PendingAction | None:
    """Return the conversation's pending action, or ``None``.

    The latest completed turn of the conversation carries it; a turn that
    left nothing pending carries none.

    Args:
        conn: Open read connection.
        task_id: The task.
        conversation_id: The Task Agent conversation.

    Returns:
        The pending action, or ``None``.
    """
    state = conn.execute(
        select(task_agent_transcript.c.task_agent_state)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.conversation_id == conversation_id)
        .where(task_agent_transcript.c.status == "completed")
        .order_by(task_agent_transcript.c.turn_index.desc())
        .limit(1)
    ).scalar_one_or_none()
    return _pending_from_state(state)


def button_confirms(message: str) -> bool:
    """Whether a message is the proposal's confirm button (its final-line marker)."""
    last_line = message.rstrip().split("\n")[-1].strip()
    match = _CONFIRM_MARKER.match(last_line)
    return (
        match is not None
        and match.group(1) == ACTION_PART_ID
        and match.group(2) == CONFIRM_OPTION_ID
    )


def _confirm_part(pending: PendingAction) -> PartProposalOut:
    """The proposal's confirm button, rendered by the thread's part card."""
    title = {
        "add": f"Add {pending.label}",
        "exclude": f"Exclude {pending.label}",
        "include_again": f"Include {pending.label} again",
    }[pending.verb]
    return PartProposalOut(
        id=ACTION_PART_ID,
        step_label="Longlist",
        title=title,
        options=[PartOptionOut(id=CONFIRM_OPTION_ID, label="Confirm", primary=True)],
    )


# --- The sort ------------------------------------------------------------------


def sort_turn(
    agent: AgentBackend,
    *,
    utterance: str,
    surface: LonglistSurface,
    pending: PendingAction | None,
    session_id: uuid.UUID | None = None,
) -> LonglistVerbWire:
    """Sort one longlist turn, failing safe to ``other``.

    A backend error and an unknown kind both resolve to ``other``: the product
    says what it can do and applies nothing. Assent is honoured only as the
    prompt defines it — kind ``other`` with ``assents_to_pending`` and a
    pending action to assent to — so a question is never read as assent.

    Args:
        agent: The agent backend seam.
        utterance: The user's verbatim turn text.
        surface: The longlist the turn arrived at.
        pending: The action awaiting confirmation, if any.
        session_id: Optional Langfuse session id (the task).

    Returns:
        A verdict whose ``kind`` is one of the five kinds.
    """
    try:
        sort = agent.sort_longlist_turn(
            utterance,
            surface.as_prompt(),
            pending=pending.as_prompt() if pending is not None else None,
            session_id=session_id,
        )
    except Exception:
        log.warning("longlist_sort_failed", exc_info=True)
        return LonglistVerbWire(kind="other", sort_reason="The longlist sort could not be read.")
    if sort.kind not in _KINDS:
        log.warning("longlist_sort_unusable", kind=sort.kind)
        return LonglistVerbWire(kind="other", sort_reason=sort.sort_reason)
    if sort.assents_to_pending and (sort.kind != "other" or pending is None):
        sort = sort.model_copy(update={"assents_to_pending": False})
    return sort


def _collapsed(text: str) -> str:
    return " ".join(text.split()).casefold()


def _verbatim(words: str | None, utterance: str) -> str:
    """The user's words for the option: the sort's quote only when it is theirs.

    Mirrors the gate's carried-text rule (044 S2): model output is not the
    user speaking, so a quote that is not verbatim in the utterance falls back
    to the whole utterance.
    """
    if words is not None and words.strip() and _collapsed(words) in _collapsed(utterance):
        return " ".join(words.split())
    return " ".join(utterance.split())


# --- Persistence -----------------------------------------------------------------


def _complete(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    result: TaskAgentTurnOut,
    pending: PendingAction | None,
) -> None:
    completed = conn.execute(
        update(task_agent_transcript)
        .where(task_agent_transcript.c.id == transcript_id)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.status.in_(("pending", "failed")))
        .values(
            reply=result.reply,
            task_agent_state=pending.as_state() if pending is not None else None,
            response=result.model_dump(mode="json"),
            part=result.part.model_dump(mode="json") if result.part is not None else None,
            suggestions=result.suggestions,
            status="completed",
            completed_at=datetime.now(UTC),
        )
    )
    if completed.rowcount != 1:
        raise RuntimeError("task_agent transcript turn was not open at its longlist commit")


def _fail(engine: Engine, *, task_id: uuid.UUID, transcript_id: uuid.UUID) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(task_agent_transcript)
            .where(task_agent_transcript.c.id == transcript_id)
            .where(task_agent_transcript.c.task_id == task_id)
            .where(task_agent_transcript.c.status.in_(("pending", "failed")))
            .values(status="failed", completed_at=datetime.now(UTC))
        )


# --- The dispatcher ----------------------------------------------------------------


@dataclass(frozen=True)
class _Turn:
    """What one longlist turn commits: its projection and the action it leaves pending."""

    result: TaskAgentTurnOut
    pending: PendingAction | None


def dispatch_longlist_turn(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    conversation_id: uuid.UUID,
    surface: LonglistSurface,
    utterance: str,
    user_id: str,
    agent: AgentBackend,
    chat_backend: ChatBackend,
    embedding_backend: EmbeddingBackend,
    runner_backends: RunnerBackends,
) -> TaskAgentTurnOut:
    """Sort one turn taken at the longlist and carry out what it turned out to be.

    Args:
        engine: Database engine.
        task_id: The options-scoping task.
        transcript_id: The reserved transcript row this turn completes.
        conversation_id: The owning Task Agent conversation.
        surface: The longlist the turn arrived at.
        utterance: The user's verbatim turn text (what the row stores).
        user_id: Authenticated actor: the History events' and the traces' user.
        agent: Backend carrying the sort and the design proposal.
        chat_backend: Chat writer seam for an answer.
        embedding_backend: Retrieval embedder seam for an answer.
        runner_backends: Runner bundle for the option search *add* opens.

    Returns:
        The completed turn (stored raw; the caller labels an answer's citations).

    Raises:
        Exception: Anything the dispatch raises, with the row failed first so
            the caller may retry it.
    """
    try:
        with engine.connect() as conn:
            pending = read_pending(conn, task_id=task_id, conversation_id=conversation_id)
        base: dict[str, Any] = {"capability": OPTIONS_SCOPING, "conversation_id": conversation_id}

        if button_confirms(utterance):
            if pending is None:
                turn = _Turn(
                    TaskAgentTurnOut(reply=NOTHING_PENDING_REPLY, kind="reply", **base), None
                )
                return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=turn)
            return _apply(
                engine,
                task_id=task_id,
                transcript_id=transcript_id,
                pending=pending,
                user_id=user_id,
                runner_backends=runner_backends,
                base=base,
            )

        sort = sort_turn(
            agent, utterance=utterance, surface=surface, pending=pending, session_id=task_id
        )
        if sort.kind == "other" and sort.assents_to_pending and pending is not None:
            return _apply(
                engine,
                task_id=task_id,
                transcript_id=transcript_id,
                pending=pending,
                user_id=user_id,
                runner_backends=runner_backends,
                base=base,
            )

        if sort.kind == "question":
            turn = _answer(
                engine,
                task_id=task_id,
                transcript_id=transcript_id,
                conversation_id=conversation_id,
                question=utterance,
                pending=pending,
                chat_backend=chat_backend,
                embedding_backend=embedding_backend,
                base=base,
            )
            return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=turn)

        if sort.kind in ("add", "exclude", "include_again"):
            turn = _propose(
                engine,
                task_id=task_id,
                sort=sort,
                utterance=utterance,
                surface=surface,
                pending=pending,
                agent=agent,
                base=base,
            )
            return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=turn)

        # Other: say what the longlist chat can do. A pending action stays
        # waiting: only an applied action, a replacing verb, or the button or
        # assent clears it.
        reply = OTHER_REPLY if pending is None else f"{OTHER_REPLY}\n\n{still_waiting(pending)}"
        turn = _Turn(TaskAgentTurnOut(reply=reply, kind="reply", **base), pending)
        return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=turn)
    except Exception:
        _fail(engine, task_id=task_id, transcript_id=transcript_id)
        raise


def _commit(
    engine: Engine, *, task_id: uuid.UUID, transcript_id: uuid.UUID, turn: _Turn
) -> TaskAgentTurnOut:
    with engine.begin() as conn:
        _complete(
            conn,
            task_id=task_id,
            transcript_id=transcript_id,
            result=turn.result,
            pending=turn.pending,
        )
    return turn.result


def _answer_window(
    conn: Connection, task_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[tuple[str, str]]:
    rows = conn.execute(
        select(task_agent_transcript.c.user_message, task_agent_transcript.c.reply)
        .where(task_agent_transcript.c.task_id == task_id)
        .where(task_agent_transcript.c.conversation_id == conversation_id)
        .where(task_agent_transcript.c.status == "completed")
        .order_by(task_agent_transcript.c.turn_index.asc())
    ).all()
    return [(row[0], row[1]) for row in rows if row[1] is not None]


def _answer(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    conversation_id: uuid.UUID,
    question: str,
    pending: PendingAction | None,
    chat_backend: ChatBackend,
    embedding_backend: EmbeddingBackend,
    base: dict[str, Any],
) -> _Turn:
    """Answer a question over the longlist's scope set; any pending action stays."""
    scope = resolve_terminal_run_components(engine, task_id=task_id)
    if scope is None:
        return _Turn(TaskAgentTurnOut(reply=NO_SCOPE_REPLY, kind="reply", **base), pending)
    with engine.connect() as conn:
        window = _answer_window(conn, task_id, conversation_id)
    try:
        prose, payload = answer_over_scope(
            engine,
            task_id=task_id,
            scope=scope,
            entry_artefact_id=None,
            window=window,
            question=question,
            backends=AnswerBackends(
                chat=chat_backend,
                embedding=embedding_backend,
                langfuse=tracing.get_langfuse(),
                # Resolved from this module at call time, as the gate resolves
                # its own tool set.
                tools_builder=build_section_tools,
            ),
            trace_run_id=transcript_id,
            # A Task Agent turn keeps the task's session (ADR 0038).
            trace_session_id=task_id,
            conversation_id=conversation_id,
        )
    except RetrievalUnitCapError as exc:
        log.warning(
            "longlist_turn_retrieval_cap",
            task_id=str(task_id),
            unit_count=exc.unit_count,
            cap=exc.cap,
        )
        return _Turn(
            TaskAgentTurnOut(reply=TOO_MANY_DOCUMENTS_REPLY, kind="reply", **base), pending
        )
    return _Turn(
        TaskAgentTurnOut(
            reply=prose,
            kind="answer",
            answer=AnswerPayloadOut.model_validate(payload.as_payload()),
            **base,
        ),
        pending,
    )


def _propose(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    sort: LonglistVerbWire,
    utterance: str,
    surface: LonglistSurface,
    pending: PendingAction | None,
    agent: AgentBackend,
    base: dict[str, Any],
) -> _Turn:
    """Propose a verb back in words and store it as the pending action.

    A turn that cannot become a proposal (no option matched, an option already
    in the asked-for state, no design readable) asks back and leaves any
    earlier pending action where it was.
    """
    verb = cast(Verb, sort.kind)
    proposal: PendingAction
    if verb == "add":
        words = _verbatim(sort.design_words, utterance)
        if not words:
            return _Turn(TaskAgentTurnOut(reply=WHAT_TO_ADD_REPLY, kind="reply", **base), pending)
        try:
            with engine.connect() as conn:
                plan_row = current_plan_row(conn, task_id=task_id)
            design = propose_design(
                agent, plan_payload=plan_row["payload"], words=words, session_id=task_id
            )
        except LonglistActionRefused as exc:
            return _Turn(
                TaskAgentTurnOut(reply=_sentence(exc.message), kind="reply", **base), pending
            )
        except (RuntimeError, ValueError) as exc:
            log.warning("longlist_turn_design_failed", error_type=type(exc).__name__)
            return _Turn(
                TaskAgentTurnOut(reply=DESIGN_UNAVAILABLE_REPLY, kind="reply", **base), pending
            )
        proposal = PendingAction(
            verb="add", option_id=None, label=design.name, design=design, words=words
        )
        words_reply = add_proposal(design)
    else:
        target = surface.find(sort.option_id)
        if target is None:
            return _Turn(TaskAgentTurnOut(reply=WHICH_OPTION_REPLY, kind="reply", **base), pending)
        wanted = "excluded" if verb == "exclude" else "included"
        if target.state == wanted:
            return _Turn(
                TaskAgentTurnOut(reply=_already_reply(target.name, wanted), kind="reply", **base),
                pending,
            )
        if verb == "exclude":
            reason = _reason(sort.reason, utterance)
            proposal = PendingAction(
                verb="exclude", option_id=target.option_id, label=target.name, reason=reason
            )
            words_reply = exclude_proposal(target.name, reason)
        else:
            proposal = PendingAction(
                verb="include_again", option_id=target.option_id, label=target.name
            )
            words_reply = include_proposal(target.name)
    if pending is not None:
        words_reply = f"{_replaced_prefix(pending)} {words_reply}"
    return _Turn(
        TaskAgentTurnOut(reply=words_reply, kind="reply", part=_confirm_part(proposal), **base),
        proposal,
    )


def _reason(reason: str | None, utterance: str) -> str | None:
    """The user's exclusion reason, only when it is verbatim theirs (else none)."""
    if reason is None or not reason.strip():
        return None
    if _collapsed(reason) in _collapsed(utterance):
        return " ".join(reason.split())
    log.warning("longlist_sort_reason_not_verbatim", reason_chars=len(reason))
    return None


def _sentence(message: str) -> str:
    text = message.strip()
    text = text[:1].upper() + text[1:]
    return text if text.endswith((".", "!", "?")) else f"{text}."


def _apply(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    pending: PendingAction,
    user_id: str,
    runner_backends: RunnerBackends,
    base: dict[str, Any],
) -> TaskAgentTurnOut:
    """Apply the confirmed pending action through the shared apply functions.

    *Exclude* and *include again* write the option, its History event and this
    turn's completion in **one** transaction, so a retried turn can never
    apply twice. *Add* opens a walk, which cannot share a transaction: its
    turn completes the moment the walk is open.
    """
    if pending.verb == "add":
        return _apply_add(
            engine,
            task_id=task_id,
            transcript_id=transcript_id,
            pending=pending,
            user_id=user_id,
            runner_backends=runner_backends,
            base=base,
        )
    option_id = cast(uuid.UUID, pending.option_id)
    wanted = "excluded" if pending.verb == "exclude" else "included"
    try:
        with engine.begin() as conn:
            task_lock(conn, task_id)
            row = conn.execute(
                select(option.c.name, option.c.state)
                .where(option.c.task_id == task_id)
                .where(option.c.option_id == option_id)
            ).one_or_none()
            if row is None:
                turn = _Turn(TaskAgentTurnOut(reply=OPTION_GONE_REPLY, kind="reply", **base), None)
            elif row.state == wanted:
                # The button route got there first: nothing to write twice.
                turn = _Turn(
                    TaskAgentTurnOut(reply=_already_reply(row.name, wanted), kind="reply", **base),
                    None,
                )
            else:
                if pending.verb == "exclude":
                    exclude_option(
                        conn,
                        task_id=task_id,
                        option_id=option_id,
                        reason=pending.reason,
                        actor=user_id,
                        require_reason=False,
                    )
                else:
                    include_option(conn, task_id=task_id, option_id=option_id, actor=user_id)
                turn = _Turn(
                    TaskAgentTurnOut(
                        reply=_applied_reply(pending.verb, row.name),
                        kind="action",
                        action=TurnActionOut(
                            verb=pending.verb, option_id=option_id, label=row.name
                        ),
                        **base,
                    ),
                    None,
                )
            _complete(
                conn,
                task_id=task_id,
                transcript_id=transcript_id,
                result=turn.result,
                pending=turn.pending,
            )
        return turn.result
    except (LonglistActionRefused, OptionNotFound) as exc:
        message = exc.message if isinstance(exc, LonglistActionRefused) else OPTION_GONE_REPLY
        # Refused (a walk started meanwhile): the action stays waiting.
        refused = _Turn(TaskAgentTurnOut(reply=_sentence(message), kind="reply", **base), pending)
        return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=refused)


def _apply_add(
    engine: Engine,
    *,
    task_id: uuid.UUID,
    transcript_id: uuid.UUID,
    pending: PendingAction,
    user_id: str,
    runner_backends: RunnerBackends,
    base: dict[str, Any],
) -> TaskAgentTurnOut:
    design = cast(OptionDesign, pending.design)
    try:
        added = add_option(
            engine,
            task_id=task_id,
            words=pending.words or design.name,
            design=design,
            backends=runner_backends,
            user_id=user_id,
        )
    except LonglistActionRefused as exc:
        refused = _Turn(
            TaskAgentTurnOut(reply=_sentence(exc.message), kind="reply", **base), pending
        )
        return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=refused)
    turn = _Turn(
        TaskAgentTurnOut(
            reply=_applied_reply("add", design.name),
            kind="action",
            action=TurnActionOut(
                verb="add",
                option_id=added.option_id,
                label=design.name,
                capability_run_id=added.capability_run_id,
            ),
            **base,
        ),
        None,
    )
    return _commit(engine, task_id=task_id, transcript_id=transcript_id, turn=turn)
