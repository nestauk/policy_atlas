"""Full-text ingestion component — fetch → parse → segment, post-screen Tier 0.

For every screened-in acquired source of a scope, resolve candidate URLs from the
provider fields task 007 retained, fetch through the ``DocumentFetcher`` seam
(current build: fixture replay of committed real, openly-licensed documents — zero
runtime egress until the live-fetcher slice opens that gate; live fetching is
v3.0-required, see docs/deferred.md), parse structure-aware (PDF via pymupdf4llm,
HTML via trafilatura), segment
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
import json
import os
import re
import time
import uuid
from collections import deque
from collections.abc import Callable, Iterable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, unquote, urljoin, urlsplit

import lxml.html  # type: ignore[import-untyped]
import pymupdf
import pymupdf4llm  # type: ignore[import-untyped]
import structlog
import trafilatura
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import (
    EmbeddingBackend,
    StubEmbeddingBackend,
    embed_pending_chunks,
)
from policy_atlas.core.hashing import content_hash
from policy_atlas.core.schema import (
    chunk as chunk_table,
)
from policy_atlas.core.schema import (
    project_source_snapshot,
    source_screening_result,
    source_snapshot,
)

log = structlog.get_logger()


def _install_deterministic_column_boxes() -> None:
    """Make pymupdf4llm's column layout process-stable (determinism, decision 8).

    pymupdf4llm 0.3.4 caches a "which background rect contains this block" lookup
    keyed on id(bb) (helpers/multi_column.py). Rect objects are freed and their
    addresses reused mid-loop, so the cache can return a stale neighbour's index;
    the collision pattern follows allocation addresses (ASLR) and so varies per
    process, making emitted markdown — and thus chunk content_hash — differ between
    identical parses (~1-in-9 on the 233-page fixture). PYTHONHASHSEED cannot help
    (it salts str/bytes hashing, not id()). We rebuild column_boxes with that one
    cache key changed to a value key; output is otherwise byte-identical. If a
    future pymupdf4llm changes the source, this no-ops — the fan-out determinism
    test is the backstop that would catch a regression.
    """
    import inspect

    import pymupdf4llm.helpers.multi_column as _mc  # type: ignore[import-untyped]
    import pymupdf4llm.helpers.pymupdf_rag as _rag  # type: ignore[import-untyped]  # imports column_boxes by name

    old = 'cache_key = f"{id(bb)}_{id(bboxes)}"'
    new = "cache_key = (tuple(bb), id(bboxes))"
    src = inspect.getsource(_mc.column_boxes)
    if old not in src:  # fixed upstream / source moved — no-op
        return
    namespace = dict(_mc.__dict__)
    exec(compile(src.replace(old, new), _mc.__file__, "exec"), namespace)  # noqa: S102
    _mc.column_boxes = namespace["column_boxes"]
    _rag.column_boxes = namespace["column_boxes"]


_install_deterministic_column_boxes()

FETCH_BYTE_CAP = 100 * 1024 * 1024  # generous guard, never a scissor (decision 6)
PARSE_TIMEOUT_SECONDS = 120.0  # hard per-document parse timeout; worker is terminated
# (120s: user-set 2026-07-05 — generous for a 200+-page report; fan-out absorbs the tail)
THIN_TEXT_MIN_CHARS = 200  # below this, parsed text is a failure, never "ok" (decision 7)
DEFAULT_MAX_WORKERS = 4
# LiveDocumentFetcher has the actual global/per-host semaphores; this pool only supplies threads.
LIVE_FETCH_WORKERS = 10

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
    "blocked", "blocked_by_host", "fetch_error",
)

_HTTP_STATUS_REASONS = {401: "paywall", 403: "blocked_by_host", 404: "not_found", 410: "not_found"}
FETCH_FAILURE_REASON_PRIORITY = (
    "paywall",
    "blocked_by_host",
    "blocked",
    "too_large",
    "timeout",
    "fetch_error",
    "empty",
    "not_found",
    "no_url",
)
_FETCH_FAILURE_REASON_SET = frozenset(FETCH_FAILURE_REASON_PRIORITY)


def _redact_url(url: str | None) -> str | None:
    """Return scheme + host + path only for log-safe URL rendering."""
    if url is None:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return url.split("?", 1)[0].split("#", 1)[0]
    if parts.scheme not in ("http", "https") or parts.hostname is None:
        return parts.path or url.split("?", 1)[0].split("#", 1)[0]
    host = parts.hostname
    try:
        port = parts.port
    except ValueError:
        port = None
    if port is not None:
        host = (
            f"[{host}]:{port}"
            if ":" in host and not host.startswith("[")
            else f"{host}:{port}"
        )
    return f"{parts.scheme}://{host}{parts.path}"


def _base_content_type(content_type: str | None) -> str:
    """Normalize a content type to its MIME base."""
    return (content_type or "").split(";", 1)[0].strip().lower()


def _highest_priority_fetch_reason(reasons: Iterable[str | None]) -> str:
    """Return the highest-priority fetch failure reason from a cascade."""
    seen = {reason for reason in reasons if reason in _FETCH_FAILURE_REASON_SET}
    for reason in FETCH_FAILURE_REASON_PRIORITY:
        if reason in seen:
            return reason
    return "no_url"


def _fetch_failure_reason(error: str | None) -> str:
    """Coerce a fetcher-provided error to the closed fetch-failure vocabulary."""
    if error in _FETCH_FAILURE_REASON_SET:
        return error
    return "fetch_error"


def _release_fetch_body(fetcher: "DocumentFetcher", n_bytes: int) -> None:
    """Duck-type the live fetcher's body-byte release hook."""
    release = getattr(fetcher, "release_body", None)
    if callable(release):
        release(n_bytes)


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
        """Fetch one URL. Never raises for per-document outcomes.

        Args:
            url: Absolute http(s) URL to fetch.

        Returns:
            ``ok`` with bytes + content type, or a reason-coded error.
        """
        ...


