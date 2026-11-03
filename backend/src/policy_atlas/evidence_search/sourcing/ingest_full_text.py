"""Full-text ingestion component — fetch → parse → segment, post-screen Tier 0.

For every screened-in acquired source of a scope, resolve candidate URLs from the
provider fields task 007 retained, fetch through the ``DocumentFetcher`` seam
(current build: fixture replay of committed real, openly-licensed documents — zero
runtime egress until the live-fetcher slice opens that gate; live fetching is
v3.0-required, see docs/deferred.md), parse structure-aware (PDF via pymupdf4llm,
HTML via trafilatura, Europe PMC JATS XML via ``parse_jats``), segment
under named versioned policies, and attach the resulting immutable ``full_text``
snapshot to the corpus document via ``task_source_snapshot.full_text_snapshot_id``
(ADR 0003).

Never truncate: a stored ``full_text`` snapshot is the whole parsed document; the
fetch byte cap and the hard per-document parse timeout are guards that fail loudly
(``too_large`` / ``timeout``), never scissors (contract decision 6). A failed source
stays on the text in hand with a queryable, reason-coded ``full_text_status`` —
nothing is dropped, nothing is silent (decision 3).

Task 057 (P8, P9): one document is handled by one call of
``ingest_document.ingest_document`` (fetch, store-key lookup, parse in its own
terminable process, one short write transaction). The stage below queues the
eligible documents, sends one message per document to a queue client, waits for
the documents to resolve, and embeds. The in-process client runs the function on a
thread pool, one database connection per thread; the cloud client (Phase 4b) puts
the messages on a queue that a function reads. Parse workers receive primitives
only (decision 8, adversarial findings 6 + 7). Each document's text is decided by
its own bytes, so the persisted outcome does not depend on the number of workers.
"""

import functools
import json
import os
import re
import threading
import time
import uuid
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
from multiprocessing import get_context
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import quote, unquote, urljoin, urlsplit

import lxml.html  # type: ignore[import-untyped]
import pymupdf
import pymupdf4llm  # type: ignore[import-untyped]
import structlog
import trafilatura
from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import (
    EmbeddingBackend,
    StubEmbeddingBackend,
    embed_pending_chunks,
)
from policy_atlas.core.liveness import publish_current_tick
from policy_atlas.core.markup import strip_markup
from policy_atlas.core.schema import (
    source_screening_result,
    source_snapshot,
    task_source_snapshot,
)
from policy_atlas.evidence_search.sourcing.parse_jats import (
    JATS_PARSE_PROFILE,
    JATS_SEGMENTATION_POLICY,
    parse_jats,
)

if TYPE_CHECKING:
    from policy_atlas.evidence_search.sourcing.ingest_queue import QueueClient, SendResult

log = structlog.get_logger()

#: Opens one short database transaction that commits when the block exits
#: (``engine.begin`` in production; a savepoint on the test connection inline).
ConnectFactory = Callable[[], AbstractContextManager[Connection]]


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
# Parse workers are separate processes doing CPU-bound work, so the width follows
# the cores: 4 on the 2-vCPU staging task, up to 8 on a developer machine
# (task 044 phase 8, owner 2026-09-17). In process (task 057) it is also the number
# of threads that each fetch, parse and write one document at a time.
DEFAULT_MAX_WORKERS = max(4, min(8, os.cpu_count() or 4))
# How often the stage reads the documents' statuses while they are being ingested.
STAGE_POLL_SECONDS = 3.0
# Task 057 (N2, D4): the per-document deadline, as a ``time.monotonic()`` value, for
# the fetcher's waits (set by ``ingest_document`` around its fetches; None in
# process). No wait or parse is started that would end within the margin of it.
FETCH_DEADLINE: ContextVar[float | None] = ContextVar("fetch_deadline", default=None)
DEADLINE_MARGIN_S = 5.0

# Parse profile v2 (task 057, N7/D8): the same parsers and cuts as v1, with the markup
# rule (``core.markup.strip_markup``) applied to every chunk's text and heading. The v1
# names stay on the snapshots parsed under v1; the parser no longer stamps them.
PDF_PARSE_PROFILE = "pymupdf4llm_v2"
HTML_PARSE_PROFILE = "trafilatura_v2"
PLAIN_PARSE_PROFILE = "plain_v2"
PDF_SEGMENTATION_POLICY = "pymupdf4llm_struct_v2"
HTML_SEGMENTATION_POLICY = "trafilatura_para_v2"
PLAIN_SEGMENTATION_POLICY = "plain_para_v2"

