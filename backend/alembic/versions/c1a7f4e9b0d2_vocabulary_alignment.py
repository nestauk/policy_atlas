"""task 038 vocabulary alignment — one product word per concept, in the catalog

Pure rename plus five losslessly reversible stored values (task 038, approved
gated change 1). Every object name comes from the catalog-derived manifest
``docs/tasks/038-vocabulary-alignment/schema-manifest.md``; no shape changes,
no rows lost, every row reads back identically under its new name.

Two steps, in this order — the order IS the collision guard: ``project`` must
become ``task`` before ``portfolio`` becomes ``project``, or ``project_pkey``
would collide (index names are schema-global). The downgrade reverses the two
steps in the opposite order for the same reason.

Step 1 · ``project`` → ``task``, ``project_source_snapshot`` →
``task_source_snapshot`` (``pss`` → ``tss`` in constraint infixes),
``orchestration_plan`` → ``plan`` (``oplan`` → ``plan``).
Step 2 · ``portfolio`` → ``project``, ``portfolio_membership`` →
``project_membership``, ``portfolio_id`` → ``project_id``.

Six FK rows carry names the manifest could not know: the manifest is generated
from the SQLAlchemy metadata, which auto-names an unnamed ``ForeignKey`` as
``<table>_<column>_fkey``, while the migration chain created these six with
explicit names. This revision renames what the catalog actually holds, so the
downgrade restores exactly the names the older revisions drop by name:

    screening_scope_project_id_fkey       (metadata: evidence_scope_project_id_fkey)
    fk_orchestration_plan_conversation    (metadata: orchestration_plan_conversation_id_fkey)
    fk_project_org_id                     (metadata: project_org_id_fkey)
    fk_portfolio_org_id                   (metadata: portfolio_org_id_fkey)
    fk_portfolio_membership_portfolio_id  (metadata: portfolio_membership_portfolio_id_fkey)
    fk_portfolio_membership_project_id    (metadata: portfolio_membership_project_id_fkey)

Stored values. Upgrade rewrites one: ``capability_run.capability``
``evidence_base`` → ``evidence_search`` (``ck_capr_capability`` dropped around
it). ``event_log`` is append-only, so its existing rows keep their words and the
readers accept both generations. The downgrade reverses all five values the new
image can write in the deploy window (contract A2): the capability, the four
``task.*`` lifecycle event types, payload ``decided_by``/``authored_by``
``agent`` → ``orchestrator``, and the steer-point id ``evidence_search_coverage``
→ ``evidence_base_coverage`` in both plan payloads and pause records.

The view ``finding_reference_union`` is dropped before the renames and recreated
after them over the new column name; its definition lives in ``core/schema.py``.

Revision ID: c1a7f4e9b0d2
Revises: b2f6a9d4c1e7
Create Date: 2026-09-04 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op

revision: str = "c1a7f4e9b0d2"
down_revision: Union[str, None] = "b2f6a9d4c1e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- The rename manifest, verbatim from the live pre-038 catalog -----------

_STEP1_TABLES: tuple[tuple[str, str], ...] = (
    ("orchestration_plan", "plan"),
    ("project", "task"),
    ("project_source_snapshot", "task_source_snapshot"),
)

_STEP1_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("artefact", "project_id", "task_id"),
    ("capability_run", "project_id", "task_id"),
    ("characterisation_result", "project_id", "task_id"),
    ("conversation", "project_id", "task_id"),
    ("event_log", "project_id", "task_id"),
    ("evidence_scope", "project_id", "task_id"),
    ("extraction_result", "project_id", "task_id"),
    ("grouping_result", "project_id", "task_id"),
    ("implementation_context_finding", "project_id", "task_id"),
    ("intervention_outcome_finding", "project_id", "task_id"),
    ("plan", "project_id", "task_id"),
    ("planning_transcript", "project_id", "task_id"),
    ("portfolio_membership", "project_id", "task_id"),
    ("task_source_snapshot", "project_id", "task_id"),
    ("task_source_snapshot", "project_source_snapshot_id", "task_source_snapshot_id"),
    ("task", "project_id", "task_id"),
    ("runs", "project_id", "task_id"),
    ("search_coverage_record", "project_id", "task_id"),
    ("selection_result", "project_id", "task_id"),
    ("source_appraisal_result", "project_id", "task_id"),
    ("source_appraisal_result", "project_source_snapshot_id", "task_source_snapshot_id"),
    ("source_classification_result", "project_id", "task_id"),
    ("source_classification_result", "project_source_snapshot_id", "task_source_snapshot_id"),
    ("source_extraction_record", "project_id", "task_id"),
    ("source_extraction_record", "project_source_snapshot_id", "task_source_snapshot_id"),
    ("source_screening_result", "project_id", "task_id"),
    ("source_screening_result", "project_source_snapshot_id", "task_source_snapshot_id"),
    ("source_tag", "project_id", "task_id"),
    ("source_tag", "project_source_snapshot_id", "task_source_snapshot_id"),
    ("synthesis_result", "project_id", "task_id"),
)

_STEP1_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("plan", "ck_oplan_payload_object", "ck_plan_payload_object"),
    ("plan", "ck_oplan_status", "ck_plan_status"),
    ("task_source_snapshot", "ck_pss_full_text_consistent", "ck_tss_full_text_consistent"),
    ("task_source_snapshot", "ck_pss_full_text_error_presence", "ck_tss_full_text_error_presence"),
    ("task_source_snapshot", "ck_pss_full_text_status", "ck_tss_full_text_status"),
    ("task", "ck_project_archived_at", "ck_task_archived_at"),
    ("task", "ck_project_status", "ck_task_status"),
    ("task", "ck_project_visibility", "ck_task_visibility"),
    ("artefact", "artefact_project_id_fkey", "artefact_task_id_fkey"),
    ("artefact", "fk_artefact_capability_run_project", "fk_artefact_capability_run_task"),
    ("capability_run", "capability_run_project_id_fkey", "capability_run_task_id_fkey"),
    ("capability_run", "fk_capr_scope_project", "fk_capr_scope_task"),
    (
        "characterisation_result",
        "characterisation_result_project_id_fkey",
        "characterisation_result_task_id_fkey",
    ),
    ("characterisation_result", "fk_char_run_project", "fk_char_run_task"),
    ("characterisation_result", "fk_char_scope_project", "fk_char_scope_task"),
    ("conversation", "conversation_project_id_fkey", "conversation_task_id_fkey"),
    (
        "conversation",
        "fk_conversation_entry_artefact_project",
        "fk_conversation_entry_artefact_task",
    ),
    ("event_log", "event_log_project_id_fkey", "event_log_task_id_fkey"),
    ("event_log", "fk_event_log_run_project", "fk_event_log_run_task"),
    ("evidence_scope", "screening_scope_project_id_fkey", "screening_scope_task_id_fkey"),
    ("extraction_result", "extraction_result_project_id_fkey", "extraction_result_task_id_fkey"),
    ("extraction_result", "fk_exr_run_project", "fk_exr_run_task"),
    ("extraction_result", "fk_exr_scope_project", "fk_exr_scope_task"),
    ("grouping_result", "fk_grr_run_project", "fk_grr_run_task"),
    ("grouping_result", "fk_grr_scope_project", "fk_grr_scope_task"),
    ("grouping_result", "grouping_result_project_id_fkey", "grouping_result_task_id_fkey"),
    ("implementation_context_finding", "fk_icf_record_project", "fk_icf_record_task"),
    (
        "implementation_context_finding",
        "implementation_context_finding_project_id_fkey",
        "implementation_context_finding_task_id_fkey",
    ),
    ("intervention_outcome_finding", "fk_iof_record_project", "fk_iof_record_task"),
    (
        "intervention_outcome_finding",
        "intervention_outcome_finding_project_id_fkey",
        "intervention_outcome_finding_task_id_fkey",
    ),
    ("plan", "fk_oplan_scope_project", "fk_plan_scope_task"),
    ("plan", "fk_orchestration_plan_conversation", "fk_plan_conversation"),
    ("plan", "orchestration_plan_project_id_fkey", "plan_task_id_fkey"),
    (
        "planning_transcript",
        "planning_transcript_project_id_fkey",
        "planning_transcript_task_id_fkey",
    ),
    (
        "portfolio_membership",
        "fk_portfolio_membership_project_id",
        "fk_portfolio_membership_task_id",
    ),
    ("task_source_snapshot", "fk_pss_full_text_snapshot", "fk_tss_full_text_snapshot"),
    (
        "task_source_snapshot",
        "project_source_snapshot_project_id_fkey",
        "task_source_snapshot_task_id_fkey",
    ),
    (
        "task_source_snapshot",
        "project_source_snapshot_run_id_fkey",
        "task_source_snapshot_run_id_fkey",
    ),
    (
        "task_source_snapshot",
        "project_source_snapshot_source_snapshot_id_fkey",
        "task_source_snapshot_source_snapshot_id_fkey",
    ),
    ("task", "fk_project_org_id", "fk_task_org_id"),
    ("runs", "fk_runs_capability_run_project", "fk_runs_capability_run_task"),
    ("runs", "runs_project_id_fkey", "runs_task_id_fkey"),
    ("search_coverage_record", "fk_scov_run_project", "fk_scov_run_task"),
    ("search_coverage_record", "fk_scov_scope_project", "fk_scov_scope_task"),
    ("selection_result", "fk_selr_run_project", "fk_selr_run_task"),
    ("selection_result", "fk_selr_scope_project", "fk_selr_scope_task"),
    ("selection_result", "selection_result_project_id_fkey", "selection_result_task_id_fkey"),
    ("source_appraisal_result", "fk_sar_pss_project", "fk_sar_tss_task"),
    ("source_appraisal_result", "fk_sar_run_project", "fk_sar_run_task"),
    ("source_appraisal_result", "fk_sar_scope_project", "fk_sar_scope_task"),
    ("source_classification_result", "fk_scr_pss_project", "fk_scr_tss_task"),
    ("source_classification_result", "fk_scr_run_project", "fk_scr_run_task"),
    ("source_classification_result", "fk_scr_scope_project", "fk_scr_scope_task"),
    ("source_extraction_record", "fk_ser_pss_project", "fk_ser_tss_task"),
    ("source_extraction_record", "fk_ser_run_project", "fk_ser_run_task"),
    (
        "source_extraction_record",
        "source_extraction_record_project_id_fkey",
        "source_extraction_record_task_id_fkey",
    ),
    ("source_screening_result", "fk_ssr_pss_project", "fk_ssr_tss_task"),
    ("source_screening_result", "fk_ssr_run_project", "fk_ssr_run_task"),
    ("source_screening_result", "fk_ssr_scope_project", "fk_ssr_scope_task"),
    ("source_tag", "fk_stag_pss_project", "fk_stag_tss_task"),
    ("source_tag", "fk_stag_run_project", "fk_stag_run_task"),
    ("source_tag", "source_tag_project_id_fkey", "source_tag_task_id_fkey"),
    ("synthesis_result", "fk_synr_run_project", "fk_synr_run_task"),
    ("synthesis_result", "fk_synr_scope_project", "fk_synr_scope_task"),
    ("synthesis_result", "synthesis_result_project_id_fkey", "synthesis_result_task_id_fkey"),
    ("plan", "orchestration_plan_pkey", "plan_pkey"),
    ("task_source_snapshot", "project_source_snapshot_pkey", "task_source_snapshot_pkey"),
    ("task", "project_pkey", "task_pkey"),
    ("artefact", "uq_artefact_id_project", "uq_artefact_id_task"),
    ("capability_run", "uq_capr_id_project", "uq_capr_id_task"),
    ("event_log", "uq_event_log_project_sequence", "uq_event_log_task_sequence"),
    ("evidence_scope", "uq_evidence_scope_id_project", "uq_evidence_scope_id_task"),
    ("plan", "uq_oplan_project_version", "uq_plan_task_version"),
    ("planning_transcript", "uq_ptr_project_client_turn", "uq_ptr_task_client_turn"),
    ("planning_transcript", "uq_ptr_project_turn_index", "uq_ptr_task_turn_index"),
    ("task_source_snapshot", "uq_project_source_snapshot", "uq_task_source_snapshot"),
    ("task_source_snapshot", "uq_pss_id_project", "uq_tss_id_task"),
    ("runs", "uq_runs_run_project", "uq_runs_run_task"),
    ("source_extraction_record", "uq_ser_id_project", "uq_ser_id_task"),
)

_STEP1_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_portfolio_membership_project_id", "ix_portfolio_membership_task_id"),
    ("ix_project_org_visibility_status", "ix_task_org_visibility_status"),
)

_STEP2_TABLES: tuple[tuple[str, str], ...] = (
    ("portfolio", "project"),
    ("portfolio_membership", "project_membership"),
)

_STEP2_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("project_membership", "portfolio_id", "project_id"),
    ("project", "portfolio_id", "project_id"),
)

_STEP2_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("project", "ck_portfolio_visibility", "ck_project_visibility"),
    (
        "project_membership",
        "fk_portfolio_membership_portfolio_id",
        "fk_project_membership_project_id",
    ),
    ("project_membership", "fk_portfolio_membership_task_id", "fk_project_membership_task_id"),
    ("project", "fk_portfolio_org_id", "fk_project_org_id"),
    ("project_membership", "portfolio_membership_pkey", "project_membership_pkey"),
    ("project", "portfolio_pkey", "project_pkey"),
)

_STEP2_INDEXES: tuple[tuple[str, str], ...] = (
    ("ix_portfolio_membership_task_id", "ix_project_membership_task_id"),
    ("ix_portfolio_org_visibility", "ix_project_org_visibility"),
)

# --- The four lifecycle event kinds and the reversible stored values -------

_LIFECYCLE_EVENT_KINDS: tuple[str, ...] = (
    "renamed",
    "archived",
    "shared_publicly",
    "unshared",
)

# JSONB rewrites run over the canonical ``jsonb`` text rendering (``"key":
# "value"``, one space after the colon), so a key/value pair matches exactly
# once and the same pair appearing inside a *string* value cannot match — its
# quotes are backslash-escaped there. Reversible by construction: the reverse
# replacement is the same pair with the two values swapped.
_ACTOR_KEYS: tuple[str, ...] = ("decided_by", "authored_by")
_OLD_STEER_POINT = "evidence_base_coverage"
_NEW_STEER_POINT = "evidence_search_coverage"

# The union view, verbatim from 7a4d9c2e1f6b with the task column
# parameterised — its shape and column order are `core/schema.py`'s
# `finding_reference_union` Table.
_UNION_VIEW_SQL = """
        CREATE VIEW finding_reference_union AS
        SELECT
            finding_id,
            'iof'::text AS kind,
            extraction_record_id,
            {column},
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
            {column},
            intervention,
            outcome,
            population,
            setting,
            study_geography,
            study_design
        FROM implementation_context_finding
        """


def _rename_tables(rows: tuple[tuple[str, str], ...], *, reverse: bool) -> None:
    """Rename each table in ``rows`` (``reverse`` swaps the pair and the order)."""
    for old, new in reversed(rows) if reverse else rows:
        op.rename_table(new if reverse else old, old if reverse else new)


def _rename_columns(rows: tuple[tuple[str, str, str], ...], *, reverse: bool) -> None:
    """Rename each column in ``rows`` (``reverse`` swaps the pair and the order)."""
    for table, old, new in reversed(rows) if reverse else rows:
        op.alter_column(
            table,
            new if reverse else old,
            new_column_name=old if reverse else new,
        )


def _rename_constraints(rows: tuple[tuple[str, str, str], ...], *, reverse: bool) -> None:
    """Rename each PK/FK/UNIQUE/CHECK in ``rows`` (``reverse`` swaps pair and order)."""
    for table, old, new in reversed(rows) if reverse else rows:
        source, target = (new, old) if reverse else (old, new)
        op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{source}" TO "{target}"')


def _rename_indexes(rows: tuple[tuple[str, str], ...], *, reverse: bool) -> None:
    """Rename each standalone index in ``rows`` (``reverse`` swaps pair and order)."""
    for old, new in reversed(rows) if reverse else rows:
        source, target = (new, old) if reverse else (old, new)
        op.execute(f'ALTER INDEX "{source}" RENAME TO "{target}"')


def _apply_step(
    tables: tuple[tuple[str, str], ...],
    columns: tuple[tuple[str, str, str], ...],
    constraints: tuple[tuple[str, str, str], ...],
    indexes: tuple[tuple[str, str], ...],
    *,
    reverse: bool,
) -> None:
    """Run one rename step forwards, or exactly backwards when ``reverse``.

    Forwards the table renames come first, so every later statement addresses
    the table by its new name; reversing runs the four kinds in the opposite
    order so the table is renamed back last.

    Args:
        tables: ``(today, after)`` table renames for the step.
        columns: ``(table_after_rename, today, after)`` column renames.
        constraints: ``(table_after_rename, today, after)`` constraint renames.
        indexes: ``(today, after)`` renames for indexes that back no constraint.
        reverse: Run the step backwards (the downgrade direction).
    """
    if reverse:
        _rename_indexes(indexes, reverse=True)
        _rename_constraints(constraints, reverse=True)
        _rename_columns(columns, reverse=True)
        _rename_tables(tables, reverse=True)
        return
    _rename_tables(tables, reverse=False)
    _rename_columns(columns, reverse=False)
    _rename_constraints(constraints, reverse=False)
    _rename_indexes(indexes, reverse=False)


def _create_finding_reference_union(*, column: str) -> None:
    """Recreate the union view over ``column`` (``task_id``, or ``project_id`` back)."""
    op.execute(_UNION_VIEW_SQL.format(column=column))


def _rewrite_jsonb(table: str, old: str, new: str) -> None:
    """Swap one canonical ``"key": "value"`` pair across a table's ``payload``."""
    op.execute(
        f"UPDATE {table} SET payload = replace(payload::text, '{old}', '{new}')::jsonb "
        f"WHERE strpos(payload::text, '{old}') > 0"
    )


