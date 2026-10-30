"""The check walk's theory-of-change steps (task 054, step 1.4; C5, C6, C20).

``toc_select`` keeps every document the item searches found (C27: no model
call), the spine steps classify and appraise them, and five steps run in
order (W16):

- ``toc_discover``: batches of screened-in documents propose routes the
  theory lacks; a proposal whose route breaks a structure rule or whose
  passages are not in the documents is dropped. Insert-only.
- ``toc_merge``: one call joins pathways that share a mechanism and sets
  aside those that miss the intended change.
- ``toc_judge``: per link, its own search's documents (or, for a link with
  none, the *K* pool documents closest by meaning) read with one call each;
  its support, verified quote and relevance (C36). Insert-only, keyed by item hash.
- ``toc_choose``: within the 6 / 3 limits, conditions supports recorded,
  and the critical connection by the C6 rule.
- ``toc_summarise``: the header paragraphs and every sentence, each citation
  checked against what the item's judgements allow.

Each step has the scoping steps' shape, ``(conn, *, task_id, run_id,
context, backend)``, and writes through :mod:`~policy_atlas.theory_of_change.store`.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from itertools import zip_longest
from typing import Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection, Row

from policy_atlas.core import events, tracing
from policy_atlas.core.embeddings import (
    EMBEDDING_PROFILE,
    UNIT_POLICY,
    EmbeddingBackend,
    validate_vector,
)
from policy_atlas.core.schema import (
    capability_run,
    chunk,
    chunk_embedding,
    event_log,
    evidence_scope,
    runs,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
    task_source_snapshot,
    toc_box,
    toc_item_evidence,
    toc_link,
    toc_pathway,
    toc_pathway_link,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.assess.screen import ScreenContext, screen_in
from policy_atlas.evidence_search.corpus.characterise import screened_sources
from policy_atlas.evidence_search.corpus.ranking import (
    RERANK_BATCH_SIZE,
    RankingBackend,
    validate_ranked,
)
from policy_atlas.evidence_search.extract.quote_verify import QuoteMatcher, build_basis
from policy_atlas.evidence_search.sourcing.search_live import crossref_abstracts
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.model_calls import CallOutcome, call_with_retry
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    validate_plan,
)
from policy_atlas.runtime.toc_plan import (
    TOC_CHECK_MODE_KEY,
    TOC_LINK_CAP,
    TOC_LINKS_KEY,
    TOC_STARTED_BY_KEY,
    TOC_STUDIES_KEY,
)
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.discover_prompt import (
    CONSOLIDATE_MAX_NEW_FAILURE,
    CONSOLIDATE_MAX_NEW_SUCCESS,
    DISCOVER_BATCH_SIZE,
    ConsolidateResponse,
    NewLinkWire,
    ProposalWire,
)
from policy_atlas.theory_of_change.draft import plan_data, walk_toc_plan
from policy_atlas.theory_of_change.evidence.grade import (
    VERDICT_LABELS,
    VERDICT_ORDER,
    DocAppraisal,
    Judgement,
    LinkVerdict,
    link_verdict,
    quality,
    trusted_publisher,
)
from policy_atlas.theory_of_change.evidence.pick_prompt import PICK_N
from policy_atlas.theory_of_change.graph import (
    MAX_CONDITIONS_PER_LINK,
    MAX_FAILURE_PATHWAYS,
    MAX_SUCCESS_PATHWAYS,
    Graph,
    Link,
    item_hash,
    item_text,
    link_problem,
    trim_conditions,
)

log = structlog.get_logger()

#: Documents judged per link (C5): an item search keeps 10 (C27), so a link
#: with its own search skips the rerank.
JUDGE_TOP_K = 10

#: Pick calls in flight at once (C28).
PICK_WORKERS = 16

#: The link search's result lists, ``(backend, query origin)``, in turn order (C27).
LINK_LISTS: tuple[tuple[str, str], ...] = (
    ("openalex", "semantic"),
    ("openalex", "semantic_place"),
    ("overton", "verbatim"),
    ("openalex", "variant_sr"),
    ("openalex", "variant_rct"),
)

#: The reasons ``toc_select`` records on the documents it screens in and out (C27).
SELECTED_REASON = "selected_by_link_search"
NOT_SELECTED_REASON = "not_selected_by_link_search"

#: The reason ``toc_judge`` records on a document no link found on topic (C31).
NOT_ABOUT_REASON = "judged_not_about_any_step"

#: The event ``toc_select`` writes with each link's picked documents; the judge reads it (C31).
PICKED_EVENT = "toc_select.picked"

#: Discover batches in flight at once.
DISCOVER_WORKERS = 4

#: Judge calls in flight at once.
JUDGE_WORKERS = 16

#: Classify's evidence type for a modelling study (W15).
MODELLING_TYPE = "Modelling & Simulation"

#: The fixed sentence for a question no document spoke to (C20).
NO_EVIDENCE_SENTENCE = "No evidence was found in the documents read."

#: The fixed sentence that replaces a link sentence whose citations fail (C20).
UNSETTLED_SENTENCE = "The documents read do not settle this step."

#: The fixed box description that replaces one whose citations fail (C20).
BOX_FALLBACK_DESCRIPTION = "A step in the theory."


# --- shared reads ---------------------------------------------------------------


@dataclass(frozen=True)
class Document:
    """One screened-in document, as the ToC steps read it."""

    tss_id: uuid.UUID
    title: str
    year: int | None
    abstract: str
    evidence_type: str | None
    score: int | None

    @property
    def text(self) -> str:
        """The judged text: title and abstract (the abstract basis)."""
        return "\n".join(part for part in (self.title.strip(), self.abstract.strip()) if part)


def _year(metadata: dict[str, Any]) -> int | None:
    value = metadata.get("publication_year", metadata.get("year"))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def screened_documents(
    conn: Connection, *, task_id: uuid.UUID, scope_id: uuid.UUID
) -> list[Document]:
    """The walk's screened-in documents with their classification and appraisal."""
    return [
        Document(
            tss_id=source.tss_id,
            title=str(source.metadata.get("title") or ""),
            year=_year(source.metadata),
            abstract=str(source.metadata.get("abstract") or ""),
            evidence_type=source.primary_evidence_type,
            score=source.quality_score,
        )
        for source in screened_sources(conn, task_id=task_id, scope_id=scope_id)
    ]


def quote_found(text: str, quote: str | None) -> bool:
    """Whether a quote is in the text, by the shared quote matcher."""
    if not quote or not quote.strip():
        return False
    return QuoteMatcher(build_basis([(None, text)])).find(quote).status != "failed"


def walk_of_run(conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID) -> uuid.UUID:
    """The capability run (walk) a component run belongs to."""
    walk = conn.execute(
        select(runs.c.capability_run_id).where(runs.c.run_id == run_id, runs.c.task_id == task_id)
    ).scalar_one_or_none()
    if walk is None:
        raise ValueError(f"run {run_id} belongs to no walk")
    return uuid.UUID(str(walk))


