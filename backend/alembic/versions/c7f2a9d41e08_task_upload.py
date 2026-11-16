"""uploads: files a user gives a task (first use: a theory of change, task 054)

Increment 5 of task 054 (contract C8), made general on the owner's ruling of
2026-11-03: one uploads bucket and one table for every capability, told apart
by ``purpose``. The file itself lives in the upload store (S3 in staging and
production, a local folder in development); this table records what was
uploaded, why, by whom, and where it is kept.

Upgrade
    ``task_upload``: ``upload_id``, ``task_id``, ``purpose`` (``toc_theory``
    for now), ``object_key`` (the store's key, ``tasks/<task_id>/<upload_id>``),
    ``file_name``, ``content_type`` (PNG, JPEG or PDF only), ``size_bytes`` (at
    most 10 MB), ``sha256``, ``uploaded_by``, ``uploaded_at``.

Downgrade
    Refuses while any upload row exists (the files would be orphaned), then
    drops the table.

Revision ID: c7f2a9d41e08
Revises: b4e8a1f63c25
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7f2a9d41e08"
down_revision: str | Sequence[str] | None = "b4e8a1f63c25"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_BYTES = 10 * 1024 * 1024


def upgrade() -> None:
    """Create ``task_upload``."""
    op.create_table(
        "task_upload",
        sa.Column("upload_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("task.task_id"), nullable=False
        ),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("uploaded_by", sa.Text(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('toc_theory')", name="ck_task_upload_purpose"),
        sa.CheckConstraint(
            "content_type IN ('image/png', 'image/jpeg', 'application/pdf')",
            name="ck_task_upload_type",
        ),
        sa.CheckConstraint(
            f"size_bytes > 0 AND size_bytes <= {MAX_BYTES}", name="ck_task_upload_size"
        ),
    )
    op.create_index("ix_task_upload_task", "task_upload", ["task_id"])


def downgrade() -> None:
    """Drop ``task_upload``, refusing while uploads exist."""
    count = op.get_bind().execute(sa.text("SELECT count(*) FROM task_upload")).scalar_one()
    if count:
        raise RuntimeError(
            f"task_upload holds {count} rows; remove the tasks (and their files) first"
        )
    op.drop_index("ix_task_upload_task", table_name="task_upload")
    op.drop_table("task_upload")
