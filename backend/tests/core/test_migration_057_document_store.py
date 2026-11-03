"""Task 057 revisions ``a3d8f6c1e2b4`` (rev1, expand) and ``b7e2c4a9d1f3`` (rev2, backfill).

Contract D2; plan P5. Covers: the upgrade and downgrade round trip; rerunning rev1
on a database that already has it; rev2 resuming after a failure part-way through
(a committed batch, then a crash, then ``upgrade head``); the frozen tokens SQL
against ``core.tokens``; the ``queued`` status and its two consistency checks; and
the ``Vector`` column type round-tripping 1,536 floats with no client library.

The ``engine`` fixture is session-scoped and the worker's database shared, so the
tests that move the chain always leave it at head and remove the rows they wrote.
"""

from __future__ import annotations

import importlib.util
import random
import struct
import time
import uuid
import warnings
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from alembic import command
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, null, select, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.embeddings import derive_units
from policy_atlas.core.schema import chunk_embedding, task_source_snapshot
from policy_atlas.core.tokens import word_tokens
from tests.conftest import _alembic_cfg
from tests.helpers import delete_task_data, now, seed_source, seed_task_and_run

PRE_REVISION = "152a234e2391"
REV1 = "a3d8f6c1e2b4"
REV2 = "b7e2c4a9d1f3"
_VERSIONS = Path(__file__).resolve().parents[2] / "alembic" / "versions"


def _load(filename: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"migration_{filename[:12]}", _VERSIONS / filename
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rev1() -> ModuleType:
    return _load("a3d8f6c1e2b4_document_store_expand.py")


def _rev2() -> ModuleType:
    return _load("b7e2c4a9d1f3_chunk_embedding_backfill.py")


def _columns(conn: Connection, table: str) -> dict[str, dict[str, Any]]:
    # SQLAlchemy does not know pgvector's type when it reads the catalogue and
    # says so; the names and nullability are all these tests read.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Did not recognize type 'vector'")
        return {str(c["name"]): dict(c) for c in inspect(conn).get_columns(table)}


def _valid_indexes(conn: Connection) -> set[str]:
    return {
        str(name)
        for (name,) in conn.execute(
            text(
                "SELECT c.relname FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
                "WHERE i.indisvalid AND c.relname IN "
                "('uq_source_snapshot_store_key', 'ix_chunk_embedding_tokens')"
            )
        )
    }


def _status_check(conn: Connection) -> str:
    return str(
        conn.execute(
            text(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conname = 'ck_tss_full_text_status'"
            )
        ).scalar_one()
    )


def _f32(value: float) -> float:
    return float(struct.unpack("f", struct.pack("f", value))[0])


def _vector(seed: int) -> list[float]:
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(1536)]


def _insert_chunk(
    conn: Connection, snapshot_id: uuid.UUID, sequence: int, content: str
) -> uuid.UUID:
    chunk_id = uuid.uuid4()
    conn.execute(
        text(
            "INSERT INTO chunk (chunk_id, source_snapshot_id, sequence, content, content_hash, "
            "locator, segmentation_policy, created_at) VALUES (:id, :snap, :seq, :content, "
            "'h', '{}'::jsonb, 'manual_v1', now())"
        ),
        {"id": chunk_id, "snap": snapshot_id, "seq": sequence, "content": content},
    )
    return chunk_id


def _insert_json_only_unit(
    conn: Connection,
    row_id: uuid.UUID,
    chunk_id: uuid.UUID,
    unit_index: int,
    start: int,
    end: int,
    vector: list[float],
) -> None:
    """A ``chunk_embedding`` row as the code before task 057 wrote it: JSON vector only."""
    conn.execute(
        text(
            "INSERT INTO chunk_embedding (chunk_embedding_id, chunk_id, embedding_profile, "
            "unit_policy, unit_index, unit_locator, vector, created_at) VALUES (:id, :chunk, "
            "'test_profile_057', 'embedding_unit_policy_v1', :idx, "
            "jsonb_build_object('start', :start, 'end', :end), CAST(:vector AS jsonb), now())"
        ),
        {
            "id": row_id,
            "chunk": chunk_id,
            "idx": unit_index,
            "start": start,
            "end": end,
            "vector": "[" + ", ".join(repr(v) for v in vector) + "]",
        },
    )