def _safe_fetch(fetcher: DocumentFetcher, url: str, *, pss_id: uuid.UUID) -> FetchResult:
    """Call the fetcher seam, reducing escaped per-link raises to ``fetch_error``.

    Args:
        fetcher: Fetcher seam implementation.
        url: Verbatim provider/discovered URL to fetch.
        pss_id: Link id for log correlation.

    Returns:
        The fetcher's result, or an ``error/fetch_error`` result when the
        fetcher unexpectedly raises for this URL.
    """
    try:
        return fetcher.fetch(url)
    except FileNotFoundError:
        # Configuration error, not a per-document outcome (e.g. a missing/empty
        # fixture corpus) — must fail the run loudly, never degrade to a
        # per-document fetch_error (016 review stack).
        raise
    except Exception as exc:
        log.warning(
            "fulltext.fetcher_escaped",
            pss_id=str(pss_id),
            url=_redact_url(url),
            exc_type=type(exc).__name__,
        )
        return FetchResult(status="error", error="fetch_error")


class FixtureFetcher:
    """Replays committed real documents by URL from the manifest. Zero egress.

    The fixture corpus is repo test data (``tests/data``), not package data — it
    never ships in the wheel (contract decision 12). URLs map to outcomes in
    ``fulltext_manifest.json``: ``ok`` entries read the committed document bytes;
    ``http_error``/``oversize`` entries replay the recorded failure. An unmapped
    URL is a dead link (``not_found``). The manifest loads lazily on first
    fetch, so constructing the default fetcher (every ``run_harness`` call)
    costs nothing for non-ingest components.
    """

    mode = "fixture"

    def __init__(self, root: Path | None = None) -> None:
        """Construct the fetcher. Cheap — no I/O until the first ``fetch()``.

        Args:
            root: Directory containing ``fulltext_manifest.json`` and the
                ``fulltext/`` document dir. If omitted, resolved lazily at first
                fetch from the ``POLICY_ATLAS_FIXTURE_CORPUS`` env var, else the
                repo-relative default ``tests/data``.
        """
        self._root_arg = root

    @functools.cached_property
    def _root(self) -> Path:
        if self._root_arg is not None:
            return self._root_arg
        if env_root := os.environ.get("POLICY_ATLAS_FIXTURE_CORPUS"):
            return Path(env_root)
        # src/policy_atlas/evidence_base/sourcing/ingest_full_text.py -> parents[4]
        # is the repo root (dev/test checkout only — the fixture corpus never
        # ships in the wheel).
        return Path(__file__).resolve().parents[4] / "tests" / "data"

    @functools.cached_property
    def _manifest(self) -> dict[str, Any]:
        manifest_path = self._root / "fulltext_manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(
                f"Fixture corpus manifest not found at {manifest_path}. The fixture "
                "corpus lives at tests/data/fulltext (manifest tests/data/"
                "fulltext_manifest.json) — point at a copy via the "
                "POLICY_ATLAS_FIXTURE_CORPUS env var if running outside the repo checkout."
            )
        data: dict[str, Any] = json.loads(manifest_path.read_text())
        return data

    def fetch(self, url: str) -> FetchResult:
        """Return the manifest-recorded outcome for ``url``.

        Args:
            url: Absolute http(s) URL; the manifest's fetch key.

        Returns:
            ``ok`` with the committed document's bytes, the recorded failure, or
            ``not_found`` for an unmapped URL (the honest dead-link equivalent).

        Raises:
            FileNotFoundError: The resolved fixture corpus (manifest or
                document dir) is missing — never a silent empty/not_found.
        """
        entry = self._manifest["outcomes"].get(url)
        if entry is None:
            return FetchResult(status="error", error="not_found")
        outcome = entry["outcome"]
        if outcome == "ok":
            name = entry["file"]
            # manifest names are basenames — keeps traversal structurally impossible
            assert "/" not in name and "\\" not in name, name
            doc_path = self._root / "fulltext" / name
            if not doc_path.is_file():
                raise FileNotFoundError(
                    f"Fixture corpus document not found at {doc_path}. The fixture "
                    "corpus lives at tests/data/fulltext — point at a copy via the "
                    "POLICY_ATLAS_FIXTURE_CORPUS env var if running outside the repo "
                    "checkout."
                )
            body = doc_path.read_bytes()
            return FetchResult(status="ok", content_type=entry["content_type"], body=body)
        if outcome == "oversize":
            return FetchResult(status="error", error="too_large")
        # http_error: map the recorded status to the reason vocabulary (decision 8).
        # 401 is unambiguous → paywall. A recorded 403 carries no body to
        # marker-scan, so it replays exactly as an uncorroborated live 403 would:
        # blocked_by_host (the live fetcher only upgrades to paywall when a
        # paywall marker is found in the response body — see
        # ``_response_outcome`` in fetch_live.py). The ingest-level OA
        # cross-check (``_apply_oa_cross_check``) may still upgrade a
        # blocked_by_host to paywall from envelope metadata. 404/410 → not_found.
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


