"""Seminal works: the studies the check's documents cite most (task 054, ruling 2026-11-04).

The item searches find recent documents by meaning, so an older, much-cited
study that shaped a field can be missed. After every item search has
finished, this step counts which works the check's OpenAlex (the open
scholarly-works index) records cite, takes the most-cited works that are not
already among them, and looks them up in one OpenAlex call. They are stored
like any acquired document, marked with the origin ``seminal`` on their
``source.acquired`` event, and ``toc_select`` then offers them to every
connection's pick.

This reuses Evidence search's backward citation chase: the same counting
(:func:`~policy_atlas.evidence_search.sourcing.pool.count_references`), the
same choice of targets, and the same OpenAlex id lookup. The plan's evidence
years go on the lookup as a filter, as on the chase.
"""

from __future__ import annotations

import uuid
from typing import Any, Final

import structlog
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import EmbeddingBackend
from policy_atlas.evidence_search.sourcing.acquire import (
    AcquireContext,
    SearchBackendBase,
    acquire_sources,
)
from policy_atlas.evidence_search.sourcing.pool import (
    backward_targets,
    count_references,
    record_short_id,
)
from policy_atlas.evidence_search.sourcing.search_loop import ExecutedCall, openalex_wire_params
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.runtime.toc_plan import TocPlan, toc_scope_constraints
from policy_atlas.theory_of_change import store

log = structlog.get_logger()

#: The most seminal works one check looks up: one OpenAlex call (it takes 50 ids).
SEMINAL_WORKS = 25

#: The origin recorded on a seminal work's ``source.acquired`` event.
SEMINAL_ORIGIN: Final = "seminal"


def fetch_seminal_works(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    plan: TocPlan,
    pool_ids: set[uuid.UUID],
    searchers: list[Any],
    embedder: EmbeddingBackend | None,
) -> dict[str, Any]:
    """Look up and store the works the check's documents cite most.

    Fails soft: with no OpenAlex backend, or when the lookup fails, nothing
    is stored and the check carries on.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run; the stored works' events go on it.
        context: The check walk's intent record.
        plan: The walk's plan; its evidence years filter the lookup.
        pool_ids: Every document the check's item searches found.
        searchers: The walk's search backends; only ``openalex`` is used.
        embedder: The embedding backend for the stored works, or ``None``.

    Returns:
        Counts: ``references_counted`` (citations read across the pool),
        ``targets`` (works asked for), ``resolved`` (works OpenAlex returned)
        and ``lookup_failed``.
    """
    counts: dict[str, Any] = {
        "references_counted": 0,
        "targets": 0,
        "resolved": 0,
        "lookup_failed": False,
    }
    if not pool_ids:
        return counts
    # Each stored OpenAlex record keeps its id and (up to 60 of) the works it cites.
    metas = [row.metadata or {} for row in store.snapshot_meta(conn, task_id, pool_ids).values()]
    records = [
        {
            "id": meta.get("backend_record_id"),
            "referenced_works": (meta.get("provider_fields") or {}).get("referenced_works"),
        }
        for meta in metas
        if meta.get("backend") == "openalex"
    ]
    in_pool = {work_id for record in records if (work_id := record_short_id(record))}
    cited = count_references(records)
    targets = backward_targets(cited, in_pool, SEMINAL_WORKS)
    counts["references_counted"] = sum(cited.values())
    counts["targets"] = len(targets)
    openalex = next((b for b in searchers if getattr(b, "name", None) == "openalex"), None)
    if not targets or openalex is None:
        return counts
    published = toc_scope_constraints(plan).to_filters().get("shared", {})
    wire = openalex_wire_params(published)
    try:
        found = list(openalex.lookup_ids(targets, wire_params=wire))
    except Exception as exc:  # any provider failure: carry on without them
        log.warning("toc_seminal.lookup_failed", task_id=str(task_id), error=str(exc))
        counts["lookup_failed"] = True
        return counts
    # Most-cited first, so the pool rank on each event is the citation rank.
    rank = {work_id: i for i, work_id in enumerate(targets)}
    found.sort(key=lambda r: rank.get(record_short_id(r) or "", len(rank)))
    counts["resolved"] = len(found)
    backend: SearchBackendBase = openalex
    acquire_sources(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=AcquireContext(
            scope_id=context.scope_id, intent=context.intent, context=context.context
        ),
        backends=[backend],
        embedder=embedder,
        executed_calls=[
            ExecutedCall(
                backend_name="openalex",
                verb="fetch_references",
                query="|".join(targets),
                query_origin=SEMINAL_ORIGIN,
                wire_params=wire,
                records=found,
                status="ok",
                error=None,
            )
        ],
        depth="link",
        pools={"openalex": [(r, SEMINAL_ORIGIN, "fetch_references") for r in found]},
    )
    return counts
