"""Tests for the embeddings module — schema, unit derivation, embed pass, stubs."""

import concurrent.futures
import io
import json
import random
import struct
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from types import SimpleNamespace
from typing import Any, Literal, cast

import boto3
import pytest
import sqlalchemy as sa
from botocore.exceptions import ClientError
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from structlog.testing import capture_logs

from policy_atlas.api import deps
from policy_atlas.core import embeddings as embeddings_module
from policy_atlas.core.embeddings import (
    API_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
    EMBEDDING_PROFILE,
    EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS,
    UNIT_CHAR_BUDGET,
    UNIT_POLICY,
    AdaptivePool,
    CohereEmbeddingBackend,
    OpenAIEmbeddingBackend,
    StubEmbeddingBackend,
    Throttled,
    derive_units,
    embed_pending_chunks,
    embed_with_retry,
    validate_vector,
)
from policy_atlas.core.schema import (
    chunk as chunk_table,
)
from policy_atlas.core.schema import (
    chunk_embedding,
    metadata,
    task_source_snapshot,
)
from policy_atlas.core.tokens import word_tokens
from policy_atlas.evidence_search.sourcing.acquire import (
    AcquireContext,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.evidence_search.sourcing.ingest_upload import ingest_upload
from tests.helpers import (
    delete_task_data,
    executed_calls_for,
    now,
    seed_scope,
    seed_source,
    seed_task_and_run,
)
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend


def _insert_chunk(
    conn: Connection, snapshot_id: uuid.UUID, sequence: int, content: str
) -> uuid.UUID:
    chunk_id = uuid.uuid4()
    conn.execute(
        chunk_table.insert().values(
            chunk_id=chunk_id,
            source_snapshot_id=snapshot_id,
            sequence=sequence,
            content=content,
            content_hash=f"hash-{chunk_id}",
            locator={"sequence": sequence},
            segmentation_policy="manual_v1",
            created_at=now(),
        )
    )
    return chunk_id


def _f32(value: float) -> float:
    """Round a float to single precision, as pgvector stores it."""
    return float(struct.unpack("f", struct.pack("f", value))[0])


def _assert_two_columns_agree(conn: Connection, chunk_ids: list[uuid.UUID]) -> int:
    """Assert ``embedding`` and ``tokens`` are right on every row of the chunks.

    Task 057 writes the vector to pgvector's binary column only (the JSON column is
    gone): it must hold the stub backend's floats for the unit's text at single
    precision, and ``tokens`` the unit's words by ``core.tokens``.
    """
    rows = conn.execute(
        sa.text(
            "SELECT ce.embedding, ce.tokens, ce.unit_locator, c.content "
            "FROM chunk_embedding ce JOIN chunk c ON c.chunk_id = ce.chunk_id "
            "WHERE ce.chunk_id = ANY(:ids)"
        ),
        {"ids": chunk_ids},
    ).fetchall()
    assert rows
    stub = StubEmbeddingBackend()
    for row in rows:
        unit_text = row.content[row.unit_locator["start"] : row.unit_locator["end"]]
        assert row.embedding is not None
        stored = [float(v) for v in row.embedding.strip("[]").split(",")]
        expected = stub.embed_texts([unit_text])[0]
        assert [_f32(v) for v in stored] == [_f32(v) for v in expected]
        assert row.tokens == sorted(word_tokens(unit_text))
    return len(rows)


# --- Migration / table presence ---


def test_table_count(conn: Connection) -> None:
    # 33 -> 36: task 033 adds `organisation` and `app_user` (tenancy above the
    # entity hierarchy) and ADR 0032 adds `project_membership`; 36 -> 37:
    # task 036 adds `waitlist_entry`; 37 -> 38: task 044 adds `task_link` (the
    # Link between two tasks); 38 -> 43: task 045 adds `option`,
    # `option_membership`, `option_relation`, `longlist_result` and
    # `intervention_profile_record`; no evidence-search table changed.
    assert len(metadata.tables) == 43


def test_uq_chunk_embedding_unit_rejects_duplicate(conn: Connection) -> None:
    pid, _rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    chunk_id = _insert_chunk(conn, snap_id, 1, "A single canonical chunk.")
    vector = StubEmbeddingBackend().embed_texts(["A single canonical chunk."])[0]

    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding_profile=EMBEDDING_PROFILE,
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": 25},
            embedding=vector,
            created_at=now(),
        )
    )
    with pytest.raises(IntegrityError, match="uq_chunk_embedding_unit"):
        conn.execute(
            chunk_embedding.insert().values(
                chunk_embedding_id=uuid.uuid4(),
                chunk_id=chunk_id,
                embedding_profile=EMBEDDING_PROFILE,
                unit_policy=UNIT_POLICY,
                unit_index=0,
                unit_locator={"start": 0, "end": 25},
                embedding=vector,
                created_at=now(),
            )
        )
    conn.rollback()
    conn.begin()


# --- Vector validation (pure Python, no DB) ---