_DOI_RE = re.compile(r"^10\.\d{4,9}/\S{1,200}$")
_DOI_HOSTS = frozenset({"doi.org", "dx.doi.org"})


def _valid_doi(value: Any) -> str | None:
    """Validate a bare, normalised DOI string (contract decision 7 recall aid).

    Must be a ``str`` matching ``^10\\.\\d{4,9}/\\S{1,200}$`` and contain no
    control characters — ``\\S`` alone does not exclude them (e.g. embedded
    ``\\x01`` is non-whitespace and would otherwise pass).

    Args:
        value: The candidate value (typically ``metadata["doi"]``).

    Returns:
        The DOI string if valid, else ``None`` (absence/invalidity is normal —
        no warning is logged).
    """
    if not isinstance(value, str) or not _DOI_RE.match(value):
        return None
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        return None
    return value


def _doi_url_already_present(urls: list[str], encoded_doi: str) -> bool:
    """True if ``urls`` already carries a doi.org URL for this DOI.

    Treats ``http://`` vs ``https://`` and ``dx.doi.org`` vs ``doi.org`` as the
    same URL, so the constructed fallback never duplicates a provider-supplied
    DOI link that only differs in scheme/host convention. Paths are compared
    percent-decoded and case-insensitively (Codex MINOR finding): a provider
    URL carrying the DOI's reserved characters unescaped (e.g.
    ``10.1234/ab(c)``) must still suppress the percent-encoded fallback
    (``10.1234/ab%28c%29``) — otherwise the two would wrongly look distinct.
    """
    target = unquote(encoded_doi.lstrip("/")).lower()
    for url in urls:
        parts = urlsplit(url)
        if (
            parts.netloc.lower() in _DOI_HOSTS
            and unquote(parts.path.lstrip("/")).lower() == target
        ):
            return True
    return False


