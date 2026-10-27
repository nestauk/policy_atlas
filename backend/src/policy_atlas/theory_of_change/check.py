"""The check walk's theory-of-change steps (task 054, step 1.4; C5, C6, C20).

After the spine steps have screened, classified and appraised the documents
the item searches found, five steps run in order (W16):

- ``toc_discover``: batches of screened-in documents propose routes the
  theory lacks; a proposal whose route breaks a structure rule or whose
  passages are not in the documents is dropped. Insert-only.
- ``toc_merge``: one call joins pathways that share a mechanism and sets
  aside those that miss the intended change.
- ``toc_judge``: per link, the top *K* documents read with one call each;
  both stances with verified quotes. Insert-only, keyed by item hash.
- ``toc_choose``: within the 6 / 3 limits, conditions supports recorded,
  and the critical connection by the C6 rule.
- ``toc_summarise``: the header paragraphs and every sentence, each citation
  checked against what the item's judgements allow.

Each step has the scoping steps' shape, ``(conn, *, task_id, run_id,
context, backend)``, and writes through :mod:`~policy_atlas.theory_of_change.store`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection, Row

from policy_atlas.core.schema import (
    capability_run,
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
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.corpus.characterise import screened_sources
from policy_atlas.evidence_search.corpus.ranking import (
    RERANK_BATCH_SIZE,
    RankingBackend,
    validate_ranked,
)
from policy_atlas.evidence_search.extract.quote_verify import QuoteMatcher, build_basis
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.model_calls import CallOutcome, call_with_retry
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    validate_plan,
)
from policy_atlas.runtime.toc_plan import TOC_LINK_CAP, TOC_LINKS_KEY
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.discover_prompt import DISCOVER_BATCH_SIZE, ProposalWire
from policy_atlas.theory_of_change.draft import plan_data, walk_toc_plan
from policy_atlas.theory_of_change.evidence.grade import (
    GRADE_ORDER,
    DocAppraisal,
    GradeResult,
    Judgement,
    counted_score,
    grade,
)
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

#: Documents judged per link (C5).
JUDGE_TOP_K = 8

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
BOX_FALLBACK_DESCRIPTION = "A step in the theory. No case studies were found in the documents read."


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
        Document id → appraisal; an unscored document has ``score=None``.
        Web pages arrive in increment 3 (``web=False`` here).
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
    out: dict[str, DocAppraisal] = {}
    for walk, tss in sorted(pairs, key=str):
        key = (scope_of.get(walk), tss)
        out[str(tss)] = DocAppraisal(
            score=scores.get(key), modelling=types.get(key) == MODELLING_TYPE
        )
    return out


def counted_judgements(conn: Connection, *, task_id: uuid.UUID) -> dict[str, list[Row[Any]]]:
    """Each link's judgements whose item hash equals its counted hash (C19)."""
    rows = conn.execute(
        select(toc_item_evidence)
        .join(
            toc_link,
            (toc_link.c.link_id == toc_item_evidence.c.link_id)
            & (toc_link.c.task_id == toc_item_evidence.c.task_id)
            & (toc_link.c.counted_hash == toc_item_evidence.c.item_hash),
        )
        .where(toc_item_evidence.c.task_id == task_id)
        .order_by(toc_item_evidence.c.created_at, toc_item_evidence.c.evidence_id)
    )
    out: dict[str, list[Row[Any]]] = {}
    for row in rows:
        out.setdefault(str(row.link_id), []).append(row)
    return out


def link_grades(
    rows: list[Row[Any]], appraisals: dict[str, DocAppraisal]
) -> tuple[GradeResult, GradeResult]:
    """Both grades of one link from its counted judgements (C4)."""
    judgements = [
        Judgement(
            document_id=str(row.task_source_snapshot_id),
            stance_elsewhere=row.stance_elsewhere,
            stance_here=row.stance_here,
            robust_model=row.robust_model,
        )
        for row in rows
    ]
    return (
        grade(judgements, appraisals, "elsewhere"),
        grade(judgements, appraisals, "here"),
    )


def _current_hash(graph: Graph, key: str) -> str:
    link = graph.links[key]
    return item_hash(link, graph.boxes[link.source].text, graph.boxes[link.target].text)


def _kept_links_first(graph: Graph) -> list[str]:
    """Link keys: those on kept pathways first, in pathway order, then the rest."""
    ordered: list[str] = []
    for pathway in graph.pathways:
        if pathway.status == "kept":
            ordered.extend(key for key in pathway.links if key in graph.links)
    ordered.extend(graph.links)
    return list(dict.fromkeys(ordered))


