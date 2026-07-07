"""grouping_result table

Task 012 (approved gated change 1): one new run-scoped table — grouping_result,
the facet-grouping roll-up (one row per (evidence_scope_id, run_id), carrying the
facet, the executed extraction_run_id, grouping provenance with the inherited
extraction base, the groups themselves, counts and flags). Groups are run-local
execution state (capability.md § Cluster persistence): memberships never promote
to canonical state. Project-scope-guarded via composite FKs per the repo pattern.
Table count 23 -> 24.

Revision ID: e2f8c4a1d7b3
Revises: d4e9b2f7a1c5
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2f8c4a1d7b3"
down_revision: Union[str, None] = "d4e9b2f7a1c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grouping_result",
        sa.Column("grouping_result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("facet", sa.Text(), nullable=False),
        sa.Column("grouping_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("groups", postgresql.JSONB(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("flags", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_grr_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_grr_run_project",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "extraction_run_id"],
            ["extraction_result.evidence_scope_id", "extraction_result.run_id"],
            name="fk_grr_extraction",
        ),
        sa.UniqueConstraint("evidence_scope_id", "run_id", name="uq_grr_scope_run"),
        sa.CheckConstraint(
            "facet IN ('intervention', 'outcome', 'population')",
            name="ck_grr_facet",
        ),
    )


def downgrade() -> None:
    op.drop_table("grouping_result")
