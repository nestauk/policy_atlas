"""Walking-skeleton end-to-end thread.

Smoke command: python -m policy_atlas.skeleton

Creates a project + run, ingests a synthetic source, creates a screening scope,
compiles a screen plan, walks the spine, prints screening results and the event log.
All gates approved; see ADR 0001 and contract.md.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select, text

from policy_atlas import events
from policy_atlas.db import get_engine
from policy_atlas.fixtures import get_source
from policy_atlas.harness import run_harness
from policy_atlas.ingest import ingest_upload
from policy_atlas.logging import configure_logging
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import (
    project,
    runs,
    screening_scope,
    source_classification_result,
    source_screening_result,
)

log = structlog.get_logger()


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
            metadata={"synthetic": True, "abstract": "A synthetic policy document."},
            text_basis="full_text",
        )
        log.info("source.ingested")

        # Create screening scope
        scope_id = uuid.uuid4()
        conn.execute(
            screening_scope.insert().values(
                screening_scope_id=scope_id,
                project_id=project_id,
                intent="What policies address housing affordability?",
                context={"theme": "housing"},
                created_at=datetime.now(UTC),
            )
        )
        log.info("screening_scope.created", scope_id=str(scope_id))

        # Create run
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
        log.info("run.started", run_id=str(run_id))

        # Compile screen plan
        the_plan = Plan(component="screen", screening_scope_id=scope_id)
        config = compile(the_plan)

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="plan.compiled",
            payload={
                "component": config.component,
                "screening_scope_id": str(config.screening_scope_id),
            },
        )
        log.info("plan.compiled", component=config.component)

        # Run harness (screen component; provider unused but required by signature)
        from policy_atlas.inference import StubEchoProvider
        run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            provider=StubEchoProvider(),
        )

        screening_results = conn.execute(
            select(
                source_screening_result.c.status,
                source_screening_result.c.screen_basis,
                source_screening_result.c.screen_decision_confidence,
            ).where(source_screening_result.c.project_id == project_id)
        ).fetchall()

        # Run classify: create a second run, then execute the classify plan
        classify_run_id = uuid.uuid4()
        conn.execute(
            runs.insert().values(
                run_id=classify_run_id,
                project_id=project_id,
                status="running",
                started_at=datetime.now(UTC),
            )
        )
        events.append(
            conn, project_id=project_id, run_id=classify_run_id,
            event_type="run.started", payload={},
        )
        log.info("run.started", run_id=str(classify_run_id))

        classify_plan = Plan(component="classify", screening_scope_id=scope_id)
        classify_config = compile(classify_plan)
        events.append(
            conn,
            project_id=project_id,
            run_id=classify_run_id,
            event_type="plan.compiled",
            payload={
                "component": classify_config.component,
                "screening_scope_id": str(classify_config.screening_scope_id),
            },
        )

        run_harness(
            conn,
            config=classify_config,
            project_id=project_id,
            run_id=classify_run_id,
            provider=StubEchoProvider(),
        )

        classify_results = conn.execute(
            select(
                source_classification_result.c.primary_evidence_type,
                source_classification_result.c.open_tags,
            ).where(source_classification_result.c.project_id == project_id)
        ).fetchall()
        log_entries = events.read(conn, project_id)

    for row in screening_results:
        log.info("screening_result", status=row.status, basis=row.screen_basis,
                 confidence=row.screen_decision_confidence)

    for row in classify_results:
        log.info("classification_result", evidence_type=row.primary_evidence_type,
                 open_tags=row.open_tags)

    for entry in log_entries:
        log.info("event_log_entry", sequence=entry["sequence"], event_type=entry["event_type"])

    log.info("skeleton.done")


if __name__ == "__main__":
    main()