def appraisals_for(
    conn: Connection, *, task_id: uuid.UUID, evidence_rows: Iterable[Row[Any]]
) -> dict[str, DocAppraisal]:
    """Each judged document's appraisal, read under the walk that judged it.

    Args:
        conn: Open connection.
        task_id: The task.
        evidence_rows: ``toc_item_evidence`` rows.

    Returns:
        Document id → appraisal; an unscored document has ``score=None``. A
        web page (``backend`` ``web``) is trusted when its address's host is
        on the trusted publisher list (C23).
    """
    pairs = {(row.capability_run_id, row.task_source_snapshot_id) for row in evidence_rows}
    if not pairs:
        return {}
    walks = {walk for walk, _ in pairs}
    scope_of = {
        row.capability_run_id: row.evidence_scope_id
        for row in conn.execute(
            select(capability_run.c.capability_run_id, capability_run.c.evidence_scope_id)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id.in_(walks))
        )
    }
    scopes = set(scope_of.values())
    tss_ids = {tss for _, tss in pairs}
    scores = {
        (row.evidence_scope_id, row.task_source_snapshot_id): row.quality_score
        for row in conn.execute(
            select(
                source_appraisal_result.c.evidence_scope_id,
                source_appraisal_result.c.task_source_snapshot_id,
                source_appraisal_result.c.quality_score,
            )
            .where(source_appraisal_result.c.task_id == task_id)
            .where(source_appraisal_result.c.evidence_scope_id.in_(scopes))
            .where(source_appraisal_result.c.task_source_snapshot_id.in_(tss_ids))
        )
    }
    types = {
        (row.evidence_scope_id, row.task_source_snapshot_id): row.primary_evidence_type
        for row in conn.execute(
            select(
                source_classification_result.c.evidence_scope_id,
                source_classification_result.c.task_source_snapshot_id,
                source_classification_result.c.primary_evidence_type,
            )
            .where(source_classification_result.c.task_id == task_id)
            .where(source_classification_result.c.evidence_scope_id.in_(scopes))
            .where(source_classification_result.c.task_source_snapshot_id.in_(tss_ids))
        )
    }
    web = {
        row.task_source_snapshot_id: trusted_publisher(row.source_locator)
        for row in conn.execute(
            select(task_source_snapshot.c.task_source_snapshot_id, source_snapshot.c.source_locator)
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(task_source_snapshot.c.task_source_snapshot_id.in_(tss_ids))
            .where(source_snapshot.c.metadata["backend"].astext == "web")
        )
    }
    out: dict[str, DocAppraisal] = {}
    for walk, tss in sorted(pairs, key=str):
        key = (scope_of.get(walk), tss)
        out[str(tss)] = DocAppraisal(
            score=scores.get(key),
            web=tss in web,
            modelling=types.get(key) == MODELLING_TYPE,
            trusted=web.get(tss, False),
        )
    return out


def counted_judgements(conn: Connection, *, task_id: uuid.UUID) -> dict[str, list[Row[Any]]]:
    """Each link's judgements that count: its counted hash (C19), accepted and not removed.

    A judgement the user removed from the link (C42), or one still pending or
    rejected (C44), does not count; the evidence list still shows it.
    """
    rows = conn.execute(
        select(toc_item_evidence)
        .join(
            toc_link,
            (toc_link.c.link_id == toc_item_evidence.c.link_id)
            & (toc_link.c.task_id == toc_item_evidence.c.task_id)
            & (toc_link.c.counted_hash == toc_item_evidence.c.item_hash),
        )
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.status == "counted")
        .where(toc_item_evidence.c.excluded_at.is_(None))
        .order_by(toc_item_evidence.c.created_at, toc_item_evidence.c.evidence_id)
    )
    out: dict[str, list[Row[Any]]] = {}
    for row in rows:
        out.setdefault(str(row.link_id), []).append(row)
    return out


def pending_judgements(conn: Connection, *, task_id: uuid.UUID) -> dict[str, list[Row[Any]]]:
    """Each link's new evidence waiting for the user's Accept (C44), for its current count."""
    rows = conn.execute(
        select(toc_item_evidence)
        .join(
            toc_link,
            (toc_link.c.link_id == toc_item_evidence.c.link_id)
            & (toc_link.c.task_id == toc_item_evidence.c.task_id)
            & (toc_link.c.counted_hash == toc_item_evidence.c.item_hash),
        )
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.status == "pending")
        .where(toc_item_evidence.c.excluded_at.is_(None))
        .order_by(toc_item_evidence.c.created_at, toc_item_evidence.c.evidence_id)
    )
    out: dict[str, list[Row[Any]]] = {}
    for row in rows:
        out.setdefault(str(row.link_id), []).append(row)
    return out


def row_judgement(row: Row[Any]) -> Judgement:
    """A ``toc_item_evidence`` row as the verdict reads it: the user's scores win (C42)."""
    support_override = getattr(row, "support_override", None)
    relevance_override = getattr(row, "relevance_override", None)
    return Judgement(
        document_id=str(row.task_source_snapshot_id),
        support=support_override or row.support,
        relevance=row.relevance if relevance_override is None else relevance_override,
        robust_model=row.robust_model,
    )


def link_verdict_of(rows: list[Row[Any]], appraisals: dict[str, DocAppraisal]) -> LinkVerdict:
    """One link's verdict from its counted judgements (C36)."""
    return link_verdict([row_judgement(row) for row in rows], appraisals)


def _current_hash(graph: Graph, key: str) -> str:
    link = graph.links[key]
    return item_hash(link, graph.boxes[link.source].text, graph.boxes[link.target].text)


def _kept_links_first(graph: Graph) -> list[str]:
    """Link keys: those on kept pathways first, in pathway order, then the rest.

    A link that sits only on set-aside pathways is left out (C29); a link on
    no pathway stays, after the rest.
    """
    ordered: list[str] = []
    set_aside: set[str] = set()
    for pathway in graph.pathways:
        if pathway.status == "kept":
            ordered.extend(key for key in pathway.links if key in graph.links)
        else:
            set_aside.update(pathway.links)
    on_kept = set(ordered)
    ordered.extend(key for key in graph.links if key not in set_aside or key in on_kept)
    return list(dict.fromkeys(ordered))


def links_to_check(graph: Graph, named: list[str] | None = None) -> tuple[list[str], int]:
    """The links a check walk covers, kept pathways first, capped at 80 (C5, C29).

    Links only on set-aside pathways are not checked, unless the user named them
    (Search for more).

    Args:
        graph: The theory.
        named: The links a named-link check covers, or ``None`` for all.

    Returns:
        ``(links, left_out)``.
    """
    if named is not None:
        wanted = set(named)
        ordered = [key for key in [*_kept_links_first(graph), *graph.links] if key in wanted]
        ordered = list(dict.fromkeys(ordered))
    else:
        ordered = _kept_links_first(graph)
    return ordered[:TOC_LINK_CAP], max(0, len(ordered) - TOC_LINK_CAP)


def item_search_intents(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    payload: Mapping[str, Any],
    links: list[str] | None = None,
) -> tuple[list[tuple[str, str]], int]:
    """The item searches a check walk dispatches: one per link, kept pathways first.

    Args:
        conn: Open connection.
        task_id: The task.
        payload: The walk's plan payload.
        links: The links a named-link check covers, or ``None`` for all.

    Returns:
        ``([(link_id, item_text)], left_out)`` under the 80-link cap (C5).
    """
    plan = expect_toc_plan(validate_plan(THEORY_OF_CHANGE, payload))
    graph, _ = store.load_graph(conn, task_id)
    keys, left_out = links_to_check(graph, links)
    intents = []
    for key in keys:
        link = graph.links[key]
        intents.append(
            (
                key,
                item_text(
                    link,
                    source_text=graph.boxes[link.source].text,
                    target_text=graph.boxes[link.target].text,
                    population=plan.target_population,
                    place=plan.where,
                ),
            )
        )
    return intents, left_out


def _flag_values(row: Row[Any], reason: str) -> dict[str, Any]:
    """The T1 flag columns for a change to user work, or nothing."""
    if row.user_edited or row.origin == "user":
        return {
            "pa_changed": True,
            "pa_change_reason": reason,
            "prior_version": store.row_state(row),
        }
    return {}


def _outcome_value[T](outcome: CallOutcome[T], usage: UsageAccumulator) -> T | None:
    for item in outcome.usages:
        usage.add(item)
    return outcome.value


def _map_traced[A, R](fn: Callable[[A], R], items: list[A], workers: int) -> list[R]:
    """Run ``fn`` over ``items`` in a thread pool, in order, each under the caller's context.

    The context carries the run's Langfuse trace and session (the task id), so
    every model call in the pool is traced under the task's session (C30).
    """
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [tracing.submit_with_context(executor, fn, item) for item in items]
        return [future.result() for future in futures]


def _call[T](name: str, call: Callable[[], Any], event: str) -> CallOutcome[T]:
    return call_with_retry(name, call, lambda response: response, event=event)


# --- discover -------------------------------------------------------------------


