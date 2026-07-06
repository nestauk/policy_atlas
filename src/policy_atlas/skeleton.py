"""Walking-skeleton end-to-end thread.

Smoke command: python -m policy_atlas.skeleton

Creates a project + run, ingests a synthetic source, creates a screening scope,
then walks screen → classify → appraise → ingest_full_text → characterise → select
over the same scope, rendering the landscape and selection summaries and the event log.
All gates approved; see ADR 0001 and contract.md.
"""

import functools
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from langfuse import Langfuse
from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection

from policy_atlas import events, tracing
from policy_atlas.db import get_engine
from policy_atlas.embeddings import EmbeddingBackend, OpenAIEmbeddingBackend, StubEmbeddingBackend
from policy_atlas.fixtures import get_source
from policy_atlas.grouping import GroupingBackend, OpenAIGroupingBackend, StubGroupingBackend
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest import ingest_upload
from policy_atlas.logging import configure_logging
from policy_atlas.plan import Plan, compile
from policy_atlas.ranking import OpenAIRankingBackend, RankingBackend
from policy_atlas.schema import (
    characterisation_result,
    evidence_scope,
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

log = structlog.get_logger()


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
    grouping_backend: GroupingBackend,
    langfuse_client: Langfuse | None,
    characterisation_run_id: uuid.UUID | None = None,
    ranking_backend: RankingBackend | None = None,
) -> uuid.UUID:
    """Create a run, compile and record the plan, and execute one scope component.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        scope_id: Evidence scope the component runs over.
        component: Component name, dispatched by the harness.
        embedding_backend: Embedding backend threaded into the harness.
        grouping_backend: Grouping backend threaded into the harness.
        langfuse_client: Optional tracing client for the component span.
        characterisation_run_id: Explicit characterisation run for ``select``;
            unused by other components.
        ranking_backend: Ranking backend for ``select``; unused by other
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
        )
    )
    plan_payload: dict[str, Any] = {
        "component": config.component,
        "evidence_scope_id": str(config.evidence_scope_id),
    }
    if config.characterisation_run_id is not None:
        plan_payload["characterisation_run_id"] = str(config.characterisation_run_id)
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
            grouping_backend=grouping_backend,
            ranking_backend=ranking_backend,
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


def _characterise_payload(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    """Return the characterise component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    pass ``run_id`` to pin the payload to one run rather than the latest.
    """
    return next(
        (
            e["payload"] for e in reversed(log_entries)
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == "characterise"
            and (run_id is None or e["run_id"] == run_id)
        ),
        None,
    )


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


def _selection_payload(
    log_entries: list[dict[str, Any]], *, run_id: uuid.UUID | None = None
) -> dict[str, Any] | None:
    """Return the select component's completed-event payload, or None if it failed.

    Entries arrive in ascending sequence order, so the search runs newest-first;
    pass ``run_id`` to pin the payload to one run rather than the latest.
    """
    return next(
        (
            e["payload"] for e in reversed(log_entries)
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == "select"
            and (run_id is None or e["run_id"] == run_id)
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
    grouping_backend: GroupingBackend
    ranking_backend: RankingBackend | None
    if live:
        embedding_backend = OpenAIEmbeddingBackend()
        grouping_backend = OpenAIGroupingBackend()
        # Tracing lives inside OpenAIRankingBackend itself — no wrapper class,
        # unlike the embedding/grouping backends below.
        ranking_backend = OpenAIRankingBackend(langfuse_client=langfuse_client)
        if langfuse_client is not None:
            embedding_backend = tracing.TracedEmbeddingBackend(
                embedding_backend, langfuse_client
            )
            grouping_backend = tracing.TracedGroupingBackend(
                grouping_backend, langfuse_client
            )
    else:
        embedding_backend = StubEmbeddingBackend()
        grouping_backend = StubGroupingBackend()
        ranking_backend = None
    log.info(
        "skeleton.backends",
        mode="live" if live else "stub",
        traced=langfuse_client is not None,
        ranking="llm_rerank_v1" if live else "coverage_stratified_v1",
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
            grouping_backend=grouping_backend,
            langfuse_client=langfuse_client,
        )

        # Walk the chain: five runs over the same scope. Acquire runs first —
        # both fixture backends over the mixed corpus (this upload + acquired sets).
        run_component("acquire")

        run_component("screen")

        screening_results = conn.execute(
            select(
                source_screening_result.c.status,
                source_screening_result.c.screen_basis,
                source_screening_result.c.screen_decision_confidence,
            ).where(source_screening_result.c.project_id == project_id)
        ).fetchall()

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

        char_run_id = run_component("characterise")

        char_row = conn.execute(
            select(characterisation_result).where(
                characterisation_result.c.project_id == project_id
            )
        ).one_or_none()

        # Pick the demo boost tag: most common source_tag.tag for this project
        # not asserted by characterise itself (deterministic order: count desc,
        # tag asc); fall back to any tag if none match.
        tag_counts = conn.execute(
            select(source_tag.c.tag, func.count())
            .where(source_tag.c.project_id == project_id)
            .where(source_tag.c.asserted_by != "characterise")
            .group_by(source_tag.c.tag)
            .order_by(func.count().desc(), source_tag.c.tag.asc())
        ).fetchall()
        if not tag_counts:
            tag_counts = conn.execute(
                select(source_tag.c.tag, func.count())
                .where(source_tag.c.project_id == project_id)
                .group_by(source_tag.c.tag)
                .order_by(func.count().desc(), source_tag.c.tag.asc())
            ).fetchall()
        boost_tag = tag_counts[0].tag if tag_counts else None
        log.info("select.demo_boost_tag", tag=boost_tag)

        # Plan finding 5: the fixture corpus is ~24 docs, so the default budget
        # (25) would leave zero contested strata — pin a small budget and a
        # boost on the chosen tag so reranking has something to do. A tagless
        # corpus gets the budget only (a None tag would fail the directive closed).
        selection_directive: dict[str, Any] = {"budget": 8}
        if boost_tag is not None:
            selection_directive["boosts"] = [
                {"match": {"tag_type": "topic_theme", "tag": boost_tag}, "weight": 3.0}
            ]
        conn.execute(
            evidence_scope.update()
            .where(evidence_scope.c.evidence_scope_id == scope_id)
            .values(context={"theme": "housing", "selection": selection_directive})
        )
        log.info("select.directive", budget=8, boost_tag=boost_tag)

        run_component(
            "select",
            characterisation_run_id=char_run_id,
            ranking_backend=ranking_backend,
        )

        selection_row = conn.execute(
            select(selection_result).where(selection_result.c.project_id == project_id)
        ).one_or_none()

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
                 confidence=row.screen_decision_confidence)

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
