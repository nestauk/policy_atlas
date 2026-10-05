"""project public sharing flag

Task 037: a Task owner can share one Task with the public. ``project`` gains
``is_public`` (``BOOLEAN NOT NULL``, default ``false``) — orthogonal to
``visibility`` (``org``|``private``, task 033): a Task inside a Project,
which cannot set its own ``visibility`` at all, can still be shared
publicly. Every existing row keeps ``is_public = false``, so no row's
reachability changes until its owner deliberately flips it.

Revision ID: b2f6a9d4c1e7
Revises: a8c3e1f5b9d2
Create Date: 2026-09-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2f6a9d4c1e7"
down_revision: Union[str, None] = "a8c3e1f5b9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # `ALTER TABLE` takes ACCESS EXCLUSIVE; same ceiling and same SET LOCAL
    # scoping rationale as a4f1c8e3b6d2 (a session-scoped `SET` would leak
    # this revision's 5s ceiling onto every later revision `alembic upgrade
    # head` runs on the same connection).
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column(
        "project",
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    # Transaction-scoped, for the reason `upgrade` states.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_column("project", "is_public")
