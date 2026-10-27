"""The draft walk's step: write the first theory of change (task 054, step 1.3).

``toc_draft`` reads the walk's plan, asks the model for a draft, runs the E1
structure checks, retries once with the problems named, and writes the graph
through :mod:`policy_atlas.theory_of_change.store`.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import capability_run, evidence_scope, runs, task_plan
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    validate_plan,
)
from policy_atlas.runtime.toc_plan import TocPlan
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.draft_prompt import TOC_DRAFT_PROMPT_VERSION, DraftResponse
from policy_atlas.theory_of_change.graph import (
    Box,
    Graph,
    Link,
    Pathway,
    check_graph,
    trim_conditions,
)

log = structlog.get_logger()

#: The plan fields the ToC prompts read (the draft prompt's documented set).
_PROMPT_FIELDS = (
    "title",
    "question",
    "entry_point",
    "intended_change",
    "target_population",
    "intervention",
    "dosage",
    "where",
    "time_horizon",
    "context",
)


class DraftFailure(RuntimeError):
    """The draft still failed the structure checks after the retry."""


def walk_toc_plan(
    conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID, scope_id: uuid.UUID
) -> TocPlan:
    """Read the plan version a theory-of-change walk runs on.

    The walk's own plan version (``capability_run.plan_id`` through the run
    row), else the intent record's ``plan_id``, as ``walk_plan`` reads a
    scoping walk's.

    Args:
        conn: Open connection.
        task_id: The task.
        run_id: This component run.
        scope_id: The walk's intent record.

    Returns:
        The validated plan.

    Raises:
        ValueError: If no plan version can be found for the walk.
    """
    plan_id = conn.execute(
        select(capability_run.c.plan_id)
        .select_from(
            runs.join(
                capability_run,
                (capability_run.c.capability_run_id == runs.c.capability_run_id)
                & (capability_run.c.task_id == runs.c.task_id),
            )
        )
        .where(runs.c.run_id == run_id, runs.c.task_id == task_id)
    ).scalar_one_or_none()
    if plan_id is None:
        plan_id = conn.execute(
            select(evidence_scope.c.plan_id).where(
                evidence_scope.c.evidence_scope_id == scope_id,
                evidence_scope.c.task_id == task_id,
            )
        ).scalar_one_or_none()
    payload = (
        conn.execute(
            select(task_plan.c.payload).where(
                task_plan.c.plan_id == plan_id, task_plan.c.task_id == task_id
            )
        ).scalar_one_or_none()
        if plan_id is not None
        else None
    )
    if payload is None:
        raise ValueError("theory of change: no plan version found for the walk")
    return expect_toc_plan(validate_plan(THEORY_OF_CHANGE, payload))


def plan_data(plan: TocPlan) -> dict[str, object]:
    """The plan fields every ToC prompt reads, as data (unset fields left out)."""
    dumped = plan.model_dump(mode="json")
    return {key: dumped[key] for key in _PROMPT_FIELDS if dumped.get(key) is not None}


def draft_graph(draft: DraftResponse) -> Graph:
    """Build a :class:`Graph` from a draft, keyed by its local keys."""
    return Graph(
        boxes={box.key: Box(key=box.key, layer=box.layer, text=box.text) for box in draft.boxes},
        links={
            link.key: Link(
                key=link.key,
                source=link.source,
                target=link.target,
                sentence=link.sentence,
                if_text=link.if_text,
                for_text=link.for_text,
                then_text=link.then_text,
                because_text=link.because_text,
                conditions=list(link.conditions),
            )
            for link in draft.links
        },
        pathways=[
            Pathway(key=pathway.key, kind=pathway.kind, links=list(pathway.links))
            for pathway in draft.pathways
        ],
    )


def with_trimmed_conditions(draft: DraftResponse) -> DraftResponse:
    """The draft with at most two conditions per link, none repeated across links.

    A condition whose normalised text appeared on an earlier link is dropped
    (:func:`~policy_atlas.theory_of_change.graph.trim_conditions`), so the
    model's repeats never fail the structure checks or reach the database.
    """
    trimmed = trim_conditions([list(link.conditions) for link in draft.links])
    return draft.model_copy(
        update={
            "links": [
                link.model_copy(update={"conditions": conditions})
                for link, conditions in zip(draft.links, trimmed, strict=True)
            ]
        }
    )


def draft_problems(draft: DraftResponse) -> list[str]:
    """The E1 problems of a draft, plus the checks only a draft can fail."""
    problems = check_graph(draft_graph(draft))
    keys = [
        *(box.key for box in draft.boxes),
        *(link.key for link in draft.links),
        *(pathway.key for pathway in draft.pathways),
    ]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        problems.append(f"keys used twice: {duplicates}")
    if draft.critical_link not in {link.key for link in draft.links}:
        problems.append(f"the critical link {draft.critical_link} is not a step")
    return problems


def toc_draft_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Draft the theory and write it as the task's graph.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The theory-of-change task.
        run_id: This ``toc_draft`` run.
        context: The draft walk's intent record.
        backend: The ToC model seam.

    Returns:
        Counts of what was written, the attempts and the usage totals.

    Raises:
        DraftFailure: If the retry still fails the structure checks; the
            message lists the problems.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    data = plan_data(plan)
    usage = UsageAccumulator()
    draft, call_usage = backend.draft(plan=data, existing_theory=plan.existing_theory_text)
    usage.add(call_usage)
    draft = with_trimmed_conditions(draft)
    problems = draft_problems(draft)
    attempts = 1
    if problems:
        log.info("toc_draft.retry", problems=problems)
        draft, call_usage = backend.draft(
            plan=data, existing_theory=plan.existing_theory_text, problems=problems
        )
        usage.add(call_usage)
        draft = with_trimmed_conditions(draft)
        attempts = 2
        problems = draft_problems(draft)
        if problems:
            raise DraftFailure("the draft failed its structure checks: " + "; ".join(problems))
    store.write_draft(conn, task_id=task_id, run_id=run_id, draft=draft)
    summary = {
        "boxes": len(draft.boxes),
        "links": len(draft.links),
        "pathways": len(draft.pathways),
        "attempts": attempts,
        "backend_mode": backend.mode,
        "prompt_version": TOC_DRAFT_PROMPT_VERSION,
        "usage_totals": usage.payload(),
    }
    log.info("toc_draft.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary
