"""Walking-skeleton end-to-end thread.

Smoke command: python -m policy_atlas.skeleton

Creates a project + run, ingests a synthetic source, creates a screening scope,
then walks the mandatory EB spine acquire(search) → screen → classify → appraise
→ ingest(fetch) → synthesise, with characterise/select/extract/group as
demo-discretionary legs over the same scope. It renders the landscape, selection,
extraction, synthesis summaries and the event log.
All gates approved; see ADR 0001 and contract.md.
"""

import functools
import os
import time
import uuid
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from langfuse import Langfuse
from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection

from policy_atlas import events, search_generation, search_live, search_loop, tracing
from policy_atlas.acquire import SearchBackend
from policy_atlas.classification_backend import (
    ClassificationBackend,
    OpenAIClassificationBackend,
    StubClassificationBackend,
)
from policy_atlas.db import get_engine
from policy_atlas.embeddings import EmbeddingBackend, OpenAIEmbeddingBackend, StubEmbeddingBackend
from policy_atlas.extraction_backend import (
    ExtractionBackend,
    OpenAIExtractionBackend,
    StubExtractionBackend,
)
from policy_atlas.fetch_live import LiveDocumentFetcher
from policy_atlas.finding_vetter import FindingVetterBackend
from policy_atlas.fixtures import get_source
from policy_atlas.grounding_judge import (
    GroundingJudgeBackend,
    OpenAIGroundingJudgeBackend,
    StubGroundingJudgeBackend,
)
from policy_atlas.group import GroupClusteringBackendFactory, StubGroupClusteringBackend
from policy_atlas.group_clustering import OpenAIGroupClusteringBackendFactory
from policy_atlas.grouping import (
    OpenAIThemeGroupingBackend,
    StubThemeGroupingBackend,
    ThemeGroupingBackend,
)
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest import ingest_upload
from policy_atlas.ingest_full_text import DocumentFetcher, FixtureFetcher
from policy_atlas.logging import configure_logging
from policy_atlas.plan import Plan, compile
from policy_atlas.ranking import OpenAIRankingBackend, RankingBackend
from policy_atlas.schema import (
    characterisation_result,
    evidence_scope,
    extraction_result,
    grouping_result,
    project,
    project_source_snapshot,
    runs,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    source_tag,
)
from policy_atlas.screen import effective_screen_rows
from policy_atlas.screening_backend import (
    OpenAIScreeningBackend,
    ScreeningBackend,
    StubScreeningBackend,
)
from policy_atlas.search_generation import SearchGenerationBackend
from policy_atlas.select import NON_EVIDENCE_TYPE
from policy_atlas.synthesis_backend import (
    OpenAISynthesisBackend,
    StubSynthesisBackend,
    SynthesisBackend,
)

log = structlog.get_logger()


def select_document_fetcher(live: bool) -> DocumentFetcher:
    """Select the full-text fetcher for the skeleton entrypoint.

    Args:
        live: Whether the operator selected live mode via the skeleton's single
            live flag.

    Returns:
        ``LiveDocumentFetcher`` in live mode, otherwise ``FixtureFetcher``.
    """
    if live:
        fetcher = LiveDocumentFetcher()
        assert fetcher.mode == "live"
        return fetcher
    return FixtureFetcher()


def _log_component_counts(log_entries: list[dict[str, Any]], component: str) -> None:
    """Surface a component's completed-event counts (or note the missing event)."""
    counts = next(
        (
            e["payload"] for e in log_entries
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == component
        ),
        None,
    )
    if counts is None:
        # the component emitted component.failed — the event log below shows it
        log.warning(f"{component}_counts.missing")
    else:
        log.info(f"{component}_counts", **{k: v for k, v in counts.items() if k != "component"})


def _run_component(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    component: str,
    *,
    embedding_backend: EmbeddingBackend,
    theme_grouping_backend: ThemeGroupingBackend,
    langfuse_client: Langfuse | None,
    screening_backend: ScreeningBackend | None = None,
    classification_backend: ClassificationBackend | None = None,
    characterisation_run_id: uuid.UUID | None = None,
    ranking_backend: RankingBackend | None = None,
    selection_run_id: uuid.UUID | None = None,
    extraction_backend: ExtractionBackend | None = None,
    finding_vetter_backend: FindingVetterBackend | None = None,
    extraction_run_id: uuid.UUID | None = None,
    group_clustering_backend: GroupClusteringBackendFactory | None = None,
    grouping_run_id: uuid.UUID | None = None,
    synthesis_backend: SynthesisBackend | None = None,
    grounding_judge_backend: GroundingJudgeBackend | None = None,
    search_backends: list[SearchBackend] | None = None,
    search_generation_backend: SearchGenerationBackend | None = None,
    document_fetcher: DocumentFetcher | None = None,
) -> uuid.UUID:
    """Create a run, compile and record the plan, and execute one scope component.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        scope_id: Evidence scope the component runs over.
        component: Component name, dispatched by the harness.
        embedding_backend: Embedding backend threaded into the harness.
        theme_grouping_backend: Theme grouping backend threaded into the harness.
        langfuse_client: Optional tracing client for the component span.
        screening_backend: Screening backend for ``screen``; unused by other
            components.
        classification_backend: Classification backend for ``classify``;
            unused by other components.
        characterisation_run_id: Explicit characterisation run for ``select``;
            unused by other components.
        ranking_backend: Ranking backend for ``select``; unused by other
            components.
        selection_run_id: Explicit selection run for ``extract``; unused by
            other components.
        extraction_backend: Extraction backend for ``extract``; unused by
            other components.
        finding_vetter_backend: Post-extract finding vetter for ``extract``; unused
            by other components. ``None`` (the default) turns judging off.
        extraction_run_id: Explicit extraction run for ``group``; unused by
            other components.
        group_clustering_backend: Group clustering backend factory for
            ``group``; unused by other components.
        grouping_run_id: Explicit grouping run for ``synthesise``; unused by
            other components.
        synthesis_backend: Synthesis backend for ``synthesise``; unused by
            other components.
        grounding_judge_backend: Grounding judge backend for ``synthesise``;
            unused by other components.
        search_backends: Search backends for ``acquire``; unused by other
            components.
        search_generation_backend: Search generation backend for ``acquire``;
            unused by other components.
        document_fetcher: Fetcher for ``ingest_full_text``; unused by other
            components.

    Returns:
        The created run's id.
    """
    run_id = uuid.uuid4()
    conn.execute(
        runs.insert().values(
            run_id=run_id,
            project_id=project_id,
            status="running",
            started_at=datetime.now(UTC),
        )
    )
    events.append(
        conn, project_id=project_id, run_id=run_id, event_type="run.started", payload={}
    )
    log.info("run.started", run_id=str(run_id), component=component)

    config = compile(
        Plan(
            component=component,
            evidence_scope_id=scope_id,
            characterisation_run_id=characterisation_run_id,
            selection_run_id=selection_run_id,
            extraction_run_id=extraction_run_id,
            grouping_run_id=grouping_run_id,
        )
    )
    plan_payload: dict[str, Any] = {
        "component": config.component,
        "evidence_scope_id": str(config.evidence_scope_id),
    }
    if config.characterisation_run_id is not None:
        plan_payload["characterisation_run_id"] = str(config.characterisation_run_id)
    if config.selection_run_id is not None:
        plan_payload["selection_run_id"] = str(config.selection_run_id)
    if config.extraction_run_id is not None:
        plan_payload["extraction_run_id"] = str(config.extraction_run_id)
    if config.grouping_run_id is not None:
        plan_payload["grouping_run_id"] = str(config.grouping_run_id)
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="plan.compiled",
        payload=plan_payload,
    )
    log.info("plan.compiled", component=config.component)

    with tracing.component_span(
        langfuse_client, run_id=run_id, project_id=project_id, component=component
    ) as run_span:
        # provider unused by scope components but required by the harness signature
        run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            provider=StubEchoProvider(),
            embedding_backend=embedding_backend,
            theme_grouping_backend=theme_grouping_backend,
            screening_backend=screening_backend,
            classification_backend=classification_backend,
            ranking_backend=ranking_backend,
            extraction_backend=extraction_backend,
            finding_vetter_backend=finding_vetter_backend,
            group_clustering_backend=group_clustering_backend,
            synthesis_backend=synthesis_backend,
            grounding_judge_backend=grounding_judge_backend,
            search_backends=search_backends,
            search_generation_backend=search_generation_backend,
            document_fetcher=document_fetcher,
        )
        if component == "screen" and langfuse_client is not None:
            payload = _component_payload(events.read(conn, project_id), "screen", run_id=run_id)
            if payload is not None:
                tracing.screening_score_summary(
                    langfuse_client, payload, root_span=run_span
                )
        if component == "classify" and langfuse_client is not None:
            payload = _component_payload(events.read(conn, project_id), "classify", run_id=run_id)
            if payload is not None:
                tracing.classification_score_summary(
                    langfuse_client, payload, root_span=run_span
                )
        if component == "characterise" and langfuse_client is not None:
            # Scores and trace I/O must attach while the run's span is still the
            # active context.
            payload = _characterise_payload(events.read(conn, project_id), run_id=run_id)
            if payload is not None:
                intent = conn.execute(
                    select(evidence_scope.c.intent).where(
                        evidence_scope.c.evidence_scope_id == scope_id
                    )
                ).scalar_one()
                tracing.score_summary(
                    langfuse_client, payload, intent=intent, root_span=run_span
                )
        if component == "extract" and langfuse_client is not None:
            payload = _extraction_payload(events.read(conn, project_id), run_id=run_id)
            if payload is not None:
                tracing.extraction_score_summary(
                    langfuse_client, payload, root_span=run_span
                )
        if component == "group" and langfuse_client is not None:
            payload = _grouping_payload(events.read(conn, project_id), run_id=run_id)
            if payload is not None:
                tracing.grouping_score_summary(
                    langfuse_client, payload, root_span=run_span
                )
        if component == "synthesise" and langfuse_client is not None:
            payload = _synthesis_payload(events.read(conn, project_id), run_id=run_id)
            if payload is not None:
                tracing.synthesis_score_summary(
                    langfuse_client, payload, root_span=run_span
                )
    return run_id