def test_validate_vector_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="must be a list"):
        validate_vector({"not": "a list"})


def test_validate_vector_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="dimensions"):
        validate_vector([0.1, 0.2, 0.3])


def test_validate_vector_rejects_non_finite() -> None:
    vector: list[Any] = [0.0] * EMBEDDING_DIMENSIONS
    vector[5] = float("nan")
    with pytest.raises(ValueError, match="not finite"):
        validate_vector(vector)


def test_validate_vector_accepts_well_formed_vector() -> None:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    assert validate_vector(vector) == vector


# --- Stub determinism ---


def test_stub_vectors_deterministic_across_instances() -> None:
    a = StubEmbeddingBackend().embed_texts(["Housing policy evidence."])[0]
    b = StubEmbeddingBackend().embed_texts(["Housing policy evidence."])[0]
    assert a == b


def test_stub_vector_dimensions() -> None:
    vector = StubEmbeddingBackend().embed_texts(["Any text."])[0]
    assert len(vector) == EMBEDDING_DIMENSIONS


# --- Unit derivation (pure Python, no DB) ---


def test_derive_units_in_budget_single_unit() -> None:
    content = "A short paragraph well within the character budget."
    units = derive_units(content)
    assert len(units) == 1
    assert units[0]["unit_index"] == 0
    assert units[0]["start"] == 0
    assert units[0]["end"] == len(content)
    assert units[0]["text"] == content


def test_derive_units_empty_and_whitespace_yield_no_units() -> None:
    assert derive_units("") == []
    assert derive_units("   \n\t  ") == []


def test_derive_units_oversized_multi_sentence_splits_with_overlap() -> None:
    sentence = "This is a sentence about policy analysis and evidence review of housing programs. "
    content = sentence * 40
    assert len(content) > UNIT_CHAR_BUDGET

    units = derive_units(content)
    assert len(units) > 1

    starts = [unit["start"] for unit in units]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)

    for index, unit in enumerate(units):
        assert unit["unit_index"] == index
        assert unit["text"] == content[unit["start"] : unit["end"]]

    for prev_unit, cur_unit in zip(units, units[1:], strict=False):
        overlap = prev_unit["end"] - cur_unit["start"]
        assert 0 < overlap <= 260

    # derive_units is pure: the canonical content passed in is never mutated.
    assert content == sentence * 40


# --- embed_pending_chunks: idempotency, stamping, canonical-chunk immutability ---


def test_embed_pending_chunks_idempotent_and_stamps_every_row(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    chunk_ids = [_insert_chunk(conn, snap_id, i, f"Chunk body number {i}.") for i in range(1, 4)]

    first = embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)
    assert first["embedded"] == 3
    assert first["already_embedded"] == 0
    assert first["failed"] == 0

    rows = conn.execute(
        select(chunk_embedding).where(chunk_embedding.c.chunk_id.in_(chunk_ids))
    ).fetchall()
    assert len(rows) == 3
    for row in rows:
        assert row.embedding_profile == EMBEDDING_PROFILE
        assert row.unit_policy == UNIT_POLICY
    assert _assert_two_columns_agree(conn, chunk_ids) == 3

    # Canonical chunk content is untouched by the embed pass.
    for i, chunk_id in enumerate(chunk_ids, start=1):
        stored = conn.execute(
            select(chunk_table.c.content).where(chunk_table.c.chunk_id == chunk_id)
        ).scalar_one()
        assert stored == f"Chunk body number {i}."

    second = embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)
    assert second["embedded"] == 0
    assert second["already_embedded"] == 3


# --- Failure isolation ---


class _RaisingEmbedder:
    mode = "stub"

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        raise RuntimeError("embedder always fails")


def test_embed_pending_chunks_failure_isolation_and_retry(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    chunk_id = _insert_chunk(conn, snap_id, 1, "This chunk will fail to embed.")

    result = embed_pending_chunks(conn, embedder=_RaisingEmbedder(), task_id=pid, run_id=rid)
    assert result["failed"] == 1
    assert result["embedded"] == 0

    rows = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == chunk_id)
    ).scalar_one()
    assert rows == 0

    retry = embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)
    assert retry["embedded"] == 1
    assert retry["failed"] == 0


class _PoisoningEmbedder:
    mode = "stub"

    def __init__(self, poison: str) -> None:
        self._poison = poison
        self.call_sizes: list[int] = []

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        self.call_sizes.append(len(texts))
        if any(self._poison in text for text in texts):
            raise RuntimeError("poisoned unit")
        return [[0.0] * EMBEDDING_DIMENSIONS for _text in texts]