def _short_keys(graph: Graph) -> tuple[dict[str, str], dict[str, str]]:
    """Short prompt keys for boxes (``b1``) and links (``l1``), and the way back."""
    to_short = {key: f"b{i}" for i, key in enumerate(graph.boxes, start=1)}
    to_short.update({key: f"l{i}" for i, key in enumerate(graph.links, start=1)})
    return to_short, {short: key for key, short in to_short.items()}


def _theory_for_discover(graph: Graph, short: dict[str, str]) -> dict[str, object]:
    return {
        "boxes": [
            {"key": short[key], "layer": box.layer, "text": box.text}
            for key, box in graph.boxes.items()
        ],
        "links": [
            {"source": short[link.source], "target": short[link.target], "sentence": link.sentence}
            for link in graph.links.values()
        ],
        "pathways": [
            {
                "kind": pathway.kind,
                "route": _route(graph, pathway.links, short),
            }
            for pathway in graph.pathways
            if pathway.status == "kept"
        ],
    }


def _route(graph: Graph, link_keys: list[str], short: dict[str, str]) -> list[str]:
    steps = [graph.links[key] for key in link_keys if key in graph.links]
    if not steps:
        return []
    return [short[steps[0].source], *(short[step.target] for step in steps)]


def route_problem(
    kind: str,
    route: list[str],
    *,
    known: dict[str, str],
    pairs: set[tuple[str, str]],
    new_links: list[NewLinkWire],
) -> str | None:
    """Why a route cannot be written, or ``None``.

    Args:
        kind: ``success`` or ``failure``.
        route: Box keys in order.
        known: Every usable box key → layer (the theory's and the new ones).
        pairs: Existing links as ``(source, target)`` keys.
        new_links: The links the route adds.

    Returns:
        The problem, or ``None`` when the route passes.
    """
    if len(route) < 2 or any(key not in known for key in route):
        return "the route names unknown boxes"
    if len(set(route)) != len(route):
        return "the route visits a box twice"
    end = "impact" if kind == "success" else "failure_outcome"
    if known[route[0]] != "input" or known[route[-1]] != end:
        return f"the route does not run from an input to {end}"
    links = {(link.source, link.target): link for link in new_links}
    for source, target in zip(route, route[1:], strict=False):
        if (source, target) in pairs:
            continue
        if (source, target) not in links:
            return f"no link between {source} and {target}"
        reason = link_problem(known[source], known[target])
        if reason:
            return reason
    return None


def proposal_problem(
    proposal: ProposalWire,
    *,
    layers: dict[str, str],
    pairs: set[tuple[str, str]],
    documents: dict[str, Document],
) -> str | None:
    """Why a discover proposal cannot be used, or ``None``.

    Args:
        proposal: The proposal, keyed by short keys.
        layers: Existing short box key → layer.
        pairs: Existing links as ``(source, target)`` short keys.
        documents: The batch's documents by id.

    Returns:
        The problem, or ``None`` when the proposal passes.
    """
    new_layers = {box.key: box.layer for box in proposal.new_boxes}
    if set(new_layers) & set(layers):
        return "a new box reuses an existing key"
    problem = route_problem(
        proposal.kind,
        proposal.route,
        known={**layers, **new_layers},
        pairs=pairs,
        new_links=proposal.new_links,
    )
    if problem:
        return problem
    if set(new_layers) - set(proposal.route):
        return "a new box is not on the route"
    if not proposal.evidence:
        return "no evidence"
    for evidence in proposal.evidence:
        document = documents.get(evidence.document_id)
        if document is None or not quote_found(document.text, evidence.quote):
            return "a passage is not in its document"
    return None


def _candidate(proposal_id: str, proposal: ProposalWire) -> dict[str, object]:
    """A checked proposal as consolidate reads it; its new keys made unique (``q1n1``)."""

    def key(value: str) -> str:
        return f"{proposal_id}{value}" if value in new else value

    new = {box.key for box in proposal.new_boxes}
    return {
        "id": proposal_id,
        "kind": proposal.kind,
        "label": proposal.label,
        "route": [key(value) for value in proposal.route],
        "new_boxes": [
            {"key": key(box.key), "layer": box.layer, "text": box.text}
            for box in proposal.new_boxes
        ],
        "new_links": [
            {**link.model_dump(), "source": key(link.source), "target": key(link.target)}
            for link in proposal.new_links
        ],
        "documents": len({evidence.document_id for evidence in proposal.evidence}),
    }


