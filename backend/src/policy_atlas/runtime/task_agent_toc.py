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

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.api.contract import TocPlanDraft
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
    DEFAULT_PUBLISHED_AFTER,
    TOC_PURPOSE,
    TOC_WALK_CHECK,
    TOC_WALK_DRAFT,
    TOC_WALK_KEY,
    TocPlan,
    toc_scope_constraints,
)
from policy_atlas.theory_of_change.store import has_graph

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
        theory_outline: The theory by code, once a draft exists (C46).
    """

    theory_state: str
    has_draft: bool
    approved: TocPlan | None
    #: Once a draft exists: its boxes, links, verdicts and pathways by code (C46).
    theory_outline: str = ""
    #: Before a draft: the user's uploaded diagram, as read (increment 5).
    imported: dict[str, Any] | None = None
    #: Before a draft: the theory the user drew on the canvas, as text.
    sketch: str | None = None


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
    from policy_atlas.theory_of_change.draft import sketch_text, user_sketch
    from policy_atlas.theory_of_change.importing import latest_import

    imported = None if drafted else latest_import(conn, task_id)
    boxes, links = user_sketch(conn, task_id)
    sketch = sketch_text(boxes, links) if boxes else None
    # The user's own theory (uploaded, or drawn on the canvas) stands in for
    # the outline until the draft exists.
    if imported is not None:
        state = f"{state}; the user uploaded their own theory of change diagram"
    if sketch is not None:
        state = f"{state}; the user drew their own theory of change on the canvas"
    outline = (
        theory_outline(conn, task_id)
        if drafted
        else "\n\n".join(part for part in (sketch, imported and imported["text"]) if part)
    )
    return TocInputs(
        theory_state=state,
        has_draft=drafted,
        approved=approved,
        theory_outline=outline,
        imported=imported,
        sketch=sketch,
    )


def theory_outline(conn: Connection, task_id: uuid.UUID) -> str:
    """The theory as the Task Agent reads it: one line per box, link and pathway (C46)."""
    from policy_atlas.theory_of_change.review import _theory

    theory = _theory(conn, task_id)
    lines = [f"Box {b['code']} ({b['layer']}): {b['text']}" for b in theory["boxes"]]
    lines += [
        f"Link {link['code']} {link['from']} → {link['to']}: {link['sentence']} [{link['verdict']}]"
        for link in theory["links"]
    ]
    lines += [
        f"Pathway {p['key']} ({p['kind']}): {p['label']}: {' → '.join(str(c) for c in p['links'])}"
        for p in theory["pathways"]
    ]
    return "\n".join(lines)


def toc_after_turn(engine: Engine, task_id: uuid.UUID, turn: Any, user_id: str) -> str | None:
    """Store what a turn proposed and any clarification; say where to find them (C46, C49)."""
    from policy_atlas.core import events
    from policy_atlas.theory_of_change import proposals
    from policy_atlas.theory_of_change.draft import TOC_CLARIFICATION_EVENT

    edits = list(getattr(turn, "proposed_edits", None) or [])
    clarification = (getattr(turn, "clarification", None) or "").strip()
    notes: list[str] = []
    with engine.begin() as conn:
        if not has_graph(conn, task_id):
            return None
        if edits:
            proposals.create_proposal(
                conn,
                task_id=task_id,
                source="chat",
                summary=f"Suggested in the chat: {len(edits)} change"
                + ("s" if len(edits) != 1 else ""),
                ops=edits[:6],
            )
            notes.append("The changes are under Suggestions, beside the canvas.")
        if clarification:
            events.append(
                conn,
                task_id=task_id,
                run_id=None,
                event_type=TOC_CLARIFICATION_EVENT,
                payload={"text": clarification, "by": user_id},
            )
            notes.append("I noted the clarification; the next check reads it.")
    return " ".join(notes) or None


def toc_after_approve(
    engine: Engine, task_id: uuid.UUID, plan: TocPlan, agent: Any
) -> tuple[TocPlan, str | None]:
    """Sense-check a ready plan: can this intervention cause this goal at all? (red team).

    Runs only with live models (the stub agent means a test or a keyless run):
    a quick search on the whole intervention and one frontier call. A doubtful
    or implausible plan gets a warning in the reply; the plan is never changed.
    """
    import os

    from policy_atlas.core import tracing
    from policy_atlas.evidence_search.sourcing.search_live import OpenAlexLiveBackend
    from policy_atlas.evidence_search.sourcing.search_loop import _semantic_filter_parts
    from policy_atlas.runtime.agent_backend import StubAgentBackend
    from policy_atlas.theory_of_change.backend import OpenAITocBackend
    from policy_atlas.theory_of_change.sense_check import run_sense_check

    key = os.environ.get("OPENALEX_API_KEY")
    if isinstance(agent, StubAgentBackend) or not key:
        return plan, None
    openalex = OpenAlexLiveBackend(key, email=os.environ.get("OPENALEX_EMAIL"))
    shared = toc_scope_constraints(plan).to_filters().get("shared", {})
    years, _local = _semantic_filter_parts(shared)
    warning = run_sense_check(
        engine,
        task_id=task_id,
        plan=plan,
        backend=OpenAITocBackend(langfuse_client=tracing.get_langfuse(), session_id=task_id),
        # The plan's publication years, as a year fence the semantic search takes.
        search=lambda text: openalex.search_semantic(text, wire_params=years, max_results=6),
    )
    return plan, warning


_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_START = re.compile(r"\b(start|begin)\b", re.IGNORECASE)


def toc_merge_note(reply: str, note: str) -> str:
    """The reply, without its invitations to start, then the sense check's warning."""
    kept = [s for s in _SENTENCE.split(reply.strip()) if not _START.search(s)]
    return "\n\n".join(part for part in (" ".join(kept), note) if part)


