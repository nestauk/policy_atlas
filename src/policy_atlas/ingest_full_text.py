"""Full-text ingestion component — fetch → parse → segment, post-screen Tier 0.

For every screened-in acquired source of a scope, resolve candidate URLs from the
provider fields task 007 retained, fetch through the ``DocumentFetcher`` seam
(v3.0: fixture replay of committed real, openly-licensed documents — zero runtime
egress), parse structure-aware (PDF via pymupdf4llm, HTML via trafilatura), segment
under named versioned policies, and attach the resulting immutable ``full_text``
snapshot to the corpus document via ``project_source_snapshot.full_text_snapshot_id``
(ADR 0003).

Never truncate: a stored ``full_text`` snapshot is the whole parsed document; the
fetch byte cap and the hard per-document parse timeout are guards that fail loudly
(``too_large`` / ``timeout``), never scissors (contract decision 6). A failed source
stays on the text in hand with a queryable, reason-coded ``full_text_status`` —
nothing is dropped, nothing is silent (decision 3).

Parse + segment run as a pure function in per-document worker processes that are
genuinely terminable; fetch stays in the parent and workers receive primitives only
(decision 8, adversarial findings 6 + 7). DB writes happen in the parent in
eligible-set order, so the persisted outcome is independent of worker count.
"""

import functools
import importlib.resources
import json
import re
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from multiprocessing import get_context
from typing import Any, Protocol

import pymupdf
import pymupdf4llm  # type: ignore[import-untyped]
import structlog
import trafilatura
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.grounding import content_hash
from policy_atlas.schema import (
    chunk as chunk_table,
)
from policy_atlas.schema import (
    project_source_snapshot,
    source_screening_result,
    source_snapshot,
)

log = structlog.get_logger()

FETCH_BYTE_CAP = 100 * 1024 * 1024  # generous guard, never a scissor (decision 6)
PARSE_TIMEOUT_SECONDS = 60.0  # hard per-document parse timeout; worker is terminated
THIN_TEXT_MIN_CHARS = 200  # below this, parsed text is a failure, never "ok" (decision 7)
DEFAULT_MAX_WORKERS = 4

PDF_PARSE_PROFILE = "pymupdf4llm_v1"
HTML_PARSE_PROFILE = "trafilatura_v1"
PLAIN_PARSE_PROFILE = "plain_v1"
PDF_SEGMENTATION_POLICY = "pymupdf4llm_struct_v1"
HTML_SEGMENTATION_POLICY = "trafilatura_para_v1"
PLAIN_SEGMENTATION_POLICY = "plain_para_v1"

# Closed failure-reason vocabulary (contract decision 3). Presence on failure is
# CHECK-enforced (ck_pss_full_text_error_presence); the values are code-enforced so
# the list can grow at the live seam without a migration.
FAILURE_REASONS = (
    "no_url", "paywall", "not_found", "too_large", "timeout",
    "corrupt", "no_text_layer", "thin_text", "empty",
)

_HTTP_STATUS_REASONS = {401: "paywall", 403: "paywall", 404: "not_found", 410: "not_found"}


@dataclass
class FetchResult:
    """Outcome of fetching one URL through a ``DocumentFetcher``.

    Attributes:
        status: ``"ok"`` or ``"error"``.
        content_type: ``"application/pdf"`` | ``"text/html"`` | ``"text/plain"``
            when ok, else None.
        body: Document bytes when ok, else None.
        error: Failure reason from the closed vocabulary (decision 3) when
            status is ``"error"``.
    """

    status: str
    content_type: str | None = None
    body: bytes | None = None
    error: str | None = None


class DocumentFetcher(Protocol):
    """The fetch seam: resolves one URL to document bytes or an honest failure.

    Attributes:
        mode: ``"fixture"`` or ``"live"``.
    """

    mode: str

    def fetch(self, url: str) -> FetchResult:
        """Fetch one URL. Never raises for per-document outcomes."""
        ...


@functools.cache  # fixture files are immutable for the process lifetime (acquire precedent)
def _load_manifest() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(
        importlib.resources.files("policy_atlas")
        .joinpath("data", "fulltext_manifest.json")
        .read_text()
    )
    return data


