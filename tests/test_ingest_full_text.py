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
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from policy_atlas import events
from policy_atlas.acquire import (
    AcquireContext,
    OpenAlexFixtureBackend,
    OvertonFixtureBackend,
    acquire_sources,
)
from policy_atlas.appraise import AppraiseContext, appraise_sources
from policy_atlas.classify import ClassifyContext, classify_sources
from policy_atlas.grounding import content_hash
from policy_atlas.harness import run_harness
from policy_atlas.inference import StubEchoProvider
from policy_atlas.ingest_full_text import (
    FixtureFetcher,
    IngestFullTextContext,
    candidate_urls,
    ingest_full_text_sources,
)
from policy_atlas.plan import Plan, compile
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import (
    event_log,
    metadata,
    project_source_snapshot,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
)
from policy_atlas.screen import ScreenContext, screen_sources
from tests.helpers import (
    delete_project_data,
    now,
    seed_project_and_run,
    seed_run,
    seed_scope,
    seed_screening_result,
    seed_source,
)

# Expected outcome distribution over the committed fixture set (the manifest's
# outcome map is the spec these tests enforce; see contract decision 9 + plan Task 2/3).
EXPECTED_ELIGIBLE = 24
EXPECTED_INGESTED = 10
EXPECTED_FETCH_FAILED = 11
EXPECTED_PARSE_FAILED = 3
EXPECTED_BY_REASON = {
    "paywall": 4,
    "not_found": 5,
    "too_large": 2,
    "thin_text": 1,
    "no_text_layer": 1,
    "corrupt": 1,
}


def seed_corpus(conn: Connection) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Acquire + screen the committed fixtures; return (project_id, run_id, scope_id)."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    ctx = AcquireContext(scope_id=scope_id, intent="test", context={})
    acquire_sources(
        conn, project_id=project_id, run_id=run_id, context=ctx,
        backends=[OpenAlexFixtureBackend(), OvertonFixtureBackend()],
    )
    screen_sources(
        conn, project_id=project_id, run_id=run_id,
        context=ScreenContext(scope_id=scope_id, intent="test", context={}),
    )
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
    return ingest_full_text_sources(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=IngestFullTextContext(scope_id=scope_id, intent="test", context={}),
        **kwargs,
    )


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


# --- Fan-out determinism, timeout termination, zero egress (lead-authored) ---


def test_fanout_determinism_workers_1_vs_4(conn: Connection) -> None:
    """workers=1 and workers=4 produce identical DB state (decision 8)."""
    p1, r1, s1 = seed_corpus(conn)
    summary1 = run_ingest(conn, p1, r1, s1, max_workers=1)
    p4, r4, s4 = seed_corpus(conn)
    summary4 = run_ingest(conn, p4, r4, s4, max_workers=4)
    assert summary1 == summary4
    assert _corpus_state(conn, p1) == _corpus_state(conn, p4)