def upgrade() -> None:
    # `ALTER TABLE` takes ACCESS EXCLUSIVE; same ceiling and same SET LOCAL
    # scoping rationale as b2f6a9d4c1e7 (a session-scoped `SET` would leak this
    # revision's 5s ceiling onto every later revision on the same connection).
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("DROP VIEW IF EXISTS finding_reference_union")
    op.drop_constraint("ck_capr_capability", "capability_run", type_="check")
    _apply_step(
        _STEP1_TABLES, _STEP1_COLUMNS, _STEP1_CONSTRAINTS, _STEP1_INDEXES, reverse=False
    )
    _apply_step(
        _STEP2_TABLES, _STEP2_COLUMNS, _STEP2_CONSTRAINTS, _STEP2_INDEXES, reverse=False
    )
    op.execute(
        "UPDATE capability_run SET capability = 'evidence_search' "
        "WHERE capability = 'evidence_base'"
    )
    op.create_check_constraint(
        "ck_capr_capability", "capability_run", "capability IN ('evidence_search')"
    )
    _create_finding_reference_union(column="task_id")


def downgrade() -> None:
    # Transaction-scoped, for the reason `upgrade` states.
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("DROP VIEW IF EXISTS finding_reference_union")
    op.drop_constraint("ck_capr_capability", "capability_run", type_="check")
    # The five stored values, reversed under the NEW names — before the name
    # renames run, so `plan` is still `plan`. Each is independent of the others.
    op.execute(
        "UPDATE capability_run SET capability = 'evidence_base' "
        "WHERE capability = 'evidence_search'"
    )
    for kind in _LIFECYCLE_EVENT_KINDS:
        op.execute(
            f"UPDATE event_log SET event_type = 'project.{kind}' "
            f"WHERE event_type = 'task.{kind}'"
        )
    for key in _ACTOR_KEYS:
        _rewrite_jsonb("event_log", f'"{key}": "agent"', f'"{key}": "orchestrator"')
    for table in ("plan", "event_log"):
        _rewrite_jsonb(
            table,
            f'"steer_point": "{_NEW_STEER_POINT}"',
            f'"steer_point": "{_OLD_STEER_POINT}"',
        )
    _apply_step(
        _STEP2_TABLES, _STEP2_COLUMNS, _STEP2_CONSTRAINTS, _STEP2_INDEXES, reverse=True
    )
    _apply_step(
        _STEP1_TABLES, _STEP1_COLUMNS, _STEP1_CONSTRAINTS, _STEP1_INDEXES, reverse=True
    )
    op.create_check_constraint(
        "ck_capr_capability", "capability_run", "capability IN ('evidence_base')"
    )
    _create_finding_reference_union(column="project_id")
