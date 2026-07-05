"""full-text columns on project_source_snapshot

Task 008 (approved gated change 1): link-level full-text attachment (ADR 0003).
Three columns + FK + three named CHECKs; no new table, count stays 16.
server_default='not_attempted' is durable — existing insert paths never set
full_text_status.

Revision ID: a1d7f3c9e6b2
Revises: f9c6e3b8d4a2
Create Date: 2026-07-05 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1d7f3c9e6b2"
down_revision: Union[str, None] = "f9c6e3b8d4a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "project_source_snapshot",
        sa.Column("full_text_snapshot_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "project_source_snapshot",
        sa.Column(
            "full_text_status", sa.Text(), nullable=False, server_default="not_attempted"
        ),
    )
    op.add_column(
        "project_source_snapshot",
        sa.Column("full_text_error", sa.Text(), nullable=True),
    )
    op.create_foreign_key(
        "fk_pss_full_text_snapshot",
        "project_source_snapshot",
        "source_snapshot",
        ["full_text_snapshot_id"],
        ["source_snapshot_id"],
    )
    op.create_check_constraint(
        "ck_pss_full_text_status",
        "project_source_snapshot",
        "full_text_status IN ('not_attempted', 'ingested', 'fetch_failed', 'parse_failed')",
    )
    op.create_check_constraint(
        "ck_pss_full_text_consistent",
        "project_source_snapshot",
        "(full_text_status = 'ingested') = (full_text_snapshot_id IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_pss_full_text_error_presence",
        "project_source_snapshot",
        "(full_text_status IN ('fetch_failed', 'parse_failed')) = (full_text_error IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_pss_full_text_error_presence", "project_source_snapshot", type_="check"
    )
    op.drop_constraint("ck_pss_full_text_consistent", "project_source_snapshot", type_="check")
    op.drop_constraint("ck_pss_full_text_status", "project_source_snapshot", type_="check")
    op.drop_constraint(
        "fk_pss_full_text_snapshot", "project_source_snapshot", type_="foreignkey"
    )
    op.drop_column("project_source_snapshot", "full_text_error")
    op.drop_column("project_source_snapshot", "full_text_status")
    op.drop_column("project_source_snapshot", "full_text_snapshot_id")
