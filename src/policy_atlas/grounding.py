"""produce_grounded_block — deterministic leg only.

Pipeline: synthesise (stub) → cite → verify (verbatim quote-presence) → write.
The LLM-as-judge grounding classifier is a deferred seam.

Fabricated quote → GroundingError raised; annotation records verification_result="fail".
Flag, don't drop — never promoted to a clean tier.
"""

import hashlib
import unicodedata
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.inference import InferenceProvider
from policy_atlas.schema import addressable_unit, annotation, block
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import citation as citation_table


class GroundingError(Exception):
    """Raised when quote-presence verification fails; carries persisted block_id for audit."""

    def __init__(self, message: str, block_id: uuid.UUID | None = None) -> None:
        """Initialise the error.

        Args:
            message: Human-readable failure description.
            block_id: ID of the block persisted before verification failed, if any.
        """
        super().__init__(message)
        self.block_id = block_id


def _normalize(text: str) -> str:
    """NFC + collapse whitespace — used for both quote and source chunks."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def content_hash(content: str) -> str:
    """Return the SHA-256 hex digest of normalised content.

    Args:
        content: Text to hash.

    Returns:
        Hex-encoded SHA-256 of the NFC-normalised, whitespace-collapsed content.
    """
    return hashlib.sha256(_normalize(content).encode()).hexdigest()


def quote_present(quote: str, chunks: tuple[str, ...]) -> bool:
    """Check whether a quote appears verbatim across the source chunks.

    Concatenation prevents a boundary-spanning quote from being a spurious miss.

    Args:
        quote: Candidate quote text.
        chunks: Source chunks, matched against their concatenation.

    Returns:
        True if the normalised quote is a substring of the normalised chunks.
    """
    return _normalize(quote) in _normalize("".join(chunks))


def produce_grounded_block(
    conn: Connection,
    *,
    artefact_id: uuid.UUID,
    source_snapshot_id: uuid.UUID,
    provider: InferenceProvider,
) -> dict[str, Any]:
    """Synthesise → cite → verify → write one block, unit and citation annotation.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        artefact_id: Artefact the new block belongs to.
        source_snapshot_id: DB-persisted source snapshot to ground against.
        provider: Inference provider supplying the synthesised text.

    Returns:
        Persisted IDs: ``block_id``, ``unit_id``, ``annotation_id``, ``citation_id``.

    Raises:
        ValueError: If no chunks are found for ``source_snapshot_id``.
        GroundingError: If the quote is not present in the source chunks. The
            failing block is still persisted and its annotation records
            ``verification_result="fail"``.
    """
    rows = conn.execute(
        select(chunk_table.c.chunk_id, chunk_table.c.content)
        .where(chunk_table.c.source_snapshot_id == source_snapshot_id)
        .order_by(chunk_table.c.sequence)
    ).fetchall()

    if not rows:
        raise ValueError(f"No chunks found for source_snapshot_id={source_snapshot_id!r}")

    chunk_texts: tuple[str, ...] = tuple(r.content for r in rows)

    # Synthesise (stub — calls the inference seam, zero egress)
    synthesised = provider.complete(f"synthesise from source_snapshot_id={source_snapshot_id}")

    # Cite: the verbatim quote is the synthesised text itself (stub co-emits claim + citation)
    quote = synthesised

    # Verify: deterministic quote-presence check
    present = quote_present(quote, chunk_texts)

    block_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    annotation_id = uuid.uuid4()
    citation_id = uuid.uuid4()
    now = datetime.now(UTC)

    # Write block
    conn.execute(
        block.insert().values(
            block_id=block_id,
            artefact_id=artefact_id,
            version=1,
            content=synthesised,
            content_hash=content_hash(synthesised),
            created_at=now,
        )
    )

    # Write addressable unit (text_span covering the full block content)
    conn.execute(
        addressable_unit.insert().values(
            unit_id=unit_id,
            block_id=block_id,
            unit_type="text_span",
            locator={"start": 0, "end": len(synthesised)},
            content=synthesised,
            created_at=now,
        )
    )

    # Write citation annotation — always written, verification_result captures outcome
    verification_result = "pass" if present else "fail"
    conn.execute(
        annotation.insert().values(
            annotation_id=annotation_id,
            block_id=block_id,
            unit_id=unit_id,
            annotation_type="citation",
            payload={"quote": quote, "verification_result": verification_result},
            created_at=now,
        )
    )

    # Find the chunk whose content contains the normalised quote; fall back to first chunk.
    # ponytail: boundary-spanning quote uses first-chunk fallback; replace with citation_chunk
    # join table when real provider lands (see docs/deferred.md and contract §Boundary-spanning).
    norm_quote = _normalize(quote)
    citing_chunk_id = next(
        (r.chunk_id for r in rows if norm_quote in _normalize(r.content)),
        rows[0].chunk_id,
    )

    conn.execute(
        citation_table.insert().values(
            citation_id=citation_id,
            annotation_id=annotation_id,
            chunk_id=citing_chunk_id,
            quote=quote,
            verification_result=verification_result,
            created_at=now,
        )
    )

    if not present:
        raise GroundingError(
            f"Quote-presence verification failed for source_snapshot_id={source_snapshot_id!r}. "
            "Fabricated quote recorded on annotation and citation; not promoted to a clean tier.",
            block_id=block_id,
        )

    return {
        "block_id": block_id,
        "unit_id": unit_id,
        "annotation_id": annotation_id,
        "citation_id": citation_id,
    }
