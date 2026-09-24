#!/usr/bin/env python3
"""Hard-delete named ``options_scoping`` tasks so their revisions can downgrade.

Two revisions refuse while options-scoping data exists, and this script is the
remedy both name:

- ``b5e1d7a4c026`` (task 044) refuses while any ``task`` or ``capability_run``
  row still carries ``capability = 'options_scoping'`` — dropping
  ``task.capability`` and narrowing ``ck_capr_capability`` would silently
  reclassify those rows as Evidence searches. ADR 0037 § Rollback: "archiving
  keeps the row, so it is not a remedy".
- ``c7e2a9f4b1d8`` (task 045) refuses while any walk runs under a
  ``longlist`` or ``targeted`` intent record (the longlist walk and its option
  searches), or an ``extraction_result`` has no ``selection_run_id``. Those
  walks exist only on options-scoping tasks, so removing the tasks removes
  them, with their option, membership, relation, ``longlist_result`` and
  intervention-profile rows (ADR 0039 § Rollback).

Options-scoping tasks may be real users' work, so nothing is deleted by
default and nothing is deleted wholesale: ``--apply`` removes only the tasks
named with one or more ``--task-id`` flags, and refuses (exit 2) without one.

Default (no ``--apply``) LISTS the options-scoping tasks — the named ones, or
every one when none is named — and their row counts across the tables
``--apply`` would touch, and changes nothing. ``--apply --task-id ...``
hard-deletes the named tasks, inside one transaction, in FK order. A named id
that is not an options-scoping task refuses the run (exit 2).

Both modes refuse (exit 2) before any delete if an Evidence search task links
to one of the scoping tasks as its target — i.e. a ``task_link`` row whose
``source_task_id`` is the scoping task and whose ``target_task_id`` names an
``evidence_search`` task. Deleting the scoping task would silently destroy
that Evidence search task's provenance, so the operator needs to know before
they plan the run — the refusal fires in list mode too.

Usage::

    uv run --project backend python scripts/ops_remove_scoping_tasks.py
    uv run --project backend python scripts/ops_remove_scoping_tasks.py \
        --apply --task-id <uuid> [--task-id <uuid> ...]
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

log = structlog.get_logger()

_DEV_URL = "postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"

#: The result tables a scoping task can carry rows in — summed for the
#: operator-facing listing's "results" count.
RESULT_TABLES: tuple[str, ...] = (
    "option",
    "option_membership",
    "option_relation",
    "longlist_result",
    "intervention_profile_record",
    "source_screening_result",
    "source_classification_result",
    "source_appraisal_result",
    "intervention_outcome_finding",
    "implementation_context_finding",
    "source_extraction_record",
    "extraction_result",
    "characterisation_result",
    "selection_result",
    "grouping_result",
    "synthesis_result",
    "source_tag",
    "search_coverage_record",
)

#: Child-before-parent deletion order for every table that carries a
#: ``task_id`` column and is scoped to the removed tasks. The earlier
#: artefact/conversation descendants (annotation, addressable_unit, block,
#: citation, chat_turn) carry no ``task_id`` of their own, so they are
#: deleted separately, ahead of this list.
#:
#: Verified against the live foreign keys in
#: ``backend/src/policy_atlas/core/schema.py`` — several entries are NOT in
#: the order a naive "layer" reading of the roll-up chain suggests:
#:
#: - ``synthesis_result`` is the deepest child (it FKs to
#:   characterisation_result, selection_result, extraction_result,
#:   grouping_result AND artefact), so it is deleted first among them, not
#:   last.
#: - ``grouping_result`` FKs to ``extraction_result``, so it precedes it.
#: - ``task_agent_transcript`` and ``plan`` FK to ``conversation``, which
#:   itself FKs to ``artefact`` (``entry_artefact_id``) — so ``conversation``
#:   must be deleted before ``artefact``, not after.
#: - ``event_log`` FKs to ``runs``, so it precedes ``runs``, not follows it.
#: - ``runs`` FKs to ``capability_run`` (``runs.capability_run_id``), and
#:   ``artefact`` also FKs to ``capability_run`` — both precede it.
#: - ``capability_run`` FKs to ``evidence_scope``, so it precedes it. Its
#:   self-FK (``parent_capability_run_id``, task 045) is satisfied inside one
#:   statement: a parent and its children always share a ``task_id``.
#: - The task 045 option records lead: ``option_membership`` and
#:   ``option_relation`` FK to ``option``; ``option`` FKs to ``runs`` (and is
#:   named by ``task_link.option_id``, whose rows are already gone);
#:   ``longlist_result`` FKs to ``runs`` and ``evidence_scope``;
#:   ``intervention_profile_record`` FKs to ``source_extraction_record``.
#:
#: Never touched — corpus-level, shared between tasks: ``source_snapshot``,
#: ``chunk``, ``chunk_embedding``. ``finding_reference_union`` is a VIEW, not
#: a table: never deleted from.
TASK_ID_TABLES: tuple[str, ...] = (
    "option_membership",
    "option_relation",
    "option",
    "longlist_result",
    "intervention_profile_record",
    "synthesis_result",
    "grouping_result",
    "extraction_result",
    "selection_result",
    "characterisation_result",
    "intervention_outcome_finding",
    "implementation_context_finding",
    "source_extraction_record",
    "source_classification_result",
    "source_appraisal_result",
    "source_screening_result",
    "source_tag",
    "search_coverage_record",
    "task_source_snapshot",
    "task_agent_transcript",
    "plan",
    "conversation",
    "artefact",
    "event_log",
    "runs",
    "capability_run",
    "evidence_scope",
    "project_membership",
)


def _scoping_task_ids(conn: Connection) -> list[uuid.UUID]:
    """Return every task id whose ``task.capability`` is options_scoping."""
    rows = conn.execute(text("SELECT task_id FROM task WHERE capability = 'options_scoping'"))
    return [row[0] for row in rows]


def _selected(
    conn: Connection, named: list[uuid.UUID] | None
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Return ``(scoping task ids to act on, named ids that are not scoping tasks)``.

    Args:
        conn: Open database connection.
        named: The ``--task-id`` values, or ``None``/empty for every scoping task.
    """
    every = _scoping_task_ids(conn)
    if not named:
        return every, []
    scoping = set(every)
    wanted = list(dict.fromkeys(named))
    return [t for t in wanted if t in scoping], [t for t in wanted if t not in scoping]