def _slow_parse(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Spawn-picklable slow-parser double for the timeout property."""
    time.sleep(60)
    return {"status": "ok", "chunks": [], "parse_profile": "x", "segmentation_policy": "y"}


def test_parse_timeout_terminates_worker_and_run_completes(conn: Connection) -> None:
    """A hung parse is genuinely terminated (finding 6): the run finishes with
    parse_failed/timeout well inside the double's sleep, leaving no live worker."""
    import multiprocessing

    project_id, run_id, scope_id = seed_corpus(conn)
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


def test_zero_egress_socket_deny(conn: Connection, monkeypatch: pytest.MonkeyPatch) -> None:
    """A full fixture ingest with socket creation blocked completes green
    (adversarial finding 5) — the zero-egress claim proven at runtime.

    Scoped, not autouse: the suite's own Postgres connection runs over a socket,
    so the guard patches socket.socket only around the ingest call, after the DB
    connection is established (plan-review finding 2).
    """
    project_id, run_id, scope_id = seed_corpus(conn)

    def _deny(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("socket creation attempted during fixture ingest")

    monkeypatch.setattr(socket, "socket", _deny)
    summary = run_ingest(conn, project_id, run_id, scope_id)
    monkeypatch.undo()
    assert summary["ingested"] == EXPECTED_INGESTED
    assert summary["fetch_failed"] == EXPECTED_FETCH_FAILED
    assert summary["parse_failed"] == EXPECTED_PARSE_FAILED


def test_recorder_script_not_imported_by_package() -> None:
    """The full-text recorder stays outside the package import graph (007 precedent)."""
    src_dir = Path(__file__).parent.parent / "src" / "policy_atlas"
    for module in src_dir.rglob("*.py"):
        assert "record_fulltext_fixtures" not in module.read_text()


def test_ingest_module_has_no_http_client() -> None:
    """ingest_full_text.py imports no HTTP client or socket machinery."""
    module = (
        Path(__file__).parent.parent / "src" / "policy_atlas" / "ingest_full_text.py"
    ).read_text()
    forbidden = re.compile(
        r"^\s*(import|from)\s+(urllib|requests|httpx|aiohttp|http\.client|socket)\b",
        re.MULTILINE,
    )
    assert not forbidden.search(module)


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

CorpusFixture = tuple[uuid.UUID, uuid.UUID, uuid.UUID, dict[str, Any]]


def _norm_ws(text: str) -> str:
    """Collapse whitespace so PDF line-wraps don't break a literal-sentence check."""
    return " ".join(text.split())


@pytest.fixture(scope="module")
def ingested_corpus(engine: Engine) -> Generator[CorpusFixture, None, None]:
    """One committed acquire+screen+ingest run, shared read-only across this module.

    Real PDF/HTML parses cost ~15-20s; every read-only test below rides this single
    run instead of paying for its own (mutating tests use the rollback-safe function-
    scoped ``conn`` fixture and seed their own corpus).
    """
    with engine.connect() as c:
        project_id, run_id, scope_id = seed_corpus(c)
        summary = run_ingest(c, project_id, run_id, scope_id)
        c.commit()
    yield project_id, run_id, scope_id, summary
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


def test_outcome_distribution(ingested_corpus: CorpusFixture) -> None:
    _, _, _, summary = ingested_corpus
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
        ("sanitizedorgdf2d12-42aba8211480495ee10e4ab8faa88047", "fetch_failed",
         "paywall", None),
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
    project_id, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, project_id, record_id)
    assert row.full_text_status == status
    assert row.full_text_error == error
    if fetched_from is not None:
        assert row.ft_source_locator == fetched_from
        assert row.ft_metadata["fetched_from"] == fetched_from


def test_pdf_structure_chunks(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _ = ingested_corpus
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
    project_id, _, _, _ = ingested_corpus
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
    project_id, _, _, _ = ingested_corpus
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


def test_success_metadata_complete(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, _, _, _ = ingested_corpus
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


def test_envelope_immutability(conn: Connection) -> None:
    project_id, run_id, scope_id = seed_corpus(conn)

    def _envelopes() -> dict[uuid.UUID, dict[str, Any]]:
        return {
            r.source_snapshot_id: dict(r._mapping)
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
        }

    before = _envelopes()
    run_ingest(conn, project_id, run_id, scope_id)
    after = _envelopes()
    assert before == after
    for snap_id, row in after.items():
        assert row["text_basis"] == "abstract_only"
        chunk_row = conn.execute(
            select(chunk_table.c.content).where(chunk_table.c.source_snapshot_id == snap_id)
        ).one()
        assert row["content_hash"] == content_hash(chunk_row.content)


def test_governance_chain(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    project_id, run_id, _, _ = ingested_corpus
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
        resources.files("policy_atlas").joinpath("data", "fulltext_manifest.json").read_text()
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

    fulltext_dir = Path(__file__).parent.parent / "src" / "policy_atlas" / "data" / "fulltext"
    for url, outcome in manifest["outcomes"].items():
        assert url.startswith(("https://example.org/", "https://doi.org/10.99999/")), url
        if outcome["outcome"] == "ok":
            filename = outcome["file"]
            assert filename in manifest["documents"]
            assert (fulltext_dir / filename).exists()


def test_migration_roundtrip_and_checks(conn: Connection) -> None:
    assert len(metadata.tables) == 16
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
    project_id, run_id, scope_id = seed_corpus(conn)
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
    project_id, run_id, scope_id = seed_corpus(conn)

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


def test_idempotency_and_retry(conn: Connection) -> None:
    project_id, run_id, scope_id = seed_corpus(conn)
    first = run_ingest(conn, project_id, run_id, scope_id)
    assert first["ingested"] == EXPECTED_INGESTED
    n_ft_before = _full_text_snapshot_count(conn, project_id)

    run_id_2 = seed_run(conn, project_id)
    second = run_ingest(conn, project_id, run_id_2, scope_id)

    assert second["already_ingested"] == EXPECTED_INGESTED
    assert second["ingested"] == 0
    assert second["fetch_failed"] == EXPECTED_FETCH_FAILED
    assert second["parse_failed"] == EXPECTED_PARSE_FAILED
    assert (
        second["eligible"]
        == second["ingested"] + second["already_ingested"]
        + second["fetch_failed"] + second["parse_failed"]
    )
    n_ft_after = _full_text_snapshot_count(conn, project_id)
    assert n_ft_after == n_ft_before  # no new full-text snapshots on retry


def test_harness_roundtrip_and_events(conn: Connection) -> None:
    project_id, run_id, scope_id = seed_corpus(conn)
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
    assert completed[0]["eligible"] == EXPECTED_ELIGIBLE
    assert completed[0]["ingested"] == EXPECTED_INGESTED
    assert completed[0]["fetch_failed"] == EXPECTED_FETCH_FAILED
    assert completed[0]["parse_failed"] == EXPECTED_PARSE_FAILED
    assert completed[0]["by_reason"] == EXPECTED_BY_REASON

    started = [e for e in run_events if e["event_type"] == "component.started"]
    assert len(started) == 1

    assert _full_text_snapshot_count(conn, project_id) >= 1


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
    project_id, run_id, scope_id = seed_corpus(conn)
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
