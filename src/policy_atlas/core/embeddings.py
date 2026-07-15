"""Embedding backends and unit-grain chunk vectorisation for task 009.

This module owns the first runtime-egress embedding seam. The defaultable stub is
deterministic and zero-egress; the live backend is explicit and env-keyed. The
embed pass is project-scoped through ``project_source_snapshot`` because chunks
and snapshots are corpus-global, not project-owned.
"""

from __future__ import annotations

import hashlib
import math
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol, TypedDict

import structlog
from openai import RateLimitError
from sqlalchemy import exists, func, select, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.core.openai_client import resolve_openai_client
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import chunk_embedding, project_source_snapshot

log = structlog.get_logger()

EMBEDDING_PROFILE = "openai_text_embedding_3_small_v1"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

UNIT_POLICY = "embedding_unit_policy_v1"
UNIT_CHAR_BUDGET = 2000
UNIT_CHAR_OVERLAP = 200

API_BATCH_SIZE = 128
DEFAULT_MAX_CHUNKS = 20_000
EMBEDDING_RATE_LIMIT_BACKOFF_BASE_S = 2.0
EMBEDDING_RATE_LIMIT_BACKOFF_CAP_S = 60.0
EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS = 4

_UINT32_MAX = float((2**32) - 1)
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_BOUNDARY_RE = re.compile(r"\n\n")
_sleep = time.sleep


class _UnitDict(TypedDict):
    unit_index: int
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class _PendingChunk:
    chunk_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    sequence: int
    content: str


@dataclass(frozen=True)
class _UnitWork:
    chunk_id: uuid.UUID
    unit_index: int
    start: int
    end: int
    text: str


@dataclass
class _ChunkState:
    units: list[_UnitWork]
    vectors: dict[int, list[float]] = field(default_factory=dict)
    failed: bool = False
    inserted: bool = False


class EmbeddingBackend(Protocol):
    """The embedding seam, implemented by live and deterministic backends."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so tracing wrappers can proxy it."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in input order.

        Args:
            texts: Text units to embed.

        Returns:
            One vector per input text, in the same order.
        """
        ...


def _hash_vector(text: str) -> list[float]:
    vector: list[float] = []
    block_index = 0
    while len(vector) < EMBEDDING_DIMENSIONS:
        digest = hashlib.sha256(f"{text}:{block_index}".encode()).digest()
        for offset in range(0, len(digest), 4):
            value = int.from_bytes(digest[offset:offset + 4], "big")
            vector.append((float(value) / _UINT32_MAX) * 2.0 - 1.0)
            if len(vector) == EMBEDDING_DIMENSIONS:
                break
        block_index += 1
    return vector


class StubEmbeddingBackend:
    """Deterministic zero-egress embedding backend for tests and local runs."""

    mode = "stub"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Return deterministic hash-derived vectors.

        Args:
            texts: Text units to embed.

        Returns:
            One 1536-dimensional vector per input text.
        """
        return [_hash_vector(text) for text in texts]


class OpenAIEmbeddingBackend:
    """Live OpenAI embedding backend.

    Args:
        api_key: Optional OpenAI API key. If omitted, ``OPENAI_API_KEY`` is read
            from the environment.

    Raises:
        RuntimeError: If no API key is provided or configured.
    """

    mode = "live"

    def __init__(self, api_key: str | None = None) -> None:
        # The SDK may spend up to 1 + max_retries HTTP attempts per logical
        # create call; the explicit 429 loop below budgets logical calls.
        self._client = resolve_openai_client(
            api_key, backend_name="OpenAIEmbeddingBackend", timeout=30.0, max_retries=2
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts through OpenAI's embeddings API.

        Args:
            texts: Text units to embed.

        Returns:
            One 1536-dimensional vector per input text, in input order.

        Raises:
            RateLimitError: If all logical attempts are exhausted on provider
                rate limits. With SDK ``max_retries=2``, the HTTP ceiling is
                ``3 * EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS`` attempts.
            RuntimeError: If the provider returns a different number of vectors.
        """
        if not texts:
            return []

        log.info("embedding.openai.request", text_count=len(texts))
        response = self._create_embeddings_with_backoff(texts)
        items = sorted(response.data, key=lambda item: item.index)
        vectors = [list(item.embedding) for item in items]
        log.info("embedding.openai.response", text_count=len(texts), vector_count=len(vectors))
        if len(vectors) != len(texts):
            raise RuntimeError("OpenAI embeddings response length did not match input length.")
        return vectors

    def _create_embeddings_with_backoff(self, texts: list[str]) -> Any:
        for attempt in range(EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS):
            try:
                return self._client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=texts,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
            except RateLimitError:
                if attempt == EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS - 1:
                    raise
                delay_s = _embedding_rate_limit_delay_s(attempt)
                log.warning(
                    "embedding.openai_rate_limited",
                    attempt=attempt + 1,
                    max_attempts=EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS,
                    sleep_s=delay_s,
                )
                _sleep(delay_s)

        raise RuntimeError("unreachable embedding retry state")


