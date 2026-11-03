"""The one-path full-text stage and the per-document function (task 057, P8 and P9).

Most tests here commit: the in-process queue client's worker threads, and every
"second connection" below, can only see committed rows. Each test removes what it
committed. The document store is shared across tasks, so each test uses bytes no
other test uses, except the fixture-corpus comparison, which deletes each leg's
snapshots before the next leg starts.
"""

import hashlib
import threading
import time
import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Connection, Engine
from structlog.testing import capture_logs

from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import chunk_embedding, source_snapshot, task_source_snapshot
from policy_atlas.evidence_search.sourcing import ingest_document as ingest_document_module
from policy_atlas.evidence_search.sourcing import ingest_full_text
from policy_atlas.evidence_search.sourcing.ingest_document import ingest_document
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    FetchResult,
    parse_profile_for,
)
from policy_atlas.evidence_search.sourcing.ingest_queue import (
    MESSAGE_SCHEMA,
    IngestMessage,
    SendResult,
    build_queue_client,
    inline_connect,
    new_message,
)
from tests.evidence_search.sourcing.test_ingest_full_text import (
    EXPECTED_BY_REASON,
    EXPECTED_ELIGIBLE,
    EXPECTED_FETCH_FAILED,
    EXPECTED_INGESTED,
    EXPECTED_PARSE_FAILED,
    _corpus_state,
    _ScriptedFetcher,
    _seed_relevant_acquired,
    _summary_without_wall_clock,
    local_queue,
    run_ingest,
    seed_corpus,
)
from tests.helpers import delete_task_data, seed_run, seed_scope, seed_task_and_run


def _plain_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:  # noqa: ARG001
    """Picklable parse double that names the profile the store key is looked up under."""
    profile, policy = parse_profile_for(content_type)
    text_ = body.decode()
    return {
        "status": "ok",
        "chunks": [{"content": part, "locator": {"paragraph": i}}
                   for i, part in enumerate(text_.split("|"), start=1)],
        "parse_profile": profile,
        "segmentation_policy": policy,
    }


def _unique_body() -> bytes:
    """Bytes no other test (or earlier run) has put in the store."""
    return f"first part {uuid.uuid4()}|second part|third part".encode()


