"""Add cohorts: named groups of people for pilots and research (task 065, owner 2026-11-18).

A cohort is a label, separate from the organisation (which decides who sees
whose work): one person can be in several cohorts, and one cohort can span
organisations. A cohort may carry the two quota overrides; they sit between the
person's own and the organisation's. ``cohort_member`` links people to cohorts; deleting a cohort
deletes its links. The ops role may create, edit and delete cohorts and add or
remove members, and nothing else on these tables.

Revision ID: d7e5f3a2b0c9
Revises: c6d4e2f1a9b8
Create Date: 2026-11-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7e5f3a2b0c9"
down_revision: str | Sequence[str] | None = "c6d4e2f1a9b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the two cohort tables and grant the ops role its share."""
    op.create_table(
        "cohort",
        sa.Column("cohort_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=True),
        sa.Column("ends_on", sa.Date(), nullable=True),
        sa.Column(
            "links", postgresql.ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("task_quota_per_year", sa.Integer(), nullable=True),
        sa.Column("runs_per_user", sa.Integer(), nullable=True),
        sa.UniqueConstraint("name", name="uq_cohort_name"),
        sa.CheckConstraint("task_quota_per_year >= 0", name="ck_cohort_task_quota_nonneg"),
        sa.CheckConstraint("runs_per_user >= 0", name="ck_cohort_runs_nonneg"),
        sa.CheckConstraint(
            "starts_on IS NULL OR ends_on IS NULL OR ends_on >= starts_on",
            name="ck_cohort_dates_ordered",
        ),
    )
    op.create_table(
        "cohort_member",
        sa.Column(
            "cohort_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cohort.cohort_id", ondelete="CASCADE"), primary_key=True,
        ),
        sa.Column(
            "user_id", sa.Text(), sa.ForeignKey("app_user.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_cohort_member_user_id", "cohort_member", ["user_id"])
    op.execute("GRANT SELECT, INSERT, DELETE ON cohort TO pa_ops")
    op.execute("GRANT UPDATE (name, description, starts_on, ends_on, links, task_quota_per_year, runs_per_user) ON cohort TO pa_ops")
    op.execute("GRANT SELECT, INSERT, DELETE ON cohort_member TO pa_ops")


def downgrade() -> None:
    """Drop the cohort tables (their grants go with them)."""
    op.drop_index("ix_cohort_member_user_id", table_name="cohort_member")
    op.drop_table("cohort_member")
    op.drop_table("cohort")