def candidate_urls(metadata: dict[str, Any]) -> list[str]:
    """Resolve the ordered candidate-URL cascade from a snapshot's provider fields.

    OpenAlex: ``best_oa_location.pdf_url`` → ``primary_location.pdf_url`` →
    ``open_access.oa_url`` → ``primary_location.landing_page_url``. Overton:
    ``pdf_url`` → ``document_url``. Deduplicated preserving order; non-URL
    sentinels (e.g. Overton's ``"n/a"``) are treated as absent.

    Every URL above is verbatim provider metadata. The one exception (contract
    decision 3/7) is a DOI-URL fallback: when ``metadata["doi"]`` is a valid
    bare DOI (see ``_valid_doi``), ``https://doi.org/<percent-encoded doi>`` is
    appended as the LAST cascade entry — the one URL this function constructs
    rather than receives — unless an equivalent doi.org/dx.doi.org URL is
    already present.

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
        # An unmapped backend would otherwise masquerade as a per-document no_url
        # data problem — surface the wiring gap loudly (review finding).
        log.warning("fulltext.unknown_backend", backend=backend)
        raw = []
    urls: list[str] = []
    for value in raw:
        url = _normalize_url(value)
        if url is not None and url not in urls:
            urls.append(url)
    doi = _valid_doi(metadata.get("doi"))
    if doi is not None:
        encoded = quote(doi, safe="/")
        if not _doi_url_already_present(urls, encoded):
            urls.append(f"https://doi.org/{encoded}")
    return urls


_ANCHOR_SCAN_CAP = 2000  # bounds worst-case anchor scan cost on huge landing pages


def discover_document_url(html_body: bytes, base_url: str) -> str | None:
    """Discover a document URL from a fetched HTML landing page.

    Pure, side-effect-free recall aid (contract decision 7): no fetching and no
    SSRF validation beyond URL shape — the caller validates any returned URL
    before use.

    Priority 1: ``<meta name="citation_pdf_url" content="...">`` — the
    scholarly-metadata standard (name matched case-insensitively) — returned
    absolutized against ``base_url``.

    Priority 2 (only when priority 1 yields nothing): a bounded scan of
    ``<a href>`` anchors in document order (capped at ``_ANCHOR_SCAN_CAP``
    anchors), considering only those whose absolutized URL path ends ``.pdf``
    (case-insensitive; the query string and fragment are ignored when testing
    the path). Same-host candidates are preferred over cross-host ones: the
    first same-host candidate wins if any exists (the scan stops there — a
    same-host match cannot be beaten by a later candidate), else the first
    cross-host candidate.

    Only http(s) results are ever returned; a candidate that absolutizes to a
    non-http(s) scheme (e.g. ``javascript:``, ``mailto:``, ``ftp:``) is
    skipped.

    Args:
        html_body: Raw HTML bytes of the fetched landing page.
        base_url: The URL the page was fetched from — the absolutization base
            and the same-host comparison point.

    Returns:
        At most one discovered URL, or ``None`` if nothing qualifies or the
        HTML could not be parsed.
    """
    try:
        tree = lxml.html.fromstring(html_body)
    except Exception:
        return None

    base_host = urlsplit(base_url).netloc.lower()

    for meta in tree.iter("meta"):
        name = meta.get("name")
        if name is not None and name.strip().lower() == "citation_pdf_url":
            content = meta.get("content")
            if content:
                candidate: str = urljoin(base_url, str(content).strip())
                if urlsplit(candidate).scheme in ("http", "https"):
                    return candidate
            break  # standard allows one such tag; fall through to anchor scan

    same_host_candidate: str | None = None
    cross_host_candidate: str | None = None
    for anchor_count, anchor in enumerate(tree.iter("a")):
        if anchor_count >= _ANCHOR_SCAN_CAP:
            break
        href = anchor.get("href")
        if not href:
            continue
        candidate = urljoin(base_url, href)
        parts = urlsplit(candidate)
        if parts.scheme not in ("http", "https"):
            continue
        if not parts.path.lower().endswith(".pdf"):
            continue
        if parts.netloc.lower() == base_host:
            same_host_candidate = candidate
            break  # same-host wins unconditionally — scanning further is dead work
        if cross_host_candidate is None:
            cross_host_candidate = candidate

    return same_host_candidate or cross_host_candidate


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
        return {"status": "error", "reason": "corrupt", "detail": str(exc)[:500]}
    pages = [
        (int(pg.get("metadata", {}).get("page", i + 1)), str(pg.get("text", "")))
        for i, pg in enumerate(page_dicts)
    ]
    # \w is Unicode-aware: a text layer in any script counts (review finding — the
    # previous ASCII-only class misread e.g. CJK/Arabic PDFs as no_text_layer).
    if not any(re.search(r"\w", text) for _, text in pages):
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
    extracted = trafilatura.extract(body, include_comments=False, include_tables=True)
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
        result = {"status": "error", "reason": "corrupt", "detail": str(exc)[:500]}
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
        # Poll even when the deadline has lapsed (max → non-blocking): a sibling job
        # whose result is already buffered must never be misread as a timeout just
        # because an earlier-submitted job consumed this loop's wall-clock (step-7
        # review finding, confirmed).
        if recv_conn.poll(max(remaining, 0.0)):
            try:
                result = recv_conn.recv()
            except EOFError:  # worker died before sending (e.g. OOM-killed)
                result = {"status": "error", "reason": "corrupt", "detail": "worker died"}
            proc.join()
        else:
            proc.terminate()
            proc.join(5.0)
            if proc.is_alive():  # SIGTERM ignored/stuck in native code — escalate
                proc.kill()
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
    metadata: dict[str, Any]
    urls: list[str]
    next_url: int = 0
    attempts: list[str] = field(default_factory=list)
    fetch_failure_reasons: list[str] = field(default_factory=list)
    discovered_landing_urls: set[str] = field(default_factory=set)
    resolution: str | None = None  # "ingested" | "fetch_failed" | "parse_failed"
    reason: str | None = None
    parsed: dict[str, Any] | None = None
    fetched_from: str | None = None
    content_type: str | None = None


@dataclass(frozen=True)
class _FetchRoundResult:
    """Parent-thread result for one document's fetch walk in a cascade round."""

    body: bytes | None
    content_type: str
    bytes_fetched: int


