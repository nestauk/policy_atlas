"""screen tables

Revision ID: a8e3f1b2c5d9
Revises: c4f2a9b3e8d1
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a8e3f1b2c5d9"
down_revision: Union[str, None] = "c4f2a9b3e8d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Composite unique on existing table — FK target for source_screening_result
    op.create_unique_constraint(
        "uq_pss_id_project",
        "project_source_snapshot",
        ["project_source_snapshot_id", "project_id"],
    )

    # 2. New table: screening_scope
    op.create_table(
        "screening_scope",
        sa.Column("screening_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.PrimaryKeyConstraint("screening_scope_id"),
        sa.UniqueConstraint("screening_scope_id", "project_id", name="uq_screening_scope_id_project"),
    )

    # 3. New table: source_screening_result
    op.create_table(
        "source_screening_result",
        sa.Column("source_screening_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screening_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screened_by_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("screen_basis", sa.Text(), nullable=True),
        sa.Column("screen_decision_confidence", sa.Float(), nullable=True),
        sa.Column("screened_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_scope_id", "project_id"],
            ["screening_scope.screening_scope_id", "screening_scope.project_id"],
            name="fk_ssr_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_source_snapshot_id", "project_id"],
            ["project_source_snapshot.project_source_snapshot_id", "project_source_snapshot.project_id"],
            name="fk_ssr_pss_project",
        ),
        sa.ForeignKeyConstraint(
            ["screened_by_run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_ssr_run_project",
        ),
        sa.PrimaryKeyConstraint("source_screening_result_id"),
        sa.UniqueConstraint("screening_scope_id", "project_source_snapshot_id", name="uq_ssr_scope_source"),
        sa.CheckConstraint("status IN ('relevant', 'not_relevant', 'failed')", name="ck_ssr_status"),
        sa.CheckConstraint(
            "screen_basis IS NULL OR screen_basis IN ('title_abstract', 'title_only')",
            name="ck_ssr_basis",
        ),
        sa.CheckConstraint(
            "screen_decision_confidence IS NULL"
            " OR (screen_decision_confidence >= 0.0 AND screen_decision_confidence <= 1.0)",
            name="ck_ssr_confidence_range",
        ),
        sa.CheckConstraint(
            "status = 'failed' OR (screen_basis IS NOT NULL AND screen_decision_confidence IS NOT NULL)",
            name="ck_ssr_non_null_when_decided",
        ),
        sa.CheckConstraint(
            "status != 'failed' OR (screen_basis IS NULL AND screen_decision_confidence IS NULL)",
            name="ck_ssr_null_when_failed",
        ),
    )

    # 4. Index for efficient filtered reads
    op.create_index("ix_ssr_scope_status", "source_screening_result", ["screening_scope_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_ssr_scope_status", table_name="source_screening_result")
    op.drop_table("source_screening_result")
    op.drop_table("screening_scope")
    op.drop_constraint("uq_pss_id_project", "project_source_snapshot", type_="unique")
