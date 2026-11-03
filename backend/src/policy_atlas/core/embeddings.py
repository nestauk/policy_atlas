"""Embedding backends and unit-grain chunk vectorisation for task 009.

This module owns the first runtime-egress embedding seam. The defaultable stub is
deterministic and zero-egress; the live backend is explicit and env-keyed. The
embed pass is task-scoped through ``task_source_snapshot`` because chunks
and snapshots are corpus-global, not task-owned.

Task 057 (D6, plan P11): when the provider says "too many requests" (throttling),
the live backends no longer wait and retry on their own; they raise
:class:`Throttled`. :class:`AdaptivePool` owns both how many requests are in
flight and the waiting: it halves the number in flight when throttled, waits,
and adds one back after a run of clean batches, up to the route's ``pool_cap``.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
import math
import os
import random
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable, Collection, Iterator, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, TypedDict

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import ClientError
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from sqlalchemy import ColumnElement, exists, func, select, union
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Connection

from policy_atlas.core.model_routes import route
from policy_atlas.core.openai_client import resolve_openai_client
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import chunk_embedding, task_source_snapshot
from policy_atlas.core.tokens import word_tokens

log = structlog.get_logger()

EMBEDDING_PROFILE = route().embeddings.profile
EMBEDDING_MODEL = route().embeddings.model
EMBEDDING_DIMENSIONS = 1536

UNIT_POLICY = "embedding_unit_policy_v1"
UNIT_CHAR_BUDGET = 2000
UNIT_CHAR_OVERLAP = 200

API_BATCH_SIZE = 96
DEFAULT_MAX_CHUNKS = 20_000
EMBEDDING_RATE_LIMIT_BACKOFF_BASE_S = 2.0
EMBEDDING_RATE_LIMIT_BACKOFF_CAP_S = 60.0
EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS = 4
#: The adaptive pool (task 057, D6): requests in flight at the start, clean
#: batches in a row before one more is allowed, and how many times one batch may
#: be throttled before it is given up for this pass (its chunks stay pending).
POOL_START_WIDTH = 2
POOL_CLEAN_RUN = 5
POOL_MAX_THROTTLES_PER_BATCH = 8
#: The longest wait a provider's ``Retry-After`` may ask the pool for.
POOL_RETRY_AFTER_CAP_S = EMBEDDING_RATE_LIMIT_BACKOFF_CAP_S
#: Seconds one OpenAI embedding request may take (the client-level value before
#: task 057). Embeddings are not a route step, so the value lives here.
OPENAI_EMBEDDING_TIMEOUT_S = 30.0
#: How the Bedrock clients (Cohere embeddings here, Claude search queries in
#: ``search_generation``) wait and retry (task 057, D12): give up on a response
#: after 60 s, and let botocore make one attempt only, because the callers run
#: their own throttling backoff.
BEDROCK_CLIENT_CONFIG = Config(read_timeout=60, retries={"mode": "standard", "max_attempts": 1})

_UINT32_MAX = float((2**32) - 1)
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_BOUNDARY_RE = re.compile(r"\n\n")
_sleep = time.sleep


#: Opens one short database transaction that commits when the block exits
#: (``engine.begin``).
ConnectFactory = Callable[[], AbstractContextManager[Connection]]


class Throttled(Exception):  # noqa: N818 - a signal, named for what the provider said
    """The provider refused an embedding request for its rate limit ("throttling").

    Raised by the live backends instead of waiting and retrying themselves;
    :class:`AdaptivePool` (or :func:`embed_with_retry` for one-off calls) decides
    how long to wait and how many requests to keep in flight.

    Args:
        provider: ``cohere`` or ``openai``; names the log event
            (``embedding.<provider>_rate_limited``).
        retry_after_s: The wait the provider asked for, when it said one.
    """

    def __init__(self, *, provider: str, retry_after_s: float | None = None) -> None:
        super().__init__(f"{provider} embedding request throttled")
        self.provider = provider
        self.retry_after_s = retry_after_s


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


_last_usage = threading.local()


def take_last_prompt_tokens() -> int | None:
    """Return and clear the prompt-token count of this thread's last live embed call.

    ``embed_texts`` returns vectors only, so the live backend parks the provider's
    usage here for the tracing wrapper that runs on the same thread. ``None`` when
    the last call was a stub or the provider omitted usage.
    """
    tokens = getattr(_last_usage, "prompt_tokens", None)
    _last_usage.prompt_tokens = None
    return tokens if isinstance(tokens, int) else None


class EmbeddingBackend(Protocol):
    """The embedding seam, implemented by live and deterministic backends."""

    @property
    def mode(self) -> str:
        """``"live"`` or ``"stub"``; read-only so tracing wrappers can proxy it."""
        ...

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        """Embed texts in input order.

        Args:
            texts: Text units to embed.
            kind: Whether the texts are documents or search queries.

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

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        """Return deterministic hash-derived vectors.

        Args:
            texts: Text units to embed.
            kind: Whether the texts are documents or search queries. The stub
                uses the same deterministic vector for either kind.

        Returns:
            One 1536-dimensional vector per input text.
        """
        return [_hash_vector(text) for text in texts]


