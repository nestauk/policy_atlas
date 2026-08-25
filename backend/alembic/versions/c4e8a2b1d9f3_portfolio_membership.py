"""Many-to-many portfolio membership (task 033, ADR 0032).

Copies existing ``project.portfolio_id`` rows into ``portfolio_membership``,
then drops the singular column. Unassigned projects stay unassigned (no
membership row).

Revision ID: c4e8a2b1d9f3
Revises: b3c7d914e0a2
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4e8a2b1d9f3"
down_revision: Union[str, None] = "b3c7d914e0a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "portfolio_membership",
        sa.Column("portfolio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolio.portfolio_id"],
            name="fk_portfolio_membership_portfolio_id",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["project.project_id"],
            name="fk_portfolio_membership_project_id",
        ),
        sa.PrimaryKeyConstraint("portfolio_id", "project_id"),
    )
    op.create_index(
        "ix_portfolio_membership_project_id",
        "portfolio_membership",
        ["project_id"],
    )
    op.execute(
        sa.text(
            """
            INSERT INTO portfolio_membership (portfolio_id, project_id, created_at)
            SELECT portfolio_id, project_id, NOW()
            FROM project
            WHERE portfolio_id IS NOT NULL
            """
        )
    )
    op.drop_constraint("fk_project_portfolio_id", "project", type_="foreignkey")
    op.drop_column("project", "portfolio_id")


def downgrade() -> None:
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
    op.execute(
        sa.text(
            """
            UPDATE project AS p
            SET portfolio_id = m.portfolio_id
            FROM (
                SELECT DISTINCT ON (project_id) project_id, portfolio_id
                FROM portfolio_membership
                ORDER BY project_id, created_at ASC, portfolio_id ASC
            ) AS m
            WHERE p.project_id = m.project_id
            """
        )
    )
    op.drop_index("ix_portfolio_membership_project_id", table_name="portfolio_membership")
    op.drop_table("portfolio_membership")