def test_embed_unit_split_isolates_one_poisoned_unit_in_128() -> None:
    poison_chunk_id = uuid.uuid4()
    units = [
        embeddings_module._UnitWork(
            chunk_id=poison_chunk_id if index == 0 else uuid.uuid4(),
            unit_index=0,
            start=0,
            end=1,
            text="poison" if index == 0 else f"healthy {index}",
        )
        for index in range(128)
    ]
    embedder = _PoisoningEmbedder("poison")

    successes, failures = embeddings_module._embed_units_with_isolation(embedder, units)

    assert len(successes) == 127
    assert [unit.chunk_id for unit, _exc in failures] == [poison_chunk_id]
    assert embedder.call_sizes == [128, 64, 32, 16, 8, 4, 2, 1, 1, 2, 4, 8, 16, 32, 64]


# --- Budget guard ---


class _RaisingIfCalledEmbedder:
    mode = "stub"

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        raise AssertionError("the embedder must never be called once the budget is exceeded")


def test_embed_pending_chunks_budget_guard_stops_before_any_call(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "Chunk A.")
    _insert_chunk(conn, snap_id, 2, "Chunk B.")

    result = embed_pending_chunks(
        conn,
        embedder=_RaisingIfCalledEmbedder(),
        task_id=pid,
        run_id=rid,
        max_chunks=1,
    )
    assert result["budget_exceeded"] == 1
    assert result["embedded"] == 0


# --- Task scoping ---


class _CountingEmbedder:
    mode = "stub"

    def __init__(self) -> None:
        self.seen_texts: list[str] = []

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        self.seen_texts.extend(texts)
        return StubEmbeddingBackend().embed_texts(texts)


def test_embed_pending_chunks_task_scoped(conn: Connection) -> None:
    pid_a, rid_a = seed_task_and_run(conn)
    pid_b, _rid_b = seed_task_and_run(conn)
    snap_a, _tss_a = seed_source(conn, pid_a)
    snap_b, _tss_b = seed_source(conn, pid_b)
    _insert_chunk(conn, snap_a, 1, "Task A content.")
    b_chunk_id = _insert_chunk(conn, snap_b, 1, "Task B content.")

    embedder = _CountingEmbedder()
    embed_pending_chunks(conn, embedder=embedder, task_id=pid_a, run_id=rid_a)

    assert "Task B content." not in embedder.seen_texts
    rows = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == b_chunk_id)
    ).scalar_one()
    assert rows == 0


# --- Eager-uniform coverage across ingestion paths ---