class OpenAIEmbeddingBackend:
    """Live OpenAI embedding backend.

    Args:
        api_key: Optional OpenAI API key. If omitted, the route's key variable is read
            from the environment.

    Raises:
        RuntimeError: If no API key is provided or configured.
    """

    mode = "live"

    def __init__(self, api_key: str | None = None) -> None:
        # The client makes one HTTP attempt per create call (``max_retries=0``,
        # task 057); the explicit 429 loop below is the only retry.
        self._client = resolve_openai_client(api_key, backend_name="OpenAIEmbeddingBackend")

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        """Embed texts through OpenAI's embeddings API.

        Args:
            texts: Text units to embed.
            kind: Whether the texts are documents or search queries. OpenAI's
                embedding endpoint does not distinguish them.

        Returns:
            One 1536-dimensional vector per input text, in input order.

        Raises:
            Throttled: The provider refused the request for its rate limit (429);
                the caller decides when to try again.
            RuntimeError: If the provider returns a different number of vectors.
        """
        if not texts:
            return []

        log.info("embedding.openai.request", text_count=len(texts))
        response = self._create_embeddings_with_backoff(texts)
        _last_usage.prompt_tokens = getattr(getattr(response, "usage", None), "prompt_tokens", None)
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
                    timeout=OPENAI_EMBEDDING_TIMEOUT_S,
                )
            except RateLimitError as exc:
                # "Too many requests" is the caller's to wait out (task 057, D6).
                raise Throttled(provider="openai", retry_after_s=_retry_after_s(exc)) from exc
            except (APITimeoutError, APIConnectionError, APIStatusError) as exc:
                # Retry a timeout, a dropped connection and a server error (5xx)
                # with the same backoff. The client no longer retries on its own
                # (task 057), so this loop covers them.
                if isinstance(exc, APIStatusError) and exc.status_code < 500:
                    raise
                if attempt == EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS - 1:
                    raise
                delay_s = _embedding_rate_limit_delay_s(attempt)
                log.warning(
                    "embedding.openai_retry",
                    error=type(exc).__name__,
                    attempt=attempt + 1,
                    max_attempts=EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS,
                    sleep_s=delay_s,
                )
                _sleep(delay_s)

        raise RuntimeError("unreachable embedding retry state")


def _retry_after_s(exc: Exception) -> float | None:
    """The ``Retry-After`` seconds on a provider error's response, if it gave one."""
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    value = headers.get("retry-after")
    try:
        seconds = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return None
    return seconds


