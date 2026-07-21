"""search_coverage_record table

New table for task 007 (approved gated change 2): one coverage record per
acquire run — the record that operationalises "adequately-searched".

Revision ID: f9c6e3b8d4a2
Revises: e7b4d2a1c8f3
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f9c6e3b8d4a2"
down_revision: Union[str, None] = "e7b4d2a1c8f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_coverage_record",
        sa.Column("search_coverage_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("acquired_by_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("backends", postgresql.JSONB(), nullable=False),
        sa.Column("scope_filters", postgresql.JSONB(), nullable=False),
        sa.Column("stop_condition", sa.Text(), nullable=False),
        sa.Column("adequacy_verdict", sa.Text(), nullable=False),
        sa.Column("verdict_origin", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_scov_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["acquired_by_run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_scov_run_project",
        ),
        sa.PrimaryKeyConstraint("search_coverage_record_id"),
        sa.UniqueConstraint("acquired_by_run_id", name="uq_scov_run"),
        sa.CheckConstraint(
            "stop_condition IN ('breadth_truncated', 're_searched_still_thin', 'error')",
            name="ck_scov_stop_condition",
        ),
        sa.CheckConstraint(
            "adequacy_verdict IN ('adequate', 'inadequate')",
            name="ck_scov_verdict",
        ),
        sa.CheckConstraint(
            "verdict_origin IN ('model', 'human')",
            name="ck_scov_verdict_origin",
        ),
        sa.CheckConstraint("jsonb_typeof(backends) = 'array'", name="ck_scov_backends_array"),
        sa.CheckConstraint(
            "jsonb_typeof(scope_filters) = 'object'", name="ck_scov_filters_object"
        ),
    )


def downgrade() -> None:
    op.drop_table("search_coverage_record")