def _maybe_discover_url(doc: _DocState, *, body: bytes, url: str, content_type: str) -> None:
    if _base_content_type(content_type) != "text/html":
        return
    if url in doc.discovered_landing_urls:
        return
    discovered = discover_document_url(body, url)
    doc.discovered_landing_urls.add(url)
    if discovered is None or discovered in doc.urls:
        return
    doc.urls.append(discovered)
    doc.attempts.append(f"{_redact_url(discovered)}: discovered_from={_redact_url(url)}")


def _openalex_is_oa(metadata: dict[str, Any]) -> bool | None:
    if metadata.get("backend") != "openalex":
        return None
    fields = metadata.get("provider_fields")
    if not isinstance(fields, dict):
        return None
    open_access = fields.get("open_access")
    if not isinstance(open_access, dict):
        return None
    is_oa = open_access.get("is_oa")
    return is_oa if isinstance(is_oa, bool) else None


def _apply_oa_cross_check(doc: _DocState) -> None:
    # 016 review stack decision 8's second corroboration channel: an envelope
    # marked OA-closed corroborates a 403 that fetch-time marker-scanning could
    # not (fetch_live has no envelope access). Reason selection is otherwise
    # owned entirely by FETCH_FAILURE_REASON_PRIORITY.
    is_oa = _openalex_is_oa(doc.metadata)
    if is_oa is False and doc.reason == "blocked_by_host":
        doc.reason = "paywall"
    if is_oa is True and doc.reason in {"paywall", "blocked_by_host"}:
        log.info(
            "fulltext.oa_inconsistency",
            pss_id=str(doc.pss_id),
            reason=doc.reason,
        )