# Europe PMC JATS XML (task 056, N10/S7). The live fetcher never labels a body
# with an XML type (it sniffs PDF / HTML / plain), so only the Europe PMC
# candidate reaches the JATS branch of ``parse_and_segment``.
EUROPE_PMC_XML_CONTENT_TYPE = "application/xml"
_JATS_CONTENT_TYPES = frozenset({"application/xml", "text/xml"})
# Which route served an ingested document (stored as ``source_kind`` on the
# full-text snapshot's metadata; counted as ``by_route`` in the run summary).
ROUTE_EUROPE_PMC_XML = "europe_pmc_xml"
# Europe PMC full-text XML endpoint (task 056 S7, egress approved 2026-11-01): the only
# thing sent is the PubMed Central id, in the path.
EUROPE_PMC_HOST = "www.ebi.ac.uk"
EUROPE_PMC_FULL_TEXT_URL = (
    f"https://{EUROPE_PMC_HOST}/europepmc/webservices/rest/{{pmcid}}/fullTextXML"
)
# OpenAlex stores the id as a link whose last part is the number, with or without
# the "PMC" prefix (e.g. ``https://www.ncbi.nlm.nih.gov/pmc/articles/5264339``).
_PMCID_LOOSE_RE = re.compile(r"(?:^|/)(?:PMC)?([0-9]{1,12})/?$", re.IGNORECASE)

# Closed failure-reason vocabulary (contract decision 3). Presence on failure is
# CHECK-enforced (ck_tss_full_text_error_presence); the values are code-enforced so
# the list can grow at the live seam without a migration.
#
# Task 057 adds two reasons the stage writes, never the per-document function, and
# neither is an access failure: ``not_ready`` (the document was still being read
# when the stage stopped waiting; the next run tries it again) and ``send_failed``
# (the queue refused the message).
FAILURE_REASONS = (
    "no_url", "paywall", "not_found", "too_large", "timeout",
    "corrupt", "no_text_layer", "thin_text", "empty",
    "blocked", "blocked_by_host", "fetch_error", "unsupported_type",
    "not_ready", "send_failed",
)

# Base content types that are never parseable text; anything here fails fast with
# a reason-coded outcome instead of being chunked as text (prod incident 2026-08-19:
# a JPEG routed to the plain path and its NUL bytes killed the whole run at INSERT).
_NON_TEXT_TYPE_PREFIXES = ("image/", "audio/", "video/", "font/", "model/")

