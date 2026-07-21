"""project lifecycle columns + event_log.run_id nullable

Task 025 adds project-owned lifecycle state so a project can be named,
archived, and eventually owned independently of a capability walk. Existing
projects are expanded before being backfilled from their latest approved
orchestration plan; planless projects intentionally remain recoverable as
``Untitled project`` rows. Lifecycle audit events have no run on fresh
projects, so ``event_log.run_id`` becomes nullable while its MATCH SIMPLE
composite foreign key remains unchanged. Downgrade intentionally discards
lifecycle-only data and run-less lifecycle events before restoring the old
NOT NULL contract.

Revision ID: b5f1a3d7e9c2
Revises: a3c6f9e2b7d4
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b5f1a3d7e9c2"
down_revision: Union[str, None] = "a3c6f9e2b7d4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("project", sa.Column("name", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("question", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("status", sa.Text(), nullable=True))
    op.add_column("project", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("project", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("project", sa.Column("owner_user_id", sa.Text(), nullable=True))

    # Every subquery selects the same latest approved plan. A planless project
    # gets the explicit recovery name and no settled question.
    op.execute(
        sa.text(
            """
            UPDATE project
            SET
                name = COALESCE((
                    SELECT payload->>'title'
                    FROM orchestration_plan
                    WHERE orchestration_plan.project_id = project.project_id
                      AND orchestration_plan.status = 'approved'
                    ORDER BY version DESC
                    LIMIT 1
                ), 'Untitled project'),
                question = (
                    SELECT payload->>'question'
                    FROM orchestration_plan
                    WHERE orchestration_plan.project_id = project.project_id
                      AND orchestration_plan.status = 'approved'
                    ORDER BY version DESC
                    LIMIT 1
                ),
                status = 'active',
                updated_at = created_at
            """
        )
    )

    op.alter_column("event_log", "run_id", nullable=True)
    op.alter_column("project", "name", nullable=False)
    op.alter_column("project", "status", nullable=False)
    op.alter_column("project", "updated_at", nullable=False)
    op.create_check_constraint(
        "ck_project_status",
        "project",
        "status IN ('active', 'archived')",
    )
    op.create_check_constraint(
        "ck_project_archived_at",
        "project",
        "(status = 'archived') = (archived_at IS NOT NULL)",
    )


def downgrade() -> None:
    # Lifecycle audit rows cannot satisfy the legacy event_log.run_id contract.
    op.execute(sa.text("DELETE FROM event_log WHERE run_id IS NULL"))
    op.alter_column("event_log", "run_id", nullable=False)

    op.drop_constraint("ck_project_archived_at", "project", type_="check")
    op.drop_constraint("ck_project_status", "project", type_="check")
    op.drop_column("project", "owner_user_id")
    op.drop_column("project", "archived_at")
    op.drop_column("project", "updated_at")
    op.drop_column("project", "status")
    op.drop_column("project", "question")
    op.drop_column("project", "name")
