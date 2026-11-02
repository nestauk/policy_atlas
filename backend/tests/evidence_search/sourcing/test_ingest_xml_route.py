"""Tests for the Europe PMC XML route in full-text ingest (task 056, N10 and S7).

A document whose metadata carries a PubMed Central id is tried on Europe PMC's
JATS XML first, then on today's PDF-first URL cascade. Fixture replay (no
Europe PMC hook) never contacts Europe PMC.
"""

import socket
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection
from structlog.testing import capture_logs

from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.core.schema import source_snapshot, task_source_snapshot
from policy_atlas.evidence_search.sourcing.fetch_live import LiveDocumentFetcher
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    EUROPE_PMC_HOST,
    FixtureFetcher,
    IngestFullTextContext,
    europe_pmc_candidate,
    ingest_full_text_sources,
)
from policy_atlas.evidence_search.sourcing.parse_jats import (
    JATS_PARSE_PROFILE,
    JATS_SEGMENTATION_POLICY,
)
from tests.evidence_search.sourcing.test_ingest_full_text import _seed_relevant_acquired
from tests.helpers import seed_scope, seed_task_and_run

DATA_DIR = Path(__file__).parents[2] / "data"
JATS_XML = (DATA_DIR / "jats" / "PMC5264339.xml").read_bytes()
PDF_BYTES = (DATA_DIR / "fulltext" / "frontiers_getting_ready_2018.pdf").read_bytes()
# Fixture-manifest URLs that replay a real PDF and a real HTML page.
FIXTURE_PDF_URL = "https://example.org/42ad8806fb1f"
FIXTURE_HTML_URL = "https://doi.org/10.99999/cacf1b906a"
XML_URL = f"https://{EUROPE_PMC_HOST}/europepmc/webservices/rest/PMC5264339/fullTextXML"
# Parses as XML but has no body text, so ``parse_jats`` returns ``empty``.
EMPTY_JATS = (
    b"<?xml version='1.0'?><article><front><article-meta><title-group>"
    b"<article-title>Only a title</article-title></title-group></article-meta>"
    b"</front></article>"
)
PUBLIC_IP = "93.184.216.34"


