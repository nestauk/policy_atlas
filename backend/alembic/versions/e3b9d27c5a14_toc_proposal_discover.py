"""suggestions found in the evidence: toc_proposal.source may be 'discover'

Task 054 (owner, 2026-11-04): a theory kept as the user drew it no longer takes
routes found in the evidence straight into the theory. Each check's found
routes wait as one suggestion, from the new source ``discover``.

Upgrade
    Widens ``ck_toc_proposal_source`` to ``review``, ``chat`` and ``discover``.

Downgrade
    Refuses while any ``discover`` suggestion exists (the narrower check would
    reject it), then narrows the check back to ``review`` and ``chat``.

Revision ID: e3b9d27c5a14
Revises: c7f2a9d41e08
Create Date: 2026-11-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b9d27c5a14"
down_revision: str | Sequence[str] | None = "c7f2a9d41e08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow suggestions found in the evidence."""
    op.drop_constraint("ck_toc_proposal_source", "toc_proposal", type_="check")
    op.create_check_constraint(
        "ck_toc_proposal_source", "toc_proposal", "source IN ('review', 'chat', 'discover')"
    )


def downgrade() -> None:
    """Narrow the check back, refusing while a suggestion from the evidence exists."""
    found = (
        op.get_bind()
        .execute(sa.text("SELECT count(*) FROM toc_proposal WHERE source = 'discover'"))
        .scalar_one()
    )
    if found:
        raise RuntimeError(
            f"refusing to downgrade e3b9d27c5a14: {found} suggestion(s) from the evidence "
            "exist. Delete those toc_proposal rows (source 'discover') first."
        )
    op.drop_constraint("ck_toc_proposal_source", "toc_proposal", type_="check")
    op.create_check_constraint(
        "ck_toc_proposal_source", "toc_proposal", "source IN ('review', 'chat')"
    )
