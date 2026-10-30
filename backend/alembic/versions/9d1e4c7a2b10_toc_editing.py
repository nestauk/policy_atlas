"""task 054 theory of change — editing: who edited, evidence overrides, pending evidence

Increment 2 (contract C41 to C44, approved 2026-10-30). One migration for
slices A to C; every column is nullable or has a default, so existing rows
read as before.

Upgrade
    ``toc_box`` / ``toc_link``      ``edited_by`` (the user id of the last edit)
                                    and ``edited_at``.
    ``toc_item_evidence``           ``excluded_by`` / ``excluded_at`` (the user
                                    removed the document from the link);
                                    ``support_override`` / ``relevance_override``
                                    with ``override_by`` / ``override_at`` (the
                                    user's scores, used instead of the judge's);
                                    ``added_by`` (a study the user added);
                                    ``status`` (``counted`` · ``pending`` ·
                                    ``rejected``; default ``counted``) with
                                    ``decided_by`` / ``decided_at``.

Downgrade
    Drops the columns and the status check.

Revision ID: 9d1e4c7a2b10
Revises: 3c2752811cce
Create Date: 2026-10-30 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d1e4c7a2b10"
down_revision: str | Sequence[str] | None = "3c2752811cce"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STAMP = sa.DateTime(timezone=True)
_COLUMNS: tuple[tuple[str, str, sa.types.TypeEngine[object]], ...] = (
    ("toc_box", "edited_by", sa.Text()),
    ("toc_box", "edited_at", _STAMP),
    ("toc_link", "edited_by", sa.Text()),
    ("toc_link", "edited_at", _STAMP),
    ("toc_item_evidence", "excluded_by", sa.Text()),
    ("toc_item_evidence", "excluded_at", _STAMP),
    ("toc_item_evidence", "support_override", sa.Text()),
    ("toc_item_evidence", "relevance_override", sa.Integer()),
    ("toc_item_evidence", "override_by", sa.Text()),
    ("toc_item_evidence", "override_at", _STAMP),
    ("toc_item_evidence", "added_by", sa.Text()),
    ("toc_item_evidence", "decided_by", sa.Text()),
    ("toc_item_evidence", "decided_at", _STAMP),
)


def upgrade() -> None:
    """Add the nullable columns and the evidence status."""
    for table, column, type_ in _COLUMNS:
        op.add_column(table, sa.Column(column, type_, nullable=True))
    op.add_column(
        "toc_item_evidence",
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'counted'")),
    )
    op.create_check_constraint(
        "ck_toc_item_evidence_status",
        "toc_item_evidence",
        "status IN ('counted', 'pending', 'rejected')",
    )
    op.create_check_constraint(
        "ck_toc_item_evidence_support_override",
        "toc_item_evidence",
        "support_override IS NULL OR support_override IN"
        " ('strong', 'weak', 'mixed', 'refutes', 'not_about')",
    )
    op.create_check_constraint(
        "ck_toc_item_evidence_relevance_override",
        "toc_item_evidence",
        "relevance_override IS NULL OR relevance_override BETWEEN 0 AND 3",
    )


def downgrade() -> None:
    """Drop them."""
    for name in (
        "ck_toc_item_evidence_relevance_override",
        "ck_toc_item_evidence_support_override",
        "ck_toc_item_evidence_status",
    ):
        op.drop_constraint(name, "toc_item_evidence", type_="check")
    op.drop_column("toc_item_evidence", "status")
    for table, column, _type in reversed(_COLUMNS):
        op.drop_column(table, column)
