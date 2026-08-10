"""Read-only, turn-scoped evidence readers for project chat.

``resolve_terminal_run_components`` reconstructs a completed walk's terminal
component references once at chat-turn reservation time.  ``search_chunks`` is
deliberately scope-wide: it searches the shared screened corpus.  The other
matrix rows are bounded to that turn-start walk: ``query_findings`` and the
selection/characterisation/grouping lookups use their resolved component ids;
appraisal, classification, tags, screening, coverage, ``docs_by_tag``, and
``tag_aggregate`` are snapshot-bound to every component-run id in that walk.
All of those currently carry a creating-run key, so no structured lookup kind
is scope-wide-by-necessity.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.embeddings import EmbeddingBackend, StubEmbeddingBackend
from policy_atlas.core.schema import capability_run, grouping_result, runs, selection_result
from policy_atlas.evidence_base.synthesis.synthesis_tools import (
    ChunkRetriever,
    PassThroughChunkReranker,
    SynthesisDirective,
    _grouping_summary,
    build_retrieval_scope,
    make_findings_reader,
    make_lookup_reader,
)


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
    """

    capability_run_id: uuid.UUID
    evidence_scope_id: uuid.UUID
    characterisation_run_id: uuid.UUID | None
    selection_run_id: uuid.UUID | None
    extraction_run_id: uuid.UUID | None
    grouping_run_id: uuid.UUID | None


def resolve_terminal_run_components(
    engine: Engine, *, project_id: uuid.UUID
) -> ResolvedRunScope | None:
    """Resolve the latest completed walk's terminal component attempts.

    The reduction intentionally mirrors ``runtime.continuation_state.build``:
    join ``run.started`` events to the walk's run rows, order by event sequence,
    then let the latest event win for each component and registry component.

    Args:
        engine: Database engine used for this short-lived read.
        project_id: Project owning the completed walk.

    Returns:
        The resolved terminal scope, or ``None`` when no completed walk exists.
    """
    with engine.connect() as conn:
        cap_row = conn.execute(
            select(capability_run)
            .where(capability_run.c.project_id == project_id)
            .where(capability_run.c.status.in_(("succeeded", "degraded")))
            .order_by(
                capability_run.c.started_at.desc(), capability_run.c.capability_run_id.desc()
            )
            .limit(1)
        ).one_or_none()
        if cap_row is None:
            return None
        cap = dict(cap_row._mapping)
        event_rows = events.read(conn, project_id)
        run_rows = [
            dict(row._mapping)
            for row in conn.execute(
                select(runs)
                .where(runs.c.project_id == project_id)
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
    project_id: uuid.UUID,
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
        project_id: Project owning all returned evidence.
        embedding_backend: Query embedding seam.  The zero-egress stub is the
            default until the chat service injects its configured live backend.

    Returns:
        Chunk retriever, findings reader (when extraction resolved), and lookup reader.
    """
    with engine.connect() as conn:
        selected_pss_ids: set[uuid.UUID] = set()
        if scope.selection_run_id is not None:
            selected = conn.execute(
                select(selection_result.c.selected)
                .where(selection_result.c.project_id == project_id)
                .where(selection_result.c.evidence_scope_id == scope.evidence_scope_id)
                .where(selection_result.c.run_id == scope.selection_run_id)
            ).scalar_one_or_none()
            if isinstance(selected, list):
                for item in selected:
                    if isinstance(item, dict) and isinstance(item.get("pss_id"), str):
                        try:
                            selected_pss_ids.add(uuid.UUID(item["pss_id"]))
                        except ValueError:
                            continue
        retrieval_scope = build_retrieval_scope(
            conn,
            project_id=project_id,
            scope_id=scope.evidence_scope_id,
            selected_pss_ids=selected_pss_ids,
        )
        terminal_run_ids = set(
            conn.execute(
                select(runs.c.run_id)
                .where(runs.c.project_id == project_id)
                .where(runs.c.capability_run_id == scope.capability_run_id)
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
                project_id=project_id,
                scope_id=scope.evidence_scope_id,
                characterisation_run_id=scope.characterisation_run_id,
                selection_run_id=scope.selection_run_id,
                extraction_run_id=scope.extraction_run_id,
                grouping_run_id=scope.grouping_run_id,
                snapshot_run_ids=terminal_run_ids,
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
                    .where(grouping_result.c.project_id == project_id)
                    .where(grouping_result.c.evidence_scope_id == scope.evidence_scope_id)
                    .where(grouping_result.c.run_id == scope.grouping_run_id)
                ).scalar_one_or_none()
                groups = _grouping_summary(raw_groups)["groups"]
            return make_findings_reader(
                conn,
                project_id=project_id,
                extraction_run_id=extraction_run_id,
                evidence_scope_id=scope.evidence_scope_id,
                grouping_groups=groups,
            )(arguments)

    return retriever, findings_reader, lookup_reader
