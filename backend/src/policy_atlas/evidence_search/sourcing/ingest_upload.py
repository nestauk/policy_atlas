"""Upload-ingest: create source_snapshot + chunks + corpus membership in one call."""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import (
    EmbeddingBackend,
    StubEmbeddingBackend,
    embed_pending_chunks,
)
from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import source_snapshot, task_source_snapshot

log = structlog.get_logger()


def ingest_upload(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    chunks: list[str],
    source_locator: str,
    metadata: dict[str, Any],
    text_basis: str,
    embedder: EmbeddingBackend | None = None,
) -> uuid.UUID:
    """Ingest an uploaded source into the task corpus.

    Creates source_snapshot, chunk, and task_source_snapshot rows.
    Each call creates a new snapshot regardless of content hash — per spec,
    a corrected re-upload is a new snapshot; silent dedup would hide that intent.

    Args:
        conn: Open database connection.
        task_id: Task to ingest into.
        chunks: Pre-parsed text chunks in sequence order (1-indexed).
        source_locator: Filename or user-assigned ref for this upload.
        metadata: Arbitrary metadata (stored as JSONB).
        text_basis: ``"full_text"`` or ``"abstract_only"``.
        embedder: Optional embedding backend. Defaults to the deterministic stub.

    Returns:
        The new ``source_snapshot_id`` UUID.
    """
    if embedder is None:
        embedder = StubEmbeddingBackend()

    snapshot_id = uuid.uuid4()
    now = datetime.now(UTC)

    conn.execute(
        source_snapshot.insert().values(
            source_snapshot_id=snapshot_id,
            content_hash=content_hash("".join(chunks)),
            text_basis=text_basis,
            source_locator=source_locator,
            metadata=metadata,
            created_at=now,
        )
    )

    for i, text in enumerate(chunks):
        conn.execute(
            chunk_table.insert().values(
                chunk_id=uuid.uuid4(),
                source_snapshot_id=snapshot_id,
                sequence=i + 1,
                content=text,
                content_hash=content_hash(text),
                locator={"sequence": i + 1},
                segmentation_policy="manual_v1",
                created_at=now,
            )
        )

    conn.execute(
        task_source_snapshot.insert().values(
            task_source_snapshot_id=uuid.uuid4(),
            task_id=task_id,
            source_snapshot_id=snapshot_id,
            origin="uploaded",
            run_id=None,
            ingested_at=now,
        )
    )
    counts = embed_pending_chunks(
        conn,
        embedder=embedder,
        task_id=task_id,
        # upload ingest runs outside any run; nil UUID marks that in embed logs (finding 3)
        run_id=uuid.UUID(int=0),
    )
    log.info("ingest_upload.embed_counts", **counts)

    return snapshot_id
