"""task 054 theory of change, iteration 3 step 4 — size of change (figures)

Contract § Iteration 3, decision C37.

Upgrade
    ``toc_figure``  one number a judged document reports about a link's cause
                    or effect: what it measures, the value as reported and
                    parsed, its range, unit, effect type, for whom, where,
                    when, sample size, pooled studies and the exact quote.
                    ``box`` says whether it is a level of the source box, of
                    the target box, or the link's effect. Written by the
                    ``toc_figures`` step after the judge; it cascades with its
                    link.
    ``toc_item_evidence.figures_checked_at``  when the figures call for that
                    judgement succeeded (with or without figures), so a later
                    walk does not ask again for the same wording.

Downgrade
    Drops the table and the column. The figures are lost; a later upgrade
    finds them again on the next check.

Revision ID: 72c3174734ea
Revises: 7fbb8bf487f2
Create Date: 2026-10-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "72c3174734ea"
down_revision: str | Sequence[str] | None = "7fbb8bf487f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_UUID = postgresql.UUID(as_uuid=True)
_EFFECT_TYPES = (
    "('absolute_change', 'relative_change', 'standardised', 'ratio', 'level')"
)


def upgrade() -> None:
    """Create ``toc_figure`` and the judgement's figures-checked stamp."""
    op.create_table(
        "toc_figure",
        sa.Column("figure_id", _UUID, primary_key=True),
        sa.Column("task_id", _UUID, sa.ForeignKey("task.task_id"), nullable=False),
        sa.Column("link_id", _UUID, nullable=False),
        sa.Column("task_source_snapshot_id", _UUID, nullable=False),
        sa.Column("item_hash", sa.Text(), nullable=False),
        sa.Column("box", sa.Text(), nullable=False),
        sa.Column("measure", sa.Text(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("ci_lower_text", sa.Text(), nullable=True),
        sa.Column("ci_lower", sa.Float(), nullable=True),
        sa.Column("ci_upper_text", sa.Text(), nullable=True),
        sa.Column("ci_upper", sa.Float(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("effect_size_type", sa.Text(), nullable=False),
        sa.Column("population", sa.Text(), nullable=True),
        sa.Column("place", sa.Text(), nullable=True),
        sa.Column("year", sa.Text(), nullable=True),
        sa.Column("n", sa.Integer(), nullable=True),
        sa.Column("k", sa.Integer(), nullable=True),
        sa.Column("quote", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["link_id", "task_id"],
            ["toc_link.link_id", "toc_link.task_id"],
            name="fk_toc_figure_link",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_source_snapshot_id", "task_id"],
            ["task_source_snapshot.task_source_snapshot_id", "task_source_snapshot.task_id"],
            name="fk_toc_figure_tss",
        ),
        sa.CheckConstraint("box IN ('source', 'target', 'link')", name="ck_toc_figure_box"),
        sa.CheckConstraint(
            f"effect_size_type IN {_EFFECT_TYPES}", name="ck_toc_figure_effect_type"
        ),
    )
    op.create_index("ix_toc_figure_task_link", "toc_figure", ["task_id", "link_id"])
    op.add_column(
        "toc_item_evidence",
        sa.Column("figures_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Drop the stamp and the table."""
    op.drop_column("toc_item_evidence", "figures_checked_at")
    op.drop_index("ix_toc_figure_task_link", table_name="toc_figure")
    op.drop_table("toc_figure")