def test_eager_uniform_upload_and_acquire_embed_every_chunk(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    scope_id = seed_scope(conn, pid)

    ingest_upload(
        conn,
        task_id=pid,
        chunks=["Upload chunk one.", "Upload chunk two."],
        source_locator="doc.pdf",
        metadata={},
        text_basis="full_text",
        embedder=StubEmbeddingBackend(),
    )
    context = AcquireContext(scope_id=scope_id, intent="Housing", context={})
    backends = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    acquire_sources(
        conn,
        task_id=pid,
        run_id=rid,
        context=context,
        backends=cast("list[SearchBackend]", backends),
        executed_calls=executed_calls_for(backends, context.intent),
        embedder=StubEmbeddingBackend(),
    )

    snapshot_ids = [
        row.source_snapshot_id
        for row in conn.execute(
            select(task_source_snapshot.c.source_snapshot_id).where(
                task_source_snapshot.c.task_id == pid
            )
        )
    ]
    chunk_ids = {
        row.chunk_id
        for row in conn.execute(
            select(chunk_table.c.chunk_id).where(chunk_table.c.source_snapshot_id.in_(snapshot_ids))
        )
    }
    assert chunk_ids, "the upload and fixture acquire backends must have produced chunks"

    embedded_chunk_ids = {
        row.chunk_id
        for row in conn.execute(
            select(chunk_embedding.c.chunk_id).where(chunk_embedding.c.chunk_id.in_(chunk_ids))
        )
    }
    assert embedded_chunk_ids == chunk_ids


# --- Live backend key hygiene ---


def test_openai_embedding_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingBackend()


class _FakeEmbeddingCreate:
    def __init__(self, outcomes: list[Any]) -> None:
        self._outcomes = outcomes
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeEmbeddingClient:
    def __init__(self, outcomes: list[Any]) -> None:
        self.embeddings = _FakeEmbeddingCreate(outcomes)


def _embedding_response(*vectors: list[float]) -> Any:
    return SimpleNamespace(
        data=[
            SimpleNamespace(index=index, embedding=vector) for index, vector in enumerate(vectors)
        ]
    )


class _FakeRateLimitError(Exception):
    def __init__(self, message: str, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.response = SimpleNamespace(
            headers={"retry-after": retry_after} if retry_after is not None else {}
        )


def test_openai_embedding_backend_raises_throttled_at_once_on_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 057 (D6): a 429 is the pool's to wait out; the backend makes one call."""
    sleeps: list[float] = []
    monkeypatch.setattr(embeddings_module, "RateLimitError", _FakeRateLimitError)
    monkeypatch.setattr(embeddings_module, "_sleep", sleeps.append)
    backend: OpenAIEmbeddingBackend = object.__new__(OpenAIEmbeddingBackend)
    fake_client = _FakeEmbeddingClient([_FakeRateLimitError("429", retry_after="7")])
    cast("Any", backend)._client = fake_client

    with pytest.raises(Throttled) as caught:
        backend.embed_texts(["hello"])

    assert (caught.value.provider, caught.value.retry_after_s) == ("openai", 7.0)
    assert sleeps == []
    assert len(fake_client.embeddings.calls) == 1


def test_embed_with_retry_waits_out_throttling_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One-off calls (query embedding) keep today's patience: the backoff curve,
    or the provider's Retry-After when it gives one."""
    sleeps: list[float] = []
    monkeypatch.setattr(embeddings_module, "RateLimitError", _FakeRateLimitError)
    monkeypatch.setattr(embeddings_module, "_sleep", sleeps.append)
    monkeypatch.setattr(random, "uniform", lambda _lo, _hi: 0.0)
    response = _embedding_response([0.25] * EMBEDDING_DIMENSIONS)
    backend: OpenAIEmbeddingBackend = object.__new__(OpenAIEmbeddingBackend)
    fake_client = _FakeEmbeddingClient(
        [_FakeRateLimitError("429"), _FakeRateLimitError("429", retry_after="3"), response]
    )
    cast("Any", backend)._client = fake_client

    vectors = embed_with_retry(backend, ["hello"], kind="query")

    assert vectors == [[0.25] * EMBEDDING_DIMENSIONS]
    assert sleeps == [2.0, 3.0]
    assert len(fake_client.embeddings.calls) == 3


def test_embed_with_retry_gives_up_after_the_last_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(embeddings_module, "RateLimitError", _FakeRateLimitError)
    monkeypatch.setattr(embeddings_module, "_sleep", sleeps.append)
    monkeypatch.setattr(random, "uniform", lambda _lo, _hi: 0.0)
    backend: OpenAIEmbeddingBackend = object.__new__(OpenAIEmbeddingBackend)
    fake_client = _FakeEmbeddingClient(
        [_FakeRateLimitError("429") for _ in range(EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS)]
    )
    cast("Any", backend)._client = fake_client

    with pytest.raises(Throttled):
        embed_with_retry(backend, ["hello"])

    assert sleeps == [2.0, 4.0, 8.0]
    assert len(fake_client.embeddings.calls) == EMBEDDING_RATE_LIMIT_MAX_ATTEMPTS


# --- Cohere Bedrock embedding backend ---


def _bedrock_client() -> tuple[Any, Stubber, list[dict[str, Any]]]:
    client = boto3.client(
        "bedrock-runtime",
        region_name="eu-west-2",
        aws_access_key_id="test",
        aws_secret_access_key="test",
    )
    captured: list[dict[str, Any]] = []
    client.meta.events.register(
        "before-parameter-build.bedrock-runtime.InvokeModel",
        lambda params, **_kwargs: captured.append(dict(params)),
    )
    stubber = Stubber(client)
    stubber.activate()
    return client, stubber, captured


def _bedrock_response(
    vectors: list[list[float]], *, tokens: str | None = "7", body: bytes | None = None
) -> dict[str, Any]:
    data = body if body is not None else json.dumps({"embeddings": {"float": vectors}}).encode()
    response: dict[str, Any] = {
        "body": StreamingBody(io.BytesIO(data), len(data)),
        "contentType": "application/json",
    }
    if tokens is not None:
        response["ResponseMetadata"] = {"HTTPHeaders": {"x-amzn-bedrock-input-token-count": tokens}}
    return response


def _expected_bedrock_params() -> dict[str, Any]:
    return {
        "modelId": embeddings_module.EMBEDDING_MODEL,
        "contentType": "application/json",
        "accept": "application/json",
        "body": ANY,
    }


@pytest.mark.parametrize(
    ("kind", "input_type"), [("document", "search_document"), ("query", "search_query")]
)
def test_cohere_embedding_backend_sends_complete_request(kind: str, input_type: str) -> None:
    client, stubber, captured = _bedrock_client()
    try:
        stubber.add_response(
            "invoke_model",
            _bedrock_response([[0.0] * EMBEDDING_DIMENSIONS]),
            _expected_bedrock_params(),
        )
        vectors = CohereEmbeddingBackend(client=client).embed_texts(
            ["policy"], kind=cast(Any, kind)
        )

        assert vectors == [[0.0] * EMBEDDING_DIMENSIONS]
        assert len(captured) == 1
        request = captured[0]
        assert request["modelId"] == embeddings_module.EMBEDDING_MODEL
        assert request["contentType"] == "application/json"
        assert request["accept"] == "application/json"
        assert json.loads(request["body"]) == {
            "texts": ["policy"],
            "input_type": input_type,
            "embedding_types": ["float"],
            "output_dimension": EMBEDDING_DIMENSIONS,
            "truncate": "NONE",
        }
    finally:
        stubber.deactivate()


def test_cohere_embedding_backend_batches_100_texts_in_order() -> None:
    client, stubber, _captured = _bedrock_client()
    texts = [f"text {index}" for index in range(100)]
    first = [[float(index)] * EMBEDDING_DIMENSIONS for index in range(API_BATCH_SIZE)]
    second = [[float(index)] * EMBEDDING_DIMENSIONS for index in range(API_BATCH_SIZE, 100)]
    try:
        stubber.add_response(
            "invoke_model", _bedrock_response(first, tokens="3"), _expected_bedrock_params()
        )
        stubber.add_response(
            "invoke_model", _bedrock_response(second, tokens="4"), _expected_bedrock_params()
        )
        assert CohereEmbeddingBackend(client=client).embed_texts(texts) == first + second
        assert embeddings_module.take_last_prompt_tokens() == 7
    finally:
        stubber.deactivate()


@pytest.mark.parametrize(
    ("response", "message"),
    [
        (_bedrock_response([], tokens=None), "length"),
        (_bedrock_response([[0.0] * (EMBEDDING_DIMENSIONS - 1)], tokens=None), "dimension"),
        (_bedrock_response([], tokens=None, body=b"not json"), "body"),
    ],
)
def test_cohere_embedding_backend_rejects_invalid_responses(
    response: dict[str, Any], message: str
) -> None:
    client, stubber, _captured = _bedrock_client()
    try:
        stubber.add_response("invoke_model", response, _expected_bedrock_params())
        with pytest.raises(RuntimeError, match=message):
            CohereEmbeddingBackend(client=client).embed_texts(["policy"])
    finally:
        stubber.deactivate()


def test_cohere_embedding_backend_does_not_retry_validation_error() -> None:
    client, stubber, _captured = _bedrock_client()
    try:
        stubber.add_client_error(
            "invoke_model",
            service_error_code="ValidationException",
            expected_params=_expected_bedrock_params(),
        )
        with pytest.raises(ClientError, match="ValidationException"):
            CohereEmbeddingBackend(client=client).embed_texts(["too long"])
    finally:
        stubber.deactivate()


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("ThrottlingException", "Rate exceeded"),
        ("ServiceUnavailableException", "Too many tokens, please wait before trying again."),
    ],
)
def test_cohere_embedding_backend_raises_throttled_after_one_call(
    monkeypatch: pytest.MonkeyPatch, code: str, message: str
) -> None:
    """Task 057 (D6): Bedrock's throttling (by code, or its "Too many tokens"
    message) is raised as ``Throttled`` after one call; nothing sleeps here."""
    client, stubber, captured = _bedrock_client()
    sleeps: list[float] = []
    monkeypatch.setattr(embeddings_module, "_sleep", sleeps.append)
    try:
        stubber.add_client_error(
            "invoke_model",
            service_error_code=code,
            service_message=message,
            expected_params=_expected_bedrock_params(),
        )
        with pytest.raises(Throttled) as caught:
            CohereEmbeddingBackend(client=client).embed_texts(["policy"])
        assert caught.value.provider == "cohere"
        assert len(captured) == 1 and sleeps == []
    finally:
        stubber.deactivate()


