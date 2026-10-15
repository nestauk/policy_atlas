"""task 044 options-scoping records — the task kind, links and the plan pointer

The second of the slice's two revisions (S10; the first, ``a7d3f1c8e2b5``, is
the Task Agent rename). Everything here is additive: four objects arrive, one
check constraint widens, and no existing row changes value.

Upgrade
    ``task.capability``      TEXT NOT NULL DEFAULT 'evidence_search' with
                             ``ck_task_capability``. The default backfills
                             every existing row, which is the truth — options
                             scoping did not exist before this revision.
    ``ck_capr_capability``   widened to the same two values.
    ``uq_plan_id_task``      a new composite unique on ``plan``, the target the
                             next column's foreign key needs.
    ``evidence_scope``       ``purpose`` (nullable, ``ck_scope_purpose``) and
                             ``plan_id`` (nullable, composite FK to the plan
                             version row over ``uq_plan_id_task``). Both NULL
                             everywhere until a scoping plan is approved.
    ``task_link``            the Link row: one per ordered pair of tasks, the
                             source's contribution pinned to one finished walk
                             through the existing ``uq_capr_id_task``.

Downgrade — the refusal (A5, C15)
    Dropping ``task.capability`` and narrowing ``ck_capr_capability`` would
    silently reclassify every options-scoping task as an Evidence search, and
    the narrowing would fail outright against a scoping ``capability_run``
    row. Archiving is not a remedy: an archived task keeps its row. So the
    downgrade **refuses** while any ``task`` or ``capability_run`` row carries
    ``options_scoping``, and names the operator script that removes them
    (``scripts/ops_remove_scoping_tasks.py --task-id <id> --apply``). Once none remain, the
    drops run in reverse order.

Revision ID: b5e1d7a4c026
Revises: a7d3f1c8e2b5
Create Date: 2026-09-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b5e1d7a4c026"
down_revision: Union[str, None] = "a7d3f1c8e2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The two capability values after this revision, and the one before it.
_CAPABILITIES_AFTER = "('evidence_search', 'options_scoping')"
_CAPABILITIES_BEFORE = "('evidence_search')"

#: What the downgrade refuses to lose, and how the operator clears it.
_REFUSAL = (
    "refusing to downgrade b5e1d7a4c026: {tasks} task row(s) and {runs} "
    "capability_run row(s) still carry capability 'options_scoping'. "
    "Dropping task.capability would silently reclassify them as Evidence "
    "searches, and archiving keeps the row. Remove them first with "
    "'python scripts/ops_remove_scoping_tasks.py --task-id <id> --apply' (it lists what it "
    "would delete without the flag), then run the downgrade again."
)


def upgrade() -> None:
    op.add_column(
        "task",
        sa.Column(
            "capability",
            sa.Text(),
            nullable=False,
            server_default="evidence_search",
        ),
    )
    op.create_check_constraint(
        "ck_task_capability", "task", f"capability IN {_CAPABILITIES_AFTER}"
    )

    op.drop_constraint("ck_capr_capability", "capability_run", type_="check")
    op.create_check_constraint(
        "ck_capr_capability",
        "capability_run",
        f"capability IN {_CAPABILITIES_AFTER}",
    )

    op.create_unique_constraint("uq_plan_id_task", "plan", ["plan_id", "task_id"])

    op.add_column("evidence_scope", sa.Column("purpose", sa.Text(), nullable=True))
    op.create_check_constraint(
        "ck_scope_purpose",
        "evidence_scope",
        "purpose IN ('baseline', 'longlist', 'variant', 'targeted')",
    )
    op.add_column(
        "evidence_scope",
        sa.Column("plan_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # MATCH SIMPLE: a NULL plan_id skips the check, so the guard binds only
    # once a plan version is actually named (the plan.evidence_scope_id
    # precedent, in the other direction).
    op.create_foreign_key(
        "fk_scope_plan_task",
        "evidence_scope",
        "plan",
        ["plan_id", "task_id"],
        ["plan_id", "task_id"],
        match="SIMPLE",
    )

    op.create_table(
        "task_link",
        sa.Column("link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_task_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "target_task_id", postgresql.UUID(as_uuid=True), nullable=False
        ),
        sa.Column(
            "source_capability_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("link_id", name="task_link_pkey"),
        sa.ForeignKeyConstraint(
            ["source_task_id"], ["task.task_id"], name="task_link_source_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["target_task_id"], ["task.task_id"], name="task_link_target_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["source_capability_run_id", "source_task_id"],
            ["capability_run.capability_run_id", "capability_run.task_id"],
            name="fk_task_link_source_run_task",
        ),
        sa.UniqueConstraint("source_task_id", "target_task_id", name="uq_task_link_pair"),
        sa.CheckConstraint("source_task_id <> target_task_id", name="ck_task_link_distinct"),
    )
    op.create_index("ix_task_link_target_task_id", "task_link", ["target_task_id"])


def downgrade() -> None:
    conn = op.get_bind()
    tasks = conn.execute(
        sa.text("SELECT count(*) FROM task WHERE capability = 'options_scoping'")
    ).scalar_one()
    runs = conn.execute(
        sa.text(
            "SELECT count(*) FROM capability_run WHERE capability = 'options_scoping'"
        )
    ).scalar_one()
    if tasks or runs:
        raise RuntimeError(_REFUSAL.format(tasks=tasks, runs=runs))

    op.drop_index("ix_task_link_target_task_id", table_name="task_link")
    op.drop_table("task_link")

    op.drop_constraint("fk_scope_plan_task", "evidence_scope", type_="foreignkey")
    op.drop_column("evidence_scope", "plan_id")
    op.drop_constraint("ck_scope_purpose", "evidence_scope", type_="check")
    op.drop_column("evidence_scope", "purpose")

    op.drop_constraint("uq_plan_id_task", "plan", type_="unique")

    op.drop_constraint("ck_capr_capability", "capability_run", type_="check")
    op.create_check_constraint(
        "ck_capr_capability",
        "capability_run",
        f"capability IN {_CAPABILITIES_BEFORE}",
    )

    op.drop_constraint("ck_task_capability", "task", type_="check")
    op.drop_column("task", "capability")
