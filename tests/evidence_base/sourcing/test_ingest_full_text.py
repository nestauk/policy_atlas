"""Tests for full-text ingestion (task 008).

Seeding helpers + the lead-authored concurrency/egress/timeout cases live at the
top; the contract's bulk test list follows below.
"""

import json
import re
import socket
import time
import uuid
from collections.abc import Generator
from importlib import resources
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
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import (
    event_log,
    metadata,
    project_source_snapshot,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
)
from policy_atlas.evidence_base.screen.appraise import AppraiseContext, appraise_sources
from policy_atlas.evidence_base.screen.classify import ClassifyContext, classify_sources
from policy_atlas.evidence_base.screen.screen import ScreenContext, screen_sources
from policy_atlas.evidence_base.sourcing import ingest_full_text
from policy_atlas.evidence_base.sourcing.acquire import (
    AcquireContext,
    OpenAlexFixtureBackend,
    OvertonFixtureBackend,
    SearchBackend,
    acquire_sources,
)
from policy_atlas.evidence_base.sourcing.grounding import content_hash
from policy_atlas.evidence_base.sourcing.ingest_full_text import (
    FixtureFetcher,
    IngestFullTextContext,
    _highest_priority_fetch_reason,
    _run_parse_jobs,
    candidate_urls,
    ingest_full_text_sources,
    parse_and_segment,
)
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    delete_project_data,
    executed_calls_for,
    now,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

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
    """Acquire + screen the committed fixtures; return (project_id, run_id, scope_id)."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    ctx = AcquireContext(scope_id=scope_id, intent="test", context={})
    backends = [OpenAlexFixtureBackend(), OvertonFixtureBackend()]
    acquire_sources(
        conn, project_id=project_id, run_id=run_id, context=ctx,
        backends=cast("list[SearchBackend]", backends),
        executed_calls=executed_calls_for(backends, ctx.intent),
    )
    screen_sources(
        conn, project_id=project_id, run_id=run_id,
        context=ScreenContext(scope_id=scope_id, intent="test", context={}),
    )
    return project_id, run_id, scope_id


def _seed_acquired_link(
    conn: Connection, project_id: uuid.UUID, run_id: uuid.UUID, meta: dict[str, Any]
) -> tuple[uuid.UUID, uuid.UUID]:
    """Insert a bare acquired-origin envelope snapshot + link (no chunk — unneeded by ingest).

    Returns (source_snapshot_id, project_source_snapshot_id).
    """
    snap_id = uuid.uuid4()
    pss_id = uuid.uuid4()
    conn.execute(source_snapshot.insert().values(
        source_snapshot_id=snap_id,
        content_hash=str(uuid.uuid4()),
        text_basis="abstract_only",
        source_locator="https://example.org/synthetic",
        metadata=meta,
        created_at=now(),
    ))
    conn.execute(project_source_snapshot.insert().values(
        project_source_snapshot_id=pss_id,
        project_id=project_id,
        source_snapshot_id=snap_id,
        origin="acquired",
        run_id=run_id,
        ingested_at=now(),
    ))
    return snap_id, pss_id


def seed_small_corpus(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Four hand-seeded links (PDF ok · HTML ok · 404 · thin) — for property tests
    that don't need the full 24-document corpus. Expected outcome: 4 eligible →
    2 ingested, 1 fetch_failed/not_found, 1 parse_failed/thin_text.
    """
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
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
        _, pss_id = _seed_acquired_link(conn, project_id, run_id, meta)
        seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    return project_id, run_id, scope_id


def run_ingest(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    **kwargs: Any,
) -> dict[str, Any]:
    """Run ingest_full_text_sources over the fixture fetcher with test-friendly defaults."""
    kwargs.setdefault("fetcher", FixtureFetcher())
    kwargs.setdefault("max_workers", 4)
    # Generous test-only headroom: outcome-distribution assertions must not flip on
    # machine load (4 concurrent parses + whatever else the host runs). Timeout
    # *semantics* are covered by the dedicated timeout test; the product default
    # stays PARSE_TIMEOUT_SECONDS in src.
    kwargs.setdefault("parse_timeout", 300.0)
    return ingest_full_text_sources(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=IngestFullTextContext(scope_id=scope_id, intent="test", context={}),
        **kwargs,
    )


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
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    meta: dict[str, Any],
) -> uuid.UUID:
    _, pss_id = _seed_acquired_link(conn, project_id, run_id, meta)
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    return pss_id


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