# --- 1. Round trip -----------------------------------------------------------------


def test_the_revisions_round_trip(engine: Engine) -> None:
    cfg = _alembic_cfg()
    task_id: uuid.UUID | None = None
    try:
        command.downgrade(cfg, PRE_REVISION)
        with engine.begin() as conn:
            assert "embedding" not in _columns(conn, "chunk_embedding")
            task_id, _run_id = seed_task_and_run(conn)
            # A full-text snapshot as the ingest writes it, and an envelope.
            full_text, _ = seed_source(
                conn,
                task_id,
                {"parse_profile": "pymupdf4llm_v1", "segmentation_policy": "pymupdf4llm_struct_v1"},
            )
            envelope, _ = seed_source(conn, task_id, {"parse_profile": "not_a_full_text"})
            conn.execute(
                text(
                    "UPDATE source_snapshot SET text_basis = 'abstract_only' "
                    "WHERE source_snapshot_id = :s"
                ),
                {"s": envelope},
            )

        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            snapshot = _columns(conn, "source_snapshot")
            assert {"body_hash", "parse_profile", "segmentation_policy"} <= set(snapshot)
            assert all(
                snapshot[c]["nullable"]
                for c in ("body_hash", "parse_profile", "segmentation_policy")
            )
            link = _columns(conn, "task_source_snapshot")
            assert link["ingested_by_run_id"]["nullable"] and link["fetched_from"]["nullable"]
            embedding = _columns(conn, "chunk_embedding")
            assert embedding["vector"]["nullable"] is True
            assert embedding["embedding"]["nullable"] is True
            assert embedding["tokens"]["nullable"] is True
            assert _valid_indexes(conn) == {
                "uq_source_snapshot_store_key",
                "ix_chunk_embedding_tokens",
            }
            assert "'queued'" in _status_check(conn)
            # parse_profile / segmentation_policy copied for full-text rows only.
            rows = {
                r.source_snapshot_id: (r.body_hash, r.parse_profile, r.segmentation_policy)
                for r in conn.execute(
                    text(
                        "SELECT source_snapshot_id, body_hash, parse_profile, segmentation_policy "
                        "FROM source_snapshot WHERE source_snapshot_id IN (:a, :b)"
                    ),
                    {"a": full_text, "b": envelope},
                )
            }
            assert rows[full_text] == (None, "pymupdf4llm_v1", "pymupdf4llm_struct_v1")
            assert rows[envelope] == (None, None, None)

            # Rows the downgrade must handle: a queued link row and a unit that only
            # the binary column holds.
            _snap, queued_tss = seed_source(conn, task_id)
            conn.execute(
                task_source_snapshot.update()
                .where(task_source_snapshot.c.task_source_snapshot_id == queued_tss)
                .values(full_text_status="queued")
            )
            chunk_id = _insert_chunk(conn, full_text, 1, "Binary only.")
            binary_only = uuid.uuid4()
            conn.execute(
                chunk_embedding.insert().values(
                    chunk_embedding_id=binary_only,
                    chunk_id=chunk_id,
                    embedding_profile="test_profile_057",
                    unit_policy="embedding_unit_policy_v1",
                    unit_index=0,
                    unit_locator={"start": 0, "end": 12},
                    vector=null(),
                    embedding=_vector(7),
                    tokens=["binary", "only"],
                    created_at=now(),
                )
            )

        command.downgrade(cfg, PRE_REVISION)
        with engine.begin() as conn:
            assert not {"body_hash", "parse_profile", "segmentation_policy"} & set(
                _columns(conn, "source_snapshot")
            )
            assert not {"ingested_by_run_id", "fetched_from"} & set(
                _columns(conn, "task_source_snapshot")
            )
            embedding = _columns(conn, "chunk_embedding")
            assert not {"embedding", "tokens"} & set(embedding)
            assert embedding["vector"]["nullable"] is False
            assert _valid_indexes(conn) == set()
            assert "'queued'" not in _status_check(conn)
            status = conn.execute(
                text(
                    "SELECT full_text_status FROM task_source_snapshot "
                    "WHERE task_source_snapshot_id = :t"
                ),
                {"t": queued_tss},
            ).scalar_one()
            assert status == "not_attempted"
            rebuilt = conn.execute(
                text("SELECT vector FROM chunk_embedding WHERE chunk_embedding_id = :i"),
                {"i": binary_only},
            ).scalar_one()
            assert [_f32(v) for v in rebuilt] == [_f32(v) for v in _vector(7)]
            # The old check refuses 'queued' again.
            with (
                pytest.raises(IntegrityError, match="ck_tss_full_text_status"),
                conn.begin_nested(),
            ):
                conn.execute(
                    text(
                        "UPDATE task_source_snapshot SET full_text_status = 'queued' "
                        "WHERE task_source_snapshot_id = :t"
                    ),
                    {"t": queued_tss},
                )
            # The extension stays installed (documented).
            assert conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")).first()

        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            assert {"embedding", "tokens"} <= set(_columns(conn, "chunk_embedding"))
            assert _valid_indexes(conn) == {
                "uq_source_snapshot_store_key",
                "ix_chunk_embedding_tokens",
            }
            # rev2 refilled the row the downgrade rebuilt as JSON.
            filled = conn.execute(
                text(
                    "SELECT embedding = (vector::text)::vector AS same, tokens "
                    "FROM chunk_embedding WHERE chunk_embedding_id = :i"
                ),
                {"i": binary_only},
            ).one()
            assert filled.same is True
            assert filled.tokens == ["binary", "only"]
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