def test_cohere_embedding_backend_parks_bedrock_token_count() -> None:
    client, stubber, _captured = _bedrock_client()
    try:
        stubber.add_response(
            "invoke_model",
            _bedrock_response([[0.0] * EMBEDDING_DIMENSIONS], tokens="11"),
            _expected_bedrock_params(),
        )
        CohereEmbeddingBackend(client=client).embed_texts(["policy"])
        assert embeddings_module.take_last_prompt_tokens() == 11
    finally:
        stubber.deactivate()


def test_live_embedding_backend_selects_route(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        embeddings_module,
        "route",
        lambda: SimpleNamespace(embeddings=SimpleNamespace(backend="cohere")),
    )
    assert isinstance(embeddings_module.live_embedding_backend(), CohereEmbeddingBackend)

    monkeypatch.setattr(
        embeddings_module,
        "route",
        lambda: SimpleNamespace(embeddings=SimpleNamespace(backend="openai")),
    )
    monkeypatch.setattr(
        embeddings_module, "resolve_openai_client", lambda *_args, **_kwargs: object()
    )
    assert isinstance(embeddings_module.live_embedding_backend(), OpenAIEmbeddingBackend)


def test_chat_embedding_backend_selects_cohere_in_live_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps, "_live", lambda: True)
    monkeypatch.setattr(
        embeddings_module,
        "route",
        lambda: SimpleNamespace(embeddings=SimpleNamespace(backend="cohere")),
    )

    assert isinstance(deps.get_chat_embedding_backend(), CohereEmbeddingBackend)


def test_chat_embedding_backend_selects_openai_in_live_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps, "_live", lambda: True)
    monkeypatch.setattr(
        embeddings_module,
        "route",
        lambda: SimpleNamespace(embeddings=SimpleNamespace(backend="openai")),
    )
    monkeypatch.setattr(
        embeddings_module, "resolve_openai_client", lambda *_args, **_kwargs: object()
    )

    assert isinstance(deps.get_chat_embedding_backend(), OpenAIEmbeddingBackend)


