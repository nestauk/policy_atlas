"""The draft walk's step: write the first theory of change (task 054, step 1.3).

``toc_draft`` reads the walk's plan, asks the model for a draft, runs the E1
structure checks, retries once with the problems named, and writes the graph
through :mod:`policy_atlas.theory_of_change.store`. A draft written onto an
empty canvas is drawn on the page as it is written
(:mod:`policy_atlas.theory_of_change.draft_stream`, task 054, S12).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    capability_run,
    event_log,
    evidence_scope,
    runs,
    task_plan,
    toc_box,
    toc_link,
)
from policy_atlas.core.usage import UsageAccumulator, UsageResult
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    validate_plan,
)
from policy_atlas.runtime.toc_plan import TocPlan, as_drawn
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.draft_prompt import (
    TOC_DRAFT_PROMPT_VERSION,
    DraftPathwayWire,
    DraftResponse,
)
from policy_atlas.theory_of_change.draft_stream import SketchFrames, draft_streamed
from policy_atlas.theory_of_change.graph import (
    Box,
    Graph,
    Link,
    Pathway,
    check_graph,
    trim_conditions,
)
from policy_atlas.theory_of_change.proposals import EditOpWire, create_proposal

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
    return with_clarifications(
        conn, task_id, expect_toc_plan(validate_plan(THEORY_OF_CHANGE, payload))
    )


#: The event a clarification to the plan is stored as (C49).
TOC_CLARIFICATION_EVENT = "toc.clarification"


def clarifications(conn: Connection, task_id: uuid.UUID) -> list[str]:
    """The user's clarifications to the plan, oldest first (C49)."""
    return [
        str(payload.get("text"))
        for payload in conn.execute(
            select(event_log.c.payload)
            .where(event_log.c.task_id == task_id)
            .where(event_log.c.event_type == TOC_CLARIFICATION_EVENT)
            .order_by(event_log.c.sequence)
        ).scalars()
        if payload.get("text")
    ]


def with_clarifications(conn: Connection, task_id: uuid.UUID, plan: TocPlan) -> TocPlan:
    """The plan with the user's clarifications added to its context, which every prompt reads."""
    notes = clarifications(conn, task_id)
    if not notes:
        return plan
    context = "\n".join(
        part
        for part in [plan.context or "", "The user's clarifications: " + " ".join(notes)]
        if part
    )
    return plan.model_copy(update={"context": context})


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


def draft_problems(draft: DraftResponse, *, as_drawn: bool = False) -> list[str]:
    """The E1 problems of a draft, plus the checks only a draft can fail.

    ``as_drawn``: the user's diagram kept as given, checked by the lighter rules.
    """
    problems = check_graph(draft_graph(draft), as_drawn=as_drawn)
    # The user's own steps keep their shape (owner, 2026-11-04): a step they drew
    # from an input straight to an outcome is theirs to keep, not a reason to redraft.
    theirs = {link.key for link in draft.links if link.from_user_theory}
    problems = [
        problem
        for problem in problems
        if not (
            problem.startswith("step ")
            and problem.split(":", 1)[0][5:] in theirs
            and "cannot lead" in problem
        )
    ]
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


#: The canvas shows at most this many of the user's own routes.
MAX_DRAWN_PATHWAYS = 6
#: Why a suggestion to complete the theory was made.
COMPLETES = "Added to complete the theory."