def _refusals(conn: Connection, task_ids: list[uuid.UUID]) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Return ``(scoping_task_id, evidence_search_task_id)`` pairs that block a run.

    A pair is a ``task_link`` row whose ``source_task_id`` is one of
    ``task_ids`` and whose ``target_task_id`` names an ``evidence_search``
    task — deleting the scoping task would silently destroy that task's
    provenance.

    Args:
        conn: Open database connection.
        task_ids: Candidate options-scoping task ids.

    Returns:
        The offending pairs, empty if none.
    """
    if not task_ids:
        return []
    rows = conn.execute(
        text(
            "SELECT tl.source_task_id, tl.target_task_id "
            "FROM task_link tl "
            "JOIN task t ON t.task_id = tl.target_task_id "
            "WHERE tl.source_task_id = ANY(:ids) AND t.capability = 'evidence_search'"
        ),
        {"ids": task_ids},
    )
    return [(row[0], row[1]) for row in rows]


def _counts(conn: Connection, task_id: uuid.UUID) -> dict[str, int]:
    """Return one scoping task's row counts across every table ``--apply`` would touch.

    Args:
        conn: Open database connection.
        task_id: The scoping task's id.

    Returns:
        Counts keyed ``links``, ``capability_run``, ``runs``, ``evidence_scope``
        and ``results`` (the sum of :data:`RESULT_TABLES`).
    """
    counts = {
        "links": conn.execute(
            text(
                "SELECT count(*) FROM task_link "
                "WHERE source_task_id = :tid OR target_task_id = :tid"
            ),
            {"tid": task_id},
        ).scalar_one(),
        "capability_run": conn.execute(
            text("SELECT count(*) FROM capability_run WHERE task_id = :tid"),
            {"tid": task_id},
        ).scalar_one(),
        "runs": conn.execute(
            text("SELECT count(*) FROM runs WHERE task_id = :tid"), {"tid": task_id}
        ).scalar_one(),
        "evidence_scope": conn.execute(
            text("SELECT count(*) FROM evidence_scope WHERE task_id = :tid"),
            {"tid": task_id},
        ).scalar_one(),
    }
    counts["results"] = sum(
        conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE task_id = :tid"),  # noqa: S608
            {"tid": task_id},
        ).scalar_one()
        for table in RESULT_TABLES
    )
    return counts


def _list_only(conn: Connection, task_ids: list[uuid.UUID]) -> None:
    """Print the operator-facing listing for the given scoping tasks. Deletes nothing.

    Args:
        conn: Open database connection.
        task_ids: The options-scoping task ids to report on.
    """
    for task_id in task_ids:
        row = conn.execute(
            text("SELECT name, status FROM task WHERE task_id = :tid"), {"tid": task_id}
        ).one()
        c = _counts(conn, task_id)
        print(
            f"{task_id}  {row.name!r}  status={row.status}  "
            f"task_link={c['links']} capability_run={c['capability_run']} "
            f"runs={c['runs']} evidence_scope={c['evidence_scope']} results={c['results']}"
        )


def _apply(conn: Connection, task_ids: list[uuid.UUID]) -> None:
    """Hard-delete the given scoping tasks and their rows, in FK order.

    Args:
        conn: Open database connection, inside the caller's transaction.
        task_ids: The options-scoping task ids to remove.
    """
    # Break the two nullable cycle pointers between plan and evidence_scope first.
    conn.execute(
        text("UPDATE plan SET evidence_scope_id = NULL WHERE task_id = ANY(:ids)"),
        {"ids": task_ids},
    )
    conn.execute(
        text("UPDATE evidence_scope SET plan_id = NULL WHERE task_id = ANY(:ids)"),
        {"ids": task_ids},
    )

    link_result = conn.execute(
        text(
            "DELETE FROM task_link WHERE source_task_id = ANY(:ids) "
            "OR target_task_id = ANY(:ids)"
        ),
        {"ids": task_ids},
    )
    log.info("ops_remove_scoping_tasks.deleted", table="task_link", count=link_result.rowcount)

    # Artefact/conversation descendants that carry no task_id of their own.
    conn.execute(
        text(
            "DELETE FROM citation WHERE annotation_id IN ("
            "  SELECT annotation_id FROM annotation WHERE block_id IN ("
            "    SELECT block_id FROM block WHERE artefact_id IN ("
            "      SELECT artefact_id FROM artefact WHERE task_id = ANY(:ids)"
            "    )"
            "  )"
            ")"
        ),
        {"ids": task_ids},
    )
    conn.execute(
        text(
            "DELETE FROM annotation WHERE block_id IN ("
            "  SELECT block_id FROM block WHERE artefact_id IN ("
            "    SELECT artefact_id FROM artefact WHERE task_id = ANY(:ids)"
            "  )"
            ")"
        ),
        {"ids": task_ids},
    )
    conn.execute(
        text(
            "DELETE FROM addressable_unit WHERE block_id IN ("
            "  SELECT block_id FROM block WHERE artefact_id IN ("
            "    SELECT artefact_id FROM artefact WHERE task_id = ANY(:ids)"
            "  )"
            ")"
        ),
        {"ids": task_ids},
    )
    conn.execute(
        text(
            "DELETE FROM block WHERE artefact_id IN ("
            "  SELECT artefact_id FROM artefact WHERE task_id = ANY(:ids)"
            ")"
        ),
        {"ids": task_ids},
    )
    conn.execute(
        text(
            "DELETE FROM chat_turn WHERE conversation_id IN ("
            "  SELECT id FROM conversation WHERE task_id = ANY(:ids)"
            ")"
        ),
        {"ids": task_ids},
    )

    for table in TASK_ID_TABLES:
        result = conn.execute(
            text(f"DELETE FROM {table} WHERE task_id = ANY(:ids)"),  # noqa: S608
            {"ids": task_ids},
        )
        log.info("ops_remove_scoping_tasks.deleted", table=table, count=result.rowcount)

    task_result = conn.execute(
        text("DELETE FROM task WHERE task_id = ANY(:ids)"), {"ids": task_ids}
    )
    log.info("ops_remove_scoping_tasks.deleted", table="task", count=task_result.rowcount)
    joined = ", ".join(str(tid) for tid in task_ids)
    print(f"deleted {task_result.rowcount} options_scoping task(s): {joined}")


def _print_refusal(refusals: list[tuple[uuid.UUID, uuid.UUID]]) -> None:
    print(
        "refusing: the following options_scoping task(s) are linked to as a target "
        "by an evidence_search task — deleting them would destroy that task's "
        "provenance:",
        file=sys.stderr,
    )
    for scoping_id, es_id in refusals:
        print(f"  scoping task {scoping_id} -> evidence_search task {es_id}", file=sys.stderr)


def _print_not_scoping(ids: list[uuid.UUID]) -> None:
    print("refusing: not an options_scoping task:", file=sys.stderr)
    for task_id in ids:
        print(f"  {task_id}", file=sys.stderr)


def run(engine: Engine, apply: bool, task_ids: list[uuid.UUID] | None = None) -> int:
    """List options-scoping tasks, or remove the named ones.

    Args:
        engine: Database engine to run against.
        apply: When ``True``, hard-delete the named tasks inside one
            transaction; when ``False`` (the default), only list and change
            nothing.
        task_ids: The tasks to act on (``--task-id``). Required with
            ``apply``; without it, listing covers every options-scoping task.

    Returns:
        Process exit code: ``0`` on success (including the empty case),
        ``2`` on a refusal (``--apply`` with no ``--task-id``, a named id that
        is not an options-scoping task, or a linked Evidence search).
    """
    if apply and not task_ids:
        print("refusing: --apply needs one or more --task-id", file=sys.stderr)
        return 2
    named = task_ids
    with engine.connect() as conn:
        task_ids, unknown = _selected(conn, named)
        if unknown:
            _print_not_scoping(unknown)
            return 2
        refusals = _refusals(conn, task_ids)
        if refusals:
            _print_refusal(refusals)
            return 2
        if not task_ids:
            print("no options_scoping tasks found.")
            return 0
        if not apply:
            _list_only(conn, task_ids)
            return 0

    with engine.begin() as conn:
        # Re-check inside the write transaction: belt and braces against a
        # task_link written between the read above and this transaction.
        task_ids, unknown = _selected(conn, named)
        if unknown:
            _print_not_scoping(unknown)
            return 2
        refusals = _refusals(conn, task_ids)
        if refusals:
            _print_refusal(refusals)
            return 2
        if not task_ids:
            print("no options_scoping tasks found.")
            return 0
        _apply(conn, task_ids)
    return 0


def main() -> int:
    """Entry point: parse the flags and run against ``$DATABASE_URL``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="hard-delete the tasks named with --task-id (default: list only)",
    )
    parser.add_argument(
        "--task-id",
        action="append",
        type=uuid.UUID,
        default=[],
        dest="task_ids",
        help="an options_scoping task to act on; repeatable; required with --apply",
    )
    args = parser.parse_args()

    url = make_url(os.environ.get("DATABASE_URL", _DEV_URL))
    engine = create_engine(url)
    try:
        return run(engine, args.apply, args.task_ids)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
