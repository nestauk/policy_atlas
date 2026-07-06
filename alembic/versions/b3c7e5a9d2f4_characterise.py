"""characterise tables + open_tags retirement

Task 009 (approved gated change 1): three new tables — chunk_embedding (unit-grain
JSONB vectors, no pgvector), characterisation_result (run-local grouping),
source_tag (single tag home, assertion provenance) — and the retirement of
source_classification_result.open_tags + its array CHECK (decision 10: stub-empty,
nothing reads it; source_tag is the single tag home). Table count 16 -> 19.
Composite-FK targets (uq_evidence_scope_id_project, uq_runs_run_project,
uq_pss_id_project) all pre-exist from the screening-result precedent.

Revision ID: b3c7e5a9d2f4
Revises: a1d7f3c9e6b2
Create Date: 2026-07-06 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b3c7e5a9d2f4"
down_revision: Union[str, None] = "a1d7f3c9e6b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chunk_embedding",
        sa.Column("chunk_embedding_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_profile", sa.Text(), nullable=False),
        sa.Column("unit_policy", sa.Text(), nullable=False),
        sa.Column("unit_index", sa.Integer(), nullable=False),
        sa.Column("unit_locator", postgresql.JSONB(), nullable=False),
        sa.Column("vector", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunk.chunk_id"]),
        sa.UniqueConstraint(
            "chunk_id", "embedding_profile", "unit_policy", "unit_index",
            name="uq_chunk_embedding_unit",
        ),
    )

    op.create_table(
        "characterisation_result",
        sa.Column("characterisation_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("evidence_scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("grouping_provenance", postgresql.JSONB(), nullable=False),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
        sa.Column("themes", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "project_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.project_id"],
            name="fk_char_scope_project",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_char_run_project",
        ),
        sa.UniqueConstraint("evidence_scope_id", "run_id", name="uq_char_scope_run"),
    )

    op.create_table(
        "source_tag",
        sa.Column("source_tag_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_source_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag", sa.Text(), nullable=False),
        sa.Column("tag_type", sa.Text(), nullable=False),
        sa.Column("asserted_by", sa.Text(), nullable=False),
        sa.Column("created_by_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.project_id"]),
        sa.ForeignKeyConstraint(
            ["project_source_snapshot_id", "project_id"],
            [
                "project_source_snapshot.project_source_snapshot_id",
                "project_source_snapshot.project_id",
            ],
            name="fk_stag_pss_project",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_run_id", "project_id"],
            ["runs.run_id", "runs.project_id"],
            name="fk_stag_run_project",
        ),
        sa.UniqueConstraint(
            "project_source_snapshot_id", "tag_type", "tag", "asserted_by",
            name="uq_source_tag_assertion",
        ),
        sa.CheckConstraint("tag_type IN ('topic_theme')", name="ck_stag_tag_type"),
    )

    op.drop_constraint(
        "ck_scr_open_tags_array", "source_classification_result", type_="check"
    )
    op.drop_column("source_classification_result", "open_tags")


def downgrade() -> None:
    # Restored rows get '[]' — exactly what the retired stub always wrote.
    op.add_column(
        "source_classification_result",
        sa.Column(
            "open_tags",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "ck_scr_open_tags_array",
        "source_classification_result",
        "jsonb_typeof(open_tags) = 'array'",
    )
    op.drop_table("source_tag")
    op.drop_table("characterisation_result")
    op.drop_table("chunk_embedding")
