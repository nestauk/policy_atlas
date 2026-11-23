"""task 064a Q9: an index on screening results that starts with the task

The effective-screen read (``effective_screen_rows``) ranks screening results
per task, scope and document. Every caller filters by one task, but no index
on ``source_screening_result`` started with ``task_id``, so PostgreSQL read
every task's rows on each call. This index matches the ranking's key, so a
call reads only the rows of the task it asks about.

Upgrade
    Builds ``ix_ssr_task_scope_snapshot`` on ``source_screening_result
    (task_id, evidence_scope_id, task_source_snapshot_id)``. It is built
    ``CONCURRENTLY`` (the app keeps reading and writing the table while it
    builds) and therefore outside a transaction. If an earlier build crashed
    part-way, PostgreSQL keeps a half-built ("invalid") index that
    ``IF NOT EXISTS`` would skip, so that leftover is dropped first and the
    rerun builds it again (the ``a3d8f6c1e2b4`` pattern).

Downgrade
    Drops the index, also ``CONCURRENTLY``. No data changes either way.

Revision ID: b1e7c3a9d5f2
Revises: f5a1c8e93b27
Create Date: 2026-11-16 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "b1e7c3a9d5f2"
down_revision: str | Sequence[str] | None = "f5a1c8e93b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NAME = "ix_ssr_task_scope_snapshot"


def upgrade() -> None:
    """Build the task-first index without blocking the app."""
    with op.get_context().autocommit_block():
        # A timed-out CONCURRENTLY build leaves an invalid index, which the
        # rerun drops and rebuilds (below).
        op.execute("SET lock_timeout = '10s'")
        invalid = (
            op.get_bind()
            .execute(
                text(
                    "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                    "WHERE c.relname = :name AND NOT i.indisvalid"
                ),
                {"name": _NAME},
            )
            .first()
        )
        if invalid is not None:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_NAME}")
        op.execute(
            f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {_NAME} "
            "ON source_screening_result (task_id, evidence_scope_id, task_source_snapshot_id)"
        )
        op.execute("RESET lock_timeout")


def downgrade() -> None:
    """Drop the task-first index without blocking the app."""
    with op.get_context().autocommit_block():
        op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {_NAME}")
