"""The ``toc_select`` and ``toc_search_new`` steps: which documents reach the judge (C27, C32).

``toc_select`` keeps every document the item searches found, with no model
call, and picks the ones the judge reads for each link. ``toc_search_new``
does the same for the links discovery added, after their own searches. The
candidate helpers (a link's own search results, the rerank, the nearest by
meaning, the user's earlier decisions) live here and the judge reuses them.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from itertools import zip_longest
from typing import Any, Protocol

import structlog
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
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
    source_snapshot,
    task_source_snapshot,
    toc_item_evidence,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.assess.screen import ScreenContext, screen_in
from policy_atlas.evidence_search.corpus.ranking import (
    RERANK_BATCH_SIZE,
    RankingBackend,
    validate_ranked,
)
from policy_atlas.evidence_search.sourcing.acquire import normalize_doi
from policy_atlas.evidence_search.sourcing.search_live import crossref_abstracts
from policy_atlas.options_scoping.context import ScopeContext
from policy_atlas.options_scoping.model_calls import CallOutcome
from policy_atlas.runtime.toc_plan import (
    TOC_CHECK_MODE_KEY,
    TOC_LINKS_KEY,
    TOC_STUDIES_KEY,
)
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.backend import TocBackend
from policy_atlas.theory_of_change.check.pick_prompt import PICK_N
from policy_atlas.theory_of_change.check.shared import (
    PROGRAMME_KEY,
    Document,
    _call,
    _link_item_text,
    _map_traced,
    _outcome_value,
    links_to_check,
    walk_of_run,
)
from policy_atlas.theory_of_change.draft import walk_toc_plan
from policy_atlas.theory_of_change.seminal import SEMINAL_ORIGIN, fetch_seminal_works

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


#: The event ``toc_select`` writes with each link's picked documents; the judge reads it (C31).
PICKED_EVENT = "toc_select.picked"


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
    conn: Connection,
    *,
    task_id: uuid.UUID,
    walk_id: uuid.UUID,
    programme: bool = False,
    seminal: bool = False,
) -> dict[str, list[LinkCandidate]]:
    """Link id → the documents its own search found, from acquire's events.

    A document the task already held counts too (``source.seen_again``): a
    named check searches again and mostly finds documents an earlier check
    acquired for another link. With ``seminal``, the seminal works this walk
    itself looked up, under :data:`SEMINAL_ORIGIN`.
    """
    child_link = (
        {walk_id: SEMINAL_ORIGIN}
        if seminal
        else _child_links(conn, task_id=task_id, walk_id=walk_id, programme=programme)
    )
    if programme:
        child_link = {run: key for run, key in child_link.items() if key == PROGRAMME_KEY}
    if not child_link:
        return {}
    # Keyed by document and link: two links' searches may find the same held document.
    found: dict[tuple[uuid.UUID, str], tuple[tuple[str, str], int]] = {}
    for row in conn.execute(
        select(event_log.c.payload, runs.c.capability_run_id)
        .select_from(
            event_log.join(
                runs,
                (runs.c.run_id == event_log.c.run_id) & (runs.c.task_id == event_log.c.task_id),
            )
        )
        .where(event_log.c.task_id == task_id)
        .where(event_log.c.event_type.in_(["source.acquired", "source.seen_again"]))
        .where(runs.c.capability_run_id.in_(list(child_link)))
        .order_by(event_log.c.sequence)
    ):
        payload = row.payload
        if seminal and payload.get("query_origin") != SEMINAL_ORIGIN:
            continue
        found.setdefault(
            (uuid.UUID(payload["task_source_snapshot_id"]), child_link[row.capability_run_id]),
            ((str(payload["backend"]), str(payload["query_origin"])), int(payload["pool_rank"])),
        )
    if not found:
        return {}
    meta = {
        tss: (row.source_snapshot_id, row.metadata or {})
        for tss, row in store.snapshot_meta(conn, task_id, {tss for tss, _ in found}).items()
    }
    out: dict[str, list[LinkCandidate]] = {}
    for (tss, link_id), (source_list, rank) in found.items():
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
                c = replace(c, abstract=text)
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
    searchers: list[Any] | None = None,
    only: set[str] | None = None,
) -> dict[str, Any]:
    """Pick each link's documents and write the screen's rows (C27, C28, C31, C32).

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

    Before picking, the seminal works step (:mod:`.seminal`) looks up the works
    the walk's documents cite most and are not among them; every link's pick
    is offered them too, after its own and its nearest documents.

    With ``only`` (:func:`toc_search_new_scope`), only those links are picked:
    the other links' picks are kept and merged into the new picks event, a
    picked document already screened out is screened in again at the next
    screen generation, and the seminal works the first select looked up are
    offered again, not looked up again.

    Args:
        conn: Open connection inside the component transaction.
        task_id: The task.
        run_id: This run.
        context: The check walk's intent record.
        backend: The ToC model seam.
        embedder: The embedding backend for the shared pool, or ``None``.
        searchers: The walk's search backends, for the seminal works lookup.
        only: The links to pick for, or ``None`` for every link with a search.

    Returns:
        Screen counts, pick call counts, the pick usage and the seminal works
        counts (``seminal_*``).
    """
    walk_id = walk_of_run(conn, task_id=task_id, run_id=run_id)
    candidates = _link_candidates(conn, task_id=task_id, walk_id=walk_id)
    plan = walk_toc_plan(conn, task_id=task_id, run_id=run_id, scope_id=context.scope_id)
    seminal_counts: dict[str, Any] = {}
    if only is None:
        whole = _link_candidates(conn, task_id=task_id, walk_id=walk_id, programme=True)
        seminal_counts = fetch_seminal_works(
            conn,
            task_id=task_id,
            run_id=run_id,
            context=context,
            plan=plan,
            pool_ids={c.tss_id for docs in [*candidates.values(), *whole.values()] for c in docs},
            searchers=searchers or [],
            embedder=embedder,
        )
    seminal = _link_candidates(conn, task_id=task_id, walk_id=walk_id, seminal=True).get(
        SEMINAL_ORIGIN, []
    )
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
        seminal = _fill_abstracts(conn, {SEMINAL_ORIGIN: seminal})[SEMINAL_ORIGIN]
    graph, _ = store.load_graph(conn, task_id)
    texts = {key: _link_item_text(graph, key, plan) for key in targets if key in graph.links}
    already: dict[str, set[uuid.UUID]] = (
        {k: set(v) for k, v in _judged_documents(conn, task_id, sorted(texts)).items()}
        if only is None and context.context.get(TOC_CHECK_MODE_KEY) == "find_more"
        else {}
    )
    # The shared pool (C31): the walk's other documents closest to each link.
    walk_pool = list({c.tss_id: c for docs in candidates.values() for c in docs}.values())
    vectors = _document_vectors(conn, [c.tss_id for c in walk_pool]) if texts else {}
    shared = 0
    seminal_offered = 0
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
        # The seminal works, offered to every link after its own and nearest ones.
        offered = {c.tss_id for c in [*own, *extra]} | already.get(key, set())
        cited = [c for c in seminal if c.tss_id not in offered]
        seminal_offered += len(cited)
        candidates[key] = [*own, *extra, *cited]
    called = [k for k in texts if len(candidates[k]) > PICK_N]

    def run_pick(key: str) -> CallOutcome[Any]:
        shown: list[dict[str, object]] = [
            {"id": f"d{i}", "title": c.title, "abstract": c.abstract}
            for i, c in enumerate(candidates[key], start=1)
        ]
        return _call(
            "toc_pick",
            lambda: backend.pick(item_text=texts[key], candidates=shown),
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
        earlier = _walk_picks(conn, task_id=task_id, walk_id=walk_id) if only is not None else {}
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
    if only is None:
        # The whole programme's documents: the round-robin rule's 10, no pick call.
        whole = _link_candidates(conn, task_id=task_id, walk_id=walk_id, programme=True)
        picked = picked | set(select_for_link(whole.get(PROGRAMME_KEY, [])))
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
        **{f"seminal_{name}": value for name, value in seminal_counts.items()},
        "seminal_works": len(seminal),
        "seminal_offered": seminal_offered,
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
    wanted = {normalize_doi(doi) for dois in dois_by_link.values() for doi in dois}
    found: dict[str, uuid.UUID] = {}
    for tss_id, row in store.snapshot_meta(conn, task_id).items():
        doi = normalize_doi((row.metadata or {}).get("doi"))
        if doi is not None and doi in wanted:
            found.setdefault(doi, tss_id)
    return {
        key: [found[d] for d in map(normalize_doi, dois) if d is not None and d in found]
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


def links_without_search(conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID) -> list[str]:
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
    picks = _walk_picks(conn, task_id=task_id, walk_id=walk_id)
    new = set(_child_links(conn, task_id=task_id, walk_id=walk_id).values()) - set(picks)
    return toc_select_scope(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=context,
        backend=backend,
        embedder=embedder,
        only=new,
    )


def _child_links(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID, programme: bool = False
) -> dict[uuid.UUID, str]:
    """Item-search child walk id → the link it searched, for this walk.

    The whole programme's search is left out unless ``programme`` is true: it
    is no connection, and only the judge's programme jobs read it.
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
    return {
        child.capability_run_id: str(link_id)
        for child in children
        if (link_id := (child.context or {}).get("link_id"))
        and (programme or link_id != PROGRAMME_KEY)
    }


def _walk_picks(
    conn: Connection, *, task_id: uuid.UUID, walk_id: uuid.UUID
) -> dict[str, set[uuid.UUID]]:
    """Link id → the documents ``toc_select`` picked for it in this walk."""
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
    return {key: {uuid.UUID(tss) for tss in ids} for key, ids in (payload or {}).items()}


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
        select(task_source_snapshot.c.task_source_snapshot_id, chunk_embedding.c.embedding)
        .select_from(
            chunk_embedding.join(chunk, chunk.c.chunk_id == chunk_embedding.c.chunk_id).join(
                task_source_snapshot,
                task_source_snapshot.c.source_snapshot_id == chunk.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(list(tss_ids)))
        .where(chunk_embedding.c.embedding_profile == EMBEDDING_PROFILE)
        .where(chunk_embedding.c.unit_policy == UNIT_POLICY)
        .where(chunk_embedding.c.embedding.is_not(None))
    ):
        # The pgvector column (task 057 dropped the JSON copy); its type reads a list of floats.
        out.setdefault(row.task_source_snapshot_id, []).append(validate_vector(row.embedding))
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