def _fetch_doc_for_round(doc: _DocState, fetcher: DocumentFetcher) -> _FetchRoundResult:
    bytes_fetched = 0
    while doc.next_url < len(doc.urls):
        url = doc.urls[doc.next_url]
        doc.next_url += 1
        fetch_result = _safe_fetch(fetcher, url, pss_id=doc.pss_id)
        if fetch_result.status == "ok":
            fetched = fetch_result.body or b""
            bytes_fetched += len(fetched)
            content_type = fetch_result.content_type or "application/octet-stream"
            if len(fetched) > FETCH_BYTE_CAP:
                _release_fetch_body(fetcher, len(fetched))
                reason = "too_large"
                doc.attempts.append(f"{_redact_url(url)}: {reason}")
                doc.fetch_failure_reasons.append(reason)
                doc.reason = _highest_priority_fetch_reason(doc.fetch_failure_reasons)
                log.info(
                    "fulltext.fetch_attempt",
                    pss_id=str(doc.pss_id),
                    url=_redact_url(url),
                    outcome=reason,
                )
                continue
            _maybe_discover_url(doc, body=fetched, url=url, content_type=content_type)
            doc.fetched_from = url
            doc.content_type = content_type
            log.info(
                "fulltext.fetch_attempt",
                pss_id=str(doc.pss_id),
                url=_redact_url(url),
                outcome="ok",
            )
            return _FetchRoundResult(
                body=fetched,
                content_type=content_type,
                bytes_fetched=bytes_fetched,
            )
        reason = _fetch_failure_reason(fetch_result.error)
        doc.attempts.append(f"{_redact_url(url)}: {reason}")
        doc.fetch_failure_reasons.append(reason)
        doc.reason = _highest_priority_fetch_reason(doc.fetch_failure_reasons)
        log.info(
            "fulltext.fetch_attempt",
            pss_id=str(doc.pss_id),
            url=_redact_url(url),
            outcome=reason,
        )

    doc.resolution = "fetch_failed"
    doc.reason = _highest_priority_fetch_reason(doc.fetch_failure_reasons)
    return _FetchRoundResult(body=None, content_type="", bytes_fetched=bytes_fetched)


