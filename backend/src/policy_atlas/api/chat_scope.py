"""Read-only, turn-scoped evidence readers for task chat.

``resolve_terminal_run_components`` reconstructs a completed walk's terminal
component references once at chat-turn reservation time.  ``search_chunks`` is
deliberately scope-wide: it searches the shared screened corpus.  The other
matrix rows are bounded to that turn-start walk: ``query_findings`` and the
selection/characterisation/grouping lookups use their resolved component ids;
appraisal, classification, tags, screening, coverage, ``docs_by_tag``, and
``tag_aggregate`` are snapshot-bound to every component-run id in that walk.
All of those currently carry a creating-run key, so no structured lookup kind
is scope-wide-by-necessity.

**An options-scoping task's scope set** (task 045, S11, A8; ADR 0039
decision 5): once a longlist exists the chat — the ordinary task chat and
the Task Agent's longlist questions alike — answers over the walk that built
it **and** every option search's targeted scope, so an added option's own
documents are reachable; before that, over the baseline walk. A document in
two of those scopes is one document under the precedence rule
(``build_retrieval_scope``).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core import events
from policy_atlas.core.embeddings import EmbeddingBackend, StubEmbeddingBackend
from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    grouping_result,
    longlist_result,
    runs,
    selection_result,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    ChunkRetriever,
    PassThroughChunkReranker,
    SynthesisDirective,
    _grouping_summary,
    build_retrieval_scope,
    make_findings_reader,
    make_lookup_reader,
)
from policy_atlas.options_scoping.labels import labels_for_snapshots
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, capability_of_task
from policy_atlas.runtime.scoping_plan import TARGETED_PURPOSE

#: A walk whose evidence a chat may answer over.
_TERMINAL = ("succeeded", "degraded")


@dataclass(frozen=True)
class ResolvedRunScope:
    """Terminal component ids resolved for one chat turn.

    Args:
        capability_run_id: Completed capability walk selected for the turn.
        evidence_scope_id: Shared evidence scope of that walk.
        characterisation_run_id: Latest successful characterisation attempt.
        selection_run_id: Latest successful selection attempt.
        extraction_run_id: Latest successful extraction attempt.
        grouping_run_id: Latest successful grouping attempt.
        extra_scope_ids: Further evidence scopes the readers span — an
            options-scoping task's option searches (task 045, S11). Empty
            for every other scope.
        resolve_labels: Whether a document with no label in its own scope
            takes the label resolver's (``options_scoping.labels``) — an
            inherited document on a longlist carries its linked task's labels
            and is never re-classified or re-appraised there.
    """

    capability_run_id: uuid.UUID
    evidence_scope_id: uuid.UUID
    characterisation_run_id: uuid.UUID | None
    selection_run_id: uuid.UUID | None
    extraction_run_id: uuid.UUID | None
    grouping_run_id: uuid.UUID | None
    extra_scope_ids: tuple[uuid.UUID, ...] = ()
    resolve_labels: bool = False


def resolve_terminal_run_components(
    engine: Engine, *, task_id: uuid.UUID
) -> ResolvedRunScope | None:
    """Resolve the latest completed walk's terminal component attempts.

    Selects the walk; ``_resolve_components`` does the reduction. An Evidence
    search reads its latest completed walk, as it always has. An
    options-scoping task reads what exists (task 045, S11, A8): once a
    ``longlist_result`` exists, the completed walk that built the latest one,
    with every option search's targeted scope as an extra scope; before that,
    its latest completed walk that is neither a child nor an option search
    (the baseline walk).

    Args:
        engine: Database engine used for this short-lived read.
        task_id: Task owning the completed walk.

    Returns:
        The resolved terminal scope, or ``None`` when no completed walk exists.
    """
    with engine.connect() as conn:
        if capability_of_task(conn, task_id) == OPTIONS_SCOPING:
            return _resolve_scoping(conn, task_id=task_id)
        cap_row = conn.execute(
            select(capability_run)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.status.in_(_TERMINAL))
            .order_by(
                capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc()
            )
            .limit(1)
        ).one_or_none()
        if cap_row is None:
            return None
        return _resolve_components(conn, task_id=task_id, cap=dict(cap_row._mapping))


def _resolve_scoping(conn: Connection, *, task_id: uuid.UUID) -> ResolvedRunScope | None:
    """Resolve an options-scoping task's chat scope: the longlist set, else the baseline."""
    longlist_walk = conn.execute(
        select(capability_run)
        .select_from(
            longlist_result.join(
                runs,
                (runs.c.run_id == longlist_result.c.run_id)
                & (runs.c.task_id == longlist_result.c.task_id),
            ).join(
                capability_run,
                (capability_run.c.capability_run_id == runs.c.capability_run_id)
                & (capability_run.c.task_id == runs.c.task_id),
            )
        )
        .where(longlist_result.c.task_id == task_id)
        .where(capability_run.c.status.in_(_TERMINAL))
        .order_by(longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id)
        .limit(1)
    ).one_or_none()
    if longlist_walk is not None:
        resolved = _resolve_components(conn, task_id=task_id, cap=dict(longlist_walk._mapping))
        return replace(
            resolved,
            extra_scope_ids=targeted_scope_ids(conn, task_id=task_id),
            resolve_labels=True,
        )
    baseline = conn.execute(
        select(capability_run)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(capability_run.c.status.in_(_TERMINAL))
        .where(capability_run.c.parent_capability_run_id.is_(None))
        .where(evidence_scope.c.purpose.is_distinct_from(TARGETED_PURPOSE))
        .order_by(capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc())
        .limit(1)
    ).one_or_none()
    if baseline is None:
        return None
    return _resolve_components(conn, task_id=task_id, cap=dict(baseline._mapping))


