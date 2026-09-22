"""Round-trip coverage for the task 045 slice revision (``c7e2a9f4b1d8``).

Contract § Acceptance checks, the migration bullet: upgrade, downgrade,
upgrade; the downgrade **refuses** while a longlist or targeted walk exists
(the 044 A5 pattern, widened) and while a selection-free extraction roll-up
would block ``NOT NULL``; ``task_link.option_id`` is nullable and guarded to
an option of the link's target task; ``parent_capability_run_id`` is a
nullable self-FK of the same task; the union view has three branches after
upgrade and two after downgrade; ``extraction_result.selection_run_id`` is
nullable after upgrade.

The ``engine`` fixture is session-scoped and the test database is shared, so
every test that moves the chain leaves it back at head, and every committed
scoping task is removed (044 verification, Phase 2 gotcha: a scoping task
left behind makes a downgrade refuse for every later round-trip test).
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from alembic import command
from sqlalchemy import inspect, select, text, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    capability_run,
    evidence_scope,
    extraction_result,
    finding_reference_union,
    intervention_profile_record,
    option,
    source_extraction_record,
    task,
    task_link,
    task_plan,
)
from tests.conftest import _alembic_cfg
from tests.helpers import delete_task_data, now, seed_scope, seed_source, seed_task_and_run

PRE_SLICE_REVISION = "b5e1d7a4c026"
SLICE_REVISION = "c7e2a9f4b1d8"

_NEW_TABLES = {
    "option",
    "option_membership",
    "option_relation",
    "longlist_result",
    "intervention_profile_record",
}

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops_remove_scoping_tasks.py"


def _load_ops() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ops_remove_scoping_tasks_045", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ops_remove_scoping_tasks_045"] = module
    spec.loader.exec_module(module)
    return module


def _view_definition(conn: Connection) -> str:
    query = text("SELECT pg_get_viewdef('finding_reference_union'::regclass)")
    return str(conn.execute(query).scalar_one())


def _column(conn: Connection, table: str, name: str) -> dict[str, object] | None:
    for column in inspect(conn).get_columns(table):
        if column["name"] == name:
            return dict(column)
    return None


def _plan_row(conn: Connection, task_id: uuid.UUID) -> uuid.UUID:
    plan_id = uuid.uuid4()
    conn.execute(
        task_plan.insert().values(
            plan_id=plan_id,
            task_id=task_id,
            version=1,
            status="approved",
            payload={},
            created_at=now(),
            created_by="test",
        )
    )
    return plan_id


def _seed_walk(
    conn: Connection,
    task_id: uuid.UUID,
    *,
    purpose: str | None,
    plan_id: uuid.UUID,
    parent: uuid.UUID | None = None,
    status: str = "succeeded",
    capability: str = "options_scoping",
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert an intent record of ``purpose`` and one walk under it."""
    scope_id = uuid.uuid4()
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent="intent",
            context={},
            created_at=now(),
            purpose=purpose,
        )
    )
    walk_id = uuid.uuid4()
    conn.execute(
        capability_run.insert().values(
            capability_run_id=walk_id,
            task_id=task_id,
            evidence_scope_id=scope_id,
            capability=capability,
            plan_id=plan_id,
            plan_version=1,
            status=status,
            started_at=now(),
            parent_capability_run_id=parent,
        )
    )
    return scope_id, walk_id


def _seed_scoping_task(engine: Engine, *, purpose: str) -> uuid.UUID:
    with engine.begin() as conn:
        task_id, _run_id = seed_task_and_run(conn)
        conn.execute(
            update(task).where(task.c.task_id == task_id).values(capability="options_scoping")
        )
        plan_id = _plan_row(conn, task_id)
        _seed_walk(conn, task_id, purpose=purpose, plan_id=plan_id)
    return task_id


def _remove(engine: Engine, task_id: uuid.UUID) -> None:
    with engine.begin() as conn:
        delete_task_data(conn, task_id)


# --- the round trip ---------------------------------------------------------


