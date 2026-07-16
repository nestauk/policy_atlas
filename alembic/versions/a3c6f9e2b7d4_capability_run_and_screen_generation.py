"""capability_run table + screen_generation

Task 024 (approved gated change: contract decisions 2 and 7b) — one migration,
two changes, table count 27 -> 28:

1. ``capability_run``: the steering-surface walk entity — one row per
   orchestrated capability walk (v1: ``capability = 'evidence_base'`` only),
   carrying the approved plan identity (``plan_id``/``plan_version``) at walk
   open and the walk's terminal ``status``. Cross-project FK guard on
   ``(evidence_scope_id, project_id)`` (the selection_result precedent) plus
   ``UNIQUE (capability_run_id, project_id)`` as the composite-FK target for
   ``runs``. ``runs`` gains a nullable ``capability_run_id`` + composite FK
   ``(capability_run_id, project_id)`` (MATCH SIMPLE — NULL skips the check,
   the synthesis_result optional-reference precedent), attributing each
   component run to the walk it executed within.

2. ``source_screening_result.screen_generation`` (generation supersession,
   decision 7b, reversing plan-review B1's no-schema exclusion): criteria-
   changed re-screen writes fresh rows at ``generation = max+1``; old rows
   are never mutated. The partial unique index ``uq_ssr_scope_source_stage``
   (task 014, one non-failed row per scope/source/stage) widens to include
   ``screen_generation`` so a fresh generation's stage-1 row no longer
   collides with a prior generation's row at the same stage — same partial
   predicate (``status != 'failed'``), same index name.

Revision ID: a3c6f9e2b7d4
Revises: 7a4d9c2e1f6b
Create Date: 2026-07-16 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a3c6f9e2b7d4"
down_revision: Union[str, None] = "7a4d9c2e1f6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "capability_run",
        sa.Column("capability_run_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("capability", sa.Text(), nullable=False),
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_capr_scope_project",
        ),
        sa.UniqueConstraint("capability_run_id", "project_id", name="uq_capr_id_project"),
        sa.CheckConstraint("capability IN ('evidence_base')", name="ck_capr_capability"),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'degraded', 'failed', 'aborted')",
            name="ck_capr_status",
        ),
    )

    op.add_column(
        "runs",
        sa.Column("capability_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_runs_capability_run_project",
        "runs",
        "capability_run",
        ["capability_run_id", "project_id"],
        ["capability_run_id", "project_id"],
    )

    op.add_column(
        "source_screening_result",
        sa.Column("screen_generation", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_ssr_generation_nonneg",
        "source_screening_result",
        "screen_generation >= 0",
    )

    op.drop_index("uq_ssr_scope_source_stage", table_name="source_screening_result")
    op.create_index(
        "uq_ssr_scope_source_stage",
        "source_screening_result",
        ["evidence_scope_id", "project_source_snapshot_id", "screen_stage", "screen_generation"],
        unique=True,
        postgresql_where=sa.text("status != 'failed'"),
    )


def downgrade() -> None:
    op.drop_index("uq_ssr_scope_source_stage", table_name="source_screening_result")
    op.create_index(
        "uq_ssr_scope_source_stage",
        "source_screening_result",
        ["evidence_scope_id", "project_source_snapshot_id", "screen_stage"],
        unique=True,
        postgresql_where=sa.text("status != 'failed'"),
    )
    op.drop_constraint("ck_ssr_generation_nonneg", "source_screening_result", type_="check")
    op.drop_column("source_screening_result", "screen_generation")

    op.drop_constraint("fk_runs_capability_run_project", "runs", type_="foreignkey")
    op.drop_column("runs", "capability_run_id")

    op.drop_table("capability_run")
