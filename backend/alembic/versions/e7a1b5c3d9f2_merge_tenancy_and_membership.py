"""Merge point: 033 tenancy chain and the portfolio-membership chain.

Both chains hang off ``b3c7d914e0a2`` (the portfolio layer): the tenancy pair
(``a4f1c8e3b6d2`` → ``d8e2a6c4f7b1``, task 033) landed on the task branch while
``c4e8a2b1d9f3`` (many-to-many membership, ADR 0032) merged to dev. They touch
disjoint columns — tenancy adds ``org_id``/``visibility``, membership moves
``project.portfolio_id`` into ``portfolio_membership`` — so either order is
safe and this revision only joins the heads. A database already at either head
(the staging canary sat at ``d8e2a6c4f7b1``) reaches the other chain's work by
upgrading to head as usual.

Revision ID: e7a1b5c3d9f2
Revises: d8e2a6c4f7b1, c4e8a2b1d9f3
"""

from __future__ import annotations

revision = "e7a1b5c3d9f2"
down_revision = ("d8e2a6c4f7b1", "c4e8a2b1d9f3")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