def _embedding_rate_limit_delay_s(attempt: int) -> float:
    base_s = float(min(
        EMBEDDING_RATE_LIMIT_BACKOFF_BASE_S * (2**attempt),
        EMBEDDING_RATE_LIMIT_BACKOFF_CAP_S,
    ))
    return float(base_s + random.uniform(0.0, base_s))


def _rightmost_boundary(boundaries: list[int], *, min_end: int, limit: int) -> int | None:
    chosen: int | None = None
    for boundary in boundaries:
        if boundary < min_end:
            continue
        if boundary > limit:
            break
        chosen = boundary
    return chosen


def _choose_unit_end(
    *,
    start: int,
    effective_end: int,
    sentence_boundaries: list[int],
    paragraph_boundaries: list[int],
) -> int:
    limit = min(start + UNIT_CHAR_BUDGET, effective_end)
    if limit >= effective_end:
        return effective_end

    # Exclude the previous unit's overlap boundary. Otherwise the next unit can
    # repeatedly end where the previous unit ended, creating tiny non-progressing
    # units when a long sentence follows a boundary.
    min_boundary_end = min(start + UNIT_CHAR_OVERLAP + 1, limit)
    sentence_end = _rightmost_boundary(
        sentence_boundaries, min_end=min_boundary_end, limit=limit
    )
    if sentence_end is not None:
        return sentence_end
    paragraph_end = _rightmost_boundary(
        paragraph_boundaries, min_end=min_boundary_end, limit=limit
    )
    if paragraph_end is not None:
        return paragraph_end
    return limit


def _overlap_start(content: str, *, unit_start: int, unit_end: int) -> int:
    floor = max(unit_start + 1, unit_end - UNIT_CHAR_OVERLAP)
    if floor >= unit_end:
        return unit_end
    for index in range(floor, unit_end):
        if content[index].isspace() and index + 1 < unit_end:
            return index + 1
    return floor