@contextmanager
def _committed(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as c:
        yield c
        c.commit()


def _seed_doc_task(
    engine: Engine, url: str
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Commit a task with one eligible document whose only candidate is ``url``."""
    with _committed(engine) as c:
        task_id, run_id = seed_task_and_run(c)
        scope_id = seed_scope(c, task_id)
        tss_id = _seed_relevant_acquired(
            c, task_id, run_id, scope_id,
            {"backend": "overton", "provider_fields": {"pdf_url": url}},
        )
    return task_id, run_id, scope_id, tss_id


def _set_status(engine: Engine, tss_id: uuid.UUID, status: str, error: str | None = None) -> None:
    with _committed(engine) as c:
        c.execute(
            task_source_snapshot.update()
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
            .values(full_text_status=status, full_text_error=error, full_text_snapshot_id=None)
        )


def _link(engine: Engine, tss_id: uuid.UUID) -> Any:
    with engine.connect() as c:
        return c.execute(
            select(task_source_snapshot).where(
                task_source_snapshot.c.task_source_snapshot_id == tss_id
            )
        ).one()


def _snapshots_for(engine: Engine, body: bytes) -> list[Any]:
    with engine.connect() as c:
        return list(c.execute(
            select(source_snapshot).where(
                source_snapshot.c.body_hash == hashlib.sha256(body).hexdigest()
            )
        ).fetchall())


def _cleanup(engine: Engine, task_ids: Sequence[uuid.UUID], bodies: Sequence[bytes]) -> None:
    """Delete the tasks, then any snapshot of ``bodies`` left without a link."""
    hashes = [hashlib.sha256(b).hexdigest() for b in bodies]
    with _committed(engine) as c:
        # A snapshot shared by two tasks: unlink every task first, so deleting one
        # task's snapshots never trips another task's foreign key.
        c.execute(
            task_source_snapshot.update()
            .where(task_source_snapshot.c.task_id.in_(list(task_ids)))
            .values(full_text_snapshot_id=None, full_text_status="not_attempted",
                    full_text_error=None)
        )
        for task_id in task_ids:
            delete_task_data(c, task_id)
        if hashes:
            snap_ids = select(source_snapshot.c.source_snapshot_id).where(
                source_snapshot.c.body_hash.in_(hashes)
            )
            chunk_ids = select(chunk_table.c.chunk_id).where(
                chunk_table.c.source_snapshot_id.in_(snap_ids)
            )
            c.execute(chunk_embedding.delete().where(chunk_embedding.c.chunk_id.in_(chunk_ids)))
            c.execute(chunk_table.delete().where(chunk_table.c.source_snapshot_id.in_(snap_ids)))
            c.execute(source_snapshot.delete().where(source_snapshot.c.body_hash.in_(hashes)))


def _fetcher_for(url: str, body: bytes) -> _ScriptedFetcher:
    return _ScriptedFetcher(
        {url: FetchResult(status="ok", content_type="text/plain", body=body)}
    )


# --- The stage on the committed fixture corpus: worker counts and modes ---


def test_fixture_corpus_same_statuses_inline_and_at_workers_1_and_4(engine: Engine) -> None:
    """N6: the committed fixture corpus gives today's statuses and reasons, and
    byte-identical chunks, on the in-process thread pool at 1 and 4 workers and in
    the inline mode on a rolled-back connection. Each committed leg's snapshots are
    deleted before the next leg, so every leg really parses (no store hits)."""
    legs: dict[str, tuple[dict[str, Any], list[tuple[Any, ...]]]] = {}
    for workers in (1, 4):
        with engine.connect() as c:
            task_id, run_id, scope_id = seed_corpus(c)
            c.commit()
            try:
                summary = run_ingest(
                    c, task_id, run_id, scope_id,
                    queue=local_queue(engine, workers=workers), connect=engine.begin,
                )
                c.commit()
                legs[f"workers={workers}"] = (summary, _corpus_state(c, task_id))
            finally:
                c.rollback()
                delete_task_data(c, task_id)
                c.commit()
    with engine.connect() as c:
        trans = c.begin()
        try:
            task_id, run_id, scope_id = seed_corpus(c)
            summary = run_ingest(c, task_id, run_id, scope_id)
            legs["inline"] = (summary, _corpus_state(c, task_id))
        finally:
            trans.rollback()

    for name, (summary, _) in legs.items():
        assert summary["eligible"] == EXPECTED_ELIGIBLE, name
        assert summary["ingested"] == EXPECTED_INGESTED, name
        assert summary["already_in_store"] == 0, name
        assert summary["fetch_failed"] == EXPECTED_FETCH_FAILED, name
        assert summary["parse_failed"] == EXPECTED_PARSE_FAILED, name
        assert summary["by_reason"] == EXPECTED_BY_REASON, name
    reference_summary, reference_state = legs["workers=1"]
    for name in ("workers=4", "inline"):
        summary, state = legs[name]
        comparable = {k: v for k, v in summary.items() if k != "embed"}
        reference = {k: v for k, v in reference_summary.items() if k != "embed"}
        assert _summary_without_wall_clock(comparable) == _summary_without_wall_clock(
            reference
        ), name
        assert state == reference_state, name


# --- The per-document function on committed data (N2, N9) ---


def test_late_write_leaves_the_row_and_keeps_the_snapshot_then_a_store_hit_skips_the_parse(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """D4: the stage closes the row (``not_ready``) while the function is working;
    the function's guarded update changes nothing on the row, and its snapshot is
    in the store. The next run's function finds it by store key and links it
    without parsing (``parse_profile_for`` consulted before the parse)."""
    url = f"https://example.org/late-{uuid.uuid4()}.txt"
    body = _unique_body()
    task_id, run_id, _, tss_id = _seed_doc_task(engine, url)
    try:
        _set_status(engine, tss_id, "queued")
        real_find = ingest_document_module.find_in_store

        def close_then_find(*args: Any, **kwargs: Any) -> Any:
            _set_status(engine, tss_id, "fetch_failed", "not_ready")  # the stage, elsewhere
            return real_find(*args, **kwargs)

        monkeypatch.setattr(ingest_document_module, "find_in_store", close_then_find)
        late = ingest_document(
            engine.begin, tss_id=tss_id, run_id=run_id, fetcher=_fetcher_for(url, body),
            parse_fn=_plain_parse, deadline=None,
        )
        assert late.resolution == "late" and not late.written
        row = _link(engine, tss_id)
        assert (row.full_text_status, row.full_text_error) == ("fetch_failed", "not_ready")
        assert row.full_text_snapshot_id is None
        [snapshot] = _snapshots_for(engine, body)
        assert (snapshot.parse_profile, snapshot.segmentation_policy) == parse_profile_for(
            "text/plain"
        )

        # The next run: the row is queued again; the store has the parse.
        monkeypatch.setattr(ingest_document_module, "find_in_store", real_find)
        parses: list[bytes] = []
        real_parse = ingest_full_text.run_parse_worker

        def recording_parse(fn: Any, b: bytes, *args: Any, **kwargs: Any) -> Any:
            parses.append(b)
            return real_parse(fn, b, *args, **kwargs)

        monkeypatch.setattr(ingest_document_module, "run_parse_worker", recording_parse)
        _set_status(engine, tss_id, "queued")
        run_2 = seed_run_committed(engine, task_id)
        hit = ingest_document(
            engine.begin, tss_id=tss_id, run_id=run_2, fetcher=_fetcher_for(url, body),
            parse_fn=_plain_parse, deadline=None,
        )
        assert hit.resolution == "ingested" and hit.already_in_store
        assert parses == []
        row = _link(engine, tss_id)
        assert row.full_text_status == "ingested"
        assert row.full_text_snapshot_id == snapshot.source_snapshot_id
        assert row.ingested_by_run_id == run_2
        assert row.fetched_from == url

        # A second delivery of the same message: the row is no longer queued.
        again = ingest_document(
            engine.begin, tss_id=tss_id, run_id=run_2, fetcher=_fetcher_for(url, body),
            parse_fn=_plain_parse, deadline=None,
        )
        assert again.resolution == "not_queued"
        assert _link(engine, tss_id).full_text_snapshot_id == snapshot.source_snapshot_id
    finally:
        _cleanup(engine, [task_id], [body])


def seed_run_committed(engine: Engine, task_id: uuid.UUID) -> uuid.UUID:
    with _committed(engine) as c:
        return seed_run(c, task_id)


def _barrier_lookup(
    monkeypatch: pytest.MonkeyPatch, parties: int
) -> threading.Barrier:
    """Make every caller miss the store and wait for the others before parsing."""
    barrier = threading.Barrier(parties, timeout=30)

    def miss_together(*args: Any, **kwargs: Any) -> None:  # noqa: ARG001
        barrier.wait()
        return None

    monkeypatch.setattr(ingest_document_module, "find_in_store", miss_together)
    return barrier


def _run_together(calls: Sequence[Any]) -> list[Any]:
    results: list[Any] = [None] * len(calls)
    errors: list[BaseException] = []

    def run(i: int) -> None:
        try:
            results[i] = calls[i]()
        except BaseException as exc:  # surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(len(calls))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(60)
    assert not errors, errors
    return results


def test_two_connections_race_on_the_same_store_key(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two tasks' documents with the same bytes, parsed at once on two real
    connections: one snapshot (one set of chunks), both link rows ingested to it."""
    body = _unique_body()
    url_a = f"https://example.org/race-a-{uuid.uuid4()}.txt"
    url_b = f"https://example.org/race-b-{uuid.uuid4()}.txt"
    task_a, run_a, _, tss_a = _seed_doc_task(engine, url_a)
    task_b, run_b, _, tss_b = _seed_doc_task(engine, url_b)
    try:
        _set_status(engine, tss_a, "queued")
        _set_status(engine, tss_b, "queued")
        _barrier_lookup(monkeypatch, 2)
        outcomes = _run_together([
            lambda: ingest_document(
                engine.begin, tss_id=tss_a, run_id=run_a, fetcher=_fetcher_for(url_a, body),
                parse_fn=_plain_parse, deadline=None,
            ),
            lambda: ingest_document(
                engine.begin, tss_id=tss_b, run_id=run_b, fetcher=_fetcher_for(url_b, body),
                parse_fn=_plain_parse, deadline=None,
            ),
        ])
        assert [o.resolution for o in outcomes] == ["ingested", "ingested"]
        [snapshot] = _snapshots_for(engine, body)
        link_a, link_b = _link(engine, tss_a), _link(engine, tss_b)
        assert link_a.full_text_snapshot_id == link_b.full_text_snapshot_id
        assert link_a.full_text_snapshot_id == snapshot.source_snapshot_id
        with engine.connect() as c:
            n_chunks = c.execute(
                select(sa.func.count()).select_from(chunk_table)
                .where(chunk_table.c.source_snapshot_id == snapshot.source_snapshot_id)
            ).scalar_one()
        assert n_chunks == 3  # one set, not two
    finally:
        _cleanup(engine, [task_a, task_b], [body])


def test_two_connections_race_on_the_same_link_row(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same message handled twice at once (a redelivery): one call resolves
    the row, the other finds it no longer queued and changes nothing."""
    body = _unique_body()
    url = f"https://example.org/same-row-{uuid.uuid4()}.txt"
    task_id, run_id, _, tss_id = _seed_doc_task(engine, url)
    try:
        _set_status(engine, tss_id, "queued")
        _barrier_lookup(monkeypatch, 2)
        call = lambda: ingest_document(  # noqa: E731
            engine.begin, tss_id=tss_id, run_id=run_id, fetcher=_fetcher_for(url, body),
            parse_fn=_plain_parse, deadline=None,
        )
        outcomes = _run_together([call, call])
        assert sorted(o.resolution for o in outcomes) == ["ingested", "late"]
        assert len(_snapshots_for(engine, body)) == 1
        row = _link(engine, tss_id)
        assert row.full_text_status == "ingested"
        assert row.full_text_snapshot_id == _snapshots_for(engine, body)[0].source_snapshot_id
    finally:
        _cleanup(engine, [task_id], [body])


# --- The stage on committed data (N3, N9) ---


def test_orphaned_queued_rows_are_queued_again_at_start(engine: Engine) -> None:
    """A row left ``queued`` by a run that died is sent again and resolved."""
    body = _unique_body()
    url = f"https://example.org/orphan-{uuid.uuid4()}.txt"
    task_id, run_id, scope_id, tss_id = _seed_doc_task(engine, url)
    try:
        _set_status(engine, tss_id, "queued")  # the dead run's leftover
        with engine.connect() as c, capture_logs() as logs:
            summary = run_ingest(
                c, task_id, run_id, scope_id,
                queue=local_queue(engine, workers=1, fetcher=_fetcher_for(url, body),
                                  parse_fn=_plain_parse),
                connect=engine.begin,
            )
            c.commit()
        assert summary["attempted"] == 1 and summary["ingested"] == 1
        assert [e["count"] for e in logs if e["event"] == "ingest.orphans_requeued"] == [1]
        assert _link(engine, tss_id).full_text_status == "ingested"
    finally:
        _cleanup(engine, [task_id], [body])


def test_already_in_store_on_a_second_task_with_the_same_bytes(engine: Engine) -> None:
    """N9: the second task's document links the first task's snapshot without a
    parse; one snapshot, two link rows, and the shared row carries no task, user,
    run or URL key in any column or JSON field."""
    body = _unique_body()
    url_a = f"https://example.org/shared-a-{uuid.uuid4()}.txt?token=SECRET"
    url_b = f"https://example.org/shared-b-{uuid.uuid4()}.txt"
    task_a, run_a, scope_a, tss_a = _seed_doc_task(engine, url_a)
    task_b, run_b, scope_b, tss_b = _seed_doc_task(engine, url_b)
    try:
        summaries = []
        for task_id, run_id, scope_id, url in (
            (task_a, run_a, scope_a, url_a), (task_b, run_b, scope_b, url_b),
        ):
            with engine.connect() as c:
                summaries.append(run_ingest(
                    c, task_id, run_id, scope_id,
                    queue=local_queue(engine, workers=1, fetcher=_fetcher_for(url, body),
                                      parse_fn=_plain_parse),
                    connect=engine.begin,
                ))
                c.commit()
        first, second = summaries
        assert (first["ingested"], first["already_in_store"]) == (1, 0)
        assert (second["ingested"], second["already_in_store"]) == (1, 1)
        for summary in summaries:
            assert summary["eligible"] == (
                summary["ingested"] + summary["already_ingested"]
                + summary["fetch_failed"] + summary["parse_failed"]
            )
        [snapshot] = _snapshots_for(engine, body)
        link_a, link_b = _link(engine, tss_a), _link(engine, tss_b)
        assert link_a.full_text_snapshot_id == link_b.full_text_snapshot_id
        assert link_a.full_text_snapshot_id == snapshot.source_snapshot_id
        # The breadcrumbs are on each task's own link row.
        assert (link_a.ingested_by_run_id, link_a.fetched_from) == (run_a, url_a)
        assert (link_b.ingested_by_run_id, link_b.fetched_from) == (run_b, url_b)
        # The shared row: no per-task key, as a column or inside the JSON.
        assert set(source_snapshot.c.keys()) == {
            "source_snapshot_id", "content_hash", "text_basis", "source_locator",
            "metadata", "created_at", "body_hash", "parse_profile", "segmentation_policy",
        }
        assert set(snapshot.metadata) == {
            "parse_profile", "segmentation_policy", "content_type", "source_kind",
        }
        flat = repr(snapshot.metadata)
        for value in (task_a, task_b, run_a, run_b, tss_a, tss_b):
            assert str(value) not in flat
        assert url_b not in flat and "SECRET" not in flat
    finally:
        _cleanup(engine, [task_a, task_b], [body])


def _plain_parse_slowly(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    time.sleep(0.4)
    return _plain_parse(body, content_type, thin_min)


def test_connection_count_stays_within_the_pool_during_a_4_worker_run(engine: Engine) -> None:
    """Each worker thread holds at most one connection at a time: a 4-worker run
    on its own engine (pool 5, no overflow: the component connection plus one per
    worker) never needs more, sampled from ``pg_stat_activity``."""
    tag = f"ingest-pool-{uuid.uuid4().hex[:8]}"
    small = create_engine(
        engine.url, pool_size=5, max_overflow=0, pool_timeout=20,
        connect_args={"application_name": tag},
    )
    bodies = [_unique_body() for _ in range(8)]
    urls = [f"https://example.org/pool-{i}-{uuid.uuid4()}.txt" for i in range(8)]
    with _committed(engine) as c:
        task_id, run_id = seed_task_and_run(c)
        scope_id = seed_scope(c, task_id)
        for url in urls:
            _seed_relevant_acquired(
                c, task_id, run_id, scope_id,
                {"backend": "overton", "provider_fields": {"pdf_url": url}},
            )
    script: dict[str, FetchResult | BaseException] = {
        url: FetchResult(status="ok", content_type="text/plain", body=body)
        for url, body in zip(urls, bodies, strict=True)
    }
    fetcher = _ScriptedFetcher(script)
    peak = 0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        with engine.connect() as probe:
            while not stop.is_set():
                n = probe.execute(
                    text("SELECT count(*) FROM pg_stat_activity WHERE application_name = :t"),
                    {"t": tag},
                ).scalar_one()
                probe.commit()
                peak = max(peak, int(n))
                time.sleep(0.02)

    sampler = threading.Thread(target=sample)
    sampler.start()
    try:
        with small.connect() as component:
            summary = run_ingest(
                component, task_id, run_id, scope_id,
                queue=local_queue(small, workers=4, fetcher=fetcher,
                                  parse_fn=_plain_parse_slowly),
                connect=small.begin,
            )
            component.commit()
        assert summary["ingested"] == 8
    finally:
        stop.set()
        sampler.join(10)
        small.dispose()
        _cleanup(engine, [task_id], bodies)
    assert 2 <= peak <= 5


# --- The stage's waiting rules with a fake queue (N3), on the rolled-back conn ---


class _FakeQueue:
    """Records the messages; ingests the first ``ingest_first`` inline; refuses some."""

    def __init__(
        self, conn: Connection, fetcher: Any, *, ingest_first: int = 0,
        refuse: int = 0,
    ) -> None:
        self.conn = conn
        self.fetcher = fetcher
        self.ingest_first = ingest_first
        self.refuse = refuse
        self.messages: list[IngestMessage] = []

    def send(self, messages: Sequence[IngestMessage]) -> SendResult:
        self.messages.extend(messages)
        for message in messages[: self.ingest_first]:
            ingest_document(
                inline_connect(self.conn), tss_id=uuid.UUID(message["link_row_id"]),
                run_id=uuid.UUID(message["run_id"]), fetcher=self.fetcher,
                parse_fn=_plain_parse, deadline=None,
            )
        refused = [m["link_row_id"] for m in messages[len(messages) - self.refuse:]] \
            if self.refuse else []
        return SendResult(
            sent=[m["link_row_id"] for m in messages if m["link_row_id"] not in refused],
            failed={link_id: "throttled" for link_id in refused},
        )


class _FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _seed_docs(conn: Connection, n: int) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, Any]:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    script: dict[str, FetchResult | BaseException] = {}
    for i in range(n):
        url = f"https://example.org/fake-{i}-{uuid.uuid4()}.txt"
        _seed_relevant_acquired(
            conn, task_id, run_id, scope_id,
            {"backend": "overton", "provider_fields": {"pdf_url": url}},
        )
        script[url] = FetchResult(status="ok", content_type="text/plain", body=_unique_body())
    return task_id, run_id, scope_id, _ScriptedFetcher(script)


def test_deadline_marks_the_rest_not_ready_and_a_refused_send_send_failed(
    conn: Connection,
) -> None:
    """Queued-mode waiting (N3, D4): one document resolves early, one message is
    refused by the queue (``send_failed`` at once), the rest are still queued at
    the deadline and become ``fetch_failed`` / ``not_ready``. The counts keep their
    invariant; the messages carry the two ids and the schema version only."""
    task_id, run_id, scope_id, fetcher = _seed_docs(conn, 4)
    queue = _FakeQueue(conn, fetcher, ingest_first=1, refuse=1)
    clock = _FakeClock()
    summary = run_ingest(
        conn, task_id, run_id, scope_id, fetcher=fetcher,
        queue=queue, stage_deadline_s=600.0, clock=clock.clock, sleep=clock.sleep,
    )
    assert summary["ingested"] == 1
    assert summary["fetch_failed"] == 3
    assert summary["by_reason"] == {"send_failed": 1, "not_ready": 2}
    assert summary["eligible"] == 4 == (
        summary["ingested"] + summary["already_ingested"]
        + summary["fetch_failed"] + summary["parse_failed"]
    )
    assert summary["bytes_fetched"] is None  # this queue cannot report it
    assert sum(clock.sleeps) >= 600.0
    assert all(set(m) == {"link_row_id", "run_id", "schema"} for m in queue.messages)
    assert {m["schema"] for m in queue.messages} == {MESSAGE_SCHEMA}
    assert {m["run_id"] for m in queue.messages} == {str(run_id)}
    statuses = sorted(
        (row.full_text_status, row.full_text_error)
        for row in conn.execute(
            select(task_source_snapshot).where(task_source_snapshot.c.task_id == task_id)
        )
    )
    assert statuses == [
        ("fetch_failed", "not_ready"), ("fetch_failed", "not_ready"),
        ("fetch_failed", "send_failed"), ("ingested", None),
    ]


def test_all_done_early_stops_without_waiting(conn: Connection) -> None:
    task_id, run_id, scope_id, fetcher = _seed_docs(conn, 3)
    queue = _FakeQueue(conn, fetcher, ingest_first=3)
    clock = _FakeClock()
    summary = run_ingest(
        conn, task_id, run_id, scope_id, fetcher=fetcher,
        queue=queue, stage_deadline_s=600.0, clock=clock.clock, sleep=clock.sleep,
    )
    assert summary["ingested"] == 3 and summary["by_reason"] == {}
    assert clock.sleeps == []


def test_message_shape_and_queued_mode_needs_its_client() -> None:
    link, run = uuid.uuid4(), uuid.uuid4()
    assert new_message(link_row_id=link, run_id=run) == {
        "link_row_id": str(link), "run_id": str(run), "schema": 1,
    }
    with pytest.raises(RuntimeError, match="Phase 4b"):
        build_queue_client("queued", connect=lambda: None, fetcher=None)  # type: ignore[arg-type, return-value]
    with pytest.raises(ValueError, match="unknown ingest mode"):
        build_queue_client("lambda", connect=lambda: None, fetcher=None)  # type: ignore[arg-type, return-value]


def test_ingest_mode_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    from policy_atlas.api.settings import ingest_mode_from_env

    monkeypatch.delenv("POLICY_ATLAS_INGEST_MODE", raising=False)
    assert ingest_mode_from_env() == "in_process"
    monkeypatch.setenv("POLICY_ATLAS_INGEST_MODE", "queued")
    assert ingest_mode_from_env() == "queued"
    monkeypatch.setenv("POLICY_ATLAS_INGEST_MODE", "lambda")
    with pytest.raises(RuntimeError, match="in_process or queued"):
        ingest_mode_from_env()


def test_already_in_store_is_kept_out_of_the_public_stage_summary() -> None:
    """G6 (owner 2026-11-03, "hide it")."""
    from policy_atlas.api.routers.sse import _summary

    payload = {"component": "ingest_full_text", "ingested": 3, "already_in_store": 2}
    assert _summary(payload) == {"ingested": 3}