class CohereEmbeddingBackend:
    """Live Cohere Embed v4 backend served through Amazon Bedrock.

    Args:
        client: Optional Bedrock Runtime client. Tests provide a stubbed client;
            live calls use the standard boto3 credential chain.
    """

    mode = "live"

    def __init__(self, client: Any | None = None) -> None:
        self._client = client or boto3.client(
            "bedrock-runtime",
            region_name=os.environ.get("AWS_REGION") or "eu-west-2",
            config=BEDROCK_CLIENT_CONFIG,
        )

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        """Embed texts through Cohere Embed v4 on Bedrock.

        Args:
            texts: Text units to embed.
            kind: Whether the texts are documents or search queries.

        Returns:
            One 1536-dimensional vector per input text, in input order.

        Raises:
            Throttled: Bedrock refused a request for its rate limit (token or
                request quota); the caller decides when to try again.
            ClientError: If Bedrock rejects a request for another reason.
            RuntimeError: If Bedrock returns an invalid embedding response.
        """
        if not texts:
            return []

        vectors: list[list[float]] = []
        token_count: int | None = 0
        for start in range(0, len(texts), API_BATCH_SIZE):
            batch = texts[start : start + API_BATCH_SIZE]
            log.info("embedding.cohere.request", text_count=len(batch), input_kind=kind)
            response = self._invoke_model_with_backoff(batch, kind=kind)
            batch_vectors = self._parse_vectors(response, text_count=len(batch))
            vectors.extend(batch_vectors)
            header = (
                response.get("ResponseMetadata", {})
                .get("HTTPHeaders", {})
                .get("x-amzn-bedrock-input-token-count")
            )
            if header is None:
                token_count = None
            elif token_count is not None:
                token_count += int(header)
            log.info(
                "embedding.cohere.response",
                text_count=len(batch),
                vector_count=len(batch_vectors),
                input_kind=kind,
            )

        _last_usage.prompt_tokens = token_count
        return vectors

    def _invoke_model_with_backoff(
        self, texts: list[str], *, kind: Literal["document", "query"]
    ) -> Any:
        try:
            return self._client.invoke_model(
                modelId=EMBEDDING_MODEL,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "texts": texts,
                        "input_type": (
                            "search_query" if kind == "query" else "search_document"
                        ),
                        "embedding_types": ["float"],
                        "output_dimension": EMBEDDING_DIMENSIONS,
                        "truncate": "NONE",
                    }
                ),
            )
        except ClientError as error:
            if _is_bedrock_throttle(error):
                # Waiting is the caller's (task 057, D6): one attempt here.
                raise Throttled(provider="cohere") from error
            raise

    @staticmethod
    def _parse_vectors(response: Any, *, text_count: int) -> list[list[float]]:
        try:
            body = json.loads(response["body"].read())
            vectors = body["embeddings"]["float"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Cohere embeddings response body was invalid.") from exc
        if not isinstance(vectors, list) or len(vectors) != text_count:
            raise RuntimeError("Cohere embeddings response length did not match input length.")
        if any(
            not isinstance(vector, list) or len(vector) != EMBEDDING_DIMENSIONS
            for vector in vectors
        ):
            raise RuntimeError("Cohere embeddings response had an invalid vector dimension.")
        return vectors


def _is_bedrock_throttle(error: ClientError) -> bool:
    """True for Bedrock's rate-limit refusals ("ThrottlingException", "Too many tokens")."""
    details = error.response.get("Error", {})
    if details.get("Code") == "ThrottlingException":
        return True
    return "too many tokens" in str(details.get("Message", "")).lower()


def live_embedding_backend() -> EmbeddingBackend:
    """Build the live embedding backend selected by the active model route.

    Returns:
        The route-selected live embedding backend.

    Raises:
        RuntimeError: If the route names an unsupported embedding backend.
    """
    backend = route().embeddings.backend
    if backend == "cohere":
        return CohereEmbeddingBackend()
    if backend == "openai":
        return OpenAIEmbeddingBackend()
    raise RuntimeError(f"Unsupported embedding backend: {backend}")


def _embedding_rate_limit_delay_s(attempt: int) -> float:
    base_s = float(min(
        EMBEDDING_RATE_LIMIT_BACKOFF_BASE_S * (2**attempt),
        EMBEDDING_RATE_LIMIT_BACKOFF_CAP_S,
    ))
    return float(base_s + random.uniform(0.0, base_s))


def embed_with_retry(
    embedder: EmbeddingBackend,
    texts: list[str],
    *,
    kind: Literal["document", "query"] = "document",
) -> list[list[float]]:
    """Embed one small set of texts, waiting and retrying when throttled.

    For the one-off calls outside the stage's pool (search-query embedding): up
    to ``EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS`` attempts on today's backoff curve,
    or the provider's ``Retry-After`` when it gives one.

    Args:
        embedder: Live or stub embedding backend.
        texts: Texts to embed.
        kind: Whether the texts are documents or search queries.

    Returns:
        One vector per text, in order.

    Raises:
        Throttled: Every attempt was throttled.
    """
    for attempt in range(EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS):
        try:
            return embedder.embed_texts(texts, kind=kind)
        except Throttled as exc:
            if attempt == EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS - 1:
                raise
            delay_s = (
                min(exc.retry_after_s, POOL_RETRY_AFTER_CAP_S)
                if exc.retry_after_s is not None
                else _embedding_rate_limit_delay_s(attempt)
            )
            log.warning(
                f"embedding.{exc.provider}_rate_limited",
                attempt=attempt + 1,
                max_attempts=EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS,
                sleep_s=delay_s,
            )
            _sleep(delay_s)
    raise RuntimeError("unreachable embedding retry state")


@dataclass(frozen=True)
class PoolResult[R]:
    """One job's result from :meth:`AdaptivePool.run`.

    Attributes:
        index: The job's position in the list given to ``run``.
        value: What the job returned; None when it was given up.
        error: The last :class:`Throttled` when the job was throttled
            ``max_throttles`` times and given up for this pass; else None.
    """

    index: int
    value: R | None
    error: Throttled | None = None


class AdaptivePool:
    """Runs embedding requests several at a time, as many as the provider allows.

    The provider (Bedrock for Cohere Embed v4) limits tokens per minute, so a
    fixed number of requests in flight is either too few (slow) or too many
    (time lost to throttling). The pool adapts, like a driver easing off when
    traffic bunches up (task 057, D6):

    - it starts with ``start`` requests in flight;
    - when a request is throttled, it halves the number in flight (never below
      1; requests sent before the last halving do not halve it again), puts the
      throttled job back at the front of the queue, and waits before sending
      more: the provider's ``Retry-After`` when given, else the backoff curve;
    - after ``clean_run`` clean results in a row it allows one more, up to
      ``cap`` (``pool_cap`` in the route file, default 8);
    - a job throttled ``max_throttles`` times is given up for this pass.

    The state carries across calls of :meth:`run`, so one pool per stage learns
    the allowance once. Jobs run on worker threads (each with a copy of the
    caller's context, so log lines keep the run id); results come back to the
    caller's thread, which does the database writes.

    Args:
        start: Requests in flight at the start.
        cap: The most in flight; None reads the route's ``pool_cap``.
        clean_run: Clean results in a row before one more is allowed.
        max_throttles: Throttles one job may take before it is given up.
        backoff: Seconds to wait after the n-th throttled round in a row
            (n from 0).
        sleep: Sleep function (a test seam).

    Raises:
        ValueError: A setting below 1.
    """

    def __init__(
        self,
        *,
        start: int = POOL_START_WIDTH,
        cap: int | None = None,
        clean_run: int = POOL_CLEAN_RUN,
        max_throttles: int = POOL_MAX_THROTTLES_PER_BATCH,
        backoff: Callable[[int], float] = _embedding_rate_limit_delay_s,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        cap = route().embeddings.pool_cap if cap is None else cap
        if min(start, cap, clean_run, max_throttles) < 1:
            raise ValueError("pool settings must be at least 1")
        self.cap = cap
        self._width = min(start, cap)
        self._clean_run = clean_run
        self._max_throttles = max_throttles
        self._backoff = backoff
        self._sleep = sleep
        self._clean = 0  # clean results in a row
        self._streak = 0  # throttled rounds in a row (indexes the backoff curve)
        self._epoch = 0  # bumped at each halving

    @property
    def width(self) -> int:
        """Requests currently allowed in flight."""
        return self._width

    def _set_width(self, width: int, reason: str) -> None:
        if width != self._width:
            log.info("embed.pool_width", width=width, previous=self._width, reason=reason)
            self._width = width

    def run[T, R](self, jobs: Sequence[T], fn: Callable[[T], R]) -> Iterator[PoolResult[R]]:
        """Run ``fn`` on every job, adapting how many run at once.

        Args:
            jobs: The jobs (embedding batches).
            fn: Runs one job on a worker thread; raises :class:`Throttled` when
                the provider throttles it. Any other error is raised from here.

        Yields:
            One result per job, in completion order, carrying the job's index.
        """
        pending: deque[tuple[int, T, int]] = deque(
            (index, job, 0) for index, job in enumerate(jobs)
        )
        if not pending:
            return
        executor = ThreadPoolExecutor(max_workers=self.cap, thread_name_prefix="policy-atlas-embed")
        running: dict[Future[R], tuple[int, T, int, int]] = {}
        try:
            while pending or running:
                while pending and len(running) < self._width:
                    index, job, throttles = pending.popleft()
                    # A fresh copy per job: one context cannot run on two threads.
                    future = executor.submit(contextvars.copy_context().run, fn, job)
                    running[future] = (index, job, throttles, self._epoch)
                done, _ = wait(running, return_when=FIRST_COMPLETED)
                throttled: list[Throttled] = []
                requeue: list[tuple[int, T, int]] = []
                results: list[PoolResult[R]] = []
                for future in sorted(done, key=lambda f: running[f][0]):
                    index, job, throttles, epoch = running.pop(future)
                    error = future.exception()
                    if isinstance(error, Throttled):
                        throttled.append(error)
                        self._clean = 0
                        if epoch == self._epoch:
                            self._epoch += 1
                            self._set_width(max(1, self._width // 2), "throttled")
                        if throttles + 1 >= self._max_throttles:
                            results.append(PoolResult(index=index, value=None, error=error))
                        else:
                            requeue.append((index, job, throttles + 1))
                        continue
                    if error is not None:
                        raise error
                    self._streak = 0
                    self._clean += 1
                    if self._clean >= self._clean_run:
                        self._clean = 0
                        self._set_width(min(self.cap, self._width + 1), "clean_run")
                    results.append(PoolResult(index=index, value=future.result()))
                pending.extendleft(reversed(requeue))
                yield from results
                if throttled:
                    asked = [t.retry_after_s for t in throttled if t.retry_after_s is not None]
                    delay_s = (
                        min(max(asked), POOL_RETRY_AFTER_CAP_S)
                        if asked
                        else self._backoff(self._streak)
                    )
                    self._streak += 1
                    log.warning(
                        f"embedding.{throttled[0].provider}_rate_limited",
                        throttled=len(throttled),
                        width=self._width,
                        sleep_s=delay_s,
                    )
                    self._sleep(delay_s)
        finally:
            executor.shutdown(wait=True, cancel_futures=True)


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

    Raises:
        Throttled: The provider throttled a request; nothing is split for it.
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
    except Throttled:
        raise  # the pool waits and resends the whole batch; never split for throttling
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
            # Task 057: the floats go to pgvector's binary column as a
            # ``'[...]'::vector`` text cast (schema.Vector), plus the unit's sorted
            # distinct words for the word-overlap score.
            "embedding": state.vectors[unit.unit_index],
            "tokens": sorted(word_tokens(unit.text)),
            "created_at": now,
        }
        for unit in state.units
    ]


def _pending_chunks(
    conn: Connection,
    task_id: uuid.UUID,
    *,
    max_hydrated: int,
    snapshot_ids: Collection[uuid.UUID] | None = None,
) -> tuple[int, int, list[_PendingChunk]]:
    eligible_snapshot_ids = union(
        select(
            task_source_snapshot.c.source_snapshot_id.label("source_snapshot_id")
        ).where(task_source_snapshot.c.task_id == task_id),
        select(
            task_source_snapshot.c.full_text_snapshot_id.label("source_snapshot_id")
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.full_text_snapshot_id.is_not(None)),
    ).subquery()

    eligible_filter: ColumnElement[bool] = chunk_table.c.source_snapshot_id.in_(
        select(eligible_snapshot_ids.c.source_snapshot_id)
    )
    if snapshot_ids is not None:
        eligible_filter = eligible_filter & chunk_table.c.source_snapshot_id.in_(
            list(snapshot_ids)
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
    conn: Connection | None,
    *,
    embedder: EmbeddingBackend,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    batch_size: int = API_BATCH_SIZE,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    snapshot_ids: Collection[uuid.UUID] | None = None,
    pool: AdaptivePool | None = None,
    connect: ConnectFactory | None = None,
    summary_event: str = "embed.summary",
) -> dict[str, int]:
    """Embed eligible task chunks that lack rows for the active profile.

    The pending query is task-scoped through the task's envelope snapshot
    IDs and non-null full-text snapshot IDs. A chunk with any row for the active
    profile and unit policy is treated as already embedded, matching the
    result-table idempotency pattern.

    The requests go through an :class:`AdaptivePool` (task 057, D6), several at
    a time; the database writes stay on the calling thread.

    Args:
        conn: Open database connection; reads and inserts use its active
            transaction. None with ``connect``: the read is one short
            transaction and each batch's insert commits on its own.
        embedder: Live or stub embedding backend.
        task_id: Task whose snapshot union defines embedding eligibility.
        run_id: Current run, used only for structured logs.
        batch_size: Maximum unit texts per backend call.
        max_chunks: Maximum embedding units allowed for this pass.
        snapshot_ids: When given, only chunks of these snapshots (still within
            the task's snapshots) are considered; the full-text stage passes the
            snapshots its documents link (task 057).
        pool: The pool to send the requests through (the full-text stage keeps
            one across its passes); None builds one for this pass.
        connect: Opens one short committed transaction; used when ``conn`` is
            None.
        summary_event: The log event for this pass's counts (the full-text
            stage logs its per-tick passes as ``embed.pass`` and one
            ``embed.summary`` for the stage).

    Returns:
        Counts for newly embedded chunks, already embedded eligible chunks, failed
        pending chunks, skipped unitless chunks, inserted units and whether the
        budget guard stopped the pass — the same key set on every path.

    Raises:
        ValueError: If ``batch_size`` is not positive, ``max_chunks`` is
            negative, or neither ``conn`` nor ``connect`` is given.
    """
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if max_chunks < 0:
        raise ValueError("max_chunks must be non-negative")
    if conn is None and connect is None:
        raise ValueError("embed_pending_chunks needs conn or connect")

    if conn is not None:
        eligible_count, pending_count, pending_chunks = _pending_chunks(
            conn, task_id, max_hydrated=max_chunks, snapshot_ids=snapshot_ids
        )
    else:
        assert connect is not None
        with connect() as read_conn:
            eligible_count, pending_count, pending_chunks = _pending_chunks(
                read_conn, task_id, max_hydrated=max_chunks, snapshot_ids=snapshot_ids
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
    batches = [all_units[start:start + batch_size] for start in range(0, total_units, batch_size)]
    if pool is None:
        pool = AdaptivePool()

    def insert(rows: list[dict[str, object]]) -> None:
        # ON CONFLICT DO NOTHING keeps an overlapping embed pass (two runs
        # racing the same anti-join) from failing the whole component on the
        # unit unique constraint; the loser's duplicate rows are discarded.
        statement = pg_insert(chunk_embedding).values(rows).on_conflict_do_nothing()
        if conn is not None:
            conn.execute(statement)
        else:
            assert connect is not None
            with connect() as write_conn:
                write_conn.execute(statement)

    def embed_batch(
        units: list[_UnitWork],
    ) -> tuple[list[tuple[_UnitWork, list[float]]], list[tuple[_UnitWork, Exception]]]:
        return _embed_units_with_isolation(embedder, units)

    for result in pool.run(batches, embed_batch):
        batch_units = batches[result.index]
        if result.value is not None:
            embedded_vectors, failed_units = result.value
        else:  # throttled too often: this pass gives the batch up; it stays pending
            assert result.error is not None
            embedded_vectors, failed_units = [], [(unit, result.error) for unit in batch_units]
        if failed_units:
            failed_chunk_ids = {unit.chunk_id for unit, _exc in failed_units}
            for chunk_id in failed_chunk_ids:
                states[chunk_id].failed = True
                states[chunk_id].vectors.clear()
            log.warning(
                "embed.batch_failed",
                batch_index=result.index + 1,
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
            for unit in batch_units
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
            insert(batch_rows)

    failed = sum(1 for state in states.values() if state.failed)
    result_counts = {
        "embedded": embedded,
        "already_embedded": already_embedded,
        "failed": failed,
        "skipped_no_units": len(unitless_chunk_ids),
        "units_embedded": units_embedded,
        "budget_exceeded": 0,
    }
    log.info(summary_event, **result_counts, run_id=str(run_id))
    return result_counts
