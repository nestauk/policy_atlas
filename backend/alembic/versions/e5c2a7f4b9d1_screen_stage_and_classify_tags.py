"""screen_stage + retry semantics + classify tag type

Task 014 (approved gated change 3): one migration, four changes, no new
tables (count stays 25):

1. ``screen_stage`` column on source_screening_result (1 = envelope,
   2 = full_text; NOT NULL, server_default 1) + ``ck_ssr_stage``.
2. ``ck_ssr_basis`` widens to admit ``'full_text'`` (stage-2 rows).
3. ``uq_ssr_scope_source`` (unique constraint over scope+source) is replaced
   by ``uq_ssr_scope_source_stage`` — a partial unique index over
   (scope, source, stage) excluding ``status='failed'`` rows, so failed
   attempts never block retry (the 011 extraction-memo precedent) and each
   stage owns at most one non-failed row.
4. ``ck_stag_tag_type`` widens to admit ``'methodological_structural'``
   (classify's open tag proposals, decision 6).

Revision ID: e5c2a7f4b9d1
Revises: f3a9d5c1e7b4
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5c2a7f4b9d1"
down_revision: Union[str, None] = "f3a9d5c1e7b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_screening_result",
        sa.Column("screen_stage", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_ssr_stage",
        "source_screening_result",
        "screen_stage IN (1, 2)",
    )

    op.drop_constraint("ck_ssr_basis", "source_screening_result", type_="check")
    op.create_check_constraint(
        "ck_ssr_basis",
        "source_screening_result",
        "screen_basis IS NULL"
        " OR screen_basis IN ('title_abstract', 'title_only', 'full_text')",
    )

    op.drop_constraint("uq_ssr_scope_source", "source_screening_result", type_="unique")
    op.create_index(
        "uq_ssr_scope_source_stage",
        "source_screening_result",
        ["evidence_scope_id", "project_source_snapshot_id", "screen_stage"],
        unique=True,
        postgresql_where=sa.text("status != 'failed'"),
    )

    op.drop_constraint("ck_stag_tag_type", "source_tag", type_="check")
    op.create_check_constraint(
        "ck_stag_tag_type",
        "source_tag",
        "tag_type IN ('topic_theme', 'methodological_structural')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_stag_tag_type", "source_tag", type_="check")
    op.create_check_constraint(
        "ck_stag_tag_type",
        "source_tag",
        "tag_type IN ('topic_theme')",
    )

    op.drop_index("uq_ssr_scope_source_stage", table_name="source_screening_result")
    # Restoring the strict constraint requires no failed-retry attempt history or
    # stage-2 rows; a corpus that has exercised the 014 semantics must prune
    # duplicate (scope, source) rows before downgrading.
    op.create_unique_constraint(
        "uq_ssr_scope_source",
        "source_screening_result",
        ["evidence_scope_id", "project_source_snapshot_id"],
    )

    op.drop_constraint("ck_ssr_basis", "source_screening_result", type_="check")
    op.create_check_constraint(
        "ck_ssr_basis",
        "source_screening_result",
        "screen_basis IS NULL OR screen_basis IN ('title_abstract', 'title_only')",
    )

    op.drop_constraint("ck_ssr_stage", "source_screening_result", type_="check")
    op.drop_column("source_screening_result", "screen_stage")
