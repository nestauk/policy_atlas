#!/usr/bin/env python3
"""Delete old full-text snapshots that no task links to any more (task 057, D3 retention rule).

What this is for, in plain terms: when the app fetches a document's full text it
parses it once and keeps the result in a shared *document store* (a
``source_snapshot`` row, its passages in ``chunk`` and their search vectors in
``chunk_embedding``). Tasks point at those stored texts through *link rows*
(``task_source_snapshot``: either column ``source_snapshot_id`` or
``full_text_snapshot_id``). Because the store is shared between tasks, removing a
task never removes the text. A stored full text that no link row points at, and
has not for a while, is dead weight. The contract's retention rule (D3) says such
a snapshot is deleted after 90 days by this script.

What it deletes: ``source_snapshot`` rows with ``text_basis = 'full_text'``,
created more than ``--older-than-days`` days ago (default 90), that no link row
references through either snapshot column, together with their chunks and chunk
embeddings. Envelope snapshots (``text_basis = 'abstract_only'``, a document's
abstract and metadata) are never touched. A snapshot whose chunks are still quoted
by a ``citation``, or that a ``source_extraction_record`` still names, is also left
in place (deleting it would break those rows' foreign keys).

How it stays safe while ingest is running (a link "racing in"): each batch runs in
its own transaction and does four steps.

1. Pick the next batch of candidates (old, full text, unreferenced), oldest first.
2. Lock those snapshot rows with ``SELECT ... FOR UPDATE SKIP LOCKED``. An ingest
   that is linking a snapshot at that moment holds a light lock on it (Postgres
   takes one for the foreign-key check on the link row), so that snapshot is
   skipped. Once our lock is held, no new link to a locked snapshot can be written
   until this transaction ends: the linker waits.
3. Re-check, in the same transaction and after the lock, that no link row (and no
   citation or extraction record) references each locked snapshot. This catches a
   link committed between step 1 and step 2. Any snapshot that fails the re-check
   is kept.
4. Delete the survivors' chunk embeddings, chunks and snapshots, then commit.

An ingest that was waiting on a snapshot this script then deleted gets a
foreign-key error and must retry (it will parse the document again). That is the
rare cost of the rule; it never leaves a link row pointing at a deleted snapshot.

Nothing is deleted unless you pass ``--apply``. The default (``--dry-run``) prints
how many snapshots, chunks and embeddings would go and changes nothing.

When and how an operator runs it: by hand, against the database named by
``DATABASE_URL``, whenever the store needs tidying (for example once a quarter, or
before a storage review). There is no scheduler for it in this slice. Run the dry
run first, read the counts, then run it again with ``--apply``::

    DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME \\
        uv run --project backend python scripts/prune_unlinked_snapshots.py
    DATABASE_URL=... uv run --project backend python \\
        scripts/prune_unlinked_snapshots.py --apply [--older-than-days 90] [--batch-size 500]

Exit codes: ``0`` on success (including nothing to delete), ``2`` when the flags
are refused (``--older-than-days`` below 1, ``--batch-size`` below 1).
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, make_url

_DEV_URL = "postgresql+psycopg://policy_atlas:policy_atlas@localhost:5432/policy_atlas"

DEFAULT_OLDER_THAN_DAYS = 90
DEFAULT_BATCH_SIZE = 500

#: True when nothing references snapshot ``s``: no link row on either snapshot
#: column, no citation on one of its chunks, no extraction record naming it.
_UNREFERENCED = (
    "NOT EXISTS (SELECT 1 FROM task_source_snapshot t "
    "  WHERE t.source_snapshot_id = s.source_snapshot_id "
    "     OR t.full_text_snapshot_id = s.source_snapshot_id) "
    "AND NOT EXISTS (SELECT 1 FROM source_extraction_record e "
    "  WHERE e.source_snapshot_id = s.source_snapshot_id) "
    "AND NOT EXISTS (SELECT 1 FROM citation ci JOIN chunk c ON c.chunk_id = ci.chunk_id "
    "  WHERE c.source_snapshot_id = s.source_snapshot_id)"
)

#: Called with the open batch transaction's connection and the batch's ids.
Hook = Callable[[Connection, list[uuid.UUID]], None]


@dataclass(frozen=True)
class BatchResult:
    """What one batch did.

    Attributes:
        candidates: Snapshots picked in step 1.
        locked: Of those, the ones this transaction locked (the rest were busy).
        deleted: Snapshot ids deleted (in dry-run mode: none).
        chunks: Chunk rows deleted.
        embeddings: Chunk-embedding rows deleted.
        last_key: The (created_at, id) of the last candidate, where the next batch
            starts; ``None`` when there were no candidates.
    """

    candidates: int
    locked: int
    deleted: list[uuid.UUID]
    chunks: int
    embeddings: int
    last_key: tuple[datetime, uuid.UUID] | None


def cutoff(conn: Connection, older_than_days: int) -> datetime:
    """Return the database's ``now()`` minus ``older_than_days`` days.

    Args:
        conn: Open database connection.
        older_than_days: Age in days a snapshot must exceed.

    Returns:
        The creation time a snapshot must be older than to be a candidate.
    """
    value: datetime = conn.execute(
        text("SELECT now() - make_interval(days => :d)"), {"d": older_than_days}
    ).scalar_one()
    return value


def select_candidates(
    conn: Connection,
    before: datetime,
    after: tuple[datetime, uuid.UUID] | None,
    limit: int,
) -> list[tuple[datetime, uuid.UUID]]:
    """Step 1: the next batch of old, unreferenced full-text snapshots, oldest first.

    Args:
        conn: Open database connection.
        before: Only snapshots created before this time qualify.
        after: Resume after this (created_at, id) key; ``None`` starts at the oldest.
        limit: Batch size.

    Returns:
        ``(created_at, source_snapshot_id)`` pairs in key order.
    """
    params: dict[str, object] = {"before": before, "limit": limit}
    resume = ""
    if after is not None:
        resume = "AND (s.created_at, s.source_snapshot_id) > (:after_at, :after_id) "
        params.update(after_at=after[0], after_id=after[1])
    rows = conn.execute(
        text(
            "SELECT s.created_at, s.source_snapshot_id FROM source_snapshot s "  # noqa: S608
            "WHERE s.text_basis = 'full_text' AND s.created_at < :before "
            f"{resume}AND {_UNREFERENCED} "
            "ORDER BY s.created_at, s.source_snapshot_id LIMIT :limit"
        ),
        params,
    )
    return [(row[0], row[1]) for row in rows]


def lock_candidates(conn: Connection, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Step 2: lock the candidate snapshot rows, skipping any another transaction holds.

    Args:
        conn: Connection inside the batch transaction.
        ids: Candidate snapshot ids.

    Returns:
        The ids this transaction now holds ``FOR UPDATE``.
    """
    if not ids:
        return []
    rows = conn.execute(
        text(
            "SELECT source_snapshot_id FROM source_snapshot "
            "WHERE source_snapshot_id = ANY(:ids) FOR UPDATE SKIP LOCKED"
        ),
        {"ids": ids},
    )
    return [row[0] for row in rows]


