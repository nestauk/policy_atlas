"""task 045 options-scoping longlist records — options, the profile, child walks

The slice's one revision (S4; contract § Constraints). Additive apart from one
relaxed column and the recreated view: no existing row changes value.

Upgrade
    ``option``                      the task-scoped option entity (ruling 44),
                                    with ``uq_option_id_task`` as the
                                    composite-FK target for the three below.
    ``option_membership``           one row per unit assigned to an option.
    ``option_relation``             ``part_of`` (``variant_of`` reserved).
    ``longlist_result``             the run-keyed roll-up (the characterise
                                    pattern); a longlist exists when a row does.
    ``intervention_profile_record`` the third extraction profile's table.
    ``task_link.option_id``         nullable, guarded to an option of the
                                    link's TARGET task.
    ``capability_run.parent_capability_run_id``
                                    nullable composite self-FK (a child walk's
                                    parent), with ``ix_capr_parent``.
    ``extraction_result.selection_run_id``
                                    relaxed to nullable (the selection-free
                                    path, D24); ``fk_exr_selection`` stays —
                                    MATCH SIMPLE passes a NULL.
    ``finding_reference_union``     dropped and recreated with a third branch
                                    over ``intervention_profile_record``. The
                                    definition is ``core/schema.py``'s
                                    ``FINDING_REFERENCE_UNION_SQL`` (one copy).

    ``evidence_scope.ck_scope_purpose`` already admits ``longlist`` and
    ``targeted`` (044 decision C4, revision ``b5e1d7a4c026``): not touched.

Downgrade — the refusal (the 044 A5 pattern, widened)
    A longlist or targeted walk is options-scoping data this revision's
    tables and columns hold the rest of; dropping them under it would leave a
    walk whose option rows, profile records and parent link are gone. So the
    downgrade **refuses** while any ``capability_run`` row's intent record has
    purpose ``longlist`` or ``targeted``, and names the operator script
    (``scripts/ops_remove_scoping_tasks.py --apply``). It also refuses while
    an ``extraction_result`` row has a NULL ``selection_run_id``, because
    ``NOT NULL`` cannot be restored over it. Both checks run before any DDL.

Revision ID: c7e2a9f4b1d8
Revises: b5e1d7a4c026
Create Date: 2026-09-22 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from policy_atlas.core.schema import FINDING_REFERENCE_UNION_SQL

revision: str = "c7e2a9f4b1d8"
down_revision: Union[str, None] = "b5e1d7a4c026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

#: The two-branch view as it stood at ``b5e1d7a4c026`` — frozen here, because
#: the downgrade must restore exactly that, whatever ``schema.py`` says later.
_TWO_BRANCH_UNION_SQL = """
CREATE VIEW finding_reference_union AS
SELECT
    finding_id,
    'iof'::text AS kind,
    extraction_record_id,
    task_id,
    intervention,
    outcome,
    population,
    setting,
    study_geography,
    study_design
FROM intervention_outcome_finding
UNION ALL
SELECT
    finding_id,
    'icf'::text AS kind,
    extraction_record_id,
    task_id,
    intervention,
    outcome,
    population,
    setting,
    study_geography,
    study_design
