"""task 057 rev2 — fill the new embedding and word columns for existing rows

The second of task 057's migrations (contract D2; plan P5 and P14). Data only: it
changes no table definition. For every ``chunk_embedding`` row that the code
before task 057 wrote, it fills the two columns revision ``a3d8f6c1e2b4`` added:

``embedding``
    The same numbers as the JSON column ``vector``, converted to pgvector's
    binary form (single precision, float32) by the database:
    ``(vector::text)::vector(1536)``.
``tokens``
    The distinct words of the unit's text, sorted. The unit's text is the part of
    the chunk the row's ``unit_locator`` points at: ``{"start": s, "end": e}`` are
    character positions in ``chunk.content``, so the text is
    ``substr(content, s + 1, e - s)`` (SQL counts from 1, Python from 0). A word
    is a run of ASCII letters and digits (``[0-9A-Za-z]+``) found in that text,
    then lower-cased: the rule in ``policy_atlas.core.tokens``, which the
    retriever and the embedding writer use. A test runs ``TOKENS_SQL`` below
    against that function on a fixed set of strings.

How it runs
    Outside a transaction, in batches of 2,000 rows taken in primary-key order.
    Each batch is one ``UPDATE`` that commits on its own, so the app keeps
    serving while it runs (it only ever touches rows the app does not change),
    and a crash loses at most the batch in flight.

How long
    About 2,000 rows per batch. On the dev database it takes a few minutes. On
    the production writer, whose table is several times larger, expect tens of
    minutes. For this release the operator runs it *before* the deploy, while the
    service is up (``infra/DEPLOYMENT.md`` § 4, task 057 pre-run), so the deploy
    finds it already applied.

How to resume
    Run ``alembic upgrade`` again (to this revision or to head). Only rows whose
    ``embedding`` is still empty are picked up, so the rerun finishes the rest and
    redoes nothing. After its first pass it checks for rows the app wrote behind
    it (code from before task 057 writes only the JSON column) and passes again.

Downgrade
    Does nothing: the columns this fills are dropped by revision
    ``a3d8f6c1e2b4``'s downgrade.

Revision ID: b7e2c4a9d1f3
Revises: a3d8f6c1e2b4
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

revision: str = "b7e2c4a9d1f3"
down_revision: str | None = "a3d8f6c1e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

log = logging.getLogger("alembic.runtime.migration")

BATCH_SIZE = 2000
#: How many times the loop goes back to the start for rows written behind it.
MAX_PASSES = 10

# Frozen here, not imported: the migration must keep doing what it did at this
# revision, whatever the product code says later. ``{unit}`` is the SQL for the
# unit's text. Match on the original text, then lower-case each (ASCII) match;
# COLLATE "C" makes lower() and the sort ignore the database's language setting.
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

BatchFn = Callable[..., tuple[int, uuid.UUID | None]]


def backfill_batch(
    conn: Connection, *, after: uuid.UUID, limit: int
) -> tuple[int, uuid.UUID | None]:
    """Fill the next batch of empty rows after ``after`` in primary-key order.

    Args:
        conn: A connection in autocommit mode, so the batch commits on its own.
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
    """Fill every empty row, batch by batch, and return how many were filled.

    Each pass walks the table once in primary-key order. A pass that leaves rows
    behind it (written by older code while it ran) is followed by another, up to
    ``max_passes``.

    Args:
        conn: A connection in autocommit mode.
        batch_size: Rows per batch.
        batch_fn: The function that fills one batch (a test can wrap it).
        max_passes: The most passes before giving up; leftovers are filled by the
            next run.

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
                    "chunk_embedding backfill: pass %d, %d rows filled, %.0f s",
                    pass_number,
                    total,
                    time.monotonic() - started,
                )
        if not conn.execute(text(_REMAINING_SQL)).scalar_one():
            break
    log.info(
        "chunk_embedding backfill: done, %d rows filled in %.0f s",
        total,
        time.monotonic() - started,
    )
    return total


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("revision b7e2c4a9d1f3 fills rows in batches and must run online")
    with op.get_context().autocommit_block():
        run_backfill(op.get_bind())


def downgrade() -> None:
    # Nothing to undo: revision a3d8f6c1e2b4's downgrade drops the filled columns.
    pass
