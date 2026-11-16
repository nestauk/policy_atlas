"""The ``toc_discover`` step: routes the evidence suggests (task 054, C6).

Batches of screened-in documents propose routes the theory lacks; a proposal
whose route breaks a structure rule or whose passages are not in the documents
is dropped. Insert-only.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    toc_box,
    toc_link,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.model_calls import CallOutcome
from policy_atlas.runtime.toc_plan import (
    as_drawn,
)
from policy_atlas.theory_of_change import proposals, store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check.discover_prompt import (
    CONSOLIDATE_MAX_NEW_FAILURE,
    CONSOLIDATE_MAX_NEW_SUCCESS,
    DISCOVER_BATCH_SIZE,
    ConsolidateResponse,
    NewLinkWire,
    ProposalWire,
)
from policy_atlas.theory_of_change.check.shared import (
    Document,
    _ask,
    _call,
    _map_traced,
    _outcome_value,
    _short_keys,
    quote_found,
    screened_documents,
)
from policy_atlas.theory_of_change.draft import plan_data, walk_toc_plan
from policy_atlas.theory_of_change.graph import (
    MAX_FAILURE_PATHWAYS,
    MAX_SUCCESS_PATHWAYS,
    Graph,
    link_problem,
    trim_conditions,
)
from policy_atlas.theory_of_change.proposals import EditOpWire

log = structlog.get_logger()


#: Discover batches in flight at once.
DISCOVER_WORKERS = 4


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


#: A found route keeps at most this many of the documents it was found in.
ROUTE_DOCUMENTS = 3


def _route_suggestion(
    path: Any,
    new_boxes: dict[str, Any],
    code_of: dict[str, str],
    link_code: dict[tuple[str, str], str],
    *,
    proposed: set[str],
    evidence: list[dict[str, str]],
    group: str,
) -> list[Any]:
    """One found route as suggested edits: its new boxes, its new connections, then the pathway.

    Existing boxes and connections are named by their codes; new ones by keys
    (``n1`` for a box, ``l1`` for a connection) that the later edits use.
    """

    def op(**values: Any) -> EditOpWire:
        return EditOpWire.of(**{"group": group, **values})

    reason = f"Found in the evidence: {path.label}."
    ops = [
        op(
            op="add_box",
            reason=reason,
            key=key,
            layer=new_boxes[key].layer,
            text=new_boxes[key].text,
        )
        for key in dict.fromkeys(path.route)
        if key in new_boxes and key not in proposed
    ]

    def ref(key: str) -> str:
        return key if key in new_boxes else code_of.get(key, key)

    new_links = {(link.source, link.target): link for link in path.new_links}
    refs: list[str] = []
    for source, target in zip(path.route, path.route[1:], strict=False):
        if (source, target) in link_code:
            refs.append(link_code[(source, target)])
            continue
        wire = new_links[(source, target)]
        key = f"l{len(proposed) + len(refs) + len(ops) + 1}"
        ops.append(
            op(
                op="add_link",
                reason=reason,
                key=key,
                source=ref(source),
                dest=ref(target),
                if_text=wire.if_text,
                then_text=wire.then_text,
                because_text=wire.because_text,
            )
        )
        refs.append(key)
    ops.append(
        op(
            op="add_pathway",
            reason=reason,
            links=refs,
            kind=path.kind,
            label=path.label,
            evidence=evidence,
        )
    )
    return ops


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
    graph, graph_rows = store.load_graph(conn, task_id)
    documents = screened_documents(conn, task_id=task_id, scope_id=context.scope_id)
    short, back = _short_keys(graph)
    theory = _theory_for_discover(graph, short)
    # An uploaded diagram kept as drawn: found routes wait as one suggestion (owner, 2026-11-04).
    suggest_only = as_drawn(plan)
    code_of = {short[key]: graph_rows.boxes[key].code or short[key] for key in graph.boxes}
    suggested: list[Any] = []
    # Each checked proposal's documents and quotes, for the suggestion and the report.
    evidence_of: dict[str, list[dict[str, str]]] = {}
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
            candidate_id = f"q{len(candidates) + 1}"
            candidates.append(_candidate(candidate_id, proposal))
            evidence_of[candidate_id] = [
                {"tss": evidence.document_id, "quote": evidence.quote}
                for evidence in proposal.evidence
            ]
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
        consolidated = _ask(
            "toc_consolidate",
            lambda: backend.consolidate(
                plan=data,
                theory=theory,
                proposals=candidates,
                max_success=limit["success"],
                max_failure=limit["failure"],
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
        if suggest_only:
            suggested.extend(
                _route_suggestion(
                    path,
                    new_boxes,
                    code_of,
                    {pair: graph_rows.links[key].code or key for pair, key in link_of_pair.items()},
                    proposed={op.key for op in suggested if op.key},
                    # Each found route is offered on its own (owner, 2026-11-04).
                    group=f"r{sum(1 for op in suggested if op.op == 'add_pathway') + 1}",
                    evidence=list(
                        {
                            item["tss"]: item
                            for proposal_id in path.from_proposals
                            for item in evidence_of.get(proposal_id, [])
                        }.values()
                    )[:ROUTE_DOCUMENTS],
                )
            )
            continue
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
    if suggested:
        routes = sum(1 for op in suggested if op.op == "add_pathway")
        proposals.create_proposal(
            conn,
            task_id=task_id,
            source="discover",
            summary=(
                f"{routes} route{'s' if routes != 1 else ''} found in the evidence that "
                "your diagram does not show"
            ),
            ops=suggested,
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