def links_to_check(graph: Graph, named: list[str] | None = None) -> tuple[list[str], int]:
    """The links a check walk covers, kept pathways first, capped at 80 (C5).

    Args:
        graph: The theory.
        named: The links a named-link check covers, or ``None`` for all.

    Returns:
        ``(links, left_out)``.
    """
    ordered = _kept_links_first(graph)
    if named is not None:
        wanted = set(named)
        ordered = [key for key in ordered if key in wanted]
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


def proposal_problem(
    proposal: ProposalWire,
    *,
    layers: dict[str, str],
    pairs: set[tuple[str, str]],
    documents: dict[str, Document],
) -> str | None:
    """Why a discover proposal cannot be written, or ``None``.

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
    known = {**layers, **new_layers}
    route = proposal.route
    if len(route) < 2 or any(key not in known for key in route):
        return "the route names unknown boxes"
    if len(set(route)) != len(route):
        return "the route visits a box twice"
    end = "impact" if proposal.kind == "success" else "failure_outcome"
    if known[route[0]] != "input" or known[route[-1]] != end:
        return f"the route does not run from an input to {end}"
    if set(new_layers) - set(route):
        return "a new box is not on the route"
    new_links = {(link.source, link.target): link for link in proposal.new_links}
    for source, target in zip(route, route[1:], strict=False):
        if (source, target) in pairs:
            continue
        link = new_links.get((source, target))
        if link is None:
            return f"no link between {source} and {target}"
        reason = link_problem(known[source], known[target])
        if reason:
            return reason
    if not proposal.evidence:
        return "no evidence"
    for evidence in proposal.evidence:
        document = documents.get(evidence.document_id)
        if document is None or not quote_found(document.text, evidence.quote):
            return "a passage is not in its document"
    return None


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

    with ThreadPoolExecutor(max_workers=DISCOVER_WORKERS) as pool:
        outcomes = list(pool.map(run_batch, batches))

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
            accepted += 1
            # A proposal's new keys are local to it: map them to fresh short keys.
            local: dict[str, str] = {}
            for box in proposal.new_boxes:
                box_id = uuid.uuid4()
                local[box.key] = f"b{len(layers) + 1}"
                layers[local[box.key]] = box.layer
                back[local[box.key]] = str(box_id)
                store.insert(
                    conn,
                    log_,
                    toc_box,
                    {
                        "box_id": box_id,
                        "task_id": task_id,
                        "layer": box.layer,
                        "text": box.text,
                        "result_criteria": {"definition": None, "timing": None},
                        "origin": "found_in_evidence",
                    },
                )
            route = [local.get(key, key) for key in proposal.route]
            new_links = {
                (local.get(link.source, link.source), local.get(link.target, link.target)): link
                for link in proposal.new_links
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
                kind=proposal.kind,
                label=proposal.label,
                link_ids=link_ids,
                origin="found_in_evidence",
            )
            changes.append(
                {
                    "text": f"Added a {proposal.kind} pathway from the evidence: {proposal.label}.",
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
        "accepted": accepted,
        "rejected": rejected,
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_discover.done", accepted=accepted, rejected=rejected, batches=len(batches))
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


def toc_merge_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Merge pathways that share a mechanism; set aside those that miss the change.

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
    short, _ = _short_keys(graph)
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
    usage = UsageAccumulator()
    response = _outcome_value(
        _call(
            "toc_merge", lambda: backend.merge(plan=plan_data(plan), pathways=payload), "toc_merge"
        ),
        usage,
    )
    if response is None:
        raise RuntimeError("toc_merge: the merge call failed")
    decisions = {
        by_short[decision.pathway]: decision
        for decision in response.decisions
        if decision.pathway in by_short
    }
    kinds = {pathway.key: pathway.kind for pathway in kept_paths}
    order = [pathway.key for pathway in kept_paths]
    kept = {key for key in order if key not in decisions or decisions[key].action == "keep"}
    kept = _keep_one_of_each(order, kinds, kept)
    log_ = store.ChangeLog()
    changes: list[store.Change] = []
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
        "skipped": len(log_.skipped),
        "backend_mode": backend.mode,
        "usage_totals": usage.payload(),
    }
    log.info("toc_merge.done", **{k: v for k, v in summary.items() if k != "usage_totals"})
    return summary


# --- judge ----------------------------------------------------------------------


def _own_search_documents(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> dict[str, set[uuid.UUID]]:
    """Link id → documents its own item search acquired in this walk.

    A link absent from the map had no search of its own.
    """
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
    out: dict[str, set[uuid.UUID]] = {}
    child_link: dict[uuid.UUID, str] = {}
    for child in children:
        link_id = (child.context or {}).get("link_id")
        if link_id:
            child_link[child.capability_run_id] = str(link_id)
            out.setdefault(str(link_id), set())
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
    """The steps just before and after a link, for the judge (``toc_judge_v3``).

    One ``Before: <sentence>`` line per link that ends at this link's source
    box and one ``After: <sentence>`` line per link that starts at its target
    box, at most :data:`NEIGHBOURS_PER_SIDE` each, in graph order.

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
    return "\n".join(before[:NEIGHBOURS_PER_SIDE] + after[:NEIGHBOURS_PER_SIDE])


