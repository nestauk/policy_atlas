"""The Task Agent for a theory-of-change task (task 054, step 1.3).

The profile the capability registry loads by name (``_toc_task_agent``):
``task_agent_toc_v1`` fills a :class:`~policy_atlas.runtime.toc_plan.TocPlan`
from the conversation. A code-authored ``theory_state`` line tells the prompt
where the theory is (no draft, drafting, checking, checked).

Once a draft exists the plan is fixed (S7): a turn answers questions, and
whatever plan draft the model returns, the approved plan stays as it is —
:func:`_build_plan` refuses, so nothing is persisted, and the turn shows the
approved plan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.api.contract import TocPlanDraft
from policy_atlas.core.model_routes import route
from policy_atlas.core.schema import capability_run, evidence_scope
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    TaskAgentProfile,
    expect_toc_plan,
    latest_approved_plan_row,
    validate_plan,
)
from policy_atlas.runtime.task_agent_toc_prompt import (
    TASK_AGENT_TOC_PROMPT_VERSION,
    TOC_TASK_AGENT_MAX_OUTPUT_TOKENS,
    TocPlanDraftWire,
    TocTurnWire,
    build_toc_messages,
)
from policy_atlas.runtime.toc_plan import (
    TOC_PURPOSE,
    TOC_WALK_CHECK,
    TOC_WALK_DRAFT,
    TOC_WALK_KEY,
    TocPlan,
)
from policy_atlas.theory_of_change.store import has_graph

TASK_AGENT_TOC_MODEL = route().model_for("task_agent_toc")

#: The code-authored theory-state lines the prompt reads as data.
NO_DRAFT = "no draft yet"
DRAFTING = "a draft is being written"
CHECKING = "the draft is on the canvas and its evidence check is running"
CHECKED = "the draft is on the canvas and its evidence has been checked"
NOT_CHECKED = "the draft is on the canvas and its evidence check did not finish"

_PLAN_FIELDS = (
    "title",
    "question",
    "entry_point",
    "intended_change",
    "target_population",
    "intervention",
    "dosage",
    "existing_theory_text",
    "where",
    "time_horizon",
    "context",
)


@dataclass(frozen=True)
class TocInputs:
    """What a theory-of-change turn reads besides the transcript.

    Args:
        theory_state: The code-authored theory-state line.
        has_draft: Whether the graph exists (the plan is then fixed).
        approved: The latest approved plan, if any.
    """

    theory_state: str
    has_draft: bool
    approved: TocPlan | None


def read_theory_state(conn: Connection, task_id: uuid.UUID) -> tuple[str, bool]:
    """Return the theory-state line and whether a graph exists.

    Args:
        conn: Open connection.
        task_id: The task.

    Returns:
        ``(line, has_draft)``.
    """
    walks = conn.execute(
        select(capability_run.c.status, evidence_scope.c.context)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.parent_capability_run_id.is_(None))
        .where(evidence_scope.c.purpose == TOC_PURPOSE)
        .order_by(capability_run.c.started_at.desc())
    ).all()
    drafted = has_graph(conn, task_id)
    latest = {
        kind: next((w.status for w in walks if (w.context or {}).get(TOC_WALK_KEY) == kind), None)
        for kind in (TOC_WALK_DRAFT, TOC_WALK_CHECK)
    }
    if not drafted:
        return (DRAFTING if latest[TOC_WALK_DRAFT] == "running" else NO_DRAFT), False
    check = latest[TOC_WALK_CHECK]
    if check in (None, "running"):
        return CHECKING, True
    return (CHECKED if check in ("succeeded", "degraded") else NOT_CHECKED), True


def load_toc_inputs(conn: Connection, task_id: uuid.UUID) -> TocInputs:
    """Read the theory state and the approved plan for one turn."""
    state, drafted = read_theory_state(conn, task_id)
    row = latest_approved_plan_row(conn, task_id)
    approved = (
        expect_toc_plan(validate_plan(THEORY_OF_CHANGE, row["payload"]))
        if row is not None
        else None
    )
    return TocInputs(theory_state=state, has_draft=drafted, approved=approved)


def toc_draft_from_plan(plan: Any) -> TocPlanDraft:
    """Project an approved plan into the API draft."""
    values = expect_toc_plan(plan).model_dump(mode="json")
    return TocPlanDraft.model_validate(
        {**{key: values.get(key) for key in _PLAN_FIELDS}, "ready": True}
    )


def toc_draft_from_wire(draft: TocPlanDraftWire, ready: bool, inputs: TocInputs) -> TocPlanDraft:
    """Project the model's draft into the API draft; the approved plan once a draft exists."""
    if inputs.has_draft and inputs.approved is not None:
        return toc_draft_from_plan(inputs.approved)
    return TocPlanDraft.model_validate({**draft.model_dump(), "ready": ready})


