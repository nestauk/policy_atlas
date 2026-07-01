"""classify table

Revision ID: b5d3e8f2a7c9
Revises: a8e3f1b2c5d9
Create Date: 2026-06-30 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b5d3e8f2a7c9"
down_revision: Union[str, None] = "a8e3f1b2c5d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_classification_result",
        sa.Column("source_classification_result_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("screening_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("classified_by_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("primary_evidence_type", sa.Text(), nullable=False),
        sa.Column(
            "open_tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["screening_scope_id", "project_id"],
            ["screening_scope.screening_scope_id", "screening_scope.project_id"],
            name="fk_scr_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_source_snapshot_id", "project_id"],
            [
                "project_source_snapshot.project_source_snapshot_id",
                "project_source_snapshot.project_id",
            ],
            name="fk_scr_pss_project",
        ),
        sa.ForeignKeyConstraint(
            ["classified_by_run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_scr_run_project",
        ),
        sa.PrimaryKeyConstraint("source_classification_result_id"),
        sa.UniqueConstraint(
            "screening_scope_id", "project_source_snapshot_id",
            name="uq_scr_scope_source",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(open_tags) = 'array'",
            name="ck_scr_open_tags_array",
        ),
        sa.CheckConstraint(
            "primary_evidence_type IN ("
            " 'Systematic Review and Meta-Analysis',"
            " 'RCTs and Quasi-Experimental Studies',"
            " 'Observational Research Studies',"
            " 'Modelling & Simulation',"
            " 'Policy Syntheses & Guidance Documents',"
            " 'Qualitative & Contextual Evidence',"
            " 'Expert Opinion and Commentary',"
            " 'Other (Non-evidence documents)',"
            " 'Unknown / Insufficient information'"
            ")",
            name="ck_scr_primary_evidence_type",
        ),
    )
    op.create_index(
        "ix_scr_scope_type",
        "source_classification_result",
        ["screening_scope_id", "primary_evidence_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_scr_scope_type", table_name="source_classification_result")
    op.drop_table("source_classification_result")