def _corpus_state(conn: Connection, project_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """Normalized, id-free ingest outcome per link: status, reason, snapshot content,
    chunk sequence/hash/locator/policy — the comparable surface for determinism."""
    full_text_snap = source_snapshot.alias("full_text_snap")
    rows = conn.execute(
        select(
            source_snapshot.c.content_hash,  # envelope hash: stable per-document key
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
            project_source_snapshot.c.full_text_snapshot_id,
            full_text_snap.c.content_hash,
            full_text_snap.c.source_locator,
            full_text_snap.c.metadata,
        )
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            ).outerjoin(
                full_text_snap,
                project_source_snapshot.c.full_text_snapshot_id
                == full_text_snap.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
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
        if meta is not None:
            # ids/run breadcrumbs differ across projects by construction
            meta.pop("envelope_source_snapshot_id", None)
            meta.pop("ingested_by_run_id", None)
        state.append((env_hash, status, error, ft_hash, ft_locator, meta, tuple(chunks)))
    return sorted(state, key=lambda t: t[0])


def _summary_without_wall_clock(summary: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(summary)
    comparable.pop("wall_clock_s", None)
    return comparable


# --- Fan-out determinism, timeout termination, zero egress (lead-authored) ---


def test_fanout_determinism_workers_1_vs_4(
    ingested_corpus: CorpusFixture, engine: Engine, conn: Connection
) -> None:
    """workers=1 and workers=4 produce identical DB state (decision 8).

    Rides the module fixture (already run at workers=1) as one leg instead of
    paying for a second full 24-document run; only the workers=4 leg is fresh.
    """
    fixture_project, _, _, fixture_summary, _ = ingested_corpus
    p4, r4, s4 = seed_corpus(conn)
    summary4 = run_ingest(conn, p4, r4, s4, max_workers=4)
    assert _summary_without_wall_clock(fixture_summary) == _summary_without_wall_clock(summary4)
    with engine.connect() as conn_a:
        state_a = _corpus_state(conn_a, fixture_project)
    assert state_a == _corpus_state(conn, p4)


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

    project_id, run_id, scope_id = seed_small_corpus(conn)
    start = time.monotonic()
    summary = run_ingest(
        conn, project_id, run_id, scope_id,
        max_workers=2, parse_timeout=1.0, parse_fn=_slow_parse,
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


def test_timeout_does_not_swallow_completed_sibling() -> None:
    """A fast job co-started with a genuinely-hung sibling keeps its result
    (step-7 review finding, confirmed): the drain loop blocks on the hung job's
    whole budget, so by the time the fast job is dequeued its own deadline has
    lapsed — its buffered ``ok`` must still be received, never mislabelled
    ``timeout``.
    """
    import multiprocessing

    # parse_timeout must comfortably exceed worker spawn + package import
    # (~1s idle, >5s under heavy host load — observed 017): the deadline clock
    # starts at proc.start(), so too tight a budget mislabels a healthy fast
    # worker as the timeout this test exists to rule out. 20s keeps the
    # property intact — the fast job's deadline still lapses while the hung
    # sibling drains — with spawn headroom.
    results = _run_parse_jobs(
        [(0, b"slow", "text/plain"), (1, b"fast", "text/plain")],
        max_workers=2, parse_timeout=20.0, thin_min=0, parse_fn=_sleep_by_marker_parse,
    )
    assert results[0] == {"status": "error", "reason": "timeout"}
    assert results[1]["status"] == "ok"
    for proc in multiprocessing.active_children():
        proc.join(timeout=5)
    assert not multiprocessing.active_children(), "worker processes leaked"


def _socket_deny_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Spawn-picklable wrapper: denies socket creation *inside the worker*, then
    parses for real — extends the zero-egress proof across the process boundary
    (step-7 security finding: the parent-side patch does not reach spawned children,
    where the third-party parsers actually run)."""
    socket.socket = _deny_socket  # type: ignore[misc, assignment]
    return parse_and_segment(body, content_type, thin_min)


def _deny_socket(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("socket creation attempted inside parse worker")


def test_zero_egress_socket_deny(conn: Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """A fixture ingest with socket creation blocked completes green
    (adversarial finding 5) — the zero-egress claim proven at runtime, in the
    parent (monkeypatch) and inside every spawned parse worker
    (``_socket_deny_parse``, step-7 security finding).

    Scoped, not autouse: the suite's own Postgres connection runs over a socket,
    so the guard patches socket.socket only around the ingest call, after the DB
    connection is established (plan-review finding 2).

    Deliberately narrowed to a 4-doc fixture subset (both parser paths, real
    committed files, full fetch→parse→write) — the full-breadth ingest runs
    unguarded in the module fixture; narrowing noted in verification.md.
    """
    project_id, run_id, scope_id = seed_small_corpus(conn)

    monkeypatch.setattr(socket, "socket", _deny_socket)
    summary = run_ingest(conn, project_id, run_id, scope_id, parse_fn=_socket_deny_parse)
    monkeypatch.undo()
    assert summary["ingested"] == 2
    assert summary["fetch_failed"] == 1
    assert summary["parse_failed"] == 1


def test_recorder_script_not_imported_by_package() -> None:
    """The full-text recorder stays outside the package import graph (007 precedent)."""
    src_dir = Path(__file__).resolve().parents[3] / "src" / "policy_atlas"
    for module in src_dir.rglob("*.py"):
        assert "record_fulltext_fixtures" not in module.read_text()


def test_ingest_module_has_no_http_client() -> None:
    """ingest_full_text.py imports no HTTP client or socket machinery."""
    module = (
        Path(__file__).resolve().parents[3] / "src" / "policy_atlas"
        / "evidence_base" / "sourcing" / "ingest_full_text.py"
    ).read_text()
    forbidden = re.compile(
        r"^\s*(import|from)\s+"
        r"(urllib\.(?:request|error)|requests|httpx|aiohttp|http\.client|socket)\b",
        re.MULTILINE,
    )
    assert not forbidden.search(module)


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
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_relevant_acquired(
        conn, project_id, run_id, scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": "https://example.org/x.pdf"}},
    )
    with pytest.raises(FileNotFoundError, match=re.escape(str(tmp_path))):
        run_ingest(conn, project_id, run_id, scope_id, fetcher=FixtureFetcher(root=tmp_path))


def test_fetch_failure_reason_priority_helper() -> None:
    assert _highest_priority_fetch_reason(["not_found", "timeout"]) == "timeout"
    assert (
        _highest_priority_fetch_reason(["not_found", "paywall", "fetch_error"])
        == "paywall"
    )
    assert _highest_priority_fetch_reason(["blocked", "blocked_by_host"]) == "blocked_by_host"
    assert _highest_priority_fetch_reason([]) == "no_url"


def test_escaped_fetcher_raise_is_reason_coded_per_link(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    url = "https://example.org/raises?token=SECRET"
    pss_id = _seed_relevant_acquired(
        conn,
        project_id,
        run_id,
        scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": url}},
    )
    fetcher = _ScriptedFetcher({url: RuntimeError("boom")})

    with capture_logs() as logs:
        summary = run_ingest(
            conn,
            project_id,
            run_id,
            scope_id,
            fetcher=fetcher,
            parse_fn=_ok_parse,
            max_workers=1,
        )

    assert summary["fetch_failed"] == 1
    assert summary["by_reason"] == {"fetch_error": 1}
    status, error = conn.execute(
        select(
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
        )
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
    ).one()
    assert (status, error) == ("fetch_failed", "fetch_error")
    assert any(entry["event"] == "fulltext.fetcher_escaped" for entry in logs)
    assert "SECRET" not in repr(logs)


def test_discovery_extends_cascade_to_discovered_pdf(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    landing_url = "https://example.org/landing?token=SECRET"
    discovered_url = "https://cdn.example.org/report.pdf?download=SECRET"
    pss_id = _seed_relevant_acquired(
        conn,
        project_id,
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
            project_id,
            run_id,
            scope_id,
            fetcher=fetcher,
            parse_fn=_html_fails_pdf_ok_parse,
            max_workers=1,
        )

    assert summary["ingested"] == 1
    assert fetcher.calls == [landing_url, discovered_url]
    row = conn.execute(
        select(
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
            project_source_snapshot.c.full_text_snapshot_id,
        )
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
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
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    urls = {
        "ok": "https://example.org/ok.txt",
        "fail": "https://example.org/fail.txt",
        "large": "https://example.org/large.txt",
    }
    for url in urls.values():
        _seed_relevant_acquired(
            conn,
            project_id,
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
        project_id,
        run_id,
        scope_id,
        fetcher=fetcher,
        parse_fn=_fail_on_marker_parse,
        max_workers=2,
    )

    assert summary["ingested"] == 1
    assert summary["parse_failed"] == 1
    assert summary["fetch_failed"] == 1
    assert summary["by_reason"] == {"too_large": 1, "corrupt": 1}
    assert summary["bytes_fetched"] == len(b"ok") + len(b"fail") + len(b"toolong")
    assert sorted(fetcher.releases) == [len(b"ok"), len(b"fail"), len(b"toolong")]


def test_oa_cross_check_upgrade_and_inconsistency_log(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    closed_url = "https://example.org/closed.pdf"
    open_url = "https://example.org/open.pdf"
    closed_pss = _seed_relevant_acquired(
        conn,
        project_id,
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
    open_pss = _seed_relevant_acquired(
        conn,
        project_id,
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
            project_id,
            run_id,
            scope_id,
            fetcher=fetcher,
            parse_fn=_ok_parse,
            max_workers=1,
        )

    assert summary["by_reason"] == {"paywall": 1, "blocked_by_host": 1}
    rows = {
        pss_id: error
        for pss_id, error in conn.execute(
            select(
                project_source_snapshot.c.project_source_snapshot_id,
                project_source_snapshot.c.full_text_error,
            )
            .where(
                project_source_snapshot.c.project_source_snapshot_id.in_(
                    [closed_pss, open_pss]
                )
            )
        ).fetchall()
    }
    assert rows[closed_pss] == "paywall"
    assert rows[open_pss] == "blocked_by_host"
    inconsistency_logs = [
        entry for entry in logs if entry["event"] == "fulltext.oa_inconsistency"
    ]
    assert len(inconsistency_logs) == 1
    assert inconsistency_logs[0]["pss_id"] == str(open_pss)
    assert inconsistency_logs[0]["reason"] == "blocked_by_host"


def test_summary_includes_attempted_bytes_and_wall_clock(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_relevant_acquired(
        conn,
        project_id,
        run_id,
        scope_id,
        {"backend": "openalex", "provider_fields": {}},
    )

    with capture_logs() as logs:
        summary = run_ingest(conn, project_id, run_id, scope_id)

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
    from policy_atlas.evidence_base.sourcing.fetch_live import (
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
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _seed_relevant_acquired(
        conn, project_id, run_id, scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": tokened_ok}},
    )
    _seed_relevant_acquired(
        conn, project_id, run_id, scope_id,
        {"backend": "overton", "provider_fields": {"pdf_url": tokened_fail}},
    )
    fetcher = _ScriptedFetcher({
        tokened_ok: ingest_full_text.FetchResult(
            status="ok", content_type="text/plain", body=b"x" * 400
        ),
        tokened_fail: ingest_full_text.FetchResult(status="error", error="not_found"),
    })

    with capture_logs() as logs:
        summary = run_ingest(conn, project_id, run_id, scope_id, fetcher=fetcher)

    assert summary["ingested"] == 1 and summary["fetch_failed"] == 1
    log_dump = repr(logs)
    assert "SECRET-OK" not in log_dump
    assert "SECRET-FAIL" not in log_dump
    assert "token=" not in log_dump
    # The verbatim URL still persists as provenance (provider-data retention).
    fetched_from = conn.execute(
        select(source_snapshot.c.metadata["fetched_from"].astext)
        .where(source_snapshot.c.text_basis == "full_text")
        .where(
            source_snapshot.c.source_snapshot_id
            == select(project_source_snapshot.c.full_text_snapshot_id)
            .where(project_source_snapshot.c.project_id == project_id)
            .where(project_source_snapshot.c.full_text_status == "ingested")
            .scalar_subquery()
        )
    ).scalar_one()
    assert fetched_from == tokened_ok


def test_parallel_fetch_matches_serial_outcomes(conn: Connection) -> None:
    """Decision 5's determinism invariant: fetch_workers > 1 persists exactly the
    outcomes and eligible-set write order of the serial path."""

    def seed_one_project() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        project_id, run_id = seed_project_and_run(conn)
        scope_id = seed_scope(conn, project_id)
        for n in range(6):
            _seed_relevant_acquired(
                conn, project_id, run_id, scope_id,
                {
                    "backend": "overton",
                    "provider_fields": {"pdf_url": f"https://example.org/doc-{n}.pdf"},
                },
            )
        return project_id, run_id, scope_id

    def script() -> dict[str, ingest_full_text.FetchResult | BaseException]:
        outcomes: dict[str, ingest_full_text.FetchResult | BaseException] = {}
        for n in range(6):
            url = f"https://example.org/doc-{n}.pdf"
            if n % 3 == 0:
                outcomes[url] = ingest_full_text.FetchResult(
                    status="ok", content_type="text/plain", body=f"body {n} ".encode() * 60
                )
            elif n % 3 == 1:
                outcomes[url] = ingest_full_text.FetchResult(status="error", error="paywall")
            else:
                outcomes[url] = ingest_full_text.FetchResult(status="error", error="not_found")
        return outcomes

    def outcomes_for(project_id: uuid.UUID) -> dict[str, tuple[str, str | None]]:
        # Keyed by the doc's one candidate URL: pss ids are random UUIDs, so
        # positional order is not comparable across two seeded projects.
        rows = conn.execute(
            select(
                source_snapshot.c.metadata,
                project_source_snapshot.c.full_text_status,
                project_source_snapshot.c.full_text_error,
            )
            .select_from(
                project_source_snapshot.join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(project_source_snapshot.c.project_id == project_id)
        ).fetchall()
        return {
            row.metadata["provider_fields"]["pdf_url"]: (
                row.full_text_status,
                row.full_text_error,
            )
            for row in rows
        }

    serial_project, serial_run, serial_scope = seed_one_project()
    serial_summary = run_ingest(
        conn, serial_project, serial_run, serial_scope,
        fetcher=_ScriptedFetcher(script()), fetch_workers=1, parse_fn=_ok_parse,
    )
    parallel_project, parallel_run, parallel_scope = seed_one_project()
    parallel_summary = run_ingest(
        conn, parallel_project, parallel_run, parallel_scope,
        fetcher=_ScriptedFetcher(script()), fetch_workers=4, parse_fn=_ok_parse,
    )

    drop_wall_clock = ("wall_clock_s",)
    assert {k: v for k, v in serial_summary.items() if k not in drop_wall_clock} == {
        k: v for k, v in parallel_summary.items() if k not in drop_wall_clock
    }
    assert outcomes_for(serial_project) == outcomes_for(parallel_project)


# --- Bulk contract tests ---

# Ground-truth strings below are extracted from the actual committed fixtures at
# authoring time (scratch `parse_and_segment` / pymupdf runs) — never invented.

# frontiers_school_readiness_2022.pdf, abstract "Method" paragraph (chunk 1, no
# heading yet) — spans a PDF line-wrap; compared after whitespace normalization.
FRONTIERS_ABSTRACT_SENTENCE = (
    "REDI was delivered by 63 teachers in 37 community-based childcare centers "
    "with center directors serving as local implementation coaches."
)

# worldbank_obesity_flagship.pdf, back-matter eco-audit page (doc[-2].get_text()) —
# survives only if the 233-page document is parsed whole, never truncated.
WB_BACKMATTER_PHRASE = "Green Press Initiative"

# nesta_heat_pumps_report_page.html, main-content paragraph 2 (verified present
# via trafilatura extraction at authoring time).
NESTA_REPORT_SENTENCE = (
    "This paper sets out a comprehensive analysis of the cost of heat pumps "
    "and the prospects for making them more affordable."
)
# nesta_heat_pumps_report_page.html, footer boilerplate (verified absent from the
# trafilatura extraction at authoring time — main-content-only, not full-page text).
NESTA_FOOTER_BOILERPLATE = "Nesta is a registered charity in England and Wales 1144091"

_ALLOWED_LICENCES = {"CC-BY-4.0", "CC-BY-3.0-IGO", "CC0-1.0"}
_REQUIRED_FT_METADATA_KEYS = {
    "parse_profile", "segmentation_policy", "fetched_from", "content_type",
    "envelope_source_snapshot_id", "ingested_by_run_id",
}
_KNOWN_INGEST_RUN_EVENT_TYPES = {
    "component.started", "component.completed", "run.completed", "run.failed",
}


def _norm_ws(text: str) -> str:
    """Collapse whitespace so PDF line-wraps don't break a literal-sentence check."""
    return " ".join(text.split())


def _envelope_snapshots(conn: Connection, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """Envelope source_snapshot rows for a project's links, as plain dicts."""
    return [
        dict(r._mapping)
        for r in conn.execute(
            select(source_snapshot)
            .select_from(
                project_source_snapshot.join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(project_source_snapshot.c.project_id == project_id)
        ).fetchall()
    ]


@pytest.fixture(scope="module")
def ingested_corpus(engine: Engine) -> Generator[CorpusFixture, None, None]:
    """One committed acquire+screen+ingest run, shared read-only across this module.

    Real PDF/HTML parses cost ~15-20s; every read-only test below rides this single
    run instead of paying for its own (mutating tests use the rollback-safe function-
    scoped ``conn`` fixture and seed their own corpus).

    Runs at ``max_workers=1``: this doubles as the workers=1 leg of the fan-out
    determinism comparison in ``test_fanout_determinism_workers_1_vs_4``, which
    seeds its own fresh workers=4 corpus and compares against this one instead of
    paying for two full 24-document runs.
    """
    with engine.connect() as c:
        project_id, run_id, scope_id = seed_corpus(c)
        envelope_snapshots = _envelope_snapshots(c, project_id)
        summary = run_ingest(c, project_id, run_id, scope_id, max_workers=1)
        c.commit()
    yield project_id, run_id, scope_id, summary, envelope_snapshots
    with engine.connect() as c:
        delete_project_data(c, project_id)
        c.commit()


def _link_rows(conn: Connection, project_id: uuid.UUID) -> list[Any]:
    """All links for a project with their envelope + full-text snapshot fields."""
    ft = source_snapshot.alias("ft")
    return list(conn.execute(
        select(
            project_source_snapshot.c.run_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
            source_snapshot.c.metadata.label("envelope_metadata"),
            ft.c.source_locator.label("ft_source_locator"),
            ft.c.metadata.label("ft_metadata"),
        )
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            ).outerjoin(
                ft,
                project_source_snapshot.c.full_text_snapshot_id == ft.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall())


def _by_backend_record_id(conn: Connection, project_id: uuid.UUID, record_id: str) -> Any:
    """The single link row whose envelope metadata carries this backend_record_id."""
    matches = [
        r for r in _link_rows(conn, project_id)
        if r.envelope_metadata.get("backend_record_id") == record_id
    ]
    assert len(matches) == 1, f"expected exactly one link for {record_id!r}, got {len(matches)}"
    return matches[0]


def _full_text_snapshot_count(conn: Connection, project_id: uuid.UUID) -> int:
    """Count of distinct full-text snapshots attached within one project (project-scoped:
    source_snapshot itself carries no project_id)."""
    return conn.execute(
        select(sa.func.count(sa.distinct(project_source_snapshot.c.full_text_snapshot_id)))
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.full_text_snapshot_id.is_not(None))
    ).scalar_one()


def test_outcome_distribution(ingested_corpus: CorpusFixture) -> None:
    _, _, _, summary, _ = ingested_corpus
    assert summary["eligible"] == EXPECTED_ELIGIBLE
    assert summary["ingested"] == EXPECTED_INGESTED
    assert summary["already_ingested"] == 0
    assert summary["fetch_failed"] == EXPECTED_FETCH_FAILED
    assert summary["parse_failed"] == EXPECTED_PARSE_FAILED
    assert summary["by_reason"] == EXPECTED_BY_REASON
    assert (
        summary["eligible"]
        == summary["ingested"] + summary["already_ingested"]
        + summary["fetch_failed"] + summary["parse_failed"]
    )


@pytest.mark.parametrize(
    ("record_id", "status", "error", "fetched_from"),
    [
        # openalex: best_oa_location.pdf_url is the FIRST cascade rung (decision 4)
        ("https://example.org/5f2286252e57", "ingested", None,
         "https://doi.org/10.99999/287b9e9e3a"),
        ("https://example.org/c8d8aa774216", "fetch_failed", "paywall", None),
        ("https://example.org/b1d9810181d0", "fetch_failed", "not_found", None),
        ("https://example.org/9e1652ffb458", "fetch_failed", "too_large", None),
        ("https://example.org/6d1e9d4886bb", "parse_failed", "thin_text", None),
        ("https://example.org/325a3b216a30", "ingested", None, None),  # HTML, trafilatura
        ("https://example.org/c62a1c4258a2", "ingested", None, None),  # BMC HTML
        # overton: pdf_url "n/a" sentinel dropped, document_url used
        ("sanitizedorg1bcd6b-9a9e73d38cfdde74d7dee8c1c06189f2", "ingested", None,
         "https://doi.org/10.99999/cf91b048b2"),
        # overton: cascade fallback — pdf_url 404s, document_url succeeds
        ("sanitizedorg93a3df-7e7e75d9cd6f5b53a0803edca29f531a", "ingested", None,
         "https://example.org/e1209ba1a2a6"),
        ("sanitizedorgf49937-f18086f777c8acbad55bb7f2230c557d", "ingested", None, None),
        ("sanitizedorg23396d-80ffb71f4011d31866fe5e4032586a8c", "parse_failed",
         "no_text_layer", None),
        ("sanitizedorg5644d9-72681ca7d0f78da51e464687e8295a7f", "parse_failed", "corrupt", None),
        ("sanitizedorgfb4a6e-15acd6e31818235c42f3d8daf6e1ea48", "fetch_failed",
         "too_large", None),
        ("sanitizedorga9aa9d-c186ae531fb481b0cc4fb0dd6669476e", "fetch_failed",
         "not_found", None),
        # Overton doc: both candidate URLs 403 and there is no OA field to
        # cross-check (decision 8 fixture-403-parity rider), so it reports the
        # uncorroborated blocked_by_host honestly rather than paywall.
        ("sanitizedorgdf2d12-42aba8211480495ee10e4ab8faa88047", "fetch_failed",
         "blocked_by_host", None),
    ],
)
def test_per_link_statuses(
    ingested_corpus: CorpusFixture,
    engine: Engine,
    record_id: str,
    status: str,
    error: str | None,
    fetched_from: str | None,
) -> None:
    project_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, project_id, record_id)
    assert row.full_text_status == status
    assert row.full_text_error == error
    if fetched_from is not None:
        assert row.ft_source_locator == fetched_from
        assert row.ft_metadata["fetched_from"] == fetched_from


def test_pdf_structure_chunks(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, project_id, "https://example.org/5f2286252e57")
        assert row.full_text_status == "ingested"
        chunks = conn.execute(
            select(
                chunk_table.c.sequence, chunk_table.c.content, chunk_table.c.locator,
                chunk_table.c.segmentation_policy,
            )
            .where(chunk_table.c.source_snapshot_id == row.full_text_snapshot_id)
            .order_by(chunk_table.c.sequence)
        ).fetchall()
        assert [c.sequence for c in chunks] == list(range(1, len(chunks) + 1))
        for c in chunks:
            assert isinstance(c.locator["pages"], list) and c.locator["pages"]
            assert "heading_path" in c.locator
            assert c.segmentation_policy == "pymupdf4llm_struct_v1"
        assert any(c.locator["heading_path"] for c in chunks)
        assert row.ft_metadata["segmentation_policy"] == "pymupdf4llm_struct_v1"
        assert row.ft_metadata["parse_profile"] == "pymupdf4llm_v1"

        norm_sentence = _norm_ws(FRONTIERS_ABSTRACT_SENTENCE)
        assert any(norm_sentence in _norm_ws(c.content) for c in chunks)

        wb_row = _by_backend_record_id(
            conn, project_id, "sanitizedorgf49937-f18086f777c8acbad55bb7f2230c557d"
        )
        wb_chunks = conn.execute(
            select(chunk_table.c.content)
            .where(chunk_table.c.source_snapshot_id == wb_row.full_text_snapshot_id)
        ).fetchall()
        assert any(c.content.startswith("|") for c in wb_chunks)  # table kept whole


def test_no_truncation_long_report(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(
            conn, project_id, "sanitizedorgf49937-f18086f777c8acbad55bb7f2230c557d"
        )
        assert row.full_text_status == "ingested"
        chunks = conn.execute(
            select(chunk_table.c.content, chunk_table.c.locator)
            .where(chunk_table.c.source_snapshot_id == row.full_text_snapshot_id)
        ).fetchall()
    max_page = max(p for c in chunks for p in c.locator["pages"])
    assert max_page >= 220  # 233-page doc parsed whole (decision 6 — never truncated)
    total_chars = sum(len(c.content) for c in chunks)
    assert total_chars > 200_000
    joined = _norm_ws(" ".join(c.content for c in chunks))
    assert WB_BACKMATTER_PHRASE in joined


def test_html_main_content(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, project_id, "https://example.org/325a3b216a30")
        assert row.full_text_status == "ingested"
        chunks = conn.execute(
            select(
                chunk_table.c.content, chunk_table.c.locator, chunk_table.c.segmentation_policy,
            )
            .where(chunk_table.c.source_snapshot_id == row.full_text_snapshot_id)
            .order_by(chunk_table.c.sequence)
        ).fetchall()
    assert chunks
    assert row.ft_metadata["parse_profile"] == "trafilatura_v1"
    for i, c in enumerate(chunks, start=1):
        assert c.content.strip()
        assert c.segmentation_policy == "trafilatura_para_v1"
        assert c.locator == {"paragraph": i}
    joined = " ".join(c.content for c in chunks)
    assert NESTA_FOOTER_BOILERPLATE not in joined
    assert NESTA_REPORT_SENTENCE in joined


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


def test_success_metadata_complete(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        ft_ids = [
            row.full_text_snapshot_id
            for row in conn.execute(
                select(project_source_snapshot.c.full_text_snapshot_id)
                .where(project_source_snapshot.c.project_id == project_id)
                .where(project_source_snapshot.c.full_text_status == "ingested")
            ).fetchall()
        ]
        assert len(ft_ids) == EXPECTED_INGESTED
        for ft_id in ft_ids:
            snap = conn.execute(
                select(
                    source_snapshot.c.text_basis, source_snapshot.c.content_hash,
                    source_snapshot.c.source_locator, source_snapshot.c.metadata,
                )
                .where(source_snapshot.c.source_snapshot_id == ft_id)
            ).one()
            assert snap.text_basis == "full_text"
            assert set(snap.metadata) >= _REQUIRED_FT_METADATA_KEYS
            for key in _REQUIRED_FT_METADATA_KEYS:
                assert snap.metadata[key] is not None
            assert snap.source_locator == snap.metadata["fetched_from"]
            chunk_rows = conn.execute(
                select(chunk_table.c.content)
                .where(chunk_table.c.source_snapshot_id == ft_id)
                .order_by(chunk_table.c.sequence)
            ).fetchall()
            assert snap.content_hash == content_hash("".join(c.content for c in chunk_rows))


def test_envelope_immutability(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _, before = ingested_corpus
    with engine.connect() as conn:
        after = _envelope_snapshots(conn, project_id)
        assert (
            sorted(before, key=lambda r: r["source_snapshot_id"])
            == sorted(after, key=lambda r: r["source_snapshot_id"])
        )
        for row in after:
            assert row["text_basis"] == "abstract_only"
            chunk_row = conn.execute(
                select(chunk_table.c.content)
                .where(chunk_table.c.source_snapshot_id == row["source_snapshot_id"])
            ).one()
            assert row["content_hash"] == content_hash(chunk_row.content)


def test_governance_chain(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, run_id, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        ingested_rows = [
            r for r in _link_rows(conn, project_id) if r.full_text_status == "ingested"
        ]
        assert len(ingested_rows) == EXPECTED_INGESTED
        for row in ingested_rows:
            assert row.ft_metadata["ingested_by_run_id"] == str(run_id)
            assert (
                uuid.UUID(row.ft_metadata["envelope_source_snapshot_id"])
                == row.source_snapshot_id
            )
            n_search_events = conn.execute(
                select(sa.func.count()).select_from(event_log)
                .where(event_log.c.run_id == row.run_id)
                .where(event_log.c.event_type == "search.executed")
            ).scalar_one()
            assert n_search_events > 0


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
    assert len(metadata.tables) == 28
    project_id, _ = seed_project_and_run(conn)
    snap_id, pss_id = seed_source(conn, project_id)

    rejections: list[tuple[str, dict[str, Any]]] = [
        ("ck_pss_full_text_status", {"full_text_status": "bogus"}),
        ("ck_pss_full_text_consistent",
         {"full_text_status": "ingested", "full_text_snapshot_id": None}),
        ("ck_pss_full_text_consistent",
         {"full_text_status": "not_attempted", "full_text_snapshot_id": snap_id}),
        ("ck_pss_full_text_error_presence",
         {"full_text_status": "fetch_failed", "full_text_error": None}),
        ("ck_pss_full_text_error_presence",
         {"full_text_status": "not_attempted", "full_text_error": "oops"}),
    ]
    for constraint, values in rejections:
        with pytest.raises(IntegrityError, match=constraint), conn.begin_nested():
            conn.execute(
                project_source_snapshot.update()
                .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
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
        resources.files("policy_atlas").joinpath("data", "overton_documents.json").read_text()
    )["records"]
    record_zero = overton_records[0]
    assert record_zero["pdf_url"] == "n/a"  # sentinel; dropped, not a candidate
    assert candidate_urls({"backend": "overton", "provider_fields": record_zero}) == [
        "https://doi.org/10.99999/cf91b048b2"
    ]

    assert candidate_urls({"backend": "overton"}) == []


def test_no_url_persisted(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _, no_url_pss = _seed_acquired_link(
        conn, project_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(conn, project_id, run_id, scope_id, no_url_pss, status="relevant")

    _, unscreened_pss = _seed_acquired_link(
        conn, project_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    # deliberately never screened -> ineligible, stays not_attempted

    run_ingest(conn, project_id, run_id, scope_id)

    status, error = conn.execute(
        select(
            project_source_snapshot.c.full_text_status, project_source_snapshot.c.full_text_error,
        )
        .where(project_source_snapshot.c.project_source_snapshot_id == no_url_pss)
    ).one()
    assert (status, error) == ("fetch_failed", "no_url")

    status2, error2 = conn.execute(
        select(
            project_source_snapshot.c.full_text_status, project_source_snapshot.c.full_text_error,
        )
        .where(project_source_snapshot.c.project_source_snapshot_id == unscreened_pss)
    ).one()
    assert (status2, error2) == ("not_attempted", None)


def test_eligibility_boundaries(conn: Connection) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    _, uploaded_pss = seed_source(conn, project_id)  # origin="uploaded"
    seed_screening_result(conn, project_id, run_id, scope_id, uploaded_pss, status="relevant")

    _, not_relevant_pss = _seed_acquired_link(
        conn, project_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(
        conn, project_id, run_id, scope_id, not_relevant_pss, status="not_relevant"
    )

    _, failed_pss = _seed_acquired_link(
        conn, project_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(conn, project_id, run_id, scope_id, failed_pss, status="failed")

    other_scope_id = seed_scope(conn, project_id)
    _, other_scope_pss = _seed_acquired_link(
        conn, project_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(
        conn, project_id, run_id, other_scope_id, other_scope_pss, status="relevant"
    )

    run_ingest(conn, project_id, run_id, scope_id)

    for pss_id in (uploaded_pss, not_relevant_pss, failed_pss, other_scope_pss):
        status = conn.execute(
            select(project_source_snapshot.c.full_text_status)
            .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
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
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    _, demoted_pss = _seed_acquired_link(
        conn, project_id, run_id, {"backend": "openalex", "provider_fields": {}}
    )
    seed_screening_result(
        conn, project_id, run_id, scope_id, demoted_pss, status="relevant", screen_stage=1
    )
    seed_screening_result(
        conn, project_id, run_id, scope_id, demoted_pss, status="not_relevant", screen_stage=2
    )

    summary = run_ingest(conn, project_id, run_id, scope_id)

    assert summary["eligible"] == 1
    status, error = conn.execute(
        select(
            project_source_snapshot.c.full_text_status, project_source_snapshot.c.full_text_error,
        )
        .where(project_source_snapshot.c.project_source_snapshot_id == demoted_pss)
    ).one()
    assert (status, error) == ("fetch_failed", "no_url")


def test_idempotency_and_retry(conn: Connection) -> None:
    project_id, run_id, scope_id = seed_small_corpus(conn)
    first = run_ingest(conn, project_id, run_id, scope_id)
    assert first["ingested"] == 2
    assert first["fetch_failed"] == 1
    assert first["parse_failed"] == 1
    assert first["by_reason"] == {"not_found": 1, "thin_text": 1}
    assert (
        first["eligible"]
        == first["ingested"] + first["already_ingested"]
        + first["fetch_failed"] + first["parse_failed"]
    )
    n_ft_before = _full_text_snapshot_count(conn, project_id)

    run_id_2 = seed_run(conn, project_id)
    second = run_ingest(conn, project_id, run_id_2, scope_id)

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
    n_ft_after = _full_text_snapshot_count(conn, project_id)
    assert n_ft_after == n_ft_before  # no new full-text snapshots on retry


def test_harness_roundtrip_and_events(conn: Connection) -> None:
    project_id, run_id, scope_id = seed_small_corpus(conn)
    ingest_run_id = seed_run(conn, project_id)
    config = compile(Plan(component="ingest_full_text", evidence_scope_id=scope_id))
    run_harness(
        conn, config=config, project_id=project_id, run_id=ingest_run_id,
        provider=StubEchoProvider(),
    )

    run_events = [
        e for e in events.read(conn, project_id) if e["run_id"] == ingest_run_id
    ]
    types = {e["event_type"] for e in run_events}
    assert types <= _KNOWN_INGEST_RUN_EVENT_TYPES
    assert "run.completed" in types
    assert not any(t.startswith(("source.", "fulltext.")) for t in types)

    completed = [e["payload"] for e in run_events if e["event_type"] == "component.completed"]
    assert len(completed) == 1
    assert completed[0]["component"] == "ingest_full_text"
    assert completed[0]["eligible"] == 4
    assert completed[0]["ingested"] == 2
    assert completed[0]["fetch_failed"] == 1
    assert completed[0]["parse_failed"] == 1
    assert completed[0]["by_reason"] == {"not_found": 1, "thin_text": 1}

    started = [e for e in run_events if e["event_type"] == "component.started"]
    assert len(started) == 1

    assert _full_text_snapshot_count(conn, project_id) == 2


def test_delete_project_data_with_fulltext(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    env_snap_id, pss_id = seed_source(conn, project_id)

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
        project_source_snapshot.update()
        .where(project_source_snapshot.c.project_source_snapshot_id == pss_id)
        .values(full_text_snapshot_id=ft_snap_id, full_text_status="ingested")
    )

    delete_project_data(conn, project_id)

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
    project_id, run_id, scope_id = seed_small_corpus(conn)
    classify_sources(
        conn, project_id=project_id, run_id=run_id,
        context=ClassifyContext(scope_id=scope_id, intent="test", context={}),
    )
    appraise_sources(
        conn, project_id=project_id, run_id=run_id,
        context=AppraiseContext(scope_id=scope_id, intent="test", context={}),
    )

    def _snapshot(table: Any) -> dict[uuid.UUID, dict[str, Any]]:
        return {
            r.project_source_snapshot_id: dict(r._mapping)
            for r in conn.execute(select(table).where(table.c.project_id == project_id)).fetchall()
        }

    before_classify = _snapshot(source_classification_result)
    before_appraise = _snapshot(source_appraisal_result)

    run_ingest(conn, project_id, run_id, scope_id)

    after_classify = _snapshot(source_classification_result)
    after_appraise = _snapshot(source_appraisal_result)

    assert before_classify == after_classify
    assert before_appraise == after_appraise
