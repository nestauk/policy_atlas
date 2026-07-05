"""Walking-skeleton end-to-end thread.

Smoke command: python -m policy_atlas.skeleton

Creates a project + run, ingests a synthetic source, creates a screening scope,
then walks screen → classify → appraise over the same scope and prints the
results and the event log.
All gates approved; see ADR 0001 and contract.md.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, text
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.db import get_engine
from policy_atlas.fixtures import get_source
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest import ingest_upload
from policy_atlas.logging import configure_logging
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import (
    evidence_scope,
    project,
    runs,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
)

log = structlog.get_logger()


def _run_component(
    conn: Connection, project_id: uuid.UUID, scope_id: uuid.UUID, component: str
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

    # provider unused by scope components but required by the harness signature
    run_harness(
        conn, config=config, project_id=project_id, run_id=run_id, provider=StubEchoProvider()
    )


def main() -> None:
    """Run the walking-skeleton thread end to end and log the result."""
    configure_logging()
    log.info("skeleton.start")

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

        # Walk the chain: four runs over the same scope. Acquire runs first —
        # both fixture backends over the mixed corpus (this upload + acquired sets).
        _run_component(conn, project_id, scope_id, "acquire")

        _run_component(conn, project_id, scope_id, "screen")

        screening_results = conn.execute(
            select(
                source_screening_result.c.status,
                source_screening_result.c.screen_basis,
                source_screening_result.c.screen_decision_confidence,
            ).where(source_screening_result.c.project_id == project_id)
        ).fetchall()

        _run_component(conn, project_id, scope_id, "classify")

        classify_results = conn.execute(
            select(
                source_classification_result.c.primary_evidence_type,
                source_classification_result.c.open_tags,
            ).where(source_classification_result.c.project_id == project_id)
        ).fetchall()

        _run_component(conn, project_id, scope_id, "appraise")

        appraise_results = conn.execute(
            select(
                source_appraisal_result.c.quality_score,
                source_appraisal_result.c.rubric_version,
            ).where(source_appraisal_result.c.project_id == project_id)
        ).fetchall()
        log_entries = events.read(conn, project_id)

    # Per-backend acquire counts — makes the authentic-shapes path visible
    acquire_counts = next(
        (
            e["payload"] for e in log_entries
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == "acquire"
        ),
        None,
    )
    if acquire_counts is None:
        log.warning("acquire_counts.missing")
    else:
        log.info(
            "acquire_counts", **{k: v for k, v in acquire_counts.items() if k != "component"}
        )

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
        log.info("classification_result", evidence_type=row.primary_evidence_type,
                 open_tags=row.open_tags)

    for row in appraise_results:
        log.info("appraisal_result", quality_score=row.quality_score,
                 rubric_version=row.rubric_version)

    # Surface the skip counts so both the scored and skipped paths are visible
    appraise_counts = next(
        (
            e["payload"] for e in log_entries
            if e["event_type"] == "component.completed"
            and e["payload"].get("component") == "appraise"
        ),
        None,
    )
    if appraise_counts is None:
        # appraise emitted component.failed — fall through to the event log below
        log.warning("appraise_counts.missing")
    else:
        log.info(
            "appraise_counts", **{k: v for k, v in appraise_counts.items() if k != "component"}
        )

    for entry in log_entries:
        log.info("event_log_entry", sequence=entry["sequence"], event_type=entry["event_type"])

    log.info("skeleton.done")


if __name__ == "__main__":
    main()
