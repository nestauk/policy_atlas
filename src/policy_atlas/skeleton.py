"""Walking-skeleton end-to-end thread.

Smoke command: python -m policy_atlas.skeleton

Creates a project + run, ingests a synthetic source, creates a screening scope,
then walks screen → classify → appraise → ingest_full_text → characterise over
the same scope, rendering the landscape summary and the event log.
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
from policy_atlas.schema import (
    characterisation_result,
    evidence_scope,
    project,
    project_source_snapshot,
    runs,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
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
) -> None:
    """Create a run, compile and record the plan, and execute one scope component."""
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

    config = compile(Plan(component=component, evidence_scope_id=scope_id))
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="plan.compiled",
        payload={
            "component": config.component,
            "evidence_scope_id": str(config.evidence_scope_id),
        },
    )
    log.info("plan.compiled", component=config.component)

    with tracing.component_span(
        langfuse_client, run_id=run_id, project_id=project_id, component=component
    ):
        # provider unused by scope components but required by the harness signature
        run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            provider=StubEchoProvider(),
            embedding_backend=embedding_backend,
            grouping_backend=grouping_backend,
        )


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


def _characterise_payload(log_entries: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Return the characterise component's completed-event payload, or None if it failed."""
    return next(
        (
            e["payload"] for e in log_entries
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == "characterise"
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
    if live:
        embedding_backend = OpenAIEmbeddingBackend()
        grouping_backend = OpenAIGroupingBackend()
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
    log.info(
        "skeleton.backends", mode="live" if live else "stub", traced=langfuse_client is not None
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

        run_component("characterise")

        char_row = conn.execute(
            select(characterisation_result).where(
                characterisation_result.c.project_id == project_id
            )
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

    characterise_payload = _characterise_payload(log_entries)
    if characterise_payload is not None:
        tracing.score_summary(langfuse_client, characterise_payload)
    tracing.flush(langfuse_client)

    log.info("skeleton.done")


if __name__ == "__main__":
    main()