def drawn_part(draft: DraftResponse) -> DraftResponse | None:
    """The user's own part of a draft of their diagram, or ``None`` to keep it all.

    Keeps the boxes marked as the user's and every link between two of them,
    and draws one route per
    chain of their links (named after a draft pathway it matches, else its
    last box). ``None`` when the user drew no connection, or their part fails
    even the lighter as-drawn structure rules: the whole draft is used then.
    """
    boxes = [box for box in draft.boxes if box.from_user_theory]
    kept = {box.key for box in boxes}
    # Every link between two of the user's boxes: their arrows, and the specific
    # ones read from a bracket or a group (shown as suggested while they review).
    links = [link for link in draft.links if link.source in kept and link.target in kept]
    if not links:
        return None
    layer = {box.key: box.layer for box in boxes}
    text = {box.key: box.text for box in boxes}
    by_key = {link.key: link for link in links}
    chains = [
        [by_key[key] for key in chain]
        for chain in _chains([(link.key, link.source, link.target) for link in links])
    ]
    named = {tuple(p.links): p.label for p in draft.pathways}
    pathways = [
        DraftPathwayWire(
            key=f"p{i}",
            kind="failure" if layer[chain[-1].target] == "failure_outcome" else "success",
            label=named.get(tuple(link.key for link in chain))
            or " ".join(text[chain[-1].target].split()[:8]),
            links=[link.key for link in chain],
        )
        for i, chain in enumerate(chains[:MAX_DRAWN_PATHWAYS], start=1)
    ]
    keys = {link.key for link in links}
    drawn = draft.model_copy(
        update={
            "boxes": boxes,
            "links": links,
            "pathways": pathways,
            "critical_link": draft.critical_link if draft.critical_link in keys else links[0].key,
        }
    )
    return None if draft_problems(drawn, as_drawn=True) else drawn


def _chains(steps: list[tuple[str, str, str]]) -> list[list[str]]:
    """Each route through the steps ``(key, source, target)``, start to end, as step keys.

    Routes start where no step leads in (or at the first step, in a loop); at
    most :data:`MAX_DRAWN_PATHWAYS`.
    """
    leaving: dict[str, list[tuple[str, str, str]]] = {}
    for step in steps:
        leaving.setdefault(step[1], []).append(step)
    ends = {step[2] for step in steps}
    chains: list[list[str]] = []

    def walk(path: list[tuple[str, str, str]]) -> None:
        onward = [step for step in leaving.get(path[-1][2], []) if step not in path]
        if not onward:
            chains.append([step[0] for step in path])
        for step in onward:
            if len(chains) < MAX_DRAWN_PATHWAYS:
                walk([*path, step])

    for start in [step for step in steps if step[1] not in ends] or steps[:1]:
        walk([start])
    return chains[:MAX_DRAWN_PATHWAYS]


def user_sketch(conn: Connection, task_id: uuid.UUID) -> tuple[list[Any], list[Any]]:
    """The boxes and connections the user drew on the canvas before any draft.

    Empty once a draft is on the canvas (:func:`store.has_graph`): then the
    user's boxes are edits to the draft, not their own theory.
    """
    if store.has_graph(conn, task_id):
        return [], []
    boxes = list(conn.execute(select(toc_box).where(toc_box.c.task_id == task_id)))
    links = list(conn.execute(select(toc_link).where(toc_link.c.task_id == task_id)))
    return boxes, links


def sketch_text(boxes: list[Any], links: list[Any]) -> str:
    """The user's canvas as the drafter's existing-theory text, as a diagram is read."""
    text = {box.box_id: box.text for box in boxes}
    lines = [
        "The user's own theory of change, drawn on the canvas.",
        "",
        "Boxes (the user's words; the layer they placed them in):",
        *(f"- [{box.layer}] {box.text}" for box in boxes),
    ]
    if links:
        lines += [
            "",
            "Connections the user drew (the user's; keep each, as from_user_theory):",
            *(
                f"- “{text[link.source_box_id]}” → “{text[link.target_box_id]}”"
                + (f" (because: {link.because_text})" if link.because_text else "")
                for link in links
            ),
        ]
    return "\n".join(lines)


