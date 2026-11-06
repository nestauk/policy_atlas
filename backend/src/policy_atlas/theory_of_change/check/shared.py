"""Reads and helpers every check step uses (task 054).

The screened-in documents, the appraisals and judgements per link and the
verdict they give, the links to check, the item texts the searches and the
judge read, and the traced model-call helpers (``_call``, ``_ask``,
``_map_traced``).
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

from policy_atlas.core import tracing
from policy_atlas.core.schema import (
    capability_run,
    runs,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
    task_source_snapshot,
    toc_item_evidence,
    toc_link,
)
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.corpus.characterise import screened_sources
from policy_atlas.evidence_search.extract.quote_verify import QuoteMatcher, build_basis
from policy_atlas.options_scoping.model_calls import CallOutcome, call_with_retry
from policy_atlas.runtime.capability_registry import (
    THEORY_OF_CHANGE,
    expect_toc_plan,
    validate_plan,
)
from policy_atlas.runtime.toc_plan import (
    TOC_LINK_CAP,
)
from policy_atlas.theory_of_change import store
from policy_atlas.theory_of_change.check.grade import (
    DocAppraisal,
    Judgement,
    LinkVerdict,
    link_verdict,
    trusted_publisher,
)
from policy_atlas.theory_of_change.graph import (
    Graph,
    item_text,
)

log = structlog.get_logger()

#: Box origins that mean the user wrote the box (C29).
_USER_ORIGINS = frozenset({"user", "imported"})


#: Classify's evidence type for a modelling study (W15).
MODELLING_TYPE = "Modelling & Simulation"


@dataclass(frozen=True)
class Document:
    """One screened-in document, as the ToC steps read it."""

    tss_id: uuid.UUID
    title: str
    year: int | None
    abstract: str
    evidence_type: str | None

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
    conn: Connection, *, task_id: uuid.UUID, evidence_rows: Iterable[Any]
) -> dict[str, DocAppraisal]:
    """Each judged document's appraisal, read under the walk that judged it.

    Args:
        conn: Open connection.
        task_id: The task.
        evidence_rows: ``toc_item_evidence`` rows, or anything with their
            ``capability_run_id`` and ``task_source_snapshot_id``.

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


def _judgements(conn: Connection, task_id: uuid.UUID, status: str) -> dict[str, list[Row[Any]]]:
    """Each link's judgements of its counted hash (C19) with this status, not removed."""
    rows = conn.execute(
        select(toc_item_evidence)
        .join(
            toc_link,
            (toc_link.c.link_id == toc_item_evidence.c.link_id)
            & (toc_link.c.task_id == toc_item_evidence.c.task_id)
            & (toc_link.c.counted_hash == toc_item_evidence.c.item_hash),
        )
        .where(toc_item_evidence.c.task_id == task_id)
        .where(toc_item_evidence.c.status == status)
        .where(toc_item_evidence.c.excluded_at.is_(None))
        .order_by(toc_item_evidence.c.created_at, toc_item_evidence.c.evidence_id)
    )
    out: dict[str, list[Row[Any]]] = {}
    for row in rows:
        out.setdefault(str(row.link_id), []).append(row)
    return out


def counted_judgements(conn: Connection, *, task_id: uuid.UUID) -> dict[str, list[Row[Any]]]:
    """Each link's judgements that count: its counted hash (C19), accepted and not removed.

    A judgement the user removed from the link (C42), or one still pending or
    rejected (C44), does not count; the evidence list still shows it.
    """
    return _judgements(conn, task_id, "counted")


def pending_judgements(conn: Connection, *, task_id: uuid.UUID) -> dict[str, list[Row[Any]]]:
    """Each link's new evidence waiting for the user's Accept (C44), for its current count."""
    return _judgements(conn, task_id, "pending")


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


#: The search and judgements on the whole programme (red team, 2026-11-03): one
#: more item search in a full check, its documents judged in the same pool as the
#: connections' and stored as one event, never as a connection's evidence.
PROGRAMME_KEY = "programme"


PROGRAMME_EVENT = "toc.programme_judged"


def programme_item_text(plan: Any) -> str:
    """The text the whole programme is searched and judged on: intervention → goal."""
    intervention = (plan.intervention or "the intervention").strip()
    goal = plan.intended_change.strip()
    where = plan.where.strip() if plan.where else "the stated place"
    return "\n".join(
        [
            f"If {intervention}, then {goal}.",
            f"From: {intervention}",
            f"To: {goal}",
            "The whole programme: evaluations of this intervention, or a close one, "
            "and what happened to the goal.",
            f"Did this work where it was tried, and does it hold for "
            f"{plan.target_population.strip()} in {where} now?",
        ]
    )


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
        ``([(link_id, item_text)], left_out)`` under the 80-link cap (C5); a
        full check adds the whole programme's search (:data:`PROGRAMME_KEY`).
    """
    plan = expect_toc_plan(validate_plan(THEORY_OF_CHANGE, payload))
    graph, _ = store.load_graph(conn, task_id)
    keys, left_out = links_to_check(graph, links)
    intents = [(key, _link_item_text(graph, key, plan)) for key in keys]
    if links is None and plan.intervention:
        intents.append((PROGRAMME_KEY, programme_item_text(plan)))
    return intents, left_out


def _link_item_text(graph: Graph, key: str, plan: Any) -> str:
    """The text one link is searched, picked and judged on."""
    link = graph.links[key]
    return item_text(
        link,
        source_text=graph.boxes[link.source].text,
        target_text=graph.boxes[link.target].text,
        population=plan.target_population,
        place=plan.where,
    )


def _flag_values(row: Row[Any], reason: str) -> dict[str, Any]:
    """The T1 flag columns for a change to user work, or nothing."""
    if _user_written(row):
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


def _call[T](name: str, call: Callable[[], Any]) -> CallOutcome[T]:
    return call_with_retry(name, call, lambda response: response, event=name)


def _ask[T](name: str, call: Callable[[], Any], usage: UsageAccumulator) -> T | None:
    """One model call with one retry: its answer, or ``None``; its usage is added."""
    return _outcome_value(_call(name, call), usage)


def _short_keys(graph: Graph) -> tuple[dict[str, str], dict[str, str]]:
    """Short prompt keys for boxes (``b1``) and links (``l1``), and the way back."""
    to_short = {key: f"b{i}" for i, key in enumerate(graph.boxes, start=1)}
    to_short.update({key: f"l{i}" for i, key in enumerate(graph.links, start=1)})
    return to_short, {short: key for key, short in to_short.items()}


def _user_written(row: Row[Any]) -> bool:
    return bool(row.user_edited) or row.origin in _USER_ORIGINS
