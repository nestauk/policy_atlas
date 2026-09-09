"""Round-trip coverage for the task 044 slice revision (``b5e1d7a4c026``).

The revision is additive, so "upgrade, downgrade, upgrade" is only half the
test. The other half is the **refusal**: this revision is the one that cannot
be reversed while options-scoping data exists, because dropping
``task.capability`` would silently reclassify every scoping task as an Evidence
search and narrowing ``ck_capr_capability`` would fail outright against a
scoping walk. Archiving keeps the row, so archiving is not a remedy (A5, C15).

The ``engine`` fixture is session-scoped and the test database is shared, so
every test here leaves the chain back at head.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import capability_run, evidence_scope, task, task_link, task_plan
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import legacy_table

PRE_SLICE_REVISION = "a7d3f1c8e2b5"
SLICE_REVISION = "b5e1d7a4c026"


def _constraint_definition(conn: Connection, name: str) -> str:
    return str(
        conn.execute(
            text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :n"),
            {"n": name},
        ).scalar_one()
    )


def _seed_pre_slice_task(engine: Engine, task_id: uuid.UUID, now: datetime) -> None:
    """Commit one ordinary task at ``a7d3f1c8e2b5``, before ``capability`` exists."""
    with engine.begin() as conn:
        conn.execute(
            legacy_table(conn, "task").insert().values(
                task_id=task_id,
                created_at=now,
                name="A pre-slice Task",
                question="What works?",
                status="active",
                updated_at=now,
                archived_at=None,
                owner_user_id="owner-044-slice",
                org_id=None,
                visibility="private",
                is_public=False,
            )
        )


def _seed_scoping_task(
    engine: Engine, *, archived: bool = False, with_walk: bool = False
) -> uuid.UUID:
    """Commit one options-scoping task at head; return its id."""
    now = datetime.now(UTC)
    task_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            task.insert().values(
                task_id=task_id,
                created_at=now,
                name="A scoping Task",
                question="How do we cut youth unemployment?",
                status="archived" if archived else "active",
                updated_at=now,
                archived_at=now if archived else None,
                owner_user_id="owner-044-slice",
                capability="options_scoping",
            )
        )
        if with_walk:
            scope_id = uuid.uuid4()
            plan_id = uuid.uuid4()
            conn.execute(
                evidence_scope.insert().values(
                    evidence_scope_id=scope_id,
                    task_id=task_id,
                    intent="baseline",
                    context={},
                    created_at=now,
                    purpose="baseline",
                )
            )
            conn.execute(
                task_plan.insert().values(
                    plan_id=plan_id,
                    task_id=task_id,
                    version=1,
                    status="approved",
                    payload={},
                    created_at=now,
                    created_by="user",
                )
            )
            conn.execute(
                capability_run.insert().values(
                    capability_run_id=uuid.uuid4(),
                    task_id=task_id,
                    evidence_scope_id=scope_id,
                    capability="options_scoping",
                    plan_id=plan_id,
                    plan_version=1,
                    status="succeeded",
                    started_at=now,
                )
            )
    return task_id


def _delete_task(engine: Engine, task_id: uuid.UUID) -> None:
    with engine.begin() as conn:
        conn.execute(task_link.delete().where(task_link.c.target_task_id == task_id))
        conn.execute(task_link.delete().where(task_link.c.source_task_id == task_id))
        conn.execute(capability_run.delete().where(capability_run.c.task_id == task_id))
        conn.execute(task_plan.delete().where(task_plan.c.task_id == task_id))
        conn.execute(evidence_scope.delete().where(evidence_scope.c.task_id == task_id))
        conn.execute(task.delete().where(task.c.task_id == task_id))


def test_the_slice_round_trips_and_backfills_every_task_as_an_evidence_search(
    engine: Engine,
) -> None:
    """Upgrade adds the four objects; a pre-slice task reads ``evidence_search``."""
    cfg = _alembic_cfg()
    task_id = uuid.uuid4()
    command.downgrade(cfg, PRE_SLICE_REVISION)
    _seed_pre_slice_task(engine, task_id, datetime.now(UTC))
    try:
        with engine.connect() as conn:
            assert "capability" not in {
                column["name"] for column in inspect(conn).get_columns("task")
            }
            assert "task_link" not in set(inspect(conn).get_table_names())
            assert "'options_scoping'" not in _constraint_definition(
                conn, "ck_capr_capability"
            )

        command.upgrade(cfg, "head")

        with engine.connect() as conn:
            task_columns = {column["name"] for column in inspect(conn).get_columns("task")}
            assert "capability" in task_columns
            scope_columns = {
                column["name"] for column in inspect(conn).get_columns("evidence_scope")
            }
            assert {"purpose", "plan_id"} <= scope_columns
            assert "task_link" in set(inspect(conn).get_table_names())
            # The row that existed before the column did.
            assert (
                conn.execute(
                    select(task.c.capability).where(task.c.task_id == task_id)
                ).scalar_one()
                == "evidence_search"
            )
            for name in ("ck_task_capability", "ck_capr_capability"):
                definition = _constraint_definition(conn, name)
                assert "'evidence_search'" in definition
                assert "'options_scoping'" in definition

        # Down and up again, with the pre-slice row still there: no scoping
        # data exists, so the refusal does not fire.
        command.downgrade(cfg, PRE_SLICE_REVISION)
        with engine.connect() as conn:
            assert "task_link" not in set(inspect(conn).get_table_names())
            assert "'options_scoping'" not in _constraint_definition(
                conn, "ck_capr_capability"
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert (
                conn.execute(
                    select(task.c.capability).where(task.c.task_id == task_id)
                ).scalar_one()
                == "evidence_search"
            )
    finally:
        command.upgrade(cfg, "head")
        _delete_task(engine, task_id)


def test_the_capability_run_check_accepts_both_values(engine: Engine) -> None:
    task_id = _seed_scoping_task(engine, with_walk=True)
    try:
        with engine.connect() as conn:
            assert (
                conn.execute(
                    select(capability_run.c.capability).where(
                        capability_run.c.task_id == task_id
                    )
                ).scalar_one()
                == "options_scoping"
            )
    finally:
        _delete_task(engine, task_id)


@pytest.mark.parametrize("archived", [False, True])
def test_the_downgrade_refuses_while_a_scoping_task_exists(
    engine: Engine, archived: bool
) -> None:
    """Archiving keeps the row, so archiving is not the remedy (A5)."""
    cfg = _alembic_cfg()
    task_id = _seed_scoping_task(engine, archived=archived)
    try:
        with pytest.raises(RuntimeError) as excinfo:
            command.downgrade(cfg, PRE_SLICE_REVISION)
        assert "ops_remove_scoping_tasks" in str(excinfo.value)
        # Nothing was dropped on the way to the refusal.
        with engine.connect() as conn:
            assert "task_link" in set(inspect(conn).get_table_names())
    finally:
        command.upgrade(cfg, "head")
        _delete_task(engine, task_id)


def test_the_downgrade_refuses_while_a_scoping_walk_exists(engine: Engine) -> None:
    """A scoping ``capability_run`` blocks the narrowing on its own (A5)."""
    cfg = _alembic_cfg()
    task_id = _seed_scoping_task(engine, with_walk=True)
    # Make the task itself look like an Evidence search: the walk row alone
    # must still stop the downgrade, because ``ck_capr_capability`` narrows
    # back to one value and that row would violate it.
    with engine.begin() as conn:
        conn.execute(
            task.update().where(task.c.task_id == task_id).values(capability="evidence_search")
        )
    try:
        with pytest.raises(RuntimeError) as excinfo:
            command.downgrade(cfg, PRE_SLICE_REVISION)
        assert "capability_run" in str(excinfo.value)
    finally:
        command.upgrade(cfg, "head")
        _delete_task(engine, task_id)


def test_the_downgrade_proceeds_once_the_scoping_rows_are_gone(engine: Engine) -> None:
    """The remedy works: remove the rows, and the revision reverses (C15)."""
    cfg = _alembic_cfg()
    task_id = _seed_scoping_task(engine, with_walk=True)
    _delete_task(engine, task_id)
    try:
        command.downgrade(cfg, PRE_SLICE_REVISION)
        with engine.connect() as conn:
            assert "capability" not in {
                column["name"] for column in inspect(conn).get_columns("task")
            }
    finally:
        command.upgrade(cfg, "head")


# --- task_link's database-level rules --------------------------------------


def _link_row(
    source_task_id: uuid.UUID, target_task_id: uuid.UUID, run_id: uuid.UUID
) -> dict[str, object]:
    return {
        "link_id": uuid.uuid4(),
        "source_task_id": source_task_id,
        "target_task_id": target_task_id,
        "source_capability_run_id": run_id,
        "created_by": "owner-044-slice",
        "created_at": datetime.now(UTC),
    }


def _seed_finished_es_task(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert an Evidence search task with one succeeded walk; return both ids."""
    now = datetime.now(UTC)
    task_id = uuid.uuid4()
    scope_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    run_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=now,
            name="A finished Evidence search",
            status="active",
            updated_at=now,
            owner_user_id="owner-044-slice",
        )
    )
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent="es",
            context={},
            created_at=now,
        )
    )
    conn.execute(
        task_plan.insert().values(
            plan_id=plan_id,
            task_id=task_id,
            version=1,
            status="approved",
            payload={},
            created_at=now,
            created_by="user",
        )
    )
    conn.execute(
        capability_run.insert().values(
            capability_run_id=run_id,
            task_id=task_id,
            evidence_scope_id=scope_id,
            capability="evidence_search",
            plan_id=plan_id,
            plan_version=1,
            status="succeeded",
            started_at=now,
        )
    )
    return task_id, run_id


