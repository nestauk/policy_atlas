"""Full-text ingestion over the committed fixture corpus, read by many tests (task 008).

One acquire + screen + ingest run is committed once for the module
(``ingested_corpus``) and the read-only contract tests below check its outcome.
Split out of ``test_ingest_full_text.py`` in task 057: the parsed snapshots this
run commits sit in the shared document store until the module ends, and a test in
the same module that must actually parse the same bytes would find them there.
"""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import event_log, source_snapshot, task_source_snapshot
from tests.evidence_search.sourcing.test_ingest_full_text import (
    EXPECTED_BY_REASON,
    EXPECTED_ELIGIBLE,
    EXPECTED_FETCH_FAILED,
    EXPECTED_INGESTED,
    EXPECTED_PARSE_FAILED,
    CorpusFixture,
    local_queue,
    run_ingest,
    seed_corpus,
)
from tests.helpers import delete_task_data

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
# Task 057 (N9): the shared full-text snapshot's metadata holds exactly these keys;
# the run, the fetch address and the envelope live on the link row.
_FT_METADATA_KEYS = {"parse_profile", "segmentation_policy", "content_type", "source_kind"}


def _norm_ws(text: str) -> str:
    """Collapse whitespace so PDF line-wraps don't break a literal-sentence check."""
    return " ".join(text.split())


