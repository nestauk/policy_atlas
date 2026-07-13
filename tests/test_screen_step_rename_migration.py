"""Migration roundtrip for b7f3d9a2c5e1 (screen step-name vocabulary rename).

Runs against the real Alembic migration chain, on the same test database as
the ``conn`` fixture (task 018 rider A5 precedent, mirrored from
test_effect_direction_migration.py). Downgrades to the pre-rename revision,
seeds an orchestration_plan row and event_log rows shaped the way pre-019
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

from policy_atlas.schema import event_log, orchestration_plan
from tests.conftest import _alembic_cfg
from tests.helpers import delete_project_data, now, seed_project_and_run

# The revision below b7f3d9a2c5e1 (the screen step-name rename) — the
# pre-rename vocabulary state this test exercises.
PRE_RENAME_REVISION = "921d3a781f3f"


def _seed_plan(conn: Connection, project_id: uuid.UUID) -> uuid.UUID:
    plan_id = uuid.uuid4()
    conn.execute(
        orchestration_plan.insert().values(
            plan_id=plan_id,
            project_id=project_id,
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


def _seed_events(conn: Connection, *, project_id: uuid.UUID, run_id: uuid.UUID) -> None:
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
            event_log.insert().values(
                event_id=uuid.uuid4(),
                run_id=run_id,
                project_id=project_id,
                sequence=sequence,
                event_type=event_type,
                occurred_at=now(),
                payload={"component": component, "registry_component": "screen"},
            )
        )


def _read_plan_payload(conn: Connection, plan_id: uuid.UUID) -> dict[str, Any]:
    return cast(
        "dict[str, Any]",
        conn.execute(
            select(orchestration_plan.c.payload).where(orchestration_plan.c.plan_id == plan_id)
        ).scalar_one(),
    )


def _read_event_components(
    conn: Connection, *, project_id: uuid.UUID, run_id: uuid.UUID
) -> list[tuple[str, str]]:
    rows = conn.execute(
        select(event_log.c.event_type, event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.run_id == run_id)
        .order_by(event_log.c.sequence)
    ).fetchall()
    return [(row.event_type, row.payload["component"]) for row in rows]


def test_screen_step_rename_migration_rewrites_existing_data(engine: Engine) -> None:
    """Pre-rename rows are rewritten on upgrade and rewritten back on downgrade."""
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_RENAME_REVISION)

    connection = engine.connect()
    trans = connection.begin()
    project_id, run_id = seed_project_and_run(connection)
    plan_id = _seed_plan(connection, project_id)
    _seed_events(connection, project_id=project_id, run_id=run_id)
    trans.commit()
    connection.close()

    try:
        command.upgrade(cfg, "head")

        connection = engine.connect()
        trans = connection.begin()
        try:
            payload = _read_plan_payload(connection, plan_id)
            assert payload["components"] == ["screen_full", "characterise"]
            assert payload["component_rationale"] == {
                "screen_full": "Full-text confirmation improves precision.",
                "characterise": "Maps the corpus landscape.",
            }

            events = _read_event_components(connection, project_id=project_id, run_id=run_id)
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
            payload = _read_plan_payload(connection, plan_id)
            assert payload["components"] == ["screen_stage2", "characterise"]
            assert payload["component_rationale"] == {
                "screen_stage2": "Full-text confirmation improves precision.",
                "characterise": "Maps the corpus landscape.",
            }

            events = _read_event_components(connection, project_id=project_id, run_id=run_id)
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
                orchestration_plan.delete().where(orchestration_plan.c.project_id == project_id)
            )
            delete_project_data(conn_delete, project_id)
            trans.commit()
        finally:
            connection.close()