def toc_discover_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Propose routes the screened-in documents describe and the theory lacks.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        Batch and proposal counts and the usage totals.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, _ = store.load_graph(conn, task_id)
    documents = screened_documents(conn, task_id=task_id, scope_id=context.scope_id)
    short, back = _short_keys(graph)
    theory = _theory_for_discover(graph, short)
    data = plan_data(plan)
    batches = [
        documents[i : i + DISCOVER_BATCH_SIZE]
        for i in range(0, len(documents), DISCOVER_BATCH_SIZE)
    ]

    def run_batch(batch: list[Document]) -> CallOutcome[Any]:
        payload: list[dict[str, object]] = [
            {"id": str(doc.tss_id), "title": doc.title, "year": doc.year, "abstract": doc.abstract}
            for doc in batch
        ]
        return _call(
            "toc_discover",
            lambda: backend.discover(plan=data, theory=theory, documents=payload),
            "toc_discover",
        )

    outcomes = _map_traced(run_batch, batches, DISCOVER_WORKERS)

    usage = UsageAccumulator()
    layers = {short[key]: box.layer for key, box in graph.boxes.items()}
    pairs = {(short[link.source], short[link.target]) for link in graph.links.values()}
    link_of_pair = {
        (short[link.source], short[link.target]): key for key, link in graph.links.items()
    }
    # Conditions already in the theory: a discovered link never repeats one.
    taken = [c for link in graph.links.values() for c in link.conditions]
    log_ = store.ChangeLog()
    changes: list[store.Change] = []
    accepted = rejected = failed_batches = 0
    # Every batch's checked proposals, held back: one consolidate call joins
    # the repeats and reuses boxes before anything is written (owner, 2026-10-27).
    candidates: list[dict[str, object]] = []
    for batch, outcome in zip(batches, outcomes, strict=True):
        response = _outcome_value(outcome, usage)
        if response is None:
            failed_batches += 1
            continue
        by_id = {str(doc.tss_id): doc for doc in batch}
        for proposal in response.proposals:
            problem = proposal_problem(proposal, layers=layers, pairs=pairs, documents=by_id)
            if problem:
                rejected += 1
                log.info("toc_discover.proposal_dropped", problem=problem)
                continue
            candidates.append(_candidate(f"q{len(candidates) + 1}", proposal))
    kept_kinds = [pathway.kind for pathway in graph.pathways if pathway.status == "kept"]
    limit = {
        "success": max(
            0,
            min(CONSOLIDATE_MAX_NEW_SUCCESS, MAX_SUCCESS_PATHWAYS - kept_kinds.count("success")),
        ),
        "failure": max(
            0,
            min(CONSOLIDATE_MAX_NEW_FAILURE, MAX_FAILURE_PATHWAYS - kept_kinds.count("failure")),
        ),
    }
    consolidated: ConsolidateResponse | None = None
    if candidates and any(limit.values()):
        consolidated = _outcome_value(
            _call(
                "toc_consolidate",
                lambda: backend.consolidate(
                    plan=data,
                    theory=theory,
                    proposals=candidates,
                    max_success=limit["success"],
                    max_failure=limit["failure"],
                ),
                "toc_consolidate",
            ),
            usage,
        )
    new_boxes = {box.key: box for box in consolidated.new_boxes} if consolidated else {}
    clash = set(new_boxes) & set(layers)
    ids = {str(candidate["id"]) for candidate in candidates}
    written: dict[str, str] = {}
    counts = {"success": 0, "failure": 0}
    for path in consolidated.pathways if consolidated else []:
        problem = (
            "a new box reuses an existing key"
            if clash & set(path.route)
            else "it joins no checked proposal"
            if not set(path.from_proposals) & ids
            else f"more than {limit[path.kind]} new {path.kind} pathways"
            if counts[path.kind] >= limit[path.kind]
            else route_problem(
                path.kind,
                path.route,
                known={**layers, **{key: box.layer for key, box in new_boxes.items()}},
                pairs=pairs,
                new_links=path.new_links,
            )
        )
        if problem:
            rejected += 1
            log.info("toc_discover.pathway_dropped", problem=problem)
            continue
        counts[path.kind] += 1
        accepted += 1
        # A new box is written once, the first time a kept route uses it.
        for key in path.route:
            if key not in new_boxes or key in written:
                continue
            box_id = uuid.uuid4()
            written[key] = f"b{len(layers) + 1}"
            layers[written[key]] = new_boxes[key].layer
            back[written[key]] = str(box_id)
            store.insert(
                conn,
                log_,
                toc_box,
                {
                    "box_id": box_id,
                    "task_id": task_id,
                    "layer": new_boxes[key].layer,
                    "text": new_boxes[key].text,
                    "result_criteria": {"definition": None, "timing": None},
                    "origin": "found_in_evidence",
                },
            )
        route = [written.get(key, key) for key in path.route]
        new_links = {
            (written.get(link.source, link.source), written.get(link.target, link.target)): link
            for link in path.new_links
        }
        link_ids: list[uuid.UUID] = []
        for source, target in zip(route, route[1:], strict=False):
            if (source, target) in link_of_pair:
                link_ids.append(uuid.UUID(link_of_pair[(source, target)]))
                continue
            wire = new_links[(source, target)]
            [conditions] = trim_conditions([list(wire.conditions)], existing=taken)
            taken.extend(conditions)
            link_id = uuid.uuid4()
            store.insert(
                conn,
                log_,
                toc_link,
                {
                    "link_id": link_id,
                    "task_id": task_id,
                    "source_box_id": uuid.UUID(back[source]),
                    "target_box_id": uuid.UUID(back[target]),
                    "sentence": wire.sentence,
                    "if_text": wire.if_text,
                    "for_text": wire.for_text,
                    "then_text": wire.then_text,
                    "because_text": wire.because_text,
                    "conditions": conditions,
                    "origin": "found_in_evidence",
                },
            )
            pairs.add((source, target))
            link_of_pair[(source, target)] = str(link_id)
            link_ids.append(link_id)
        pathway_id = uuid.uuid4()
        store.insert_pathway(
            conn,
            log_,
            task_id=task_id,
            pathway_id=pathway_id,
            kind=path.kind,
            label=path.label,
            link_ids=link_ids,
            origin="found_in_evidence",
        )
        changes.append(
            {
                "text": f"Added a {path.kind} pathway from the evidence: {path.label}.",
                "pathway_id": str(pathway_id),
            }
        )
    store.record(
        conn, task_id=task_id, run_id=run_id, step="toc_discover", log=log_, changes=changes
    )
    summary = {
        "documents": len(documents),
        "batches": len(batches),
        "failed_batches": failed_batches,
        "proposals": len(candidates),
        "accepted": accepted,
        "rejected": rejected,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info(
        "toc_discover.done",
        proposals=len(candidates),
        accepted=accepted,
        rejected=rejected,
        batches=len(batches),
    )
    return summary


# --- merge ----------------------------------------------------------------------


def _keep_one_of_each(order: list[str], kinds: dict[str, str], kept: set[str]) -> set[str]:
    """Keep back the first pathway of a kind the decisions left with none."""
    for kind in ("success", "failure"):
        if not any(kinds[key] == kind for key in kept):
            first = next((key for key in order if kinds[key] == kind), None)
            if first is not None:
                kept.add(first)
    return kept


#: Box origins that mean the user wrote the box (C29).
_USER_ORIGINS = frozenset({"user", "imported"})


def _user_written(row: Row[Any]) -> bool:
    return bool(row.user_edited) or row.origin in _USER_ORIGINS


def fold_problem(rows: store.GraphRows, box: str, into: str) -> str | None:
    """Why one box may not be folded into another, or ``None`` when it may (C29).

    Args:
        rows: The current graph rows.
        box: The box to fold away (row id as text).
        into: The box it would be folded into.

    Returns:
        The reason, or ``None``.
    """
    if box not in rows.boxes or into not in rows.boxes:
        return "a box does not exist"
    if box == into:
        return "it is the same box"
    if rows.boxes[box].layer != rows.boxes[into].layer:
        return "the boxes are in different layers"
    if _user_written(rows.boxes[box]) and not _user_written(rows.boxes[into]):
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
    if fold_problem(rows, box, into) is not None:
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
    response = _outcome_value(
        _call(
            "toc_merge",
            lambda: backend.merge(plan=plan_data(plan), boxes=boxes, pathways=payload),
            "toc_merge",
        ),
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
            changes.append(
                f"Merged box “{graph.boxes[box].text}” into “{graph.boxes[into].text}”"
            )
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


# --- select ---------------------------------------------------------------------


@dataclass(frozen=True)
class LinkCandidate:
    """One document a link's own search acquired, as the pick sees it.

    Attributes:
        tss_id: The document.
        source_list: The result list it came from, ``(backend, query origin)``.
        rank: Its pool rank; within one list, lower is earlier in that list.
        title: Its title.
        abstract: Its abstract, ``""`` when it has none.
        doi: Its DOI, when it has one.
        snapshot_id: The source snapshot its metadata lives on.
    """

    tss_id: uuid.UUID
    source_list: tuple[str, str]
    rank: int
    title: str = ""
    abstract: str = ""
    doi: str | None = None
    snapshot_id: uuid.UUID | None = None

    @property
    def has_abstract(self) -> bool:
        """Whether it has an abstract."""
        return bool(self.abstract.strip())


def select_for_link(candidates: list[LinkCandidate]) -> list[uuid.UUID]:
    """The round-robin rule: the pick call's top-up and its fallback (C27, C28).

    In turn from the result lists (:data:`LINK_LISTS` order) in rank order,
    :data:`PICK_N` documents. A document with no abstract is taken only when
    fewer than :data:`PICK_N` have one.

    Args:
        candidates: The link's documents.

    Returns:
        The picked documents, in pick order.
    """

    def order(source_list: tuple[str, str]) -> int:
        return LINK_LISTS.index(source_list) if source_list in LINK_LISTS else len(LINK_LISTS)

    def in_turn(pool: list[LinkCandidate]) -> list[uuid.UUID]:
        lists: dict[tuple[str, str], list[uuid.UUID]] = {}
        for c in sorted(pool, key=lambda c: (order(c.source_list), c.source_list, c.rank)):
            lists.setdefault(c.source_list, []).append(c.tss_id)
        return [tss for row in zip_longest(*lists.values()) for tss in row if tss is not None]

    with_abstract = in_turn([c for c in candidates if c.has_abstract])
    without = in_turn([c for c in candidates if not c.has_abstract])
    return (with_abstract + without)[:PICK_N]


def picked_ids(ids: list[str], candidates: list[LinkCandidate]) -> list[uuid.UUID]:
    """Map a pick answer's short ids (``d1``...) back, topped up by round-robin (C28).

    Unknown and repeated ids are dropped; a short answer is filled from
    :func:`select_for_link` in its order.

    Args:
        ids: The ids the pick call returned, most likely first.
        candidates: The link's documents; ``d1`` is the first.

    Returns:
        At most :data:`PICK_N` documents.
    """
    short = {f"d{i}": c.tss_id for i, c in enumerate(candidates, start=1)}
    chosen: list[uuid.UUID] = []
    for tss in [*(short[i] for i in ids if i in short), *select_for_link(candidates)]:
        if tss not in chosen:
            chosen.append(tss)
    return chosen[:PICK_N]


def _link_candidates(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> dict[str, list[LinkCandidate]]:
    """Link id → the documents its own search acquired, from acquire's events."""
    child_link = _child_links(conn, task_id=task_id, walk_id=walk_id)
    if not child_link:
        return {}
    found: dict[uuid.UUID, tuple[str, tuple[str, str], int]] = {}
    for row in conn.execute(
        select(event_log.c.payload, runs.c.capability_run_id)
        .select_from(
            event_log.join(
                runs,
                (runs.c.run_id == event_log.c.run_id) & (runs.c.task_id == event_log.c.task_id),
            )
        )
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type == "source.acquired")
        .where(runs.c.capability_run_id.in_(list(child_link)))
    ):
        payload = row.payload
        found[uuid.UUID(payload["task_source_snapshot_id"])] = (
            child_link[row.capability_run_id],
            (str(payload["backend"]), str(payload["query_origin"])),
            int(payload["pool_rank"]),
        )
    if not found:
        return {}
    meta = {
        row.task_source_snapshot_id: (row.source_snapshot_id, row.metadata or {})
        for row in conn.execute(
            select(
                task_source_snapshot.c.task_source_snapshot_id,
                source_snapshot.c.source_snapshot_id,
                source_snapshot.c.metadata,
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(task_source_snapshot.c.task_source_snapshot_id.in_(list(found)))
        )
    }
    out: dict[str, list[LinkCandidate]] = {}
    for tss, (link_id, source_list, rank) in found.items():
        snapshot_id, metadata = meta.get(tss, (None, {}))
        out.setdefault(link_id, []).append(
            LinkCandidate(
                tss,
                source_list,
                rank,
                title=str(metadata.get("title") or ""),
                abstract=str(metadata.get("abstract") or ""),
                doi=metadata.get("doi") or None,
                snapshot_id=snapshot_id,
            )
        )
    for docs in out.values():
        docs.sort(key=lambda c: (c.source_list, c.rank))
    return out


def _fill_abstracts(
    conn: Connection, candidates: dict[str, list[LinkCandidate]]
) -> dict[str, list[LinkCandidate]]:
    """Store Crossref abstracts on the snapshots of candidates that lack one (C30).

    The abstract goes on the snapshot's metadata with ``abstract_source``
    ``crossref``, so the pick, classify, appraise and the judge all read it.

    Returns:
        The candidates, with the found abstracts filled in.
    """
    wanted = {
        c.doi
        for docs in candidates.values()
        for c in docs
        if not c.has_abstract and c.doi and c.snapshot_id
    }
    found = crossref_abstracts(sorted(wanted))
    if not found:
        return candidates
    stored: set[uuid.UUID] = set()
    out: dict[str, list[LinkCandidate]] = {}
    for link_id, docs in candidates.items():
        filled = []
        for c in docs:
            text = found.get(c.doi or "") if not c.has_abstract else None
            if text and c.snapshot_id is not None:
                if c.snapshot_id not in stored:
                    conn.execute(
                        source_snapshot.update()
                        .where(source_snapshot.c.source_snapshot_id == c.snapshot_id)
                        .values(
                            metadata=source_snapshot.c.metadata.op("||")(
                                {"abstract": text, "abstract_source": "crossref"}
                            )
                        )
                    )
                    stored.add(c.snapshot_id)
                c = LinkCandidate(**{**c.__dict__, "abstract": text})
            filled.append(c)
        out[link_id] = filled
    return out


def toc_select_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    embedder: EmbeddingBackend | None = None,
) -> dict[str, Any]:
    """Pick each link's documents and write the screen's rows (C27, C28, C31).

    No screen model call: each link search already searched its own sentence
    by meaning. One small pick call per link (in parallel) chooses the
    :data:`PICK_N` documents most likely to test the step; a short answer is
    topped up, and a failed call replaced, by :func:`select_for_link`. Each
    link chooses from its own search's documents plus the :data:`PICK_N`
    documents of the whole walk's searches closest by meaning to its item text
    (C31), so a study one link's search found can serve another link. A link
    with no more than :data:`PICK_N` documents to choose from keeps them all,
    with no call. The picks are written as one ``toc_select.picked`` event,
    which the judge reads.
    Picked documents are screened in, the rest screened out; the rows are the
    screen's own, so classify, appraise and the later steps read them
    unchanged. A live backend first fills missing abstracts from Crossref.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        embedder: The embedding backend for the shared pool, or ``None``.

    Returns:
        Screen counts, pick call counts and the pick usage.
    """
    return _select_links(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=context,
        backend=backend,
        embedder=embedder,
        only=None,
    )


def _select_links(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    embedder: EmbeddingBackend | None,
    only: set[str] | None,
) -> dict[str, Any]:
    """Pick documents for the walk's links, or for the ``only`` links (C28, C31, C32).

    With ``only``, the other links' picks are kept and merged into the new
    picks event, and a picked document already screened out is screened in
    again at the next screen generation.
    """
    walk_id = walk_of_run(conn, task_id=task_id, run_id=run_id)
    candidates = _link_candidates(conn, task_id=task_id, walk_id=walk_id)
    targets = set(candidates) if only is None else only & set(candidates)
    # A named check (C40): studies the user added are picked as given (C42); Check
    # again also re-judges the documents already judged for the link (C43).
    studies = (
        _studies_by_link(conn, task_id, context.context.get(TOC_STUDIES_KEY) or {})
        if only is None
        else {}
    )
    again = (
        _judged_documents(conn, task_id, context.context.get(TOC_LINKS_KEY) or [])
        if only is None and context.context.get(TOC_CHECK_MODE_KEY) == "check_again"
        else {}
    )
    for key in [*studies, *again]:
        candidates.setdefault(key, [])
        targets.add(key)
    # Find more evidence (C44): the documents already judged for a link make way for new ones.
    if only is None and context.context.get(TOC_CHECK_MODE_KEY) == "find_more":
        judged = _judged_documents(conn, task_id, sorted(targets))
        for key in targets:
            seen = set(judged.get(key, []))
            candidates[key] = [c for c in candidates[key] if c.tss_id not in seen]
    if backend.mode == "live":
        candidates.update(_fill_abstracts(conn, {k: candidates[k] for k in targets}))
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, _ = store.load_graph(conn, task_id)
    texts: dict[str, str] = {}
    for key in targets:
        link = graph.links.get(key)
        if link is not None:
            texts[key] = item_text(
                link,
                source_text=graph.boxes[link.source].text,
                target_text=graph.boxes[link.target].text,
                population=plan.target_population,
                place=plan.where,
            )
    already: dict[str, set[uuid.UUID]] = (
        {k: set(v) for k, v in _judged_documents(conn, task_id, sorted(texts)).items()}
        if only is None and context.context.get(TOC_CHECK_MODE_KEY) == "find_more"
        else {}
    )
    # The shared pool (C31): the walk's other documents closest to each link.
    walk_pool = list({c.tss_id: c for docs in candidates.values() for c in docs}.values())
    vectors = _document_vectors(conn, [c.tss_id for c in walk_pool]) if texts else {}
    shared = 0
    for key in list(texts):
        own = candidates[key]
        mine = {c.tss_id for c in own}
        others = [c for c in walk_pool if c.tss_id not in mine]
        extra = [
            c
            for c in nearest(embedder, others, vectors, text=texts[key])
            if c.tss_id not in already.get(key, set())
        ]
        shared += len(extra)
        candidates[key] = [*own, *extra]
    called = [k for k in texts if len(candidates[k]) > PICK_N]

    def run_pick(key: str) -> CallOutcome[Any]:
        shown: list[dict[str, object]] = [
            {"id": f"d{i}", "title": c.title, "abstract": c.abstract}
            for i, c in enumerate(candidates[key], start=1)
        ]
        return _call(
            "toc_pick",
            lambda: backend.pick(item_text=texts[key], candidates=shown),
            "toc_pick",
        )

    outcomes = dict(zip(called, _map_traced(run_pick, called, PICK_WORKERS), strict=True))
    usage = UsageAccumulator()
    failed = 0
    per_link: dict[str, list[uuid.UUID]] = {}
    for key in targets:
        docs = candidates[key]
        response = _outcome_value(outcomes[key], usage) if key in outcomes else None
        if key in outcomes and response is None:
            failed += 1
        per_link[key] = (
            picked_ids(response.ids, docs) if response is not None else select_for_link(docs)
        )
        if key in studies:
            per_link[key] = studies[key]
        elif key in again:
            per_link[key] = list(dict.fromkeys([*again[key], *per_link[key]]))
    picked = {tss for chosen in per_link.values() for tss in chosen}
    if only is None or per_link:
        earlier = (
            _walk_picks(conn, task_id=task_id, walk_id=walk_id) if only is not None else None
        ) or {}
        events.append(
            conn,
            task_id=task_id,
            run_id=run_id,
            event_type=PICKED_EVENT,
            payload={
                **{key: sorted(str(tss) for tss in chosen) for key, chosen in earlier.items()},
                **{key: [str(tss) for tss in chosen] for key, chosen in per_link.items()},
            },
        )
    everything = {c.tss_id for key in targets for c in candidates[key]}
    screen = ScreenContext(
        scope_id=context.scope_id, intent=context.intent, context=context.context
    )
    kept = screen_in(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=screen,
        tss_ids=picked,
        status="relevant",
        reason=SELECTED_REASON,
        rescreen=only is not None,
    )
    dropped = screen_in(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=screen,
        tss_ids=everything - picked,
        status="not_relevant",
        reason=NOT_SELECTED_REASON,
    )
    return {
        "screened": kept["screened"] + dropped["screened"],
        "relevant": kept["relevant"],
        "not_relevant": dropped["not_relevant"],
        "excluded_retracted": kept["excluded_retracted"] + dropped["excluded_retracted"],
        "pick_calls": len(called),
        "failed_pick_calls": failed,
        "links": len(targets),
        "shared_candidates": shared,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }


def _studies_by_link(
    conn: Connection, task_id: uuid.UUID, dois_by_link: dict[str, list[str]]
) -> dict[str, list[uuid.UUID]]:
    """The task's documents for the DOIs the user added to each link (C42).

    The link's search has acquired them, or found them already in the task.
    """
    if not dois_by_link:
        return {}
    wanted = {
        doi.lower().removeprefix("https://doi.org/")
        for dois in dois_by_link.values()
        for doi in dois
    }
    found: dict[str, uuid.UUID] = {}
    for tss_id, metadata in conn.execute(
        select(task_source_snapshot.c.task_source_snapshot_id, source_snapshot.c.metadata)
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
        .where(task_source_snapshot.c.task_id == task_id)
    ):
        doi = str((metadata or {}).get("doi") or "").lower().removeprefix("https://doi.org/")
        if doi in wanted:
            found.setdefault(doi, tss_id)
    return {
        key: [
            found[d]
            for d in (doi.lower().removeprefix("https://doi.org/") for doi in dois)
            if d in found
        ]
        for key, dois in dois_by_link.items()
    }


#: The user's decisions on a judged document that carry to a new wording (C43).
_CARRIED = (
    "excluded_by",
    "excluded_at",
    "support_override",
    "relevance_override",
    "override_by",
    "override_at",
    "added_by",
)


def _user_decisions(
    conn: Connection, task_id: uuid.UUID, link_keys: set[str]
) -> dict[tuple[str, uuid.UUID], dict[str, Any]]:
    """(link, document) → the user's latest removal, scores or addition, from earlier wordings."""
    out: dict[tuple[str, uuid.UUID], dict[str, Any]] = {}
    if not link_keys:
        return out
    for row in conn.execute(
        select(toc_item_evidence)
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.link_id.in_([uuid.UUID(key) for key in link_keys]))
        .order_by(toc_item_evidence.c.created_at)
    ):
        decided = {name: getattr(row, name) for name in _CARRIED if getattr(row, name) is not None}
        if decided:
            out[(str(row.link_id), row.task_source_snapshot_id)] = decided
    return out


def _judged_documents(
    conn: Connection, task_id: uuid.UUID, link_ids: list[str]
) -> dict[str, list[uuid.UUID]]:
    """The documents already judged for each link, any wording, not removed (C43)."""
    out: dict[str, list[uuid.UUID]] = {}
    if not link_ids:
        return out
    for link_id, tss_id in conn.execute(
        select(toc_item_evidence.c.link_id, toc_item_evidence.c.task_source_snapshot_id)
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.link_id.in_([uuid.UUID(key) for key in link_ids]))
        .where(toc_item_evidence.c.excluded_at.is_(None))
        .where(toc_item_evidence.c.status != "rejected")
        .order_by(toc_item_evidence.c.created_at)
    ):
        chosen = out.setdefault(str(link_id), [])
        if tss_id not in chosen:
            chosen.append(tss_id)
    return out