def test_the_slice_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    try:
        command.downgrade(cfg, PRE_SLICE_REVISION)
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            assert not (_NEW_TABLES & tables)
            assert _column(conn, "task_link", "option_id") is None
            assert _column(conn, "capability_run", "parent_capability_run_id") is None
            selection = _column(conn, "extraction_result", "selection_run_id")
            assert selection is not None and selection["nullable"] is False
            definition = _view_definition(conn)
            assert "intervention_outcome_finding" in definition
            assert "implementation_context_finding" in definition
            assert "intervention_profile_record" not in definition

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) >= _NEW_TABLES
            link_option = _column(conn, "task_link", "option_id")
            assert link_option is not None and link_option["nullable"] is True
            parent = _column(conn, "capability_run", "parent_capability_run_id")
            assert parent is not None and parent["nullable"] is True
            selection = _column(conn, "extraction_result", "selection_run_id")
            assert selection is not None and selection["nullable"] is True
            definition = _view_definition(conn)
            assert "intervention_profile_record" in definition
            assert "'interventions'::text" in definition
    finally:
        command.upgrade(cfg, "head")


# --- the refusals -----------------------------------------------------------


@pytest.mark.parametrize("purpose", ["longlist", "targeted"])
def test_the_downgrade_refuses_while_a_longlist_or_targeted_walk_exists(
    engine: Engine, purpose: str
) -> None:
    cfg = _alembic_cfg()
    task_id = _seed_scoping_task(engine, purpose=purpose)
    try:
        with pytest.raises(RuntimeError) as excinfo:
            command.downgrade(cfg, PRE_SLICE_REVISION)
        assert "ops_remove_scoping_tasks" in str(excinfo.value)
        assert "longlist or targeted" in str(excinfo.value)
        # Refused before any DDL: nothing was dropped on the way.
        with engine.connect() as conn:
            assert set(inspect(conn).get_table_names()) >= _NEW_TABLES
    finally:
        command.upgrade(cfg, "head")
        _remove(engine, task_id)


def test_a_baseline_walk_alone_does_not_block_this_revision(engine: Engine) -> None:
    """The widened predicate names the two new purposes, nothing else."""
    cfg = _alembic_cfg()
    task_id = _seed_scoping_task(engine, purpose="baseline")
    try:
        command.downgrade(cfg, PRE_SLICE_REVISION)
        with engine.connect() as conn:
            assert "option" not in set(inspect(conn).get_table_names())
    finally:
        command.upgrade(cfg, "head")
        _remove(engine, task_id)


def test_the_downgrade_refuses_while_a_selection_free_roll_up_exists(engine: Engine) -> None:
    """``NOT NULL`` cannot be restored over a NULL, so the downgrade says so."""
    cfg = _alembic_cfg()
    with engine.begin() as conn:
        task_id, run_id = seed_task_and_run(conn)
        scope_id = seed_scope(conn, task_id)
        conn.execute(
            extraction_result.insert().values(
                extraction_result_id=uuid.uuid4(),
                task_id=task_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                selection_run_id=None,
                extraction_provenance={},
                docs=[],
                counts={},
                flags={},
                created_at=now(),
            )
        )
    try:
        with pytest.raises(RuntimeError) as excinfo:
            command.downgrade(cfg, PRE_SLICE_REVISION)
        assert "selection_run_id" in str(excinfo.value)
    finally:
        command.upgrade(cfg, "head")
        _remove(engine, task_id)


