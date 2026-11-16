"""suggestions to complete an uploaded theory: toc_proposal.source may be 'draft'

Task 054 (owner, 2026-11-04): an uploaded diagram goes on the canvas as the
user drew it. What the draft adds to complete the theory (boxes, steps, routes
and ways it could go wrong) waits as one suggestion, from the new source
``draft``.

Upgrade
    Widens ``ck_toc_proposal_source`` to ``review``, ``chat``, ``discover`` and
    ``draft``.

Downgrade
    Refuses while any ``draft`` suggestion exists (the narrower check would
    reject it), then narrows the check back to ``review``, ``chat`` and
    ``discover``.

Revision ID: f5a1c8e93b27
Revises: e3b9d27c5a14
Create Date: 2026-11-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f5a1c8e93b27"
down_revision: str | Sequence[str] | None = "e3b9d27c5a14"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow suggestions that complete an uploaded theory."""
    op.drop_constraint("ck_toc_proposal_source", "toc_proposal", type_="check")
    op.create_check_constraint(
        "ck_toc_proposal_source",
        "toc_proposal",
        "source IN ('review', 'chat', 'discover', 'draft')",
    )


def downgrade() -> None:
    """Narrow the check back, refusing while a suggestion from the draft exists."""
    found = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM toc_proposal WHERE source = 'draft'"))
        .scalar_one()
    )
    if found:
        raise RuntimeError(
            f"refusing to downgrade f5a1c8e93b27: {found} suggestion(s) from the draft "
            "exist. Delete those toc_proposal rows (source 'draft') first."
        )
    op.drop_constraint("ck_toc_proposal_source", "toc_proposal", type_="check")
    op.create_check_constraint(
        "ck_toc_proposal_source", "toc_proposal", "source IN ('review', 'chat', 'discover')"
    )