# A short page telling the client to enable JavaScript or cookies is the host
# blocking a bot, not the document — record it as blocked_by_host, never as full
# text (issue #74: a 284-char "JavaScript is disabled" wall cleared the 200-char
# thin-text floor and 6 of 21 "read in full" documents were that page). Only
# consulted below the ceiling, so a real paper that discusses JavaScript is
# unaffected.
_STUB_PAGE_CEILING_CHARS = 2000
_STUB_PAGE_MARKERS = (
    "javascript is disabled",
    "javascript is required",
    "enable javascript",
    "cookies are disabled",
    "enable cookies",
    "checking your browser",
    "just a moment...",
    "verify you are a human",
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


def _safe_fetch(fetcher: DocumentFetcher, url: str, *, tss_id: uuid.UUID) -> FetchResult:
    """Call the fetcher seam, reducing escaped per-link raises to ``fetch_error``.

    Args:
        fetcher: Fetcher seam implementation.
        url: Verbatim provider/discovered URL to fetch.
        tss_id: Link id for log correlation.

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
            tss_id=str(tss_id),
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
        # src/policy_atlas/evidence_search/sourcing/ingest_full_text.py -> parents[4]
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


def normalise_pmcid(value: object) -> str | None:
    """Turn a stored PubMed Central id into the ``PMC<digits>`` form Europe PMC wants.

    OpenAlex keeps the id as a web link (``https://www.ncbi.nlm.nih.gov/pmc/articles/5264339``),
    sometimes with the ``PMC`` prefix and sometimes without; other sources give
    ``PMC5264339`` or the bare number.

    Args:
        value: The stored id in any of those forms.

    Returns:
        ``"PMC5264339"``-style id, or ``None`` when the value is not a PubMed
        Central id.
    """
    if not isinstance(value, str):
        return None
    match = _PMCID_LOOSE_RE.search(value.strip())
    if match is None:
        return None
    return f"PMC{match.group(1)}"


def europe_pmc_candidate(metadata: dict[str, Any]) -> tuple[str, str] | None:
    """Return the Europe PMC XML candidate for a document carrying a PubMed Central id.

    The id is read from ``provider_fields.ids.pmcid`` (OpenAlex keeps it as a
    link ending in the number) and normalised to ``PMC<digits>``.

    Args:
        metadata: The envelope snapshot's metadata JSONB.

    Returns:
        ``(pmcid, europe_pmc_full_text_url)``, or ``None`` when no valid id is stored.
    """
    fields = metadata.get("provider_fields")
    ids = fields.get("ids") if isinstance(fields, dict) else None
    pmcid = normalise_pmcid(ids.get("pmcid")) if isinstance(ids, dict) else None
    if pmcid is None:
        return None
    return pmcid, EUROPE_PMC_FULL_TEXT_URL.format(pmcid=pmcid)


def _route_of(fetched_from: str | None, xml_url: str | None, content_type: str | None) -> str:
    """Name the route that served a document: Europe PMC XML, PDF, HTML or plain text."""
    if xml_url is not None and fetched_from == xml_url:
        return ROUTE_EUROPE_PMC_XML
    base_type = _base_content_type(content_type)
    if base_type == "application/pdf":
        return "pdf"
    if base_type == "text/html":
        return "html"
    return "plain"


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


def _strip_markup_lines(text: str) -> str:
    """One line of text without markup; a ``<br>`` in it starts a new, trimmed line."""
    return "\n".join(part for part in (p.strip() for p in strip_markup(text).split("\n")) if part)


def _clean_heading(text: str) -> str:
    """Heading text without markup, its whitespace collapsed to single spaces."""
    return " ".join(strip_markup(text).split())


def _segment_markdown_pages(pages: list[tuple[int, str]]) -> list[dict[str, Any]]:
    """Segment pymupdf4llm markdown into heading-bounded section + table chunks.

    Sections may span pages; each chunk's locator carries its page number(s) and
    the heading path in force (decision 7 — the provenance v2 threw away).

    Parse profile v2 (task 057, N7): the markup rule runs on every line as it is
    read, after the line has been recognised as a heading, a table row or body
    text, so the structure (which lines are headings, which are tables) is decided
    exactly as in v1. Body lines are cleaned with ``table=False`` (a ``<br>`` starts
    a new line); a body line that is only markup (an image, say) is dropped. Table
    rows are cleaned with ``table=True`` (a ``<br>`` becomes a space, so the row
    stays one line). Heading text is cleaned before it goes into the locator.

    Args:
        pages: ``(page_number, markdown_text)`` pairs in reading order.

    Returns:
        Chunks as ``{"content": str, "locator": {"pages": [...], "heading_path":
        [...]}}`` dicts, in reading order.
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
                heading_stack.append(_clean_heading(heading.group(2)))
                continue
            if stripped.startswith("|"):
                flush_paragraph()
                table_lines.append(strip_markup(stripped, table=True).strip())
                table_pages.add(page_no)
                continue
            flush_table()
            if not stripped:
                flush_paragraph()
                continue
            cleaned = _strip_markup_lines(stripped)
            if not cleaned:
                continue  # the line was only markup
            paragraph_lines.append(cleaned)
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
    # Parse profile v2: the markup rule on each paragraph (a ``<br>`` inside one starts
    # a new line within the same chunk); a paragraph that was only markup is dropped.
    chunks = [
        {"content": para, "locator": {"paragraph": i}}
        for i, para in enumerate((_strip_markup_lines(p) for p in extracted.splitlines()), start=1)
        if para
    ]
    return {
        "status": "ok",
        "chunks": chunks,
        "parse_profile": HTML_PARSE_PROFILE,
        "segmentation_policy": HTML_SEGMENTATION_POLICY,
    }


def _parse_plain(body: bytes) -> dict[str, Any]:
    if b"\x00" in body:
        # NUL bytes mean binary (git's own binary heuristic) — mislabeled or
        # untyped binary lands here; Postgres text columns reject NUL anyway.
        return {"status": "error", "reason": "unsupported_type"}
    text = _decode(body)
    if not text.strip():
        return {"status": "error", "reason": "empty"}
    # Parse profile v2: the markup rule on each paragraph, line by line.
    paragraphs = [
        cleaned
        for p in re.split(r"\n\s*\n", text)
        if (cleaned := strip_markup(p.strip()).strip())
    ]
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


def parse_profile_for(content_type: str) -> tuple[str, str]:
    """Name the parse profile and segmentation policy a content type is parsed under.

    The same choice :func:`parse_and_segment` makes, without parsing anything, so
    the document store can be searched for an existing parse of the same bytes
    (keyed by body hash, parse profile and segmentation policy) before parsing.

    Args:
        content_type: The fetched body's content type (parameters such as
            ``; charset=utf-8`` are ignored, case does not matter).

    Returns:
        ``(parse_profile, segmentation_policy)``.

    Raises:
        ValueError: The content type is one :func:`parse_and_segment` refuses
            without parsing (``image/``, ``audio/``, ``video/``, ``font/``,
            ``model/``): no profile applies, and the outcome is
            ``unsupported_type``.
    """
    base_type = content_type.split(";")[0].strip().lower()
    if base_type.startswith(_NON_TEXT_TYPE_PREFIXES):
        raise ValueError(f"unsupported_type: {base_type}")
    if base_type == "application/pdf":
        return PDF_PARSE_PROFILE, PDF_SEGMENTATION_POLICY
    if base_type == "text/html":
        return HTML_PARSE_PROFILE, HTML_SEGMENTATION_POLICY
    if base_type in _JATS_CONTENT_TYPES:
        return JATS_PARSE_PROFILE, JATS_SEGMENTATION_POLICY
    return PLAIN_PARSE_PROFILE, PLAIN_SEGMENTATION_POLICY


def parse_and_segment(body: bytes, content_type: str, thin_min: int) -> dict[str, Any]:
    """Parse document bytes and segment them under the named policy for their type.

    Pure function over primitives — no DB, no network, no shared state — so it can
    run in a separate worker process (decision 8). Never raises for per-document
    outcomes.

    Args:
        body: Raw document bytes.
        content_type: ``"application/pdf"`` | ``"text/html"`` | ``"text/plain"`` |
            ``"application/xml"`` / ``"text/xml"`` (Europe PMC JATS, task 056).
        thin_min: Minimum total parsed characters; below it → ``thin_text``.

    Returns:
        ``{"status": "ok", "chunks": [...], "parse_profile": ..., "segmentation_policy": ...}``
        or ``{"status": "error", "reason": <closed vocabulary>}``.
    """
    base_type = content_type.split(";")[0].strip().lower()
    if base_type.startswith(_NON_TEXT_TYPE_PREFIXES):
        return {"status": "error", "reason": "unsupported_type"}
    if base_type == "application/pdf":
        result = _parse_pdf(body)
    elif base_type == "text/html":
        result = _parse_html(body)
    elif base_type in _JATS_CONTENT_TYPES:
        # JATS XML: one pseudo-page of heading-marked text, cut by the same
        # segmenter as the PDF branch (locators keep the parser's ``pages: [1]``;
        # nothing reads the page of an XML chunk). A ``corrupt`` / ``empty``
        # parse is an ordinary parse failure: the cascade moves on to the next
        # candidate (the PDF) when one remains.
        jats = parse_jats(body)
        if jats["status"] != "ok":
            return jats
        result = {
            "status": "ok",
            "chunks": _segment_markdown_pages(jats["pages"]),
            "parse_profile": jats["parse_profile"],
            "segmentation_policy": jats["segmentation_policy"],
        }
    else:
        result = _parse_plain(body)
    if result["status"] != "ok":
        return result
    for c in result["chunks"]:
        # Stray NULs from PDF/HTML extraction would abort the whole write
        # transaction at INSERT (Postgres text rejects NUL) — replace like any
        # other undecodable byte.
        c["content"] = c["content"].replace("\x00", "�")
    total_chars = sum(len(c["content"]) for c in result["chunks"])
    if total_chars == 0:
        reason = "no_text_layer" if base_type == "application/pdf" else "empty"
        return {"status": "error", "reason": reason}
    if total_chars < _STUB_PAGE_CEILING_CHARS:
        lowered = "\n".join(c["content"] for c in result["chunks"]).lower()
        if any(marker in lowered for marker in _STUB_PAGE_MARKERS):
            return {"status": "error", "reason": "blocked_by_host"}
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
    """Worker-process entrypoint: parse, send the result, exit. Top-level so it pickles."""
    try:
        result = parse_fn(body, content_type, thin_min)
    except Exception as exc:  # defensive: an unexpected parser crash is a corrupt parse
        result = {"status": "error", "reason": "corrupt", "detail": str(exc)[:500]}
    send_conn.send(result)
    send_conn.close()


def _parse_process_context() -> Any:
    """Return the start-method context for parse workers (task 056, N8).

    A ``forkserver`` context whose helper ("server") process imports this module
    once, and with it pymupdf4llm, trafilatura and the determinism patch above.
    Each parse job is still its own process, forked from that already-loaded
    server, so it starts in milliseconds instead of re-importing the parsers
    (1 to 2 s per document under ``spawn``), and a stuck job can still be
    terminated on its own. The server is started fresh (not forked from this
    threaded process), so the fork-with-threads hazard does not apply.

    Returns:
        The process-wide forkserver context (the preload list is set once).
    """
    with _PARSE_CONTEXT_LOCK:
        global _PARSE_CONTEXT
        if _PARSE_CONTEXT is None:
            ctx = get_context("forkserver")
            ctx.set_forkserver_preload([__name__])
            _PARSE_CONTEXT = ctx
        return _PARSE_CONTEXT


_PARSE_CONTEXT: Any = None
_PARSE_CONTEXT_LOCK = threading.Lock()


def run_parse_worker(
    parse_fn: Callable[[bytes, str, int], dict[str, Any]],
    body: bytes,
    content_type: str,
    *,
    thin_min: int,
    timeout: float,
) -> dict[str, Any]:
    """Parse one document in its own process, killing it if it runs out of time.

    The process is forked from the preloaded forkserver (task 056, N8), so it
    starts in milliseconds, and it is a real process, so a parser stuck in native
    code can be terminated (adversarial finding 6). It receives primitives only
    (finding 7). While it runs it holds one of the process-wide ingest slots
    (task 045, S2), so every walk in the process shares one budget of parse
    processes. The pipe is readable when the worker has sent its result or has
    died, so a child busy sending a large result is never misread as a timeout.

    Args:
        parse_fn: Top-level parse callable (a test seam; the worker imports it by
            reference, so it must be picklable).
        body: The fetched document bytes.
        content_type: The body's content type.
        thin_min: Passed through to ``parse_fn``.
        timeout: Seconds the parse may run, from the worker's start.

    Returns:
        The parse result: ok, a reason-coded error, or ``{"status": "error",
        "reason": "timeout"}`` when the worker was killed.
    """
    # Imported here, not at module level: the slots module sizes itself from
    # this module's constant.
    from policy_atlas.runtime.walk_pool import INGEST_SLOTS

    ctx = _parse_process_context()
    with INGEST_SLOTS:
        recv_conn, send_conn = ctx.Pipe(duplex=False)
        proc = ctx.Process(
            target=_worker_entry, args=(send_conn, parse_fn, body, content_type, thin_min)
        )
        try:
            proc.start()
        finally:
            send_conn.close()  # the parent keeps only the receive end
        try:
            result: dict[str, Any]
            if recv_conn.poll(max(timeout, 0.0)):
                try:
                    result = recv_conn.recv()
                except EOFError:  # the worker died before sending (e.g. OOM-killed)
                    result = {"status": "error", "reason": "corrupt", "detail": "worker died"}
                proc.join()
            else:
                result = {"status": "error", "reason": "timeout"}
        finally:
            recv_conn.close()
            if proc.is_alive():
                proc.terminate()
                proc.join(5.0)
                if proc.is_alive():  # SIGTERM ignored or stuck in native code: escalate
                    proc.kill()
                    proc.join()
    return result


# --- Per-document cascade state (used by ``ingest_document``) ---


@dataclass
class _DocState:
    """One document's cascade state while ``ingest_document`` walks its candidates."""

    tss_id: uuid.UUID
    metadata: dict[str, Any]
    urls: list[str]
    xml_pmcid: str | None = None  # set when ``urls[0]`` is the Europe PMC candidate
    xml_url: str | None = None
    next_url: int = 0
    attempts: list[str] = field(default_factory=list)
    fetch_failure_reasons: list[str] = field(default_factory=list)
    discovered_landing_urls: set[str] = field(default_factory=set)
    resolution: str | None = None  # "ingested" | "fetch_failed" | "parse_failed"
    reason: str | None = None
    fetched_from: str | None = None
    content_type: str | None = None


@dataclass(frozen=True)
class _FetchStep:
    """One step of a document's fetch walk: the next body in hand, or none left."""

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
            tss_id=str(doc.tss_id),
            reason=doc.reason,
        )


def _safe_fetch_xml(fetcher: DocumentFetcher, pmcid: str, *, tss_id: uuid.UUID) -> bytes | None:
    """Call the fetcher's Europe PMC hook; an escaped raise counts as no XML."""
    try:
        body: bytes | None = getattr(fetcher, "fetch_europe_pmc_xml")(pmcid)  # noqa: B009
    except Exception as exc:
        log.warning(
            "fulltext.fetcher_escaped",
            tss_id=str(tss_id),
            url="europe_pmc_xml",
            exc_type=type(exc).__name__,
        )
        return None
    return body


def _fetch_next_body(doc: _DocState, fetcher: DocumentFetcher) -> _FetchStep:
    """Walk the document's remaining candidate URLs until one returns a body.

    Records every failed attempt on ``doc``; when the candidates run out the
    document is resolved ``fetch_failed`` with the highest-priority reason seen.

    Args:
        doc: The document's cascade state (advanced in place).
        fetcher: The fetch seam.

    Returns:
        The body and its content type, or ``body=None`` when nothing was fetched.
    """
    bytes_fetched = 0
    while doc.next_url < len(doc.urls):
        url = doc.urls[doc.next_url]
        doc.next_url += 1
        if doc.xml_pmcid is not None and url == doc.xml_url:
            xml = _safe_fetch_xml(fetcher, doc.xml_pmcid, tss_id=doc.tss_id)
            if xml is None:
                # No XML from Europe PMC: fall through to the next candidate,
                # exactly as a failed URL does.
                doc.attempts.append(f"{_redact_url(url)}: not_found")
                doc.fetch_failure_reasons.append("not_found")
                doc.reason = _highest_priority_fetch_reason(doc.fetch_failure_reasons)
                log.info(
                    "fulltext.fetch_attempt",
                    tss_id=str(doc.tss_id),
                    url=_redact_url(url),
                    outcome="not_found",
                )
                continue
            bytes_fetched += len(xml)
            doc.fetched_from = url
            doc.content_type = EUROPE_PMC_XML_CONTENT_TYPE
            log.info(
                "fulltext.fetch_attempt",
                tss_id=str(doc.tss_id),
                url=_redact_url(url),
                outcome="ok",
            )
            return _FetchStep(
                body=xml,
                content_type=EUROPE_PMC_XML_CONTENT_TYPE,
                bytes_fetched=bytes_fetched,
            )
        fetch_result = _safe_fetch(fetcher, url, tss_id=doc.tss_id)
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
                    tss_id=str(doc.tss_id),
                    url=_redact_url(url),
                    outcome=reason,
                )
                continue
            _maybe_discover_url(doc, body=fetched, url=url, content_type=content_type)
            doc.fetched_from = url
            doc.content_type = content_type
            log.info(
                "fulltext.fetch_attempt",
                tss_id=str(doc.tss_id),
                url=_redact_url(url),
                outcome="ok",
            )
            return _FetchStep(
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
            tss_id=str(doc.tss_id),
            url=_redact_url(url),
            outcome=reason,
        )

    doc.resolution = "fetch_failed"
    doc.reason = _highest_priority_fetch_reason(doc.fetch_failure_reasons)
    return _FetchStep(body=None, content_type="", bytes_fetched=bytes_fetched)


