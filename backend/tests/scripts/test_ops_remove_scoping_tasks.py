"""Coverage for the options-scoping removal operator script (`scripts/ops_remove_scoping_tasks.py`).

Every test seeds and cleans up *committed* rows through the shared session
`engine` fixture — not the per-test rolled-back `conn` fixture — because the
script opens its own connections against `DATABASE_URL` and so can only see
committed data. The last test downgrades and re-upgrades the live schema
(`b5e1d7a4c026`), the revision this script exists to unblock; restoring head
before the test ends is mandatory since `engine` is session-scoped and shared.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from alembic import command
from sqlalchemy import text, update
from sqlalchemy.engine import Engine

from policy_atlas.core.schema import (
    capability_run,
    task,
    task_agent_transcript,
    task_link,
    task_plan,
)
from tests.conftest import _alembic_cfg
from tests.helpers import now, seed_scope, seed_task_and_run

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops_remove_scoping_tasks.py"

_PRE_044 = "a7d3f1c8e2b5"  # b5e1d7a4c026's down_revision


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ops_remove_scoping_tasks", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ops_remove_scoping_tasks"] = module
    spec.loader.exec_module(module)
    return module


ops = _load()


def _seed_scoping_task(engine: Engine) -> dict[str, uuid.UUID]:
    """Commit an options_scoping task with a run, a scope, a plan and a walk.

    Returns the ids (`task_id`, `run_id`, `scope_id`, `plan_id`,
    `capability_run_id`).
    """
    with engine.begin() as conn:
        task_id, run_id = seed_task_and_run(conn)
        conn.execute(
            update(task).where(task.c.task_id == task_id).values(capability="options_scoping")
        )
        scope_id = seed_scope(conn, task_id)
        plan_id = uuid.uuid4()
        conn.execute(
            task_plan.insert().values(
                plan_id=plan_id,
                task_id=task_id,
                conversation_id=None,
                evidence_scope_id=None,
                version=1,
                status="approved",
                payload={},
                created_at=now(),
                created_by="test",
                approved_at=now(),
            )
        )
        capr_id = uuid.uuid4()
        conn.execute(
            capability_run.insert().values(
                capability_run_id=capr_id,
                task_id=task_id,
                evidence_scope_id=scope_id,
                capability="options_scoping",
                plan_id=plan_id,
                plan_version=1,
                status="succeeded",
                session_id=None,
                started_at=now(),
                ended_at=now(),
            )
        )
    return {
        "task_id": task_id,
        "run_id": run_id,
        "scope_id": scope_id,
        "plan_id": plan_id,
        "capability_run_id": capr_id,
    }


def _delete_scoping_task_rows(engine: Engine, ids: dict[str, uuid.UUID]) -> None:
    """Manual cleanup for a seeded scoping task, FK-ordered, when apply never ran."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM task_link WHERE source_task_id = :tid OR "
                           "target_task_id = :tid"), {"tid": ids["task_id"]})
        conn.execute(text("DELETE FROM task_agent_transcript WHERE task_id = :tid"),
                     {"tid": ids["task_id"]})
        conn.execute(text("DELETE FROM runs WHERE task_id = :tid"), {"tid": ids["task_id"]})
        conn.execute(text("DELETE FROM capability_run WHERE task_id = :tid"),
                     {"tid": ids["task_id"]})
        conn.execute(text("DELETE FROM plan WHERE task_id = :tid"), {"tid": ids["task_id"]})
        conn.execute(text("DELETE FROM evidence_scope WHERE task_id = :tid"),
                     {"tid": ids["task_id"]})
        conn.execute(text("DELETE FROM task WHERE task_id = :tid"), {"tid": ids["task_id"]})


def _row_exists(engine: Engine, table: str, task_id: uuid.UUID) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text(f"SELECT count(*) FROM {table} WHERE task_id = :tid"),
                {"tid": task_id},
            ).scalar_one()
        )


def _every_scoping_task(engine: Engine) -> list[uuid.UUID]:
    with engine.connect() as conn:
        return list(ops._scoping_task_ids(conn))


def test_apply_needs_named_scoping_tasks_and_deletes_nothing_without(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    """S4: ``--apply`` never removes every scoping task; it takes explicit ids."""
    ids = _seed_scoping_task(engine)
    with engine.begin() as conn:
        es_task_id, _ = seed_task_and_run(conn)
    try:
        assert ops.run(engine, apply=True) == 2
        assert "--task-id" in capsys.readouterr().err
        assert ops.run(engine, apply=True, task_ids=[]) == 2
        assert ops.run(engine, apply=True, task_ids=[ids["task_id"], es_task_id]) == 2
        assert str(es_task_id) in capsys.readouterr().err
        assert _row_exists(engine, "task", ids["task_id"]) == 1
        assert _row_exists(engine, "task", es_task_id) == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM runs WHERE task_id = :tid"), {"tid": es_task_id})
            conn.execute(text("DELETE FROM task WHERE task_id = :tid"), {"tid": es_task_id})
        _delete_scoping_task_rows(engine, ids)


def test_list_mode_reports_counts_and_deletes_nothing(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    ids = _seed_scoping_task(engine)
    try:
        assert ops.run(engine, apply=False) == 0
        out = capsys.readouterr().out
        assert str(ids["task_id"]) in out
        assert "capability_run=1" in out
        assert "runs=1" in out
        assert "evidence_scope=1" in out
        assert "results=0" in out
        assert "task_link=0" in out

        assert _row_exists(engine, "task", ids["task_id"]) == 1
        assert _row_exists(engine, "capability_run", ids["task_id"]) == 1
        assert _row_exists(engine, "runs", ids["task_id"]) == 1
        assert _row_exists(engine, "evidence_scope", ids["task_id"]) == 1
    finally:
        _delete_scoping_task_rows(engine, ids)


def test_refuses_when_an_evidence_search_task_links_to_it(
    engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    scoping = _seed_scoping_task(engine)
    with engine.begin() as conn:
        es_task_id, _ = seed_task_and_run(conn)
        link_id = uuid.uuid4()
        conn.execute(
            task_link.insert().values(
                link_id=link_id,
                source_task_id=scoping["task_id"],
                target_task_id=es_task_id,
                source_capability_run_id=scoping["capability_run_id"],
                created_by="test",
                created_at=now(),
            )
        )
    try:
        assert ops.run(engine, apply=False) == 2
        err = capsys.readouterr().err
        assert str(scoping["task_id"]) in err
        assert str(es_task_id) in err

        assert ops.run(engine, apply=True, task_ids=[scoping["task_id"]]) == 2
        assert _row_exists(engine, "task", scoping["task_id"]) == 1
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM task_link WHERE link_id = :lid"), {"lid": link_id})
            conn.execute(text("DELETE FROM runs WHERE task_id = :tid"), {"tid": es_task_id})
            conn.execute(text("DELETE FROM task WHERE task_id = :tid"), {"tid": es_task_id})
        _delete_scoping_task_rows(engine, scoping)


def test_apply_removes_every_scoping_row_and_then_the_downgrade_succeeds(
    engine: Engine,
) -> None:
    cfg = _alembic_cfg()
    a = _seed_scoping_task(engine)
    with engine.begin() as conn:
        b_task_id, _ = seed_task_and_run(conn)
        conn.execute(
            update(task).where(task.c.task_id == b_task_id).values(capability="options_scoping")
        )
        link_id = uuid.uuid4()
        conn.execute(
            task_link.insert().values(
                link_id=link_id,
                source_task_id=a["task_id"],
                target_task_id=b_task_id,
                source_capability_run_id=a["capability_run_id"],
                created_by="test",
                created_at=now(),
            )
        )
        conn.execute(
            task_agent_transcript.insert().values(
                id=uuid.uuid4(),
                task_id=a["task_id"],
                conversation_id=None,
                client_turn_id=uuid.uuid4(),
                turn_index=0,
                user_message="Seeded for the removal test",
                reply=None,
                task_agent_state=None,
                response=None,
                part=None,
                suggestions=[],
                status="pending",
                created_at=now(),
                completed_at=None,
            )
        )

    try:
        assert ops.run(engine, apply=True, task_ids=_every_scoping_task(engine)) == 0

        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT count(*) FROM task WHERE capability = 'options_scoping'")
                ).scalar_one()
                == 0
            )
            assert (
                conn.execute(
                    text(
                        "SELECT count(*) FROM capability_run WHERE capability = 'options_scoping'"
                    )
                ).scalar_one()
                == 0
            )

        # A fresh scoping task, seeded AFTER the sweep above, must still block
        # the downgrade — the guard is a live check, not a one-off gate.
        _seed_scoping_task(engine)
        try:
            with pytest.raises(RuntimeError) as caught:
                command.downgrade(cfg, _PRE_044)
            message = str(caught.value)
            assert "ops_remove_scoping_tasks" in message
        finally:
            assert ops.run(engine, apply=True, task_ids=_every_scoping_task(engine)) == 0

        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT count(*) FROM task WHERE capability = 'options_scoping'")
                ).scalar_one()
                == 0
            )

        command.downgrade(cfg, _PRE_044)
    finally:
        command.upgrade(cfg, "head")
