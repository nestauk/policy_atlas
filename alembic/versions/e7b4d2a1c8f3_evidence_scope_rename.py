"""evidence_scope rename

Renames screening_scope -> evidence_scope (task 007, approved gated change 1).
Pure rename — no shape change, no data change. Postgres renames nothing
automatically beyond the table itself: the four screening_scope_id columns,
the composite unique constraint and the primary-key constraint are renamed
explicitly; FK constraints referencing the renamed objects keep working by OID.

Revision ID: e7b4d2a1c8f3
Revises: d6a1c4e9b2f7
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b4d2a1c8f3"
down_revision: Union[str, None] = "d6a1c4e9b2f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMN_TABLES = (
    "evidence_scope",
    "source_screening_result",
    "source_classification_result",
    "source_appraisal_result",
)


def upgrade() -> None:
    op.rename_table("screening_scope", "evidence_scope")
    op.execute(
        "ALTER TABLE evidence_scope RENAME CONSTRAINT "
        "screening_scope_pkey TO evidence_scope_pkey"
    )
    op.execute(
        "ALTER TABLE evidence_scope RENAME CONSTRAINT "
        "uq_screening_scope_id_project TO uq_evidence_scope_id_project"
    )
    for table in _COLUMN_TABLES:
        op.alter_column(table, "screening_scope_id", new_column_name="evidence_scope_id")


def downgrade() -> None:
    for table in _COLUMN_TABLES:
        op.alter_column(table, "evidence_scope_id", new_column_name="screening_scope_id")
    op.execute(
        "ALTER TABLE evidence_scope RENAME CONSTRAINT "
        "uq_evidence_scope_id_project TO uq_screening_scope_id_project"
    )
    op.execute(
        "ALTER TABLE evidence_scope RENAME CONSTRAINT "
        "evidence_scope_pkey TO screening_scope_pkey"
    )
    op.rename_table("evidence_scope", "screening_scope")