def _envelope_snapshots(conn: Connection, task_id: uuid.UUID) -> list[dict[str, Any]]:
    """Envelope source_snapshot rows for a task's links, as plain dicts."""
    return [
        dict(r._mapping)
        for r in conn.execute(
            select(source_snapshot)
            .select_from(
                task_source_snapshot.join(
                    source_snapshot,
                    task_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(task_source_snapshot.c.task_id == task_id)
        ).fetchall()
    ]


@pytest.fixture(scope="module")
def ingested_corpus(engine: Engine) -> Generator[CorpusFixture, None, None]:
    """One committed acquire+screen+ingest run, shared read-only across this module.

    Real PDF/HTML parses cost ~15-20s; every read-only test below rides this single
    run instead of paying for its own (mutating tests use the rollback-safe function-
    scoped ``conn`` fixture and seed their own corpus).

    Task 057: the documents run through the in-process queue client on one
    worker thread, which writes through its own committed connections, so the
    seeded corpus is committed first. The worker-count comparison (1 and 4) lives
    in ``test_ingest_stage.py``; this module is its own so that the parsed
    snapshots it commits (the document store is shared across tasks) never meet
    the rolled-back tests in ``test_ingest_full_text.py``, which must parse.
    """
    with engine.connect() as c:
        task_id, run_id, scope_id = seed_corpus(c)
        envelope_snapshots = _envelope_snapshots(c, task_id)
        c.commit()
        summary = run_ingest(
            c, task_id, run_id, scope_id,
            queue=local_queue(engine, workers=1), connect=engine.begin,
        )
        c.commit()
    yield task_id, run_id, scope_id, summary, envelope_snapshots
    with engine.connect() as c:
        delete_task_data(c, task_id)
        c.commit()


def _link_rows(conn: Connection, task_id: uuid.UUID) -> list[Any]:
    """All links for a task with their envelope + full-text snapshot fields."""
    ft = source_snapshot.alias("ft")
    return list(conn.execute(
        select(
            task_source_snapshot.c.run_id,
            task_source_snapshot.c.source_snapshot_id,
            task_source_snapshot.c.full_text_snapshot_id,
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
            source_snapshot.c.metadata.label("envelope_metadata"),
            ft.c.source_locator.label("ft_source_locator"),
            ft.c.metadata.label("ft_metadata"),
            task_source_snapshot.c.fetched_from,
            task_source_snapshot.c.ingested_by_run_id,
        )
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            ).outerjoin(
                ft,
                task_source_snapshot.c.full_text_snapshot_id == ft.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
    ).fetchall())


def _by_backend_record_id(conn: Connection, task_id: uuid.UUID, record_id: str) -> Any:
    """The single link row whose envelope metadata carries this backend_record_id."""
    matches = [
        r for r in _link_rows(conn, task_id)
        if r.envelope_metadata.get("backend_record_id") == record_id
    ]
    assert len(matches) == 1, f"expected exactly one link for {record_id!r}, got {len(matches)}"
    return matches[0]


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
    task_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, task_id, record_id)
    assert row.full_text_status == status
    assert row.full_text_error == error
    if fetched_from is not None:
        assert row.ft_source_locator == fetched_from
        assert row.fetched_from == fetched_from


def test_pdf_structure_chunks(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    task_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, task_id, "https://example.org/5f2286252e57")
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
            assert c.segmentation_policy == "pymupdf4llm_struct_v2"
        assert any(c.locator["heading_path"] for c in chunks)
        assert row.ft_metadata["segmentation_policy"] == "pymupdf4llm_struct_v2"
        assert row.ft_metadata["parse_profile"] == "pymupdf4llm_v2"

        norm_sentence = _norm_ws(FRONTIERS_ABSTRACT_SENTENCE)
        assert any(norm_sentence in _norm_ws(c.content) for c in chunks)

        wb_row = _by_backend_record_id(
            conn, task_id, "sanitizedorgf49937-f18086f777c8acbad55bb7f2230c557d"
        )
        wb_chunks = conn.execute(
            select(chunk_table.c.content)
            .where(chunk_table.c.source_snapshot_id == wb_row.full_text_snapshot_id)
        ).fetchall()
        assert any(c.content.startswith("|") for c in wb_chunks)  # table kept whole


def test_no_truncation_long_report(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    task_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(
            conn, task_id, "sanitizedorgf49937-f18086f777c8acbad55bb7f2230c557d"
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
    task_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        row = _by_backend_record_id(conn, task_id, "https://example.org/325a3b216a30")
        assert row.full_text_status == "ingested"
        chunks = conn.execute(
            select(
                chunk_table.c.content, chunk_table.c.locator, chunk_table.c.segmentation_policy,
            )
            .where(chunk_table.c.source_snapshot_id == row.full_text_snapshot_id)
            .order_by(chunk_table.c.sequence)
        ).fetchall()
    assert chunks
    assert row.ft_metadata["parse_profile"] == "trafilatura_v2"
    for i, c in enumerate(chunks, start=1):
        assert c.content.strip()
        assert c.segmentation_policy == "trafilatura_para_v2"
        assert c.locator == {"paragraph": i}
    joined = " ".join(c.content for c in chunks)
    assert NESTA_FOOTER_BOILERPLATE not in joined
    assert NESTA_REPORT_SENTENCE in joined


def test_success_metadata_complete(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    task_id, _, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        links = conn.execute(
            select(
                task_source_snapshot.c.full_text_snapshot_id,
                task_source_snapshot.c.fetched_from,
            )
            .where(task_source_snapshot.c.task_id == task_id)
            .where(task_source_snapshot.c.full_text_status == "ingested")
        ).fetchall()
        assert len(links) == EXPECTED_INGESTED
        for link in links:
            snap = conn.execute(
                select(
                    source_snapshot.c.text_basis, source_snapshot.c.content_hash,
                    source_snapshot.c.source_locator, source_snapshot.c.metadata,
                    source_snapshot.c.body_hash, source_snapshot.c.parse_profile,
                    source_snapshot.c.segmentation_policy,
                )
                .where(source_snapshot.c.source_snapshot_id == link.full_text_snapshot_id)
            ).one()
            assert snap.text_basis == "full_text"
            assert set(snap.metadata) == _FT_METADATA_KEYS
            for key in _FT_METADATA_KEYS:
                assert snap.metadata[key] is not None
            # The store key is stamped as columns, matching the metadata.
            assert snap.body_hash is not None and len(snap.body_hash) == 64
            assert snap.parse_profile == snap.metadata["parse_profile"]
            assert snap.segmentation_policy == snap.metadata["segmentation_policy"]
            assert snap.source_locator == link.fetched_from
            chunk_rows = conn.execute(
                select(chunk_table.c.content)
                .where(chunk_table.c.source_snapshot_id == link.full_text_snapshot_id)
                .order_by(chunk_table.c.sequence)
            ).fetchall()
            assert snap.content_hash == content_hash("".join(c.content for c in chunk_rows))


def test_envelope_immutability(ingested_corpus: CorpusFixture, engine: Engine) -> None:
    task_id, _, _, _, before = ingested_corpus
    with engine.connect() as conn:
        after = _envelope_snapshots(conn, task_id)
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
    task_id, run_id, _, _, _ = ingested_corpus
    with engine.connect() as conn:
        ingested_rows = [
            r for r in _link_rows(conn, task_id) if r.full_text_status == "ingested"
        ]
        assert len(ingested_rows) == EXPECTED_INGESTED
        for row in ingested_rows:
            assert row.ingested_by_run_id == run_id
            n_search_events = conn.execute(
                select(sa.func.count()).select_from(event_log)
                .where(event_log.c.run_id == row.run_id)
                .where(event_log.c.event_type == "search.executed")
            ).scalar_one()
            assert n_search_events > 0
