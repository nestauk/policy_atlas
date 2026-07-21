"""extract schema v2 columns

Adds the task-020 IOF v2 fields without backfill: finding-grain
``effect_basis`` / ``study_geography`` and extraction-call evidence-type
provenance on ``source_extraction_record``. Existing rows satisfy the new
CHECKs through NULL and keep their v1 data untouched.

Revision ID: 0f4e2d8c9b1a
Revises: b7f3d9a2c5e1
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f4e2d8c9b1a"
down_revision: Union[str, None] = "b7f3d9a2c5e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EFFECT_BASIS_CHECK = "effect_basis IS NULL OR effect_basis IN ('observed', 'modelled')"

# Keep the literal 'Unclassified' in sync with
# iof_prompt.UNCLASSIFIED_EVIDENCE_TYPE; migrations must remain static.
_SER_EVIDENCE_TYPE_CHECK = (
    "primary_evidence_type IS NULL OR primary_evidence_type IN ("
    "'Systematic Review and Meta-Analysis', "
    "'RCTs and Quasi-Experimental Studies', "
    "'Observational Research Studies', "
    "'Modelling & Simulation', "
    "'Policy Syntheses & Guidance Documents', "
    "'Qualitative & Contextual Evidence', "
    "'Expert Opinion and Commentary', "
    "'Other (Non-evidence documents)', "
    "'Unknown / Insufficient information', "
    "'Unclassified'"
    ")"
)


def upgrade() -> None:
    op.add_column(
        "intervention_outcome_finding",
        sa.Column("study_geography", sa.Text(), nullable=True),
    )
    op.add_column(
        "intervention_outcome_finding",
        sa.Column("effect_basis", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_extraction_record",
        sa.Column("primary_evidence_type", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_iof_effect_basis",
        "intervention_outcome_finding",
        _EFFECT_BASIS_CHECK,
    )
    op.create_check_constraint(
        "ck_ser_evidence_type",
        "source_extraction_record",
        _SER_EVIDENCE_TYPE_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_ser_evidence_type", "source_extraction_record", type_="check"
    )
    op.drop_constraint(
        "ck_iof_effect_basis", "intervention_outcome_finding", type_="check"
    )
    op.drop_column("source_extraction_record", "primary_evidence_type")
    op.drop_column("intervention_outcome_finding", "effect_basis")
    op.drop_column("intervention_outcome_finding", "study_geography")