def _text_basis_distribution(conn: Connection, project_id: uuid.UUID) -> dict[str, int]:
    """Effective text basis per corpus document: the full-text snapshot's when attached,
    else the envelope's.
    """
    full_text_snap = source_snapshot.alias("full_text_snap")
    effective_basis = func.coalesce(full_text_snap.c.text_basis, source_snapshot.c.text_basis)
    rows = conn.execute(
        select(effective_basis.label("text_basis"))
        .select_from(
            project_source_snapshot
            .join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
            .join(
                full_text_snap,
                project_source_snapshot.c.full_text_snapshot_id
                == full_text_snap.c.source_snapshot_id,
                isouter=True,
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall()
    distribution: dict[str, int] = {}
    for row in rows:
        distribution[row.text_basis] = distribution.get(row.text_basis, 0) + 1
    return distribution


def _component_payload(
    log_entries: list[dict[str, Any]], component: str, *, run_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    """Return one component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    pass ``run_id`` to pin the payload to one run rather than the latest.
    """
    return next(
        (
            e["payload"] for e in reversed(log_entries)
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == component
            and (run_id is None or e["run_id"] == run_id)
        ),
        None,
    )


def _component_payload_or_raise(
    conn: Connection,
    project_id: uuid.UUID,
    component: str,
    *,
    run_id: uuid.UUID,
) -> dict[str, Any]:
    payload = _component_payload(events.read(conn, project_id), component, run_id=run_id)
    if payload is None:
        raise RuntimeError(f"{component} component completed payload missing")
    return payload


def _characterise_payload(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    """Return the characterise component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    pass ``run_id`` to pin the payload to one run rather than the latest.
    """
    return _component_payload(log_entries, "characterise", run_id=run_id)


def _render_landscape(log_entries: list[dict[str, Any]]) -> None:
    """Render the characterise landscape summary from the event log, human-readably."""
    payload = _characterise_payload(log_entries)
    if payload is None:
        # the component emitted component.failed — the event log below shows it
        log.warning("landscape.missing")
        return

    log.info("landscape.base", **payload["coverage"]["base_counts"])
    for name, dist in payload["coverage"]["distributions"].items():
        if name == "tags":
            continue
        log.info(
            "landscape.distribution",
            name=name,
            base=payload["coverage"]["base"],
            values=dist,
        )
    log.info(
        "landscape.tags",
        **{k: sum(v.values()) for k, v in payload["coverage"]["distributions"]["tags"].items()},
    )
    log.info("landscape.rates", **payload["coverage"]["rates"])
    for theme in payload["themes"]:
        log.info(
            "landscape.theme",
            name=theme["name"],
            size=theme["size"],
            description=theme["description"],
        )
    log.info("landscape.unclustered", **payload["unclustered"])
    log.info("landscape.flags", flags=payload["flags"])
    log.info("landscape.provenance", **payload["provenance"])


def _selection_payload(log_entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the select component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first.
    """
    return next(
        (
            e["payload"] for e in reversed(log_entries)
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == "select"
        ),
        None,
    )


def _render_selection(
    log_entries: list[dict[str, Any]], selected: list[dict[str, Any]]
) -> None:
    """Render the select summary from the event log and the persisted selection row.

    Args:
        log_entries: Full project event log.
        selected: The persisted ``selection_result.selected`` rationale records
            (per-doc detail the event payload only summarizes).
    """
    payload = _selection_payload(log_entries)
    if payload is None:
        # the component emitted component.failed — the event log below shows it
        log.warning("selection.missing")
        return

    log.info("selection.base", **payload["base"])
    for stratum in payload["strata"]:
        log.info(
            "selection.stratum",
            name=stratum["name"],
            candidate_count=stratum["candidate_count"],
            allocated_count=stratum["allocated_count"],
            selected_count=stratum["selected_count"],
            full_text_share_candidates=stratum["full_text_share_candidates"],
            full_text_share_selected=stratum["full_text_share_selected"],
        )
    log.info("selection.selected", **payload["selected"])
    log.info("selection.excluded", **payload["excluded"])
    log.info("selection.flags", flags=payload["flags"])
    log.info("selection.provenance", **payload["provenance"])

    for record in selected:
        fields: dict[str, Any] = {
            "pss_id": record["pss_id"],
            "stratum": record["stratum"],
            "reason": record["reason"],
            "composite": record["composite"],
        }
        for key in ("llm_score", "llm_reason", "rank_fallback"):
            if key in record:
                fields[key] = record[key]
        log.info("selection.selected_doc", **fields)


def _extraction_payload(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    """Return the extract component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    pass ``run_id`` to pin the payload to one run rather than the latest.
    """
    return _component_payload(log_entries, "extract", run_id=run_id)


def _render_extraction(log_entries: list[dict[str, Any]]) -> None:
    """Render the extract summary from the event log, human-readably."""
    payload = _extraction_payload(log_entries)
    if payload is None:
        # the component emitted component.failed — the event log below shows it
        log.warning("extraction.missing")
        return

    # The 021 per-profile payload shape: counts/provenance/doc statuses live
    # under per-profile blocks (this renderer is demo-only, read tolerantly).
    counts = payload.get("counts", {})
    log.info("extraction.counts", selected=counts.get("selected"))
    for profile_id, block in (counts.get("profiles") or {}).items():
        findings = block.get("findings") if isinstance(block, dict) else None
        if isinstance(findings, dict):
            log.info("extraction.findings", profile=profile_id, **findings)
    if isinstance(counts.get("basis"), dict):
        log.info("extraction.basis", **counts["basis"])
    for doc in payload.get("docs", []):
        for profile_id, doc_block in (doc.get("profiles") or {}).items():
            log.info(
                "extraction.doc",
                pss_id=doc.get("pss_id"),
                profile=profile_id,
                status=doc_block.get("status"),
                basis=doc.get("basis"),
                finding_count=doc_block.get("finding_count"),
                reused=doc_block.get("reused"),
                error=doc_block.get("error"),
            )
    log.info("extraction.flags", flags=payload.get("flags"))
    # The full provenance map is in the DB row; only the headline fields here.
    for profile_id, prov in (payload.get("provenance", {}).get("profiles") or {}).items():
        if isinstance(prov, dict):
            log.info(
                "extraction.provenance",
                profile=profile_id,
                fingerprint=prov.get("fingerprint"),
                model=prov.get("model"),
                prompt=prov.get("prompt"),
                mode=prov.get("mode"),
            )


def _grouping_payload(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    """Return the group component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    pass ``run_id`` to pin the payload to one run rather than the latest.
    """
    return _component_payload(log_entries, "group", run_id=run_id)


def _render_grouping(log_entries: list[dict[str, Any]], *, run_id: uuid.UUID | None = None) -> None:
    """Render the group summary from the event log, human-readably."""
    payload = _grouping_payload(log_entries, run_id=run_id)
    if payload is None:
        # the component emitted component.failed — the event log below shows it
        log.warning("grouping.missing")
        return

    # The 022 multi-facet summary shape: groups/residuals/counts/flags are
    # facet-keyed (this renderer is demo-only, read tolerantly).
    log.info(
        "grouping.facets",
        facets=payload.get("facets", [payload.get("facet")]),
        facet_source=payload.get("facet_source"),
    )
    groups = payload.get("groups", {})
    facet_groups = groups if isinstance(groups, dict) else {"": groups}
    for facet, group_list in facet_groups.items():
        if not isinstance(group_list, list):
            continue
        for group in group_list:
            if not isinstance(group, dict):
                continue
            log.info(
                "grouping.group",
                facet=facet or group.get("facet"),
                group_id=group.get("group_id"),
                label=group.get("label"),
                size=group.get("size"),
                value_count=group.get("value_count"),
                direction_spread=group.get("direction_spread"),
            )
    log.info("grouping.residuals", residuals=payload.get("residuals"))
    log.info("grouping.counts", counts=payload.get("counts"))
    log.info("grouping.flags", flags=payload.get("flags"))
    # The full provenance map is in the DB row; only the headline fields here.
    provenance = payload.get("provenance", {})
    log.info(
        "grouping.provenance",
        prompt_version=provenance.get("prompt_version"),
        model=provenance.get("model"),
        mode=provenance.get("mode"),
        facets=provenance.get("facets"),
    )


def _synthesis_payload(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID
) -> dict[str, Any] | None:
    """Return the synthesise component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    ``run_id`` pins the payload to one run.
    """
    return _component_payload(log_entries, "synthesise", run_id=run_id)


def _render_synthesis(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID, profile: str
) -> None:
    """Render the synthesise summary from the event log, human-readably."""
    payload = _synthesis_payload(log_entries, run_id=run_id)
    if payload is None:
        # the component emitted component.failed — the event log below shows it
        log.warning("synthesis.missing", profile=profile)
        return

    counts = payload["counts"]
    log.info(
        "synthesis.summary",
        profile=profile,
        artefact_id=payload["artefact_id"],
        section_count=payload["section_count"],
        claims_total=counts["claims_total"],
        citations_verified=counts["citations_verified"],
        citations_unverified=counts["citations_unverified"],
        chunk_claims_rejected=counts["chunk_claims_rejected"],
        gap_claims_degraded=counts["gap_claims_degraded"],
    )
    log.info("synthesis.flags", profile=profile, flags=payload["flags"])


def main() -> None:
    """Run the walking-skeleton thread end to end and log the result."""
    configure_logging()
    log.info("skeleton.start")

    # Egress is the product — a configured key on the demo entrypoint is the
    # operator's live intent; suite/library defaults stay stub. Stubs are
    # never traced.
    live = bool(os.environ.get("OPENAI_API_KEY"))
    langfuse_client = tracing.get_langfuse() if live else None
    embedding_backend: EmbeddingBackend
    theme_grouping_backend: ThemeGroupingBackend
    screening_backend: ScreeningBackend
    classification_backend: ClassificationBackend
    ranking_backend: RankingBackend | None
    extraction_backend: ExtractionBackend
    group_clustering_backend: GroupClusteringBackendFactory
    search_backends: list[SearchBackend] | None
    search_generation_backend: SearchGenerationBackend | None
    selected_document_fetcher = select_document_fetcher(live)
    if live:
        assert selected_document_fetcher.mode == "live"
    document_fetcher = selected_document_fetcher
    if live:
        embedding_backend = OpenAIEmbeddingBackend()
        theme_grouping_backend = OpenAIThemeGroupingBackend()
        # Tracing lives inside OpenAIScreeningBackend itself — no wrapper
        # class, unlike the embedding/grouping backends below.
        screening_backend = OpenAIScreeningBackend(langfuse_client=langfuse_client)
        # Tracing lives inside OpenAIClassificationBackend itself — no wrapper
        # class, unlike the embedding/grouping backends below.
        classification_backend = OpenAIClassificationBackend(langfuse_client=langfuse_client)
        # Tracing lives inside OpenAIRankingBackend itself — no wrapper class,
        # unlike the embedding/grouping backends below.
        ranking_backend = OpenAIRankingBackend(langfuse_client=langfuse_client)
        # Tracing lives inside OpenAIExtractionBackend itself — no wrapper
        # class, unlike the embedding/grouping backends below.
        extraction_backend = OpenAIExtractionBackend(langfuse_client=langfuse_client)
        group_clustering_backend = OpenAIGroupClusteringBackendFactory(
            langfuse_client=langfuse_client
        )
        search_backends = cast(list[SearchBackend], search_live.live_search_backends())
        search_generation_backend = search_generation.OpenAISearchGenerationBackend(
            langfuse_client=langfuse_client
        )
        if langfuse_client is not None:
            embedding_backend = tracing.TracedEmbeddingBackend(
                embedding_backend, langfuse_client
            )
            theme_grouping_backend = tracing.TracedThemeGroupingBackend(
                theme_grouping_backend, langfuse_client
            )
    else:
        embedding_backend = StubEmbeddingBackend()
        theme_grouping_backend = StubThemeGroupingBackend()
        screening_backend = StubScreeningBackend()
        classification_backend = StubClassificationBackend()
        ranking_backend = None
        extraction_backend = StubExtractionBackend()
        group_clustering_backend = StubGroupClusteringBackend()
        search_backends = None
        search_generation_backend = None
    log.info(
        "skeleton.backends",
        mode="live" if live else "stub",
        traced=langfuse_client is not None,
        ranking="llm_rerank_v1" if live else "coverage_stratified_v1",
        search="live" if live else "fixture",
        fetch="live" if live else "fixture",
    )

    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))  # connection liveness check

        # Create project
        project_id = uuid.uuid4()
        conn.execute(
            project.insert().values(
                project_id=project_id,
                created_at=datetime.now(UTC),
            )
        )
        log.info("project.created", project_id=str(project_id))

        # Ingest synthetic source into the project corpus
        src = get_source("syn-001")
        ingest_upload(
            conn,
            project_id=project_id,
            chunks=list(src.chunks),
            source_locator="syn-001",
            # _stub_systematic_review steers the classify stub so appraise scores it (5)
            metadata={
                "synthetic": True,
                "abstract": "A synthetic policy document.",
                "_stub_systematic_review": True,
            },
            text_basis="full_text",
            embedder=embedding_backend,
        )
        # The on-topic appraised seed for the synthesise demo (task 013): the
        # acquired fixture docs classify Unknown (no sentinels) and are never
        # appraised, so this uploaded full-text review is what the chunk lane
        # can honestly cite under the appraised-evidence rule.
        seed_src = get_source("syn-002")
        ingest_upload(
            conn,
            project_id=project_id,
            chunks=list(seed_src.chunks),
            source_locator="syn-002",
            metadata={
                "synthetic": True,
                "title": "Synthetic review of housing affordability policies",
                "abstract": "A synthetic systematic review of housing affordability policies.",
                "_stub_systematic_review": True,
            },
            text_basis="full_text",
            embedder=embedding_backend,
        )
        log.info("source.ingested")

        # Create screening scope
        scope_id = uuid.uuid4()
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=scope_id,
                project_id=project_id,
                intent="What policies address housing affordability?",
                context={"theme": "housing"},
                created_at=datetime.now(UTC),
            )
        )
        log.info("evidence_scope.created", scope_id=str(scope_id))

        run_component = functools.partial(
            _run_component,
            conn,
            project_id,
            scope_id,
            embedding_backend=embedding_backend,
            theme_grouping_backend=theme_grouping_backend,
            langfuse_client=langfuse_client,
            screening_backend=screening_backend,
            classification_backend=classification_backend,
            search_backends=search_backends,
            search_generation_backend=search_generation_backend,
            document_fetcher=document_fetcher,
        )

        # Walk the mandatory spine over the same scope. Acquire runs first —
        # both fixture backends over the mixed corpus (this upload + acquired sets).
        rapid_start = time.monotonic()
        run_component("acquire")

        # rapid: the first screen leg runs entirely on stage-1 rows. The
        # discretionary stage-2 full-text confirmation leg runs later, after
        # ingest_full_text has full text to confirm against.
        log.info("screen.profile", profile="rapid", stage=1)
        run_component("screen")
        rapid_elapsed = time.monotonic() - rapid_start
        log.info("search.rapid_leg_elapsed", wall_clock_s=rapid_elapsed)
        log.info(
            "screen.rapid_profile_stage2_skipped",
            reason="rapid profile: stage-2 full-text confirmation not run yet",
        )

        confident_after_rapid = search_loop.confident_relevant_count(
            conn,
            project_id=project_id,
            scope_id=scope_id,
        )
        if search_loop.should_escalate(conn, project_id=project_id, scope_id=scope_id):
            log.info(
                "search.rapid_thin_escalation",
                confident_relevant=confident_after_rapid,
                threshold=search_loop.THIN_CONFIDENT_RELEVANT,
            )
        else:
            log.info(
                "search.deep_profile_demo",
                confident_relevant=confident_after_rapid,
                threshold=search_loop.THIN_CONFIDENT_RELEVANT,
            )

        scope_context = dict(
            conn.execute(
                select(evidence_scope.c.context).where(
                    evidence_scope.c.evidence_scope_id == scope_id
                )
            ).scalar_one()
        )
        raw_search_context = scope_context.get("search")
        search_context = (
            dict(raw_search_context) if isinstance(raw_search_context, dict) else {}
        )
        search_context["depth"] = "deep"
        directed_context = {**scope_context, "search": search_context}
        conn.execute(
            evidence_scope.update()
            .where(evidence_scope.c.evidence_scope_id == scope_id)
            .values(context=directed_context)
        )

        def acquire_deep_round() -> dict[str, Any]:
            acquire_run_id = run_component("acquire")
            return _component_payload_or_raise(
                conn,
                project_id,
                "acquire",
                run_id=acquire_run_id,
            )

        def screen_deep_round() -> dict[str, Any]:
            screen_run_id = run_component("screen")
            return _component_payload_or_raise(
                conn,
                project_id,
                "screen",
                run_id=screen_run_id,
            )

        deep_summary = search_loop.run_deep_rounds(
            conn,
            project_id=project_id,
            scope_id=scope_id,
            acquire_round=acquire_deep_round,
            screen_round=screen_deep_round,
            start_round=2,
        )
        for round_summary in deep_summary["rounds"]:
            log.info("search.deep_round_summary", **round_summary)
        log.info(
            "search.deep_episode_completed",
            stop_condition=deep_summary["stop_condition"],
            confident_relevant=deep_summary["confident_relevant"],
            wall_clock_s=deep_summary["wall_clock_s"],
            suggest_grounded_screened_out=deep_summary[
                "suggest_grounded_screened_out"
            ],
        )

        # Effective rows (screen.effective_screen_rows) drive the summaries below,
        # never raw attempt/stage history — a demoted or confirmed doc must be
        # read once, at its effective status. Raw-vs-effective counts are logged
        # separately (screening_attempt_history) so history stays visible.
        effective_screening = effective_screen_rows()
        screening_results = conn.execute(
            select(
                effective_screening.c.status,
                effective_screening.c.screen_basis,
                effective_screening.c.screen_decision_confidence,
            ).where(effective_screening.c.project_id == project_id)
        ).fetchall()
        raw_screening_row_count = conn.execute(
            select(func.count())
            .select_from(source_screening_result)
            .where(source_screening_result.c.project_id == project_id)
        ).scalar_one()
        log.info(
            "screening_attempt_history",
            raw_row_count=raw_screening_row_count,
            effective_row_count=len(screening_results),
        )

        run_component("classify")

        classify_results = conn.execute(
            select(
                source_classification_result.c.primary_evidence_type,
            ).where(source_classification_result.c.project_id == project_id)
        ).fetchall()

        run_component("appraise")

        appraise_results = conn.execute(
            select(
                source_appraisal_result.c.quality_score,
                source_appraisal_result.c.rubric_version,
            ).where(source_appraisal_result.c.project_id == project_id)
        ).fetchall()

        log.info(
            "text_basis_distribution_before",
            **_text_basis_distribution(conn, project_id),
        )

        run_component("ingest_full_text")

        log.info(
            "text_basis_distribution_after",
            **_text_basis_distribution(conn, project_id),
        )

        # deep: the second screen leg — stage-2 full-text confirmation over the
        # stage-1-relevant, now-ingested docs. Same read-modify-write directive
        # pattern as the second group run below: preserve existing scope
        # context keys.
        log.info("screen.profile", profile="deep", stage=2)
        scope_context = conn.execute(
            select(evidence_scope.c.context).where(
                evidence_scope.c.evidence_scope_id == scope_id
            )
        ).scalar_one()
        directed_context = {**scope_context, "screening": {"stage": 2}}
        conn.execute(
            evidence_scope.update()
            .where(evidence_scope.c.evidence_scope_id == scope_id)
            .values(context=directed_context)
        )
        stage2_run_id = run_component("screen")
        stage2_payload = _component_payload(
            events.read(conn, project_id), "screen", run_id=stage2_run_id
        )
        if stage2_payload is None:
            # the component emitted component.failed — the event log below shows it
            log.warning("screen.stage2_counts.missing")
        else:
            log.info(
                "screen.stage2_counts",
                stage2_screened=stage2_payload.get("stage2_screened"),
                confirmed=stage2_payload.get("confirmed"),
                demoted=stage2_payload.get("demoted"),
                failed=stage2_payload.get("failed"),
                skipped_no_fulltext=stage2_payload.get("skipped_no_fulltext"),
            )

        # Effective rows now span both stages — recompute the summary read used
        # by the demo's screening_result output below so it shows the mixed
        # stage-1/stage-2 grain rather than the pre-deep-profile snapshot above.
        screening_results = conn.execute(
            select(
                effective_screening.c.status,
                effective_screening.c.screen_basis,
                effective_screening.c.screen_decision_confidence,
                effective_screening.c.screen_stage,
            ).where(effective_screening.c.project_id == project_id)
        ).fetchall()

        char_run_id = run_component("characterise")

        char_row = conn.execute(
            select(characterisation_result).where(
                characterisation_result.c.project_id == project_id
            )
        ).one_or_none()

        # Pick the demo boost tag: most common source_tag.tag for this project
        # not asserted by characterise itself (deterministic order: count desc,
        # tag asc); fall back to any tag if none match.
        tag_counts_query = (
            select(source_tag.c.tag, func.count())
            .where(source_tag.c.project_id == project_id)
            .group_by(source_tag.c.tag)
            .order_by(func.count().desc(), source_tag.c.tag.asc())
        )
        tag_counts = conn.execute(
            tag_counts_query.where(source_tag.c.asserted_by != "characterise")
        ).fetchall()
        if not tag_counts:
            tag_counts = conn.execute(tag_counts_query).fetchall()
        boost_tag = tag_counts[0].tag if tag_counts else None
        log.info("select.demo_boost_tag", tag=boost_tag)

        # Plan finding 7: budget + tag boost alone can't guarantee the live
        # extract run sees both bases — pin one full-text and one abstract-only
        # doc as must-includes, deterministically (min pss_id per basis).
        # Effective-relevant via the helper — same screened-in-scope rule as
        # characterise.screened_sources (select's candidate set).
        effective_pins = effective_screen_rows()
        basis_pin_rows = conn.execute(
            select(
                project_source_snapshot.c.project_source_snapshot_id,
                project_source_snapshot.c.full_text_status,
                project_source_snapshot.c.full_text_snapshot_id,
                source_snapshot.c.metadata,
            )
            .select_from(
                project_source_snapshot
                .join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
                .join(
                    effective_pins,
                    (
                        project_source_snapshot.c.project_source_snapshot_id
                        == effective_pins.c.project_source_snapshot_id
                    )
                    & (project_source_snapshot.c.project_id == effective_pins.c.project_id),
                )
                .join(
                    source_classification_result,
                    project_source_snapshot.c.project_source_snapshot_id
                    == source_classification_result.c.project_source_snapshot_id,
                )
            )
            .where(project_source_snapshot.c.project_id == project_id)
            .where(effective_pins.c.status == "relevant")
            .where(source_classification_result.c.primary_evidence_type != NON_EVIDENCE_TYPE)
            .order_by(project_source_snapshot.c.project_source_snapshot_id)
        ).fetchall()

        ft_pin: uuid.UUID | None = None
        ab_pin: uuid.UUID | None = None
        for row in basis_pin_rows:
            if ft_pin is None and row.full_text_status == "ingested":
                ft_pin = row.project_source_snapshot_id
            abstract = row.metadata.get("abstract")
            if (
                ab_pin is None
                and row.full_text_snapshot_id is None
                and isinstance(abstract, str)
                and abstract
            ):
                ab_pin = row.project_source_snapshot_id
            if ft_pin is not None and ab_pin is not None:
                break

        # Plan finding 5: the fixture corpus is ~24 docs, so the default budget
        # (25) would leave zero contested strata — pin a small budget and a
        # boost on the chosen tag so reranking has something to do. A tagless
        # corpus gets the budget only (a None tag would fail the directive closed).
        selection_directive: dict[str, Any] = {"budget": 8}
        if boost_tag is not None:
            selection_directive["boosts"] = [
                {"match": {"tag_type": "topic_theme", "tag": boost_tag}, "weight": 3.0}
            ]
        if ft_pin is not None and ab_pin is not None:
            selection_directive["must_include_ids"] = [str(ft_pin), str(ab_pin)]
            log.info("select.must_include_pins", full_text=str(ft_pin), abstract_only=str(ab_pin))
        else:
            log.warning(
                "select.must_include_pins_incomplete",
                full_text=str(ft_pin) if ft_pin is not None else None,
                abstract_only=str(ab_pin) if ab_pin is not None else None,
            )
        scope_context = dict(
            conn.execute(
                select(evidence_scope.c.context).where(
                    evidence_scope.c.evidence_scope_id == scope_id
                )
            ).scalar_one()
        )
        conn.execute(
            evidence_scope.update()
            .where(evidence_scope.c.evidence_scope_id == scope_id)
            .values(context={**scope_context, "selection": selection_directive})
        )
        log.info("select.directive", budget=8, boost_tag=boost_tag)

        select_run_id = run_component(
            "select",
            characterisation_run_id=char_run_id,
            ranking_backend=ranking_backend,
        )

        selection_row = conn.execute(
            select(selection_result).where(selection_result.c.project_id == project_id)
        ).one_or_none()

        selected_bases = {
            record["text_basis"]
            for record in (selection_row.selected if selection_row is not None else [])
        }
        if not {"full_text", "abstract_only"} <= selected_bases:
            log.error("extract.mixed_basis_missing", bases=sorted(selected_bases))
            if live:
                raise RuntimeError(
                    "live extract run requires both text bases in the selected set"
                )

        extract_run_id = run_component(
            "extract",
            selection_run_id=select_run_id,
            extraction_backend=extraction_backend,
        )

        extraction_row = conn.execute(
            select(extraction_result).where(extraction_result.c.project_id == project_id)
        ).one_or_none()

        group_run_id = run_component(
            "group",
            extraction_run_id=extract_run_id,
            group_clustering_backend=group_clustering_backend,
        )

        # Second group run demonstrating the directive path (the selection-
        # directive update precedent): re-group the same extraction run on an
        # explicit facet, preserving the existing scope context keys.
        scope_context = conn.execute(
            select(evidence_scope.c.context).where(
                evidence_scope.c.evidence_scope_id == scope_id
            )
        ).scalar_one()
        directed_context = {**scope_context, "grouping": {"facets": ["outcome"]}}
        conn.execute(
            evidence_scope.update()
            .where(evidence_scope.c.evidence_scope_id == scope_id)
            .values(context=directed_context)
        )
        log.info("group.directive", facet="outcome")

        group_directive_run_id = run_component(
            "group",
            extraction_run_id=extract_run_id,
            group_clustering_backend=group_clustering_backend,
        )

        grouping_rows = conn.execute(
            select(grouping_result.c.grouping_result_id).where(
                grouping_result.c.project_id == project_id
            )
        ).fetchall()

        # Synthesise: EB's terminal component, demoed over four profiles that
        # walk the substrate-conditional flow from a rapid (no-reference) run
        # up through the full resolved chain — same live-switch pattern as
        # the other backends above.
        synthesis_backend: SynthesisBackend
        grounding_judge_backend: GroundingJudgeBackend
        if live:
            synthesis_backend = OpenAISynthesisBackend(langfuse_client=langfuse_client)
            grounding_judge_backend = OpenAIGroundingJudgeBackend(langfuse_client=langfuse_client)
        else:
            synthesis_backend = StubSynthesisBackend()
            grounding_judge_backend = StubGroundingJudgeBackend()

        # rapid: no run references at all — substrate is the appraised
        # screened-in ingested corpus only.
        log.info("synthesise.profile", profile="rapid")
        synth_rapid_run_id = run_component(
            "synthesise",
            synthesis_backend=synthesis_backend,
            grounding_judge_backend=grounding_judge_backend,
        )
        _render_synthesis(
            events.read(conn, project_id), run_id=synth_rapid_run_id, profile="rapid"
        )

        # characterisation_only: characterisation resolves nothing further.
        log.info(
            "synthesise.profile",
            profile="characterisation_only",
            characterisation_run_id=str(char_run_id),
        )
        synth_characterisation_run_id = run_component(
            "synthesise",
            characterisation_run_id=char_run_id,
            synthesis_backend=synthesis_backend,
            grounding_judge_backend=grounding_judge_backend,
        )
        _render_synthesis(
            events.read(conn, project_id),
            run_id=synth_characterisation_run_id,
            profile="characterisation_only",
        )

        # characterisation_selection: selection given alone — characterisation
        # resolves transitively.
        log.info(
            "synthesise.profile",
            profile="characterisation_selection",
            selection_run_id=str(select_run_id),
        )
        synth_selection_run_id = run_component(
            "synthesise",
            selection_run_id=select_run_id,
            synthesis_backend=synthesis_backend,
            grounding_judge_backend=grounding_judge_backend,
        )
        _render_synthesis(
            events.read(conn, project_id),
            run_id=synth_selection_run_id,
            profile="characterisation_selection",
        )

        # full_chain: the first group run given alone — everything upstream
        # resolves transitively.
        log.info(
            "synthesise.profile", profile="full_chain", grouping_run_id=str(group_run_id)
        )
        synth_full_chain_run_id = run_component(
            "synthesise",
            grouping_run_id=group_run_id,
            synthesis_backend=synthesis_backend,
            grounding_judge_backend=grounding_judge_backend,
        )
        _render_synthesis(
            events.read(conn, project_id),
            run_id=synth_full_chain_run_id,
            profile="full_chain",
        )

        log_entries = events.read(conn, project_id)

    # Per-backend acquire counts — makes the authentic-shapes path visible
    _log_component_counts(log_entries, "acquire")

    # Screen-basis distribution: missing abstracts/snippets flow the title_only
    # fail-open path — visible here, per contract.
    basis_distribution: dict[str, int] = {}
    for row in screening_results:
        if row.screen_basis is not None:
            basis_distribution[row.screen_basis] = basis_distribution.get(row.screen_basis, 0) + 1
    log.info("screen_basis_distribution", **basis_distribution)

    for row in screening_results:
        log.info("screening_result", status=row.status, basis=row.screen_basis,
                 confidence=row.screen_decision_confidence, screen_stage=row.screen_stage)

    for row in classify_results:
        log.info("classification_result", evidence_type=row.primary_evidence_type)

    for row in appraise_results:
        log.info("appraisal_result", quality_score=row.quality_score,
                 rubric_version=row.rubric_version)

    # Surface the skip counts so both the scored and skipped paths are visible
    _log_component_counts(log_entries, "appraise")
    _log_component_counts(log_entries, "ingest_full_text")

    for entry in log_entries:
        log.info("event_log_entry", sequence=entry["sequence"], event_type=entry["event_type"])

    _render_landscape(log_entries)
    log.info("characterisation_row", present=char_row is not None)

    _render_selection(
        log_entries, selection_row.selected if selection_row is not None else []
    )
    log.info("selection_row", present=selection_row is not None)

    _render_extraction(log_entries)
    log.info("extraction_row", present=extraction_row is not None)

    _render_grouping(log_entries, run_id=group_run_id)
    _render_grouping(log_entries, run_id=group_directive_run_id)
    log.info("grouping_row_present", present=len(grouping_rows) > 0, count=len(grouping_rows))

    if live:
        # Finding 5's assert-and-log: a live run that never actually calls the
        # ranking backend (e.g. no contested strata) is a silent regression.
        selection_payload = _selection_payload(log_entries)
        if selection_payload is None:
            log.warning("select.rerank_check_skipped")
        else:
            used = selection_payload["provenance"]["call_budget"]["used"]
            if used == 0:
                log.error("select.rerank_never_fired", used=used)
            else:
                log.info("select.rerank_fired", used=used)

    # Scores attach inside the characterise run's span (_run_component); only flush here.
    tracing.flush(langfuse_client)

    log.info("skeleton.done")


if __name__ == "__main__":
    main()
