"""The ``toc_choose`` step: choose after grading (task 054, C6).

Within the 6 / 3 limits, condition supports are recorded, and the critical
connection is chosen by the C6 rule.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    toc_link,
    toc_pathway,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check.grade import (
    VERDICT_LABELS,
    VERDICT_ORDER,
    LinkVerdict,
)
from policy_atlas.theory_of_change.check.shared import (
    _ask,
    _flag_values,
    _short_keys,
    appraisals_for,
    counted_judgements,
    link_verdict_of,
)
from policy_atlas.theory_of_change.draft import _norm, plan_data, walk_toc_plan
from policy_atlas.theory_of_change.graph import (
    MAX_CONDITIONS_PER_LINK,
    MAX_FAILURE_PATHWAYS,
    MAX_SUCCESS_PATHWAYS,
    Graph,
    item_hash,
)

log = structlog.get_logger()


def critical_link(graph: Graph, verdicts: Mapping[str, LinkVerdict]) -> str | None:
    """The critical connection by the C6 rule, on verdicts (C36).

    The weakest important step on a success pathway: among links on kept
    success pathways, the one with the lowest verdict; ties go to the link on
    the most kept pathways, then the earlier one in pathway order. A step the
    evidence supports (Supported or Leaning supports) is never critical
    (owner, 2026-11-04): when every step is supported, there is none.

    Args:
        graph: The theory, with current pathway statuses.
        verdicts: Link key → its verdict; a link without one counts as too
            little evidence.

    Returns:
        The link key, or ``None`` when no kept success pathway has a link or
        every such link is supported.
    """
    kept = [p for p in graph.pathways if p.status == "kept"]
    order = list(
        dict.fromkeys(
            key for p in kept if p.kind == "success" for key in p.links if key in graph.links
        )
    )
    if not order:
        return None
    on = {key: sum(1 for p in kept if key in p.links) for key in order}

    def rank(key: str) -> int:
        found = verdicts.get(key)
        return VERDICT_ORDER.index(found.verdict if found else "not_sure_insufficient")

    weakest = min(order, key=lambda key: (rank(key), -on[key], order.index(key)))
    return None if rank(weakest) >= VERDICT_ORDER.index(CRITICAL_ABOVE) else weakest


#: A step at this verdict or better is never the critical connection.
CRITICAL_ABOVE = "leaning_supports"


def toc_choose_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Keep the best pathways within the limits, add recorded conditions, pick the critical link.

    The model is called only when kept pathways exceed a limit or a support
    recorded a condition its link does not name. Code enforces the 6 / 3
    limits whatever the model says (C6).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        Counts, whether the model was called, and the usage totals.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, rows = store.load_graph(conn, task_id)
    counted = counted_judgements(conn, task_id=task_id)
    appraisals = appraisals_for(
        conn, task_id=task_id, evidence_rows=[row for group in counted.values() for row in group]
    )
    verdicts = {key: link_verdict_of(counted.get(key, []), appraisals) for key in graph.links}
    short, back = _short_keys(graph)
    kept_paths = [p for p in graph.pathways if p.status == "kept"]
    pkey = {p.key: f"p{i}" for i, p in enumerate(kept_paths, start=1)}
    by_short = {value: key for key, value in pkey.items()}
    recorded: list[dict[str, object]] = []
    for key, link in graph.links.items():
        named = {_norm(c) for c in link.conditions}
        new = sorted(
            {
                row.condition
                for row in counted.get(key, [])
                if row.condition and _norm(row.condition) not in named
            }
        )
        if new:
            recorded.append(
                {"link": short[key], "current_conditions": link.conditions, "recorded": new}
            )
    success = [p for p in kept_paths if p.kind == "success"]
    failure = [p for p in kept_paths if p.kind == "failure"]
    over = len(success) > MAX_SUCCESS_PATHWAYS or len(failure) > MAX_FAILURE_PATHWAYS
    usage = UsageAccumulator()
    model_keep: set[str] | None = None
    reasons: dict[str, str] = {}
    added: list[tuple[str, str]] = []
    called = over or bool(recorded)
    if called:
        payload: list[dict[str, object]] = [
            {
                "key": pkey[p.key],
                "kind": p.kind,
                "label": rows.pathways[p.key].label,
                "user_edited": bool(rows.pathways[p.key].user_edited),
                "steps": [
                    {
                        "link": short[key],
                        "sentence": graph.links[key].sentence,
                        "verdict": VERDICT_LABELS[verdicts[key].verdict],
                    }
                    for key in p.links
                    if key in graph.links
                ],
            }
            for p in kept_paths
        ]
        response = _ask(
            "toc_choose",
            lambda: backend.choose(
                plan=plan_data(plan),
                pathways=payload,
                recorded_conditions=recorded,
                max_success=MAX_SUCCESS_PATHWAYS,
                max_failure=MAX_FAILURE_PATHWAYS,
            ),
            usage,
        )
        if response is None:
            raise RuntimeError("toc_choose: the choose call failed")
        model_keep = {
            by_short[d.pathway] for d in response.pathways if d.keep and d.pathway in by_short
        }
        reasons = {
            by_short[d.pathway]: d.reason for d in response.pathways if d.pathway in by_short
        }
        recorded_links = {str(item["link"]) for item in recorded}
        added = [
            (back[a.link], a.condition.strip())
            for a in response.added_conditions
            if a.link in recorded_links and a.condition.strip()
        ]

    log_ = store.ChangeLog()
    changes: list[store.Change] = []
    set_aside = 0
    for kind_paths, limit in ((success, MAX_SUCCESS_PATHWAYS), (failure, MAX_FAILURE_PATHWAYS)):
        if len(kind_paths) <= limit:
            continue
        # The model's keeps first, in pathway order, then the rest, up to the limit.
        preferred = [p for p in kind_paths if model_keep and p.key in model_keep]
        rest = [p for p in kind_paths if p not in preferred]
        keep = {p.key for p in (preferred + rest)[:limit]}
        for p in kind_paths:
            if p.key in keep:
                continue
            row = rows.pathways[p.key]
            reason = reasons.get(p.key) or f"Over the limit of {limit} {p.kind} pathways."
            if store.update(
                conn,
                log_,
                toc_pathway,
                row.pathway_id,
                observed_revision=row.revision,
                values={"status": "set_aside", "reason": reason, **_flag_values(row, reason)},
            ):
                p.status = "set_aside"
                set_aside += 1
                changes.append(
                    {
                        "text": f"Set aside pathway “{row.label}”: {reason}",
                        "pathway_id": str(row.pathway_id),
                    }
                )

    conditions_added = conditions_skipped = 0
    # The conditions rule: at most two per link, none on two links.
    taken = {_norm(c) for other in graph.links.values() for c in other.conditions}
    for key, condition in added:
        link = graph.links[key]
        if len(link.conditions) >= MAX_CONDITIONS_PER_LINK or _norm(condition) in taken:
            conditions_skipped += 1
            continue
        row = rows.links[key]
        new_conditions = [*link.conditions, condition]
        new_link = replace(link, conditions=new_conditions)
        new_hash = item_hash(new_link, graph.boxes[link.source].text, graph.boxes[link.target].text)
        reason = f"Added a condition the evidence recorded: {condition}"
        # kept_by = choose: the condition came from evidence already judged, so
        # the link stays checked, not pending (C19).
        if store.update(
            conn,
            log_,
            toc_link,
            row.link_id,
            observed_revision=row.revision,
            values={
                "conditions": new_conditions,
                "kept_hash": new_hash,
                "kept_by": "choose",
                **_flag_values(row, reason),
            },
        ):
            link.conditions = new_conditions
            taken.add(_norm(condition))
            conditions_added += 1
            changes.append(f"Added a condition to “{link.sentence}”: {condition}")

    critical_changed = _pick_critical(
        conn, log_, task_id=task_id, graph=graph, verdicts=verdicts, changes=changes
    )
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_choose", log=log_, changes=changes)
    summary = {
        "called_model": called,
        # The done row's "kept" (task 054, S2): the pathways still kept after this step.
        "kept": len(kept_paths) - set_aside,
        "set_aside": set_aside,
        "conditions_added": conditions_added,
        "conditions_skipped": conditions_skipped,
        "critical_changed": critical_changed,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_choose.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary


def _pick_critical(
    conn: Connection,
    log_: store.ChangeLog,
    *,
    task_id: uuid.UUID,
    graph: Graph,
    verdicts: Mapping[str, LinkVerdict],
    changes: list[store.Change],
) -> bool:
    """Re-pick the critical connection; a user-marked one is kept (C6)."""
    current = {
        str(row.link_id): row
        for row in conn.execute(select(toc_link).where(toc_link.c.task_id == task_id))
    }
    marked = [row for row in current.values() if row.critical]
    if any(row.user_edited for row in marked):
        return False
    choice = critical_link(graph, verdicts)
    if marked and str(marked[0].link_id) == choice:
        return False
    # Unmark first: at most one critical link per task (W10).
    for row in marked:
        store.update(
            conn,
            log_,
            toc_link,
            row.link_id,
            observed_revision=row.revision,
            values={"critical": False},
        )
    if choice is None:
        # Every step on the routes to the goal is supported: no connection is critical.
        if marked:
            changes.append("No connection is critical: every step to the goal is supported.")
        return bool(marked)
    row = current[choice]
    if store.update(
        conn, log_, toc_link, row.link_id, observed_revision=row.revision, values={"critical": True}
    ):
        changes.append(f"The critical connection is now “{row.sentence}”.")
        return True
    return False
