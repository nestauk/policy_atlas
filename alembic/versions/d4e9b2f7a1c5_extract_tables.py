"""extract / findings-layer tables

Task 011 (approved gated change 1): three new tables — source_extraction_record
(the durable per-document extraction memo: partial unique over the two success
states so a failed attempt never blocks its own retry), intervention_outcome_finding
(the framework's first findings-layer records: source-named references, verified
grounding anchors, closed effect/estimate/causality vocabularies), and
extraction_result (the run-scoped roll-up group will reference by extraction_run_id).
Project-scope-guarded via composite FKs per the repo pattern. Table count 20 -> 23.

Revision ID: d4e9b2f7a1c5
Revises: c8d4f2e7a3b1
Create Date: 2026-07-07 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d4e9b2f7a1c5"
down_revision: Union[str, None] = "c8d4f2e7a3b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_extraction_record",
        sa.Column("extraction_record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_fingerprint", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finding_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["source_snapshot.source_snapshot_id"]),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_ser_run_project",
        ),
        sa.ForeignKeyConstraint(
            ["project_source_snapshot_id", "project_id"],
            [
                "project_source_snapshot.project_source_snapshot_id",
                "project_source_snapshot.project_id",
            ],
            name="fk_ser_pss_project",
        ),
        sa.UniqueConstraint("extraction_record_id", "project_id", name="uq_ser_id_project"),
        sa.CheckConstraint(
            "status IN ('extracted', 'no_findings', 'extraction_failed')",
            name="ck_ser_status",
        ),
        sa.CheckConstraint(
            "basis IN ('full_text', 'abstract_only')",
            name="ck_ser_basis",
        ),
        sa.CheckConstraint(
            "(status = 'extraction_failed') = (error IS NOT NULL)",
            name="ck_ser_error_presence",
        ),
    )
    op.create_index(
        "uq_ser_memo",
        "source_extraction_record",
        ["project_id", "source_snapshot_id", "extraction_fingerprint"],
        unique=True,
        postgresql_where=sa.text("status IN ('extracted', 'no_findings')"),
    )

    op.create_table(
        "intervention_outcome_finding",
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intervention", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("population", sa.Text(), nullable=True),
        sa.Column("comparator", sa.Text(), nullable=True),
        sa.Column("effect_direction", sa.Text(), nullable=False),
        sa.Column("estimate_level", sa.Text(), nullable=True),
        sa.Column("study_design", sa.Text(), nullable=True),
        sa.Column("stratum_qualifiers", postgresql.JSONB(), nullable=False),
        sa.Column("statistics", postgresql.JSONB(), nullable=False),
        sa.Column("causality_by_design", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=True),
        sa.Column("is_prevalence_only", sa.Boolean(), nullable=True),
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
            name="fk_iof_record_project",
        ),
        sa.CheckConstraint(
            "effect_direction IN ('positive', 'negative', 'no_effect', 'mixed', 'unclear')",
            name="ck_iof_direction",
        ),
        sa.CheckConstraint(
            "estimate_level IS NULL OR estimate_level IN ('study', 'pooled', 'claim')",
            name="ck_iof_estimate_level",
        ),
        sa.CheckConstraint(
            "causality_by_design IS NULL OR causality_by_design IN"
            " ('attributable', 'plausibly_causal', 'associational', 'descriptive')",
            name="ck_iof_causality",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(stratum_qualifiers) = 'array'", name="ck_iof_strata_array"
        ),
        sa.CheckConstraint("jsonb_typeof(grounding) = 'array'", name="ck_iof_grounding_array"),
    )
    op.create_index("ix_iof_record", "intervention_outcome_finding", ["extraction_record_id"])

    op.create_table(
        "extraction_result",
        sa.Column("extraction_result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("selection_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("extraction_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("docs", postgresql.JSONB(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("flags", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_exr_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_exr_run_project",
        ),
        sa.UniqueConstraint("evidence_scope_id", "run_id", name="uq_exr_scope_run"),
    )


def downgrade() -> None:
    op.drop_table("extraction_result")
    op.drop_table("intervention_outcome_finding")
    op.drop_index("uq_ser_memo", table_name="source_extraction_record")
    op.drop_table("source_extraction_record")
