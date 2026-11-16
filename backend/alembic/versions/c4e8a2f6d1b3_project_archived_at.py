"""task 058 round 11 — a project can be archived

Adds one empty column, ``project.archived_at`` (when the project was archived,
``NULL`` while it is in use). Archiving a project hides it from the Projects
list's default view; it changes nothing about the project's tasks.

The column is nullable with no default, so adding it does not rewrite the
table and takes a moment. Downgrade drops it again (any archive times are lost,
and the archived projects show as in use).

Revision ID: c4e8a2f6d1b3
Revises: 0914321f8de4
Create Date: 2026-11-06 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a2f6d1b3"
down_revision: str | None = "0914321f8de4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("project", "archived_at")