def _meta(
    *, pmcid: str | None, pdf_url: str | None = None, landing: str | None = None
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    if pdf_url is not None:
        fields["best_oa_location"] = {"pdf_url": pdf_url}
    if landing is not None:
        fields["primary_location"] = {"landing_page_url": landing}
    if pmcid is not None:
        fields["ids"] = {"pmcid": pmcid}
    return {"backend": "openalex", "provider_fields": fields}


def _run(
    conn: Connection, task_id: uuid.UUID, run_id: uuid.UUID, scope_id: uuid.UUID, fetcher: Any
) -> dict[str, Any]:
    return ingest_full_text_sources(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=IngestFullTextContext(scope_id=scope_id, intent="test", context={}),
        fetcher=fetcher,
        max_workers=2,
        parse_timeout=300.0,
    )


def _setup(
    conn: Connection, *metas: dict[str, Any]
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    task_id, run_id = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    tss_ids = [_seed_relevant_acquired(conn, task_id, run_id, scope_id, m) for m in metas]
    return task_id, run_id, scope_id, tss_ids


def _full_text(conn: Connection, tss_id: uuid.UUID) -> tuple[Any, Sequence[Any]]:
    ft_id = conn.execute(
        select(task_source_snapshot.c.full_text_snapshot_id).where(
            task_source_snapshot.c.task_source_snapshot_id == tss_id
        )
    ).scalar_one()
    snap = conn.execute(
        select(source_snapshot.c.source_locator, source_snapshot.c.metadata).where(
            source_snapshot.c.source_snapshot_id == ft_id
        )
    ).one()
    chunks = conn.execute(
        select(chunk_table.c.content, chunk_table.c.locator)
        .where(chunk_table.c.source_snapshot_id == ft_id)
        .order_by(chunk_table.c.sequence)
    ).fetchall()
    return snap, chunks


class _XmlFixtureFetcher(FixtureFetcher):
    """Fixture replay plus a scripted Europe PMC hook (zero egress)."""

    def __init__(self, xml_by_pmcid: dict[str, bytes | None]) -> None:
        super().__init__()
        self.xml_by_pmcid = xml_by_pmcid
        self.xml_calls: list[str] = []
        self.url_calls: list[str] = []

    def fetch(self, url: str) -> Any:
        self.url_calls.append(url)
        return super().fetch(url)

    def fetch_europe_pmc_xml(self, pmcid: str) -> bytes | None:
        self.xml_calls.append(pmcid)
        return self.xml_by_pmcid.get(pmcid)


def test_europe_pmc_candidate_reads_openalex_pmcid_link() -> None:
    assert europe_pmc_candidate(
        _meta(pmcid="https://www.ncbi.nlm.nih.gov/pmc/articles/5264339")
    ) == ("PMC5264339", XML_URL)
    assert europe_pmc_candidate(_meta(pmcid=None)) is None
    assert europe_pmc_candidate(_meta(pmcid="not an id")) is None
    assert europe_pmc_candidate({"backend": "overton"}) is None


def test_pmcid_document_is_served_from_europe_pmc_xml_through_live_fetcher(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end through the live fetcher with a fake transport: the XML wins
    over the PDF, only the id is sent, and the chunks carry section headings."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == EUROPE_PMC_HOST:
            return httpx.Response(
                200, headers={"content-type": "application/xml"}, content=JATS_XML
            )
        return httpx.Response(200, headers={"content-type": "application/pdf"}, content=PDF_BYTES)

    fetcher = LiveDocumentFetcher(
        resolver=lambda host, port: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, port))
        ],
        sleep=lambda _s: None,
        transport=httpx.MockTransport(handler),
    )
    task_id, run_id, scope_id, (tss_id,) = _setup(
        conn,
        _meta(
            pmcid="https://www.ncbi.nlm.nih.gov/pmc/articles/5264339",
            pdf_url="https://pub.example/a.pdf",
        ),
    )
    summary = _run(conn, task_id, run_id, scope_id, fetcher)

    assert summary["ingested"] == 1
    assert summary["by_route"] == {"europe_pmc_xml": 1}
    assert [str(r.url) for r in requests] == [XML_URL]  # no query string, PDF never fetched
    assert requests[0].content == b""
    snap, chunks = _full_text(conn, tss_id)
    assert snap.source_locator == XML_URL
    assert snap.metadata["source_kind"] == "europe_pmc_xml"
    assert snap.metadata["parse_profile"] == JATS_PARSE_PROFILE
    assert snap.metadata["segmentation_policy"] == JATS_SEGMENTATION_POLICY
    assert snap.metadata["content_type"] == "application/xml"
    assert len(chunks) > 5
    assert all(c.locator["heading_path"] for c in chunks)
    assert all(c.locator["pages"] == [1] for c in chunks)
    headings = {h for c in chunks for h in c.locator["heading_path"]}
    assert any(h.lower().startswith("method") for h in headings)
    assert any(c.content.startswith("|") for c in chunks)  # a table chunk


