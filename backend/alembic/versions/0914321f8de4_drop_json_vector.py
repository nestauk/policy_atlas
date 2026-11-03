"""task 057 rev3 — drop the old JSON embedding column

The third of task 057's migrations (contract D2, "second migration step"; plan P5).
From this release the code reads and writes embeddings only in the binary column
``chunk_embedding.embedding`` (pgvector, added by revision ``a3d8f6c1e2b4`` and
filled by revision ``b7e2c4a9d1f3``). The old copy of the same numbers, the JSON
column ``chunk_embedding.vector``, is no longer used, so this revision removes it.

What it does, in order
    1. **Fills any row that is still empty.** Rows the old service wrote after the
       operator's pre-deploy run of ``b7e2c4a9d1f3`` hold their numbers only in the
       JSON column. This step runs the same fill as ``b7e2c4a9d1f3`` (copied into
       this file, not imported: a migration must keep doing what it did when it was
       written), in committed batches of 2,000 rows, outside a transaction.
    2. **Checks, then drops, in one short transaction.** It locks the table (waiting
       at most 10 seconds for the lock), fills any row written in the meantime,
       counts the rows that still have no ``embedding`` and stops with an error if
       there are any. Otherwise it drops the JSON column. Because the check and the
       drop share one transaction and the lock, no row can slip in between them.

How long
    Step 1 takes seconds when the pre-run was done (``infra/DEPLOYMENT.md`` § 4,
    task 057 pre-run): only the few rows written since are left. Without the
    pre-run it does the whole fill, tens of minutes on the production writer.
    Step 2 takes seconds; dropping a column does not rewrite the table.

If it stops with an error
    The message gives two counts:

    * rows that still have a JSON list of numbers but no ``embedding``: the fill
      did not reach them (for example the old service kept writing while it ran).
      Run ``alembic upgrade`` again; it resumes and fills them.
    * rows with no usable JSON (SQL ``NULL``, JSON ``null`` or anything that is not
      a list) and no ``embedding``: nothing can be copied for them. Delete them
      (the next run embeds their chunk again) or fix them, then run again.

    Nothing is dropped when it stops, and every batch already filled stays filled.
    If the 10-second lock wait runs out (a long query was using the table), just
    run it again.

Downgrade
    Adds the JSON column back, rebuilds it from ``embedding`` and makes it
    ``NOT NULL`` again. The rebuilt numbers are pgvector's single precision
    (float32) values, so they are close to, not exactly, what the provider
    returned. One transaction; on the production table expect minutes.

Revision ID: 0914321f8de4
Revises: b7e2c4a9d1f3
Create Date: 2026-11-03 00:00:00.000000

"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Sequence

from alembic import op
from sqlalchemy import text
from sqlalchemy.engine import Connection

revision: str = "0914321f8de4"
down_revision: str | None = "b7e2c4a9d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")

BATCH_SIZE = 2000
#: How many times the loop goes back to the start for rows written behind it.
MAX_PASSES = 10

# --- Frozen copy of revision b7e2c4a9d1f3's fill (do not import it) -----------------
# ``{unit}`` is the SQL for the unit's text. Match on the original text, then
# lower-case each (ASCII) match; COLLATE "C" makes lower() and the sort ignore the
# database's language setting. The same rule as ``policy_atlas.core.tokens``.
TOKENS_SQL = (
    'ARRAY(SELECT DISTINCT lower(m[1] COLLATE "C") '
    "FROM regexp_matches({unit}, '[0-9A-Za-z]+', 'g') AS m ORDER BY 1)"
)
UNIT_TEXT_SQL = (
    "substr(c.content, (ce.unit_locator->>'start')::int + 1, "
    "(ce.unit_locator->>'end')::int - (ce.unit_locator->>'start')::int)"
)

_BATCH_SQL = f"""
WITH batch AS (
    SELECT chunk_embedding_id
    FROM chunk_embedding
    WHERE embedding IS NULL AND jsonb_typeof(vector) = 'array' AND chunk_embedding_id > :after
    ORDER BY chunk_embedding_id
    LIMIT :limit
), filled AS (
    UPDATE chunk_embedding AS ce
    SET embedding = (ce.vector::text)::vector(1536),
        tokens = {TOKENS_SQL.format(unit=UNIT_TEXT_SQL)}
    FROM batch AS b, chunk AS c
    WHERE ce.chunk_embedding_id = b.chunk_embedding_id AND c.chunk_id = ce.chunk_id
    RETURNING ce.chunk_embedding_id
)
SELECT
    (SELECT count(*) FROM filled) AS filled,
    (SELECT chunk_embedding_id FROM batch ORDER BY chunk_embedding_id DESC LIMIT 1) AS last_id
