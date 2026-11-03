"""task 057 rev1 — document store: new columns, the queued status, the pgvector column

The first of task 057's migrations (contract D2; plan P5). It only *adds* things,
so the app keeps working while it runs and the code before and after it can both
serve on the result. Nothing is removed and no table is rewritten.

What it adds
    ``source_snapshot.body_hash``, ``parse_profile``, ``segmentation_policy``
        Three nullable text columns: the document-store key (contract § Terms).
        ``parse_profile`` and ``segmentation_policy`` are copied from each
        full-text snapshot's ``metadata`` JSON (the keys ``parse_profile`` and
        ``segmentation_policy`` that the full-text ingest writes). ``body_hash``
        (a SHA-256 fingerprint of the downloaded file) stays empty on existing
        rows: their downloaded bytes were never kept, so they are never matched
        by key.
    ``uq_source_snapshot_store_key``
        A unique index on those three columns for rows that have a body hash, so
        the same file parsed the same way is stored once.
    ``task_source_snapshot.ingested_by_run_id`` (uuid), ``fetched_from`` (text)
        Two nullable columns: the per-task notes (which run read the document,
        from which address) that will move off the shared snapshot row.
    ``queued`` in ``ck_tss_full_text_status``
        A document handed to the ingest queue and not finished yet. The two
        consistency checks are unchanged and already right for it: a queued row
        has no full-text snapshot and no error.
    The ``vector`` extension (pgvector)
        A PostgreSQL add-on that stores embeddings (lists of 1,536 numbers) in a
        compact binary form and compares them inside the database.
    ``chunk_embedding.embedding vector(1536)`` and ``tokens text[]``
        The embedding in pgvector's binary form and the unit's words, both
        nullable and empty until revision ``b7e2c4a9d1f3`` fills them. The JSON
        column ``vector`` becomes nullable so later code can stop writing it.
    ``ix_chunk_embedding_tokens``
        A GIN index (an index that finds rows whose list contains a given word)
        on ``tokens``.

Online-safe and rerun-safe
    Every statement is ``IF NOT EXISTS`` or otherwise safe to run twice, so an
    interrupted run is finished by running it again. The column changes take a
    brief exclusive lock each; ``lock_timeout`` makes them give up after 10 s
    rather than queue the app behind them (rerun if that happens). The new check
    is added ``NOT VALID`` and validated after the commit, the metadata copy runs
    as its own statement after the commit, and both indexes are built
    ``CONCURRENTLY`` (without blocking writes) outside a transaction; an index
    left half-built by a crash is dropped and rebuilt on the rerun.

How long
    Seconds on the dev database. On production the two index builds read the
    whole ``chunk_embedding`` and ``source_snapshot`` tables, a few minutes at
    most; the slow part of the release is the next revision's backfill.

Downgrade
    Drops the two indexes and every column above, puts any ``queued`` row back to
    ``not_attempted`` (consistent with the old checks: no snapshot, no error) and
    restores the old status check. Before it makes ``chunk_embedding.vector`` NOT
    NULL again it rebuilds the JSON for any row that only has the binary column
    (at float32 precision, so approximate). The two link-row columns are lost.
    The ``vector`` extension is left installed: other database objects may use
    it and it is harmless when unused.

Revision ID: a3d8f6c1e2b4
Revises: 152a234e2391
Create Date: 2026-11-03 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "a3d8f6c1e2b4"
down_revision: str | None = "152a234e2391"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen here, not imported: the checks must keep meaning what they meant at this
# revision, whatever ``schema.py`` says later.
_STATUS_WITH_QUEUED = (
    "full_text_status IN ('not_attempted', 'queued', 'ingested', 'fetch_failed', 'parse_failed')"
)
_STATUS_BEFORE = "full_text_status IN ('not_attempted', 'ingested', 'fetch_failed', 'parse_failed')"

_INDEXES = {
    "uq_source_snapshot_store_key": (
        "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS uq_source_snapshot_store_key "
        "ON source_snapshot (body_hash, parse_profile, segmentation_policy) "
        "WHERE body_hash IS NOT NULL"
    ),
    "ix_chunk_embedding_tokens": (
        "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_chunk_embedding_tokens "
        "ON chunk_embedding USING gin (tokens)"
    ),
}


def upgrade() -> None:
    # Part 1, one short transaction: catalogue changes only, no table rewrite.
    op.execute("SET LOCAL lock_timeout = '10s'")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        "ALTER TABLE source_snapshot "
        "ADD COLUMN IF NOT EXISTS body_hash text, "
        "ADD COLUMN IF NOT EXISTS parse_profile text, "
        "ADD COLUMN IF NOT EXISTS segmentation_policy text"
    )
    op.execute(
        "ALTER TABLE task_source_snapshot "
        "ADD COLUMN IF NOT EXISTS ingested_by_run_id uuid, "
        "ADD COLUMN IF NOT EXISTS fetched_from text, "
        "DROP CONSTRAINT IF EXISTS ck_tss_full_text_status, "
        f"ADD CONSTRAINT ck_tss_full_text_status CHECK ({_STATUS_WITH_QUEUED}) NOT VALID"
    )
    op.execute(
        "ALTER TABLE chunk_embedding "
        "ADD COLUMN IF NOT EXISTS embedding vector(1536), "
        "ADD COLUMN IF NOT EXISTS tokens text[], "
        "ALTER COLUMN vector DROP NOT NULL"
    )

    # Part 2, outside a transaction: each statement commits on its own, and none
    # blocks the app's reads or writes for long.
    with op.get_context().autocommit_block():
        # task 057 review: Codex 13 - SET LOCAL ended with part 1's commit, so set
        # the timeout for the session here and reset it when the block ends. A
        # CONCURRENTLY build that hits it leaves an invalid index, which the
        # rerun drops and rebuilds (below).
        op.execute("SET lock_timeout = '10s'")
        # Checking existing rows against the new rule takes only a light lock.
        op.execute("ALTER TABLE task_source_snapshot VALIDATE CONSTRAINT ck_tss_full_text_status")
        # Snapshots are written once and never updated, so this touches no live row.
        op.execute(
            "UPDATE source_snapshot "
            "SET parse_profile = metadata->>'parse_profile', "
            "segmentation_policy = metadata->>'segmentation_policy' "
            "WHERE text_basis = 'full_text' AND parse_profile IS NULL "
            "AND segmentation_policy IS NULL "
            "AND (metadata ? 'parse_profile' OR metadata ? 'segmentation_policy')"
        )
        conn = op.get_bind()
        for name, create_sql in _INDEXES.items():
            # A crashed CONCURRENTLY build leaves an INVALID index behind, which
            # IF NOT EXISTS would then skip: drop it first so the rerun rebuilds it.
            invalid = conn.execute(
                text(
                    "SELECT 1 FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                    "WHERE c.relname = :name AND NOT i.indisvalid"
                ),
                {"name": name},
            ).first()
            if invalid is not None:
                op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS {name}")
            op.execute(create_sql)
        op.execute("RESET lock_timeout")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunk_embedding_tokens")
    op.execute("DROP INDEX IF EXISTS uq_source_snapshot_store_key")
    # Rows only the binary column holds get their JSON back (float32, approximate).
    op.execute(
        "UPDATE chunk_embedding SET vector = to_jsonb(embedding::real[]) "
        "WHERE (vector IS NULL OR jsonb_typeof(vector) = 'null') AND embedding IS NOT NULL"
    )
    op.execute(
        "ALTER TABLE chunk_embedding "
        "DROP COLUMN IF EXISTS embedding, "
        "DROP COLUMN IF EXISTS tokens, "
        "ALTER COLUMN vector SET NOT NULL"
    )
    # The old check has no 'queued'; such a row has no snapshot and no error,
    # which is exactly a 'not_attempted' row.
    op.execute(
        "UPDATE task_source_snapshot SET full_text_status = 'not_attempted' "
        "WHERE full_text_status = 'queued'"
    )
    op.execute(
        "ALTER TABLE task_source_snapshot "
        "DROP CONSTRAINT IF EXISTS ck_tss_full_text_status, "
        f"ADD CONSTRAINT ck_tss_full_text_status CHECK ({_STATUS_BEFORE}), "
        "DROP COLUMN IF EXISTS ingested_by_run_id, "
        "DROP COLUMN IF EXISTS fetched_from"
    )
    op.execute(
        "ALTER TABLE source_snapshot "
        "DROP COLUMN IF EXISTS body_hash, "
        "DROP COLUMN IF EXISTS parse_profile, "
        "DROP COLUMN IF EXISTS segmentation_policy"
    )