class FixtureFetcher:
    """Replays committed real documents by URL from the manifest. Zero egress.

    URLs map to outcomes in ``fulltext_manifest.json``: ``ok`` entries read the
    committed document bytes; ``http_error``/``oversize`` entries replay the
    recorded failure. An unmapped URL is a dead link (``not_found``). The
    manifest loads lazily on first fetch, so constructing the default fetcher
    (every ``run_harness`` call) costs nothing for non-ingest components.
    """

    mode = "fixture"

    def fetch(self, url: str) -> FetchResult:
        """Return the manifest-recorded outcome for ``url``."""
        entry = _load_manifest()["outcomes"].get(url)
        if entry is None:
            return FetchResult(status="error", error="not_found")
        outcome = entry["outcome"]
        if outcome == "ok":
            body = (
                importlib.resources.files("policy_atlas")
                .joinpath("data", "fulltext", entry["file"])
                .read_bytes()
            )
            return FetchResult(status="ok", content_type=entry["content_type"], body=body)
        if outcome == "oversize":
            return FetchResult(status="error", error="too_large")
        # http_error: map the recorded status to the reason vocabulary the same
        # way the live fetcher will (401/403 → paywall, 404/410 → not_found).
        status_code = int(entry["http_status"])
        return FetchResult(status="error", error=_HTTP_STATUS_REASONS.get(status_code, "not_found"))


