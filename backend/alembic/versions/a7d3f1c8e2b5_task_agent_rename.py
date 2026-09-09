"""task 044 Task Agent rename — planning/planner → task_agent, in the catalog

Pure rename plus two losslessly reversible stored values (task 044,
deliverable 2). The product's steering conversation is the **Task Agent**, so
the last two code names for it leave the catalog: the conversation kind
``planning`` and the persona word ``planner``. No shape changes, no rows lost,
every row reads back identically under its new name.

Every object below comes from the live catalog at ``c1a7f4e9b0d2``, queried
with ``pg_constraint`` / ``pg_indexes`` rather than read off the SQLAlchemy
metadata — 038's docstring explains why: the metadata auto-names an unnamed
``ForeignKey`` as ``<table>_<column>_fkey`` while the chain may have created it
under an explicit name, and the downgrade has to restore exactly what the
older revisions drop by name. Two names here live only in the catalog:

    planning_transcript_pkey           (metadata: unnamed primary key)
    planning_transcript_task_id_fkey   (auto-named; follows the table)

Renamed by name, after :func:`_verify_constraints` has confirmed all eight are
present (a diverged catalog fails with a diagnostic naming the missing set,
not a bare "constraint does not exist"). Renaming a UNIQUE or PRIMARY KEY
*constraint* renames its
backing index with it, so the three indexes of ``planning_transcript`` need no
statement of their own.

    planning_transcript                 → task_agent_transcript
    planning_transcript.planner_state   → task_agent_transcript.task_agent_state
    planning_transcript_pkey            → task_agent_transcript_pkey
    planning_transcript_task_id_fkey    → task_agent_transcript_task_id_fkey
    fk_planning_transcript_conversation → fk_task_agent_transcript_conversation
    uq_ptr_task_client_turn             → uq_tat_task_client_turn
    uq_ptr_task_turn_index              → uq_tat_task_turn_index
    ck_ptr_status                       → ck_tat_status
    ck_ptr_suggestions_array            → ck_tat_suggestions_array
    ck_conversation_planning_never_archived
                                        → ck_conversation_task_agent_never_archived

Rewritten, not renamed. Two objects carry the stored value ``'planning'`` in
their own definition, so they are dropped around the value rewrite and
recreated over the new value:

    ck_conversation_kind — keeps its *name*; its expression becomes
        ``kind IN ('task_agent', 'chat')``.
    uq_conversation_one_active_planning — a partial unique index whose
        predicate names the kind; recreated as
        ``uq_conversation_one_active_task_agent`` over
        ``kind = 'task_agent' AND status = 'active'``.

Stored values, both reversed on downgrade:

    conversation.kind   'planning' → 'task_agent'
    plan.created_by     'planner'  → 'task_agent'

``plan.created_by`` is written as ``'user'`` by every production writer the 044
manifest could find; the ``'planner'`` value appears in the schema comment and
in eight test modules. The one-line rewrite stays for safety — it is a no-op
where the value was never written, and the downgrade puts back exactly what it
took.

Revision ID: a7d3f1c8e2b5
Revises: c1a7f4e9b0d2
Create Date: 2026-09-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7d3f1c8e2b5"
down_revision: Union[str, None] = "c1a7f4e9b0d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- The rename manifest, verbatim from the live catalog at c1a7f4e9b0d2 ---

_TABLES: tuple[tuple[str, str], ...] = (("planning_transcript", "task_agent_transcript"),)

_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("task_agent_transcript", "planner_state", "task_agent_state"),
)

# ``(table_after_the_table_rename, today, after)``.
_CONSTRAINTS: tuple[tuple[str, str, str], ...] = (
    ("task_agent_transcript", "planning_transcript_pkey", "task_agent_transcript_pkey"),
    (
        "task_agent_transcript",
        "planning_transcript_task_id_fkey",
        "task_agent_transcript_task_id_fkey",
    ),
    (
        "task_agent_transcript",
        "fk_planning_transcript_conversation",
        "fk_task_agent_transcript_conversation",
    ),
    ("task_agent_transcript", "uq_ptr_task_client_turn", "uq_tat_task_client_turn"),
    ("task_agent_transcript", "uq_ptr_task_turn_index", "uq_tat_task_turn_index"),
    ("task_agent_transcript", "ck_ptr_status", "ck_tat_status"),
    ("task_agent_transcript", "ck_ptr_suggestions_array", "ck_tat_suggestions_array"),
    (
        "conversation",
        "ck_conversation_planning_never_archived",
        "ck_conversation_task_agent_never_archived",
    ),
)

# Where each renamed constraint lives *before* the step that renames it: on the
# upgrade the transcript table still has its old name, on the downgrade its new
# one (the downgrade renames constraints before it renames the table back).
_TABLE_BEFORE: dict[str, str] = {new: old for old, new in _TABLES}

_KIND_CHECK = "ck_conversation_kind"
_ACTIVE_INDEX_OLD = "uq_conversation_one_active_planning"
_ACTIVE_INDEX_NEW = "uq_conversation_one_active_task_agent"


def _verify_constraints(*, reverse: bool) -> None:
    """Fail with a named diagnostic when the catalog is not what this expects.

    Every rename below addresses a constraint by name, and Postgres answers a
    name it does not hold with a bare "constraint ... does not exist". On a
    catalog that has diverged (a hand-patched database, a partial restore) that
    error names one object and explains nothing, so the whole set is checked
    first and the missing ones are reported together.

    Args:
        reverse: Check the post-rename names, for the downgrade.

    Raises:
        RuntimeError: When any expected constraint is absent, naming all of them.
    """
    bind = op.get_bind()
    missing: list[str] = []
    for table, old, new in _CONSTRAINTS:
        name = new if reverse else old
        live_table = table if reverse else _TABLE_BEFORE.get(table, table)
        found = bind.execute(
            sa.text(
                "SELECT 1 FROM pg_constraint "
                "WHERE conname = :name AND conrelid = to_regclass(:table)"
            ),
            {"name": name, "table": live_table},
        ).scalar()
        if found is None:
            missing.append(f"{live_table}.{name}")
    if missing:
        direction = "downgrade" if reverse else "upgrade"
        raise RuntimeError(
            f"a7d3f1c8e2b5 {direction}: the catalog is missing "
            f"{len(missing)} of {len(_CONSTRAINTS)} expected constraint(s): "
            + ", ".join(missing)
            + ". This revision renames by name and cannot run against a "
            "diverged catalog; reconcile the database with the migration "
            "chain before retrying."
        )


def _rename_tables(*, reverse: bool) -> None:
    """Rename each table in :data:`_TABLES` (``reverse`` swaps the pair)."""
    for old, new in reversed(_TABLES) if reverse else _TABLES:
        op.rename_table(new if reverse else old, old if reverse else new)


def _rename_columns(*, reverse: bool) -> None:
    """Rename each column in :data:`_COLUMNS` (``reverse`` swaps the pair)."""
    for table, old, new in reversed(_COLUMNS) if reverse else _COLUMNS:
        op.alter_column(table, new if reverse else old, new_column_name=old if reverse else new)


def _rename_constraints(*, reverse: bool) -> None:
    """Rename each PK/FK/UNIQUE/CHECK in :data:`_CONSTRAINTS`.

    Args:
        reverse: Swap each pair and the order, for the downgrade. The table a
            constraint hangs off is named post-rename, so the downgrade runs
            this before :func:`_rename_tables` puts the old table name back.
    """
    for table, old, new in reversed(_CONSTRAINTS) if reverse else _CONSTRAINTS:
        source, target = (new, old) if reverse else (old, new)
        op.execute(f'ALTER TABLE "{table}" RENAME CONSTRAINT "{source}" TO "{target}"')


def _rewrite_conversation_kind(*, reverse: bool) -> None:
    """Move the stored ``conversation.kind`` value, with its two guards.

    The CHECK expression and the partial unique index both name the value, so
    the value cannot move while they stand: drop both, rewrite the rows,
    recreate both over the new value.

    Args:
        reverse: Rewrite ``task_agent`` back to ``planning``.
    """
    source, target = ("task_agent", "planning") if reverse else ("planning", "task_agent")
    index_from = _ACTIVE_INDEX_NEW if reverse else _ACTIVE_INDEX_OLD
    index_to = _ACTIVE_INDEX_OLD if reverse else _ACTIVE_INDEX_NEW
    op.execute(f'ALTER TABLE conversation DROP CONSTRAINT "{_KIND_CHECK}"')
    op.execute(f'DROP INDEX "{index_from}"')
    op.execute(f"UPDATE conversation SET kind = '{target}' WHERE kind = '{source}'")
    op.execute(
        f'ALTER TABLE conversation ADD CONSTRAINT "{_KIND_CHECK}" '
        f"CHECK (kind IN ('{target}', 'chat'))"
    )
    op.execute(
        f'CREATE UNIQUE INDEX "{index_to}" ON conversation (task_id) '
        f"WHERE (kind = '{target}' AND status = 'active')"
    )


def _rewrite_plan_created_by(*, reverse: bool) -> None:
    """Move the stored ``plan.created_by`` attribution value."""
    source, target = ("task_agent", "planner") if reverse else ("planner", "task_agent")
    op.execute(f"UPDATE plan SET created_by = '{target}' WHERE created_by = '{source}'")


def upgrade() -> None:
    """Rename the transcript objects and move the two stored values forward."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    _verify_constraints(reverse=False)
    _rename_tables(reverse=False)
    _rename_columns(reverse=False)
    _rename_constraints(reverse=False)
    _rewrite_conversation_kind(reverse=False)
    _rewrite_plan_created_by(reverse=False)


def downgrade() -> None:
    """Reverse every rename and both stored values, in the opposite order."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    _verify_constraints(reverse=True)
    _rewrite_plan_created_by(reverse=True)
    _rewrite_conversation_kind(reverse=True)
    _rename_constraints(reverse=True)
    _rename_columns(reverse=True)
    _rename_tables(reverse=True)
