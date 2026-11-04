"""Tests for full-text ingestion (task 008).

Seeding helpers + the lead-authored concurrency/egress/timeout cases live at the
top; the contract's bulk test list follows below.
"""

import json
import re
import socket
import time
import uuid
from pathlib import Path
from typing import Any, cast

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from structlog.testing import capture_logs

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.markup import strip_markup
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import (
    metadata,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.appraise import AppraiseContext, appraise_sources
from policy_atlas.evidence_search.assess.classify import ClassifyContext, classify_sources
from policy_atlas.evidence_search.assess.screen import ScreenContext, screen_sources
from policy_atlas.evidence_search.sourcing import ingest_full_text
from policy_atlas.evidence_search.sourcing.acquire import (
    AcquireContext,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    FixtureFetcher,
    IngestFullTextContext,
    _highest_priority_fetch_reason,
    candidate_urls,
    ingest_full_text_sources,
    parse_and_segment,
    parse_profile_for,
    run_parse_worker,
)
from policy_atlas.evidence_search.sourcing.ingest_queue import (
    LocalQueueClient,
    make_ingest_handler,
)
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    delete_task_data,
    executed_calls_for,
    now,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
    seed_task_and_run,
)
from tests.provider_fixtures import OpenAlexFixtureBackend, OvertonFixtureBackend

# Expected outcome distribution over the committed fixture set (the manifest's
# outcome map is the spec these tests enforce; see contract decision 9 + plan Task 2/3).
# Decision 8 fixture-403-parity rider (016 review stack): a recorded 403 replays as
# blocked_by_host (no body to marker-scan), upgraded back to paywall by the OA
# cross-check for the 3 OpenAlex docs whose envelope metadata says closed access;
# the 1 Overton doc among the former "paywall" 403s has no OA field to cross-check
# and now reports blocked_by_host honestly.
EXPECTED_ELIGIBLE = 24
EXPECTED_INGESTED = 10
EXPECTED_FETCH_FAILED = 11
EXPECTED_PARSE_FAILED = 3
EXPECTED_BY_REASON = {
    "paywall": 3,
    "blocked_by_host": 1,
    "not_found": 5,
    "too_large": 2,
    "thin_text": 1,
    "no_text_layer": 1,
    "corrupt": 1,
}

CorpusFixture = tuple[
    uuid.UUID, uuid.UUID, uuid.UUID, dict[str, Any], list[dict[str, Any]]
]


