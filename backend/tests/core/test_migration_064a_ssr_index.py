"""Task 064a Q9, revision ``b1e7c3a9d5f2``: the task-first screening index.

Covers the round trip (the index exists at head, is gone one revision down and
comes back on upgrade) and the rerun after a crash that left the index invalid.
Both tests move the shared worker database, so they always leave it at head.
"""

from __future__ import annotations

from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from tests.conftest import _alembic_cfg

PRE_REVISION = "f5a1c8e93b27"
REVISION = "b1e7c3a9d5f2"
_NAME = "ix_ssr_task_scope_snapshot"


def _index_def(conn: Connection) -> str | None:
    value = conn.execute(
        text("SELECT indexdef FROM pg_indexes WHERE indexname = :name"), {"name": _NAME}
    ).scalar_one_or_none()
    return None if value is None else str(value)


def _is_valid(conn: Connection) -> bool:
    return bool(
        conn.execute(
            text(
                "SELECT i.indisvalid FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE c.relname = :name"
            ),
            {"name": _NAME},
        ).scalar_one()
    )


def test_the_index_round_trips(engine: Engine) -> None:
    cfg = _alembic_cfg()
    try:
        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            definition = _index_def(conn)
            assert definition is not None
            assert definition.endswith(
                "ON public.source_screening_result USING btree "
                "(task_id, evidence_scope_id, task_source_snapshot_id)"
            )
            assert _is_valid(conn)
        command.downgrade(cfg, PRE_REVISION)
        with engine.connect() as conn:
            assert _index_def(conn) is None
        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            assert _index_def(conn) is not None
    finally:
        command.upgrade(cfg, "head")


def test_the_upgrade_rebuilds_an_index_a_crash_left_invalid(engine: Engine) -> None:
    """A CONCURRENTLY build that crashed leaves an invalid index; the rerun replaces it."""
    cfg = _alembic_cfg()
    try:
        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"UPDATE pg_index SET indisvalid = false WHERE indexrelid = '{_NAME}'::regclass"
                )
            )
            conn.commit()
            assert not _is_valid(conn)
        # Step back without the downgrade so the invalid index stays, then rerun.
        command.stamp(cfg, PRE_REVISION)
        command.upgrade(cfg, REVISION)
        with engine.connect() as conn:
            assert _is_valid(conn)
    finally:
        command.upgrade(cfg, "head")