# --- The stage ---


def _eligible_rows(conn: Connection, *, task_id: uuid.UUID, scope_id: uuid.UUID) -> list[Any]:
    """The stage's eligible set: the scope's stage-1 relevant acquired documents."""
    return list(conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            task_source_snapshot.c.full_text_status,
        )
        .select_from(
            source_screening_result.join(
                task_source_snapshot,
                (source_screening_result.c.task_source_snapshot_id
                 == task_source_snapshot.c.task_source_snapshot_id)
                & (source_screening_result.c.task_id
                   == task_source_snapshot.c.task_id),
            )
        )
        .where(source_screening_result.c.evidence_scope_id == scope_id)
        .where(source_screening_result.c.status == "relevant")
        # Stage-1 relevant ONLY: stage 2 runs post-ingestion (it needs the full
        # text this component produces), so fetch must never consult stage-2
        # rows. The effective-screen-rows helper ranks by highest stage, which
        # would return a stage-2 verdict once one exists — wrong for this
        # reader — so this filters screen_stage inline instead (screen.py's
        # unique-non-failed-per-stage constraint means at most one such row).
        .where(source_screening_result.c.screen_stage == 1)
        .where(task_source_snapshot.c.task_id == task_id)
        .where(task_source_snapshot.c.origin == "acquired")
        .order_by(task_source_snapshot.c.task_source_snapshot_id)
    ).fetchall())


