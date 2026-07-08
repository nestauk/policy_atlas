"""synthesis_result table

Task 013 (approved gated change 1): one new run-scoped table — synthesis_result,
the synthesise roll-up (one row per (evidence_scope_id, run_id), pointing at the
minted artefact and carrying the resolved upstream references — all nullable,
substrate-conditional — synthesis provenance, per-section block summaries, counts
and flags). The artefact itself lives in the 001 substrate (artefact/block/
addressable_unit/annotation/citation); this table is the component's roll-up
sibling of characterisation/selection/extraction/grouping_result. NULL reference
run ids skip their composite FK checks (MATCH SIMPLE) so each guard binds only
when that substrate resolved. Project-scope-guarded per the repo pattern.
Table count 24 -> 25.

Revision ID: f3a9d5c1e7b4
Revises: e2f8c4a1d7b3
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3a9d5c1e7b4"
down_revision: Union[str, None] = "e2f8c4a1d7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "synthesis_result",
        sa.Column("synthesis_result_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("characterisation_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("selection_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extraction_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("grouping_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artefact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("synthesis_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("blocks", postgresql.JSONB(), nullable=False),
        sa.Column("counts", postgresql.JSONB(), nullable=False),
        sa.Column("flags", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(["artefact_id"], ["artefact.artefact_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_synr_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_synr_run_project",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "characterisation_run_id"],
            ["characterisation_result.evidence_scope_id", "characterisation_result.run_id"],
            name="fk_synr_characterisation",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "selection_run_id"],
            ["selection_result.evidence_scope_id", "selection_result.run_id"],
            name="fk_synr_selection",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "extraction_run_id"],
            ["extraction_result.evidence_scope_id", "extraction_result.run_id"],
            name="fk_synr_extraction",
        ),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "grouping_run_id"],
            ["grouping_result.evidence_scope_id", "grouping_result.run_id"],
            name="fk_synr_grouping",
        ),
        sa.UniqueConstraint("evidence_scope_id", "run_id", name="uq_synr_scope_run"),
    )


def downgrade() -> None:
    op.drop_table("synthesis_result")