def test_the_remedy_clears_a_longlist_walk_and_its_records_then_the_downgrade_runs(
    engine: Engine,
) -> None:
    """The operator script reaches every table this revision adds (ADR 0039 § Rollback)."""
    ops = _load_ops()
    cfg = _alembic_cfg()
    with engine.begin() as conn:
        task_id, run_id = seed_task_and_run(conn)
        conn.execute(
            update(task).where(task.c.task_id == task_id).values(capability="options_scoping")
        )
        plan_id = _plan_row(conn, task_id)
        scope_id, walk_id = _seed_walk(conn, task_id, purpose="longlist", plan_id=plan_id)
        _seed_walk(conn, task_id, purpose="targeted", plan_id=plan_id, parent=walk_id)
        _snap, tss_id = seed_source(conn, task_id)
        option_id = _insert_option(conn, task_id, run_id=run_id)
        other_option = _insert_option(conn, task_id, run_id=run_id)
        conn.execute(
            text(
                "INSERT INTO option_relation (relation_id, task_id, from_option_id, "
                "to_option_id, kind, created_by, created_at) "
                "VALUES (:r, :t, :a, :b, 'part_of', 'longlist', now())"
            ),
            {"r": uuid.uuid4(), "t": task_id, "a": option_id, "b": other_option},
        )
        record_id = _insert_profile_record(conn, task_id, tss_id=tss_id, run_id=run_id)
        conn.execute(
            text(
                "INSERT INTO option_membership (membership_id, option_id, task_id, "
                "unit_kind, unit_id, unit_task_id, task_source_snapshot_id, "
                "assigned_by_run_id) VALUES (:m, :o, :t, 'interventions', :u, :t, :s, :r)"
            ),
            {
                "m": uuid.uuid4(),
                "o": option_id,
                "t": task_id,
                "u": record_id,
                "s": tss_id,
                "r": run_id,
            },
        )
        conn.execute(
            text(
                "INSERT INTO longlist_result (longlist_result_id, task_id, evidence_scope_id, "
                "run_id, plan_version, themes, coverage, judgements, guesses, counts, "
                "provenance, created_at) VALUES (:l, :t, :s, :r, 1, '[]', '{}', '{}', '[]', "
                "'{}', '{}', now())"
            ),
            {"l": uuid.uuid4(), "t": task_id, "s": scope_id, "r": run_id},
        )
        conn.execute(
            extraction_result.insert().values(
                extraction_result_id=uuid.uuid4(),
                task_id=task_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                selection_run_id=None,
                extraction_provenance={},
                docs=[],
                counts={},
                flags={},
                created_at=now(),
            )
        )
    try:
        assert ops.run(engine, apply=True) == 0
        with engine.connect() as conn:
            for table in sorted(_NEW_TABLES):
                count = conn.execute(
                    text(f"SELECT count(*) FROM {table} WHERE task_id = :t"),  # noqa: S608
                    {"t": task_id},
                ).scalar_one()
                assert count == 0, table
        command.downgrade(cfg, PRE_SLICE_REVISION)
    finally:
        command.upgrade(cfg, "head")
        _remove(engine, task_id)


# --- the database rules the revision adds -------------------------------------


def _insert_option(
    conn: Connection, task_id: uuid.UUID, *, run_id: uuid.UUID | None = None
) -> uuid.UUID:
    option_id = uuid.uuid4()
    conn.execute(
        option.insert().values(
            option_id=option_id,
            task_id=task_id,
            name="Youth guarantee",
            description="An offer of work or training within four months.",
            design={"features": ["offer within four months"]},
            outcomes=["the NEET rate"],
            origin="suggested",
            secondary_lever_types=[],
            created_by_run_id=run_id,
            created_at=now(),
            updated_at=now(),
        )
    )
    return option_id


