"""Round-trip coverage for the task 046 amendment 2 revision (``e9a4c1f7b3d2``).

amendment-2-final § 2.10, Migration (R45): one JSONB column,
``longlist_result.option_profile``, NOT NULL; a row written before the
revision reads ``{}`` after it; the downgrade drops the column. The ``engine``
fixture is session-scoped and the test database shared, so the test leaves the
chain at head and removes the task it wrote.
"""

from __future__ import annotations

import uuid

from alembic import command
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import longlist_result
from tests.conftest import _alembic_cfg
from tests.helpers import delete_task_data, now, seed_scope, seed_task_and_run

PRE_REVISION = "d8f3b6a2c4e1"
_COLUMN = "option_profile"

# The stored shape (§ 2.10): keyed [option_id][design_version].
_PROFILE = {
    "opt-1": {
        "1": {
            "lines": {
                "cost": {"sentence": "A grant paid once to each council.", "mark": "less"},
                "who_decides": {"sentence": "The Welsh Government (Wales).", "mark": None},
            },
            "setting": {"main": "local authority", "second": None},
        }
    }
}


def _columns(conn: Connection) -> dict[str, dict[str, object]]:
    return {
        str(column["name"]): dict(column)
        for column in inspect(conn).get_columns("longlist_result")
    }


def _insert_pre_revision_row(conn: Connection, task_id: uuid.UUID, run_id: uuid.UUID) -> uuid.UUID:
    """A row in the shape the table had before this revision (no ``option_profile``)."""
    scope_id = seed_scope(conn, task_id)
    row_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO longlist_result (longlist_result_id, task_id, evidence_scope_id, "
            "run_id, plan_version, themes, coverage, judgements, guesses, counts, "
            "provenance, created_at) VALUES (:l, :t, :s, :r, 1, '[]', '{}', '{}', '[]', "
            "'{}', '{}', :c)"
        ),
        {"l": row_id, "t": task_id, "s": scope_id, "r": run_id, "c": now()},
    )
    return row_id


def test_the_revision_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    task_id: uuid.UUID | None = None
    try:
        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            assert _COLUMN not in _columns(conn)
        with engine.begin() as conn:
            task_id, run_id = seed_task_and_run(conn)
            row_id = _insert_pre_revision_row(conn, task_id, run_id)

        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            column = _columns(conn)[_COLUMN]
            assert column["nullable"] is False
            # The fill default is dropped: the table matches ``schema.py``.
            assert column["default"] is None
            stored = conn.execute(
                select(longlist_result.c.option_profile).where(
                    longlist_result.c.longlist_result_id == row_id
                )
            ).scalar_one()
            assert stored == {}
            conn.execute(
                longlist_result.update()
                .where(longlist_result.c.longlist_result_id == row_id)
                .values(option_profile=_PROFILE)
            )
            assert (
                conn.execute(
                    select(longlist_result.c.option_profile).where(
                        longlist_result.c.longlist_result_id == row_id
                    )
                ).scalar_one()
                == _PROFILE
            )

        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            assert _COLUMN not in _columns(conn)

        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert _COLUMN in _columns(conn)
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)