@dataclass
class IngestFullTextContext:
    """Scope-level input to a full-text ingestion run.

    Attributes:
        scope_id: The evidence scope whose screened-in acquired sources are ingested.
        intent: The scope's research intent (unused by v3.0 ingestion; carried for
            signature parity with the other scope components).
        context: The scope's context JSONB.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


# --- URL resolution (decision 4) ---


def _normalize_url(value: Any) -> str | None:
    """Accept only http(s) URL strings; sentinels like ``"n/a"`` are absent."""
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return None


def candidate_urls(metadata: dict[str, Any]) -> list[str]:
    """Resolve the ordered candidate-URL cascade from a snapshot's provider fields.

    OpenAlex: ``best_oa_location.pdf_url`` → ``primary_location.pdf_url`` →
    ``open_access.oa_url`` → ``primary_location.landing_page_url``. Overton:
    ``pdf_url`` → ``document_url``. Deduplicated preserving order; non-URL
    sentinels (e.g. Overton's ``"n/a"``) are treated as absent.

    Args:
        metadata: The envelope snapshot's metadata JSONB.

    Returns:
        Ordered, deduplicated candidate URLs (possibly empty).
    """
    fields = metadata.get("provider_fields") or {}
    backend = metadata.get("backend")
    raw: list[Any]
    if backend == "openalex":
        best_oa = fields.get("best_oa_location") or {}
        primary = fields.get("primary_location") or {}
        open_access = fields.get("open_access") or {}
        raw = [
            best_oa.get("pdf_url"),
            primary.get("pdf_url"),
            open_access.get("oa_url"),
            primary.get("landing_page_url"),
        ]
    elif backend == "overton":
        raw = [fields.get("pdf_url"), fields.get("document_url")]
    else:
        raw = []
    urls: list[str] = []
    for value in raw:
        url = _normalize_url(value)
        if url is not None and url not in urls:
            urls.append(url)
    return urls


# --- Parse + segment (pure; runs in worker processes; primitives in/out) ---


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _segment_markdown_pages(pages: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Segment pymupdf4llm markdown into heading-bounded section + table chunks.

    Sections may span pages; each chunk's locator carries its page number(s) and
    the heading path in force (decision 7 — the provenance v2 threw away).
    """
    chunks: list[dict[str, Any]] = []
    heading_stack: list[str] = []  # index = heading level - 1

    section_parts: list[str] = []  # completed paragraphs in the current section
    section_pages: set[int] = set()
    paragraph_lines: list[str] = []
    table_lines: list[str] = []
    table_pages: set[int] = set()

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        if paragraph_lines:
            section_parts.append("\n".join(paragraph_lines))
            paragraph_lines = []

    def flush_section() -> None:
        nonlocal section_parts, section_pages
        flush_paragraph()
        text = "\n\n".join(section_parts).strip()
        if text:
            chunks.append({
                "content": text,
                "locator": {
                    "pages": sorted(section_pages),
                    "heading_path": [h for h in heading_stack if h],
                },
            })
        section_parts = []
        section_pages = set()

    def flush_table() -> None:
        nonlocal table_lines, table_pages
        if table_lines:
            chunks.append({
                "content": "\n".join(table_lines),
                "locator": {
                    "pages": sorted(table_pages),
                    "heading_path": [h for h in heading_stack if h],
                },
            })
            table_lines = []
            table_pages = set()

    for page_no, text in pages:
        for line in text.splitlines():
            stripped = line.strip()
            heading = _HEADING_RE.match(stripped)
            if heading is not None:
                flush_table()
                flush_section()
                level = len(heading.group(1))
                del heading_stack[level - 1:]
                heading_stack.extend([""] * (level - 1 - len(heading_stack)))
                heading_stack.append(heading.group(2))
                continue
            if stripped.startswith("|"):
                flush_paragraph()
                table_lines.append(stripped)
                table_pages.add(page_no)
                continue
            flush_table()
            if not stripped:
                flush_paragraph()
                continue
            paragraph_lines.append(stripped)
            section_pages.add(page_no)
    flush_table()
    flush_section()
    return chunks


def _parse_pdf(body: bytes) -> dict[str, Any]:
    try:
        doc = pymupdf.open(stream=body, filetype="pdf")  # type: ignore[no-untyped-call]
        page_dicts = pymupdf4llm.to_markdown(doc, page_chunks=True)
    except Exception as exc:
        return {"status": "error", "reason": "corrupt", "detail": str(exc)}
    pages = [
        (int(pg.get("metadata", {}).get("page", i + 1)), str(pg.get("text", "")))
        for i, pg in enumerate(page_dicts)
    ]
    if not any(re.search(r"[0-9A-Za-z]", text) for _, text in pages):
        return {"status": "error", "reason": "no_text_layer"}
    chunks = _segment_markdown_pages(pages)
    return {
        "status": "ok",
        "chunks": chunks,
        "parse_profile": PDF_PARSE_PROFILE,
        "segmentation_policy": PDF_SEGMENTATION_POLICY,
    }


def _decode(body: bytes) -> str:
    # errors="replace" keeps unknown bytes visible as U+FFFD instead of the
    # silent-ignore character loss v2 shipped (integration review).
    return body.decode("utf-8", errors="replace")


def _parse_html(body: bytes) -> dict[str, Any]:
    extracted = trafilatura.extract(_decode(body), include_comments=False, include_tables=True)
    if not extracted or not extracted.strip():
        return {"status": "error", "reason": "empty"}
    chunks = [
        {"content": para, "locator": {"paragraph": i}}
        for i, para in enumerate((p.strip() for p in extracted.splitlines()), start=1)
        if para
    ]
    return {
        "status": "ok",
        "chunks": chunks,
        "parse_profile": HTML_PARSE_PROFILE,
        "segmentation_policy": HTML_SEGMENTATION_POLICY,
    }


def _parse_plain(body: bytes) -> dict[str, Any]:
    text = _decode(body)
    if not text.strip():
        return {"status": "error", "reason": "empty"}
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = [
        {"content": para, "locator": {"paragraph": i}}
        for i, para in enumerate(paragraphs, start=1)
    ]
    return {
        "status": "ok",
        "chunks": chunks,
        "parse_profile": PLAIN_PARSE_PROFILE,
        "segmentation_policy": PLAIN_SEGMENTATION_POLICY,
    }


def parse_and_segment(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Parse document bytes and segment them under the named policy for their type.

    Pure function over primitives — no DB, no network, no shared state — so it can
    run in a spawned worker process (decision 8). Never raises for per-document
    outcomes.

    Args:
        body: Raw document bytes.
        content_type: ``"application/pdf"`` | ``"text/html"`` | ``"text/plain"``.
        thin_min: Minimum total parsed characters; below it → ``thin_text``.

    Returns:
        ``{"status": "ok", "chunks": [...], "parse_profile": ..., "segmentation_policy": ...}``
        or ``{"status": "error", "reason": <closed vocabulary>}``.
    """
    base_type = content_type.split(";")[0].strip().lower()
    if base_type == "application/pdf":
        result = _parse_pdf(body)
    elif base_type == "text/html":
        result = _parse_html(body)
    else:
        result = _parse_plain(body)
    if result["status"] != "ok":
        return result
    total_chars = sum(len(c["content"]) for c in result["chunks"])
    if total_chars == 0:
        reason = "no_text_layer" if base_type == "application/pdf" else "empty"
        return {"status": "error", "reason": reason}
    if total_chars < thin_min:
        return {"status": "error", "reason": "thin_text"}
    return result


def _worker_entry(
    send_conn: Any,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]],
    body: bytes,
    content_type: str,
    thin_min: int,
) -> None:
    """Worker-process entrypoint: parse, send the result, exit. Top-level for spawn."""
    try:
        result = parse_fn(body, content_type, thin_min)
    except Exception as exc:  # defensive: an unexpected parser crash is a corrupt parse
        result = {"status": "error", "reason": "corrupt", "detail": str(exc)}
    send_conn.send(result)
    send_conn.close()


def _run_parse_jobs(
    jobs: list[tuple[int, bytes, str]],
    *,
    max_workers: int,
    parse_timeout: float,
    thin_min: int,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """Run parse jobs over a bounded pool of per-document worker processes.

    Each job runs in its own spawned ``multiprocessing.Process`` so a timeout can
    genuinely ``terminate()`` it (``ProcessPoolExecutor.cancel()`` cannot kill a
    running task — adversarial finding 6). Results are drained in submission order
    before joining, so a child blocked sending a large payload is never misread as
    a timeout (finding 7); the reorder buffer is the ≤ ``max_workers`` live pipes.
    Workers receive primitives only (finding 7 — spawn requires picklable args).

    Args:
        jobs: ``(index, body, content_type)`` triples.
        max_workers: Live-process bound.
        parse_timeout: Per-document seconds, measured from that worker's start.
        thin_min: Passed through to ``parse_fn``.
        parse_fn: Top-level parse callable (test seam for the timeout property —
            spawned children import it by reference, so it must be picklable).

    Returns:
        index → parse result (ok / error / ``timeout``).
    """
    ctx = get_context("spawn")  # deterministic cross-platform; fork is unsafe with threads
    results: dict[int, dict[str, Any]] = {}
    pending = deque(jobs)
    live: deque[tuple[int, Any, Any, float]] = deque()

    while pending or live:
        while pending and len(live) < max_workers:
            idx, body, content_type = pending.popleft()
            recv_conn, send_conn = ctx.Pipe(duplex=False)
            proc = ctx.Process(
                target=_worker_entry,
                args=(send_conn, parse_fn, body, content_type, thin_min),
            )
            proc.start()
            send_conn.close()  # parent keeps only the receive end
            live.append((idx, proc, recv_conn, time.monotonic()))

        idx, proc, recv_conn, started = live.popleft()
        remaining = parse_timeout - (time.monotonic() - started)
        if remaining > 0 and recv_conn.poll(remaining):
            try:
                result = recv_conn.recv()
            except EOFError:  # worker died before sending (e.g. OOM-killed)
                result = {"status": "error", "reason": "corrupt", "detail": "worker died"}
            proc.join()
        else:
            proc.terminate()
            proc.join()
            result = {"status": "error", "reason": "timeout"}
        recv_conn.close()
        results[idx] = result
    return results


# --- Component ---


@dataclass
class _DocState:
    """Parent-side per-document cascade state."""

    pss_id: uuid.UUID
    envelope_snapshot_id: uuid.UUID
    urls: list[str]
    next_url: int = 0
    attempts: list[str] = field(default_factory=list)
    resolution: str | None = None  # "ingested" | "fetch_failed" | "parse_failed"
    reason: str | None = None
    parsed: dict[str, Any] | None = None
    fetched_from: str | None = None
    content_type: str | None = None


def ingest_full_text_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: IngestFullTextContext,
    fetcher: DocumentFetcher,
    max_workers: int = DEFAULT_MAX_WORKERS,
    parse_timeout: float = PARSE_TIMEOUT_SECONDS,
    thin_min: int = THIN_TEXT_MIN_CHARS,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]] = parse_and_segment,
) -> dict[str, Any]:
    """Ingest full text for a scope's screened-in acquired sources.

    Resolves each eligible document's candidate URLs, walks the fetch cascade in
    the parent, fans parse + segment out over bounded per-document worker
    processes, and writes results in eligible-set order: success creates an
    immutable ``full_text`` snapshot (+ chunks) linked via
    ``full_text_snapshot_id``; failure records a reason-coded status on the link.
    Re-runs skip ``ingested`` links and retry failed ones (decision 10).

    Args:
        conn: Open database connection; all writes occur within its transaction.
        project_id: Owning project.
        run_id: The run recorded in the snapshot's governance breadcrumbs.
        context: Scope-level input naming the evidence scope.
        fetcher: The ``DocumentFetcher`` seam implementation.
        max_workers: Bound on live worker processes.
        parse_timeout: Hard per-document parse timeout in seconds.
        thin_min: Thin-text guard threshold in characters.
        parse_fn: Parse callable (test seam; must be a picklable top-level function).

    Returns:
        Counts dict: ``eligible``, ``ingested``, ``already_ingested``,
        ``fetch_failed``, ``parse_failed``, ``by_reason`` (invariant:
        ``eligible == ingested + already_ingested + fetch_failed + parse_failed``).
    """
    eligible_rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_status,
            source_snapshot.c.metadata,
        )
        .select_from(
            source_screening_result.join(
                project_source_snapshot,
                (source_screening_result.c.project_source_snapshot_id
                 == project_source_snapshot.c.project_source_snapshot_id)
                & (source_screening_result.c.project_id
                   == project_source_snapshot.c.project_id),
            ).join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(source_screening_result.c.evidence_scope_id == context.scope_id)
        .where(source_screening_result.c.status == "relevant")
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.origin == "acquired")
        .order_by(project_source_snapshot.c.project_source_snapshot_id)
    ).fetchall()

    already_ingested = sum(1 for row in eligible_rows if row.full_text_status == "ingested")
    docs: list[_DocState] = [
        _DocState(
            pss_id=row.project_source_snapshot_id,
            envelope_snapshot_id=row.source_snapshot_id,
            urls=candidate_urls(row.metadata),
        )
        for row in eligible_rows
        if row.full_text_status != "ingested"
    ]

    for doc in docs:
        if not doc.urls:
            # Durable state, distinguishable from not_attempted (adversarial finding 1)
            doc.resolution, doc.reason = "fetch_failed", "no_url"

    # Cascade rounds: fetch in the parent, parse in workers; a parse failure with
    # candidates remaining re-enters the next round on its next URL (decision 4).
    while True:
        jobs: list[tuple[int, bytes, str]] = []
        job_meta: dict[int, tuple[str, str]] = {}
        for i, doc in enumerate(docs):
            if doc.resolution is not None:
                continue
            body: bytes | None = None
            while doc.next_url < len(doc.urls):
                url = doc.urls[doc.next_url]
                doc.next_url += 1
                fetch_result = fetcher.fetch(url)
                if fetch_result.status == "ok":
                    fetched = fetch_result.body or b""
                    if len(fetched) > FETCH_BYTE_CAP:
                        doc.attempts.append(f"{url}: too_large")
                        doc.reason = "too_large"
                        log.info(
                            "fulltext.fetch_attempt", pss_id=str(doc.pss_id), url=url,
                            outcome="too_large",
                        )
                        continue
                    body = fetched
                    doc.fetched_from = url
                    doc.content_type = fetch_result.content_type or "application/octet-stream"
                    log.info(
                        "fulltext.fetch_attempt", pss_id=str(doc.pss_id), url=url, outcome="ok",
                    )
                    break
                doc.attempts.append(f"{url}: {fetch_result.error}")
                doc.reason = fetch_result.error
                log.info(
                    "fulltext.fetch_attempt", pss_id=str(doc.pss_id), url=url,
                    outcome=fetch_result.error,
                )
            if body is None:
                # every remaining candidate failed to fetch: last failure wins
                doc.resolution = "fetch_failed"
                continue
            jobs.append((i, body, doc.content_type or ""))
            job_meta[i] = (doc.fetched_from or "", doc.content_type or "")
        if not jobs:
            break

        results = _run_parse_jobs(
            jobs,
            max_workers=max_workers,
            parse_timeout=parse_timeout,
            thin_min=thin_min,
            parse_fn=parse_fn,
        )
        for i, result in results.items():
            doc = docs[i]
            if result["status"] == "ok":
                doc.resolution = "ingested"
                doc.parsed = result
                continue
            doc.attempts.append(f"{doc.fetched_from}: {result['reason']}")
            doc.reason = result["reason"]
            log.info(
                "fulltext.parse_failed", pss_id=str(doc.pss_id), url=doc.fetched_from,
                reason=result["reason"], detail=result.get("detail"),
            )
            if doc.next_url >= len(doc.urls):
                doc.resolution = "parse_failed"
            # else: unresolved — next round fetches the next candidate

    # Writes, in eligible-set order (decision 8: deterministic regardless of
    # completion order and worker count).
    now = datetime.now(UTC)
    counts = {"ingested": 0, "fetch_failed": 0, "parse_failed": 0}
    by_reason: dict[str, int] = {}
    for doc in docs:
        assert doc.resolution is not None  # every doc lands in exactly one bucket
        if doc.resolution == "ingested":
            assert doc.parsed is not None
            chunks = doc.parsed["chunks"]
            snapshot_id = uuid.uuid4()
            conn.execute(
                source_snapshot.insert().values(
                    source_snapshot_id=snapshot_id,
                    content_hash=content_hash("".join(c["content"] for c in chunks)),
                    text_basis="full_text",
                    source_locator=doc.fetched_from,
                    metadata={
                        # Required full-text snapshot metadata (adversarial
                        # findings 3 + 8): parse identity + governance breadcrumbs.
                        "parse_profile": doc.parsed["parse_profile"],
                        "segmentation_policy": doc.parsed["segmentation_policy"],
                        "fetched_from": doc.fetched_from,
                        "content_type": doc.content_type,
                        "envelope_source_snapshot_id": str(doc.envelope_snapshot_id),
                        "ingested_by_run_id": str(run_id),
                    },
                    created_at=now,
                )
            )
            for seq, chunk in enumerate(chunks, start=1):
                conn.execute(
                    chunk_table.insert().values(
                        chunk_id=uuid.uuid4(),
                        source_snapshot_id=snapshot_id,
                        sequence=seq,
                        content=chunk["content"],
                        content_hash=content_hash(chunk["content"]),
                        locator=chunk["locator"],
                        segmentation_policy=doc.parsed["segmentation_policy"],
                        created_at=now,
                    )
                )
            conn.execute(
                project_source_snapshot.update()
                .where(project_source_snapshot.c.project_source_snapshot_id == doc.pss_id)
                .values(
                    full_text_snapshot_id=snapshot_id,
                    full_text_status="ingested",
                    full_text_error=None,
                )
            )
            counts["ingested"] += 1
            log.info(
                "fulltext.ingested", pss_id=str(doc.pss_id), url=doc.fetched_from,
                chunk_count=len(chunks),
            )
        else:
            assert doc.reason is not None  # failure ⟺ reason, enforced by the CHECK too
            conn.execute(
                project_source_snapshot.update()
                .where(project_source_snapshot.c.project_source_snapshot_id == doc.pss_id)
                .values(
                    full_text_snapshot_id=None,
                    full_text_status=doc.resolution,
                    full_text_error=doc.reason,
                )
            )
            counts[doc.resolution] += 1
            by_reason[doc.reason] = by_reason.get(doc.reason, 0) + 1
            log.info(
                "fulltext.failed", pss_id=str(doc.pss_id), status=doc.resolution,
                reason=doc.reason, attempts=doc.attempts,
            )

    summary = {
        "eligible": len(eligible_rows),
        "already_ingested": already_ingested,
        **counts,
        "by_reason": by_reason,
    }
    log.info("fulltext.summary", **summary)
    return summary
