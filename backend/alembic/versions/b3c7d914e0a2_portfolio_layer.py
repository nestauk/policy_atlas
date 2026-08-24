"""Portfolio layer: a named grouping above the project row.

Task 032 introduces the screen-word "Project" as a `portfolio` row sitting
*above* the existing `project` row (the screen-word "Task"). Nothing is
re-parented: plan, run and artefact keep their project as before, and the link
is one nullable column, so every existing project reads `portfolio_id IS NULL`
and behaves exactly as it did.

Revision ID: b3c7d914e0a2
Revises: d8e4a1c7f2b9
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3c7d914e0a2"
down_revision: Union[str, None] = "d8e4a1c7f2b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio",
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_user_id", sa.Text(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "project",
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_project_portfolio_id",
        "project",
        "portfolio",
        ["portfolio_id"],
        ["portfolio_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_project_portfolio_id", "project", type_="foreignkey")
    op.drop_column("project", "portfolio_id")
    op.drop_table("portfolio")
