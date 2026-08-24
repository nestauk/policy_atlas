"""Tests for the embeddings module — schema, unit derivation, embed pass, stubs."""

import random
import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import embeddings as embeddings_module
from policy_atlas.core.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_PROFILE,
    UNIT_CHAR_BUDGET,
    UNIT_POLICY,
    OpenAIEmbeddingBackend,
    StubEmbeddingBackend,
    derive_units,
    embed_pending_chunks,
    validate_vector,
)
from policy_atlas.core.schema import (
    chunk as chunk_table,
)
from policy_atlas.core.schema import (
    chunk_embedding,
    metadata,
    project_source_snapshot,
)
from policy_atlas.evidence_base.sourcing.acquire import (
    AcquireContext,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.evidence_base.sourcing.ingest_upload import ingest_upload
from tests.helpers import (
    delete_project_data,
    executed_calls_for,
    now,
    seed_project_and_run,
    seed_scope,
    seed_source,
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


# --- Migration / table presence ---


def test_table_count(conn: Connection) -> None:
    assert len(metadata.tables) == 33


def test_uq_chunk_embedding_unit_rejects_duplicate(conn: Connection) -> None:
    pid, _rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
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
            vector=vector,
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
                vector=vector,
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
    sentence = (
        "This is a sentence about policy analysis and evidence review of housing programs. "
    )
    content = sentence * 40
    assert len(content) > UNIT_CHAR_BUDGET

    units = derive_units(content)
    assert len(units) > 1

    starts = [unit["start"] for unit in units]
    assert starts == sorted(starts)
    assert len(set(starts)) == len(starts)

    for index, unit in enumerate(units):
        assert unit["unit_index"] == index
        assert unit["text"] == content[unit["start"]:unit["end"]]

    for prev_unit, cur_unit in zip(units, units[1:], strict=False):
        overlap = prev_unit["end"] - cur_unit["start"]
        assert 0 < overlap <= 260

    # derive_units is pure: the canonical content passed in is never mutated.
    assert content == sentence * 40


# --- embed_pending_chunks: idempotency, stamping, canonical-chunk immutability ---


def test_embed_pending_chunks_idempotent_and_stamps_every_row(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    chunk_ids = [
        _insert_chunk(conn, snap_id, i, f"Chunk body number {i}.") for i in range(1, 4)
    ]

    first = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid
    )
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

    # Canonical chunk content is untouched by the embed pass.
    for i, chunk_id in enumerate(chunk_ids, start=1):
        stored = conn.execute(
            select(chunk_table.c.content).where(chunk_table.c.chunk_id == chunk_id)
        ).scalar_one()
        assert stored == f"Chunk body number {i}."

    second = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid
    )
    assert second["embedded"] == 0
    assert second["already_embedded"] == 3


# --- Failure isolation ---


class _RaisingEmbedder:
    mode = "stub"

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedder always fails")


def test_embed_pending_chunks_failure_isolation_and_retry(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    chunk_id = _insert_chunk(conn, snap_id, 1, "This chunk will fail to embed.")

    result = embed_pending_chunks(conn, embedder=_RaisingEmbedder(), project_id=pid, run_id=rid)
    assert result["failed"] == 1
    assert result["embedded"] == 0

    rows = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == chunk_id)
    ).scalar_one()
    assert rows == 0

    retry = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid
    )
    assert retry["embedded"] == 1
    assert retry["failed"] == 0


class _PoisoningEmbedder:
    mode = "stub"

    def __init__(self, poison: str) -> None:
        self._poison = poison
        self.call_sizes: list[int] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
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

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("the embedder must never be called once the budget is exceeded")


def test_embed_pending_chunks_budget_guard_stops_before_any_call(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "Chunk A.")
    _insert_chunk(conn, snap_id, 2, "Chunk B.")

    result = embed_pending_chunks(
        conn,
        embedder=_RaisingIfCalledEmbedder(),
        project_id=pid,
        run_id=rid,
        max_chunks=1,
    )
    assert result["budget_exceeded"] == 1
    assert result["embedded"] == 0


# --- Project scoping ---


class _CountingEmbedder:
    mode = "stub"

    def __init__(self) -> None:
        self.seen_texts: list[str] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.seen_texts.extend(texts)
        return StubEmbeddingBackend().embed_texts(texts)


def test_embed_pending_chunks_project_scoped(conn: Connection) -> None:
    pid_a, rid_a = seed_project_and_run(conn)
    pid_b, _rid_b = seed_project_and_run(conn)
    snap_a, _pss_a = seed_source(conn, pid_a)
    snap_b, _pss_b = seed_source(conn, pid_b)
    _insert_chunk(conn, snap_a, 1, "Project A content.")
    b_chunk_id = _insert_chunk(conn, snap_b, 1, "Project B content.")

    embedder = _CountingEmbedder()
    embed_pending_chunks(conn, embedder=embedder, project_id=pid_a, run_id=rid_a)

    assert "Project B content." not in embedder.seen_texts
    rows = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == b_chunk_id)
    ).scalar_one()
    assert rows == 0


# --- Eager-uniform coverage across ingestion paths ---


