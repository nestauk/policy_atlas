"""Record a person's first sign-in and a rejected access request (task 065, owner 2026-11-18).

``app_user.first_signed_in_at`` is stamped by the public ``/me`` route the first
time the person opens the app, so the ops pages can tell an invitation still
waiting from one used. ``waitlist_entry.rejected_at`` marks a request an
operator turned down: it leaves the waitlist, the sweep skips it, and no email
is sent. An operator may later approve it (which clears the mark) or delete it
for good. The ops role may set ``rejected_at`` and delete waitlist rows; the
command refuses to delete a row that is not rejected, and so does a trigger.

Revision ID: e8f6a4b3c1d0
Revises: d7e5f3a2b0c9
Create Date: 2026-11-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e8f6a4b3c1d0"
down_revision: str | Sequence[str] | None = "d7e5f3a2b0c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the two timestamps and the ops role's grant on the second."""
    op.add_column("app_user", sa.Column("first_signed_in_at", sa.DateTime(timezone=True)))
    op.add_column("waitlist_entry", sa.Column("rejected_at", sa.DateTime(timezone=True)))
    op.execute("GRANT UPDATE (rejected_at) ON waitlist_entry TO pa_ops")
    op.execute("GRANT DELETE ON waitlist_entry TO pa_ops")
    # The command checks this too; the trigger holds even if a later command forgets.
    op.execute(
        "CREATE FUNCTION waitlist_entry_refuse_unrejected_delete() RETURNS trigger "
        "LANGUAGE plpgsql AS $$ "
        "BEGIN "
        "IF current_user = 'pa_ops' AND OLD.rejected_at IS NULL THEN "
        "RAISE EXCEPTION 'the ops login can only delete a rejected request' "
        "USING ERRCODE = '42501'; "
        "END IF; "
        "RETURN OLD; "
        "END $$"
    )
    op.execute(
        "CREATE TRIGGER trg_waitlist_entry_refuse_unrejected_delete "
        "BEFORE DELETE ON waitlist_entry "
        "FOR EACH ROW EXECUTE FUNCTION waitlist_entry_refuse_unrejected_delete()"
    )


def downgrade() -> None:
    """Drop the two timestamps (the column grant goes with its column) and the delete grant."""
    op.execute("DROP TRIGGER trg_waitlist_entry_refuse_unrejected_delete ON waitlist_entry")
    op.execute("DROP FUNCTION waitlist_entry_refuse_unrejected_delete()")
    op.execute("REVOKE DELETE ON waitlist_entry FROM pa_ops")
    op.drop_column("waitlist_entry", "rejected_at")
    op.drop_column("app_user", "first_signed_in_at")
