"""in-app feedback: feedback_event, missing_paper_resolution, user_profile, runs.trace_id

Postgres is the system of record for in-app feedback.

Upgrade
    Adds the nullable ``runs.trace_id`` column (the Langfuse trace of a component
    run) and three tables: ``feedback_event`` (one row per feedback record),
    ``missing_paper_resolution`` (the resolver's answer for a missing-paper
    report) and ``user_profile`` (the onboarding profile).

Downgrade
    Drops the three tables and the column. All feedback and profile data is lost.

The value lists below are a frozen copy of the lists in ``core/schema.py`` at
the time of this revision. A later change to a list needs its own revision.

Revision ID: a4c7e19d5b32
Revises: a3c9e1f7b2d4
Create Date: 2026-11-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a4c7e19d5b32"
down_revision: str | Sequence[str] | None = "a3c9e1f7b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = (
    "'citation_flag', 'missing_paper', 'screening_override', "
    "'use_intent', 'claim_flag', 'problem_report'"
)
TOGGLE_KINDS = "'citation_flag', 'screening_override', 'use_intent', 'claim_flag'"
SURFACES = (
    "'report_references', 'sources_all', 'report_foot', 'sources_tab', "
    "'screened_out_row', 'report_key_findings', 'report_claim_sidebar', 'app_header'"
)
TARGET_TYPES = "'document', 'run', 'report', 'claim'"
FAILURE_STAGES = (
    "'unresolved', 'cited', 'not_cited', 'not_selected', 'screened_out_s2', "
    "'screened_out_s1', 'acquired_only', 'not_retrieved'"
)
TEAM_TYPES = "'policy', 'analysis_evidence', 'strategy_finance', 'private_office', 'other'"
JOBS = "'j1', 'j2', 'j3', 'j4', 'j5', 'j6', 'j7', 'other'"
SOURCES = "'signup', 'migration', 'waitlist'"


def upgrade() -> None:
    """Add the trace id column and the three feedback tables."""
    # ADD COLUMN takes a short exclusive lock on `runs`; give up quickly
    # rather than queue behind a long component transaction.
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
        sa.CheckConstraint(f"kind IN ({KINDS})", name="ck_feedback_event_kind"),
        sa.CheckConstraint(f"surface IN ({SURFACES})", name="ck_feedback_event_surface"),
        sa.CheckConstraint(
            f"target_type IN ({TARGET_TYPES})", name="ck_feedback_event_target_type"
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
        ["user_id", "target_type", "target_id", "kind"],
        unique=True,
        postgresql_where=sa.text(f"retracted_at IS NULL AND kind IN ({TOGGLE_KINDS})"),
    )

    op.create_table(
        "missing_paper_resolution",
        sa.Column("feedback_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resolved_id", sa.Text(), nullable=True),
        sa.Column("failure_stage", sa.Text(), nullable=True),
        sa.Column("resolver_confidence", sa.Float(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("feedback_event_id"),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_event.feedback_event_id"]),
        sa.CheckConstraint(
            f"failure_stage IN ({FAILURE_STAGES})",
            name="ck_missing_paper_resolution_failure_stage",
        ),
    )

    op.create_table(
        "user_profile",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=True),
        sa.Column("department_other", sa.Text(), nullable=True),
        sa.Column("team_type", sa.Text(), nullable=True),
        sa.Column("primary_job", sa.Text(), nullable=True),
        sa.Column("secondary_job", sa.Text(), nullable=True),
        sa.Column("panel_opt_in", sa.Boolean(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("skipped_once_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"]),
        sa.CheckConstraint(f"team_type IN ({TEAM_TYPES})", name="ck_user_profile_team_type"),
        sa.CheckConstraint(f"primary_job IN ({JOBS})", name="ck_user_profile_primary_job"),
        sa.CheckConstraint(f"secondary_job IN ({JOBS})", name="ck_user_profile_secondary_job"),
        sa.CheckConstraint(f"source IN ({SOURCES})", name="ck_user_profile_source"),
        sa.CheckConstraint(
            "completed_at IS NULL OR "
            "(department IS NOT NULL AND team_type IS NOT NULL AND primary_job IS NOT NULL)",
            name="ck_user_profile_completed_has_answers",
        ),
    )


def downgrade() -> None:
    """Drop the three feedback tables and the trace id column."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_table("user_profile")
    op.drop_table("missing_paper_resolution")
    op.drop_table("feedback_event")
    op.drop_column("runs", "trace_id")
