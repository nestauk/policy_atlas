"""capability_run status widening

Task 025 makes paused and interrupted capability walks durable states. The
upgrade widens only ``ck_capr_status``. Downgrade maps values absent from the
legacy vocabulary to its closest terminal state, stamping an end time only
where one was not already present, before restoring the narrow check.

Revision ID: c6e2b4f8a1d3
Revises: b5f1a3d7e9c2
Create Date: 2026-07-21 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c6e2b4f8a1d3"
down_revision: Union[str, None] = "b5f1a3d7e9c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("ck_capr_status", "capability_run", type_="check")
    op.create_check_constraint(
        "ck_capr_status",
        "capability_run",
        "status IN ('running', 'paused', 'succeeded', 'degraded', 'failed', "
        "'aborted', 'interrupted')",
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE capability_run SET status = 'aborted', "
            "ended_at = COALESCE(ended_at, now()) WHERE status = 'paused'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE capability_run SET status = 'failed', "
            "ended_at = COALESCE(ended_at, now()) WHERE status = 'interrupted'"
        )
    )
    op.drop_constraint("ck_capr_status", "capability_run", type_="check")
    op.create_check_constraint(
        "ck_capr_status",
        "capability_run",
        "status IN ('running', 'succeeded', 'degraded', 'failed', 'aborted')",
    )
