"""Phase-A additive planning, summary, and theme identity columns.

Revision ID: f4a8c2d7e1b9
Revises: e9a7c3d1f6b4
Create Date: 2026-08-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f4a8c2d7e1b9"
down_revision: Union[str, None] = "e9a7c3d1f6b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable Phase-A columns without backfilling existing rows."""
    op.add_column("planning_transcript", sa.Column("part", postgresql.JSONB(), nullable=True))
    op.add_column("block", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("block", sa.Column("summary_status", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_block_summary_status",
        "block",
        "summary_status IN ('pending', 'verified', 'failed')",
    )
    op.add_column("artefact", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("artefact", sa.Column("summary_status", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_artefact_summary_status",
        "artefact",
        "summary_status IN ('pending', 'verified', 'failed')",
    )
    op.add_column("source_tag", sa.Column("theme_id", postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    """Remove exactly the nullable Phase-A columns and their checks."""
    op.drop_column("source_tag", "theme_id")
    op.drop_constraint("ck_artefact_summary_status", "artefact", type_="check")
    op.drop_column("artefact", "summary_status")
    op.drop_column("artefact", "summary")
    op.drop_constraint("ck_block_summary_status", "block", type_="check")
    op.drop_column("block", "summary_status")
    op.drop_column("block", "summary")
    op.drop_column("planning_transcript", "part")
