"""The options-scoping Task Agent profile (the ``task_agent_scoping_v5`` call).

The Evidence search profile (``task_agent.py``) one capability over. The live
backend and the stub are shared (``task_agent.OpenAITaskAgentBackend``,
``task_agent.StubTaskAgentBackend``); this module supplies what differs: the
scoping turn's two extra inputs — the fenced linked-task context and the
baseline state — read from the database, the plan builder, the draft
projections, the option designs proposed once a plan is approved, and the
deterministic stub turn.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine, RowMapping

from policy_atlas.api.contract import PlanStep, ScopingPlanDraft
from policy_atlas.api.routers._common import ACTIVE_WALK_STATUSES, parentless_walk
from policy_atlas.core.model_routes import route
from policy_atlas.core.schema import (
    artefact,
    capability_run,
    evidence_scope,
    longlist_result,
    task_link,
    task_plan,
)
from policy_atlas.runtime.capability_registry import (
    OPTIONS_SCOPING,
    TaskAgentProfile,
    expect_scoping_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.runtime.inherit import linked_context
from policy_atlas.runtime.scoping_plan import (
    DEFAULT_WHERE_TEXT,
    LONGLIST_PURPOSE,
    SCOPING_STEPS,
    ScopingPlan,
    baseline_inputs_changed,
    baseline_inputs_sentence,
    build_scoping_plan,
    default_preference_for,
    ensure_option_designs,
    merge_your_options,
    wire_draft_from_plan,
)
from policy_atlas.runtime.task_agent import StubTaskAgentBackend
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

if TYPE_CHECKING:
    from policy_atlas.runtime.agent_backend import AgentBackend

log = structlog.get_logger()

#: The scoping Task Agent's model — the strongest tier ("frontier"), apart from the
#: Evidence search Task Agent's. Model from the route file (task 053).
TASK_AGENT_SCOPING_MODEL = route().model_for("task_agent_scoping")

#: The code-authored line the prompt reads as data when nothing has run yet.
NO_BASELINE_STATE = "no baseline built yet"

#: The shared stub, under the name the scoping tests know it by.
StubScopingTaskAgentBackend = StubTaskAgentBackend


@dataclass(frozen=True)
class ScopingInputs:
    """What a scoping turn reads besides the transcript.

    Args:
        linked_context: One entry per ``task_link``, in link order.
        linked_task_ids: The linked source task ids, in link order.
        baseline_state: The code-authored baseline-state line.
        previous: The latest approved scoping plan, or ``None`` before the
            first; a new version is built against it (task 045, D19, D22).
    """

    linked_context: list[LinkedTaskContext]
    linked_task_ids: list[uuid.UUID]
    baseline_state: str = NO_BASELINE_STATE
    previous: ScopingPlan | None = None


# --- Reading the inputs -------------------------------------------------------


def read_linked_task_ids(conn: Connection, task_id: uuid.UUID) -> list[uuid.UUID]:
    """Return the source tasks this scoping task starts from, in link order."""
    rows = conn.execute(
        select(task_link.c.source_task_id)
        .where(task_link.c.target_task_id == task_id)
        .order_by(task_link.c.created_at.asc())
    ).scalars().all()
    return [uuid.UUID(str(value)) for value in rows]


def approved_scoping_plan(
    conn: Connection, task_id: uuid.UUID
) -> tuple[ScopingPlan, RowMapping] | None:
    """Return the latest approved scoping plan and its row, or ``None`` before the first."""
    row = latest_approved_plan_row(conn, task_id)
    if row is None:
        return None
    return expect_scoping_plan(validate_plan(OPTIONS_SCOPING, row["payload"])), row


def latest_approved_scoping_plan(conn: Connection, task_id: uuid.UUID) -> ScopingPlan | None:
    """Return the latest approved scoping plan, or ``None`` before the first.

    The previous version a new one is built against: it carries the default
    preference's state and the options' designs forward (task 045, D19, D22).
    """
    try:
        found = approved_scoping_plan(conn, task_id)
    except ValidationError:
        return None
    return found[0] if found is not None else None


def read_baseline_state(conn: Connection, task_id: uuid.UUID) -> str:
    """Return the code-authored baseline-state line for the scoping prompt.

    The prompt reads this as data and changes what it says about an edit (an
    edit before any baseline exists is a plan change; after one, it may have
    changed what the baseline was built from). It is a *sentence*, never a
    flag, because the prompt fences it as data alongside the transcript.

    A walk paused on the gate says so, so the Task Agent never proposes
    starting a run that is already under way (task 044, S5). The longlist
    states come first (task 045): a longlist walk under way ("a longlist is
    being built"), then — after the gate — a built longlist ("a longlist
    exists, built from plan version N", N from the latest
    ``longlist_result``), then the baseline states unchanged.
    """
    building = conn.execute(
        select(capability_run.c.capability_run_id)
        .select_from(
            capability_run.join(
                evidence_scope,
                evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id,
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.capability == OPTIONS_SCOPING)
        .where(capability_run.c.status.in_(ACTIVE_WALK_STATUSES))
        .where(parentless_walk())
        .where(evidence_scope.c.purpose == LONGLIST_PURPOSE)
        .limit(1)
    ).first()
    if building is not None:
        return "a longlist is being built"
    paused_version = conn.execute(
        select(capability_run.c.plan_version)
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.capability == OPTIONS_SCOPING)
        .where(capability_run.c.status == "paused")
        .order_by(capability_run.c.started_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if paused_version is not None:
        return (
            "paused on the baseline, which was built from plan version "
            f"{int(paused_version)}"
        )
    longlist_version = conn.execute(
        select(longlist_result.c.plan_version)
        .where(longlist_result.c.task_id == task_id)
        .order_by(longlist_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if longlist_version is not None:
        return f"a longlist exists, built from plan version {int(longlist_version)}"
    version = baseline_built_from(conn, task_id)
    if version is None:
        return NO_BASELINE_STATE
    return f"a baseline exists, built from plan version {int(version)}"


def baseline_built_from(conn: Connection, task_id: uuid.UUID) -> int | None:
    """Return the plan version the latest existing baseline was built from.

    A baseline exists when a walk **wrote one**, which is what the artefact
    row says (C5): ``succeeded`` (the gate confirmed), ``degraded``, or
    ``aborted`` by "Change the plan" after synthesise — the artefact stays on
    screen marked *built from plan version N* (C1), so a later edit is still
    measured against it.

    The status alone is not enough. A walk aborted at an earlier floor pause —
    say after acquire — is also ``aborted`` and wrote nothing, and reading it
    as a baseline told the Task Agent one existed and fired the S4 "this
    changed what the baseline was built from" sentence about a document the
    user has never seen. So the artefact is the evidence, and the status only
    excludes the walk that is still going.
    """
    version = conn.execute(
        select(capability_run.c.plan_version)
        .select_from(
            capability_run.join(
                artefact,
                artefact.c.capability_run_id == capability_run.c.capability_run_id,
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.capability == OPTIONS_SCOPING)
        .where(capability_run.c.status.notin_(("running", "paused")))
        .order_by(capability_run.c.started_at.desc())
        .limit(1)
    ).scalars().first()
    return int(version) if version is not None else None


def inputs_changed_sentence(
    conn: Connection, task_id: uuid.UUID, approved: ScopingPlan
) -> str | None:
    """The deterministic "did the change touch the baseline's inputs" sentence (S4).

    Returns ``None`` when no baseline exists yet or the baseline's own plan
    version cannot be read.
    """
    built_from = baseline_built_from(conn, task_id)
    if built_from is None:
        return None
    row = conn.execute(
        select(task_plan.c.payload)
        .where(task_plan.c.task_id == task_id)
        .where(task_plan.c.version == built_from)
    ).mappings().one_or_none()
    if row is None:
        return None
    try:
        previous = expect_scoping_plan(validate_plan(OPTIONS_SCOPING, row["payload"]))
    except ValidationError:
        return None
    return baseline_inputs_sentence(baseline_inputs_changed(previous, approved), built_from)


def load_scoping_inputs(conn: Connection, task_id: uuid.UUID) -> ScopingInputs:
    """Read everything a scoping turn needs besides the transcript.

    Args:
        conn: Open database connection.
        task_id: The scoping task.

    Returns:
        The linked context and ids, the baseline-state line and the previous
        approved plan.
    """
    return ScopingInputs(
        linked_context=linked_context(conn, task_id),
        linked_task_ids=read_linked_task_ids(conn, task_id),
        baseline_state=read_baseline_state(conn, task_id),
        previous=latest_approved_scoping_plan(conn, task_id),
    )


# --- Projections --------------------------------------------------------------


def scoping_draft_from_wire(
    draft: Any, *, ready: bool, previous: ScopingPlan | None = None
) -> ScopingPlanDraft:
    """Project the scoping Task Agent's loose draft into the API shape.

    Fields the model has not filled stay absent; the three steps and the time
    band are code-owned, so they are supplied here exactly as
    ``build_scoping_plan`` supplies them to the plan — and so is the default
    transferability preference (D22), so the draft shows the row the plan
    will carry, and the options' designs already proposed on ``previous``.
    A draft field the closed API vocabulary rejects (an origin tag the model
    invented, say) drops out of the projection rather than 500ing the turn —
    the draft is not ready yet, which is the honest reading.

    Args:
        draft: The scoping wire draft.
        ready: Whether the draft validated into a plan.
        previous: The latest approved scoping plan, if any.

    Returns:
        The API scoping draft.
    """
    values = draft.model_dump(exclude_none=True)
    values["steps"] = [step.model_dump() for step in SCOPING_STEPS]
    values["ready"] = ready
    where = values.get("where")
    where_text = DEFAULT_WHERE_TEXT
    if isinstance(where, dict) and isinstance(where.get("text"), str) and where["text"]:
        where_text = where["text"]
    default = default_preference_for(where_text, previous)
    if default is not None:
        constraints = [
            c
            for c in values.get("constraints", [])
            if not (
                c.get("kind") == "preference"
                and str(c.get("text", "")).casefold().startswith("transferable to")
            )
        ]
        constraints.append(default.model_dump(mode="json"))
        values["constraints"] = constraints
    if "your_options" in values:
        previous_options = previous.your_options if previous is not None else []
        texts = [o["text"] for o in values["your_options"] if str(o.get("text", "")).strip()]
        merged = merge_your_options(texts, previous_options, turn_index=0)
        carried = {id(o) for o in previous_options}
        values["your_options"] = [
            {
                **option.model_dump(mode="json"),
                "turn_index": option.turn_index if id(option) in carried else None,
            }
            for option in merged
        ]
    try:
        return ScopingPlanDraft.model_validate(values)
    except ValidationError:
        log.warning("task_agent_scoping_draft_degraded", reason="invalid_wire_field")
        return ScopingPlanDraft(
            question=values.get("question"),
            steps=[PlanStep.model_validate(step.model_dump()) for step in SCOPING_STEPS],
            ready=False,
        )


def scoping_draft_from_plan(plan: ScopingPlan) -> ScopingPlanDraft:
    """Project a validated scoping plan into the API's approved draft shape.

    Args:
        plan: An approved scoping plan.

    Returns:
        The API scoping draft.
    """
    values = plan.model_dump(mode="json")
    values.pop("source_turn_index", None)
    values["ready"] = True
    return ScopingPlanDraft.model_validate(values)


# --- After approval -----------------------------------------------------------


def _after_approve(
    engine: Engine, task_id: uuid.UUID, plan: ScopingPlan, agent: AgentBackend
) -> tuple[ScopingPlan, str | None]:
    """Propose designs for new options, then say whether the baseline's inputs moved.

    A design is proposed back for each new or reworded option (D19) so one
    exists on the version the user confirms; then, after a baseline exists,
    the deterministic sentence says whether the change touched what it was
    built from (S4, C1).
    """
    plan = ensure_option_designs(plan, agent, session_id=task_id)
    with engine.connect() as conn:
        return plan, inputs_changed_sentence(conn, task_id, plan)


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


def _stub_turn(turns: list[dict[str, str]]) -> ScopingTurnWire:
    """Return a deterministic scoping turn derived from ``turns`` alone."""
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


# --- The profile --------------------------------------------------------------


def _build_messages(
    turns: list[dict[str, str]], previous: dict[str, object] | None, inputs: ScopingInputs
) -> list[Any]:
    return build_scoping_messages(
        turns,
        previous,
        linked_context=inputs.linked_context,
        baseline_state=inputs.baseline_state,
    )


def _build_plan(draft: ScopingPlanDraftWire, inputs: ScopingInputs, turn_index: int) -> ScopingPlan:
    return build_scoping_plan(
        draft,
        linked_task_ids=inputs.linked_task_ids,
        source_turn_index=turn_index,
        previous=inputs.previous,
    )


OPTIONS_SCOPING_TASK_AGENT = TaskAgentProfile(
    capability=OPTIONS_SCOPING,
    wire=ScopingTurnWire,
    build_messages=_build_messages,
    model=TASK_AGENT_SCOPING_MODEL,
    max_output_tokens=SCOPING_MAX_OUTPUT_TOKENS,
    prompt_version=TASK_AGENT_SCOPING_PROMPT_VERSION,
    trace_name="task_agent_scoping:turn",
    usage_event="task_agent.scoping.turn.usage",
    label="task-agent-scoping",
    load_inputs=load_scoping_inputs,
    build_plan=_build_plan,
    draft_from_plan=scoping_draft_from_plan,
    draft_from_wire=lambda draft, ready, inputs: scoping_draft_from_wire(
        draft, ready=ready, previous=inputs.previous
    ),
    seed_draft=lambda plan: wire_draft_from_plan(expect_scoping_plan(plan)),
    stub_turn=_stub_turn,
    # Closed per capability: a scoping card keyed 'thoroughness' would render
    # an Evidence search control on a plan that has no such dial.
    part_ids=frozenset({"question", "settings", "constraints", "depth"}),
    # OS ruling 25: neither depth is a recommendation.
    no_primary_parts=frozenset({"depth"}),
    after_approve=_after_approve,
)
