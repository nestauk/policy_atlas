"""Add invite links, and record on a request the code it came with and the link it used.

An invite link carries a 12-character code, the organisation a redeemed request
joins, the email domains it accepts, a use limit and an end date. A link is
never deleted, so the ops role gets no delete right on it. ``invite_link_cohort``
lists the cohorts a redeemed person joins; deleting a cohort removes its rows.
``waitlist_entry.invite_code`` is the code a request arrived with and
``waitlist_entry.invite_link_id`` the link that redeemed it.

Revision ID: 9c5cdd050525
Revises: a3c9e1f7b2d4
Create Date: 2026-11-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9c5cdd050525"
down_revision: str | Sequence[str] | None = "a3c9e1f7b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the two link tables, the two request columns, and the ops role's grants."""
    op.create_table(
        "invite_link",
        sa.Column("invite_link_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "org_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organisation.org_id"), nullable=False,
        ),
        sa.Column("allowed_domains", postgresql.ARRAY(sa.Text()), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.UniqueConstraint("code", name="uq_invite_link_code"),
        # The alphabet of policy_atlas.core.invite_code, frozen here as of this revision.
        sa.CheckConstraint(
            "code ~ '^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{12}$'", name="ck_invite_link_code_format"
        ),
        sa.CheckConstraint(
            "char_length(label) BETWEEN 1 AND 200", name="ck_invite_link_label_length"
        ),
        sa.CheckConstraint(
            "cardinality(allowed_domains) BETWEEN 1 AND 10", name="ck_invite_link_domain_count"
        ),
        sa.CheckConstraint("max_uses > 0", name="ck_invite_link_max_uses_positive"),
    )
    op.create_table(
        "invite_link_cohort",
        sa.Column(
            "invite_link_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invite_link.invite_link_id"), primary_key=True,
        ),
        sa.Column(
            "cohort_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cohort.cohort_id", ondelete="CASCADE"), primary_key=True,
        ),
    )
    op.add_column("waitlist_entry", sa.Column("invite_code", sa.Text(), nullable=True))
    op.add_column(
        "waitlist_entry",
        sa.Column(
            "invite_link_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invite_link.invite_link_id", name="fk_waitlist_entry_invite_link_id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_waitlist_entry_invite_code", "waitlist_entry", ["invite_code"],
        postgresql_where=sa.text("invite_code IS NOT NULL"),
    )
    op.create_index(
        "ix_waitlist_entry_invite_link_id", "waitlist_entry", ["invite_link_id"],
        postgresql_where=sa.text("invite_link_id IS NOT NULL"),
    )
    op.execute("GRANT SELECT, INSERT ON invite_link TO pa_ops")
    op.execute("GRANT UPDATE (label, max_uses, expires_at, revoked_at) ON invite_link TO pa_ops")
    op.execute("GRANT SELECT, INSERT ON invite_link_cohort TO pa_ops")
    op.execute("GRANT UPDATE (invite_link_id) ON waitlist_entry TO pa_ops")


def downgrade() -> None:
    """Revoke the grants, then drop the indexes, the columns and the tables."""
    op.execute("REVOKE UPDATE (invite_link_id) ON waitlist_entry FROM pa_ops")
    op.execute("REVOKE ALL ON invite_link_cohort FROM pa_ops")
    op.execute("REVOKE ALL ON invite_link FROM pa_ops")
    op.drop_index("ix_waitlist_entry_invite_link_id", table_name="waitlist_entry")
    op.drop_index("ix_waitlist_entry_invite_code", table_name="waitlist_entry")
    op.drop_column("waitlist_entry", "invite_link_id")
    op.drop_column("waitlist_entry", "invite_code")
    op.drop_table("invite_link_cohort")
    op.drop_table("invite_link")
