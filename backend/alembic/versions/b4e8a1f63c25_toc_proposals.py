"""task 054 theory of change — proposals: suggested edits that wait for the user

Increment 2, slice D (contract C45, C46). The review after edits and the Task
Agent's chat both propose edits; each proposal waits for the user's Accept or
Reject, edit by edit.

Upgrade
    ``toc_proposal``: ``proposal_id``, ``task_id``, ``source`` (``review`` ·
    ``chat``), ``summary`` (one line), ``edits`` (JSONB list: each edit's
    operation, its arguments, its reason and its ``status`` ``pending`` ·
    ``accepted`` · ``rejected``), ``report_findings`` (JSONB list of report
    sections that no longer match, with why), ``status`` (``open`` ·
    ``closed``), ``created_at``, ``updated_at``, ``revision``.

Downgrade
    Drops the table.

Revision ID: b4e8a1f63c25
Revises: 9d1e4c7a2b10
Create Date: 2026-10-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b4e8a1f63c25"
down_revision: str | Sequence[str] | None = "9d1e4c7a2b10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create ``toc_proposal``."""
    op.create_table(
        "toc_proposal",
        sa.Column("proposal_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task.task_id"), nullable=False
        ),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "edits", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "report_findings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.CheckConstraint("source IN ('review', 'chat')", name="ck_toc_proposal_source"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="ck_toc_proposal_status"),
    )
    op.create_index("ix_toc_proposal_task", "toc_proposal", ["task_id"])


def downgrade() -> None:
    """Drop it."""
    op.drop_index("ix_toc_proposal_task", table_name="toc_proposal")
    op.drop_table("toc_proposal")