def _close_queued(
    connect: ConnectFactory, tss_ids: list[uuid.UUID], *, reason: str
) -> list[uuid.UUID]:
    """Mark the rows still ``queued`` among ``tss_ids`` as ``fetch_failed`` with ``reason``.

    One short committed transaction; the update is guarded on ``queued``, so a
    row a worker resolved in the meantime keeps its own outcome.

    Returns:
        The ids that were closed.
    """
    if not tss_ids:
        return []
    with connect() as c:
        return list(
            c.execute(
                task_source_snapshot.update()
                .where(task_source_snapshot.c.task_source_snapshot_id.in_(tss_ids))
                .where(task_source_snapshot.c.full_text_status == "queued")
                .values(
                    full_text_snapshot_id=None,
                    full_text_status="fetch_failed",
                    full_text_error=reason,
                )
                .returning(task_source_snapshot.c.task_source_snapshot_id)
            ).scalars()
        )


def _status_counts(conn: Connection, tss_ids: list[uuid.UUID]) -> dict[str, int]:
    """Count ``full_text_status`` over ``tss_ids`` (a fresh read: sees other commits)."""
    if not tss_ids:
        return {}
    rows = conn.execute(
        select(task_source_snapshot.c.full_text_status, func.count())
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(tss_ids))
        .group_by(task_source_snapshot.c.full_text_status)
    ).fetchall()
    return {status: int(n) for status, n in rows}


