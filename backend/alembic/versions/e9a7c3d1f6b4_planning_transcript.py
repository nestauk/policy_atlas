"""planning_transcript table

Durable per-project planner turns for task 027. The table retains the raw
planner state and separately retains the projected HTTP response so planner
rehydration and idempotent response replay cannot drift into one another.

Revision ID: e9a7c3d1f6b4
Revises: c6e2b4f8a1d3
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e9a7c3d1f6b4"
down_revision: Union[str, None] = "c6e2b4f8a1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "planning_transcript",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("reply", sa.Text(), nullable=True),
        sa.Column("planner_state", postgresql.JSONB(), nullable=True),
        sa.Column("response", postgresql.JSONB(), nullable=True),
        sa.Column("suggestions", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "client_turn_id", name="uq_ptr_project_client_turn"),
        sa.UniqueConstraint("project_id", "turn_index", name="uq_ptr_project_turn_index"),
        sa.CheckConstraint("status IN ('pending', 'completed', 'failed')", name="ck_ptr_status"),
        sa.CheckConstraint("jsonb_typeof(suggestions) = 'array'", name="ck_ptr_suggestions_array"),
    )


def downgrade() -> None:
    op.drop_table("planning_transcript")
