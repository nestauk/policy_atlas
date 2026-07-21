"""orchestration_plan table

New table for task 017 (thin v1 orchestrator/planning slice): one row per plan
version — an intent-to-plan lineage that a project accumulates via appended
amendment rows (never in-place edits). ``evidence_scope_id`` is nullable and
resolved at approval; the composite cross-project FK guard binds only once it
is set (MATCH SIMPLE, per synthesis_result's optional-reference precedent).

Revision ID: d2f8a4c1e9b7
Revises: c9e4b7f2d1a8
Create Date: 2026-07-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d2f8a4c1e9b7"
down_revision: Union[str, None] = "c9e4b7f2d1a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orchestration_plan",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_oplan_scope_project",
        ),
        sa.PrimaryKeyConstraint("plan_id"),
        sa.UniqueConstraint("project_id", "version", name="uq_oplan_project_version"),
        sa.CheckConstraint(
            "status IN ('proposed', 'approved', 'superseded', 'abandoned')",
            name="ck_oplan_status",
        ),
        sa.CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_oplan_payload_object"),
    )


def downgrade() -> None:
    op.drop_table("orchestration_plan")