def ingest_full_text_sources(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: IngestFullTextContext,
    fetcher: DocumentFetcher,
    embedder: EmbeddingBackend | None = None,
    queue: "QueueClient | None" = None,
    connect: ConnectFactory | None = None,
    stage_deadline_s: float | None = None,
    parse_timeout: float = PARSE_TIMEOUT_SECONDS,
    thin_min: int = THIN_TEXT_MIN_CHARS,
    parse_fn: Callable[[bytes, str, int], dict[str, Any]] = parse_and_segment,
    poll_interval_s: float = STAGE_POLL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Ingest full text for a scope's screened-in acquired sources (task 057, P9).

    One path in both ingest modes. In its own committed transaction the stage
    sets every eligible document that is not yet ``ingested`` to ``queued`` (a
    row left ``queued`` by a run that died is simply queued again), then sends
    one message per document (the link row id and the run id, nothing else) to
    ``queue``. The documents are fetched, parsed and written by
    :func:`~policy_atlas.evidence_search.sourcing.ingest_document.ingest_document`,
    each in its own short transaction. Meanwhile the stage polls the statuses on
    ``conn`` (which sees the other connections' commits) and publishes the
    ``ingest`` progress ticks. A document still ``queued`` when the stage stops
    waiting becomes ``fetch_failed`` with reason ``not_ready``. The stage then
    embeds the chunks of every ingested document that lack embeddings, and
    returns the counts.

    The stage stops waiting when no document is ``queued`` any more, or at
    ``stage_deadline_s`` (queued mode). In process (``stage_deadline_s=None``)
    the local queue client returns only once every document has been handled,
    so there is nothing left to wait for.

    Args:
        conn: The component's connection; the eligible-set read, the polls and
            the embedding pass run on it, inside its transaction.
        task_id: Owning task.
        run_id: The run, recorded on each ingested link row.
        context: Scope-level input naming the evidence scope.
        fetcher: The ``DocumentFetcher`` seam; used only by the default queue
            client below.
        embedder: Optional embedding backend. Defaults to the deterministic stub.
        queue: Where the messages go. ``None`` (tests, direct calls) builds the
            inline local client: every document is handled on the caller's thread
            and on ``conn``, each in a savepoint.
        connect: Opens a short transaction that commits on exit (``engine.begin``).
            ``None`` uses a savepoint on ``conn``, to pair with the inline client.
        stage_deadline_s: Seconds from the first send after which documents still
            ``queued`` become ``not_ready``; ``None`` in process.
        parse_timeout: Hard per-document parse timeout (default client only).
        thin_min: Thin-text guard threshold (default client only).
        parse_fn: Parse callable (default client only; a test seam).
        poll_interval_s: Seconds between status polls.
        clock: Monotonic clock (a test seam for the deadline).
        sleep: Sleep function (a test seam for the deadline).

    Returns:
        Counts dict: ``eligible``, ``attempted`` (documents queued this run),
        ``already_ingested``, ``ingested``, ``already_in_store`` (the part of
        ``ingested`` whose parsed text was in the document store before this
        stage began, so it was linked, not parsed again), ``fetch_failed``,
        ``parse_failed``, ``by_reason``, ``by_route`` (this run's ingested
        documents by serving route), ``bytes_fetched`` (``None`` when the queue
        client cannot report it), ``wall_clock_s``, ``embed``. Invariant:
        ``eligible == ingested + already_ingested + fetch_failed + parse_failed``.
    """
    from policy_atlas.evidence_search.sourcing.ingest_queue import (
        LocalQueueClient,
        inline_connect,
        make_ingest_handler,
        new_message,
    )

    started_at = clock()
    stage_started = datetime.now(UTC)
    if connect is None:
        connect = inline_connect(conn)
    if queue is None:
        queue = LocalQueueClient(
            make_ingest_handler(
                fetcher, parse_fn=parse_fn, parse_timeout=parse_timeout, thin_min=thin_min
            ),
            connect,
            workers=0,
        )

    eligible_ids = [
        row.task_source_snapshot_id
        for row in _eligible_rows(conn, task_id=task_id, scope_id=context.scope_id)
    ]
    eligible_set = set(eligible_ids)

    # Queue every eligible row that is not yet ingested, committed BEFORE any send
    # (a worker that starts at once must find its row ``queued``). Rows left
    # ``queued`` by a run that died are among them: they are sent again.
    queued: list[uuid.UUID] = []
    orphans = 0
    if eligible_ids:
        with connect() as c:
            orphans = int(
                c.execute(
                    select(func.count())
                    .where(task_source_snapshot.c.task_source_snapshot_id.in_(eligible_ids))
                    .where(task_source_snapshot.c.full_text_status == "queued")
                ).scalar_one()
            )
            queued_set = set(
                c.execute(
                    task_source_snapshot.update()
                    .where(task_source_snapshot.c.task_source_snapshot_id.in_(eligible_ids))
                    .where(task_source_snapshot.c.full_text_status != "ingested")
                    .values(
                        full_text_snapshot_id=None,
                        full_text_status="queued",
                        full_text_error=None,
                    )
                    .returning(task_source_snapshot.c.task_source_snapshot_id)
                ).scalars()
            )
        queued = [tss_id for tss_id in eligible_ids if tss_id in queued_set]
    if orphans:
        log.warning("ingest.orphans_requeued", count=orphans)
    already_ingested = len(eligible_ids) - len(queued)
    total = len(eligible_ids)

    def publish(ingested_now: int) -> None:
        # ``fetched`` cannot be observed on this path (the worker fetches and
        # parses in one call); the web-api spec allows it to be null.
        publish_current_tick(
            stage="ingest",
            note=f"{ingested_now} of {total} read.",
            fetched=None,
            parsed=ingested_now,
            total=total,
        )

    # Send. The inline client runs every document on this thread and this
    # connection, so it is called directly; any other client is called on a
    # helper thread while this thread polls (the local thread-pool client
    # returns only when every document is done, so the ticks come from here).
    messages = [new_message(link_row_id=tss_id, run_id=run_id) for tss_id in queued]
    send_box: dict[str, Any] = {}

    def do_send() -> None:
        try:
            send_box["result"] = queue.send(messages)
        except BaseException as exc:  # re-raised on the stage's thread
            send_box["error"] = exc

    sender: threading.Thread | None = None
    if messages:
        if isinstance(queue, LocalQueueClient) and queue.inline:
            do_send()
        else:
            sender = threading.Thread(target=do_send, name="policy-atlas-ingest-send")
            sender.start()

    deadline = None if stage_deadline_s is None else clock() + stage_deadline_s
    send_failures_closed = False
    while True:
        if sender is not None:
            sender.join(timeout=poll_interval_s)
        send_done = sender is None or not sender.is_alive()
        if send_done and "error" in send_box:
            raise send_box["error"]
        send_result: SendResult | None = send_box.get("result")
        if send_done and not send_failures_closed:
            send_failures_closed = True
            if send_result is not None and send_result.failed:
                # A message the queue refused never reaches a worker: its row
                # is closed now rather than waiting for the deadline.
                closed = _close_queued(
                    connect, [uuid.UUID(i) for i in send_result.failed], reason="send_failed"
                )
                log.warning("ingest.send_failed", count=len(closed))
        counts_now = _status_counts(conn, eligible_ids)
        publish(counts_now.get("ingested", 0))
        if send_done and counts_now.get("queued", 0) == 0:
            break
        if deadline is None and send_done:
            break  # in process: nothing is left that could still finish a row
        if deadline is not None and clock() >= deadline:
            break
        if send_done:
            sleep(poll_interval_s)

    send_result = send_box.get("result")
    # Rows still ``queued`` now: past the deadline, or (in process) left by a
    # handler that never wrote. A late result cannot flip them back (the
    # function's write is guarded on ``queued``); its snapshot joins the store.
    not_ready = _close_queued(connect, queued, reason="not_ready")
    if not_ready:
        log.warning("ingest.not_ready", count=len(not_ready))

    # Final read of this run's rows, with the snapshot each ingested row links.
    rows = conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
            task_source_snapshot.c.full_text_snapshot_id,
            source_snapshot.c.created_at,
            source_snapshot.c.metadata,
        )
        .select_from(
            task_source_snapshot.outerjoin(
                source_snapshot,
                task_source_snapshot.c.full_text_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(eligible_ids))
    ).fetchall() if eligible_ids else []
    queued_set = set(queued)
    counts = {"ingested": 0, "already_in_store": 0, "fetch_failed": 0, "parse_failed": 0}
    by_reason: dict[str, int] = {}
    by_route: dict[str, int] = {}
    ingested_snapshot_ids: list[uuid.UUID] = []
    for row in rows:
        if row.full_text_snapshot_id is not None:
            ingested_snapshot_ids.append(row.full_text_snapshot_id)
        if row.task_source_snapshot_id not in queued_set:
            continue  # already ingested before this run
        status = row.full_text_status
        if status == "ingested":
            counts["ingested"] += 1
            if row.created_at is not None and row.created_at < stage_started:
                counts["already_in_store"] += 1
            route = (row.metadata or {}).get("source_kind") or "plain"
            by_route[route] = by_route.get(route, 0) + 1
        elif status in ("fetch_failed", "parse_failed"):
            counts[status] += 1
            reason = row.full_text_error
            by_reason[reason] = by_reason.get(reason, 0) + 1
        else:  # cannot happen: every queued row was closed above
            raise RuntimeError(f"ingest left a row in status {status!r}")
    assert eligible_set == {row.task_source_snapshot_id for row in rows}

    if embedder is None:
        embedder = StubEmbeddingBackend()
    embed_counts = embed_pending_chunks(
        conn,
        embedder=embedder,
        task_id=task_id,
        run_id=run_id,
        snapshot_ids=ingested_snapshot_ids,
    )

    summary = {
        "eligible": total,
        "attempted": len(queued),
        "already_ingested": already_ingested,
        **counts,
        "by_reason": by_reason,
        "by_route": by_route,
        "bytes_fetched": (
            sum(outcome.bytes_fetched for outcome in send_result.outcomes)
            if send_result is not None and send_result.outcomes is not None
            else (0 if not messages else None)
        ),
        "wall_clock_s": round(clock() - started_at, 2),
        "embed": embed_counts,
    }
    log.info("fulltext.summary", **summary)
    return summary