def targeted_scope_ids(conn: Connection, *, task_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
    """Return every option search's targeted scope on a task, oldest first.

    The children of the longlist walks (a rebuild searches only its new
    entrants, so an earlier walk's children still hold the other options'
    documents) and every parentless option search the verb *add* opened.

    Args:
        conn: Open read connection.
        task_id: The options-scoping task.

    Returns:
        The distinct targeted scope ids, in walk start order.
    """
    rows = conn.execute(
        select(capability_run.c.evidence_scope_id)
        .select_from(
            capability_run.join(
                evidence_scope,
                (evidence_scope.c.evidence_scope_id == capability_run.c.evidence_scope_id)
                & (evidence_scope.c.task_id == capability_run.c.task_id),
            )
        )
        .where(capability_run.c.task_id == task_id)
        .where(evidence_scope.c.purpose == TARGETED_PURPOSE)
        .order_by(capability_run.c.started_at, capability_run.c.capability_run_id)
    ).scalars()
    return tuple(dict.fromkeys(rows))


def resolve_run_components(
    engine: Engine, task_id: uuid.UUID, *, capability_run_id: uuid.UUID
) -> ResolvedRunScope | None:
    """Resolve one named walk's component attempts, paused walks included.

    The chat route reads the *latest completed* walk
    (``resolve_terminal_run_components``, which keeps its
    ``succeeded|degraded`` filter). A Task Agent turn taken while a scoping
    walk is paused on its baseline gate has no completed walk to read: it
    answers over the walk it is parked in, named by id. The component
    reduction is identical — only the walk selection differs.

    Args:
        engine: Database engine used for this short-lived read.
        task_id: Task owning the walk, enforced on the lookup.
        capability_run_id: The walk to resolve.

    Returns:
        The resolved scope, or ``None`` when that task holds no such walk in a
        paused or completed state (a walk still ``running`` has no pinned
        answer scope, and an ``aborted`` or ``failed`` one is not answerable).
    """
    with engine.connect() as conn:
        cap_row = conn.execute(
            select(capability_run)
            .where(capability_run.c.task_id == task_id)
            .where(capability_run.c.capability_run_id == capability_run_id)
            .where(capability_run.c.status.in_(("paused", "succeeded", "degraded")))
        ).one_or_none()
        if cap_row is None:
            return None
        return _resolve_components(conn, task_id=task_id, cap=dict(cap_row._mapping))


def _resolve_components(
    conn: Connection, *, task_id: uuid.UUID, cap: dict[str, Any]
) -> ResolvedRunScope:
    """Reduce one walk's ordered component attempts to its latest per component.

    The reduction intentionally mirrors ``runtime.continuation_state.build``:
    join ``run.started`` events to the walk's run rows, order by event
    sequence, then let the latest event win for each component and registry
    component.

    Args:
        conn: Open read connection.
        task_id: Task owning the walk.
        cap: The walk's ``capability_run`` row mapping.

    Returns:
        The resolved component scope for that walk.
    """
    event_rows = events.read(conn, task_id)
    run_rows = [
        dict(row._mapping)
        for row in conn.execute(
            select(runs)
            .where(runs.c.task_id == task_id)
            .where(runs.c.capability_run_id == cap["capability_run_id"])
        )
    ]

    # Parity with continuation_state.build() lines 184–214: do not replace
    # sequence ordering with timestamps (they are not the durable ordering key).
    started_by_run = {
        entry["run_id"]: entry
        for entry in event_rows
        if entry["event_type"] == "run.started" and entry["run_id"] is not None
    }
    run_rows_by_id = {row["run_id"]: row for row in run_rows}
    attempts = sorted(
        (
            (started_by_run[run_id], row)
            for run_id, row in run_rows_by_id.items()
            if run_id in started_by_run
        ),
        key=lambda item: item[0]["sequence"],
    )
    latest_component: dict[str, dict[str, Any]] = {}
    latest_registry: dict[str, dict[str, Any]] = {}
    for started, row in attempts:
        payload = started["payload"]
        component = payload.get("component")
        registry = payload.get("registry_component")
        if isinstance(component, str):
            latest_component[component] = row
        if isinstance(registry, str):
            latest_registry[registry] = row

    def successful(component: str) -> uuid.UUID | None:
        row = latest_component.get(component) or latest_registry.get(component)
        return row["run_id"] if row is not None and row["status"] == "succeeded" else None

    return ResolvedRunScope(
        capability_run_id=cap["capability_run_id"],
        evidence_scope_id=cap["evidence_scope_id"],
        characterisation_run_id=successful("characterise"),
        selection_run_id=successful("select"),
        extraction_run_id=successful("extract"),
        grouping_run_id=successful("group"),
    )


def build_chat_readers(
    engine: Engine,
    scope: ResolvedRunScope,
    task_id: uuid.UUID,
    *,
    embedding_backend: EmbeddingBackend | None = None,
) -> tuple[
    ChunkRetriever,
    Callable[[dict[str, Any]], dict[str, Any]] | None,
    Callable[[dict[str, Any]], dict[str, Any]],
]:
    """Build short-lived-connection readers bound to one resolved chat scope.

    Args:
        engine: Database engine; connections are opened only to build/read.
        scope: Turn-start terminal component resolution.
        task_id: Task owning all returned evidence.
        embedding_backend: Query embedding seam.  The zero-egress stub is the
            default until the chat service injects its configured live backend.

    Returns:
        Chunk retriever, findings reader (when extraction resolved), and lookup reader.
    """
    with engine.connect() as conn:
        selected_tss_ids: set[uuid.UUID] = set()
        if scope.selection_run_id is not None:
            selected = conn.execute(
                select(selection_result.c.selected)
                .where(selection_result.c.task_id == task_id)
                .where(selection_result.c.evidence_scope_id == scope.evidence_scope_id)
                .where(selection_result.c.run_id == scope.selection_run_id)
            ).scalar_one_or_none()
            if isinstance(selected, list):
                for item in selected:
                    if isinstance(item, dict) and isinstance(item.get("tss_id"), str):
                        try:
                            selected_tss_ids.add(uuid.UUID(item["tss_id"]))
                        except ValueError:
                            continue
        retrieval_scope = build_retrieval_scope(
            conn,
            task_id=task_id,
            scope_id=scope.evidence_scope_id,
            selected_tss_ids=selected_tss_ids,
            extra_scope_ids=scope.extra_scope_ids,
        )
        if scope.resolve_labels:
            _fill_resolved_labels(conn, task_id=task_id, docs=retrieval_scope.docs)
        terminal_run_ids = set(
            conn.execute(
                select(runs.c.run_id)
                .where(runs.c.task_id == task_id)
                .where(runs.c.capability_run_id == scope.capability_run_id)
            ).scalars()
        )
        if scope.extra_scope_ids:
            # The option searches' own component runs belong to the snapshot too.
            terminal_run_ids |= set(
                conn.execute(
                    select(runs.c.run_id)
                    .select_from(
                        runs.join(
                            capability_run,
                            (capability_run.c.capability_run_id == runs.c.capability_run_id)
                            & (capability_run.c.task_id == runs.c.task_id),
                        )
                    )
                    .where(runs.c.task_id == task_id)
                    .where(capability_run.c.evidence_scope_id.in_(scope.extra_scope_ids))
                ).scalars()
            )

    retriever = ChunkRetriever(
        retrieval_scope,
        embedder=embedding_backend or StubEmbeddingBackend(),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
        selection_reference_resolved=scope.selection_run_id is not None,
    )

    def lookup_reader(arguments: dict[str, Any]) -> dict[str, Any]:
        with engine.connect() as conn:
            return make_lookup_reader(
                conn,
                task_id=task_id,
                scope_id=scope.evidence_scope_id,
                characterisation_run_id=scope.characterisation_run_id,
                selection_run_id=scope.selection_run_id,
                extraction_run_id=scope.extraction_run_id,
                grouping_run_id=scope.grouping_run_id,
                snapshot_run_ids=terminal_run_ids,
                extra_scope_ids=scope.extra_scope_ids,
            )(arguments)

    if scope.extraction_run_id is None:
        return retriever, None, lookup_reader
    extraction_run_id = scope.extraction_run_id

    def findings_reader(arguments: dict[str, Any]) -> dict[str, Any]:
        with engine.connect() as conn:
            groups: list[dict[str, Any]] | None = None
            if scope.grouping_run_id is not None:
                raw_groups = conn.execute(
                    select(grouping_result.c.groups)
                    .where(grouping_result.c.task_id == task_id)
                    .where(grouping_result.c.evidence_scope_id == scope.evidence_scope_id)
                    .where(grouping_result.c.run_id == scope.grouping_run_id)
                ).scalar_one_or_none()
                groups = _grouping_summary(raw_groups)["groups"]
            return make_findings_reader(
                conn,
                task_id=task_id,
                extraction_run_id=extraction_run_id,
                evidence_scope_id=scope.evidence_scope_id,
                grouping_groups=groups,
            )(arguments)

    return retriever, findings_reader, lookup_reader


def _fill_resolved_labels(
    conn: Connection, *, task_id: uuid.UUID, docs: dict[str, dict[str, Any]]
) -> None:
    """Give an unlabelled document the label resolver's labels, in place.

    A document inherited from a linked Evidence search task is neither
    classified nor appraised again in the longlist scope (task 045, S6); its
    labels are read across through the resolver, the same one the citations
    use. Without this the retriever would read it as unappraised, and the
    citation floor would refuse a citation to it.
    """
    missing = {
        uuid.UUID(tss_id): doc
        for tss_id, doc in docs.items()
        if doc.get("appraisal_tier") is None or doc.get("primary_evidence_type") is None
    }
    if not missing:
        return
    labels = labels_for_snapshots(conn, task_id=task_id, tss_ids=set(missing))
    for tss_id, doc in missing.items():
        label = labels.get(tss_id)
        if label is None:
            continue
        if doc.get("appraisal_tier") is None and label.quality_score is not None:
            doc["appraisal_tier"] = str(label.quality_score)
        if doc.get("primary_evidence_type") is None and label.evidence_type is not None:
            doc["primary_evidence_type"] = label.evidence_type