def _insert_profile_record(
    conn: Connection, task_id: uuid.UUID, *, tss_id: uuid.UUID, run_id: uuid.UUID
) -> uuid.UUID:
    snapshot_id = conn.execute(
        text(
            "SELECT source_snapshot_id FROM task_source_snapshot "
            "WHERE task_source_snapshot_id = :s"
        ),
        {"s": tss_id},
    ).scalar_one()
    record_id = uuid.uuid4()
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=record_id,
            task_id=task_id,
            source_snapshot_id=snapshot_id,
            task_source_snapshot_id=tss_id,
            extraction_fingerprint="fp",
            status="extracted",
            basis="abstract_only",
            finding_count=1,
            run_id=run_id,
            created_at=now(),
        )
    )
    profile_id = uuid.uuid4()
    conn.execute(
        intervention_profile_record.insert().values(
            record_id=profile_id,
            task_id=task_id,
            extraction_record_id=record_id,
            intervention="Youth guarantee",
            role="evaluated",
            design_features=["offer within four months"],
            components=[],
            outcome="the NEET rate",
            study_geography="Finland",
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    return profile_id


def test_a_link_may_name_only_an_option_of_its_target_task(conn: Connection) -> None:
    source_id, source_run = seed_task_and_run(conn)
    plan_id = _plan_row(conn, source_id)
    _scope, pinned = _seed_walk(
        conn, source_id, purpose=None, plan_id=plan_id, capability="evidence_search"
    )
    target_id, _ = seed_task_and_run(conn)
    stranger_id, _ = seed_task_and_run(conn)
    del source_run
    foreign_option = _insert_option(conn, stranger_id)
    link = {
        "link_id": uuid.uuid4(),
        "source_task_id": source_id,
        "target_task_id": target_id,
        "source_capability_run_id": pinned,
        "created_by": "test",
        "created_at": now(),
    }
    # NULL is the default and passes (MATCH SIMPLE).
    conn.execute(task_link.insert().values(**link))
    own_option = _insert_option(conn, target_id)
    conn.execute(
        task_link.update()
        .where(task_link.c.link_id == link["link_id"])
        .values(option_id=own_option)
    )
    with pytest.raises(IntegrityError, match="fk_task_link_option_target"):
        conn.execute(
            task_link.update()
            .where(task_link.c.link_id == link["link_id"])
            .values(option_id=foreign_option)
        )


def test_a_parent_walk_must_be_a_walk_of_the_same_task(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    plan_id = _plan_row(conn, task_id)
    _scope, parent = _seed_walk(conn, task_id, purpose="longlist", plan_id=plan_id)
    _child_scope, child = _seed_walk(
        conn, task_id, purpose="targeted", plan_id=plan_id, parent=parent
    )
    assert (
        conn.execute(
            select(capability_run.c.parent_capability_run_id).where(
                capability_run.c.capability_run_id == child
            )
        ).scalar_one()
        == parent
    )
    other_id, _ = seed_task_and_run(conn)
    other_plan = _plan_row(conn, other_id)
    with pytest.raises(IntegrityError, match="fk_capr_parent_task"):
        _seed_walk(conn, other_id, purpose="targeted", plan_id=other_plan, parent=parent)


def test_the_union_view_carries_profile_records_as_the_third_kind(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    _snap, tss_id = seed_source(conn, task_id)
    record_id = _insert_profile_record(conn, task_id, tss_id=tss_id, run_id=run_id)
    row = conn.execute(
        select(finding_reference_union).where(finding_reference_union.c.finding_id == record_id)
    ).mappings().one()
    assert row["kind"] == "interventions"
    assert row["task_id"] == task_id
    assert row["intervention"] == "Youth guarantee"
    assert row["study_geography"] == "Finland"
    assert row["population"] is None


@pytest.mark.parametrize(
    ("column", "value", "constraint"),
    [
        ("origin", "invented", "ck_option_origin"),
        ("state", "shortlisted", "ck_option_state"),
    ],
)
def test_the_option_vocabularies_are_closed(
    conn: Connection, column: str, value: str, constraint: str
) -> None:
    task_id, _ = seed_task_and_run(conn)
    option_id = _insert_option(conn, task_id)
    with pytest.raises(IntegrityError, match=constraint):
        conn.execute(
            option.update().where(option.c.option_id == option_id).values(**{column: value})
        )


def test_a_profile_record_s_role_is_closed(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    _snap, tss_id = seed_source(conn, task_id)
    record_id = _insert_profile_record(conn, task_id, tss_id=tss_id, run_id=run_id)
    with pytest.raises(IntegrityError, match="ck_ipr_role"):
        conn.execute(
            intervention_profile_record.update()
            .where(intervention_profile_record.c.record_id == record_id)
            .values(role="adopted")
        )