"""

_REMAINING_SQL = (
    "SELECT EXISTS (SELECT 1 FROM chunk_embedding "
    "WHERE embedding IS NULL AND jsonb_typeof(vector) = 'array')"
)
# --- End of the frozen copy ----------------------------------------------------------

# Rows with no binary embedding, split by whether the JSON could still fill them.
_MISSING_SQL = """
SELECT
    count(*) FILTER (WHERE jsonb_typeof(vector) = 'array') AS unfilled,
    count(*) FILTER (WHERE vector IS NULL OR jsonb_typeof(vector) <> 'array') AS unfillable
FROM chunk_embedding
WHERE embedding IS NULL
"""

BatchFn = Callable[..., tuple[int, uuid.UUID | None]]


def backfill_batch(
    conn: Connection, *, after: uuid.UUID, limit: int
) -> tuple[int, uuid.UUID | None]:
    """Fill the next batch of empty rows after ``after`` in primary-key order.

    Args:
        conn: A connection; in autocommit mode the batch commits on its own.
        after: Only rows whose primary key sorts after this one are taken.
        limit: The batch size.

    Returns:
        The number of rows filled and the last primary key the batch took, or
        ``None`` when no empty row is left after ``after``.
    """
    row = conn.execute(text(_BATCH_SQL), {"after": after, "limit": limit}).one()
    return int(row.filled), row.last_id


def run_backfill(
    conn: Connection,
    *,
    batch_size: int = BATCH_SIZE,
    batch_fn: BatchFn = backfill_batch,
    max_passes: int = MAX_PASSES,
) -> int:
    """Fill every empty row that has a JSON vector, batch by batch.

    Each pass walks the table once in primary-key order. A pass that leaves rows
    behind it (written by older code while it ran) is followed by another, up to
    ``max_passes``.

    Args:
        conn: A connection; in autocommit mode each batch commits on its own.
        batch_size: Rows per batch.
        batch_fn: The function that fills one batch (a test can wrap it).
        max_passes: The most passes before giving up; the check that follows
            reports any leftovers.

    Returns:
        The number of rows filled.
    """
    started = time.monotonic()
    total = 0
    for pass_number in range(1, max_passes + 1):
        after = uuid.UUID(int=0)
        batches = 0
        while True:
            filled, last_id = batch_fn(conn, after=after, limit=batch_size)
            if last_id is None:
                break
            total += filled
            after = last_id
            batches += 1
            if batches % 25 == 0:
                log.info(
                    "chunk_embedding fill before the drop: pass %d, %d rows filled, %.0f s",
                    pass_number,
                    total,
                    time.monotonic() - started,
                )
        if not conn.execute(text(_REMAINING_SQL)).scalar_one():
            break
    log.info(
        "chunk_embedding fill before the drop: done, %d rows filled in %.0f s",
        total,
        time.monotonic() - started,
    )
    return total


def check_no_row_is_missing(conn: Connection) -> None:
    """Stop the migration if any row still has no binary embedding.

    Args:
        conn: A connection inside the transaction that will drop the column.

    Raises:
        RuntimeError: If any row has ``embedding IS NULL``; the message counts
            the rows a rerun can fill and the rows it cannot.
    """
    row = conn.execute(text(_MISSING_SQL)).one()
    unfilled, unfillable = int(row.unfilled), int(row.unfillable)
    if unfilled or unfillable:
        raise RuntimeError(
            "revision 0914321f8de4 will not drop chunk_embedding.vector: "
            f"{unfilled + unfillable} rows have no embedding. "
            f"{unfilled} still have a JSON vector the fill did not reach "
            "(run the upgrade again; it resumes). "
            f"{unfillable} have a JSON null, SQL NULL or non-array vector and no "
            "embedding, so nothing can be copied (delete or fix those rows, then run "
            "the upgrade again). Nothing was dropped."
        )


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("revision 0914321f8de4 fills rows in batches and must run online")
    # Step 1, outside a transaction: the bulk of any fill, one committed batch at a time.
    with op.get_context().autocommit_block():
        run_backfill(op.get_bind())
    # Step 2, one transaction (with the version stamp): lock, fill stragglers, check, drop.
    conn = op.get_bind()
    op.execute("SET LOCAL lock_timeout = '10s'")
    op.execute("LOCK TABLE chunk_embedding IN ACCESS EXCLUSIVE MODE")
    run_backfill(conn, max_passes=1)
    check_no_row_is_missing(conn)
    op.execute("ALTER TABLE chunk_embedding DROP COLUMN IF EXISTS vector")


def downgrade() -> None:
    op.execute("ALTER TABLE chunk_embedding ADD COLUMN IF NOT EXISTS vector jsonb")
    # The same rebuild as revision a3d8f6c1e2b4's downgrade (float32, approximate).
    op.execute(
        "UPDATE chunk_embedding SET vector = to_jsonb(embedding::real[]) "
        "WHERE (vector IS NULL OR jsonb_typeof(vector) = 'null') AND embedding IS NOT NULL"
    )
    op.execute("ALTER TABLE chunk_embedding ALTER COLUMN vector SET NOT NULL")