FROM implementation_context_finding
"""

_ROLES = "('evaluated', 'described', 'recommended', 'comparator', 'mentioned')"
_ORIGINS = "('clustered', 'suggested', 'from_evidence_search', 'added_by_you')"
_STATES = "('included', 'excluded')"
_UNIT_KINDS = "('interventions', 'iof', 'icf')"
_RELATION_KINDS = "('part_of', 'variant_of')"

_WALK_REFUSAL = (
    "refusing to downgrade c7e2a9f4b1d8: {runs} capability_run row(s) belong to "
    "a longlist or targeted intent record. Dropping the option, profile and "
    "child-walk records would strand them. Remove the options-scoping tasks "
    "first with 'python scripts/ops_remove_scoping_tasks.py --apply' (it lists "
    "what it would delete without the flag), then run the downgrade again."
)
_NULL_SELECTION_REFUSAL = (
    "refusing to downgrade c7e2a9f4b1d8: {rows} extraction_result row(s) have "
    "no selection_run_id (the selection-free path), so NOT NULL cannot be "
    "restored. Remove the options-scoping tasks first with "
    "'python scripts/ops_remove_scoping_tasks.py --apply', then run the "
    "downgrade again."
)

_UUID = postgresql.UUID(as_uuid=True)
_JSONB = postgresql.JSONB()


def upgrade() -> None:
    op.create_table(
        "option",
        sa.Column("option_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("design", _JSONB, nullable=False),
        sa.Column("design_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("outcomes", _JSONB, nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="included"),
        sa.Column("exclusion", _JSONB, nullable=True),
        sa.Column(
            "no_in_scope_evidence", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("primary_lever_type", sa.Text(), nullable=True),
        sa.Column("secondary_lever_types", _JSONB, nullable=False),
        sa.Column("lever_none_fits_reason", sa.Text(), nullable=True),
        sa.Column("taxonomy_version", sa.Text(), nullable=True),
        sa.Column("ambition", sa.Text(), nullable=True),
        sa.Column("ambition_reason", sa.Text(), nullable=True),
        sa.Column("created_by_run_id", _UUID, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("option_id", name="option_pkey"),
        sa.ForeignKeyConstraint(["task_id"], ["task.task_id"], name="option_task_id_fkey"),
        sa.ForeignKeyConstraint(
            ["created_by_run_id", "task_id"],
            ["runs.run_id", "runs.task_id"],
            name="fk_option_run_task",
            match="SIMPLE",
        ),
        sa.UniqueConstraint("option_id", "task_id", name="uq_option_id_task"),
        sa.CheckConstraint(f"origin IN {_ORIGINS}", name="ck_option_origin"),
        sa.CheckConstraint(f"state IN {_STATES}", name="ck_option_state"),
        sa.CheckConstraint("design_version >= 1", name="ck_option_design_version"),
        sa.CheckConstraint("jsonb_typeof(outcomes) = 'array'", name="ck_option_outcomes_array"),
        sa.CheckConstraint(
            "jsonb_typeof(secondary_lever_types) = 'array'",
            name="ck_option_secondary_levers_array",
        ),
    )
    op.create_index("ix_option_task", "option", ["task_id"])

    op.create_table(
        "option_membership",
        sa.Column("membership_id", _UUID, nullable=False),
        sa.Column("option_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("unit_kind", sa.Text(), nullable=False),
        sa.Column("unit_id", _UUID, nullable=False),
        sa.Column("unit_task_id", _UUID, nullable=False),
        sa.Column("task_source_snapshot_id", _UUID, nullable=True),
        sa.Column("assignment_reason", sa.Text(), nullable=True),
        sa.Column(
            "design_feature_not_stated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("assigned_by_run_id", _UUID, nullable=False),
        sa.PrimaryKeyConstraint("membership_id", name="option_membership_pkey"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.task_id"], name="option_membership_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["unit_task_id"], ["task.task_id"], name="option_membership_unit_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["option_id", "task_id"],
            ["option.option_id", "option.task_id"],
            name="fk_om_option_task",
        ),
        sa.ForeignKeyConstraint(
            ["task_source_snapshot_id", "task_id"],
            ["task_source_snapshot.task_source_snapshot_id", "task_source_snapshot.task_id"],
            name="fk_om_tss_task",
            match="SIMPLE",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_run_id", "task_id"],
            ["runs.run_id", "runs.task_id"],
            name="fk_om_run_task",
        ),
        sa.UniqueConstraint("option_id", "unit_kind", "unit_id", name="uq_om_option_unit"),
        sa.CheckConstraint(f"unit_kind IN {_UNIT_KINDS}", name="ck_om_unit_kind"),
    )
    op.create_index("ix_om_task", "option_membership", ["task_id"])

    op.create_table(
        "option_relation",
        sa.Column("relation_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("from_option_id", _UUID, nullable=False),
        sa.Column("to_option_id", _UUID, nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("relation_id", name="option_relation_pkey"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.task_id"], name="option_relation_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["from_option_id", "task_id"],
            ["option.option_id", "option.task_id"],
            name="fk_orel_from_task",
        ),
        sa.ForeignKeyConstraint(
            ["to_option_id", "task_id"],
            ["option.option_id", "option.task_id"],
            name="fk_orel_to_task",
        ),
        sa.UniqueConstraint(
            "from_option_id", "to_option_id", "kind", name="uq_orel_pair_kind"
        ),
        sa.CheckConstraint("from_option_id <> to_option_id", name="ck_orel_distinct"),
        sa.CheckConstraint(f"kind IN {_RELATION_KINDS}", name="ck_orel_kind"),
    )

    op.create_table(
        "longlist_result",
        sa.Column("longlist_result_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("evidence_scope_id", _UUID, nullable=False),
        sa.Column("run_id", _UUID, nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("themes", _JSONB, nullable=False),
        sa.Column("coverage", _JSONB, nullable=False),
        sa.Column("judgements", _JSONB, nullable=False),
        sa.Column("guesses", _JSONB, nullable=False),
        sa.Column("counts", _JSONB, nullable=False),
        sa.Column("provenance", _JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("longlist_result_id", name="longlist_result_pkey"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.task_id"], name="longlist_result_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["evidence_scope_id", "task_id"],
            ["evidence_scope.evidence_scope_id", "evidence_scope.task_id"],
            name="fk_llr_scope_task",
        ),
        sa.ForeignKeyConstraint(
            ["run_id", "task_id"],
            ["runs.run_id", "runs.task_id"],
            name="fk_llr_run_task",
        ),
        sa.UniqueConstraint("evidence_scope_id", "run_id", name="uq_llr_scope_run"),
    )
    op.create_index("ix_llr_task", "longlist_result", ["task_id"])

    op.create_table(
        "intervention_profile_record",
        sa.Column("record_id", _UUID, nullable=False),
        sa.Column("task_id", _UUID, nullable=False),
        sa.Column("extraction_record_id", _UUID, nullable=False),
        sa.Column("intervention", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("design_features", _JSONB, nullable=False),
        sa.Column("is_bundle", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("components", _JSONB, nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("population", sa.Text(), nullable=True),
        sa.Column("setting", sa.Text(), nullable=True),
        sa.Column("study_geography", sa.Text(), nullable=True),
        sa.Column("study_design", sa.Text(), nullable=True),
        sa.Column(
            "covers_no_intervention",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("field_coverage", _JSONB, nullable=False),
        sa.Column("grounding", _JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("record_id", name="intervention_profile_record_pkey"),
        sa.ForeignKeyConstraint(
            ["task_id"], ["task.task_id"], name="intervention_profile_record_task_id_fkey"
        ),
        sa.ForeignKeyConstraint(
            ["extraction_record_id", "task_id"],
            ["source_extraction_record.extraction_record_id", "source_extraction_record.task_id"],
            name="fk_ipr_record_task",
        ),
        sa.CheckConstraint(f"role IN {_ROLES}", name="ck_ipr_role"),
        sa.CheckConstraint(
            "jsonb_typeof(design_features) = 'array'", name="ck_ipr_design_features_array"
        ),
        sa.CheckConstraint("jsonb_typeof(components) = 'array'", name="ck_ipr_components_array"),
        sa.CheckConstraint("jsonb_typeof(grounding) = 'array'", name="ck_ipr_grounding_array"),
    )
    op.create_index("ix_ipr_record", "intervention_profile_record", ["extraction_record_id"])

    op.add_column("task_link", sa.Column("option_id", _UUID, nullable=True))
    op.create_foreign_key(
        "fk_task_link_option_target",
        "task_link",
        "option",
        ["option_id", "target_task_id"],
        ["option_id", "task_id"],
        match="SIMPLE",
    )

    op.add_column(
        "capability_run", sa.Column("parent_capability_run_id", _UUID, nullable=True)
    )
    op.create_foreign_key(
        "fk_capr_parent_task",
        "capability_run",
        "capability_run",
        ["parent_capability_run_id", "task_id"],
        ["capability_run_id", "task_id"],
        match="SIMPLE",
    )
    op.create_index("ix_capr_parent", "capability_run", ["parent_capability_run_id"])

    op.alter_column("extraction_result", "selection_run_id", nullable=True)

    op.execute("DROP VIEW finding_reference_union")
    op.execute(FINDING_REFERENCE_UNION_SQL)


def downgrade() -> None:
    conn = op.get_bind()
    walks = conn.execute(
        sa.text(
            "SELECT count(*) FROM capability_run cr "
            "JOIN evidence_scope es ON es.evidence_scope_id = cr.evidence_scope_id "
            "WHERE es.purpose IN ('longlist', 'targeted')"
        )
    ).scalar_one()
    if walks:
        raise RuntimeError(_WALK_REFUSAL.format(runs=walks))
    null_selections = conn.execute(
        sa.text("SELECT count(*) FROM extraction_result WHERE selection_run_id IS NULL")
    ).scalar_one()
    if null_selections:
        raise RuntimeError(_NULL_SELECTION_REFUSAL.format(rows=null_selections))

    op.execute("DROP VIEW finding_reference_union")
    op.execute(_TWO_BRANCH_UNION_SQL)

    op.alter_column("extraction_result", "selection_run_id", nullable=False)

    op.drop_index("ix_capr_parent", table_name="capability_run")
    op.drop_constraint("fk_capr_parent_task", "capability_run", type_="foreignkey")
    op.drop_column("capability_run", "parent_capability_run_id")

    op.drop_constraint("fk_task_link_option_target", "task_link", type_="foreignkey")
    op.drop_column("task_link", "option_id")

    op.drop_index("ix_ipr_record", table_name="intervention_profile_record")
    op.drop_table("intervention_profile_record")
    op.drop_index("ix_llr_task", table_name="longlist_result")
    op.drop_table("longlist_result")
    op.drop_table("option_relation")
    op.drop_index("ix_om_task", table_name="option_membership")
    op.drop_table("option_membership")
    op.drop_index("ix_option_task", table_name="option")
    op.drop_table("option")
