"""task 056 — Unrated appraisals: a row with no score and a flag that says so

The slice's one revision (contract D7 and S3; plan Phase 3). Documents the
classifier typed ``Unknown / Insufficient information`` or ``Other
(Non-evidence documents)`` used to get no appraisal row at all, which made
them uncitable. From this revision they get a row with no score and
``unrated = true``, so the writer can cite them and the reader sees the label
"Unrated".

Upgrade
    ``source_appraisal_result.quality_score``
                                    NOT NULL is dropped, so an Unrated row can
                                    store no score. The 1 to 5 check
                                    ``ck_sar_quality_score`` and the index
                                    ``ix_sar_scope_score`` are untouched: a
                                    database check passes when the value is
                                    NULL, so scored rows keep the 1 to 5 rule.
    ``source_appraisal_result.unrated``
                                    new boolean, NOT NULL, server default
                                    ``false`` (kept; ``schema.py`` carries the
                                    same default), so every existing row reads
                                    as an ordinary scored row.
    ``ck_sar_unrated_consistent``   new check: an Unrated row has no score and
                                    a scored row has a score. It stops the two
                                    columns from ever disagreeing.

Downgrade
    1. Every Unrated row is **deleted**. **This step loses data**: the old
       schema has no way to store an appraisal without a score, so these rows
       cannot be kept. A later upgrade does not bring them back; the next
       appraise of those documents writes them again.
    2. The consistency check and the ``unrated`` column are dropped.
    3. ``quality_score`` is NOT NULL again.

Revision ID: 152a234e2391
Revises: b33ffb8c3a16
Create Date: 2026-11-02 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "152a234e2391"
down_revision: str | None = "b33ffb8c3a16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here, not imported: the check must keep meaning what it meant at this
# revision, whatever ``schema.py`` says later.
_UNRATED_CONSISTENT = (
    "(unrated AND quality_score IS NULL) OR (NOT unrated AND quality_score IS NOT NULL)"
)


def upgrade() -> None:
    op.alter_column("source_appraisal_result", "quality_score", nullable=True)
    op.add_column(
        "source_appraisal_result",
        sa.Column("unrated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_check_constraint(
        "ck_sar_unrated_consistent",
        "source_appraisal_result",
        _UNRATED_CONSISTENT,
    )


def downgrade() -> None:
    # Lossy: see the module docstring.
    op.execute("DELETE FROM source_appraisal_result WHERE unrated")
    op.drop_constraint("ck_sar_unrated_consistent", "source_appraisal_result", type_="check")
    op.drop_column("source_appraisal_result", "unrated")
    op.alter_column("source_appraisal_result", "quality_score", nullable=False)
