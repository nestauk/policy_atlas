#!/usr/bin/env python3
"""Hard-delete every ``options_scoping`` task so revision ``b5e1d7a4c026`` can downgrade.

That revision's ``downgrade()`` refuses while any ``task`` or ``capability_run``
row still carries ``capability = 'options_scoping'`` — dropping
``task.capability`` and narrowing ``ck_capr_capability`` would silently
reclassify those rows as Evidence searches. ADR 0037 § Rollback names the
remedy this script is: "archiving keeps the row, so it is not a remedy". This
is pre-merge, staging-only data; there is no production options-scoping data
to protect yet.

Default (no flags) LISTS every options-scoping task and its row counts across
the tables ``--apply`` would touch, and changes nothing. ``--apply``
hard-deletes them all, inside one transaction, in FK order.

Both modes refuse (exit 2) before any delete if an Evidence search task links
to one of the scoping tasks as its target — i.e. a ``task_link`` row whose
``source_task_id`` is the scoping task and whose ``target_task_id`` names an
``evidence_search`` task. Deleting the scoping task would silently destroy
that Evidence search task's provenance, so the operator needs to know before
they plan the run — the refusal fires in list mode too.

Usage::

    uv run --project backend python scripts/ops_remove_scoping_tasks.py
    uv run --project backend python scripts/ops_remove_scoping_tasks.py --apply
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
#: - ``capability_run`` FKs to ``evidence_scope``, so it precedes it.
#:
#: Never touched — corpus-level, shared between tasks: ``source_snapshot``,
#: ``chunk``, ``chunk_embedding``. ``finding_reference_union`` is a VIEW, not
#: a table: never deleted from.
TASK_ID_TABLES: tuple[str, ...] = (
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
    """Print the operator-facing listing for every scoping task. Deletes nothing.

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
    """Hard-delete every scoping task and its rows, in FK order.

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


def run(engine: Engine, apply: bool) -> int:
    """List or apply the removal of every options-scoping task.

    Args:
        engine: Database engine to run against.
        apply: When ``True``, hard-delete inside one transaction; when
            ``False`` (the default), only list and change nothing.

    Returns:
        Process exit code: ``0`` on success (including the empty case),
        ``2`` on the linked-Evidence-search refusal.
    """
    with engine.connect() as conn:
        task_ids = _scoping_task_ids(conn)
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
        task_ids = _scoping_task_ids(conn)
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
    """Entry point: parse ``--apply`` and run against ``$DATABASE_URL``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="hard-delete every options_scoping task (default: list only)",
    )
    args = parser.parse_args()

    url = make_url(os.environ.get("DATABASE_URL", _DEV_URL))
    engine = create_engine(url)
    try:
        return run(engine, args.apply)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
