"""waitlist_entry table

Public Request-access intake for the splash page. Email is unique;
organisation is optional. No FK to app_user — ops enrolment remains the
Cognito on-ramp.

Revision ID: a8c3e1f5b9d2
Revises: e7a1b5c3d9f2
Create Date: 2026-09-03 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a8c3e1f5b9d2"
down_revision: Union[str, None] = "e7a1b5c3d9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "waitlist_entry",
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("organisation", sa.Text(), nullable=True),
        sa.Column("role_or_reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("entry_id"),
        sa.UniqueConstraint("email", name="uq_waitlist_entry_email"),
    )


def downgrade() -> None:
    op.drop_table("waitlist_entry")
