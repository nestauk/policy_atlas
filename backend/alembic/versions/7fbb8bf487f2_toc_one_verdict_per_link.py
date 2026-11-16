"""task 054 theory of change, iteration 3 step 3 — one evidence verdict per link (BEAM)

Contract § Iteration 3, decision C36. The two questions (*worked elsewhere*,
*holds here*) give way to one verdict per link, computed on read from each
document's *support* and *relevance*.

Upgrade
    ``toc_item_evidence``  gains ``support`` (strong, weak, mixed, refutes,
                           not_about), ``quote``, ``relevance`` (0 to 3) and
                           ``relevance_reason``. The old stance and quote
                           columns stay, now nullable, and are no longer
                           written. Old rows are backfilled here, once:
                           worked-elsewhere supports → weak, challenges →
                           refutes, not_about → not_about, keeping that quote;
                           relevance 3 when holds-here supported, else 1.
    ``toc_link``           gains ``evidence_sentence``, backfilled from the
                           two old sentences (joined, without repeating one);
                           the old sentence columns are no longer written.

Downgrade
    Rows written after the upgrade have no stances, so they are mapped back:
    strong or weak → supports, refutes → challenges, mixed or not_about →
    not_about on *worked elsewhere*; *holds here* supports only when the
    document supported at relevance 3. Then the new columns are dropped and the
    stances made required again. Not lossless: mixed and the strength of
    support are forgotten.

Revision ID: 7fbb8bf487f2
Revises: 80f4e6c430b0
Create Date: 2026-10-28 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7fbb8bf487f2"
down_revision: str | Sequence[str] | None = "80f4e6c430b0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SUPPORTS = "('strong', 'weak', 'mixed', 'refutes', 'not_about')"


def upgrade() -> None:
    """Add support, quote and relevance; backfill old rows; add the one link sentence."""
    op.add_column("toc_item_evidence", sa.Column("support", sa.Text(), nullable=True))
    op.add_column("toc_item_evidence", sa.Column("quote", sa.Text(), nullable=True))
    op.add_column("toc_item_evidence", sa.Column("relevance", sa.SmallInteger(), nullable=True))
    op.add_column("toc_item_evidence", sa.Column("relevance_reason", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE toc_item_evidence SET
            support = CASE stance_elsewhere
                WHEN 'supports' THEN 'weak' WHEN 'challenges' THEN 'refutes'
                ELSE 'not_about' END,
            quote = CASE WHEN stance_elsewhere IN ('supports', 'challenges')
                THEN quote_elsewhere END,
            relevance = CASE WHEN stance_here = 'supports' THEN 3 ELSE 1 END
        """
    )
    op.alter_column("toc_item_evidence", "support", nullable=False)
    op.alter_column("toc_item_evidence", "relevance", nullable=False)
    for column in ("stance_elsewhere", "stance_here"):
        op.alter_column("toc_item_evidence", column, nullable=True)
    op.create_check_constraint(
        "ck_toc_evidence_support", "toc_item_evidence", f"support IN {_SUPPORTS}"
    )
    op.create_check_constraint(
        "ck_toc_evidence_relevance", "toc_item_evidence", "relevance BETWEEN 0 AND 3"
    )
    op.create_check_constraint(
        "ck_toc_evidence_support_quote",
        "toc_item_evidence",
        "support = 'not_about' OR quote IS NOT NULL",
    )
    op.add_column("toc_link", sa.Column("evidence_sentence", sa.Text(), nullable=True))
    op.execute(
        """
        UPDATE toc_link SET evidence_sentence = NULLIF(
            concat_ws(' ', elsewhere_sentence, NULLIF(here_sentence, elsewhere_sentence)), ''
        )
        """
    )


def downgrade() -> None:
    """Map new rows back to the two stances and drop the new columns."""
    op.execute(
        """
        UPDATE toc_item_evidence SET
            stance_elsewhere = CASE
                WHEN support IN ('strong', 'weak') THEN 'supports'
                WHEN support = 'refutes' THEN 'challenges'
                ELSE 'not_about' END,
            quote_elsewhere = CASE WHEN support IN ('strong', 'weak', 'refutes') THEN quote END,
            stance_here = CASE
                WHEN support IN ('strong', 'weak') AND relevance = 3 THEN 'supports'
                ELSE 'not_about' END,
            quote_here = CASE WHEN support IN ('strong', 'weak') AND relevance = 3 THEN quote END
        WHERE stance_elsewhere IS NULL
        """
    )
    op.execute(
        "UPDATE toc_link SET elsewhere_sentence = evidence_sentence"
        " WHERE elsewhere_sentence IS NULL AND here_sentence IS NULL"
    )
    op.drop_column("toc_link", "evidence_sentence")
    for name in (
        "ck_toc_evidence_support_quote",
        "ck_toc_evidence_relevance",
        "ck_toc_evidence_support",
    ):
        op.drop_constraint(name, "toc_item_evidence", type_="check")
    for column in ("relevance_reason", "relevance", "quote", "support"):
        op.drop_column("toc_item_evidence", column)
    for column in ("stance_elsewhere", "stance_here"):
        op.alter_column("toc_item_evidence", column, nullable=False)