def _seed_bare_task(conn: Connection, capability: str = "options_scoping") -> uuid.UUID:
    now = datetime.now(UTC)
    task_id = uuid.uuid4()
    conn.execute(
        task.insert().values(
            task_id=task_id,
            created_at=now,
            name="A target Task",
            status="active",
            updated_at=now,
            owner_user_id="owner-044-slice",
            capability=capability,
        )
    )
    return task_id


def test_a_link_cannot_name_the_same_task_on_both_sides(conn: Connection) -> None:
    source_id, run_id = _seed_finished_es_task(conn)
    with pytest.raises(IntegrityError, match="ck_task_link_distinct"):
        conn.execute(task_link.insert().values(**_link_row(source_id, source_id, run_id)))


def test_a_pair_of_tasks_can_be_linked_only_once(conn: Connection) -> None:
    source_id, run_id = _seed_finished_es_task(conn)
    target_id = _seed_bare_task(conn)
    conn.execute(task_link.insert().values(**_link_row(source_id, target_id, run_id)))
    with pytest.raises(IntegrityError, match="uq_task_link_pair"):
        conn.execute(task_link.insert().values(**_link_row(source_id, target_id, run_id)))


def test_the_pinned_walk_must_belong_to_the_source_task(conn: Connection) -> None:
    """The composite FK, over ``uq_capr_id_task``: no cross-task pin (C11)."""
    source_id, _ = _seed_finished_es_task(conn)
    _other_id, other_run_id = _seed_finished_es_task(conn)
    target_id = _seed_bare_task(conn)
    with pytest.raises(IntegrityError, match="fk_task_link_source_run_task"):
        conn.execute(task_link.insert().values(**_link_row(source_id, target_id, other_run_id)))


