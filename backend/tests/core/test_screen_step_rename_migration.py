"""Migration roundtrip for b7f3d9a2c5e1 (screen step-name vocabulary rename).

Runs against the real Alembic migration chain, on the same test database as
the ``conn`` fixture (task 018 rider A5 precedent, mirrored from
test_effect_direction_migration.py). Downgrades to the pre-rename revision,
seeds a plan row (table ``orchestration_plan`` down there) and event_log rows
shaped the way pre-019
code wrote them, upgrades to head, and proves the seeded rows were rewritten
in place — then downgrades again and proves the rewrite reverses.

Same coupling as test_search_migration.py / test_effect_direction_migration.py:
no row-holding transaction may be open while alembic runs DDL on a second
connection, so seeding happens strictly after the DDL step it accompanies and
every seed transaction is rolled back (or committed-then-cleaned-up) before
the next DDL step.
"""

import uuid
from typing import Any, cast

from alembic import command
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import event_log, task_plan
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table, seed_legacy_task_and_run
from tests.helpers import delete_task_data, now

# The revision below b7f3d9a2c5e1 (the screen step-name rename) — the
# pre-rename vocabulary state this test exercises.
PRE_RENAME_REVISION = "921d3a781f3f"


def _seed_plan(conn: Connection, task_id: uuid.UUID) -> uuid.UUID:
    """Insert the pre-rename plan row below the 038 revision (plan D9)."""
    plan_id = uuid.uuid4()
    conn.execute(
        legacy_table(conn, "orchestration_plan").insert().values(
            plan_id=plan_id,
            project_id=task_id,
            evidence_scope_id=None,
            version=1,
            status="approved",
            payload={
                "title": "Pre-rename plan",
                "question": "What works?",
                "backend_scope": "both",
                "search_effort": "standard",
                "analysis_depth": "standard",
                "components": ["screen_stage2", "characterise"],
                "component_rationale": {
                    "screen_stage2": "Full-text confirmation improves precision.",
                    "characterise": "Maps the corpus landscape.",
                },
                "steering_mode": "moderate",
            },
            created_at=now(),
            created_by="planner",
            approved_at=None,
        )
    )
    return plan_id


def _seed_events(conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID) -> None:
    """Insert the pre-rename event rows below the 038 revision (plan D9)."""
    events = legacy_table(conn, "event_log")
    for sequence, (event_type, component) in enumerate(
        [
            ("run.started", "screen"),
            ("plan.compiled", "screen"),
            ("component.timing", "screen"),
            ("run.started", "screen_stage2"),
            ("plan.compiled", "screen_stage2"),
            ("component.timing", "screen_stage2"),
            # A harness-level event carrying the registry component name
            # "screen" under event_type "component.completed" — outside this
            # migration's event_type filter, so it must survive untouched.
            ("component.completed", "screen"),
        ]
    ):
        conn.execute(
            events.insert().values(
                event_id=uuid.uuid4(),
                run_id=run_id,
                project_id=task_id,
                sequence=sequence,
                event_type=event_type,
                occurred_at=now(),
                payload={"component": component, "registry_component": "screen"},
            )
        )


def _read_plan_payload(conn: Connection, plan_id: uuid.UUID, *, legacy: bool) -> dict[str, Any]:
    """Read the plan payload from whichever catalog generation is live (plan D9)."""
    plans = legacy_table(conn, "orchestration_plan") if legacy else task_plan
    return cast(
        "dict[str, Any]",
        conn.execute(select(plans.c.payload).where(plans.c.plan_id == plan_id)).scalar_one(),
    )


def _read_event_components(
    conn: Connection, *, task_id: uuid.UUID, run_id: uuid.UUID, legacy: bool
) -> list[tuple[str, str]]:
    """Read the run's event components from whichever catalog generation is live."""
    events = legacy_table(conn, "event_log") if legacy else event_log
    task_column = events.c.project_id if legacy else events.c.task_id
    rows = conn.execute(
        select(events.c.event_type, events.c.payload)
        .where(task_column == task_id)
        .where(events.c.run_id == run_id)
        .order_by(events.c.sequence)
    ).fetchall()
    return [(row.event_type, row.payload["component"]) for row in rows]


def test_screen_step_rename_migration_rewrites_existing_data(engine: Engine) -> None:
    """Pre-rename rows are rewritten on upgrade and rewritten back on downgrade."""
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_RENAME_REVISION)

    connection = engine.connect()
    trans = connection.begin()
    task_id, run_id = seed_legacy_task_and_run(connection)
    plan_id = _seed_plan(connection, task_id)
    _seed_events(connection, task_id=task_id, run_id=run_id)
    trans.commit()
    connection.close()

    try:
        command.upgrade(cfg, "head")

        connection = engine.connect()
        trans = connection.begin()
        try:
            payload = _read_plan_payload(connection, plan_id, legacy=False)
            assert payload["components"] == ["screen_full", "characterise"]
            assert payload["component_rationale"] == {
                "screen_full": "Full-text confirmation improves precision.",
                "characterise": "Maps the corpus landscape.",
            }

            events = _read_event_components(
                connection, task_id=task_id, run_id=run_id, legacy=False
            )
            assert events == [
                ("run.started", "screen_abstract"),
                ("plan.compiled", "screen_abstract"),
                ("component.timing", "screen_abstract"),
                ("run.started", "screen_full"),
                ("plan.compiled", "screen_full"),
                ("component.timing", "screen_full"),
                # Untouched: component.completed carries the registry name,
                # outside this migration's event_type filter.
                ("component.completed", "screen"),
            ]
        finally:
            trans.rollback()
            connection.close()

        command.downgrade(cfg, PRE_RENAME_REVISION)

        connection = engine.connect()
        trans = connection.begin()
        try:
            payload = _read_plan_payload(connection, plan_id, legacy=True)
            assert payload["components"] == ["screen_stage2", "characterise"]
            assert payload["component_rationale"] == {
                "screen_stage2": "Full-text confirmation improves precision.",
                "characterise": "Maps the corpus landscape.",
            }

            events = _read_event_components(
                connection, task_id=task_id, run_id=run_id, legacy=True
            )
            assert events == [
                ("run.started", "screen"),
                ("plan.compiled", "screen"),
                ("component.timing", "screen"),
                ("run.started", "screen_stage2"),
                ("plan.compiled", "screen_stage2"),
                ("component.timing", "screen_stage2"),
                ("component.completed", "screen"),
            ]
        finally:
            trans.rollback()
            connection.close()
    finally:
        # Clean up the committed seed rows (outside any migration's own DDL
        # transaction) then restore head for the rest of the suite.
        command.upgrade(cfg, "head")
        connection = engine.connect()
        trans = connection.begin()
        try:
            conn_delete = connection
            conn_delete.execute(
                task_plan.delete().where(task_plan.c.task_id == task_id)
            )
            delete_task_data(conn_delete, task_id)
            trans.commit()
        finally:
            connection.close()
