"""onboarding profile: free-text workplace and role, one or more uses

Upgrade
    Changes ``user_profile``. ``department`` becomes free text. ``role`` (free
    text) and ``jobs`` (an array of use codes) are added. ``department_other``,
    ``team_type``, ``primary_job`` and ``secondary_job`` are dropped.

    The old answers are not converted. A profile that was completed before
    this revision becomes not completed, so the user answers the new form. The
    onboarding element was not released when this revision was written.

Downgrade
    Brings back the old columns, empty. Each profile becomes not completed.

The value lists below are a frozen copy of the lists in ``core/schema.py`` at
the time of this revision. A later change to a list needs its own revision.

Revision ID: c8e2a5f71d46
Revises: a4c7e19d5b32
Create Date: 2026-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c8e2a5f71d46"
down_revision: str | Sequence[str] | None = "a4c7e19d5b32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TEAM_TYPES = "'policy', 'analysis_evidence', 'strategy_finance', 'private_office', 'other'"
JOBS = "'j1', 'j2', 'j3', 'j4', 'j5', 'j6', 'j7', 'other'"
RESET_ANSWERS = "UPDATE user_profile SET department = NULL, completed_at = NULL"


def upgrade() -> None:
    """Replace the coded workplace and the one or two uses with the new answers."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(RESET_ANSWERS)
    # DROP COLUMN also drops each CHECK that names the column.
    for column in ("department_other", "team_type", "primary_job", "secondary_job"):
        op.drop_column("user_profile", column)
    op.add_column("user_profile", sa.Column("role", sa.Text(), nullable=True))
    op.add_column(
        "user_profile", sa.Column("jobs", postgresql.ARRAY(sa.Text()), nullable=True)
    )
    op.create_check_constraint(
        "ck_user_profile_jobs", "user_profile", f"jobs <@ ARRAY[{JOBS}]::text[]"
    )
    op.create_check_constraint(
        "ck_user_profile_completed_has_answers",
        "user_profile",
        "completed_at IS NULL OR (department IS NOT NULL AND role IS NOT NULL "
        "AND jobs IS NOT NULL AND cardinality(jobs) > 0)",
    )


def downgrade() -> None:
    """Bring back the coded workplace, the team type and the one or two uses."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(RESET_ANSWERS)
    # DROP COLUMN also drops each CHECK that names the column.
    op.drop_column("user_profile", "role")
    op.drop_column("user_profile", "jobs")
    for column in ("department_other", "team_type", "primary_job", "secondary_job"):
        op.add_column("user_profile", sa.Column(column, sa.Text(), nullable=True))
    for column, values in (
        ("team_type", TEAM_TYPES),
        ("primary_job", JOBS),
        ("secondary_job", JOBS),
    ):
        op.create_check_constraint(
            f"ck_user_profile_{column}", "user_profile", f"{column} IN ({values})"
        )
    op.create_check_constraint(
        "ck_user_profile_completed_has_answers",
        "user_profile",
        "completed_at IS NULL OR "
        "(department IS NOT NULL AND team_type IS NOT NULL AND primary_job IS NOT NULL)",
    )