def test_rev1_runs_again_on_a_database_that_has_it(engine: Engine) -> None:
    """Every rev1 statement is rerun-safe: running it twice changes nothing."""
    command.upgrade(_alembic_cfg(), "head")
    rev1 = _rev1()
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context), context.begin_transaction():
            rev1.upgrade()
    with engine.connect() as conn:
        assert _valid_indexes(conn) == {"uq_source_snapshot_store_key", "ix_chunk_embedding_tokens"}
        assert "'queued'" in _status_check(conn)
        assert {"embedding", "tokens"} <= set(_columns(conn, "chunk_embedding"))


def test_rev1_rebuilds_an_index_a_crash_left_invalid(engine: Engine) -> None:
    """A CONCURRENTLY build that crashed leaves an INVALID index; the rerun replaces it."""
    command.upgrade(_alembic_cfg(), "head")
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE pg_index SET indisvalid = false WHERE indexrelid = "
                "'ix_chunk_embedding_tokens'::regclass"
            )
        )
        conn.commit()
        assert "ix_chunk_embedding_tokens" not in _valid_indexes(conn)
    rev1 = _rev1()
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context), context.begin_transaction():
            rev1.upgrade()
    with engine.connect() as conn:
        assert _valid_indexes(conn) == {"uq_source_snapshot_store_key", "ix_chunk_embedding_tokens"}


# --- 2. Resume after a failure -------------------------------------------------------

# Unit texts that exercise the tokeniser: mixed case, digits, punctuation, unicode.
_LONG_CHUNK = ("Policy RCT-2024 showed a 12% rise; the effect (n=340) held. " * 80).strip()
_SHORT_CHUNKS = [
    "Don't over-count the Kelvin sign K or İstanbul; café résumé MIXED Case.",
    "",
    "   ",
]


class _InjectedCrash(RuntimeError):
    pass