def test_pending_chunks_with_old_profile_are_pending_for_cohere(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid, _rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    chunk_id = _insert_chunk(conn, snap_id, 1, "Old profile vector.")
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding_profile="openai_text_embedding_3_small_v1",
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": 19},
            embedding=[0.0] * EMBEDDING_DIMENSIONS,
            created_at=now(),
        )
    )
    monkeypatch.setattr(embeddings_module, "EMBEDDING_PROFILE", "cohere_embed_v4_1536_v1")

    _eligible, pending, chunks = embeddings_module._pending_chunks(conn, pid, max_hydrated=10)

    assert pending == 1
    assert [chunk.chunk_id for chunk in chunks] == [chunk_id]


# --- delete_task_data ---


def test_delete_task_data_removes_chunk_embedding(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    chunk_id = _insert_chunk(conn, snap_id, 1, "Content to embed and later delete.")
    embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)

    count_before = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == chunk_id)
    ).scalar_one()
    assert count_before >= 1

    conn.commit()
    delete_task_data(conn, pid)
    conn.commit()

    count_after = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == chunk_id)
    ).scalar_one()
    assert count_after == 0


# --- Judgment cases (Task 10) appended below ---


def test_judgment_derive_units_deterministic_and_gap_free() -> None:
    paragraph = (
        "Housing policy evidence is gathered from trials, modelling and guidance. "
        "The review tracks implementation, outcomes and equity. "
        "Findings are compared across local delivery settings.\n\n"
    )
    text = paragraph * 34
    assert len(text) > 6000

    first = derive_units(text)
    second = derive_units(text)

    assert first == second
    covered = [False] * len(text.rstrip())
    for unit in first:
        for position in range(unit["start"], unit["end"]):
            if position < len(covered):
                covered[position] = True
    assert all(covered)


def test_judgment_one_vector_per_unit_no_mean_pooling_path(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    sentence = "This long chunk should split into several embedding units. "
    chunk_content = sentence * 90
    chunk_id = _insert_chunk(conn, snap_id, 1, chunk_content)

    units = derive_units(chunk_content)
    assert len(units) > 1
    result = embed_pending_chunks(
        conn,
        embedder=StubEmbeddingBackend(),
        task_id=pid,
        run_id=rid,
    )

    assert result["embedded"] == 1
    rows = conn.execute(
        select(
            chunk_embedding.c.unit_index,
            chunk_embedding.c.unit_locator,
            chunk_embedding.c.embedding,
        )
        .where(chunk_embedding.c.chunk_id == chunk_id)
        .order_by(chunk_embedding.c.unit_index)
    ).fetchall()
    assert len(rows) == len(units)

    stub = StubEmbeddingBackend()
    # Each row holds the stub's floats for the text its locator points at.
    assert _assert_two_columns_agree(conn, [chunk_id]) == len(units)
    # The ORM read of the binary column parses back to the stub's floats (float32).
    embeddings = conn.execute(
        select(chunk_embedding.c.embedding)
        .where(chunk_embedding.c.chunk_id == chunk_id)
        .order_by(chunk_embedding.c.unit_index)
    ).scalars().all()
    for unit, embedding in zip(units, embeddings, strict=True):
        expected = stub.embed_texts([unit["text"]])[0]
        assert embedding is not None
        assert [_f32(v) for v in embedding] == [_f32(v) for v in expected]

    # No vector-pooling path. The request pool (task 057, D6: how many embedding
    # requests are in flight) is a different thing and is named as such.
    request_pool_names = {
        "AdaptivePool", "POOL_START_WIDTH", "POOL_CLEAN_RUN", "POOL_MAX_THROTTLES_PER_BATCH",
        "POOL_RETRY_AFTER_CAP_S", "PoolResult", "ThreadPoolExecutor",
    }
    assert not any(
        "mean" in name.casefold() or "pool" in name.casefold()
        for name in set(dir(embeddings_module)) - request_pool_names
    )


# --- Review-stack fixes (task 009 step 7) ---


def test_derive_units_drops_whitespace_only_units_and_renumbers() -> None:
    content = " " * (UNIT_CHAR_BUDGET + 500) + "Policy evidence sentence."
    units = derive_units(content)
    assert units, "non-whitespace content must yield at least one unit"
    assert all(unit["text"].strip() for unit in units)
    assert [unit["unit_index"] for unit in units] == list(range(len(units)))
    for unit in units:
        assert content[unit["start"] : unit["end"]] == unit["text"]


def test_embed_pending_chunks_whitespace_chunk_skipped_not_failed(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "\n\n\t  \n")
    _insert_chunk(conn, snap_id, 2, "A real chunk body.")

    result = embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)
    assert result["embedded"] == 1
    assert result["failed"] == 0
    assert result["skipped_no_units"] == 1

    # The unitless chunk stays pending and stays out of the failed count on re-runs.
    second = embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)
    assert second["embedded"] == 0
    assert second["failed"] == 0
    assert second["skipped_no_units"] == 1