def seed_corpus(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Acquire + screen the committed fixtures; return (task_id, run_id, scope_id)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    ctx = AcquireContext(scope_id=scope_id, intent="test", context={})
    backends = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    acquire_sources(
        conn, task_id=task_id, run_id=run_id, context=ctx,
        backends=cast("list[SearchBackend]", backends),
        executed_calls=executed_calls_for(backends, ctx.intent),
    )
    screen_sources(
        conn, task_id=task_id, run_id=run_id,
        context=ScreenContext(scope_id=scope_id, intent="test", context={}),
    )
    return task_id, run_id, scope_id


def _seed_acquired_link(
    conn: Connection, task_id: uuid.UUID, run_id: uuid.UUID, meta: dict[str, Any]
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a bare acquired-origin envelope snapshot + link (no chunk — unneeded by ingest).

    Returns (source_snapshot_id, task_source_snapshot_id).
    """
    snap_id = uuid.uuid4()
    tss_id = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=snap_id,
        content_hash=str(uuid.uuid4()),
        text_basis="abstract_only",
        source_locator="https://example.org/synthetic",
        metadata=meta,
        created_at=now(),
    ))
    conn.execute(task_source_snapshot.insert().values(
        task_source_snapshot_id=tss_id,
        task_id=task_id,
        source_snapshot_id=snap_id,
        origin="acquired",
        run_id=run_id,
        ingested_at=now(),
    ))
    return snap_id, tss_id


def seed_small_corpus(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Four hand-seeded links (PDF ok · HTML ok · 404 · thin) — for property tests
    that don't need the full 24-document corpus. Expected outcome: 4 eligible →
    2 ingested, 1 fetch_failed/not_found, 1 parse_failed/thin_text.
    """
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    for meta in (
        {"backend": "overton", "provider_fields": {"pdf_url": "https://example.org/42ad8806fb1f"}},
        {
            "backend": "openalex",
            "provider_fields": {
                "primary_location": {"landing_page_url": "https://doi.org/10.99999/cacf1b906a"}
            },
        },
        {
            "backend": "overton",
            "provider_fields": {"pdf_url": "https://example.org/04fc90d2b999.pdf"},
        },
        {
            "backend": "openalex",
            "provider_fields": {
                "primary_location": {"landing_page_url": "https://doi.org/10.99999/050131ae0e"}
            },
        },
    ):
        _, tss_id = _seed_acquired_link(conn, task_id, run_id, meta)
        seed_screening_result(conn, task_id, run_id, scope_id, tss_id, status="relevant")
    return task_id, run_id, scope_id


def run_ingest(
    conn: Connection,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run ingest_full_text_sources over the fixture fetcher with test-friendly defaults.

    Without ``queue``/``connect`` the stage runs inline: every document on this
    connection, each write in a savepoint, so the rolled-back ``conn`` fixture
    still rolls everything back (task 057).
    """
    kwargs.setdefault("fetcher", FixtureFetcher())
    # Generous test-only headroom: outcome-distribution assertions must not flip on
    # machine load (4 concurrent parses + whatever else the host runs). Timeout
    # *semantics* are covered by the dedicated timeout test; the product default
    # stays PARSE_TIMEOUT_SECONDS in src.
    kwargs.setdefault("parse_timeout", 300.0)
    return ingest_full_text_sources(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=IngestFullTextContext(scope_id=scope_id, intent="test", context={}),
        **kwargs,
    )


def local_queue(
    engine: Engine,
    *,
    workers: int,
    fetcher: Any = None,
    parse_fn: Any = parse_and_segment,
    parse_timeout: float = 300.0,
) -> LocalQueueClient:
    """The in-process queue client on real threads, each with its own connections.

    Only for committed data: the worker threads cannot see a test's uncommitted rows.
    """
    handler = make_ingest_handler(
        fetcher if fetcher is not None else FixtureFetcher(),
        parse_fn=parse_fn,
        parse_timeout=parse_timeout,
    )
    return LocalQueueClient(handler, engine.begin, workers)


class _ScriptedFetcher:
    mode = "fixture"

    def __init__(
        self,
        script: dict[str, ingest_full_text.FetchResult | BaseException],
    ) -> None:
        self.script = script
        self.calls: list[str] = []

    def fetch(self, url: str) -> ingest_full_text.FetchResult:
        self.calls.append(url)
        outcome = self.script[url]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class _RecordingReleaseFetcher(_ScriptedFetcher):
    def __init__(
        self,
        script: dict[str, ingest_full_text.FetchResult | BaseException],
    ) -> None:
        super().__init__(script)
        self.releases: list[int] = []

    def release_body(self, n_bytes: int) -> None:
        self.releases.append(n_bytes)


def _seed_relevant_acquired(
    conn: Connection,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    meta: dict[str, Any],
) -> uuid.UUID:
    _, tss_id = _seed_acquired_link(conn, task_id, run_id, meta)
    seed_screening_result(conn, task_id, run_id, scope_id, tss_id, status="relevant")
    return tss_id


def _ok_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:  # noqa: ARG001
    return {
        "status": "ok",
        "chunks": [{"content": f"parsed {len(body)} bytes", "locator": {}}],
        "parse_profile": "test_v1",
        "segmentation_policy": "test_v1",
    }


def _html_fails_pdf_ok_parse(
    body: bytes,
    content_type: str,
    thin_min: int,  # noqa: ARG001
) -> dict[str, Any]:
    if content_type.split(";", 1)[0].strip().lower() == "text/html":
        return {"status": "error", "reason": "empty"}
    return _ok_parse(body, content_type, thin_min)


def _fail_on_marker_parse(
    body: bytes,
    content_type: str,
    thin_min: int,
) -> dict[str, Any]:
    if body == b"fail":
        return {"status": "error", "reason": "corrupt"}
    return _ok_parse(body, content_type, thin_min)


def _corpus_state(conn: Connection, task_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """Normalized, id-free ingest outcome per link: status, reason, snapshot content,
    chunk sequence/hash/locator/policy — the comparable surface for determinism."""
    full_text_snap = source_snapshot.alias("full_text_snap")
    rows = conn.execute(
        select(
            source_snapshot.c.content_hash,  # envelope hash: stable per-document key
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
            task_source_snapshot.c.full_text_snapshot_id,
            full_text_snap.c.content_hash,
            full_text_snap.c.source_locator,
            full_text_snap.c.metadata,
        )
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            ).outerjoin(
                full_text_snap,
                task_source_snapshot.c.full_text_snapshot_id
                == full_text_snap.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall()
    state = []
    for env_hash, status, error, snap_id, ft_hash, ft_locator, ft_meta in rows:
        chunks: list[tuple[Any, ...]] = []
        if snap_id is not None:
            chunks = [
                tuple(row)
                for row in conn.execute(
                    select(
                        chunk_table.c.sequence,
                        chunk_table.c.content_hash,
                        chunk_table.c.locator,
                        chunk_table.c.segmentation_policy,
                    )
                    .where(chunk_table.c.source_snapshot_id == snap_id)
                    .order_by(chunk_table.c.sequence)
                ).fetchall()
            ]
        meta = dict(ft_meta) if ft_meta is not None else None
        state.append((env_hash, status, error, ft_hash, ft_locator, meta, tuple(chunks)))
    return sorted(state, key=lambda t: t[0])


def _summary_without_wall_clock(summary: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(summary)
    comparable.pop("wall_clock_s", None)
    return comparable


def _slow_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Spawn-picklable slow-parser double for the timeout property."""
    time.sleep(60)
    return {"status": "ok", "chunks": [], "parse_profile": "x", "segmentation_policy": "y"}


def test_parse_timeout_terminates_worker_and_run_completes(conn: Connection) -> None:
    """A hung parse is genuinely terminated (finding 6): the run finishes with
    parse_failed/timeout well inside the double's sleep, leaving no live worker.

    The suite runs serially, so the bound is tight (45s): a leaked worker set stuck
    in the double's 60s sleep would instead take several hundred seconds (one full
    sleep per remaining candidate, serialized).
    """
    import multiprocessing

    task_id, run_id, scope_id = seed_small_corpus(conn)
    start = time.monotonic()
    summary = run_ingest(
        conn, task_id, run_id, scope_id,
        parse_timeout=1.0, parse_fn=_slow_parse,
    )
    elapsed = time.monotonic() - start
    assert elapsed < 45, f"run took {elapsed:.0f}s — workers were not terminated"
    # Nothing ingests; every parse attempt times out. A timed-out parse with a
    # further candidate falls through the cascade, so a doc whose last candidate
    # fails to *fetch* lands in fetch_failed — assert structurally.
    assert summary["ingested"] == 0
    assert summary["parse_failed"] > 0
    assert summary["by_reason"]["timeout"] == summary["parse_failed"]
    assert (
        summary["fetch_failed"] + summary["parse_failed"] + summary["already_ingested"]
        == summary["eligible"]
    )
    for proc in multiprocessing.active_children():
        proc.join(timeout=5)
    assert not multiprocessing.active_children(), "worker processes leaked"


def _sleep_by_marker_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Spawn-picklable double: hangs on the marked body, parses others instantly."""
    if body == b"slow":
        time.sleep(60)
    return {"status": "ok", "chunks": [{"content": "x", "locator": {}}],
            "parse_profile": "p", "segmentation_policy": "s"}


# Openly licensed committed fixtures (licences in tests/data/fulltext_manifest.json):
# three CC-BY-4.0 articles and the CC0 generated corrupt PDF (error path).
_BYTE_IDENTITY_FILES = (
    "frontiers_getting_ready_2018.pdf",
    "frontiers_school_readiness_2022.pdf",
    "plos_food_environment_review.pdf",
    "derived_corrupt.pdf",
)
# SHA-256 of the parse results below under parse profile v2 (task 057, N7: the markup
# rule at segmentation), from an in-process parse_and_segment, equal at workers 1 and 4.
# The v1 digest (scheduler before task 056, commit 35c92e59, same at workers 1 and 4)
# was 15f69fc20ab88c0d21ad866686e26da009a0f65e52b6587b74b2f108787078b9. A
# pymupdf4llm/pymupdf/trafilatura upgrade may move it: re-derive it from the
# in-process leg and check the workers legs still equal it. The first v2 digest
# (c84804da2ebe3e77f98e2a5a51cb9f3b6600e3b42bd85469b113071d517c2c78) moved on
# 2026-11-03 when the markup rule stopped deleting significance stars after a number
# (one chunk of frontiers_school_readiness_2022: `0.47* 0.50** 0.54***` kept whole).
_BYTE_IDENTITY_DIGEST = "59655557f2958d057a89a811ea50f21845db1534d4161b360844ddd2ddde30fc"


def _results_digest(results: dict[int, dict[str, Any]]) -> str:
    import hashlib

    ordered = [results[i] for i in sorted(results)]
    return hashlib.sha256(json.dumps(ordered, sort_keys=True).encode()).hexdigest()


def test_parse_worker_output_is_byte_identical_serial_and_concurrent() -> None:
    """Task 057 (N6; replaces the task 056 scheduler test): a parse in its own
    worker process gives exactly the in-process result, whether the documents are
    parsed one at a time or four at once on four threads (the in-process queue's
    shape), and equals the committed parse profile v2 digest."""
    from concurrent.futures import ThreadPoolExecutor

    fulltext_dir = Path(__file__).resolve().parents[2] / "data" / "fulltext"
    jobs = [
        (i, (fulltext_dir / name).read_bytes(), "application/pdf")
        for i, name in enumerate(_BYTE_IDENTITY_FILES)
    ]
    thin = ingest_full_text.THIN_TEXT_MIN_CHARS
    in_process = {i: parse_and_segment(body, ct, thin) for i, body, ct in jobs}

    def parse(job: tuple[int, bytes, str]) -> dict[str, Any]:
        _, body, ct = job
        return run_parse_worker(parse_and_segment, body, ct, thin_min=thin, timeout=300.0)

    serial = {i: parse((i, body, ct)) for i, body, ct in jobs}
    with ThreadPoolExecutor(max_workers=4) as pool:
        concurrent = dict(zip([i for i, _, _ in jobs], pool.map(parse, jobs), strict=True))
    assert serial == in_process
    assert concurrent == in_process
    assert [r["status"] for _, r in sorted(in_process.items())] == ["ok", "ok", "ok", "error"]
    assert in_process[0]["parse_profile"] == "pymupdf4llm_v2"
    assert _results_digest(in_process) == _BYTE_IDENTITY_DIGEST


def test_hung_parse_does_not_hold_back_a_concurrent_one() -> None:
    """Task 057 (replaces the task 056 drain tests): each parse is its own process
    with its own clock, so a hung parse on one thread is killed at its own timeout
    while a parse started beside it returns its result, and no process is left."""
    import multiprocessing
    from concurrent.futures import ThreadPoolExecutor

    finished: dict[str, float] = {}

    def parse(body: bytes, timeout: float) -> dict[str, Any]:
        result = run_parse_worker(
            _sleep_by_marker_parse, body, "text/plain", thin_min=0, timeout=timeout
        )
        finished[body.decode()] = time.monotonic()
        return result

    # Warm the forkserver first: its first start imports the parsers (seconds
    # under a loaded suite), which would otherwise land on the fast job's clock.
    assert parse(b"warm", 60.0)["status"] == "ok"
    with ThreadPoolExecutor(max_workers=2) as pool:
        slow = pool.submit(parse, b"slow", 8.0)
        fast = pool.submit(parse, b"fast", 60.0)
        assert slow.result() == {"status": "error", "reason": "timeout"}
        assert fast.result()["status"] == "ok"
    assert finished["fast"] < finished["slow"]
    for proc in multiprocessing.active_children():
        proc.join(timeout=5)
    assert not multiprocessing.active_children(), "worker processes leaked"


def test_local_queue_slow_document_holds_only_its_own_thread() -> None:
    """Task 057 (replaces the any-free-slot test): with two threads, a slow first
    document holds one thread; the three behind it all finish on the other."""
    import threading

    order: list[str] = []
    quick_done = threading.Event()

    def handler(connect: Any, message: Any) -> Any:  # noqa: ARG001
        kind = message["link_row_id"]
        if kind == "slow":
            assert quick_done.wait(30), "the quick documents waited behind the slow one"
        order.append(kind)
        if len(order) == 3 and "slow" not in order:
            quick_done.set()
        return kind

    client = LocalQueueClient(handler, connect=lambda: None, workers=2)  # type: ignore[arg-type, return-value]
    result = client.send(
        [{"link_row_id": kind, "run_id": "r", "schema": 1} for kind in ("slow", "a", "b", "c")]
    )
    assert order == ["a", "b", "c", "slow"]
    assert result.sent == ["slow", "a", "b", "c"]
    assert result.outcomes == cast(Any, ["slow", "a", "b", "c"])  # in message order


def test_local_queue_raises_a_handler_error_after_the_rest_finish() -> None:
    """A handler error (a configuration error such as a missing fixture corpus)
    fails the send loudly, but only once every other document has been handled."""
    handled: list[str] = []

    def handler(connect: Any, message: Any) -> Any:  # noqa: ARG001
        if message["link_row_id"] == "bad":
            raise FileNotFoundError("corpus")
        handled.append(message["link_row_id"])
        return None

    client = LocalQueueClient(handler, connect=lambda: None, workers=2)  # type: ignore[arg-type, return-value]
    with pytest.raises(FileNotFoundError):
        client.send(
            [{"link_row_id": k, "run_id": "r", "schema": 1} for k in ("bad", "a", "b", "c")]
        )
    assert sorted(handled) == ["a", "b", "c"]


def test_document_log_carries_fetch_and_parse_timings(conn: Connection) -> None:
    """Task 057 (replaces the per-round ``ingest.batch_handover`` line, whose rounds
    are gone): each document's outcome line carries its fetch and parse seconds."""
    task_id, run_id, scope_id = seed_small_corpus(conn)
    with capture_logs() as logs:
        run_ingest(conn, task_id, run_id, scope_id, parse_fn=_ok_parse)
    lines = [e for e in logs if e["event"] in ("fulltext.ingested", "fulltext.failed")]
    assert len(lines) == 4
    for line in lines:
        assert line["fetch_s"] >= 0 and line["parse_s"] >= 0
    assert all(line["parse_s"] > 0 for line in lines if line["event"] == "fulltext.ingested")


# --- Parse profile v2 on the committed fixture corpus (task 057, N7 and D8) ---


def _fixture_corpus_documents() -> list[tuple[Path, str]]:
    data_dir = Path(__file__).resolve().parents[2] / "data"
    manifest = json.loads((data_dir / "fulltext_manifest.json").read_text())["documents"]
    docs = [
        (data_dir / "fulltext" / name, str(meta["content_type"]))
        for name, meta in sorted(manifest.items())
        if (data_dir / "fulltext" / name).exists()
    ]
    return docs + [(path, "application/xml") for path in sorted((data_dir / "jats").glob("*.xml"))]


def _parse_recording_pages(
    body: bytes, content_type: str
) -> tuple[dict[str, Any], list[tuple[int, str]] | None]:
    """``parse_and_segment``, plus the markdown pages its segmenter was given (PDF, JATS)."""
    seen: list[list[tuple[int, str]]] = []
    real_segment = ingest_full_text._segment_markdown_pages

    def recording(pages: list[tuple[int, str]]) -> list[dict[str, Any]]:
        seen.append(list(pages))
        return real_segment(pages)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ingest_full_text, "_segment_markdown_pages", recording)
        result = parse_and_segment(body, content_type, ingest_full_text.THIN_TEXT_MIN_CHARS)
    return result, (seen[0] if seen else None)


def _segment_v1(pages: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Parse profile v1's cut of the same pages: v2 with the markup rule switched off."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ingest_full_text, "strip_markup", lambda text, table=False: text)
        return ingest_full_text._segment_markdown_pages(pages)


def _markup_bearing(chunks: list[dict[str, Any]]) -> int:
    return sum(1 for c in chunks if strip_markup(c["content"]) != c["content"])


def _is_table_chunk(chunk: dict[str, Any]) -> bool:
    return str(chunk["content"]).startswith("|")


# v1's cut of the same parsed pages (8 PDFs, 3 JATS articles): this many chunks carried
# markup, all of them PDF chunks (counted when v2 was built, task 057 phase 4a, and
# matched by running the v1 code from commit 528250f7). The v1 HTML route added one
# more (a reference-list URL with underscores on the BMC page): 107 in all; 0 under v2.
_V1_MARKUP_BEARING_CHUNKS = 106


def test_parse_profile_v2_on_the_fixture_corpus() -> None:
    """Parse profile v2 on every committed fixture that parses (8 PDFs, 2 HTML pages,
    3 JATS articles), in one test so the large PDFs are parsed once:

    * no chunk carries markup (``strip_markup(text) != text``) under v2;
    * v1's structure is kept: the same chunks, table chunks, pages and heading paths
      (v1's headings with the markup taken out of their text);
    * ``parse_profile_for`` names what ``parse_and_segment`` stamped, on every route;
    * a second parse is byte-identical (determinism).
    """
    parsed = {
        path.name: (content_type, *_parse_recording_pages(path.read_bytes(), content_type))
        for path, content_type in _fixture_corpus_documents()
    }
    ok = {name: p for name, p in parsed.items() if p[1]["status"] == "ok"}
    assert len(ok) == 13, sorted(ok)

    v1_markup_bearing = 0
    v2_markup_bearing = 0
    compared_chunks = 0
    for name, (content_type, result, pages) in ok.items():
        v2 = result["chunks"]
        v2_markup_bearing += _markup_bearing(v2)
        assert parse_profile_for(content_type) == (
            result["parse_profile"], result["segmentation_policy"],
        ), name
        if pages is None:  # HTML: no markdown pages to cut the v1 way
            continue
        v1 = _segment_v1(pages)
        v1_markup_bearing += _markup_bearing(v1)
        assert len(v2) == len(v1), name
        assert sum(map(_is_table_chunk, v2)) == sum(map(_is_table_chunk, v1)), name
        for c1, c2 in zip(v1, v2, strict=True):
            assert _is_table_chunk(c2) == _is_table_chunk(c1), name
            assert c2["locator"]["pages"] == c1["locator"]["pages"], name
            expected_path = [
                h for h in map(ingest_full_text._clean_heading, c1["locator"]["heading_path"]) if h
            ]
            assert c2["locator"]["heading_path"] == expected_path, name
            compared_chunks += 1
    assert v2_markup_bearing == 0
    assert v1_markup_bearing == _V1_MARKUP_BEARING_CHUNKS
    assert compared_chunks > 200
    assert {ct for ct, _, _ in ok.values()} == {"application/pdf", "text/html", "application/xml"}

    # Determinism: one document per route parsed a second time, byte for byte.
    one_per_route = {
        "frontiers_ashp_ventilation_2021.pdf", "bmc_fiscal_policies_review.html", "PMC5264339.xml",
    }
    for path, content_type in _fixture_corpus_documents():
        if path.name in one_per_route:
            again = parse_and_segment(
                path.read_bytes(), content_type, ingest_full_text.THIN_TEXT_MIN_CHARS
            )
            assert json.dumps(again, sort_keys=True) == json.dumps(ok[path.name][1], sort_keys=True)


def _socket_deny_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Spawn-picklable wrapper: denies socket creation *inside the worker*, then
    parses for real — extends the zero-egress proof across the process boundary
    (step-7 security finding: the parent-side patch does not reach spawned children,
    where the third-party parsers actually run)."""
    socket.socket = _deny_socket  # type: ignore[misc, assignment]
    return parse_and_segment(body, content_type, thin_min)


def _deny_socket(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("socket creation attempted inside parse worker")


_REAL_SOCKET = socket.socket


def _deny_network_socket(family: int = -1, *args: Any, **kwargs: Any) -> Any:
    """Parent-side guard: refuses every socket except a local Unix-domain one.

    The parse workers' forkserver (task 056, N8) hands each job to its helper
    process over a Unix-domain socket on this machine, which cannot reach the
    network. Any other family (internet sockets included) is refused.
    """
    if family == socket.AF_UNIX:
        return _REAL_SOCKET(family, *args, **kwargs)
    raise AssertionError("network socket creation attempted in the ingest parent")


def test_zero_egress_socket_deny(conn: Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fixture ingest with socket creation blocked completes green
    (adversarial finding 5) — the zero-egress claim proven at runtime, in the
    parent (monkeypatch; only the forkserver's local Unix-domain socket is
    allowed, task 056) and inside every parse worker, where every socket is
    refused (``_socket_deny_parse``, step-7 security finding).

    Scoped, not autouse: the suite's own Postgres connection runs over a socket,
    so the guard patches socket.socket only around the ingest call, after the DB
    connection is established (plan-review finding 2).

    Deliberately narrowed to a 4-doc fixture subset (both parser paths, real
    committed files, full fetch→parse→write) — the full-breadth ingest runs
    unguarded in the module fixture; narrowing noted in verification.md.
    """
    task_id, run_id, scope_id = seed_small_corpus(conn)

    monkeypatch.setattr(socket, "socket", _deny_network_socket)
    summary = run_ingest(conn, task_id, run_id, scope_id, parse_fn=_socket_deny_parse)
    monkeypatch.undo()
    assert summary["ingested"] == 2
    assert summary["fetch_failed"] == 1
    assert summary["parse_failed"] == 1


def _parse_that_opens_a_socket(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    socket.socket()  # refused by the worker itself, not by a test wrapper
    return parse_and_segment(body, content_type, thin_min)


def test_the_parse_worker_refuses_sockets_on_its_own() -> None:
    """Task 057 review (security 1): ``_worker_entry`` installs the socket
    denial before the parse, so a parser that opens a socket gets a ``corrupt``
    result naming the refusal."""
    result = ingest_full_text.run_parse_worker(
        _parse_that_opens_a_socket, b"plain text", "text/plain", thin_min=1, timeout=60.0
    )
    assert (result["status"], result["reason"]) == ("error", "corrupt")
    assert "socket creation attempted inside the parse worker" in result["detail"]


def test_recorder_script_not_imported_by_package() -> None:
    """The full-text recorder stays outside the package import graph (007 precedent)."""
    src_dir = Path(__file__).resolve().parents[3] / "src" / "policy_atlas"
    for module in src_dir.rglob("*.py"):
        assert "record_fulltext_fixtures" not in module.read_text()


def test_ingest_module_has_no_http_client() -> None:
    """ingest_full_text.py imports no HTTP client and never constructs a socket.

    The module may name ``socket`` (task 057 review: the parse worker replaces
    ``socket.socket`` with a refuser), but no line may open one.
    """
    module = (
        Path(__file__).resolve().parents[3] / "src" / "policy_atlas"
        / "evidence_search" / "sourcing" / "ingest_full_text.py"
    ).read_text()
    forbidden = re.compile(
        r"^\s*(import|from)\s+"
        r"(urllib\.(?:request|error)|requests|httpx|aiohttp|http\.client)\b",
        re.MULTILINE,
    )
    assert not forbidden.search(module)
    opens_socket = re.compile(r"socket\.(socket|create_connection|socketpair|fromfd)\(")
    assert not opens_socket.search(module)


def test_fulltext_corpus_not_in_package() -> None:
    """The fixture corpus must not ship in the wheel — it lives at tests/data
    (contract decision 12, task 016)."""
    package_data_dir = Path(ingest_full_text.__file__).resolve().parents[2] / "data"
    assert not (package_data_dir / "fulltext").exists(), (
        "src/policy_atlas/data/fulltext must not exist — the fixture corpus lives "
        "at tests/data/fulltext, out of the wheel"
    )
    assert not (package_data_dir / "fulltext_manifest.json").exists(), (
        "src/policy_atlas/data/fulltext_manifest.json must not exist — the fixture "
        "corpus lives at tests/data/fulltext_manifest.json, out of the wheel"
    )


def test_fixture_fetcher_missing_corpus_raises_on_fetch_not_construct(
    tmp_path: Path,
) -> None:
    """An empty/missing fixture corpus root is a loud FileNotFoundError at first
    fetch — never a silent empty/not_found — but construction alone must not
    raise (every ``run_harness`` call constructs a default fetcher)."""
    fetcher = FixtureFetcher(root=tmp_path)  # must not raise
    with pytest.raises(FileNotFoundError, match=re.escape(str(tmp_path))):
        fetcher.fetch("https://example.org/whatever")


def test_missing_fixture_corpus_fails_the_run_loudly(
    conn: Connection, tmp_path: Path,
) -> None:
    """A configuration error (empty/missing fixture corpus) must fail the whole
    run loudly through the real ingest entry point — never degrade to a
    per-document ``fetch_error`` row via ``_safe_fetch``'s isolation belt
    (016 review stack)."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_relevant_acquired(
        conn, task_id, run_id, scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": "https://example.org/x.pdf"}},
    )
    with pytest.raises(FileNotFoundError, match=re.escape(str(tmp_path))):
        run_ingest(conn, task_id, run_id, scope_id, fetcher=FixtureFetcher(root=tmp_path))


def test_fetch_failure_reason_priority_helper() -> None:
    assert _highest_priority_fetch_reason(["not_found", "timeout"]) == "timeout"
    assert (
        _highest_priority_fetch_reason(["not_found", "paywall", "fetch_error"])
        == "paywall"
    )
    assert _highest_priority_fetch_reason(["blocked", "blocked_by_host"]) == "blocked_by_host"
    assert _highest_priority_fetch_reason([]) == "no_url"


def test_escaped_fetcher_raise_is_reason_coded_per_link(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    url = "https://example.org/raises?token=SECRET"
    tss_id = _seed_relevant_acquired(
        conn,
        task_id,
        run_id,
        scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": url}},
    )
    fetcher = _ScriptedFetcher({url: RuntimeError("boom")})

    with capture_logs() as logs:
        summary = run_ingest(
            conn,
            task_id,
            run_id,
            scope_id,
            fetcher=fetcher,
            parse_fn=_ok_parse,
        )

    assert summary["fetch_failed"] == 1
    assert summary["by_reason"] == {"fetch_error": 1}
    status, error = conn.execute(
        select(
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
        )
        .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
    ).one()
    assert (status, error) == ("fetch_failed", "fetch_error")
    assert any(entry["event"] == "fulltext.fetcher_escaped" for entry in logs)
    assert "SECRET" not in repr(logs)


def test_discovery_extends_cascade_to_discovered_pdf(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    landing_url = "https://example.org/landing?token=SECRET"
    discovered_url = "https://cdn.example.org/report.pdf?download=SECRET"
    tss_id = _seed_relevant_acquired(
        conn,
        task_id,
        run_id,
        scope_id,
        {"backend": "openalex", "provider_fields": {
            "primary_location": {"landing_page_url": landing_url}
        }},
    )
    html = (
        b"<html><head><meta name='citation_pdf_url' "
        b"content='https://cdn.example.org/report.pdf?download=SECRET'></head>"
        b"<body>landing page</body></html>"
    )
    fetcher = _ScriptedFetcher({
        landing_url: ingest_full_text.FetchResult(
            status="ok",
            content_type="text/html",
            body=html,
        ),
        discovered_url: ingest_full_text.FetchResult(
            status="ok",
            content_type="application/pdf",
            body=b"%PDF-1.7 synthetic",
        ),
    })

    with capture_logs() as logs:
        summary = run_ingest(
            conn,
            task_id,
            run_id,
            scope_id,
            fetcher=fetcher,
            parse_fn=_html_fails_pdf_ok_parse,
        )

    assert summary["ingested"] == 1
    assert fetcher.calls == [landing_url, discovered_url]
    row = conn.execute(
        select(
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
            task_source_snapshot.c.full_text_snapshot_id,
        )
        .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
    ).one()
    assert row.full_text_status == "ingested"
    assert row.full_text_error is None
    locator = conn.execute(
        select(source_snapshot.c.source_locator)
        .where(source_snapshot.c.source_snapshot_id == row.full_text_snapshot_id)
    ).scalar_one()
    assert locator == discovered_url
    rendered = repr(logs)
    assert "SECRET" not in rendered
    assert "?token" not in rendered
    assert "?download" not in rendered
    assert "https://example.org/landing" in rendered
    assert "https://cdn.example.org/report.pdf" in rendered


def test_release_body_called_for_parse_and_preparse_reject(
    conn: Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    urls = {
        "ok": "https://example.org/ok.txt",
        "fail": "https://example.org/fail.txt",
        "large": "https://example.org/large.txt",
    }
    for url in urls.values():
        _seed_relevant_acquired(
            conn,
            task_id,
            run_id,
            scope_id,
            {"backend": "overton", "provider_fields": {"pdf_url": url}},
        )
    fetcher = _RecordingReleaseFetcher({
        urls["ok"]: ingest_full_text.FetchResult(
            status="ok",
            content_type="text/plain",
            body=b"ok",
        ),
        urls["fail"]: ingest_full_text.FetchResult(
            status="ok",
            content_type="text/plain",
            body=b"fail",
        ),
        urls["large"]: ingest_full_text.FetchResult(
            status="ok",
            content_type="text/plain",
            body=b"toolong",
        ),
    })
    monkeypatch.setattr(ingest_full_text, "FETCH_BYTE_CAP", 5)

    summary = run_ingest(
        conn,
        task_id,
        run_id,
        scope_id,
        fetcher=fetcher,
        parse_fn=_fail_on_marker_parse,
    )

    assert summary["ingested"] == 1
    assert summary["parse_failed"] == 1
    assert summary["fetch_failed"] == 1
    assert summary["by_reason"] == {"too_large": 1, "corrupt": 1}
    assert summary["bytes_fetched"] == len(b"ok") + len(b"fail") + len(b"toolong")
    assert sorted(fetcher.releases) == [len(b"ok"), len(b"fail"), len(b"toolong")]


def test_oa_cross_check_upgrade_and_inconsistency_log(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    closed_url = "https://example.org/closed.pdf"
    open_url = "https://example.org/open.pdf"
    closed_tss = _seed_relevant_acquired(
        conn,
        task_id,
        run_id,
        scope_id,
        {
            "backend": "openalex",
            "provider_fields": {
                "best_oa_location": {"pdf_url": closed_url},
                "open_access": {"is_oa": False},
            },
        },
    )
    open_tss = _seed_relevant_acquired(
        conn,
        task_id,
        run_id,
        scope_id,
        {
            "backend": "openalex",
            "provider_fields": {
                "best_oa_location": {"pdf_url": open_url},
                "open_access": {"is_oa": True},
            },
        },
    )
    fetcher = _ScriptedFetcher({
        closed_url: ingest_full_text.FetchResult(status="error", error="blocked_by_host"),
        open_url: ingest_full_text.FetchResult(status="error", error="blocked_by_host"),
    })

    with capture_logs() as logs:
        summary = run_ingest(
            conn,
            task_id,
            run_id,
            scope_id,
            fetcher=fetcher,
            parse_fn=_ok_parse,
        )

    assert summary["by_reason"] == {"paywall": 1, "blocked_by_host": 1}
    rows = {
        tss_id: error
        for tss_id, error in conn.execute(
            select(
                task_source_snapshot.c.task_source_snapshot_id,
                task_source_snapshot.c.full_text_error,
            )
            .where(
                task_source_snapshot.c.task_source_snapshot_id.in_(
                    [closed_tss, open_tss]
                )
            )
        ).fetchall()
    }
    assert rows[closed_tss] == "paywall"
    assert rows[open_tss] == "blocked_by_host"
    inconsistency_logs = [
        entry for entry in logs if entry["event"] == "fulltext.oa_inconsistency"
    ]
    assert len(inconsistency_logs) == 1
    assert inconsistency_logs[0]["tss_id"] == str(open_tss)
    assert inconsistency_logs[0]["reason"] == "blocked_by_host"


def test_summary_includes_attempted_bytes_and_wall_clock(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_relevant_acquired(
        conn,
        task_id,
        run_id,
        scope_id,
        {"backend": "openalex", "provider_fields": {}},
    )

    with capture_logs() as logs:
        summary = run_ingest(conn, task_id, run_id, scope_id)

    assert summary["attempted"] == 1
    assert summary["bytes_fetched"] == 0
    assert isinstance(summary["wall_clock_s"], float)
    assert summary["wall_clock_s"] >= 0.0
    summary_logs = [entry for entry in logs if entry["event"] == "fulltext.summary"]
    assert len(summary_logs) == 1
    assert summary_logs[0]["attempted"] == 1
    assert summary_logs[0]["bytes_fetched"] == 0
    assert isinstance(summary_logs[0]["wall_clock_s"], float)


def test_live_flag_never_silently_falls_back_to_fixture_replay() -> None:
    """A live-flagged run constructs the live fetcher, never FixtureFetcher —
    the decision-12 test-pinned invariant riding decision 2's one switch."""
    from policy_atlas.evidence_search.sourcing.fetch_live import (
        LiveDocumentFetcher,
        select_document_fetcher,
    )

    live_fetcher = select_document_fetcher(True)
    assert isinstance(live_fetcher, LiveDocumentFetcher)
    try:
        assert live_fetcher.mode == "live"
        assert not isinstance(live_fetcher, FixtureFetcher)
    finally:
        live_fetcher.close()

    stub_fetcher = select_document_fetcher(False)
    assert isinstance(stub_fetcher, FixtureFetcher)
    assert stub_fetcher.mode == "fixture"


def test_ingest_log_lines_never_carry_query_strings(conn: Connection) -> None:
    """URL log hygiene (contract decision 3, rev 2.4 blocker 1): tokened OA URLs
    must never leak query strings into log lines — attempts trail included."""
    tokened_ok = "https://example.org/ok.pdf?token=SECRET-OK-b7f3"
    tokened_fail = "https://example.org/gone.pdf?token=SECRET-FAIL-a1c9"
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _seed_relevant_acquired(
        conn, task_id, run_id, scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": tokened_ok}},
    )
    _seed_relevant_acquired(
        conn, task_id, run_id, scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": tokened_fail}},
    )
    fetcher = _ScriptedFetcher({
        tokened_ok: ingest_full_text.FetchResult(
            status="ok", content_type="text/plain", body=b"x" * 400
        ),
        tokened_fail: ingest_full_text.FetchResult(status="error", error="not_found"),
    })

    with capture_logs() as logs:
        summary = run_ingest(conn, task_id, run_id, scope_id, fetcher=fetcher)

    assert summary["ingested"] == 1 and summary["fetch_failed"] == 1
    log_dump = repr(logs)
    assert "SECRET-OK" not in log_dump
    assert "SECRET-FAIL" not in log_dump
    assert "token=" not in log_dump
    # The verbatim URL still persists as provenance (provider-data retention), on
    # the link row since task 057 (N9), and as the snapshot's public locator.
    fetched_from, locator = conn.execute(
        select(task_source_snapshot.c.fetched_from, source_snapshot.c.source_locator)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.full_text_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.full_text_status == "ingested")
    ).one()
    assert fetched_from == locator == tokened_ok

_ALLOWED_LICENCES = {"CC-BY-4.0", "CC-BY-3.0-IGO", "CC0-1.0"}
_KNOWN_INGEST_RUN_EVENT_TYPES = {
    "component.started", "component.completed", "run.completed", "run.failed",
}


def _full_text_snapshot_count(conn: Connection, task_id: uuid.UUID) -> int:
    """Count of distinct full-text snapshots attached within one task (task-scoped:
    source_snapshot itself carries no task_id)."""
    return conn.execute(
        select(sa.func.count(sa.distinct(task_source_snapshot.c.full_text_snapshot_id)))
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.full_text_snapshot_id.is_not(None))
    ).scalar_one()


def test_html_non_utf8_charset_decoded_correctly() -> None:
    """Decision 6 pin (Codex finding): HTML bytes must reach trafilatura undecoded
    so a declared non-UTF-8 ``<meta charset>`` is honoured by its own encoding
    sniffer. A UTF-8-with-replace pre-decode (the ``_decode`` helper used for plain
    text) would instead mangle every non-ASCII byte into U+FFFD before trafilatura
    ever sees it — this pins that ``_parse_html`` never does that."""
    # windows-1252 bytes: 0xE9 = é, 0x93/0x94 = curly open/close quotes.
    html = (
        b'<html><head><meta charset="windows-1252"></head><body><article>'
        b"<p>This report examines caf\xe9 culture and the \x93important\x94 trends "
        b"in policy analysis across many different regions and sectors of the "
        b"economy today for readers everywhere in the world.</p></article>"
        b"</body></html>"
    )
    result = parse_and_segment(html, "text/html", thin_min=0)
    assert result["status"] == "ok"
    joined = " ".join(c["content"] for c in result["chunks"])
    assert "café" in joined
    assert "“important”" in joined
    assert "�" not in joined  # replacement char proves a mangled pre-decode


def test_binary_content_is_reason_coded_not_chunked() -> None:
    """Prod incident 2026-08-19 (run f4c029b3): a source URL served a JPEG, the
    plain path chunked its raw bytes, and the surviving NUL bytes aborted the
    whole write transaction at INSERT. Binary must resolve to a reason-coded
    per-document failure, and no chunk content may ever carry NUL."""
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00" + b"\x00" * 300

    # Declared binary type: rejected before any parse.
    result = parse_and_segment(jpeg, "image/jpeg", thin_min=0)
    assert result == {"status": "error", "reason": "unsupported_type"}

    # Mislabeled/untyped binary falls to the plain path: NUL sniff rejects it.
    result = parse_and_segment(jpeg, "application/octet-stream", thin_min=0)
    assert result == {"status": "error", "reason": "unsupported_type"}

    # Stray NULs in genuine text (any parse path) are replaced, never inserted.
    result = parse_and_segment(
        b"<html><body><article><p>A stray \x00 NUL inside otherwise ordinary "
        b"prose about policy analysis must not abort the ingest run at the "
        b"database insert stage.</p></article></body></html>",
        "text/html",
        thin_min=0,
    )
    assert result["status"] == "ok"
    assert all("\x00" not in c["content"] for c in result["chunks"])


def test_javascript_wall_is_blocked_by_host_not_full_text() -> None:
    """Issue #74: a publisher's "JavaScript is disabled" page is 284 characters, so
    it cleared the 200-character thin-text floor and was stored as the document's
    full text (6 of 21 documents "read in full" in the options-scoping checks were
    this page). The spec's rule is that a bot block is ``blocked_by_host`` and
    never full text."""
    wall = (
        b"<html><body><article><p>JavaScript is disabled in your browser. "
        b"Please enable JavaScript to proceed. A required part of this site "
        b"couldn't load. This may be due to a browser extension, network issue, "
        b"or browser setting. Please check your connection and try again.</p>"
        b"</article></body></html>"
    )
    assert parse_and_segment(wall, "text/html", thin_min=200) == {
        "status": "error",
        "reason": "blocked_by_host",
    }

    # A real document that happens to discuss JavaScript is untouched: the marker
    # scan only applies below the stub-page ceiling.
    real = (
        b"<html><body><article><p>JavaScript is disabled by default in the "
        b"departmental browser build, which this evaluation treats as a "
        b"digital-access barrier.</p><p>"
        + b"The programme measured take-up across every local authority. " * 60
        + b"</p></article></body></html>"
    )
    assert parse_and_segment(real, "text/html", thin_min=200)["status"] == "ok"


def test_licence_guard() -> None:
    manifest = json.loads(
        (Path(__file__).resolve().parents[2] / "data" / "fulltext_manifest.json").read_text()
    )
    meta = manifest["_meta"]
    assert meta["recorded_at"]
    assert meta["coverage"]
    assert meta["total_bytes"]
    for doc in manifest["documents"].values():
        licence = doc.get("licence")
        if licence is not None:
            assert licence in _ALLOWED_LICENCES
        else:
            permission = doc.get("permission")
            assert isinstance(permission, dict)
            assert permission.get("org") and permission.get("who") and permission.get("date")

    fulltext_dir = Path(__file__).resolve().parents[2] / "data" / "fulltext"
    for url, outcome in manifest["outcomes"].items():
        assert url.startswith(("https://example.org/", "https://doi.org/10.99999/")), url
        if outcome["outcome"] == "ok":
            filename = outcome["file"]
            assert filename in manifest["documents"]
            assert (fulltext_dir / filename).exists()

    # Corpus size budget (user decision, 2026-07-05): committed documents ship inside
    # the package while fixture replay is the product behaviour, so growth is a
    # conscious gate, not drift. Raising this cap = deciding the corpus strategy
    # (see the live-DocumentFetcher entry in docs/deferred.md).
    total_bytes = sum(f.stat().st_size for f in fulltext_dir.iterdir() if f.is_file())
    assert total_bytes <= 30 * 1024 * 1024, f"corpus {total_bytes} bytes exceeds the 30 MB budget"


def test_migration_roundtrip_and_checks(conn: Connection) -> None:
    # 33 -> 36: task 033 adds `organisation` and `app_user` (tenancy above the
    # entity hierarchy) and ADR 0032 adds `project_membership`; 36 -> 37:
    # task 036 adds `waitlist_entry`; 37 -> 38: task 044 adds `task_link` (the
    # Link between two tasks); 38 -> 43: task 045 adds `option`,
    # `option_membership`, `option_relation`, `longlist_result` and
    # `intervention_profile_record`; no evidence-search table changed.
    assert len(metadata.tables) == 43
    task_id, _ = seed_task_and_run(conn)
    snap_id, tss_id = seed_source(conn, task_id)

    rejections: list[tuple[str, dict[str, Any]]] = [
        ("ck_tss_full_text_status", {"full_text_status": "bogus"}),
        ("ck_tss_full_text_consistent",
         {"full_text_status": "ingested", "full_text_snapshot_id": None}),
        ("ck_tss_full_text_consistent",
         {"full_text_status": "not_attempted", "full_text_snapshot_id": snap_id}),
        ("ck_tss_full_text_error_presence",
         {"full_text_status": "fetch_failed", "full_text_error": None}),
        ("ck_tss_full_text_error_presence",
         {"full_text_status": "not_attempted", "full_text_error": "oops"}),
    ]
    for constraint, values in rejections:
        with pytest.raises(IntegrityError, match=constraint), conn.begin_nested():
            conn.execute(
                task_source_snapshot.update()
                .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
                .values(**values)
            )


def test_url_resolution_order() -> None:
    openalex_meta = {
        "backend": "openalex",
        "provider_fields": {
            "best_oa_location": {"pdf_url": "https://example.org/best.pdf"},
            "primary_location": {
                "pdf_url": "https://example.org/best.pdf",  # duplicate of best_oa -> deduped
                "landing_page_url": "https://example.org/landing",
            },
            "open_access": {"oa_url": "https://example.org/oa.pdf"},
        },
    }
    assert candidate_urls(openalex_meta) == [
        "https://example.org/best.pdf",
        "https://example.org/oa.pdf",
        "https://example.org/landing",
    ]

    overton_meta = {
        "backend": "overton",
        "provider_fields": {
            "pdf_url": "https://example.org/doc.pdf",
            "document_url": "https://example.org/doc-landing",
        },
    }
    assert candidate_urls(overton_meta) == [
        "https://example.org/doc.pdf",
        "https://example.org/doc-landing",
    ]

    overton_records = json.loads(
        (
        Path(__file__).resolve().parents[2] / "data" / "provider_records" / "overton_documents.json"
    ).read_text()
    )["records"]
    record_zero = overton_records[0]
    assert record_zero["pdf_url"] == "n/a"  # sentinel; dropped, not a candidate
    assert candidate_urls({"backend": "overton", "provider_fields": record_zero}) == [
        "https://doi.org/10.99999/cf91b048b2"
    ]

    assert candidate_urls({"backend": "overton"}) == []


def test_no_url_persisted(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _, no_url_tss = _seed_acquired_link(
        conn, task_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(conn, task_id, run_id, scope_id, no_url_tss, status="relevant")

    _, unscreened_tss = _seed_acquired_link(
        conn, task_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    # deliberately never screened -> ineligible, stays not_attempted

    run_ingest(conn, task_id, run_id, scope_id)

    status, error = conn.execute(
        select(
            task_source_snapshot.c.full_text_status, task_source_snapshot.c.full_text_error,
        )
        .where(task_source_snapshot.c.task_source_snapshot_id == no_url_tss)
    ).one()
    assert (status, error) == ("fetch_failed", "no_url")

    status2, error2 = conn.execute(
        select(
            task_source_snapshot.c.full_text_status, task_source_snapshot.c.full_text_error,
        )
        .where(task_source_snapshot.c.task_source_snapshot_id == unscreened_tss)
    ).one()
    assert (status2, error2) == ("not_attempted", None)


def test_eligibility_boundaries(conn: Connection) -> None:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    _, uploaded_tss = seed_source(conn, task_id)  # origin="uploaded"
    seed_screening_result(conn, task_id, run_id, scope_id, uploaded_tss, status="relevant")

    _, not_relevant_tss = _seed_acquired_link(
        conn, task_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(
        conn, task_id, run_id, scope_id, not_relevant_tss, status="not_relevant"
    )

    _, failed_tss = _seed_acquired_link(
        conn, task_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(conn, task_id, run_id, scope_id, failed_tss, status="failed")

    other_scope_id = seed_scope(conn, task_id)
    _, other_scope_tss = _seed_acquired_link(
        conn, task_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(
        conn, task_id, run_id, other_scope_id, other_scope_tss, status="relevant"
    )

    run_ingest(conn, task_id, run_id, scope_id)

    for tss_id in (uploaded_tss, not_relevant_tss, failed_tss, other_scope_tss):
        status = conn.execute(
            select(task_source_snapshot.c.full_text_status)
            .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
        ).scalar_one()
        assert status == "not_attempted"


def test_stage2_demoted_doc_still_eligible_stage1_only(conn: Connection) -> None:
    """Ingest reads effective STAGE-1 relevant only, never stage 2 (task 014
    sweep item 4): stage 2 needs the full text this component produces, so
    fetch must never consult stage-2 rows. A doc demoted at stage 2 (stage-1
    relevant + stage-2 not_relevant) therefore stays eligible here — the
    deliberate inverse of the sweep's general "demoted doc excluded from
    screened-in scope" rule, which applies to readers keyed off the highest
    screening stage rather than stage 1 specifically."""
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    _, demoted_tss = _seed_acquired_link(
        conn, task_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(
        conn, task_id, run_id, scope_id, demoted_tss, status="relevant", screen_stage=1
    )
    seed_screening_result(
        conn, task_id, run_id, scope_id, demoted_tss, status="not_relevant", screen_stage=2
    )

    summary = run_ingest(conn, task_id, run_id, scope_id)

    assert summary["eligible"] == 1
    status, error = conn.execute(
        select(
            task_source_snapshot.c.full_text_status, task_source_snapshot.c.full_text_error,
        )
        .where(task_source_snapshot.c.task_source_snapshot_id == demoted_tss)
    ).one()
    assert (status, error) == ("fetch_failed", "no_url")


def test_idempotency_and_retry(conn: Connection) -> None:
    task_id, run_id, scope_id = seed_small_corpus(conn)
    first = run_ingest(conn, task_id, run_id, scope_id)
    assert first["ingested"] == 2
    assert first["fetch_failed"] == 1
    assert first["parse_failed"] == 1
    assert first["by_reason"] == {"not_found": 1, "thin_text": 1}
    assert (
        first["eligible"]
        == first["ingested"] + first["already_ingested"]
        + first["fetch_failed"] + first["parse_failed"]
    )
    n_ft_before = _full_text_snapshot_count(conn, task_id)

    run_id_2 = seed_run(conn, task_id)
    second = run_ingest(conn, task_id, run_id_2, scope_id)

    assert second["already_ingested"] == 2
    assert second["ingested"] == 0
    assert second["fetch_failed"] == 1
    assert second["parse_failed"] == 1
    assert second["by_reason"] == {"not_found": 1, "thin_text": 1}
    assert (
        second["eligible"]
        == second["ingested"] + second["already_ingested"]
        + second["fetch_failed"] + second["parse_failed"]
    )
    n_ft_after = _full_text_snapshot_count(conn, task_id)
    assert n_ft_after == n_ft_before  # no new full-text snapshots on retry


def test_harness_roundtrip_and_events(conn: Connection) -> None:
    task_id, run_id, scope_id = seed_small_corpus(conn)
    ingest_run_id = seed_run(conn, task_id)
    config = compile(Plan(component="ingest_full_text", evidence_scope_id=scope_id))
    outcome = run_harness(
        conn, config=config, task_id=task_id, run_id=ingest_run_id,
        provider=StubEchoProvider(),
    )

    run_events = [
        e for e in events.read(conn, task_id) if e["run_id"] == ingest_run_id
    ]
    types = {e["event_type"] for e in run_events}
    assert types <= _KNOWN_INGEST_RUN_EVENT_TYPES
    assert "run.completed" in types
    assert not any(t.startswith(("source.", "fulltext.")) for t in types)

    summary = outcome["summary"]
    assert summary is not None
    assert summary["eligible"] == 4
    assert summary["ingested"] == 2
    assert summary["fetch_failed"] == 1
    assert summary["parse_failed"] == 1
    assert summary["by_reason"] == {"not_found": 1, "thin_text": 1}

    assert _full_text_snapshot_count(conn, task_id) == 2


def test_delete_task_data_with_fulltext(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    env_snap_id, tss_id = seed_source(conn, task_id)

    ft_snap_id = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=ft_snap_id,
        content_hash="synthetic-ft-hash",
        text_basis="full_text",
        source_locator="https://example.org/synthetic-doc",
        metadata={"parse_profile": "x"},
        created_at=now(),
    ))
    chunk_id = uuid.uuid4()
    conn.execute(chunk_table.insert().values(
        chunk_id=chunk_id,
        source_snapshot_id=ft_snap_id,
        sequence=1,
        content="synthetic content",
        content_hash="synthetic-chunk-hash",
        locator={"paragraph": 1},
        segmentation_policy="x",
        created_at=now(),
    ))
    conn.execute(
        task_source_snapshot.update()
        .where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
        .values(full_text_snapshot_id=ft_snap_id, full_text_status="ingested")
    )

    delete_task_data(conn, task_id)

    n_snapshots = conn.execute(
        select(sa.func.count()).select_from(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id.in_([env_snap_id, ft_snap_id]))
    ).scalar_one()
    assert n_snapshots == 0
    n_chunks = conn.execute(
        select(sa.func.count()).select_from(chunk_table)
        .where(chunk_table.c.chunk_id == chunk_id)
    ).scalar_one()
    assert n_chunks == 0


def test_downstream_unchanged(conn: Connection) -> None:
    task_id, run_id, scope_id = seed_small_corpus(conn)
    classify_sources(
        conn, task_id=task_id, run_id=run_id,
        context=ClassifyContext(scope_id=scope_id, intent="test", context={}),
    )
    appraise_sources(
        conn, task_id=task_id, run_id=run_id,
        context=AppraiseContext(scope_id=scope_id, intent="test", context={}),
    )

    def _snapshot(table: Any) -> dict[uuid.UUID, dict[str, Any]]:
        return {
            r.task_source_snapshot_id: dict(r._mapping)
            for r in conn.execute(select(table).where(table.c.task_id == task_id)).fetchall()
        }

    before_classify = _snapshot(source_classification_result)
    before_appraise = _snapshot(source_appraisal_result)

    run_ingest(conn, task_id, run_id, scope_id)

    after_classify = _snapshot(source_classification_result)
    after_appraise = _snapshot(source_appraisal_result)

    assert before_classify == after_classify
    assert before_appraise == after_appraise


def test_javascript_wall_page_is_blocked_by_host_not_full_text() -> None:
    """Issue #74: a 284-character "JavaScript is disabled" page cleared the thin-text
    floor and was stored as the document's full text."""
    wall = (
        b"<html><body><div><p>JavaScript is disabled in your browser. Please enable "
        b"JavaScript to proceed. A required part of this site couldn't load. This may "
        b"be due to a browser extension, network issues, or browser settings. Please "
        b"check your connection, disable any ad blockers, or try using a different "
        b"browser.</p></div></body></html>"
    )
    assert parse_and_segment(wall, "text/html", thin_min=200) == {
        "status": "error",
        "reason": "blocked_by_host",
    }

    article = (
        b"<html><body><article><p>This evaluation of youth employment programmes "
        b"notes that the survey tool required participants to enable JavaScript, which "
        b"excluded some respondents.</p>"
        + b"<p>Further findings on programme outcomes across regions and cohorts.</p>" * 40
        + b"</article></body></html>"
    )
    assert parse_and_segment(article, "text/html", thin_min=200)["status"] == "ok"


def test_progress_ticks_carry_store_status_counts(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Task 057 (N3): the stage publishes ``ingest`` ticks from the stored statuses:
    ``parsed`` is the eligible documents ``ingested`` so far (those the store held
    before the run included), ``fetched`` is null (one call fetches and parses, so
    a fetched-but-unparsed count does not exist), ``total`` the eligible set."""
    ticks: list[dict[str, Any]] = []
    monkeypatch.setattr(
        ingest_full_text, "publish_current_tick", lambda **kwargs: ticks.append(kwargs)
    )
    task_id, run_id, scope_id = seed_small_corpus(conn)
    first = run_ingest(conn, task_id, run_id, scope_id)
    assert ticks
    assert {tick["stage"] for tick in ticks} == {"ingest"}
    assert {tick["total"] for tick in ticks} == {first["eligible"]} == {4}
    assert {tick["fetched"] for tick in ticks} == {None}
    for tick in ticks:
        assert 0 <= tick["parsed"] <= tick["total"]
        assert tick["note"]
    assert [t["parsed"] for t in ticks] == sorted(t["parsed"] for t in ticks)
    assert ticks[-1]["parsed"] == first["ingested"] == 2

    ticks.clear()
    second = run_ingest(conn, task_id, seed_run(conn, task_id), scope_id)
    assert second["already_ingested"] == 2
    # The store's two ``ingested`` rows count as read from the start.
    assert ticks and all(t["parsed"] >= 2 for t in ticks)
    assert ticks[-1]["parsed"] == 2
