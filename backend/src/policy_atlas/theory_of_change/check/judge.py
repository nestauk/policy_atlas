"""The ``toc_judge`` step: one link against one document (task 054, C5, C36).

Per link, its own search's documents (or, for a link with none, the *K* pool
documents closest by meaning) are read with one call each; its support,
verified quote and relevance are stored. Insert-only, keyed by item hash.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.embeddings import (
    EmbeddingBackend,
)
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    toc_item_evidence,
    toc_link,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.assess.screen import ScreenContext, screen_in
from policy_atlas.evidence_search.corpus.ranking import (
    RankingBackend,
)
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.model_calls import CallOutcome
from policy_atlas.runtime.toc_plan import (
    TOC_CHECK_MODE_KEY,
    TOC_LINKS_KEY,
    TOC_REFORMULATE_KEY,
    TOC_STARTED_BY_KEY,
    TOC_STUDIES_KEY,
)
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check.selecting import (
    JUDGE_TOP_K,
    _child_links,
    _document_vectors,
    _link_candidates,
    _user_decisions,
    _walk_picks,
    documents_per_link,
    nearest,
    rerank,
    toc_select_scope,
)
from policy_atlas.theory_of_change.check.shared import (
    PROGRAMME_EVENT,
    PROGRAMME_KEY,
    Document,
    _call,
    _link_item_text,
    _map_traced,
    _outcome_value,
    links_to_check,
    programme_item_text,
    quote_found,
    screened_documents,
    walk_of_run,
)
from policy_atlas.theory_of_change.draft import walk_toc_plan
from policy_atlas.theory_of_change.graph import (
    Graph,
    Link,
    item_hash,
)

log = structlog.get_logger()


#: The reason ``toc_judge`` records on a document no link found on topic (C31).
NOT_ABOUT_REASON = "judged_not_about_any_step"


#: Judge calls in flight at once.
JUDGE_WORKERS = 16


@dataclass
class _JudgeJob:
    link_key: str
    document: Document
    item_text: str
    item_hash: str
    source_key: str
    target_key: str
    neighbours: str


#: Neighbouring steps shown to the judge on each side of a link.
NEIGHBOURS_PER_SIDE = 3


def neighbour_lines(graph: Graph, key: str) -> str:
    """The steps just before, after and alongside a link, for the judge (``toc_judge_v8``).

    One ``Before: <sentence>`` line per link that ends at this link's source
    box, one ``After: <sentence>`` line per link that starts at its target
    box, and one ``Alongside: <sentence>`` line per other link into the same
    target or out of the same source (the same effect by another route), at
    most :data:`NEIGHBOURS_PER_SIDE` each, in graph order.

    Args:
        graph: The current theory.
        key: The link being judged.

    Returns:
        The lines joined by newlines, or ``""`` when the link has no neighbours.
    """
    link = graph.links[key]

    def sentence(other: Link) -> str:
        return other.sentence.strip() or (
            f"{graph.boxes[other.source].text} leads to {graph.boxes[other.target].text}"
        )

    others = [other for k, other in graph.links.items() if k != key]
    before = [f"Before: {sentence(o)}" for o in others if o.target == link.source]
    after = [f"After: {sentence(o)}" for o in others if o.source == link.target]
    alongside = [
        f"Alongside: {sentence(o)}"
        for o in others
        if o.target == link.target or o.source == link.source
    ]
    return "\n".join(
        before[:NEIGHBOURS_PER_SIDE] + after[:NEIGHBOURS_PER_SIDE] + alongside[:NEIGHBOURS_PER_SIDE]
    )


def toc_judge_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    ranker: RankingBackend | None = None,
    embedder: EmbeddingBackend | None = None,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Judge each link against its top documents, both questions at once (C5).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        ranker: The rerank backend ``select`` uses, or ``None`` to keep order.
        embedder: The embedding backend that picks the closest pool documents
            for a link with no search of its own (C27), or ``None``.

    Returns:
        Link, call and judgement counts, ``unverified_dropped`` and the usage.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    walk_id = walk_of_run(conn, task_id=task_id, run_id=run_id)
    graph, rows = store.load_graph(conn, task_id)
    named = context.context.get(TOC_LINKS_KEY)
    link_keys, left_out = links_to_check(graph, list(named) if named else None)
    if only is not None:
        # The second search (C44): these links only, no programme judgements.
        link_keys, named = [key for key in link_keys if key in only], list(only)
    pool = screened_documents(conn, task_id=task_id, scope_id=context.scope_id)
    pool_by_id = {doc.tss_id: doc for doc in pool}
    # Each link reads what toc_select picked for it (C31). When no link's search
    # found anything, a link with a search of its own judges nothing.
    # Find more evidence (C44) reads more documents per link.
    top_k = documents_per_link(context.context)
    own = _walk_picks(conn, task_id=task_id, walk_id=walk_id) or {
        key: set() for key in _child_links(conn, task_id=task_id, walk_id=walk_id).values()
    }
    vectors: dict[uuid.UUID, list[list[float]]] | None = None  # read once, when needed
    usage = UsageAccumulator()
    place = plan.where
    jobs: list[_JudgeJob] = []
    hashes: dict[str, str] = {}
    for key in link_keys:
        link = graph.links[key]
        source, target = graph.boxes[link.source], graph.boxes[link.target]
        current = hashes[key] = item_hash(link, source.text, target.text)
        text = _link_item_text(graph, key, plan)
        judged = set(
            conn.execute(
                select(toc_item_evidence.c.task_source_snapshot_id)
                .where(toc_item_evidence.c.task_id == task_id)
                .where(toc_item_evidence.c.link_id == uuid.UUID(key))
                .where(toc_item_evidence.c.item_hash == current)
            ).scalars()
        )
        if key in own:
            candidates = [
                pool_by_id[tss]
                for tss in sorted(own[key], key=str)
                if tss in pool_by_id and tss not in judged
            ]
            chosen = rerank(ranker, candidates, intent=text, usage=usage)[:top_k]
        else:
            # Added by discovery after the fan-out: the closest pool documents.
            if vectors is None:
                vectors = _document_vectors(conn, pool_by_id)
            candidates = [doc for doc in pool if doc.tss_id not in judged]
            chosen = nearest(embedder, candidates, vectors, text=text, k=top_k)
        for document in chosen:
            jobs.append(
                _JudgeJob(
                    key,
                    document,
                    text,
                    current,
                    link.source,
                    link.target,
                    neighbour_lines(graph, key),
                )
            )

    # The whole programme, on a full check: its own search's documents, judged
    # in the same pool as the connections' (no extra wait).
    if not named:
        found = _link_candidates(conn, task_id=task_id, walk_id=walk_id, programme=True)
        candidates = [
            pool_by_id[c.tss_id] for c in found.get(PROGRAMME_KEY, []) if c.tss_id in pool_by_id
        ]
        whole = programme_item_text(plan)
        for document in rerank(ranker, candidates, intent=whole, usage=usage)[:JUDGE_TOP_K]:
            jobs.append(_JudgeJob(PROGRAMME_KEY, document, whole, "", "", "", ""))

    def run_job(job: _JudgeJob) -> CallOutcome[Any]:
        return _call(
            "toc_judge",
            lambda: backend.judge(
                item_text=job.item_text,
                population=plan.target_population,
                place=place or "not stated",
                document_id=str(job.document.tss_id),
                title=job.document.title,
                year=job.document.year,
                text=job.document.text,
                neighbours=job.neighbours,
            ),
        )

    outcomes = _map_traced(run_job, jobs, JUDGE_WORKERS)

    stored = unverified = failed = 0
    started_by = context.context.get(TOC_STARTED_BY_KEY)
    find_more = context.context.get(TOC_CHECK_MODE_KEY) == "find_more"
    study_links = set(context.context.get(TOC_STUDIES_KEY) or {})
    carried = _user_decisions(
        conn, task_id, {job.link_key for job in jobs if job.link_key != PROGRAMME_KEY}
    )
    programme: list[dict[str, Any]] = []
    for job, outcome in zip(jobs, outcomes, strict=True):
        response = _outcome_value(outcome, usage)
        if response is None:
            failed += 1
            continue
        text = job.document.text
        support, quote = response.support, response.quote
        # A quote not in the text drops the answer to not_about (counted).
        if support != "not_about" and not quote_found(text, quote):
            unverified += 1
            support = "not_about"
        about = support != "not_about"
        if job.link_key == PROGRAMME_KEY:
            programme.append(
                {
                    "tss": str(job.document.tss_id),
                    "support": support,
                    "quote": quote if about else None,
                    "relevance": response.relevance if about else 0,
                    "relevance_reason": response.relevance_reason if about else None,
                    "robust_model": response.robust_model,
                }
            )
            continue
        # A case study only from a document about the step, with a quote in its text.
        case = response.case_study if about else None
        if case is not None and not quote_found(text, case.quote):
            case = None
        indicator = response.indicator
        # One box per judgement row: the case study's box wins; an indicator
        # naming the other end of the link is dropped.
        if case is not None and indicator is not None and indicator.box != case.box:
            indicator = None
        box_end = case.box if case is not None else (indicator.box if indicator else None)
        supports = support in ("strong", "weak")
        store.insert(
            conn,
            store.ChangeLog(),
            toc_item_evidence,
            {
                "evidence_id": uuid.uuid4(),
                "task_id": task_id,
                "link_id": uuid.UUID(job.link_key),
                "case_box_id": (
                    uuid.UUID(job.source_key if box_end == "source" else job.target_key)
                    if box_end
                    else None
                ),
                "task_source_snapshot_id": job.document.tss_id,
                "capability_run_id": walk_id,
                "support": support,
                "quote": quote if about else None,
                "relevance": response.relevance if about else 0,
                "relevance_reason": response.relevance_reason if about else None,
                "condition": response.condition if supports else None,
                "case_study": (
                    {
                        "programme": case.programme,
                        "place": case.place,
                        "note": case.note,
                        "quote": case.quote,
                    }
                    if case is not None
                    else None
                ),
                "indicator": indicator.text if indicator is not None else None,
                # Stored as the judge said it; it counts only when classify,
                # which now runs after the judge, also calls it a modelling study (C31).
                "robust_model": response.robust_model,
                "item_hash": job.item_hash,
                # A study the user added (C42) and their earlier decisions on this
                # document for this link, carried to the new wording (C43).
                "added_by": started_by if job.link_key in study_links else None,
                # What Find more evidence found waits for the user's Accept (C44); a
                # document not about the step changes nothing, so it does not wait.
                "status": "pending" if find_more and about else "counted",
                **carried.get((job.link_key, job.document.tss_id), {}),
            },
        )
        stored += 1

    # Every covered link now counts the judgements of its current wording (C19).
    # Find more evidence leaves that alone: what it found waits as pending (C44).
    log_ = store.ChangeLog()
    for key in link_keys if not find_more else []:
        row = rows.links[key]
        store.update(
            conn,
            log_,
            toc_link,
            row.link_id,
            observed_revision=row.revision,
            values={"counted_hash": hashes[key], "kept_hash": None, "kept_by": None},
        )
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_judge", log=log_)
    # Classify and appraise run after the judge, on what it found on topic (C31):
    # every other document is screened out here.
    on_topic = set(
        conn.execute(
            select(toc_item_evidence.c.task_source_snapshot_id)
            .where(toc_item_evidence.c.task_id == task_id)
            .where(toc_item_evidence.c.task_source_snapshot_id.in_(list(pool_by_id)))
            .where(toc_item_evidence.c.support != "not_about")
        ).scalars()
    )
    if programme:
        events.append(
            conn,
            task_id=task_id,
            run_id=run_id,
            event_type=PROGRAMME_EVENT,
            payload={"walk_id": str(walk_id), "judgements": programme},
        )
        # Kept for classify and appraise, which weigh them like any document.
        on_topic |= {uuid.UUID(j["tss"]) for j in programme if j["support"] != "not_about"}
    off_topic = set(pool_by_id) - on_topic
    if off_topic:
        screen_in(
            conn,
            task_id=task_id,
            run_id=run_id,
            context=ScreenContext(
                scope_id=context.scope_id, intent=context.intent, context=context.context
            ),
            tss_ids=off_topic,
            status="not_relevant",
            reason=NOT_ABOUT_REASON,
            rescreen=True,
        )
    summary = {
        "links": len(link_keys),
        "screened_out_not_about": len(off_topic),
        "links_left_out": left_out,
        "calls": len(jobs),
        "failed_calls": failed,
        "judgements": stored,
        "programme_judgements": len(programme),
        "unverified_dropped": unverified,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_judge.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary


def toc_search_again_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    ranker: RankingBackend | None = None,
    embedder: EmbeddingBackend | None = None,
) -> dict[str, Any]:
    """One more search for the links the judge left thin, then judge what it found (C44).

    The runner has already dispatched and joined one reformulated item search
    per link whose verdict was *Not enough evidence* after the judge (stage
    ``toc_retry_searches``): the same five calls, in the words of the research
    that would test the step, with the link's earlier queries ruled out. This
    step picks each such link's new documents, leaving out those already
    judged, and judges them; their judgements count like the first round's.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        ranker: The rerank backend, or ``None`` to keep order.
        embedder: The embedding backend for the shared pool, or ``None``.

    Returns:
        The links searched again, the select counts and the judge counts.
    """
    walk_id = walk_of_run(conn, task_id=task_id, run_id=run_id)
    retried = {
        link
        for child, link in _child_links(conn, task_id=task_id, walk_id=walk_id).items()
        if child in _retry_children(conn, task_id=task_id, walk_id=walk_id)
    }
    if not retried:
        return {"links": 0, "backend_mode": backend.mode}
    picked = toc_select_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=context,
        backend=backend,
        embedder=embedder,
        only=retried,
        exclude_judged=True,
    )
    judged = toc_judge_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=context,
        backend=backend,
        ranker=ranker,
        embedder=embedder,
        only=retried,
    )
    return {
        "links": len(retried),
        "backend_mode": backend.mode,
        **{f"select_{k}": v for k, v in picked.items() if k != "usage_totals"},
        **{k: v for k, v in judged.items() if k != "links"},
    }


def _retry_children(conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> set[uuid.UUID]:
    """The walk's reformulated item-search children (their context carries the earlier queries)."""
    rows = conn.execute(
        select(capability_run.c.capability_run_id)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.parent_capability_run_id == walk_id)
        .where(evidence_scope.c.context.has_key(TOC_REFORMULATE_KEY))
    ).scalars()
    return set(rows)