def test_embed_pending_chunks_budget_path_returns_uniform_shape(conn: Connection) -> None:
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "One chunk over a zero budget.")

    result = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid, max_chunks=0
    )
    assert result["budget_exceeded"] == 1
    ok = embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), task_id=pid, run_id=rid)
    assert ok["budget_exceeded"] == 0
    assert set(result) == set(ok)


# --- The adaptive pool (task 057, D6) ---


class _QuotaFakeBackend:
    """A provider with an allowance: a request that arrives while ``limit``
    others are being served is throttled at once; the others take ``hold_s``.

    With every request taking the same time, "at most ``limit`` in flight" is
    the same as a token budget per minute: the pool must find that width.
    """

    mode = "stub"

    def __init__(self, limit: int, hold_s: float = 0.02) -> None:
        self.limit = limit
        self.hold_s = hold_s
        self._lock = threading.Lock()
        self._in_flight = 0
        self.peak = 0
        self.throttles = 0
        self.call_sizes: list[int] = []

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        with self._lock:
            self.call_sizes.append(len(texts))
            if self._in_flight >= self.limit:
                self.throttles += 1
                raise Throttled(provider="cohere")
            self._in_flight += 1
            self.peak = max(self.peak, self._in_flight)
        try:
            time.sleep(self.hold_s)
            return StubEmbeddingBackend().embed_texts(texts)
        finally:
            with self._lock:
                self._in_flight -= 1


def _widths(logs: Sequence[Mapping[str, Any]]) -> list[tuple[int, str]]:
    return [(e["width"], e["reason"]) for e in logs if e["event"] == "embed.pool_width"]


def test_adaptive_pool_converges_under_a_quota_and_never_splits_for_throttling(
    conn: Connection,
) -> None:
    """D6: under an allowance of 3 requests the pool, starting at 2 with a cap of
    8, climbs, is throttled, halves, and settles between 2 and 4 (at or just
    under the allowance, never at the cap); no batch is split because of
    throttling, and every chunk ends with a vector."""
    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    chunk_ids = [
        _insert_chunk(conn, snap_id, i + 1, f"Quota chunk {i} about housing.") for i in range(160)
    ]
    # hold_s 0.2: "in flight" is measured by the fake, so the requests of one pass must
    # still overlap when the pool's threads start late (under a full parallel suite a
    # 20 ms hold let the width climb past the allowance before any throttle; the
    # task 057 exit gate caught it once in about ten runs).
    backend = _QuotaFakeBackend(limit=3, hold_s=0.2)
    sleeps: list[float] = []
    pool = AdaptivePool(start=2, cap=8, clean_run=5, backoff=lambda _n: 0.5, sleep=sleeps.append)

    with capture_logs() as logs:
        result = embed_pending_chunks(
            conn, embedder=backend, task_id=pid, run_id=rid, batch_size=2, pool=pool
        )

    assert (result["embedded"], result["failed"]) == (160, 0)
    embedded = set(
        conn.execute(
            select(chunk_embedding.c.chunk_id).where(chunk_embedding.c.chunk_id.in_(chunk_ids))
        ).scalars()
    )
    assert embedded == set(chunk_ids)
    # Never split: every request carried a whole batch of 2.
    assert set(backend.call_sizes) == {2}
    assert backend.throttles >= 1
    widths = _widths(logs)
    assert (3, "clean_run") in widths  # it climbed
    first_throttle = next(i for i, (_w, why) in enumerate(widths) if why == "throttled")
    assert max(w for w, _why in widths) <= backend.limit + 1
    assert {w for w, _why in widths[first_throttle:]} <= {2, 3, 4}
    assert 2 <= pool.width <= backend.limit + 1
    # Each throttled round waited and said so, in the event stage_walls.py reads.
    rate_limited = [e for e in logs if e["event"] == "embedding.cohere_rate_limited"]
    assert len(rate_limited) == len(sleeps) >= 1
    assert all(e["sleep_s"] == 0.5 for e in rate_limited)


def test_adaptive_pool_climbs_to_its_cap_when_never_throttled() -> None:
    backend = _QuotaFakeBackend(limit=100, hold_s=0.005)
    pool = AdaptivePool(start=2, cap=4, clean_run=5, sleep=lambda _s: None)
    with capture_logs() as logs:
        results = list(pool.run(list(range(40)), lambda job: backend.embed_texts([str(job)])))
    assert sorted(r.index for r in results) == list(range(40))
    assert all(r.value is not None and r.error is None for r in results)
    assert _widths(logs) == [(3, "clean_run"), (4, "clean_run")]
    assert pool.width == 4
    assert backend.peak <= 4 and backend.throttles == 0