def toc_judge_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
    ranker: RankingBackend | None = None,
) -> dict[str, Any]:
    """Judge each link against its top documents, both questions at once (C5).

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        ranker: The rerank backend ``select`` uses, or ``None`` to keep order.

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
    own = _own_search_documents(conn, task_id=task_id, walk_id=walk_id)
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
        if key in own:
            candidates = [pool_by_id[tss] for tss in sorted(own[key], key=str) if tss in pool_by_id]
        else:
            candidates = list(pool)
        judged = set(
            conn.execute(
                select(toc_item_evidence.c.task_source_snapshot_id)
                .where(toc_item_evidence.c.task_id == task_id)
                .where(toc_item_evidence.c.link_id == uuid.UUID(key))
                .where(toc_item_evidence.c.item_hash == current)
            ).scalars()
        )
        candidates = [doc for doc in candidates if doc.tss_id not in judged]
        for document in rerank(ranker, candidates, intent=text, usage=usage)[:JUDGE_TOP_K]:
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
                modelling=job.document.evidence_type == MODELLING_TYPE,
                neighbours=job.neighbours,
            ),
            "toc_judge",
        )

    with ThreadPoolExecutor(max_workers=JUDGE_WORKERS) as executor:
        outcomes = list(executor.map(run_job, jobs))

    stored = unverified = failed = 0
    for job, outcome in zip(jobs, outcomes, strict=True):
        response = _outcome_value(outcome, usage)
        if response is None:
            failed += 1
            continue
        text = job.document.text
        stances: dict[str, tuple[str, str | None]] = {}
        for name, wire in (("elsewhere", response.worked_elsewhere), ("here", response.holds_here)):
            if wire.stance != "not_about" and not quote_found(text, wire.quote):
                unverified += 1
                stances[name] = ("not_about", None)
            elif wire.stance == "not_about":
                stances[name] = ("not_about", None)
            else:
                stances[name] = (wire.stance, wire.quote)
        case = response.case_study
        if case is not None and not quote_found(text, case.quote):
            case = None
        indicator = response.indicator
        # One box per judgement row: the case study's box wins; an indicator
        # naming the other end of the link is dropped.
        if case is not None and indicator is not None and indicator.box != case.box:
            indicator = None
        box_end = case.box if case is not None else (indicator.box if indicator else None)
        supports = any(stance == "supports" for stance, _ in stances.values())
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
                "stance_elsewhere": stances["elsewhere"][0],
                "quote_elsewhere": stances["elsewhere"][1],
                "stance_here": stances["here"][0],
                "quote_here": stances["here"][1],
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
                "robust_model": (
                    response.robust_model if job.document.evidence_type == MODELLING_TYPE else None
                ),
                "item_hash": job.item_hash,
            },
        )
        stored += 1

    # Every covered link now counts the judgements of its current wording (C19).
    log_ = store.ChangeLog()
    for key in link_keys:
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
    summary = {
        "links": len(link_keys),
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


def critical_link(graph: Graph, grades: dict[str, tuple[GradeResult, GradeResult]]) -> str | None:
    """The critical connection by the C6 rule.

    Among links on kept success pathways whose *worked elsewhere* grade is
    medium or strong and whose *holds here* grade is weak or none: the one on
    the most kept pathways (ties: the earlier one in pathway order). If none
    qualifies: the link with the lowest *holds here* grade on the most kept
    pathways.

    Args:
        graph: The theory, with current pathway statuses.
        grades: Link key → (elsewhere, here).

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
    none = GradeResult(grade="none", against=0, supports=0)

    def here(key: str) -> int:
        return GRADE_ORDER.index(grades.get(key, (none, none))[1].grade)

    def elsewhere(key: str) -> int:
        return GRADE_ORDER.index(grades.get(key, (none, none))[0].grade)

    qualifying = [
        key for key in order if elsewhere(key) >= GRADE_ORDER.index("medium") and here(key) <= 1
    ]
    if qualifying:
        return max(qualifying, key=lambda key: (on[key], -order.index(key)))
    return min(order, key=lambda key: (here(key), -on[key], order.index(key)))


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
    grades = {key: link_grades(counted.get(key, []), appraisals) for key in graph.links}
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
                        "worked_elsewhere": grades[key][0].grade,
                        "holds_here": grades[key][1].grade,
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
        conn, log_, task_id=task_id, graph=graph, grades=grades, changes=changes
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
    grades: dict[str, tuple[GradeResult, GradeResult]],
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
    choice = critical_link(graph, grades)
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


