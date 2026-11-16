"""task 054 theory of change — presentation: titles, cited sentences, "seen in", statements

Owner's presentation round (2026-10-29), with toc_summary_v3 and toc_figures_v2.

Upgrade
    ``toc_link.title``            a short title for the step (at most 8 words).
    ``toc_link.evidence_cites``   the document ids (task source snapshots) the
                                  evidence sentence cites, so the panel can number them.
    ``toc_box.seen_in``           where the change has been seen, from its case
                                  studies; ``toc_box.seen_in_cites`` the documents it cites.
    ``toc_figure.statement``      one plain sentence explaining the figure.
    All nullable; earlier rows have none until the next check.

Downgrade
    Drops the five columns.

Revision ID: 3c2752811cce
Revises: 72c3174734ea
Create Date: 2026-10-29 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3c2752811cce"
down_revision: str | Sequence[str] | None = "72c3174734ea"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS: tuple[tuple[str, str, sa.types.TypeEngine[object]], ...] = (
    ("toc_link", "title", sa.Text()),
    ("toc_link", "evidence_cites", postgresql.JSONB()),
    ("toc_box", "seen_in", sa.Text()),
    ("toc_box", "seen_in_cites", postgresql.JSONB()),
    ("toc_figure", "statement", sa.Text()),
)


_OWN_DATA = "SELECT count(*) FROM toc_link WHERE title IS NOT NULL OR evidence_cites IS NOT NULL"
_WHAT = "link row(s) carry its titles"

REMEDY = (
    "; remove the theory-of-change tasks first with 'python scrip"
    "ts/ops_remove_toc_tasks.py --apply', then downgrade again"
)


def upgrade() -> None:
    """Add the five nullable columns."""
    for table, column, type_ in _COLUMNS:
        op.add_column(table, sa.Column(column, type_, nullable=True))


def downgrade() -> None:
    """Drop them."""
    # Refuse while this revision's own data exists (contract § Schema): the
    # downgrade would lose it. Earlier revisions in the chain have already run.
    count = op.get_bind().execute(sa.text(_OWN_DATA)).scalar_one()
    if count:
        raise RuntimeError(f"refusing to downgrade {revision}: {count} {_WHAT}" + REMEDY)
    for table, column, _type in reversed(_COLUMNS):
        op.drop_column(table, column)