@pytest.mark.parametrize(
    ("xml", "attempted_xml_reason"),
    [(None, "not_found"), (EMPTY_JATS, "empty"), (b"<article><unclosed>", "corrupt")],
    ids=["no-xml", "empty-xml", "corrupt-xml"],
)
def test_xml_missing_or_unparseable_falls_back_to_pdf(
    conn: Connection, xml: bytes | None, attempted_xml_reason: str
) -> None:
    fetcher = _XmlFixtureFetcher({"PMC5264339": xml})
    task_id, run_id, scope_id, (tss_id,) = _setup(
        conn, _meta(pmcid="PMC5264339", pdf_url=FIXTURE_PDF_URL)
    )
    with capture_logs() as logs:
        summary = _run(conn, task_id, run_id, scope_id, fetcher)

    xml_events = [
        e
        for e in logs
        if e["event"] in {"fulltext.fetch_attempt", "fulltext.parse_failed"}
        and e.get("url") == XML_URL
        and (e.get("outcome") or e.get("reason")) != "ok"
    ]
    assert [e.get("outcome") or e.get("reason") for e in xml_events] == [attempted_xml_reason]
    assert fetcher.xml_calls == ["PMC5264339"]
    assert fetcher.url_calls == [FIXTURE_PDF_URL]
    assert summary["ingested"] == 1
    assert summary["parse_failed"] == summary["fetch_failed"] == 0
    assert summary["by_route"] == {"pdf": 1}
    snap, chunks = _full_text(conn, tss_id)
    assert snap.source_locator == FIXTURE_PDF_URL
    assert snap.metadata["source_kind"] == "pdf"
    assert snap.metadata["parse_profile"] == "pymupdf4llm_v1"
    assert chunks


def test_unparseable_xml_with_no_other_candidate_is_parse_failed(conn: Connection) -> None:
    fetcher = _XmlFixtureFetcher({"PMC5264339": EMPTY_JATS})
    task_id, run_id, scope_id, (tss_id,) = _setup(conn, _meta(pmcid="PMC5264339"))
    summary = _run(conn, task_id, run_id, scope_id, fetcher)

    assert summary["parse_failed"] == 1
    assert summary["by_reason"] == {"empty": 1}
    assert summary["by_route"] == {}
    status, error = conn.execute(
        select(
            task_source_snapshot.c.full_text_status, task_source_snapshot.c.full_text_error
        ).where(task_source_snapshot.c.task_source_snapshot_id == tss_id)
    ).one()
    assert (status, error) == ("parse_failed", "empty")


def test_document_without_pmcid_never_calls_europe_pmc(conn: Connection) -> None:
    fetcher = _XmlFixtureFetcher({"PMC5264339": JATS_XML})
    task_id, run_id, scope_id, _ = _setup(conn, _meta(pmcid=None, pdf_url=FIXTURE_PDF_URL))
    summary = _run(conn, task_id, run_id, scope_id, fetcher)

    assert fetcher.xml_calls == []
    assert fetcher.url_calls == [FIXTURE_PDF_URL]
    assert summary["by_route"] == {"pdf": 1}


def test_fixture_replay_without_the_hook_never_tries_europe_pmc(conn: Connection) -> None:
    """Plain fixture replay has no Europe PMC hook, so a pmcid changes nothing
    (the zero-egress fixture mode stays zero-egress)."""
    task_id, run_id, scope_id, (tss_id,) = _setup(
        conn, _meta(pmcid="PMC5264339", pdf_url=FIXTURE_PDF_URL)
    )
    summary = _run(conn, task_id, run_id, scope_id, FixtureFetcher())

    assert summary["by_route"] == {"pdf": 1}
    snap, _ = _full_text(conn, tss_id)
    assert snap.source_locator == FIXTURE_PDF_URL


def test_by_route_counts_each_serving_route(conn: Connection) -> None:
    fetcher = _XmlFixtureFetcher({"PMC5264339": JATS_XML})
    task_id, run_id, scope_id, tss_ids = _setup(
        conn,
        _meta(pmcid="PMC5264339", pdf_url=FIXTURE_PDF_URL),
        _meta(pmcid=None, pdf_url=FIXTURE_PDF_URL),
        _meta(pmcid=None, landing=FIXTURE_HTML_URL),
    )
    summary = _run(conn, task_id, run_id, scope_id, fetcher)

    assert summary["ingested"] == 3
    assert summary["by_route"] == {"europe_pmc_xml": 1, "pdf": 1, "html": 1}
    kinds = [_full_text(conn, tss_id)[0].metadata["source_kind"] for tss_id in tss_ids]
    assert sorted(kinds) == ["europe_pmc_xml", "html", "pdf"]