def derive_units(content: str) -> list[_UnitDict]:
    """Derive deterministic embedding units from canonical chunk content.

    Args:
        content: Canonical chunk content.

    Returns:
        Ordered unit dictionaries with ``unit_index``, ``start``, ``end`` and
        ``text``. Empty or whitespace-only content returns an empty list.
    """
    if not content.strip():
        return []
    if len(content) <= UNIT_CHAR_BUDGET:
        return [{"unit_index": 0, "start": 0, "end": len(content), "text": content}]

    effective_end = len(content.rstrip())
    scan_content = content[:effective_end]
    sentence_boundaries = [
        match.start() for match in _SENTENCE_BOUNDARY_RE.finditer(scan_content)
    ]
    paragraph_boundaries = [
        match.start() for match in _PARAGRAPH_BOUNDARY_RE.finditer(scan_content)
    ]

    units: list[_UnitDict] = []
    start = 0
    while start < effective_end:
        end = _choose_unit_end(
            start=start,
            effective_end=effective_end,
            sentence_boundaries=sentence_boundaries,
            paragraph_boundaries=paragraph_boundaries,
        )
        if end <= start:
            end = min(start + UNIT_CHAR_BUDGET, effective_end)
        units.append({
            "unit_index": len(units),
            "start": start,
            "end": end,
            "text": content[start:end],
        })
        if end >= effective_end:
            break
        next_start = _overlap_start(content, unit_start=start, unit_end=end)
        start = end if next_start <= start else next_start

    # A slice inside long whitespace padding can be whitespace-only even when the
    # chunk as a whole has content; embedding it would store a meaningless vector.
    # Offsets stay anchored to the untouched canonical chunk; only unit_index is
    # renumbered so the per-chunk sequence stays gap-free.
    kept = [unit for unit in units if unit["text"].strip()]
    for index, unit in enumerate(kept):
        unit["unit_index"] = index
    return kept


def validate_vector(vector: object) -> list[float]:
    """Validate and normalize one embedding vector.

    Args:
        vector: Candidate vector object.

    Returns:
        A list of finite floats.

    Raises:
        ValueError: If the vector is not a list of exactly 1536 finite numbers.
    """
    if not isinstance(vector, list):
        raise ValueError("embedding vector must be a list")
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"embedding vector must have {EMBEDDING_DIMENSIONS} dimensions; got {len(vector)}"
        )

    validated: list[float] = []
    for index, value in enumerate(vector):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"embedding vector element {index} is not a number")
        as_float = float(value)
        if not math.isfinite(as_float):
            raise ValueError(f"embedding vector element {index} is not finite")
        validated.append(as_float)
    return validated


def _embed_units_with_isolation(
    embedder: EmbeddingBackend, units: list[_UnitWork]
) -> tuple[list[tuple[_UnitWork, list[float]]], list[tuple[_UnitWork, Exception]]]:
    """Embed a batch, recursively splitting failures down to single units.

    The split retries both halves and then only the failing half recursively, so
    one poisoned unit in ``n`` units adds about ``2 * ceil(log2(n))`` calls over
    the initial failed batch while allowing healthy sibling units to persist.

    Args:
        embedder: Live or stub embedding backend.
        units: Active embedding units in API-call order.

    Returns:
        Successful ``(unit, vector)`` pairs and failed ``(unit, exception)`` pairs.
    """
    if not units:
        return [], []
    try:
        raw_vectors = embedder.embed_texts([unit.text for unit in units])
        if len(raw_vectors) != len(units):
            raise ValueError(
                f"embedding backend returned {len(raw_vectors)} vectors for {len(units)} texts"
            )
        vectors = [validate_vector(vector) for vector in raw_vectors]
    except Exception as exc:
        if len(units) == 1:
            return [], [(units[0], exc)]
        midpoint = len(units) // 2
        left_vectors, left_failures = _embed_units_with_isolation(
            embedder, units[:midpoint]
        )
        right_vectors, right_failures = _embed_units_with_isolation(
            embedder, units[midpoint:]
        )
        return left_vectors + right_vectors, left_failures + right_failures

    return list(zip(units, vectors, strict=True)), []


def _chunk_rows_for_insert(state: _ChunkState) -> list[dict[str, object]]:
    now = datetime.now(UTC)
    return [
        {
            "chunk_embedding_id": uuid.uuid4(),
            "chunk_id": unit.chunk_id,
            "embedding_profile": EMBEDDING_PROFILE,
            "unit_policy": UNIT_POLICY,
            "unit_index": unit.unit_index,
            "unit_locator": {"start": unit.start, "end": unit.end},
            "vector": state.vectors[unit.unit_index],
            "created_at": now,
        }
        for unit in state.units
    ]