def test_rev2_resumes_after_a_failure_part_way_through(engine: Engine) -> None:
    cfg = _alembic_cfg()
    rev2 = _rev2()
    task_id: uuid.UUID | None = None
    # Ids that sort before every random uuid4 in the table, so the first batch is ours.
    ids = [uuid.UUID(int=n) for n in range(1, 64)]
    expected: dict[uuid.UUID, tuple[list[float], list[str]]] = {}
    try:
        command.upgrade(cfg, "head")
        command.downgrade(cfg, REV1)
        with engine.begin() as conn:
            conn.execute(
                text("DELETE FROM chunk_embedding WHERE chunk_embedding_id = ANY(:ids)"),
                {"ids": ids},
            )
            task_id, _ = seed_task_and_run(conn)
            snapshot, _ = seed_source(conn, task_id)
            next_id = iter(ids)
            for sequence, content in enumerate([_LONG_CHUNK, *_SHORT_CHUNKS], start=1):
                chunk_id = _insert_chunk(conn, snapshot, sequence, content)
                units = derive_units(content) or [
                    {"unit_index": 0, "start": 0, "end": len(content), "text": content}
                ]
                for unit in units:
                    row_id = next(next_id)
                    vector = _vector(row_id.int)
                    _insert_json_only_unit(
                        conn,
                        row_id,
                        chunk_id,
                        unit["unit_index"],
                        unit["start"],
                        unit["end"],
                        vector,
                    )
                    expected[row_id] = (vector, sorted(word_tokens(unit["text"])))
        assert len(expected) >= 6

        calls = 0

        def crash_on_second_batch(
            conn: Connection, *, after: uuid.UUID, limit: int
        ) -> tuple[int, uuid.UUID | None]:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise _InjectedCrash("simulated crash after one committed batch")
            result: tuple[int, uuid.UUID | None] = rev2.backfill_batch(
                conn, after=after, limit=limit
            )
            return result

        with engine.connect() as conn:
            autocommit = conn.execution_options(isolation_level="AUTOCOMMIT")
            with pytest.raises(_InjectedCrash):
                rev2.run_backfill(autocommit, batch_size=2, batch_fn=crash_on_second_batch)

        with engine.connect() as conn:
            filled = {
                r.chunk_embedding_id: r.embedding is not None
                for r in conn.execute(
                    text(
                        "SELECT chunk_embedding_id, embedding FROM chunk_embedding "
                        "WHERE chunk_embedding_id = ANY(:ids)"
                    ),
                    {"ids": list(expected)},
                )
            }
            assert sum(filled.values()) == 2  # the committed first batch survived the crash
            assert filled[ids[0]] and filled[ids[1]]
            assert not any(filled[i] for i in list(expected)[2:])

        started = time.monotonic()
        command.upgrade(cfg, "head")
        elapsed = time.monotonic() - started
        assert elapsed < 60

        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT chunk_embedding_id, embedding, tokens, "
                    "embedding = (vector::text)::vector AS same FROM chunk_embedding "
                    "WHERE chunk_embedding_id = ANY(:ids)"
                ),
                {"ids": list(expected)},
            ).fetchall()
            assert len(rows) == len(expected)
            for row in rows:
                vector, tokens = expected[row.chunk_embedding_id]
                assert row.embedding is not None
                assert row.same is True
                stored = [float(v) for v in row.embedding.strip("[]").split(",")]
                assert [_f32(v) for v in stored] == [_f32(v) for v in vector]
                assert row.tokens == tokens
            # The Kelvin sign and the dotted capital I are not words (product rule).
            kelvin_row = next(r for r in rows if "kelvin" in r.tokens)
            assert "stanbul" in kelvin_row.tokens and "istanbul" not in kelvin_row.tokens
    finally:
        command.upgrade(cfg, "head")
        if task_id is not None:
            with engine.begin() as conn:
                delete_task_data(conn, task_id)


# --- 3. The frozen tokens SQL against core.tokens -----------------------------------

_PARITY_STRINGS = [
    "",
    "   ",
    "word",
    "Two Words",
    "UPPER lower MiXeD",
    "digits 123 and 4.56 and 7,890",
    "abc123def 9lives",
    "hyphen-ated well-being co-operate",
    "don't can't it's O'Brien",
    "punctuation!?;:,.()[]{}<>\"'/\\|@#$%^&*~`",
    "under_score snake_case_name",
    "tab\tnew\nline\r\nreturn",
    "café résumé naïve",
    "Ärger Übel Öl Straße",
    "Kelvin K sign and Ångström",
    "İstanbul ıd",
    "Ελλάδα Greek Σοφία",
    "Россия Cyrillic",
    "中文 Chinese 日本語",
    "emoji \U0001f600 mid\U0001f680word",
    "fullＷidth ＡＢＣ letters",
    "superscript x² and ① circled",
    "ligature ﬁne ﬂow",
    "repeat repeat Repeat REPEAT",
    "NHS UK 2030 net-zero CO2e",
    "e.g. i.e. etc. U.S.A.",
    "URL https://example.org/path?q=1&r=2",
    "email name@example.com",
    "zero​width non breaking",
    "Final 99% (p<0.05) [ref 12]",
]