def still_unreferenced(conn: Connection, ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Step 3: of the locked ids, the ones nothing references now.

    Runs as a new statement after the lock, so under Postgres's default isolation it
    sees every link committed before the lock was taken.

    Args:
        conn: Connection inside the batch transaction.
        ids: Locked snapshot ids.

    Returns:
        The ids safe to delete.
    """
    if not ids:
        return []
    rows = conn.execute(
        text(
            "SELECT s.source_snapshot_id FROM source_snapshot s "  # noqa: S608
            f"WHERE s.source_snapshot_id = ANY(:ids) AND {_UNREFERENCED}"
        ),
        {"ids": ids},
    )
    return [row[0] for row in rows]


def delete_snapshots(conn: Connection, ids: list[uuid.UUID]) -> tuple[int, int]:
    """Step 4: delete the snapshots' chunk embeddings, chunks and snapshot rows.

    Args:
        conn: Connection inside the batch transaction.
        ids: Snapshot ids that passed the re-check.

    Returns:
        ``(chunks deleted, embeddings deleted)``.
    """
    if not ids:
        return 0, 0
    embeddings = conn.execute(
        text(
            "DELETE FROM chunk_embedding WHERE chunk_id IN "
            "(SELECT chunk_id FROM chunk WHERE source_snapshot_id = ANY(:ids))"
        ),
        {"ids": ids},
    ).rowcount
    chunks = conn.execute(
        text("DELETE FROM chunk WHERE source_snapshot_id = ANY(:ids)"), {"ids": ids}
    ).rowcount
    conn.execute(
        text("DELETE FROM source_snapshot WHERE source_snapshot_id = ANY(:ids)"), {"ids": ids}
    )
    return chunks, embeddings


def prune_batch(
    engine: Engine,
    before: datetime,
    after: tuple[datetime, uuid.UUID] | None,
    batch_size: int,
    *,
    before_lock: Hook | None = None,
    after_lock: Hook | None = None,
) -> BatchResult:
    """Run steps 1 to 4 for one batch inside one transaction, and commit it.

    Args:
        engine: Database engine.
        before: Creation-time cutoff (see :func:`cutoff`).
        after: Resume key from the previous batch, or ``None``.
        batch_size: Most snapshots handled in this batch.
        before_lock: Test seam, called between steps 1 and 2.
        after_lock: Test seam, called between steps 2 and 3.

    Returns:
        The batch's :class:`BatchResult`.
    """
    with engine.begin() as conn:
        picked = select_candidates(conn, before, after, batch_size)
        ids = [snapshot_id for _, snapshot_id in picked]
        if before_lock is not None:
            before_lock(conn, ids)
        locked = lock_candidates(conn, ids)
        if after_lock is not None:
            after_lock(conn, locked)
        survivors = still_unreferenced(conn, locked)
        chunks, embeddings = delete_snapshots(conn, survivors)
    return BatchResult(
        candidates=len(picked),
        locked=len(locked),
        deleted=survivors,
        chunks=chunks,
        embeddings=embeddings,
        last_key=picked[-1] if picked else None,
    )


def _dry_run(conn: Connection, before: datetime) -> int:
    """Print what ``--apply`` would delete now, and change nothing.

    Args:
        conn: Open database connection.
        before: Creation-time cutoff.

    Returns:
        The number of snapshots that would be deleted.
    """
    row = conn.execute(
        text(
            "WITH c AS (SELECT s.source_snapshot_id FROM source_snapshot s "  # noqa: S608
            "  WHERE s.text_basis = 'full_text' AND s.created_at < :before "
            f"  AND {_UNREFERENCED}) "
            "SELECT (SELECT count(*) FROM c), "
            "  (SELECT count(*) FROM chunk WHERE source_snapshot_id IN "
            "     (SELECT source_snapshot_id FROM c)), "
            "  (SELECT count(*) FROM chunk_embedding WHERE chunk_id IN "
            "     (SELECT chunk_id FROM chunk WHERE source_snapshot_id IN "
            "        (SELECT source_snapshot_id FROM c)))"
        ),
        {"before": before},
    ).one()
    snapshots, chunks, embeddings = int(row[0]), int(row[1]), int(row[2])
    print(
        f"dry run: would delete {snapshots} snapshot(s), {chunks} chunk(s), "
        f"{embeddings} embedding(s) created before {before.isoformat()}; "
        "nothing changed (pass --apply to delete)"
    )
    return snapshots


def run(
    engine: Engine,
    *,
    older_than_days: int = DEFAULT_OLDER_THAN_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    apply: bool = False,
) -> int:
    """Report, or delete, old full-text snapshots that nothing links to.

    Args:
        engine: Database engine to run against.
        older_than_days: Only snapshots older than this many days go; at least 1.
        batch_size: Snapshots per transaction; at least 1.
        apply: ``True`` deletes in committed batches; ``False`` (default) only counts.

    Returns:
        Process exit code: ``0`` on success, ``2`` when a flag is refused.
    """
    if older_than_days < 1:
        print("refusing: --older-than-days must be 1 or more", file=sys.stderr)
        return 2
    if batch_size < 1:
        print("refusing: --batch-size must be 1 or more", file=sys.stderr)
        return 2

    with engine.connect() as conn:
        before = cutoff(conn, older_than_days)
        if not apply:
            _dry_run(conn, before)
            return 0

    totals = {"snapshots": 0, "chunks": 0, "embeddings": 0, "kept": 0}
    after: tuple[datetime, uuid.UUID] | None = None
    number = 0
    while True:
        result = prune_batch(engine, before, after, batch_size)
        if result.last_key is None:
            break
        number += 1
        kept = result.candidates - len(result.deleted)
        print(
            f"batch {number}: candidates={result.candidates} locked={result.locked} "
            f"deleted={len(result.deleted)} kept={kept} "
            f"chunks={result.chunks} embeddings={result.embeddings}"
        )
        totals["snapshots"] += len(result.deleted)
        totals["chunks"] += result.chunks
        totals["embeddings"] += result.embeddings
        totals["kept"] += kept
        after = result.last_key
    print(
        f"total: deleted {totals['snapshots']} snapshot(s), {totals['chunks']} chunk(s), "
        f"{totals['embeddings']} embedding(s); kept {totals['kept']} "
        "(busy or linked during the run)"
    )
    return 0


def main() -> int:
    """Entry point: parse the flags and run against ``$DATABASE_URL``."""
    parser = argparse.ArgumentParser(
        description="Delete old full-text snapshots that no task links to (task 057 D3)."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="count what would be deleted and change nothing (the default)",
    )
    mode.add_argument("--apply", dest="apply", action="store_true", help="delete")
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--older-than-days",
        type=int,
        default=DEFAULT_OLDER_THAN_DAYS,
        help=f"only snapshots older than this many days (default {DEFAULT_OLDER_THAN_DAYS})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"snapshots per committed batch (default {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    engine = create_engine(make_url(os.environ.get("DATABASE_URL", _DEV_URL)))
    try:
        return run(
            engine,
            older_than_days=args.older_than_days,
            batch_size=args.batch_size,
            apply=args.apply,
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
