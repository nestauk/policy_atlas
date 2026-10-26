"""task 054 theory of change, revision 1 — the graph tables and four widened checks

Increment 1's one revision (contract § Schema, "Revision 1"). Additive: no
existing row changes value.

Upgrade
    ``toc_box``            one element in a layer (input, output, outcome,
                           impact, failure outcome); ``uq_toc_box_id_task`` is
                           the composite-FK target for links and evidence.
    ``toc_link``           a causal step between two boxes of the same task,
                           cascading with either box; at most one critical
                           link per task (``uq_toc_link_one_critical``, a
                           partial unique index).
    ``toc_band_item``      a context or supporting-activities line.
    ``toc_pathway``        an ordered route, success or failure, kept or set
                           aside.
    ``toc_pathway_link``   the pathway's links in order; cascades with either.
    ``toc_item_evidence``  one judgement: one link, one document, two stances.
                           A deleted case-study box sets only ``case_box_id``
                           to NULL (``SET NULL (case_box_id)``, PostgreSQL 15+),
                           never ``task_id``.
    ``ck_task_capability``, ``ck_capr_capability`` gain ``theory_of_change``;
    ``ck_scope_purpose`` gains ``toc``; ``ck_conversation_kind`` gains
    ``stress_test`` (used from increment 4).

Downgrade — the refusal (the 044 A5 pattern)
    Refuses while any ``task`` or ``capability_run`` row carries
    ``theory_of_change``: narrowing the checks under them would fail, and
    dropping the tables would strand their walks. The remedy is
    ``scripts/ops_remove_toc_tasks.py --apply``. ``toc`` intent records and
    ``stress_test`` conversations exist only on theory-of-change tasks, so the
    one check covers them. Then the six tables are dropped child first and the
    four checks narrowed.

Revision ID: 9127f849697f
Revises: f1b6d3a8c2e5
Create Date: 2026-10-26 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9127f849697f"
down_revision: Union[str, None] = "f1b6d3a8c2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UUID = postgresql.UUID(as_uuid=True)
_JSONB = postgresql.JSONB()

_ORIGINS = "('drafted', 'found_in_evidence', 'imported', 'user', 'options_scoping')"
_STANCES = "('supports', 'challenges', 'not_about')"

#: (constraint, table, column, values before, values after).
_WIDENED: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "ck_task_capability",
        "task",
        "capability",
        "('evidence_search', 'options_scoping')",
        "('evidence_search', 'options_scoping', 'theory_of_change')",
    ),
    (
        "ck_capr_capability",
        "capability_run",
        "capability",
        "('evidence_search', 'options_scoping')",
        "('evidence_search', 'options_scoping', 'theory_of_change')",
    ),
    (
        "ck_scope_purpose",
        "evidence_scope",
        "purpose",
        "('baseline', 'longlist', 'variant', 'targeted')",
        "('baseline', 'longlist', 'variant', 'targeted', 'toc')",
    ),
    (
        "ck_conversation_kind",
        "conversation",
        "kind",
        "('task_agent', 'chat')",
        "('task_agent', 'chat', 'stress_test')",
    ),
)

_REFUSAL = (
    "refusing to downgrade 9127f849697f: {tasks} task row(s) and {runs} "
    "capability_run row(s) carry 'theory_of_change'. Remove the theory-of-change "
    "tasks first with 'python scripts/ops_remove_toc_tasks.py --apply' (it lists "
    "what it would delete without the flag), then run the downgrade again."
)


def _common() -> list[sa.Column]:
    """``created_at``, ``updated_at`` and ``revision`` (C10)."""
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default=sa.text("1")),
    ]


def _flags() -> list[sa.Column]:
    """The changed-by-Policy-Atlas flag columns (T1, C9)."""
    return [
        sa.Column("pa_changed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pa_change_reason", sa.Text(), nullable=True),
        sa.Column("prior_version", _JSONB, nullable=True),
        sa.Column("user_edited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    ]


def _task_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["task_id"], ["task.task_id"], name=f"{table}_task_id_fkey")


def upgrade() -> None:
    op.create_table(
        "toc_box",
        sa.Column("box_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("layer", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("dosage", sa.Text(), nullable=True),
        sa.Column("result_criteria", _JSONB, nullable=False),
        sa.Column("indicator", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=False),
        *_flags(),
        sa.Column("position", _JSONB, nullable=True),
        *_common(),
        sa.PrimaryKeyConstraint("box_id", name="toc_box_pkey"),
        _task_fk("toc_box"),
        sa.UniqueConstraint("box_id", "task_id", name="uq_toc_box_id_task"),
        sa.CheckConstraint(
            "layer IN ('input', 'output', 'outcome', 'impact', 'failure_outcome')",
            name="ck_toc_box_layer",
        ),
        sa.CheckConstraint(f"origin IN {_ORIGINS}", name="ck_toc_box_origin"),
    )
    op.create_index("ix_toc_box_task", "toc_box", ["task_id"])

    op.create_table(
        "toc_link",
        sa.Column("link_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("source_box_id", _UUID, nullable=False),
        sa.Column("target_box_id", _UUID, nullable=False),
        sa.Column("if_text", sa.Text(), nullable=False),
        sa.Column("for_text", sa.Text(), nullable=False),
        sa.Column("then_text", sa.Text(), nullable=False),
        sa.Column("because_text", sa.Text(), nullable=False),
        sa.Column("conditions", _JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sentence", sa.Text(), nullable=True),
        sa.Column("elsewhere_sentence", sa.Text(), nullable=True),
        sa.Column("here_sentence", sa.Text(), nullable=True),
        sa.Column("critical", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("counted_hash", sa.Text(), nullable=True),
        sa.Column("kept_hash", sa.Text(), nullable=True),
        sa.Column("kept_by", sa.Text(), nullable=True),
        sa.Column("origin", sa.Text(), nullable=False),
        *_flags(),
        *_common(),
        sa.PrimaryKeyConstraint("link_id", name="toc_link_pkey"),
        _task_fk("toc_link"),
        sa.UniqueConstraint("link_id", "task_id", name="uq_toc_link_id_task"),
        sa.UniqueConstraint(
            "task_id", "source_box_id", "target_box_id", name="uq_toc_link_pair"
        ),
        sa.ForeignKeyConstraint(
            ["source_box_id", "task_id"],
            ["toc_box.box_id", "toc_box.task_id"],
            name="fk_toc_link_source",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_box_id", "task_id"],
            ["toc_box.box_id", "toc_box.task_id"],
            name="fk_toc_link_target",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("source_box_id <> target_box_id", name="ck_toc_link_distinct"),
        sa.CheckConstraint("kept_by IN ('user', 'check', 'choose')", name="ck_toc_link_kept_by"),
        sa.CheckConstraint(f"origin IN {_ORIGINS}", name="ck_toc_link_origin"),
    )
    op.create_index(
        "uq_toc_link_one_critical",
        "toc_link",
        ["task_id"],
        unique=True,
        postgresql_where=sa.text("critical"),
    )

    op.create_table(
        "toc_band_item",
        sa.Column("item_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("band", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("item_id", name="toc_band_item_pkey"),
        _task_fk("toc_band_item"),
        sa.CheckConstraint("band IN ('context', 'supporting')", name="ck_toc_band"),
        sa.CheckConstraint(f"origin IN {_ORIGINS}", name="ck_toc_band_item_origin"),
    )
    op.create_index("ix_toc_band_item_task", "toc_band_item", ["task_id"])

    op.create_table(
        "toc_pathway",
        sa.Column("pathway_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        *_flags(),
        *_common(),
        sa.PrimaryKeyConstraint("pathway_id", name="toc_pathway_pkey"),
        _task_fk("toc_pathway"),
        sa.UniqueConstraint("pathway_id", "task_id", name="uq_toc_pathway_id_task"),
        sa.CheckConstraint("kind IN ('success', 'failure')", name="ck_toc_pathway_kind"),
        sa.CheckConstraint("status IN ('kept', 'set_aside')", name="ck_toc_pathway_status"),
        sa.CheckConstraint(f"origin IN {_ORIGINS}", name="ck_toc_pathway_origin"),
    )
    op.create_index("ix_toc_pathway_task", "toc_pathway", ["task_id"])

    op.create_table(
        "toc_pathway_link",
        sa.Column("pathway_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("link_id", _UUID, nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("pathway_id", "position", name="toc_pathway_link_pkey"),
        _task_fk("toc_pathway_link"),
        sa.ForeignKeyConstraint(
            ["pathway_id", "task_id"],
            ["toc_pathway.pathway_id", "toc_pathway.task_id"],
            name="fk_toc_pathway_link_pathway",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["link_id", "task_id"],
            ["toc_link.link_id", "toc_link.task_id"],
            name="fk_toc_pathway_link_link",
            ondelete="CASCADE",
        ),
    )

    op.create_table(
        "toc_item_evidence",
        sa.Column("evidence_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("link_id", _UUID, nullable=False),
        sa.Column("case_box_id", _UUID, nullable=True),
        sa.Column("task_source_snapshot_id", _UUID, nullable=False),
        sa.Column("capability_run_id", _UUID, nullable=False),
        sa.Column("stance_elsewhere", sa.Text(), nullable=False),
        sa.Column("quote_elsewhere", sa.Text(), nullable=True),
        sa.Column("stance_here", sa.Text(), nullable=False),
        sa.Column("quote_here", sa.Text(), nullable=True),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column("case_study", _JSONB, nullable=True),
        sa.Column("indicator", sa.Text(), nullable=True),
        sa.Column("robust_model", sa.Boolean(), nullable=True),
        sa.Column("item_hash", sa.Text(), nullable=False),
        *_common(),
        sa.PrimaryKeyConstraint("evidence_id", name="toc_item_evidence_pkey"),
        _task_fk("toc_item_evidence"),
        sa.ForeignKeyConstraint(
            ["link_id", "task_id"],
            ["toc_link.link_id", "toc_link.task_id"],
            name="fk_toc_evidence_link",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["case_box_id", "task_id"],
            ["toc_box.box_id", "toc_box.task_id"],
            name="fk_toc_evidence_case_box",
            ondelete="SET NULL (case_box_id)",
        ),
        sa.ForeignKeyConstraint(
            ["task_source_snapshot_id", "task_id"],
            ["task_source_snapshot.task_source_snapshot_id", "task_source_snapshot.task_id"],
            name="fk_toc_evidence_tss",
        ),
        sa.ForeignKeyConstraint(
            ["capability_run_id", "task_id"],
            ["capability_run.capability_run_id", "capability_run.task_id"],
            name="fk_toc_evidence_capr",
        ),
        sa.UniqueConstraint(
            "link_id", "task_source_snapshot_id", "item_hash", name="uq_toc_evidence_link_doc_hash"
        ),
        sa.CheckConstraint(
            f"stance_elsewhere IN {_STANCES} AND stance_here IN {_STANCES}",
            name="ck_toc_evidence_stances",
        ),
        sa.CheckConstraint(
            "(stance_elsewhere = 'not_about' OR quote_elsewhere IS NOT NULL) "
            "AND (stance_here = 'not_about' OR quote_here IS NOT NULL)",
            name="ck_toc_evidence_quotes",
        ),
    )

    for name, table, column, _before, after in _WIDENED:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"{column} IN {after}")


def downgrade() -> None:
    conn = op.get_bind()
    tasks = conn.execute(
        sa.text("SELECT count(*) FROM task WHERE capability = 'theory_of_change'")
    ).scalar_one()
    runs = conn.execute(
        sa.text("SELECT count(*) FROM capability_run WHERE capability = 'theory_of_change'")
    ).scalar_one()
    if tasks or runs:
        raise RuntimeError(_REFUSAL.format(tasks=tasks, runs=runs))

    op.drop_table("toc_item_evidence")
    op.drop_table("toc_pathway_link")
    op.drop_index("ix_toc_pathway_task", table_name="toc_pathway")
    op.drop_table("toc_pathway")
    op.drop_index("uq_toc_link_one_critical", table_name="toc_link")
    op.drop_table("toc_link")
    op.drop_index("ix_toc_box_task", table_name="toc_box")
    op.drop_table("toc_box")
    op.drop_index("ix_toc_band_item_task", table_name="toc_band_item")
    op.drop_table("toc_band_item")

    for name, table, column, before, _after in _WIDENED:
        op.drop_constraint(name, table, type_="check")
        op.create_check_constraint(name, table, f"{column} IN {before}")