def _pending_chunks(
    conn: Connection, project_id: uuid.UUID, *, max_hydrated: int
) -> tuple[int, int, list[_PendingChunk]]:
    eligible_snapshot_ids = union(
        select(
            project_source_snapshot.c.source_snapshot_id.label("source_snapshot_id")
        ).where(project_source_snapshot.c.project_id == project_id),
        select(
            project_source_snapshot.c.full_text_snapshot_id.label("source_snapshot_id")
        )
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.full_text_snapshot_id.is_not(None)),
    ).subquery()

    eligible_filter = chunk_table.c.source_snapshot_id.in_(
        select(eligible_snapshot_ids.c.source_snapshot_id)
    )
    pending_filter = ~exists().where(
        (chunk_embedding.c.chunk_id == chunk_table.c.chunk_id)
        & (chunk_embedding.c.embedding_profile == EMBEDDING_PROFILE)
        & (chunk_embedding.c.unit_policy == UNIT_POLICY)
    )

    eligible_count = int(
        conn.execute(
            select(func.count()).select_from(chunk_table).where(eligible_filter)
        ).scalar_one()
    )
    pending_count = int(
        conn.execute(
            select(func.count())
            .select_from(chunk_table)
            .where(eligible_filter)
            .where(pending_filter)
        ).scalar_one()
    )
    if pending_count > max_hydrated:
        # The budget guard will trip anyway (units >= chunks with content); skip
        # hydrating full content for a backlog the pass is going to refuse.
        return eligible_count, pending_count, []
    rows = conn.execute(
        select(
            chunk_table.c.chunk_id,
            chunk_table.c.source_snapshot_id,
            chunk_table.c.sequence,
            chunk_table.c.content,
        )
        .where(eligible_filter)
        .where(pending_filter)
        .order_by(chunk_table.c.source_snapshot_id, chunk_table.c.sequence)
    ).fetchall()
    return eligible_count, pending_count, [
        _PendingChunk(
            chunk_id=row.chunk_id,
            source_snapshot_id=row.source_snapshot_id,
            sequence=row.sequence,
            content=row.content,
        )
        for row in rows
    ]


def _derive_unit_work(
    pending_chunks: list[_PendingChunk],
) -> tuple[dict[uuid.UUID, _ChunkState], list[_UnitWork], set[uuid.UUID]]:
    states: dict[uuid.UUID, _ChunkState] = {}
    all_units: list[_UnitWork] = []
    unitless_chunk_ids: set[uuid.UUID] = set()

    for chunk in pending_chunks:
        works = [
            _UnitWork(
                chunk_id=chunk.chunk_id,
                unit_index=unit["unit_index"],
                start=unit["start"],
                end=unit["end"],
                text=unit["text"],
            )
            for unit in derive_units(chunk.content)
        ]
        states[chunk.chunk_id] = _ChunkState(units=works)
        if works:
            all_units.extend(works)
        else:
            unitless_chunk_ids.add(chunk.chunk_id)
    return states, all_units, unitless_chunk_ids


