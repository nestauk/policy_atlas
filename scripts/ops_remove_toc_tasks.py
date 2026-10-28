#!/usr/bin/env python3
"""Permanently delete theory-of-change tasks, so the database change can be undone.

What it is for
    Task 054 added a database revision (``9127f849697f``) with the theory-of-change
    tables. Undoing that revision (an Alembic "downgrade") refuses while any
    theory-of-change task exists, because dropping the tables would leave those
    tasks half-deleted. This script removes those tasks completely, so the
    downgrade can run. Use it only when rolling the feature back.

What it deletes
    Each theory-of-change task (``task.capability = 'theory_of_change'``) and every
    row that belongs to it, in one transaction (all or nothing): the theory itself
    (boxes, links, pathways, band items, judgements, figures), its walks (runs), intent
    records (scopes), events, document membership rows, plans, Task Agent
    transcripts and conversations. The documents themselves (``source_snapshot``)
    are shared between tasks and are kept. Uploaded files are not touched yet
    (they arrive in increment 5).

How to use it
    Without ``--apply`` it only lists what it would delete and changes nothing
    (a "dry run"). Add ``--apply`` to delete. Name tasks with ``--task-id`` to act
    on those alone; with none named, it acts on every theory-of-change task.
    A named id that is not a theory-of-change task stops the run (exit 2).

Usage::

    uv run --project backend python scripts/ops_remove_toc_tasks.py
    uv run --project backend python scripts/ops_remove_toc_tasks.py --apply \
        [--task-id <uuid> ...]
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ops_remove_scoping_tasks as scoping  # noqa: E402 - the shared FK-ordered delete

log = structlog.get_logger()

#: The theory-of-change tables, child first. They go before the shared order in
#: ``ops_remove_scoping_tasks._apply``: judgements name documents and walks.
TOC_TABLES: tuple[str, ...] = (
    "toc_figure",
    "toc_item_evidence",
    "toc_pathway_link",
    "toc_pathway",
    "toc_link",
    "toc_box",
    "toc_band_item",
)


def _selected(
    conn: Connection, named: list[uuid.UUID]
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """Return ``(theory-of-change task ids to act on, named ids that are not one)``."""
    every = [
        row[0]
        for row in conn.execute(
            text("SELECT task_id FROM task WHERE capability = 'theory_of_change'")
        )
    ]
    if not named:
        return every, []
    toc = set(every)
    wanted = list(dict.fromkeys(named))
    return [t for t in wanted if t in toc], [t for t in wanted if t not in toc]


def _list(conn: Connection, task_ids: list[uuid.UUID]) -> None:
    """Print each task and its row counts. Deletes nothing."""
    for task_id in task_ids:
        name = conn.execute(
            text("SELECT name FROM task WHERE task_id = :tid"), {"tid": task_id}
        ).scalar_one()
        counts = " ".join(
            f"{table}="
            + str(
                conn.execute(
                    text(f"SELECT count(*) FROM {table} WHERE task_id = :tid"),  # noqa: S608
                    {"tid": task_id},
                ).scalar_one()
            )
            for table in (*TOC_TABLES, "capability_run")
        )
        print(f"{task_id}  {name!r}  {counts}")


def run(engine: Engine, apply: bool, task_ids: list[uuid.UUID] | None = None) -> int:
    """List theory-of-change tasks, or delete them.

    Args:
        engine: Database engine to run against.
        apply: When ``True``, delete inside one transaction; when ``False``
            (the default), only list.
        task_ids: The tasks to act on; every theory-of-change task when empty.

    Returns:
        ``0`` on success (including nothing to do), ``2`` when a named id is
        not a theory-of-change task.
    """
    named = task_ids or []
    with engine.begin() as conn:
        selected, unknown = _selected(conn, named)
        if unknown:
            print("refusing: not a theory_of_change task:", file=sys.stderr)
            for task_id in unknown:
                print(f"  {task_id}", file=sys.stderr)
            return 2
        if not selected:
            print("no theory_of_change tasks found.")
            return 0
        if not apply:
            _list(conn, selected)
            return 0
        for table in TOC_TABLES:
            result = conn.execute(
                text(f"DELETE FROM {table} WHERE task_id = ANY(:ids)"),  # noqa: S608
                {"ids": selected},
            )
            log.info("ops_remove_toc_tasks.deleted", table=table, count=result.rowcount)
        scoping._apply(conn, selected, kind="theory_of_change")
    return 0


def main() -> int:
    """Entry point: parse the flags and run against ``$DATABASE_URL``."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--apply", action="store_true", help="delete (default: list only, change nothing)"
    )
    parser.add_argument(
        "--task-id",
        action="append",
        type=uuid.UUID,
        default=[],
        dest="task_ids",
        help="a theory_of_change task to act on; repeatable; default every one",
    )
    args = parser.parse_args()
    engine = create_engine(
        make_url(os.environ.get("DATABASE_URL", scoping._DEV_URL))
    )
    try:
        return run(engine, args.apply, args.task_ids)
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
