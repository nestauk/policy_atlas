"""New rows are private by default (owner amendment, 2026-08-26).

The 033 contract's owner call (c) set the ``visibility`` column default to
``org``; the staging canary reversed it — a newly created project or
portfolio must be private until its owner deliberately shares it. Only the
COLUMN DEFAULT changes: rows the 033 migration already stamped ``org`` stay
as they are, because the only paths that can make them reachable (enrolment,
``rows assign``) both privatise on the way through, and the create paths
deliberately rely on the column default rather than writing a value.

Revision ID: d8e2a6c4f7b1
Revises: a4f1c8e3b6d2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d8e2a6c4f7b1"
down_revision = "a4f1c8e3b6d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ALTER TABLE takes ACCESS EXCLUSIVE even for a default change; same
    # ceiling and same SET LOCAL scoping rationale as a4f1c8e3b6d2.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.alter_column(
        "project",
        "visibility",
        existing_type=sa.Text(),
        existing_nullable=False,
        server_default="private",
    )
    op.alter_column(
        "portfolio",
        "visibility",
        existing_type=sa.Text(),
        existing_nullable=False,
        server_default="private",
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.alter_column(
        "project",
        "visibility",
        existing_type=sa.Text(),
        existing_nullable=False,
        server_default="org",
    )
    op.alter_column(
        "portfolio",
        "visibility",
        existing_type=sa.Text(),
        existing_nullable=False,
        server_default="org",
    )