def is_merged(rows: list[Row[Any]]) -> bool:
    """Every judged document that spoke to the link answers both questions the same way."""
    spoke = [
        row for row in rows if row.stance_elsewhere != "not_about" or row.stance_here != "not_about"
    ]
    return bool(spoke) and all(row.stance_elsewhere == row.stance_here for row in spoke)


def toc_summarise_scope(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScopeContext,
    backend: TocBackend,
) -> dict[str, Any]:
    """Write the header paragraphs and every sentence, each citation checked (C20).

    ``about``, ``evidence_says`` and ``evaluation_questions`` are returned in
    the summary (the step's ``component.completed`` payload), which the read
    API serves; link sentences and box descriptions are written on the rows.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.

    Returns:
        The header paragraphs, the questions, the replaced count and the usage.

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

    allowed: dict[str, dict[str, set[str]]] = {}
    for key in graph.links:
        group = counted.get(key, [])
        allowed[key] = {
            "elsewhere": {
                str(r.task_source_snapshot_id) for r in group if r.stance_elsewhere != "not_about"
            },
            "here": {str(r.task_source_snapshot_id) for r in group if r.stance_here != "not_about"},
        }
    answered = {back.get(item.link): item for item in response.links}
    replaced = 0
    log_ = store.ChangeLog()
    for key, row in rows.links.items():
        item = answered.get(key)
        sentences: dict[str, str] = {}
        for question in ("elsewhere", "here"):
            if not allowed[key][question]:
                sentences[question] = NO_EVIDENCE_SENTENCE
                continue
            sentence = getattr(item, f"{question}_sentence", None) if item else None
            cites = getattr(item, f"{question}_cites", []) if item else []
            if sentence and sentence.strip() and check_citations(cites, allowed[key][question]):
                sentences[question] = sentence.strip()
            else:
                replaced += 1
                sentences[question] = UNSETTLED_SENTENCE
        store.update(
            conn,
            log_,
            toc_link,
            row.link_id,
            observed_revision=row.revision,
            values={
                "elsewhere_sentence": sentences["elsewhere"],
                "here_sentence": sentences["here"],
            },
        )
    case_docs: dict[str, set[str]] = {}
    for row in every:
        if row.case_box_id is not None and row.case_study is not None:
            case_docs.setdefault(str(row.case_box_id), set()).add(str(row.task_source_snapshot_id))
    described = {back.get(item.box): item for item in response.boxes}
    for key, row in rows.boxes.items():
        item = described.get(key)
        if (
            item is not None
            and item.description.strip()
            and check_citations(item.cites, case_docs.get(key, set()))
        ):
            description = item.description.strip()
        else:
            replaced += 1
            description = BOX_FALLBACK_DESCRIPTION
        store.update(
            conn,
            log_,
            toc_box,
            row.box_id,
            observed_revision=row.revision,
            values={"description": description},
        )
    store.record(conn, task_id=task_id, run_id=run_id, step="toc_summarise", log=log_)
    summary = {
        "about": response.about,
        "evidence_says": response.evidence_says,
        "evaluation_questions": list(response.evaluation_questions),
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

    Ranks by the document's appraisal score (a robust model counts as 3, C4),
    then supporting documents before others, then the given order; keeps
    the first of each programme and place (case and spacing ignored) and at
    most :data:`CASE_STUDIES_PER_BOX`.

    Args:
        candidates: ``(item, programme, place, score, supports)`` per case
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
    """A judgement row's ``(score, supports)`` for :func:`top_case_studies`."""
    judgement = Judgement(
        document_id=str(row.task_source_snapshot_id),
        stance_elsewhere=row.stance_elsewhere,
        stance_here=row.stance_here,
        robust_model=row.robust_model,
    )
    supports = "supports" in (row.stance_elsewhere, row.stance_here)
    return counted_score(judgement, appraisal), supports


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
        elsewhere, here = link_grades(group, appraisals)
        links.append(
            {
                "key": short[key],
                "source": short[link.source],
                "target": short[link.target],
                "sentence": link.sentence,
                "conditions": link.conditions,
                "critical": bool(rows.links[key].critical),
                "worked_elsewhere": elsewhere.grade,
                "holds_here": here.grade,
                "merged": is_merged(group),
                "documents": [
                    {
                        "id": str(row.task_source_snapshot_id),
                        "title": titles.get(str(row.task_source_snapshot_id), ("", None))[0],
                        "year": titles.get(str(row.task_source_snapshot_id), ("", None))[1],
                        "worked_elsewhere": {
                            "stance": row.stance_elsewhere,
                            "quote": row.quote_elsewhere,
                        },
                        "holds_here": {"stance": row.stance_here, "quote": row.quote_here},
                        "condition": row.condition,
                    }
                    for row in group
                    if row.stance_elsewhere != "not_about" or row.stance_here != "not_about"
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
