"""Live document fetcher — demo stand-in for the real 016 live fetcher.

Implements the ``DocumentFetcher`` seam (``policy_atlas.ingest_full_text``) with
real HTTP egress, so the live demo can fetch full text for screened-in sources
instead of replaying fixtures. This is intentionally minimal: no per-host
politeness/rate limiting, no SSRF policy (no private-IP/redirect-target
blocklist), no paywall ladder beyond the closed HTTP-status map — those are
pre-registered in docs/deferred.md for the real 016 slice.

ponytail: single shared client, no per-host concurrency cap, no SSRF guard —
this is a throwaway demo fetcher, not the hardened production seam.
"""

import concurrent.futures
import threading
from collections.abc import Callable

import httpx

from policy_atlas.ingest_full_text import FetchResult

_HTTP_STATUS_REASONS = {401: "paywall", 403: "paywall", 404: "not_found", 410: "not_found"}


def _classify_content_type(header_content_type: str | None, body: bytes) -> str:
    """Classify body content type by magic bytes first, headers second.

    Args:
        header_content_type: The response's ``Content-Type`` header value, if any.
        body: The downloaded document bytes.

    Returns:
        ``"application/pdf"`` | ``"text/html"`` | ``"text/plain"``.
    """
    if body.startswith(b"%PDF"):
        return "application/pdf"
    header_lower = (header_content_type or "").lower()
    sniff = body[:1000].lower()
    if (
        "text/html" in header_lower
        or b"text/html" in sniff
        or b"<html" in sniff
        or b"<!doctype html" in sniff
    ):
        return "text/html"
    if "application/pdf" in header_lower:
        return "application/pdf"
    return "text/plain"


class DemoLiveFetcher:
    """Fetches document bytes over real HTTP, with a shared cache.

    Attributes:
        mode: Always ``"live"``.
    """

    mode = "live"

    def __init__(
        self,
        max_concurrency: int = 10,
        timeout_s: float = 30.0,
        max_bytes: int = 25_000_000,
    ) -> None:
        """Construct the fetcher.

        Args:
            max_concurrency: Maximum parallel fetches during ``prefetch``.
            timeout_s: Per-request timeout in seconds.
            max_bytes: Byte cap enforced against both ``Content-Length`` and the
                downloaded body.
        """
        self._max_concurrency = max_concurrency
        self._max_bytes = max_bytes
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=timeout_s,
            headers={"User-Agent": "PolicyAtlas-demo/0.1 (research prototype)"},
        )
        self._cache: dict[str, FetchResult] = {}
        self._lock = threading.Lock()

    def prefetch(
        self,
        urls: list[str],
        on_progress: Callable[[int, int, int, int], None] | None = None,
    ) -> None:
        """Fetch a batch of URLs in parallel and populate the cache.

        Args:
            urls: URLs to fetch. Duplicates and already-cached URLs are skipped.
            on_progress: Optional callback invoked after each completed URL as
                ``on_progress(done_count, ok_count, failed_count, total)``.
        """
        with self._lock:
            pending = [url for url in dict.fromkeys(urls) if url not in self._cache]
        total = len(pending)
        if total == 0:
            return

        done_count = 0
        ok_count = 0
        failed_count = 0
        progress_lock = threading.Lock()

        def run_one(url: str) -> tuple[str, FetchResult]:
            return url, self._fetch_one(url)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_concurrency) as pool:
            futures = [pool.submit(run_one, url) for url in pending]
            for future in concurrent.futures.as_completed(futures):
                url, result = future.result()
                with self._lock:
                    self._cache[url] = result
                with progress_lock:
                    done_count += 1
                    if result.status == "ok":
                        ok_count += 1
                    else:
                        failed_count += 1
                    if on_progress is not None:
                        on_progress(done_count, ok_count, failed_count, total)

    def fetch(self, url: str) -> FetchResult:
        """Fetch one URL. Never raises for per-document outcomes.

        Args:
            url: Absolute http(s) URL to fetch.

        Returns:
            The cached result if present, else a freshly fetched (and cached)
            result.
        """
        with self._lock:
            cached = self._cache.get(url)
        if cached is not None:
            return cached
        result = self._fetch_one(url)
        with self._lock:
            self._cache[url] = result
        return result

    def _fetch_one(self, url: str) -> FetchResult:
        """Fetch one URL over HTTP. Never raises; maps every outcome to a result."""
        try:
            with self._client.stream("GET", url) as response:
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > self._max_bytes:
                            return FetchResult(status="error", error="too_large")
                    except ValueError:
                        pass  # malformed header — fall through to body-size enforcement

                if response.status_code >= 400:
                    reason = _HTTP_STATUS_REASONS.get(response.status_code, "not_found")
                    return FetchResult(status="error", error=reason)

                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._max_bytes:
                        return FetchResult(status="error", error="too_large")
                    chunks.append(chunk)
                body = b"".join(chunks)

            if not body:
                return FetchResult(status="error", error="empty")

            content_type = _classify_content_type(response.headers.get("Content-Type"), body)
            return FetchResult(status="ok", content_type=content_type, body=body)
        except httpx.TimeoutException:
            return FetchResult(status="error", error="timeout")
        except Exception:
            return FetchResult(status="error", error="not_found")