def test_adaptive_pool_round_with_a_throttle_grants_no_clean_credit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """task 057 review (Codex 10): a round that completes one throttle and
    ``clean_run`` successes together ends at the halved width; the successes do
    not widen the pool again before the backoff sleep."""
    # Every round waits for all its futures, so the first round completes all three.
    monkeypatch.setattr(
        embeddings_module, "wait",
        lambda fs, return_when: concurrent.futures.wait(
            fs, return_when=concurrent.futures.ALL_COMPLETED
        ),
    )
    seen: set[int] = set()

    def fn(job: int) -> int:
        if job == 0 and job not in seen:
            seen.add(job)
            raise Throttled(provider="cohere")
        return job

    pool = AdaptivePool(start=3, cap=8, clean_run=2, sleep=lambda _s: None)
    results = pool.run([0, 1, 2], fn)
    first = next(results)  # the first round has been processed
    assert pool.width == 1
    assert sorted([first.index, *(r.index for r in results)]) == [0, 1, 2]


def test_adaptive_pool_gives_a_batch_up_after_its_throttle_budget(conn: Connection) -> None:
    """A batch throttled ``max_throttles`` times comes back as an error result;
    ``embed_pending_chunks`` counts its chunks as ``deferred`` (not ``failed``),
    writes no vector and leaves them pending for the next pass; the width never
    drops below 1."""
    class _AlwaysThrottled:
        calls = 0

        def __call__(self, _job: int) -> list[float]:
            type(self).calls += 1
            raise Throttled(provider="openai", retry_after_s=120.0)

    sleeps: list[float] = []
    pool = AdaptivePool(start=4, cap=4, max_throttles=3, sleep=sleeps.append)
    results = list(pool.run([0, 1], _AlwaysThrottled()))
    assert sorted(r.index for r in results) == [0, 1]
    assert all(r.value is None and isinstance(r.error, Throttled) for r in results)
    assert _AlwaysThrottled.calls == 6
    assert pool.width == 1
    # Retry-After is honoured, capped at the backoff cap.
    assert set(sleeps) == {embeddings_module.POOL_RETRY_AFTER_CAP_S}

    # task 057 review (code-review 5): the pass reports the given-up batch as deferred.
    class _ThrottlingBackend:
        mode = "stub"

        def embed_texts(
            self, texts: list[str], *, kind: Literal["document", "query"] = "document"
        ) -> list[list[float]]:
            raise Throttled(provider="cohere")

    pid, rid = seed_task_and_run(conn)
    snap_id, _tss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "Deferred chunk about housing.")
    with capture_logs() as logs:
        result = embed_pending_chunks(
            conn, embedder=_ThrottlingBackend(), task_id=pid, run_id=rid,
            pool=AdaptivePool(start=1, cap=1, max_throttles=1, sleep=lambda _s: None),
        )
    assert (result["embedded"], result["failed"], result["deferred"]) == (0, 0, 1)
    events = {e["event"] for e in logs}
    assert "embed.batch_deferred" in events and "embed.batch_failed" not in events


def test_throttling_is_never_split_by_failure_isolation() -> None:
    class _Throttling:
        mode = "stub"

        def __init__(self) -> None:
            self.call_sizes: list[int] = []

        def embed_texts(
            self, texts: list[str], *, kind: Literal["document", "query"] = "document"
        ) -> list[list[float]]:
            self.call_sizes.append(len(texts))
            raise Throttled(provider="cohere")

    units = [
        embeddings_module._UnitWork(
            chunk_id=uuid.uuid4(), unit_index=0, start=0, end=1, text=f"unit {i}"
        )
        for i in range(16)
    ]
    embedder = _Throttling()
    with pytest.raises(Throttled):
        embeddings_module._embed_units_with_isolation(embedder, units)
    assert embedder.call_sizes == [16]


def test_embed_pending_chunks_with_connect_commits_each_batch(engine: Any) -> None:
    """With ``connect`` and no ``conn`` (the stage's embedding thread), the pass
    reads in one short transaction and each batch's rows are committed on their
    own, so another connection sees them at once."""
    with engine.connect() as c:
        pid, rid = seed_task_and_run(c)
        snap_id, _tss_id = seed_source(c, pid)
        chunk_ids = [_insert_chunk(c, snap_id, i + 1, f"Committed chunk {i}.") for i in range(5)]
        c.commit()
    try:
        result = embed_pending_chunks(
            None, connect=engine.begin, embedder=StubEmbeddingBackend(), task_id=pid,
            run_id=rid, batch_size=2, snapshot_ids=[snap_id],
        )
        assert result["embedded"] == 5
        with engine.connect() as c:
            n = c.execute(
                select(sa.func.count()).select_from(chunk_embedding)
                .where(chunk_embedding.c.chunk_id.in_(chunk_ids))
            ).scalar_one()
        assert n == 5
    finally:
        with engine.connect() as c:
            delete_task_data(c, pid)
            c.commit()