def _evidence_years(plan: TocPlan | None) -> dict[str, str | None]:
    """The publication dates the searches use: the plan's, or the default before one exists."""
    if plan is None:
        return {"published_after": DEFAULT_PUBLISHED_AFTER, "published_before": None}
    scope = toc_scope_constraints(plan)
    return {"published_after": scope.published_after, "published_before": scope.published_before}


def toc_draft_from_plan(plan: Any) -> TocPlanDraft:
    """Project an approved plan into the API draft."""
    toc = expect_toc_plan(plan)
    values = toc.model_dump(mode="json")
    return TocPlanDraft.model_validate(
        {
            **{key: values.get(key) for key in _PLAN_FIELDS},
            "upload_id": values.get("upload_id"),
            **_evidence_years(toc),
            "ready": True,
        }
    )


def toc_draft_from_wire(draft: TocPlanDraftWire, ready: bool, inputs: TocInputs) -> TocPlanDraft:
    """Project the model's draft into the API draft; the approved plan once a draft exists."""
    if inputs.has_draft and inputs.approved is not None:
        return toc_draft_from_plan(inputs.approved)
    return TocPlanDraft.model_validate(
        {
            **draft.model_dump(),
            **_evidence_years(inputs.approved),
            "ready": ready,
        }
    )


def build_toc_plan(draft: TocPlanDraftWire, inputs: TocInputs, turn_index: int) -> TocPlan:
    """Validate the model's draft into the executable plan, failing closed.

    Raises:
        ValueError: If a draft already exists (the plan is fixed, S7) or the
            plan is not ready for its entry point.
        ValidationError: If the draft does not validate.
    """
    if inputs.has_draft:
        raise ValueError("the plan is fixed once the draft exists")
    values: dict[str, Any] = {key: getattr(draft, key) for key in _PLAN_FIELDS}
    # The model never sets the years: keep the user's from the approved plan
    # (edited in the plan panel), or start from the default.
    previous = inputs.approved.evidence_restriction if inputs.approved is not None else None
    values["evidence_restriction"] = (
        previous.model_dump(mode="json", exclude_none=True)
        if previous is not None
        else {"published_after": DEFAULT_PUBLISHED_AFTER}
    )
    if inputs.imported is not None:
        # The uploaded diagram is the user's theory, word for word (increment 5).
        values |= {
            "entry_point": "existing_theory",
            "existing_theory_text": inputs.imported["text"],
            "upload_id": inputs.imported["upload_id"],
        }
    if inputs.sketch is not None:
        # So is the theory drawn on the canvas; the draft reads the canvas as it is then.
        values |= {
            "entry_point": "existing_theory",
            "existing_theory_text": values.get("existing_theory_text") or inputs.sketch,
            "drawn_on_canvas": True,
        }
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
    return build_toc_messages(
        turns, previous, theory_state=inputs.theory_state, theory_outline=inputs.theory_outline
    )


TOC_TASK_AGENT = TaskAgentProfile(
    capability=THEORY_OF_CHANGE,
    wire=TocTurnWire,
    build_messages=_build_messages,
    step="task_agent_toc",
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
    after_turn=toc_after_turn,
    after_approve=toc_after_approve,
    merge_note=toc_merge_note,
)
