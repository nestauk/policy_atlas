"""Organisation tenancy above the entity hierarchy, and chat authorship.

Task 033 puts an ``organisation`` above the entity hierarchy and an ``app_user``
row per token ``sub``. ``project`` and ``portfolio`` each gain a nullable
``org_id`` and a per-row ``visibility`` (``org``|``private``, defaulting to
``org``), and ``conversation`` gains ``created_by`` so a colleague's chat is
distinguishable from the project owner's. Nothing is enrolled by this migration:
every existing row keeps ``org_id IS NULL``, which no organisation leg matches,
so behaviour is unchanged until an operator enrols someone (the dark launch).

``created_by`` is backfilled from the owning project's ``owner_user_id`` —
before this slice every conversation on a project was necessarily the owner's.

**The downgrade is data-destructive by design** (contract § Rollback posture:
roll forward, not back). It drops ``created_by``, so chat authorship is lost and
pre-033 code lists *every* conversation on a project to its owner — evidenced by
``test_downgrade_erases_chat_authorship_exposing_colleague_chats``. It also drops
both ``visibility`` columns, so a re-upgrade defaults every row back to ``org``.

Revision ID: a4f1c8e3b6d2
Revises: b3c7d914e0a2
Create Date: 2026-08-24 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a4f1c8e3b6d2"
down_revision: Union[str, None] = "b3c7d914e0a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _backfill_conversation_created_by() -> None:
    """Attribute every pre-033 conversation to its project's owner.

    Projects with no owner (``runtime/orchestrate.py`` CLI rows) leave
    ``created_by`` NULL — there is no author to record, and inventing one would
    hand those rows to whoever is later stamped onto them.
    """
    op.execute(
        sa.text(
            "UPDATE conversation SET created_by = project.owner_user_id "
            "FROM project "
            "WHERE conversation.project_id = project.project_id "
            "AND project.owner_user_id IS NOT NULL"
        )
    )


def upgrade() -> None:
    # `ALTER TABLE` takes ACCESS EXCLUSIVE and the API is scaled to zero while
    # this runs; an idle jumpbox session holding a conflicting lock would
    # otherwise queue the deploy behind it — and queue every reader behind us.
    # Fail fast instead, so the runbook's blocker preflight is the remedy.
    op.execute("SET lock_timeout = '5s'")

    op.create_table(
        "organisation",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("org_id"),
        sa.UniqueConstraint("name", name="uq_organisation_name"),
    )

    op.create_table(
        "app_user",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
        sa.ForeignKeyConstraint(["org_id"], ["organisation.org_id"], name="fk_app_user_org_id"),
    )

    # server_default 'org' is durable, not migration-only: every existing row
    # backfills to 'org' here, and rows inserted by paths that never name the
    # column (the runtime CLI, fixtures) keep getting it. It matches the
    # server_default in core/schema.py.
    op.add_column(
        "project",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "project",
        sa.Column("visibility", sa.Text(), nullable=False, server_default="org"),
    )
    op.create_foreign_key(
        "fk_project_org_id",
        "project",
        "organisation",
        ["org_id"],
        ["org_id"],
    )
    op.create_check_constraint(
        "ck_project_visibility", "project", "visibility IN ('org', 'private')"
    )
    op.create_index(
        "ix_project_org_visibility_status",
        "project",
        ["org_id", "visibility", "status"],
    )

    op.add_column(
        "portfolio",
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "portfolio",
        sa.Column("visibility", sa.Text(), nullable=False, server_default="org"),
    )
    op.create_foreign_key(
        "fk_portfolio_org_id",
        "portfolio",
        "organisation",
        ["org_id"],
        ["org_id"],
    )
    op.create_check_constraint(
        "ck_portfolio_visibility", "portfolio", "visibility IN ('org', 'private')"
    )
    op.create_index(
        "ix_portfolio_org_visibility",
        "portfolio",
        ["org_id", "visibility"],
    )

    op.add_column("conversation", sa.Column("created_by", sa.Text(), nullable=True))

    _backfill_conversation_created_by()


def downgrade() -> None:
    op.execute("SET lock_timeout = '5s'")

    op.drop_column("conversation", "created_by")

    op.drop_index("ix_portfolio_org_visibility", table_name="portfolio")
    op.drop_constraint("ck_portfolio_visibility", "portfolio", type_="check")
    op.drop_constraint("fk_portfolio_org_id", "portfolio", type_="foreignkey")
    op.drop_column("portfolio", "visibility")
    op.drop_column("portfolio", "org_id")

    op.drop_index("ix_project_org_visibility_status", table_name="project")
    op.drop_constraint("ck_project_visibility", "project", type_="check")
    op.drop_constraint("fk_project_org_id", "project", type_="foreignkey")
    op.drop_column("project", "visibility")
    op.drop_column("project", "org_id")

    op.drop_table("app_user")
    op.drop_table("organisation")
