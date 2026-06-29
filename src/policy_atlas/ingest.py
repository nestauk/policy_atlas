"""Upload-ingest: create source_snapshot + chunks + corpus membership in one call."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Connection

from policy_atlas.grounding import content_hash
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import project_source_snapshot, source_snapshot


def ingest_upload(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    chunks: list[str],
    source_locator: str,
    metadata: dict[str, Any],
    text_basis: str,
) -> uuid.UUID:
    """Ingest an uploaded source into the project corpus.

    Creates source_snapshot, chunk, and project_source_snapshot rows.
    Each call creates a new snapshot regardless of content hash — per spec,
    a corrected re-upload is a new snapshot; silent dedup would hide that intent.

    Args:
        conn: Open database connection.
        project_id: Project to ingest into.
        chunks: Pre-parsed text chunks in sequence order (1-indexed).
        source_locator: Filename or user-assigned ref for this upload.
        metadata: Arbitrary metadata (stored as JSONB).
        text_basis: ``"full_text"`` or ``"abstract_only"``.

    Returns:
        The new ``source_snapshot_id`` UUID.
    """
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
        project_source_snapshot.insert().values(
            project_source_snapshot_id=uuid.uuid4(),
            project_id=project_id,
            source_snapshot_id=snapshot_id,
            origin="uploaded",
            run_id=None,
            ingested_at=now,
        )
    )

    return snapshot_id