def _drain_ready_parse_jobs(
    *,
    ready_jobs: list[tuple[int, bytes, str]],
    ready_body_lengths: dict[int, int],
    docs: list[_DocState],
    fetcher: DocumentFetcher,
    max_workers: int,
    parse_timeout: float,
    thin_min: int,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]],
) -> bool:
    if not ready_jobs:
        return False
    jobs = sorted(ready_jobs, key=lambda job: job[0])
    body_lengths = dict(ready_body_lengths)
    ready_jobs.clear()
    ready_body_lengths.clear()
    released: set[int] = set()
    try:
        results = _run_parse_jobs(
            jobs,
            max_workers=max_workers,
            parse_timeout=parse_timeout,
            thin_min=thin_min,
            parse_fn=parse_fn,
        )
    except Exception:
        for idx, n_bytes in body_lengths.items():
            if idx not in released:
                _release_fetch_body(fetcher, n_bytes)
        raise
    try:
        for i, result in results.items():
            _release_fetch_body(fetcher, body_lengths[i])
            released.add(i)
            doc = docs[i]
            if result["status"] == "ok":
                doc.resolution = "ingested"
                doc.parsed = result
                continue
            doc.attempts.append(f"{_redact_url(doc.fetched_from)}: {result['reason']}")
            doc.reason = result["reason"]
            log.info(
                "fulltext.parse_failed",
                pss_id=str(doc.pss_id),
                url=_redact_url(doc.fetched_from),
                reason=result["reason"],
                detail=result.get("detail"),
            )
            if doc.next_url >= len(doc.urls):
                doc.resolution = "parse_failed"
            # else: unresolved — next round fetches the next candidate
    finally:
        for idx, n_bytes in body_lengths.items():
            if idx not in released:
                _release_fetch_body(fetcher, n_bytes)
    return True


