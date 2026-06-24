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

from sqlalchemy.engine import Connection

from policy_atlas.fixtures import get_source
from policy_atlas.inference import InferenceProvider
from policy_atlas.schema import addressable_unit, annotation, block


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

    Summary is trivially excluded (not a column this slice).

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
    source_ref: str,
    provider: InferenceProvider,
) -> dict[str, Any]:
    """Synthesise → cite → verify → write one block, unit and citation annotation.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        artefact_id: Artefact the new block belongs to.
        source_ref: Synthetic source to ground against.
        provider: Inference provider supplying the synthesised text.

    Returns:
        Persisted IDs: ``block_id``, ``unit_id`` and ``annotation_id``.

    Raises:
        GroundingError: If the quote is not present in the source chunks. The
            failing block is still persisted and its annotation records
            ``verification_result="fail"``.
    """
    source = get_source(source_ref)

    # Synthesise (stub — calls the inference seam, zero egress)
    synthesised = provider.complete(f"synthesise from {source_ref}")

    # Cite: the verbatim quote is the synthesised text itself (stub co-emits claim + citation)
    quote = synthesised

    # Verify: deterministic quote-presence check
    present = quote_present(quote, source.chunks)

    block_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    annotation_id = uuid.uuid4()
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
            payload={
                "source_ref": source_ref,
                "quote": quote,
                "verification_result": verification_result,
            },
            created_at=now,
        )
    )

    if not present:
        raise GroundingError(
            f"Quote-presence verification failed for source_ref={source_ref!r}. "
            "Fabricated quote recorded on annotation; not promoted to a clean tier.",
            block_id=block_id,
        )

    return {"block_id": block_id, "unit_id": unit_id, "annotation_id": annotation_id}