def adopt_sketch(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    draft: DraftResponse,
    boxes: list[Any],
    links: list[Any],
) -> tuple[DraftResponse, dict[str, uuid.UUID]]:
    """Keep the user's canvas as drawn and fill it in from the draft (owner, 2026-11-05).

    The user's boxes and connections stay where they are. A draft box with
    the same text is theirs; a draft link between two of them is their
    connection, and gives its wording to a connection the user left without a
    reason. Each route through their connections becomes a pathway, and the
    draft's context and supporting activities are added. Their boxes are
    marked as from their theory, so the canvas now counts as drafted.

    Returns:
        The draft's part already on the canvas, and draft key → row id, for
        :func:`suggest_the_rest`.
    """
    log = store.ChangeLog()
    row_of = {_norm(box.text): box for box in boxes}
    ids: dict[str, uuid.UUID] = {}
    kept_boxes = []
    for box in draft.boxes:
        row = row_of.get(_norm(box.text))
        if row is not None and row.box_id not in ids.values():
            ids[box.key] = row.box_id
            kept_boxes.append(box)
    by_ends = {(link.source_box_id, link.target_box_id): link for link in links}
    kept_links = []
    for link in draft.links:
        row = by_ends.get((ids.get(link.source), ids.get(link.target)))
        if row is None or row.link_id in ids.values():
            continue
        ids[link.key] = row.link_id
        kept_links.append(link)
        if not row.because_text:
            store.update(
                conn,
                log,
                toc_link,
                row.link_id,
                observed_revision=row.revision,
                values={
                    "sentence": link.sentence,
                    "if_text": link.if_text,
                    "for_text": link.for_text,
                    "then_text": link.then_text,
                    "because_text": link.because_text,
                    "conditions": list(row.conditions or []) or list(link.conditions),
                },
            )
    for row in boxes:
        store.update(
            conn,
            log,
            toc_box,
            row.box_id,
            observed_revision=row.revision,
            values={"origin": "imported"},
        )
    layer = {box.box_id: box.layer for box in boxes}
    text = {box.box_id: box.text for box in boxes}
    target = {str(link.link_id): link.target_box_id for link in links}
    named = {tuple(str(ids[k]) for k in p.links if k in ids): p.label for p in draft.pathways}
    for chain in _chains(
        [(str(link.link_id), str(link.source_box_id), str(link.target_box_id)) for link in links]
    ):
        end = target[chain[-1]]
        store.insert_pathway(
            conn,
            log,
            task_id=task_id,
            pathway_id=uuid.uuid4(),
            kind="failure" if layer[end] == "failure_outcome" else "success",
            label=named.get(tuple(chain)) or " ".join(text[end].split()[:8]),
            link_ids=[uuid.UUID(key) for key in chain],
            origin="imported",
        )
    store.insert_bands(conn, log, task_id=task_id, draft=draft)
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_draft", log=log)
    drawn = draft.model_copy(update={"boxes": kept_boxes, "links": kept_links, "pathways": []})
    return drawn, ids


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def suggest_the_rest(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    draft: DraftResponse,
    drawn: DraftResponse,
    ids: dict[str, uuid.UUID],
) -> uuid.UUID | None:
    """Store what the draft added to the user's diagram as one suggestion.

    Its new boxes, then its new links, then each draft pathway that uses one,
    so Accept all builds them in order. The user's boxes and links are named
    by their codes, new ones by their draft keys.
    """
    on_canvas = {box.key for box in drawn.boxes} | {link.key for link in drawn.links}
    code: dict[uuid.UUID, str | None] = {
        row.box_id: row.code
        for row in conn.execute(
            select(toc_box.c.box_id, toc_box.c.code).where(toc_box.c.task_id == task_id)
        )
    }
    code |= {
        row.link_id: row.code
        for row in conn.execute(
            select(toc_link.c.link_id, toc_link.c.code).where(toc_link.c.task_id == task_id)
        )
    }

    def ref(key: str) -> str:
        return str(code.get(ids[key]) or key) if key in on_canvas and key in ids else key

    def op(**values: object) -> EditOpWire:
        return EditOpWire.of(**{"reason": COMPLETES, **values})

    # One route at a time (owner, 2026-11-04): each route's new boxes, its new
    # links, then the pathway, tagged r1, r2 ... A box or link two routes share
    # goes with the first; accepting the second brings it along.
    box_of = {box.key: box for box in draft.boxes}
    link_of = {link.key: link for link in draft.links}
    routes = [p for p in draft.pathways if any(key not in on_canvas for key in p.links)]
    ops: list[EditOpWire] = []
    offered: set[str] = set()
    for n, path in enumerate(routes, start=1):
        group = f"r{n}"
        new_links = [link_of[key] for key in path.links if key in link_of and key not in on_canvas]
        for link in new_links:
            for end in (link.source, link.target):
                if end not in on_canvas and end not in offered and end in box_of:
                    offered.add(end)
                    box = box_of[end]
                    ops.append(
                        op(op="add_box", key=box.key, layer=box.layer, text=box.text, group=group)
                    )
        for link in new_links:
            if link.key in offered:
                continue
            offered.add(link.key)
            ops.append(
                op(
                    op="add_link",
                    key=link.key,
                    source=ref(link.source),
                    dest=ref(link.target),
                    if_text=link.if_text,
                    then_text=link.then_text,
                    because_text=link.because_text,
                    group=group,
                )
            )
        ops.append(
            op(
                op="add_pathway",
                links=[ref(key) for key in path.links],
                kind=path.kind,
                label=path.label,
                group=group,
            )
        )
    failures = sum(1 for p in routes if p.kind == "failure")
    successes = len(routes) - failures

    def count(n: int, one: str, many: str) -> str:
        return f"{n} {one if n == 1 else many}"

    parts = [
        count(successes, "more route to the goal", "more routes to the goal") if successes else "",
        count(failures, "way it could go wrong", "ways it could go wrong") if failures else "",
    ]
    return create_proposal(
        conn,
        task_id=task_id,
        source="draft",
        summary="To complete your theory: "
        + (" and ".join(part for part in parts if part) or "steps your diagram does not show"),
        ops=ops,
    )


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
    # The user's own boxes on the canvas are their theory, with any diagram they uploaded.
    sketched, sketched_links = user_sketch(conn, task_id)
    existing = plan.existing_theory_text
    if sketched:
        # The canvas as it is now, and the uploaded diagram's reading if there is one.
        from policy_atlas.theory_of_change.importing import latest_import

        imported = latest_import(conn, task_id) if plan.upload_id is not None else None
        existing = "\n\n".join(
            part
            for part in (sketch_text(sketched, sketched_links), imported and imported["text"])
            if part
        )
    # Drawn live only when the draft becomes the canvas as written: the user's own
    # boxes or diagram keep their place, and the draft only fills them in (S12).
    sketch = SketchFrames() if not sketched and not as_drawn(plan) else None

    def ask(problems: list[str] | None = None) -> UsageResult[DraftResponse]:
        if sketch is None:
            return backend.draft(plan=data, existing_theory=existing, problems=problems)
        return draft_streamed(
            backend, plan=data, existing_theory=existing, problems=problems, frames=sketch
        )

    draft, call_usage = ask()
    usage.add(call_usage)
    draft = with_trimmed_conditions(draft)
    problems = draft_problems(draft)
    attempts = 1
    if problems:
        log.info("toc_draft.retry", problems=problems)
        if sketch is not None:
            # The page drops the failed draft and draws the retry from the start.
            sketch.reset()
        draft, call_usage = ask(problems)
        usage.add(call_usage)
        draft = with_trimmed_conditions(draft)
        attempts = 2
        problems = draft_problems(draft)
        if problems:
            if sketch is not None:
                sketch.reset()
            raise DraftFailure("the draft failed its structure checks: " + "; ".join(problems))
    # An uploaded diagram: the canvas starts with the user's own boxes and arrows;
    # what the draft added to complete the theory waits as one suggestion
    # (owner, 2026-11-04).
    if sketched_links:
        kept, ids = adopt_sketch(
            conn,
            task_id=task_id,
            run_id=run_id,
            draft=draft,
            boxes=sketched,
            links=sketched_links,
        )
        suggest_the_rest(conn, task_id=task_id, draft=draft, drawn=kept, ids=ids)
        return _draft_summary(draft, attempts, backend, usage)
    if sketched:
        # Boxes without connections: the draft's reading of them replaces them.
        log_ = store.ChangeLog()
        for row in sketched:
            store.delete(conn, log_, toc_box, row.box_id)
        store.record(conn, task_id=task_id, run_id=run_id, step="toc_draft", log=log_)
    drawn = drawn_part(draft) if as_drawn(plan) or sketched else None
    if drawn is None:
        store.write_draft(conn, task_id=task_id, run_id=run_id, draft=draft)
    else:
        ids = store.write_draft(conn, task_id=task_id, run_id=run_id, draft=drawn)
        suggest_the_rest(conn, task_id=task_id, draft=draft, drawn=drawn, ids=ids)
    return _draft_summary(draft, attempts, backend, usage)


def _draft_summary(
    draft: DraftResponse, attempts: int, backend: TocBackend, usage: UsageAccumulator
) -> dict[str, Any]:
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