def links_without_search(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> list[str]:
    """The kept links that have no item search of their own in this walk (C32).

    After merge, these are the links discovery added. Kept-pathway links
    first, as :func:`links_to_check` orders them.

    Args:
        conn: Open connection.
        task_id: The task.
        walk_id: The check walk.

    Returns:
        Link ids.
    """
    graph, _ = store.load_graph(conn, task_id)
    searched = set(_child_links(conn, task_id=task_id, walk_id=walk_id).values())
    keys, _ = links_to_check(graph)
    return [key for key in keys if key not in searched]


def toc_search_new_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    embedder: EmbeddingBackend | None = None,
) -> dict[str, Any]:
    """Pick documents for the links discovery added, after their own searches (C32).

    The runner has already dispatched and joined one item search per kept
    link with no search of its own (stage ``toc_new_link_searches``). Each such
    link is then picked for exactly as :func:`toc_select_scope` picks: its own
    documents plus the 10 nearest from the whole walk, one pick call, the
    round-robin fallback. A link whose search failed or found nothing has no
    picks, and the judge falls back to the nearest pool documents.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        embedder: The embedding backend for the shared pool, or ``None``.

    Returns:
        The same counts as :func:`toc_select_scope`.
    """
    walk_id = walk_of_run(conn, task_id=task_id, run_id=run_id)
    picks = _walk_picks(conn, task_id=task_id, walk_id=walk_id) or {}
    new = set(_child_links(conn, task_id=task_id, walk_id=walk_id).values()) - set(picks)
    return _select_links(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=context,
        backend=backend,
        embedder=embedder,
        only=new,
    )


