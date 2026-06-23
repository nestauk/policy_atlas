"""Walking-skeleton end-to-end thread.

Smoke command: python -m policy_atlas.skeleton

Creates a project + run, compiles a trivial plan, walks the spine, prints persisted IDs
and the ordered event log. All gates approved; see ADR 0001 and contract.md.
"""

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import text

from policy_atlas import events
from policy_atlas.db import get_engine
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.logging import configure_logging
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import project, runs

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

        # Emit run.started
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="run.started",
            payload={},
        )
        log.info("run.started", run_id=str(run_id))

        # Compile plan
        the_plan = Plan(component="echo", source_ref="syn-001")
        config = compile(the_plan)

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="plan.compiled",
            payload={"component": config.component, "source_ref": config.source_ref},
        )
        log.info("plan.compiled", component=config.component)

        # Run harness
        ids = run_harness(
            conn,
            config=config,
            project_id=project_id,
            run_id=run_id,
            provider=StubEchoProvider(),
        )

    # Read back and print
    with engine.connect() as conn:
        log_entries = events.read(conn, project_id)

    for key, val in ids.items():
        log.info("persisted_id", field=key, value=str(val))

    for entry in log_entries:
        log.info("event_log_entry", sequence=entry["sequence"], event_type=entry["event_type"])

    log.info("skeleton.done")


if __name__ == "__main__":
    main()
