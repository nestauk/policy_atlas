"""selection_result table

Task 010 (approved gated change 1): one new table — selection_result (run-scoped
coverage-aware stratified selection: executed directive + bidirectional rationale +
escalation-trigger flags), project-scope-guarded via composite FKs onto the
pre-existing uq_evidence_scope_id_project and uq_runs_run_project targets.
UNIQUE (evidence_scope_id, run_id): selection is run-local; same-run re-execution
is a loud error, retry = new run. Table count 19 -> 20.

Revision ID: c8d4f2e7a3b1
Revises: b3c7e5a9d2f4
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c8d4f2e7a3b1"
down_revision: Union[str, None] = "b3c7e5a9d2f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "selection_result",
        sa.Column("selection_result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("strategy", sa.Text(), nullable=False),
        sa.Column("budget", sa.Integer(), nullable=False),
        sa.Column("selection_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("selected", postgresql.JSONB(), nullable=False),
        sa.Column("excluded", postgresql.JSONB(), nullable=False),
        sa.Column("flags", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_selr_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_selr_run_project",
        ),
        sa.UniqueConstraint("evidence_scope_id", "run_id", name="uq_selr_scope_run"),
        sa.CheckConstraint(
            "strategy IN ('coverage_stratified_v1', 'llm_rerank_v1')",
            name="ck_selr_strategy",
        ),
        sa.CheckConstraint("budget > 0", name="ck_selr_budget_positive"),
    )


def downgrade() -> None:
    op.drop_table("selection_result")
