"""ICF domain core and IOF setting rider

Adds the task-021 implementation-context finding table and the bounded IOF
``setting`` rider column. The IOF change is additive-only with no backfill:
existing findings keep their prior values and gain NULL ``setting``.

Revision ID: 2f9d7e1c4a6b
Revises: 0f4e2d8c9b1a
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "2f9d7e1c4a6b"
down_revision: Union[str, None] = "0f4e2d8c9b1a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ICF_CONTEXT_TYPE_CHECK = (
    "context_type IN ("
    "'mechanism', "
    "'barrier', "
    "'enabler', "
    "'implementation_condition', "
    "'delivery_process', "
    "'adaptation', "
    "'fidelity'"
    ")"
)
_ICF_CLAIM_LEVEL_CHECK = "claim_level IS NULL OR claim_level IN ('study', 'pooled')"
_ICF_CLAIM_BASIS_CHECK = (
    "claim_basis IS NULL OR claim_basis IN ("
    "'studied', "
    "'author_assertion', "
    "'cited_theory'"
    ")"
)
_ICF_LEVEL_CHECK = (
    "level IS NULL OR level IN ("
    "'system', "
    "'organisation', "
    "'provider', "
    "'recipient'"
    ")"
)


def upgrade() -> None:
    op.create_table(
        "implementation_context_finding",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_type", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("intervention", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("population", sa.Text(), nullable=True),
        sa.Column("setting", sa.Text(), nullable=True),
        sa.Column("study_geography", sa.Text(), nullable=True),
        sa.Column("study_design", sa.Text(), nullable=True),
        sa.Column("claim_level", sa.Text(), nullable=True),
        sa.Column("claim_basis", sa.Text(), nullable=True),
        sa.Column("level", sa.Text(), nullable=True),
        sa.Column("resource_requirements", sa.Text(), nullable=True),
        sa.Column("workforce_requirements", sa.Text(), nullable=True),
        sa.Column("field_coverage", postgresql.JSONB(), nullable=False),
        sa.Column("grounding", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["extraction_record_id", "project_id"],
            [
                "source_extraction_record.extraction_record_id",
                "source_extraction_record.project_id",
            ],
            name="fk_icf_record_project",
        ),
        sa.PrimaryKeyConstraint("finding_id"),
        sa.CheckConstraint(_ICF_CONTEXT_TYPE_CHECK, name="ck_icf_context_type"),
        sa.CheckConstraint(_ICF_CLAIM_LEVEL_CHECK, name="ck_icf_claim_level"),
        sa.CheckConstraint(_ICF_CLAIM_BASIS_CHECK, name="ck_icf_claim_basis"),
        sa.CheckConstraint(_ICF_LEVEL_CHECK, name="ck_icf_level"),
        sa.CheckConstraint("jsonb_typeof(grounding) = 'array'", name="ck_icf_grounding_array"),
    )
    op.create_index(
        "ix_icf_record",
        "implementation_context_finding",
        ["extraction_record_id"],
    )
    op.add_column(
        "intervention_outcome_finding",
        sa.Column("setting", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("intervention_outcome_finding", "setting")
    op.drop_index("ix_icf_record", table_name="implementation_context_finding")
    op.drop_table("implementation_context_finding")
