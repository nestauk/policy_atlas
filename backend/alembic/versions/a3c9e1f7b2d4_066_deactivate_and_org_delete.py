"""Record a deactivated person, and let the ops role delete an empty organisation (task 066).

``app_user.deactivated_at`` marks a person whose login an operator turned off.
They keep their organisation, tasks and projects (owner ruling, 2026-11-19), so
reactivating is a clean undo. The ops role may set the mark and delete an
organisation; the command refuses an organisation anything still points at, and
the foreign keys refuse it too.

Revision ID: a3c9e1f7b2d4
Revises: e8f6a4b3c1d0
Create Date: 2026-11-19 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c9e1f7b2d4"
down_revision: str | Sequence[str] | None = "e8f6a4b3c1d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the mark, the ops role's grant on it, and its delete on organisation."""
    op.add_column("app_user", sa.Column("deactivated_at", sa.DateTime(timezone=True)))
    op.execute("GRANT UPDATE (deactivated_at) ON app_user TO pa_ops")
    op.execute("GRANT DELETE ON organisation TO pa_ops")


def downgrade() -> None:
    """Revoke the delete and drop the mark (its column grant goes with it)."""
    op.execute("REVOKE DELETE ON organisation FROM pa_ops")
    op.drop_column("app_user", "deactivated_at")