# --- judge ----------------------------------------------------------------------


def _child_links(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    """Item-search child walk id → the link it searched, for this walk."""
    children = conn.execute(
        select(capability_run.c.capability_run_id, evidence_scope.c.context)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.parent_capability_run_id == walk_id)
    ).all()
    return {
        child.capability_run_id: str(link_id)
        for child in children
        if (link_id := (child.context or {}).get("link_id"))
    }


def _own_search_documents(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> dict[str, set[uuid.UUID]]:
    """Link id → documents its own item search acquired in this walk.

    A link absent from the map had no search of its own.
    """
    child_link = _child_links(conn, task_id=task_id, walk_id=walk_id)
    out: dict[str, set[uuid.UUID]] = {link_id: set() for link_id in child_link.values()}
    if not child_link:
        return out
    # ponytail: a document two searches both found is filed under the first
    # one's run only (acquire dedupes in the task); read search results per run
    # if links start missing shared documents.
    for row in conn.execute(
        select(task_source_snapshot.c.task_source_snapshot_id, runs.c.capability_run_id)
        .select_from(
            task_source_snapshot.join(
                runs,
                (runs.c.run_id == task_source_snapshot.c.run_id)
                & (runs.c.task_id == task_source_snapshot.c.task_id),
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .where(runs.c.capability_run_id.in_(list(child_link)))
    ):
        out[child_link[row.capability_run_id]].add(row.task_source_snapshot_id)
    return out


def _walk_picks(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> dict[str, set[uuid.UUID]] | None:
    """Link id → the documents ``toc_select`` picked for it in this walk, or ``None``.

    ``None`` for a walk from before C31, whose judge reads each link's own
    search's documents instead.
    """
    payload = conn.execute(
        select(event_log.c.payload)
        .select_from(
            event_log.join(
                runs,
                (runs.c.run_id == event_log.c.run_id) & (runs.c.task_id == event_log.c.task_id),
            )
        )
        .where(event_log.c.task_id == task_id)
        .where(runs.c.capability_run_id == walk_id)
        .where(event_log.c.event_type == PICKED_EVENT)
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).scalar_one_or_none()
    if payload is None:
        return None
    return {key: {uuid.UUID(tss) for tss in ids} for key, ids in payload.items()}


def rerank(
    ranker: RankingBackend | None,
    candidates: list[Document],
    *,
    intent: str,
    usage: UsageAccumulator,
) -> list[Document]:
    """Order candidates by the rerank backend against the item text.

    ``None`` (the harness default with no ranking backend) or a failed batch
    keeps the candidates' own order.
    """
    if ranker is None or len(candidates) <= JUDGE_TOP_K:
        return candidates
    scores: dict[str, int] = {}
    for start in range(0, len(candidates), RERANK_BATCH_SIZE):
        batch = candidates[start : start + RERANK_BATCH_SIZE]
        try:
            ranked, call_usage = ranker.rank(
                [
                    {"id": str(doc.tss_id), "title": doc.title, "abstract": doc.abstract}
                    for doc in batch
                ],
                intent=intent,
            )
        except Exception as exc:  # noqa: BLE001 - a failed rerank keeps the order
            log.warning("toc_judge.rerank_failed", error_type=type(exc).__name__)
            continue
        usage.add(call_usage)
        try:
            valid = validate_ranked({str(doc.tss_id) for doc in batch}, ranked)
        except ValueError:
            continue
        scores.update({doc_id: item["score"] for doc_id, item in valid.items()})
    position = {doc.tss_id: i for i, doc in enumerate(candidates)}
    return sorted(
        candidates, key=lambda doc: (-scores.get(str(doc.tss_id), -1), position[doc.tss_id])
    )


def _document_vectors(
    conn: Connection, tss_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[list[float]]]:
    """The embedding vectors acquire stored for each document's text, by document."""
    out: dict[uuid.UUID, list[list[float]]] = {}
    for row in conn.execute(
        select(task_source_snapshot.c.task_source_snapshot_id, chunk_embedding.c.vector)
        .select_from(
            chunk_embedding.join(chunk, chunk.c.chunk_id == chunk_embedding.c.chunk_id).join(
                task_source_snapshot,
                task_source_snapshot.c.source_snapshot_id == chunk.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(list(tss_ids)))
        .where(chunk_embedding.c.embedding_profile == EMBEDDING_PROFILE)
        .where(chunk_embedding.c.unit_policy == UNIT_POLICY)
    ):
        out.setdefault(row.task_source_snapshot_id, []).append(validate_vector(row.vector))
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    norms = math.sqrt(math.sumprod(a, a)) * math.sqrt(math.sumprod(b, b))
    return math.sumprod(a, b) / norms if norms else 0.0


class _HasId(Protocol):
    @property
    def tss_id(self) -> uuid.UUID: ...


def nearest[D: _HasId](
    embedder: EmbeddingBackend | None,
    candidates: list[D],
    vectors: Mapping[uuid.UUID, list[list[float]]],
    *,
    text: str,
) -> list[D]:
    """The :data:`JUDGE_TOP_K` candidates closest by meaning to the item text (C27).

    For a link with no search of its own. A document's closeness is its
    best-matching stored embedding unit; a document with no embedding ranks
    last. With no embedder, or a failed query embedding, the candidates keep
    their own order.

    Args:
        embedder: The embedding backend, or ``None``.
        candidates: The pool documents not yet judged for this link.
        vectors: Stored vectors by document (:func:`_document_vectors`).
        text: The link's item text.

    Returns:
        At most :data:`JUDGE_TOP_K` documents, closest first.
    """
    if embedder is None or len(candidates) <= JUDGE_TOP_K:
        return candidates[:JUDGE_TOP_K]
    try:
        query = validate_vector(embedder.embed_texts([text], kind="query")[0])
    except Exception as exc:  # noqa: BLE001 - a failed embedding keeps the order
        log.warning("toc_judge.embed_failed", error_type=type(exc).__name__)
        return candidates[:JUDGE_TOP_K]

    def closeness(doc: D) -> float:
        return max((_cosine(query, v) for v in vectors.get(doc.tss_id, [])), default=-2.0)

    return sorted(candidates, key=closeness, reverse=True)[:JUDGE_TOP_K]


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
    pool = screened_documents(conn, task_id=task_id, scope_id=context.scope_id)
    pool_by_id = {doc.tss_id: doc for doc in pool}
    # Each link reads what toc_select picked for it (C31); older walks, its own search's.
    own = _walk_picks(conn, task_id=task_id, walk_id=walk_id) or _own_search_documents(
        conn, task_id=task_id, walk_id=walk_id
    )
    vectors: dict[uuid.UUID, list[list[float]]] | None = None  # read once, when needed
    usage = UsageAccumulator()
    place = plan.where
    jobs: list[_JudgeJob] = []
    for key in link_keys:
        link = graph.links[key]
        source, target = graph.boxes[link.source], graph.boxes[link.target]
        current = item_hash(link, source.text, target.text)
        text = item_text(
            link,
            source_text=source.text,
            target_text=target.text,
            population=plan.target_population,
            place=place,
        )
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
            chosen = rerank(ranker, candidates, intent=text, usage=usage)[:JUDGE_TOP_K]
        else:
            # Added by discovery after the fan-out: the closest pool documents.
            if vectors is None:
                vectors = _document_vectors(conn, pool_by_id)
            candidates = [doc for doc in pool if doc.tss_id not in judged]
            chosen = nearest(embedder, candidates, vectors, text=text)
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
            "toc_judge",
        )

    outcomes = _map_traced(run_job, jobs, JUDGE_WORKERS)

    stored = unverified = failed = 0
    started_by = context.context.get(TOC_STARTED_BY_KEY)
    find_more = context.context.get(TOC_CHECK_MODE_KEY) == "find_more"
    study_links = set(context.context.get(TOC_STUDIES_KEY) or {})
    carried = _user_decisions(conn, task_id, {job.link_key for job in jobs})
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
                # What Find more evidence found waits for the user's Accept (C44).
                "status": "pending" if find_more else "counted",
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
            values={"counted_hash": _current_hash(graph, key), "kept_hash": None, "kept_by": None},
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
        "unverified_dropped": unverified,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_judge.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary


# --- choose ---------------------------------------------------------------------


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def critical_link(graph: Graph, verdicts: Mapping[str, LinkVerdict]) -> str | None:
    """The critical connection by the C6 rule, on verdicts (C36).

    The weakest important step on a success pathway: among links on kept
    success pathways, the one with the lowest verdict; ties go to the link on
    the most kept pathways, then the earlier one in pathway order.

    Args:
        graph: The theory, with current pathway statuses.
        verdicts: Link key → its verdict; a link without one counts as too
            little evidence.

    Returns:
        The link key, or ``None`` when no kept success pathway has a link.
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

    return min(order, key=lambda key: (rank(key), -on[key], order.index(key)))


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
    not_models = {
        str(row.task_source_snapshot_id)
        for group in counted.values()
        for row in group
        if row.robust_model
        and not getattr(appraisals.get(str(row.task_source_snapshot_id)), "modelling", False)
    }
    if not_models:
        # The judge called these robust models, but classify did not call them
        # modelling studies: they count by their score, not as a model (C31).
        log.info("toc_choose.robust_not_modelling", documents=len(not_models))
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
        response = _outcome_value(
            _call(
                "toc_choose",
                lambda: backend.choose(
                    plan=plan_data(plan),
                    pathways=payload,
                    recorded_conditions=recorded,
                    max_success=MAX_SUCCESS_PATHWAYS,
                    max_failure=MAX_FAILURE_PATHWAYS,
                ),
                "toc_choose",
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
        new_link = Link(**{**link.__dict__, "conditions": new_conditions})
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
    if choice is None or (marked and str(marked[0].link_id) == choice):
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
    row = current[choice]
    if store.update(
        conn, log_, toc_link, row.link_id, observed_revision=row.revision, values={"critical": True}
    ):
        changes.append(f"The critical connection is now “{row.sentence}”.")
        return True
    return False


# --- summarise ------------------------------------------------------------------


def check_citations(cites: Iterable[str], allowed: set[str]) -> bool:
    """Whether every cited document is one the item may cite (C20)."""
    return set(cites) <= allowed


def toc_summarise_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Write each link's title and evidence sentence and each box's texts (C20).

    Every citation is checked; a sentence that fails is replaced with a fixed
    one, and a "seen in" note that fails is dropped. The texts are written on
    the rows, with the documents each cites. The theory's title, summary and
    narrative are the report's (``toc_report``).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        The count of replaced texts and the usage.

    Raises:
        RuntimeError: If the summary call failed twice.
    """
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    graph, rows = store.load_graph(conn, task_id)
    counted = counted_judgements(conn, task_id=task_id)
    every = [row for group in counted.values() for row in group]
    appraisals = appraisals_for(conn, task_id=task_id, evidence_rows=every)
    titles = _titles(conn, task_id=task_id, tss_ids={row.task_source_snapshot_id for row in every})
    short, back = _short_keys(graph)
    theory = _theory_for_summary(graph, rows, counted, appraisals, titles, short)
    usage = UsageAccumulator()
    response = _outcome_value(
        _call(
            "toc_summarise",
            lambda: backend.summarise(plan=plan_data(plan), theory=theory),
            "toc_summarise",
        ),
        usage,
    )
    if response is None:
        raise RuntimeError("toc_summarise: the summary call failed")

    allowed = {
        key: {
            str(r.task_source_snapshot_id)
            for r in counted.get(key, [])
            if row_judgement(r).support != "not_about"
        }
        for key in graph.links
    }
    answered = {back.get(item.link): item for item in response.links}
    replaced = 0
    log_ = store.ChangeLog()
    for key, row in rows.links.items():
        item = answered.get(key)
        cites: list[str] = []
        if not allowed[key]:
            sentence = NO_EVIDENCE_SENTENCE
        elif (
            item is not None
            and item.sentence
            and item.sentence.strip()
            and check_citations(item.cites, allowed[key])
        ):
            sentence = item.sentence.strip()
            cites = list(dict.fromkeys(item.cites))
        else:
            replaced += 1
            sentence = UNSETTLED_SENTENCE
        title = item.title.strip() if item is not None and item.title.strip() else None
        store.update(
            conn,
            log_,
            toc_link,
            row.link_id,
            observed_revision=row.revision,
            values={"title": title, "evidence_sentence": sentence, "evidence_cites": cites},
        )
    case_docs: dict[str, set[str]] = {}
    for row in every:
        if row.case_box_id is not None and row.case_study is not None:
            case_docs.setdefault(str(row.case_box_id), set()).add(str(row.task_source_snapshot_id))
    described = {back.get(item.box): item for item in response.boxes}
    for key, row in rows.boxes.items():
        item = described.get(key)
        if item is not None and item.description.strip():
            description = item.description.strip()
        else:
            replaced += 1
            description = BOX_FALLBACK_DESCRIPTION
        # "Seen in" stands only when the box has case studies and it cites only them.
        seen_in: str | None = None
        seen_cites: list[str] = []
        if item is not None and item.seen_in and item.seen_in.strip():
            docs = case_docs.get(key, set())
            if docs and check_citations(item.cites, docs):
                seen_in, seen_cites = item.seen_in.strip(), list(dict.fromkeys(item.cites))
            else:
                replaced += 1
        store.update(
            conn,
            log_,
            toc_box,
            row.box_id,
            observed_revision=row.revision,
            values={"description": description, "seen_in": seen_in, "seen_in_cites": seen_cites},
        )
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_summarise", log=log_)
    summary = {
        "replaced": replaced,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_summarise.done", replaced=replaced)
    return summary


#: Case studies shown per box, after de-duplication (read time).
CASE_STUDIES_PER_BOX = 5


def top_case_studies[T](
    candidates: Iterable[tuple[T, str, str | None, int, bool]],
) -> list[T]:
    """One box's case studies to show, best first (read time).

    Ranks by the document's quality Q (C36), then supporting documents before
    others, then the given order; keeps the first of each programme and place
    (case and spacing ignored) and at most :data:`CASE_STUDIES_PER_BOX`.

    Args:
        candidates: ``(item, programme, place, quality, supports)`` per case
            study, in their existing order.

    Returns:
        The kept items.
    """
    ranked = sorted(enumerate(candidates), key=lambda p: (-p[1][3], not p[1][4], p[0]))
    seen: set[tuple[str, str]] = set()
    kept: list[T] = []
    for _, (item, programme, place, _score, _supports) in ranked:
        key = (_norm(programme), _norm(place or ""))
        if key in seen:
            continue
        seen.add(key)
        kept.append(item)
        if len(kept) == CASE_STUDIES_PER_BOX:
            break
    return kept


def row_case_score(row: Row[Any], appraisal: DocAppraisal | None) -> tuple[int, bool]:
    """A judgement row's ``(quality, supports)`` for :func:`top_case_studies`."""
    return quality(appraisal, row.robust_model), row_judgement(row).support in ("strong", "weak")


def _titles(
    conn: Connection, *, task_id: uuid.UUID, tss_ids: set[uuid.UUID]
) -> dict[str, tuple[str, int | None]]:
    if not tss_ids:
        return {}
    return {
        str(row.task_source_snapshot_id): (
            str((row.metadata or {}).get("title") or ""),
            _year(row.metadata or {}),
        )
        for row in conn.execute(
            select(task_source_snapshot.c.task_source_snapshot_id, source_snapshot.c.metadata)
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(task_source_snapshot.c.task_source_snapshot_id.in_(tss_ids))
        )
    }


def _theory_for_summary(
    graph: Graph,
    rows: store.GraphRows,
    counted: dict[str, list[Row[Any]]],
    appraisals: dict[str, DocAppraisal],
    titles: dict[str, tuple[str, int | None]],
    short: dict[str, str],
) -> dict[str, object]:
    candidates: dict[str, list[tuple[dict[str, object], str, str | None, int, bool]]] = {}
    for group in counted.values():
        for row in group:
            if row.case_box_id is not None and row.case_study is not None:
                case = row.case_study
                score, supports = row_case_score(
                    row, appraisals.get(str(row.task_source_snapshot_id))
                )
                candidates.setdefault(str(row.case_box_id), []).append(
                    (
                        {"document_id": str(row.task_source_snapshot_id), **case},
                        str(case.get("programme") or ""),
                        case.get("place"),
                        score,
                        supports,
                    )
                )
    case_studies = {box: top_case_studies(items) for box, items in candidates.items()}
    links = []
    for key, link in graph.links.items():
        group = counted.get(key, [])
        links.append(
            {
                "key": short[key],
                "source": short[link.source],
                "target": short[link.target],
                "sentence": link.sentence,
                "conditions": link.conditions,
                "critical": bool(rows.links[key].critical),
                "verdict": VERDICT_LABELS[link_verdict_of(group, appraisals).verdict],
                "documents": [
                    {
                        "id": str(row.task_source_snapshot_id),
                        "title": titles.get(str(row.task_source_snapshot_id), ("", None))[0],
                        "year": titles.get(str(row.task_source_snapshot_id), ("", None))[1],
                        "support": row_judgement(row).support,
                        "quote": row.quote,
                        "relevance": row_judgement(row).relevance,
                        "relevance_note": row.relevance_reason,
                        "condition": row.condition,
                    }
                    for row in group
                    if row_judgement(row).support != "not_about"
                ],
            }
        )
    return {
        "boxes": [
            {
                "key": short[key],
                "layer": box.layer,
                "text": box.text,
                "result_criteria": {
                    **(rows.boxes[key].result_criteria or {}),
                    "indicator": rows.boxes[key].indicator,
                },
                "case_studies": case_studies.get(key, []),
            }
            for key, box in graph.boxes.items()
        ],
        "links": links,
        "pathways": [
            {
                "kind": p.kind,
                "label": rows.pathways[p.key].label,
                "links": [short[k] for k in p.links if k in short],
            }
            for p in graph.pathways
            if p.status == "kept"
        ],
    }