def build_toc_plan(draft: TocPlanDraftWire, inputs: TocInputs, turn_index: int) -> TocPlan:
    """Validate the model's draft into the executable plan, failing closed.

    Raises:
        ValueError: If a draft already exists (the plan is fixed, S7) or the
            plan is not ready for its entry point.
        ValidationError: If the draft does not validate.
    """
    if inputs.has_draft:
        raise ValueError("the plan is fixed once the draft exists")
    values = {key: getattr(draft, key) for key in _PLAN_FIELDS}
    plan = expect_toc_plan(
        validate_plan(
            THEORY_OF_CHANGE,
            {k: v for k, v in values.items() if v is not None} | {"source_turn_index": turn_index},
        )
    )
    if not plan.ready:
        raise ValueError("the plan is missing its entry point's own slot")
    return plan


def seed_toc_draft(plan: Any) -> dict[str, object]:
    """The wire draft a successor conversation starts from."""
    values = expect_toc_plan(plan).model_dump(mode="json")
    return {**{key: values.get(key) for key in _PLAN_FIELDS}, "assumptions": []}


def stub_toc_turn(turns: list[dict[str, str]]) -> TocTurnWire:
    """A deterministic zero-egress turn: the first message becomes the change, ready."""
    first = next((t["text"] for t in turns if t["role"] == "user" and t["text"].strip()), "")
    text = " ".join(first.split()) or "A theory of change"
    return TocTurnWire(
        reply="Deterministic stub Task Agent: the plan is ready to draft.",
        plan_draft=TocPlanDraftWire(
            title=text[:60],
            question=text[:500],
            entry_point="outcome_first",
            intended_change=text[:300],
            target_population="the people the question is about",
            intervention=None,
            dosage=None,
            existing_theory_text=None,
            where="England",
            time_horizon="within 5 years",
            context=None,
            assumptions=["The place is assumed to be England."],
        ),
        question=None,
        suggested_answers=None,
        ready=True,
    )


def _build_messages(
    turns: list[dict[str, str]], previous: dict[str, object] | None, inputs: TocInputs
) -> list[Any]:
    return build_toc_messages(turns, previous, theory_state=inputs.theory_state)


TOC_TASK_AGENT = TaskAgentProfile(
    capability=THEORY_OF_CHANGE,
    wire=TocTurnWire,
    build_messages=_build_messages,
    model=TASK_AGENT_TOC_MODEL,
    max_output_tokens=TOC_TASK_AGENT_MAX_OUTPUT_TOKENS,
    prompt_version=TASK_AGENT_TOC_PROMPT_VERSION,
    trace_name="task_agent_toc:turn",
    usage_event="task_agent.toc.turn.usage",
    label="task-agent-toc",
    load_inputs=load_toc_inputs,
    build_plan=build_toc_plan,
    draft_from_plan=toc_draft_from_plan,
    draft_from_wire=toc_draft_from_wire,
    seed_draft=seed_toc_draft,
    stub_turn=stub_toc_turn,
    part_ids=frozenset(),
)