def test_the_frozen_tokens_sql_matches_core_tokens(conn: Connection) -> None:
    assert len(_PARITY_STRINGS) == 30
    rev2 = _rev2()
    sql = text("SELECT " + rev2.TOKENS_SQL.format(unit="CAST(:s AS text)"))
    for value in _PARITY_STRINGS:
        assert conn.execute(sql, {"s": value}).scalar_one() == sorted(word_tokens(value)), value


# --- 4. The queued status --------------------------------------------------------------


def _set_link(conn: Connection, tss_id: uuid.UUID, **values: object) -> None:
    conn.execute(
        task_source_snapshot.update()
        .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
        .values(**values)
    )


def test_queued_is_admitted_with_no_snapshot_and_no_error(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    _snap, tss_id = seed_source(conn, task_id)
    _set_link(
        conn,
        tss_id,
        full_text_status="queued",
        ingested_by_run_id=run_id,
        fetched_from="https://x.invalid/a.pdf",
    )
    row = conn.execute(
        select(task_source_snapshot.c.full_text_status, task_source_snapshot.c.fetched_from).where(
            task_source_snapshot.c.task_source_snapshot_id == tss_id
        )
    ).one()
    assert row == ("queued", "https://x.invalid/a.pdf")


def test_queued_with_a_snapshot_is_refused(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    snap, tss_id = seed_source(conn, task_id)
    with pytest.raises(IntegrityError, match="ck_tss_full_text_consistent"):
        _set_link(conn, tss_id, full_text_status="queued", full_text_snapshot_id=snap)


def test_queued_with_an_error_is_refused(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    _snap, tss_id = seed_source(conn, task_id)
    with pytest.raises(IntegrityError, match="ck_tss_full_text_error_presence"):
        _set_link(conn, tss_id, full_text_status="queued", full_text_error="not_ready")


# --- 5. The Vector column type ---------------------------------------------------------


def test_the_vector_type_round_trips_1536_floats(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    snap, _ = seed_source(conn, task_id)
    chunk_id = _insert_chunk(conn, snap, 1, "Vector round trip.")
    values = _vector(2026)
    values[0], values[1], values[2] = 0.0, 1e-30, -123456.789
    row_id = uuid.uuid4()
    insert = chunk_embedding.insert().values(
        chunk_embedding_id=row_id,
        chunk_id=chunk_id,
        embedding_profile="test_profile_057",
        unit_policy="embedding_unit_policy_v1",
        unit_index=0,
        unit_locator={"start": 0, "end": 18},
        vector=values,
        embedding=values,
        tokens=sorted(word_tokens("Vector round trip.")),
        created_at=now(),
    )
    # Sent as text with a cast in the SQL: no pgvector client library involved.
    compiled = str(insert.compile(dialect=conn.dialect))
    assert "CAST(" in compiled and "AS vector(1536))" in compiled
    conn.execute(insert)
    stored = conn.execute(
        select(chunk_embedding.c.embedding, chunk_embedding.c.tokens).where(
            chunk_embedding.c.chunk_embedding_id == row_id
        )
    ).one()
    assert stored.embedding is not None and len(stored.embedding) == 1536
    assert [_f32(v) for v in stored.embedding] == [_f32(v) for v in values]
    assert stored.tokens == ["round", "trip", "vector"]
    # The database agrees the two columns hold the same vector.
    assert (
        conn.execute(
            text(
                "SELECT embedding = (vector::text)::vector FROM chunk_embedding "
                "WHERE chunk_embedding_id = :i"
            ),
            {"i": row_id},
        ).scalar_one()
        is True
    )
    # A NULL stays NULL both ways.
    nulled = uuid.uuid4()
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=nulled,
            chunk_id=chunk_id,
            embedding_profile="test_profile_057",
            unit_policy="embedding_unit_policy_v1",
            unit_index=1,
            unit_locator={"start": 0, "end": 18},
            vector=values,
            embedding=None,
            created_at=now(),
        )
    )
    assert (
        conn.execute(
            select(chunk_embedding.c.embedding).where(
                chunk_embedding.c.chunk_embedding_id == nulled
            )
        ).scalar_one()
        is None
    )
