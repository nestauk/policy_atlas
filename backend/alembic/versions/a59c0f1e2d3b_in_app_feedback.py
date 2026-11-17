"""in-app feedback: feedback_event, missing_paper_resolution, user_profile, runs.trace_id

Task 062 (ADR 0045): one row for each piece of feedback a user gives, where
the pipeline lost a paper a user reported as missing, a user's onboarding
answers, and the Langfuse trace of each component run.

Upgrade
    Creates the three tables and adds the nullable ``runs.trace_id``. Old runs
    keep NULL: feedback on them is saved but has no Langfuse score.

Downgrade
    Drops the column and the three tables. Lossy: every feedback row and
    profile is deleted.

Revision ID: a59c0f1e2d3b
Revises: f5a1c8e93b27
Create Date: 2026-11-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a59c0f1e2d3b"
down_revision: str | Sequence[str] | None = "f5a1c8e93b27"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the feedback tables and add the trace id to runs."""
    # Transaction-scoped: `runs` is written by every live walk, so do not
    # queue behind one for longer than this.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("runs", sa.Column("trace_id", sa.Text(), nullable=True))
    op.create_table(
        "feedback_event",
        sa.Column("feedback_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("capability_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("surface", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("pa_version", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("feedback_event_id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"]),
        sa.ForeignKeyConstraint(["capability_run_id"], ["capability_run.capability_run_id"]),
        sa.CheckConstraint(
            "kind IN ('citation_flag', 'screening_override', 'missing_paper', 'use_intent', "
            "'claim_flag', 'problem_report')",
            name="ck_feedback_event_kind",
        ),
        sa.CheckConstraint(
            "surface IN ('report_references', 'sources_all', 'report_foot', 'sources_tab', "
            "'screened_out_row', 'report_key_findings', 'report_claim_sidebar', 'app_header')",
            name="ck_feedback_event_surface",
        ),
        sa.CheckConstraint(
            "target_type IN ('document', 'run', 'report', 'claim')",
            name="ck_feedback_event_target_type",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_feedback_event_payload_object"
        ),
    )
    op.create_index("ix_feedback_event_run", "feedback_event", ["capability_run_id"])
    op.create_index("ix_feedback_event_user", "feedback_event", ["user_id"])
    op.create_index("ix_feedback_event_kind_created", "feedback_event", ["kind", "created_at"])
    op.create_index("ix_feedback_event_target", "feedback_event", ["target_type", "target_id"])
    op.create_index(
        "uq_feedback_event_active_toggle",
        "feedback_event",
        ["user_id", "capability_run_id", "target_type", "target_id", "kind"],
        unique=True,
        postgresql_where=sa.text(
            "retracted_at IS NULL AND kind IN "
            "('citation_flag', 'screening_override', 'claim_flag', 'use_intent')"
        ),
    )
    op.create_table(
        "missing_paper_resolution",
        sa.Column("feedback_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolved_id", sa.Text(), nullable=True),
        sa.Column("failure_stage", sa.Text(), nullable=False),
        sa.Column("resolver_confidence", sa.Float(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("feedback_event_id"),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_event.feedback_event_id"]),
        sa.CheckConstraint(
            "failure_stage IN ('unresolved', 'cited', 'not_cited', 'not_selected', "
            "'screened_out_s2', 'screened_out_s1', 'acquired_only', 'not_retrieved')",
            name="ck_missing_paper_resolution_stage",
        ),
    )
    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=True),
        sa.Column("team_type", sa.Text(), nullable=True),
        sa.Column("primary_job", sa.Text(), nullable=True),
        sa.Column("secondary_job", sa.Text(), nullable=True),
        sa.Column("panel_opt_in", sa.Boolean(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_once_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"]),
    )


def downgrade() -> None:
    """Drop the feedback tables and the trace id. Lossy."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_table("user_profile")
    op.drop_table("missing_paper_resolution")
    op.drop_table("feedback_event")
    op.drop_column("runs", "trace_id")