def test_eager_uniform_upload_and_acquire_embed_every_chunk(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    scope_id = seed_scope(conn, pid)

    ingest_upload(
        conn,
        project_id=pid,
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
        project_id=pid,
        run_id=rid,
        context=context,
        backends=cast("list[SearchBackend]", backends),
        executed_calls=executed_calls_for(backends, context.intent),
        embedder=StubEmbeddingBackend(),
    )

    snapshot_ids = [
        row.source_snapshot_id
        for row in conn.execute(
            select(project_source_snapshot.c.source_snapshot_id).where(
                project_source_snapshot.c.project_id == pid
            )
        )
    ]
    chunk_ids = {
        row.chunk_id
        for row in conn.execute(
            select(chunk_table.c.chunk_id).where(
                chunk_table.c.source_snapshot_id.in_(snapshot_ids)
            )
        )
    }
    assert chunk_ids, "the upload and fixture acquire backends must have produced chunks"

    embedded_chunk_ids = {
        row.chunk_id
        for row in conn.execute(
            select(chunk_embedding.c.chunk_id).where(
                chunk_embedding.c.chunk_id.in_(chunk_ids)
            )
        )
    }
    assert embedded_chunk_ids == chunk_ids


# --- Live backend key hygiene ---


def test_openai_embedding_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingBackend()


class _FakeRateLimitError(Exception):
    pass


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
            SimpleNamespace(index=index, embedding=vector)
            for index, vector in enumerate(vectors)
        ]
    )


def test_openai_embedding_backend_rate_limit_backoff_then_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(embeddings_module, "RateLimitError", _FakeRateLimitError)
    monkeypatch.setattr(embeddings_module, "_sleep", sleeps.append)
    monkeypatch.setattr(random, "uniform", lambda _lo, _hi: 0.0)
    response = _embedding_response([0.25] * EMBEDDING_DIMENSIONS)
    backend: OpenAIEmbeddingBackend = object.__new__(OpenAIEmbeddingBackend)
    fake_client = _FakeEmbeddingClient([_FakeRateLimitError("429"), response])
    cast("Any", backend)._client = fake_client

    vectors = backend.embed_texts(["hello"])

    assert vectors == [[0.25] * EMBEDDING_DIMENSIONS]
    assert sleeps == [2.0]
    assert len(fake_client.embeddings.calls) == 2


def test_openai_embedding_backend_rate_limit_exhaustion_fails_loudly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr(embeddings_module, "RateLimitError", _FakeRateLimitError)
    monkeypatch.setattr(embeddings_module, "_sleep", sleeps.append)
    monkeypatch.setattr(random, "uniform", lambda _lo, _hi: 0.0)
    backend: OpenAIEmbeddingBackend = object.__new__(OpenAIEmbeddingBackend)
    fake_client = _FakeEmbeddingClient([_FakeRateLimitError("429") for _ in range(4)])
    cast("Any", backend)._client = fake_client

    with pytest.raises(_FakeRateLimitError):
        backend.embed_texts(["hello"])

    assert sleeps == [2.0, 4.0, 8.0]
    assert len(fake_client.embeddings.calls) == 4


# --- delete_project_data ---


def test_delete_project_data_removes_chunk_embedding(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    chunk_id = _insert_chunk(conn, snap_id, 1, "Content to embed and later delete.")
    embed_pending_chunks(conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid)

    count_before = conn.execute(
        select(sa.func.count())
        .select_from(chunk_embedding)
        .where(chunk_embedding.c.chunk_id == chunk_id)
    ).scalar_one()
    assert count_before >= 1

    conn.commit()
    delete_project_data(conn, pid)
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
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    sentence = "This long chunk should split into several embedding units. "
    chunk_content = sentence * 90
    chunk_id = _insert_chunk(conn, snap_id, 1, chunk_content)

    units = derive_units(chunk_content)
    assert len(units) > 1
    result = embed_pending_chunks(
        conn,
        embedder=StubEmbeddingBackend(),
        project_id=pid,
        run_id=rid,
    )

    assert result["embedded"] == 1
    rows = conn.execute(
        select(
            chunk_embedding.c.unit_index,
            chunk_embedding.c.unit_locator,
            chunk_embedding.c.vector,
        )
        .where(chunk_embedding.c.chunk_id == chunk_id)
        .order_by(chunk_embedding.c.unit_index)
    ).fetchall()
    assert len(rows) == len(units)

    stub = StubEmbeddingBackend()
    for row in rows:
        unit_text = chunk_content[row.unit_locator["start"]:row.unit_locator["end"]]
        assert row.vector == stub.embed_texts([unit_text])[0]

    assert not any(
        "mean" in name.casefold() or "pool" in name.casefold()
        for name in dir(embeddings_module)
    )


# --- Review-stack fixes (task 009 step 7) ---


def test_derive_units_drops_whitespace_only_units_and_renumbers() -> None:
    content = " " * (UNIT_CHAR_BUDGET + 500) + "Policy evidence sentence."
    units = derive_units(content)
    assert units, "non-whitespace content must yield at least one unit"
    assert all(unit["text"].strip() for unit in units)
    assert [unit["unit_index"] for unit in units] == list(range(len(units)))
    for unit in units:
        assert content[unit["start"]:unit["end"]] == unit["text"]


def test_embed_pending_chunks_whitespace_chunk_skipped_not_failed(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "\n\n\t  \n")
    _insert_chunk(conn, snap_id, 2, "A real chunk body.")

    result = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid
    )
    assert result["embedded"] == 1
    assert result["failed"] == 0
    assert result["skipped_no_units"] == 1

    # The unitless chunk stays pending and stays out of the failed count on re-runs.
    second = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid
    )
    assert second["embedded"] == 0
    assert second["failed"] == 0
    assert second["skipped_no_units"] == 1


def test_embed_pending_chunks_budget_path_returns_uniform_shape(conn: Connection) -> None:
    pid, rid = seed_project_and_run(conn)
    snap_id, _pss_id = seed_source(conn, pid)
    _insert_chunk(conn, snap_id, 1, "One chunk over a zero budget.")

    result = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid, max_chunks=0
    )
    assert result["budget_exceeded"] == 1
    ok = embed_pending_chunks(
        conn, embedder=StubEmbeddingBackend(), project_id=pid, run_id=rid
    )
    assert ok["budget_exceeded"] == 0
    assert set(result) == set(ok)
