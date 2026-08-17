"""user_feedback table

In-app human feedback for task 032: a per-source "not relevant" flag and a
free-text issue report, in one append-only table keyed by a `kind`
discriminator. Nothing in the pipeline reads these rows.

Revision ID: b7c1e5a9d340
Revises: d8e4a1c7f2b9
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c1e5a9d340"
down_revision: Union[str, None] = "d8e4a1c7f2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_feedback",
        sa.Column("user_feedback_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column(
            "project_source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("page_path", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_feedback_id"),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["project_source_snapshot_id", "project_id"],
            [
                "project_source_snapshot.project_source_snapshot_id",
                "project_source_snapshot.project_id",
            ],
            name="fk_ufb_pss_project",
            match="SIMPLE",
        ),
        sa.CheckConstraint(
            "kind IN ('source_not_relevant', 'issue_report')", name="ck_ufb_kind"
        ),
        sa.CheckConstraint(
            "(kind = 'source_not_relevant'"
            " AND project_source_snapshot_id IS NOT NULL AND body IS NULL)"
            " OR (kind = 'issue_report'"
            " AND project_source_snapshot_id IS NULL AND body IS NOT NULL)",
            name="ck_ufb_shape",
        ),
    )
    op.create_index(
        "ux_ufb_source_flag",
        "user_feedback",
        ["project_source_snapshot_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("kind = 'source_not_relevant'"),
    )
    op.create_index("ix_ufb_project_kind", "user_feedback", ["project_id", "kind"])


def downgrade() -> None:
    op.drop_index("ix_ufb_project_kind", table_name="user_feedback")
    op.drop_index("ux_ufb_source_flag", table_name="user_feedback")
    op.drop_table("user_feedback")
