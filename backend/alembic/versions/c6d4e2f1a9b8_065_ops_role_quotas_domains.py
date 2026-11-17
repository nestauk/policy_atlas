"""Add account-management schema and the constrained ops database role.

``ops_action`` is the durable audit trail for every write made by the ops
service. ``organisation_domain`` maps an approved email domain to the
organisation that owns it for self-signup. The nullable quota columns let a
person or organisation override the configured default, while the waitlist
columns record the account created from a request.

The ``pa_ops`` role is NOLOGIN here because deployment, not a schema migration,
sets its LOGIN attribute and password. Its grants cover exactly the ops command
queries. The app-user trigger has one job: this role may clear either privilege
flag during de-enrolment, but may never grant ``is_admin`` or ``is_ops``.

Revision ID: c6d4e2f1a9b8
Revises: b1e7c3a9d5f2
Create Date: 2026-11-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c6d4e2f1a9b8"
down_revision: str | Sequence[str] | None = "b1e7c3a9d5f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the account-management schema and grant the constrained ops role."""
    op.add_column(
        "app_user",
        sa.Column("is_ops", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("app_user", sa.Column("invited_at", sa.DateTime(timezone=True)))
    op.add_column("app_user", sa.Column("task_quota_per_year", sa.Integer()))
    op.add_column("app_user", sa.Column("runs_per_user", sa.Integer()))
    op.create_check_constraint(
        "ck_app_user_task_quota_nonneg", "app_user", "task_quota_per_year >= 0"
    )
    op.create_check_constraint("ck_app_user_runs_nonneg", "app_user", "runs_per_user >= 0")

    op.add_column("organisation", sa.Column("task_quota_per_year", sa.Integer()))
    op.add_column("organisation", sa.Column("runs_per_user", sa.Integer()))
    op.create_check_constraint(
        "ck_organisation_task_quota_nonneg", "organisation", "task_quota_per_year >= 0"
    )
    op.create_check_constraint("ck_organisation_runs_nonneg", "organisation", "runs_per_user >= 0")

    op.create_table(
        "ops_action",
        sa.Column("action_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_user_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("target", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("action_id"),
    )
    op.create_index(
        "ix_ops_action_actor_action_at", "ops_action", ["actor_user_id", "action", "at"]
    )
    op.create_index("ix_ops_action_target", "ops_action", ["target"])
    op.create_table(
        "organisation_domain",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("domain = lower(domain)", name="ck_organisation_domain_lower"),
        sa.ForeignKeyConstraint(["org_id"], ["organisation.org_id"]),
        sa.PrimaryKeyConstraint("domain"),
    )

    op.add_column("waitlist_entry", sa.Column("account_user_id", sa.Text()))
    op.add_column("waitlist_entry", sa.Column("account_created_at", sa.DateTime(timezone=True)))

    op.execute(
        "DO $$ BEGIN CREATE ROLE pa_ops NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$;"
    )
    op.execute("GRANT USAGE ON SCHEMA public TO pa_ops")
    op.execute("GRANT SELECT, INSERT ON app_user TO pa_ops")
    op.execute(
        "GRANT UPDATE (org_id, email, display_name, is_admin, is_ops, invited_at, "
        "task_quota_per_year, runs_per_user) ON app_user TO pa_ops"
    )
    op.execute("GRANT SELECT, INSERT ON organisation TO pa_ops")
    op.execute("GRANT UPDATE (name, task_quota_per_year, runs_per_user) ON organisation TO pa_ops")
    op.execute("GRANT SELECT, INSERT ON organisation_domain TO pa_ops")
    op.execute("GRANT SELECT, INSERT ON waitlist_entry TO pa_ops")
    op.execute("GRANT UPDATE (account_user_id, account_created_at) ON waitlist_entry TO pa_ops")
    op.execute("GRANT SELECT, INSERT ON ops_action TO pa_ops")
    op.execute("GRANT SELECT ON task TO pa_ops")
    op.execute("GRANT UPDATE (org_id, visibility, is_public, updated_at) ON task TO pa_ops")
    op.execute("GRANT SELECT ON project TO pa_ops")
    op.execute("GRANT UPDATE (org_id, visibility) ON project TO pa_ops")
    op.execute("GRANT SELECT, DELETE ON project_membership TO pa_ops")
    op.execute(
        "CREATE FUNCTION app_user_refuse_privilege_grant() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ "
        "BEGIN "
        "IF current_user = 'pa_ops' AND ((NEW.is_admin AND NOT OLD.is_admin) "
        "OR (NEW.is_ops AND NOT OLD.is_ops)) THEN "
        "RAISE EXCEPTION 'the ops login cannot grant is_admin or is_ops' USING ERRCODE = '42501'; "
        "END IF; "
        "RETURN NEW; "
        "END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_app_user_refuse_privilege_grant BEFORE UPDATE ON app_user "
        "FOR EACH ROW EXECUTE FUNCTION app_user_refuse_privilege_grant()"
    )


def downgrade() -> None:
    """Remove this revision's database objects and constrained role grants."""
    op.execute("DROP TRIGGER trg_app_user_refuse_privilege_grant ON app_user")
    op.execute("DROP FUNCTION app_user_refuse_privilege_grant()")
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM pa_ops")
    op.execute("REVOKE ALL ON SCHEMA public FROM pa_ops")
    op.execute(
        "DO $$ BEGIN DROP ROLE pa_ops; "
        "EXCEPTION WHEN dependent_objects_still_exist OR undefined_object THEN NULL; END $$;"
    )

    op.drop_column("waitlist_entry", "account_created_at")
    op.drop_column("waitlist_entry", "account_user_id")
    op.drop_table("organisation_domain")
    op.drop_index("ix_ops_action_target", table_name="ops_action")
    op.drop_index("ix_ops_action_actor_action_at", table_name="ops_action")
    op.drop_table("ops_action")

    op.drop_constraint("ck_organisation_runs_nonneg", "organisation", type_="check")
    op.drop_constraint("ck_organisation_task_quota_nonneg", "organisation", type_="check")
    op.drop_column("organisation", "runs_per_user")
    op.drop_column("organisation", "task_quota_per_year")

    op.drop_constraint("ck_app_user_runs_nonneg", "app_user", type_="check")
    op.drop_constraint("ck_app_user_task_quota_nonneg", "app_user", type_="check")
    op.drop_column("app_user", "runs_per_user")
    op.drop_column("app_user", "task_quota_per_year")
    op.drop_column("app_user", "invited_at")
    op.drop_column("app_user", "is_ops")
