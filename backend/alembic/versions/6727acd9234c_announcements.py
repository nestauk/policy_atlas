"""Announcements: the email an operator sends, its recipients, and the opt-out.

``app_user`` gains the product-update opt-out and the token in each person's
unsubscribe link. Adding the token column with a ``gen_random_uuid()`` default
rewrites the table and calls the function once per existing row, so every
person gets their own token. The ops role may record announcements and update a
recipient row's address, status and reason. It gets no update grant on the
opt-out or the token, so only the person can change them; it already reads
every ``app_user`` column through its table-wide SELECT.

Revision ID: 6727acd9234c
Revises: a3c9e1f7b2d4
Create Date: 2026-11-25 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "6727acd9234c"
down_revision: str | Sequence[str] | None = "a3c9e1f7b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the two app_user columns, the two tables and the ops role's grants."""
    op.add_column(
        "app_user", sa.Column("updates_unsubscribed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "app_user",
        sa.Column(
            "unsubscribe_token", UUID(as_uuid=True), nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
    )
    op.create_unique_constraint(
        "uq_app_user_unsubscribe_token", "app_user", ["unsubscribe_token"]
    )
    op.create_table(
        "announcement",
        sa.Column("announcement_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("subject", sa.Text, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("button_label", sa.Text),
        sa.Column("button_url", sa.Text),
        sa.Column("image_url", sa.Text),
        sa.Column("image_alt", sa.Text),
        sa.Column("audience", JSONB, nullable=False),
        sa.Column("audience_summary", sa.Text, nullable=False),
        sa.Column("sent_by", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('product_update', 'service_notice')", name="ck_announcement_kind"
        ),
        sa.CheckConstraint(
            "(button_label IS NULL) = (button_url IS NULL)", name="ck_announcement_button_pair"
        ),
        sa.CheckConstraint(
            "(image_url IS NULL) = (image_alt IS NULL)", name="ck_announcement_image_pair"
        ),
    )
    op.create_table(
        "announcement_recipient",
        sa.Column(
            "announcement_id", UUID(as_uuid=True),
            sa.ForeignKey("announcement.announcement_id"), primary_key=True,
        ),
        sa.Column("user_id", sa.Text, sa.ForeignKey("app_user.user_id"), primary_key=True),
        sa.Column("email", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'sending', 'sent', 'failed', 'left_out')",
            name="ck_announcement_recipient_status",
        ),
        sa.CheckConstraint(
            "reason IS NULL OR status IN ('failed', 'left_out')",
            name="ck_announcement_recipient_reason",
        ),
    )
    op.execute("GRANT SELECT, INSERT ON announcement TO pa_ops")
    op.execute("GRANT SELECT, INSERT ON announcement_recipient TO pa_ops")
    # Column-level, like every other ops update grant: the key never changes.
    op.execute(
        "GRANT UPDATE (email, status, reason, updated_at) ON announcement_recipient TO pa_ops"
    )


def downgrade() -> None:
    """Drop the tables (their grants go with them) and the two app_user columns."""
    op.drop_table("announcement_recipient")
    op.drop_table("announcement")
    op.drop_constraint("uq_app_user_unsubscribe_token", "app_user", type_="unique")
    op.drop_column("app_user", "unsubscribe_token")
    op.drop_column("app_user", "updates_unsubscribed_at")
