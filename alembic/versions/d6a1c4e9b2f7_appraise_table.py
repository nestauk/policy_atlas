"""appraise table

Revision ID: d6a1c4e9b2f7
Revises: b5d3e8f2a7c9
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d6a1c4e9b2f7"
down_revision: Union[str, None] = "b5d3e8f2a7c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_appraisal_result",
        sa.Column("source_appraisal_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screening_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("appraised_by_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quality_score", sa.SmallInteger(), nullable=False),
        sa.Column("rubric_version", sa.Text(), nullable=False),
        sa.Column("appraised_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_scope_id", "project_id"],
            ["screening_scope.screening_scope_id", "screening_scope.project_id"],
            name="fk_sar_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_source_snapshot_id", "project_id"],
            [
                "project_source_snapshot.project_source_snapshot_id",
                "project_source_snapshot.project_id",
            ],
            name="fk_sar_pss_project",
        ),
        sa.ForeignKeyConstraint(
            ["appraised_by_run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_sar_run_project",
        ),
        sa.PrimaryKeyConstraint("source_appraisal_result_id"),
        sa.UniqueConstraint(
            "screening_scope_id", "project_source_snapshot_id",
            name="uq_sar_scope_source",
        ),
        sa.CheckConstraint(
            "quality_score BETWEEN 1 AND 5",
            name="ck_sar_quality_score",
        ),
    )
    op.create_index(
        "ix_sar_scope_score",
        "source_appraisal_result",
        ["screening_scope_id", "quality_score"],
    )


def downgrade() -> None:
    op.drop_index("ix_sar_scope_score", table_name="source_appraisal_result")
    op.drop_table("source_appraisal_result")