def test_archiving_a_task_with_an_inbound_link_keeps_the_link_row(conn: Connection) -> None:
    source_id, run_id = _seed_finished_es_task(conn)
    target_id = _seed_bare_task(conn)
    conn.execute(task_link.insert().values(**_link_row(source_id, target_id, run_id)))
    conn.execute(
        task.update()
        .where(task.c.task_id == target_id)
        .values(status="archived", archived_at=datetime.now(UTC))
    )
    assert (
        conn.execute(
            select(task_link.c.link_id).where(task_link.c.target_task_id == target_id)
        ).scalar_one_or_none()
        is not None
    )


def test_an_intent_record_may_name_only_a_plan_of_its_own_task(conn: Connection) -> None:
    """``fk_scope_plan_task``, the composite guard behind ``plan_id`` (A16)."""
    now = datetime.now(UTC)
    task_id = _seed_bare_task(conn)
    other_task_id, _ = _seed_finished_es_task(conn)
    other_plan_id = conn.execute(
        select(task_plan.c.plan_id).where(task_plan.c.task_id == other_task_id)
    ).scalar_one()
    with pytest.raises(IntegrityError, match="fk_scope_plan_task"):
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=uuid.uuid4(),
                task_id=task_id,
                intent="baseline",
                context={},
                created_at=now,
                purpose="baseline",
                plan_id=other_plan_id,
            )
        )


def test_an_intent_record_s_purpose_is_closed(conn: Connection) -> None:
    task_id = _seed_bare_task(conn)
    with pytest.raises(IntegrityError, match="ck_scope_purpose"):
        conn.execute(
            evidence_scope.insert().values(
                evidence_scope_id=uuid.uuid4(),
                task_id=task_id,
                intent="baseline",
                context={},
                created_at=datetime.now(UTC),
                purpose="shortlist",
            )
        )