def embed_pending_chunks(
    conn: Connection,
    *,
    embedder: EmbeddingBackend,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    batch_size: int = API_BATCH_SIZE,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> dict[str, int]:
    """Embed eligible project chunks that lack rows for the active profile.

    The pending query is project-scoped through the project's envelope snapshot
    IDs and non-null full-text snapshot IDs. A chunk with any row for the active
    profile and unit policy is treated as already embedded, matching the
    result-table idempotency pattern.

    Args:
        conn: Open database connection; inserts use its active transaction.
        embedder: Live or stub embedding backend.
        project_id: Project whose snapshot union defines embedding eligibility.
        run_id: Current run, used only for structured logs.
        batch_size: Maximum unit texts per backend call.
        max_chunks: Maximum embedding units allowed for this pass.

    Returns:
        Counts for newly embedded chunks, already embedded eligible chunks, failed
        pending chunks, skipped unitless chunks, inserted units and whether the
        budget guard stopped the pass — the same key set on every path.

    Raises:
        ValueError: If ``batch_size`` is not positive or ``max_chunks`` is negative.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if max_chunks < 0:
        raise ValueError("max_chunks must be non-negative")

    eligible_count, pending_count, pending_chunks = _pending_chunks(
        conn, project_id, max_hydrated=max_chunks
    )
    already_embedded = eligible_count - pending_count
    states, all_units, unitless_chunk_ids = _derive_unit_work(pending_chunks)
    total_units = len(all_units)

    if pending_count > max_chunks or total_units > max_chunks:
        log.error(
            "embed.budget_exceeded",
            eligible_chunks=eligible_count,
            pending_chunks=pending_count,
            already_embedded=already_embedded,
            pending_units=total_units if pending_chunks else None,
            max_chunks=max_chunks,
        )
        return {
            "embedded": 0,
            "already_embedded": already_embedded,
            "failed": 0,
            "skipped_no_units": len(unitless_chunk_ids),
            "units_embedded": 0,
            "budget_exceeded": 1,
        }

    # Unitless chunks (whitespace-only content) are skipped, not failed: nothing
    # was attempted, and counting them as failed would inflate the failure share
    # on every future pass since they never gain an embedding row.
    if unitless_chunk_ids:
        log.warning(
            "embed.chunk_no_units",
            chunk_count=len(unitless_chunk_ids),
            run_id=str(run_id),
        )

    chunk_order = {chunk.chunk_id: index for index, chunk in enumerate(pending_chunks)}
    embedded = 0
    units_embedded = 0

    for batch_index, start in enumerate(range(0, len(all_units), batch_size), start=1):
        batch_units = all_units[start:start + batch_size]
        active_units = [
            unit for unit in batch_units
            if not states[unit.chunk_id].failed and not states[unit.chunk_id].inserted
        ]
        if not active_units:
            continue

        embedded_vectors, failed_units = _embed_units_with_isolation(embedder, active_units)
        if failed_units:
            failed_chunk_ids = {unit.chunk_id for unit, _exc in failed_units}
            for chunk_id in failed_chunk_ids:
                states[chunk_id].failed = True
                states[chunk_id].vectors.clear()
            log.warning(
                "embed.batch_failed",
                batch_index=batch_index,
                chunk_count=len(failed_chunk_ids),
                unit_count=len(failed_units),
                error_type=",".join(
                    sorted({type(exc).__name__ for _unit, exc in failed_units})
                ),
                run_id=str(run_id),
            )

        for unit, vector in embedded_vectors:
            if states[unit.chunk_id].failed or states[unit.chunk_id].inserted:
                continue
            states[unit.chunk_id].vectors[unit.unit_index] = vector

        completed_chunk_ids = {
            unit.chunk_id
            for unit in active_units
            if len(states[unit.chunk_id].vectors) == len(states[unit.chunk_id].units)
        }
        batch_rows: list[dict[str, object]] = []
        for chunk_id in sorted(completed_chunk_ids, key=lambda item: chunk_order[item]):
            state = states[chunk_id]
            if state.failed or state.inserted:
                continue
            batch_rows.extend(_chunk_rows_for_insert(state))
            state.inserted = True
            embedded += 1
            units_embedded += len(state.units)
        if batch_rows:
            # ON CONFLICT DO NOTHING keeps an overlapping embed pass (two runs
            # racing the same anti-join) from failing the whole component on the
            # unit unique constraint; the loser's duplicate rows are discarded.
            conn.execute(pg_insert(chunk_embedding).values(batch_rows).on_conflict_do_nothing())

    failed = sum(1 for state in states.values() if state.failed)
    result = {
        "embedded": embedded,
        "already_embedded": already_embedded,
        "failed": failed,
        "skipped_no_units": len(unitless_chunk_ids),
        "units_embedded": units_embedded,
        "budget_exceeded": 0,
    }
    log.info("embed.summary", **result, run_id=str(run_id))
    return result