def ingest_full_text_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: IngestFullTextContext,
    fetcher: DocumentFetcher,
    embedder: EmbeddingBackend | None = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
    fetch_workers: int | None = None,
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
        embedder: Optional embedding backend. Defaults to the deterministic stub.
        max_workers: Bound on live worker processes.
        fetch_workers: Bound on parent-side fetch threads. ``None`` resolves to
            ``LIVE_FETCH_WORKERS`` for live fetchers and ``1`` for fixture replay.
        parse_timeout: Hard per-document parse timeout in seconds.
        thin_min: Thin-text guard threshold in characters.
        parse_fn: Parse callable (test seam; must be a picklable top-level function).

    Returns:
        Counts dict: ``eligible``, ``attempted``, ``ingested``,
        ``already_ingested``, ``fetch_failed``, ``parse_failed``,
        ``by_reason``, ``bytes_fetched``, ``wall_clock_s``, ``embed``
        (invariant:
        ``eligible == ingested + already_ingested + fetch_failed + parse_failed``).
    """
    started_at = time.monotonic()
    if fetch_workers is None:
        resolved_fetch_workers = LIVE_FETCH_WORKERS if fetcher.mode == "live" else 1
    else:
        resolved_fetch_workers = fetch_workers
    if resolved_fetch_workers < 1:
        raise ValueError("fetch_workers must be >= 1")

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
        # Stage-1 relevant ONLY: stage 2 runs post-ingestion (it needs the full
        # text this component produces), so fetch must never consult stage-2
        # rows. The effective-screen-rows helper ranks by highest stage, which
        # would return a stage-2 verdict once one exists — wrong for this
        # reader — so this filters screen_stage inline instead (screen.py's
        # unique-non-failed-per-stage constraint means at most one such row).
        .where(source_screening_result.c.screen_stage == 1)
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.origin == "acquired")
        .order_by(project_source_snapshot.c.project_source_snapshot_id)
    ).fetchall()

    already_ingested = sum(1 for row in eligible_rows if row.full_text_status == "ingested")
    docs: list[_DocState] = [
        _DocState(
            pss_id=row.project_source_snapshot_id,
            envelope_snapshot_id=row.source_snapshot_id,
            metadata=dict(row.metadata),
            urls=candidate_urls(row.metadata),
        )
        for row in eligible_rows
        if row.full_text_status != "ingested"
    ]

    for doc in docs:
        if not doc.urls:
            # Durable state, distinguishable from not_attempted (adversarial finding 1)
            doc.resolution, doc.reason = "fetch_failed", "no_url"
            doc.fetch_failure_reasons.append("no_url")

    # Cascade rounds: fetch in the parent, parse in workers; a parse failure with
    # candidates remaining re-enters the next round on its next URL (decision 4).
    bytes_fetched = 0
    while True:
        unresolved = [
            (i, doc)
            for i, doc in enumerate(docs)
            if doc.resolution is None
        ]
        if not unresolved:
            break
        parsed_any = False
        ready_jobs: list[tuple[int, bytes, str]] = []
        ready_body_lengths: dict[int, int] = {}
        serial_fixture_fetch = resolved_fetch_workers == 1 and fetcher.mode != "live"

        with ThreadPoolExecutor(max_workers=resolved_fetch_workers) as executor:
            future_to_index: dict[Future[_FetchRoundResult], int] = {
                executor.submit(_fetch_doc_for_round, doc, fetcher): i
                for i, doc in unresolved
            }
            pending = set(future_to_index)
            while pending:
                timeout = None if serial_fixture_fetch else 0.1 if ready_jobs else None
                done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
                if not done:
                    parsed_any = (
                        _drain_ready_parse_jobs(
                            ready_jobs=ready_jobs,
                            ready_body_lengths=ready_body_lengths,
                            docs=docs,
                            fetcher=fetcher,
                            max_workers=max_workers,
                            parse_timeout=parse_timeout,
                            thin_min=thin_min,
                            parse_fn=parse_fn,
                        )
                        or parsed_any
                    )
                    continue
                for future in done:
                    i = future_to_index[future]
                    outcome = future.result()
                    bytes_fetched += outcome.bytes_fetched
                    if outcome.body is None:
                        continue
                    ready_jobs.append((i, outcome.body, outcome.content_type))
                    ready_body_lengths[i] = len(outcome.body)
                if not serial_fixture_fetch and len(ready_jobs) >= max_workers:
                    parsed_any = (
                        _drain_ready_parse_jobs(
                            ready_jobs=ready_jobs,
                            ready_body_lengths=ready_body_lengths,
                            docs=docs,
                            fetcher=fetcher,
                            max_workers=max_workers,
                            parse_timeout=parse_timeout,
                            thin_min=thin_min,
                            parse_fn=parse_fn,
                        )
                        or parsed_any
                    )
            parsed_any = (
                _drain_ready_parse_jobs(
                    ready_jobs=ready_jobs,
                    ready_body_lengths=ready_body_lengths,
                    docs=docs,
                    fetcher=fetcher,
                    max_workers=max_workers,
                    parse_timeout=parse_timeout,
                    thin_min=thin_min,
                    parse_fn=parse_fn,
                )
                or parsed_any
            )
        if not parsed_any:
            break

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
                "fulltext.ingested", pss_id=str(doc.pss_id), url=_redact_url(doc.fetched_from),
                chunk_count=len(chunks),
            )
        else:
            if doc.resolution == "fetch_failed":
                _apply_oa_cross_check(doc)
            # failure ⟺ closed-vocabulary reason (the CHECK enforces presence; the
            # vocabulary is code-enforced here, as the FAILURE_REASONS comment claims)
            assert doc.reason in FAILURE_REASONS, doc.reason
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

    if embedder is None:
        embedder = StubEmbeddingBackend()
    embed_counts = embed_pending_chunks(
        conn,
        embedder=embedder,
        project_id=project_id,
        run_id=run_id,
    )

    summary = {
        "eligible": len(eligible_rows),
        "attempted": len(docs),
        "already_ingested": already_ingested,
        **counts,
        "by_reason": by_reason,
        "bytes_fetched": bytes_fetched,
        "wall_clock_s": round(time.monotonic() - started_at, 2),
        "embed": embed_counts,
    }
    log.info("fulltext.summary", **summary)
    return summary
