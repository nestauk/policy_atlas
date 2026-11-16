"""The ``toc_merge`` step: join and set aside before judging (task 054, C6).

One call joins pathways that share a mechanism and sets aside those that miss
the intended change. ``fold_box`` is the same move on one box, for a proposal.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.engine import Connection, Row

from policy_atlas.core.schema import (
    toc_box,
    toc_link,
    toc_pathway,
    toc_pathway_link,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check.shared import (
    _ask,
    _flag_values,
    _short_keys,
    _user_written,
)
from policy_atlas.theory_of_change.draft import plan_data, walk_toc_plan

log = structlog.get_logger()


def _keep_one_of_each(order: list[str], kinds: dict[str, str], kept: set[str]) -> set[str]:
    """Keep back the first pathway of a kind the decisions left with none."""
    for kind in ("success", "failure"):
        if not any(kinds[key] == kind for key in kept):
            first = next((key for key in order if kinds[key] == kind), None)
            if first is not None:
                kept.add(first)
    return kept


def fold_problem(
    rows: store.GraphRows, box: str, into: str, *, by_user: bool = False
) -> str | None:
    """Why one box may not be folded into another, or ``None`` when it may (C29).

    Args:
        rows: The current graph rows.
        box: The box to fold away (row id as text).
        into: The box it would be folded into.
        by_user: The user accepted this merge (C45): their own boxes may go.

    Returns:
        The reason, or ``None``.
    """
    if box not in rows.boxes or into not in rows.boxes:
        return "a box does not exist"
    if box == into:
        return "it is the same box"
    if rows.boxes[box].layer != rows.boxes[into].layer:
        return "the boxes are in different layers"
    if not by_user and _user_written(rows.boxes[box]) and not _user_written(rows.boxes[into]):
        return "a box the user wrote is never folded into one they did not"
    return None


class _FoldSkipped(Exception):
    """A row changed under the fold: the fold is rolled back (C10)."""


def fold_box(
    conn: Connection,
    log_: store.ChangeLog,
    *,
    task_id: uuid.UUID,
    box: str,
    into: str,
    by_user: bool = False,
) -> bool:
    """Fold one box into another of the same layer (C29).

    Every link from or to ``box`` is re-pointed at ``into``. A link that would
    then join a box to itself is dropped from its pathways and deleted. Two
    links that would then join the same pair become one: the user-edited one
    is kept, else the older, and the other's pathway steps point at it. Then
    ``box`` is deleted. All of it, or nothing when a row changed meanwhile.

    Args:
        conn: Open connection inside the component transaction.
        log_: The step's change log.
        task_id: The task.
        box: The box to fold away (row id as text).
        into: The box to keep.

    Returns:
        Whether the fold was applied.
    """
    _, rows = store.load_graph(conn, task_id)
    if fold_problem(rows, box, into, by_user=by_user) is not None:
        return False
    old, new = uuid.UUID(box), uuid.UUID(into)

    def ends(row: Row[Any]) -> tuple[uuid.UUID, uuid.UUID]:
        swap = {old: new}
        return swap.get(row.source_box_id, row.source_box_id), swap.get(
            row.target_box_id, row.target_box_id
        )

    links = list(rows.links.values())
    moved = [row for row in links if old in (row.source_box_id, row.target_box_id)]
    by_pair: dict[tuple[uuid.UUID, uuid.UUID], list[Row[Any]]] = {}
    for row in links:
        by_pair.setdefault(ends(row), []).append(row)
    attempt = store.ChangeLog()
    nested = conn.begin_nested()
    try:
        for row in moved:
            source, target = ends(row)
            if source == target:
                conn.execute(
                    toc_pathway_link.delete().where(toc_pathway_link.c.link_id == row.link_id)
                )
                store.delete(conn, attempt, toc_link, row.link_id)
                continue
            pair = by_pair[(source, target)]
            survivor = min(pair, key=lambda r: (not r.user_edited, r.created_at))
            for loser in pair:
                if loser.link_id == survivor.link_id:
                    continue
                conn.execute(
                    toc_pathway_link.update()
                    .where(toc_pathway_link.c.link_id == loser.link_id)
                    .values(link_id=survivor.link_id)
                )
                store.delete(conn, attempt, toc_link, loser.link_id)
            pair[:] = [survivor]
        for row in moved:
            source, target = ends(row)
            if source == target or by_pair[(source, target)][0].link_id != row.link_id:
                continue
            if not store.update(
                conn,
                attempt,
                toc_link,
                row.link_id,
                observed_revision=row.revision,
                values={"source_box_id": source, "target_box_id": target},
            ):
                raise _FoldSkipped
        store.delete(conn, attempt, toc_box, old)
    except _FoldSkipped:
        nested.rollback()
        log_.skipped.append({"table": "toc_box", "id": box})
        return False
    nested.commit()
    log_.created.extend(attempt.created)
    log_.before.extend(attempt.before)
    return True


def toc_merge_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Fold repeated boxes, merge pathways that share a mechanism, set aside misses (C29).

    The box folds the call names are applied first, each checked by
    :func:`fold_problem` and done by :func:`fold_box`; then the pathway
    decisions.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        Counts of kept, merged and set-aside pathways and the usage totals.

    Raises:
        RuntimeError: If the merge call failed twice.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, rows = store.load_graph(conn, task_id)
    short, back = _short_keys(graph)
    kept_paths = [pathway for pathway in graph.pathways if pathway.status == "kept"]
    pkey = {pathway.key: f"p{i}" for i, pathway in enumerate(kept_paths, start=1)}
    by_short = {value: key for key, value in pkey.items()}
    payload: list[dict[str, object]] = []
    for pathway in kept_paths:
        row = rows.pathways[pathway.key]
        payload.append(
            {
                "key": pkey[pathway.key],
                "kind": pathway.kind,
                "label": row.label,
                "origin": row.origin,
                "user_edited": bool(row.user_edited),
                "route": [
                    {
                        "source": short[graph.links[key].source],
                        "target": short[graph.links[key].target],
                        "sentence": graph.links[key].sentence,
                        "because": graph.links[key].because_text,
                    }
                    for key in pathway.links
                    if key in graph.links
                ],
            }
        )
    on_kept = {
        end
        for pathway in kept_paths
        for key in pathway.links
        if key in graph.links
        for end in (graph.links[key].source, graph.links[key].target)
    }
    boxes: list[dict[str, object]] = [
        {
            "key": short[key],
            "layer": box.layer,
            "text": box.text,
            "user_edited": _user_written(rows.boxes[key]),
        }
        for key, box in graph.boxes.items()
        if key in on_kept
    ]
    usage = UsageAccumulator()
    response = _ask(
        "toc_merge",
        lambda: backend.merge(plan=plan_data(plan), boxes=boxes, pathways=payload),
        usage,
    )
    if response is None:
        raise RuntimeError("toc_merge: the merge call failed")
    log_ = store.ChangeLog()
    changes: list[store.Change] = []
    # Box folds first (C29): the pathway decisions were made on the folded boxes.
    folded: dict[str, str] = {}
    box_folds = refused = 0
    for wire in response.box_merges:
        box, into = back.get(wire.box), back.get(wire.into)
        while into in folded:  # a chain of folds ends at the box that stays
            into = folded[into]
        if box is None or into is None or box in folded:
            refused += 1
            continue
        if fold_box(conn, log_, task_id=task_id, box=box, into=into):
            folded[box] = into
            box_folds += 1
            changes.append(f"Merged box “{graph.boxes[box].text}” into “{graph.boxes[into].text}”")
        else:
            refused += 1
    decisions = {
        by_short[decision.pathway]: decision
        for decision in response.decisions
        if decision.pathway in by_short
    }
    kinds = {pathway.key: pathway.kind for pathway in kept_paths}
    order = [pathway.key for pathway in kept_paths]
    kept = {key for key in order if key not in decisions or decisions[key].action == "keep"}
    kept = _keep_one_of_each(order, kinds, kept)
    merged = set_aside = 0
    for key in order:
        if key in kept:
            continue
        decision = decisions[key]
        row = rows.pathways[key]
        into = by_short.get(decision.into or "")
        if decision.action == "merge" and into is not None and into != key:
            reason = f"Merged into “{rows.pathways[into].label}”: {decision.reason}"
            line = f"Merged pathway “{row.label}” into “{rows.pathways[into].label}”"
            line += f": {decision.reason}"
        else:
            reason = decision.reason
            line = f"Set aside pathway “{row.label}”: {decision.reason}"
        if store.update(
            conn,
            log_,
            toc_pathway,
            row.pathway_id,
            observed_revision=row.revision,
            values={"status": "set_aside", "reason": reason, **_flag_values(row, reason)},
        ):
            changes.append({"text": line, "pathway_id": str(row.pathway_id)})
            if decision.action == "merge":
                merged += 1
            else:
                set_aside += 1
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_merge", log=log_, changes=changes)
    summary = {
        "pathways": len(order),
        "kept": len(order) - merged - set_aside,
        "merged": merged,
        "set_aside": set_aside,
        "box_folds": box_folds,
        "box_folds_refused": refused,
        "skipped": len(log_.skipped),
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_merge.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary
