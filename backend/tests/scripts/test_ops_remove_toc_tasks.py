"""The theory-of-change removal script (`scripts/ops_remove_toc_tasks.py`).

Rows are committed through the shared `engine`: the script opens its own
connection and only sees committed data.
"""

from __future__ import annotations

import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from tests.helpers import delete_task_data, seed_toc_task

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ops_remove_toc_tasks.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ops_remove_toc_tasks", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["ops_remove_toc_tasks"] = module
    spec.loader.exec_module(module)
    return module


ops = _load()


def test_a_dry_run_changes_nothing_and_apply_removes_every_row(engine: Engine) -> None:
    with engine.begin() as conn:
        task_id = seed_toc_task(conn)["task_id"]
    try:
        assert ops.run(engine, apply=False, task_ids=[task_id]) == 0
        with engine.connect() as conn:
            assert conn.execute(
                text("SELECT count(*) FROM toc_box WHERE task_id = :t"), {"t": task_id}
            ).scalar_one() == 3

        assert ops.run(engine, apply=True, task_ids=[task_id]) == 0
        with engine.connect() as conn:
            tables = [
                table
                for table in inspect(conn).get_table_names()
                if "task_id" in {c["name"] for c in inspect(conn).get_columns(table)}
            ]
            left = {
                table: conn.execute(
                    text(f"SELECT count(*) FROM {table} WHERE task_id = :t"),  # noqa: S608
                    {"t": task_id},
                ).scalar_one()
                for table in tables
            }
        assert set(left.values()) == {0}, left
    finally:
        with engine.begin() as conn:
            delete_task_data(conn, task_id)


def test_a_named_task_that_is_not_a_theory_of_change_is_refused(engine: Engine) -> None:
    assert ops.run(engine, apply=True, task_ids=[uuid.uuid4()]) == 2
