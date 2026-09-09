"""Hardened live document fetcher for full-text ingestion."""

from __future__ import annotations

import http.cookiejar
import ipaddress
import select
import socket
import ssl
import threading
import time
from collections import deque
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpcore
import httpx
import structlog

from policy_atlas.core.liveness import publish_current_tick
from policy_atlas.evidence_search.sourcing.ingest_full_text import (
    DocumentFetcher,
    FetchResult,
    FixtureFetcher,
    _redact_url,
)

log = structlog.get_logger()

FETCH_TIMEOUT_S = 30.0
REDIRECT_HOP_CAP = 5
MAX_DOCUMENT_BYTES = 25_000_000
RETRY_BACKOFF_S = 2.0
FETCH_MAX_CONCURRENCY = 10
PER_HOST_MAX_CONCURRENCY = 2
PER_HOST_MIN_INTERVAL_S = 1.0
MAX_INFLIGHT_BYTES = 100_000_000
BYTE_BUDGET_WAIT_TIMEOUT_S = 300.0  # ponytail: see _account_bytes
PAYWALL_MARKERS = (
    "purchase this article",
    "institutional login",
    "access through your institution",
    "sign in to read",
    "subscribe to read",
    "rent this article",
    "get access",
    "log in via your institution",
)

USER_AGENT = "policy-atlas/0.1 (+research; contact via repo)"
_ALLOWED_SCHEMES = frozenset({"http", "https"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_RETRYABLE_STATUSES = frozenset({429, 500, 502, 503, 504})
_Resolver = Callable[[str, int], Sequence[Any]]
_Clock = Callable[[], float]
_Sleep = Callable[[float], None]
_SocketOption = (
    tuple[int, int, int]
    | tuple[int, int, bytes | bytearray]
    | tuple[int, int, None, int]
)


class _BlockedURL(RuntimeError):
    pass


@dataclass(frozen=True)
class _Address:
    family: socket.AddressFamily
    socktype: socket.SocketKind
    proto: int
    sockaddr: Any
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address


@dataclass
class _HostState:
    semaphore: threading.Semaphore
    lock: threading.Lock
    last_start_at: float | None = None


@dataclass
class _Redirect:
    url: str


@dataclass(frozen=True)
class _RetryableStatus:
    status_code: int


@dataclass
class _InflightRequest:
    condition: threading.Condition
    waiters: int = 1
    result: FetchResult | None = None


class _SocketStream(httpcore.NetworkStream):
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        self._sock.settimeout(timeout)
        return self._sock.recv(max_bytes)

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._sock.settimeout(timeout)
        self._sock.sendall(buffer)

    def close(self) -> None:
        self._sock.close()

    def start_tls(
        self,
        ssl_context: ssl.SSLContext,
        server_hostname: str | None = None,
        timeout: float | None = None,
    ) -> httpcore.NetworkStream:
        self._sock.settimeout(timeout)
        try:
            tls_sock = ssl_context.wrap_socket(self._sock, server_hostname=server_hostname)
        except Exception:
            self.close()
            raise
        return _SocketStream(tls_sock)

    def get_extra_info(self, info: str) -> Any:
        if info == "ssl_object" and isinstance(self._sock, ssl.SSLSocket):
            return self._sock._sslobj  # type: ignore[attr-defined]  # noqa: SLF001
        if info == "client_addr":
            return self._sock.getsockname()
        if info == "server_addr":
            return self._sock.getpeername()
        if info == "socket":
            return self._sock
        if info == "is_readable":
            readable, _, _ = select.select([self._sock], [], [], 0)
            return bool(readable)
        return None


class _PinnedIPNetworkBackend(httpcore.NetworkBackend):
    def __init__(self, resolver: _Resolver | None = None) -> None:
        self._resolver = resolver or _default_resolver

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[_SocketOption] | None = None,
    ) -> httpcore.NetworkStream:
        addresses = _resolve_and_validate(host, port, self._resolver)
        last_exc: OSError | None = None
        for address in addresses:
            try:
                return self._connect_address(
                    address,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except OSError as exc:
                last_exc = exc
        raise httpcore.ConnectError(str(last_exc) if last_exc is not None else "connect failed")

    def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: Iterable[_SocketOption] | None = None,
    ) -> httpcore.NetworkStream:
        raise httpcore.UnsupportedProtocol("unix sockets are not supported")

    def _connect_address(
        self,
        address: _Address,
        *,
        timeout: float | None,
        local_address: str | None,
        socket_options: Iterable[_SocketOption] | None,
    ) -> httpcore.NetworkStream:
        sock = socket.socket(address.family, address.socktype, address.proto)
        try:
            sock.settimeout(timeout)
            if local_address is not None:
                sock.bind((local_address, 0))
            for option in socket_options or ():
                sock.setsockopt(*option)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.connect(address.sockaddr)
        except TimeoutError as exc:
            sock.close()
            raise httpcore.ConnectTimeout(str(exc)) from exc
        except OSError:
            sock.close()
            raise
        return _SocketStream(sock)


class _CoreResponseStream(httpx.SyncByteStream):
    def __init__(self, stream: Iterable[bytes]) -> None:
        self._stream = stream

    def __iter__(self) -> Iterator[bytes]:
        yield from self._stream

    def close(self) -> None:
        close = getattr(self._stream, "close", None)
        if close is not None:
            cast(Callable[[], None], close)()


class _PinnedIPTransport(httpx.BaseTransport):
    def __init__(self, resolver: _Resolver | None = None) -> None:
        self._pool = httpcore.ConnectionPool(
            ssl_context=ssl.create_default_context(),
            max_connections=FETCH_MAX_CONCURRENCY,
            http1=True,
            http2=False,
            retries=0,
            network_backend=_PinnedIPNetworkBackend(resolver),
        )

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        assert isinstance(request.stream, httpx.SyncByteStream)
        core_request = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        core_response = self._pool.handle_request(core_request)
        assert isinstance(core_response.stream, Iterable)
        return httpx.Response(
            status_code=core_response.status,
            headers=core_response.headers,
            stream=_CoreResponseStream(core_response.stream),
            extensions=core_response.extensions,
        )

    def close(self) -> None:
        self._pool.close()


class LiveDocumentFetcher:
    """Live implementation of the full-text ``DocumentFetcher`` seam.

    Args:
        resolver: Optional ``getaddrinfo``-like resolver for tests. The default
            resolves with ``socket.getaddrinfo``.
        clock: Monotonic clock used for per-host politeness.
        sleep: Sleep function used for retry backoff and politeness waits.
        transport: Optional httpx transport seam for zero-egress tests. When
            omitted, a pooled httpcore transport with pinned-IP connects is used.
    """

    mode = "live"

    def __init__(
        self,
        *,
        resolver: _Resolver | None = None,
        clock: _Clock = time.monotonic,
        sleep: _Sleep = time.sleep,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._resolver = resolver or _default_resolver
        self._clock = clock
        self._sleep = sleep
        cookie_jar = http.cookiejar.CookieJar(
            policy=http.cookiejar.DefaultCookiePolicy(allowed_domains=())
        )
        self._client = httpx.Client(
            transport=transport if transport is not None else _PinnedIPTransport(self._resolver),
            timeout=httpx.Timeout(FETCH_TIMEOUT_S),
            follow_redirects=False,
            trust_env=False,
            headers={"User-Agent": USER_AGENT},
            cookies=cookie_jar,
        )
        self._global_semaphore = threading.Semaphore(FETCH_MAX_CONCURRENCY)
        self._hosts_lock = threading.Lock()
        self._hosts: dict[str, _HostState] = {}
        self._byte_condition = threading.Condition()
        self._inflight_bytes = 0
        self._body_leases: dict[int, deque[int]] = {}
        self._cache_lock = threading.Lock()
        self._error_cache: dict[str, FetchResult] = {}
        self._inflight: dict[str, _InflightRequest] = {}

    def fetch(self, url: str) -> FetchResult:
        """Fetch one document URL without raising for per-document outcomes.

        Args:
            url: Absolute HTTP(S) URL from provider metadata or a guarded
                redirect/discovery cascade.

        Returns:
            ``FetchResult(status="ok")`` with raw bytes and a sniffed content
            type, or ``FetchResult(status="error")`` with a reason code.
        """
        cache_key = _strip_fragment(url)
        publish_current_tick(stage="acquire", note="Fetching a source in full.")
        try:
            result = self._fetch_deduped(cache_key)
            note = (
                "Read a source in full."
                if result.status == "ok"
                else "A source could not be fetched — recorded."
            )
            publish_current_tick(
                stage="acquire",
                note=note,
            )
            return result
        except Exception as exc:
            log.warning(
                "fetch_live.unexpected",
                url=_redact_url(cache_key),
                exc_type=type(exc).__name__,
            )
            publish_current_tick(stage="acquire", note="A source could not be fetched — recorded.")
            return FetchResult(status="error", error="fetch_error")

    def release_body(self, n_bytes: int) -> None:
        """Release byte-budget accounting for a returned successful body.

        The ingest pipeline calls this after handing the body to the parser. A
        fixture fetcher intentionally has no equivalent method; callers should use
        duck typing.

        Args:
            n_bytes: Number of body bytes being released, normally
                ``len(FetchResult.body)``.

        Returns:
            None.
        """
        if n_bytes <= 0:
            return
        with self._byte_condition:
            leases = self._body_leases.get(n_bytes)
            if not leases:
                return
            remaining = leases[0] - 1
            if remaining > 0:
                leases[0] = remaining
                return
            leases.popleft()
            if not leases:
                del self._body_leases[n_bytes]
            self._release_accounted_bytes_locked(n_bytes)

    def close(self) -> None:
        """Close the pooled HTTP client.

        Returns:
            None.
        """
        self._client.close()

    def _fetch_deduped(self, url: str) -> FetchResult:
        owner = False
        with self._cache_lock:
            cached = self._error_cache.get(url)
            if cached is not None:
                log.info("fetch_live.error_cache_hit", url=_redact_url(url), error=cached.error)
                return _clone_fetch_result(cached)
            inflight = self._inflight.get(url)
            if inflight is not None:
                inflight.waiters += 1
                while inflight.result is None:
                    inflight.condition.wait()
                return _clone_fetch_result(inflight.result)
            inflight = _InflightRequest(condition=threading.Condition(self._cache_lock))
            self._inflight[url] = inflight
            owner = True

        if not owner:
            raise RuntimeError("unreachable inflight state")

        result = self._fetch_uncached(url)
        with self._cache_lock:
            if result.status == "ok" and result.body is not None:
                self._register_body_lease(len(result.body), inflight.waiters)
            if result.status == "error":
                self._error_cache[url] = _clone_fetch_result(result)
            inflight.result = result
            del self._inflight[url]
            inflight.condition.notify_all()
        return result

    def _fetch_uncached(self, url: str) -> FetchResult:
        current_url = url
        redirects_followed = 0
        while True:
            outcome = self._request_with_retry(current_url)
            if isinstance(outcome, FetchResult):
                return outcome
            if redirects_followed >= REDIRECT_HOP_CAP:
                log.warning("fetch_live.redirect_hop_cap", url=_redact_url(outcome.url))
                return FetchResult(status="error", error="blocked")
            current_url = outcome.url
            redirects_followed += 1

    def _request_with_retry(self, url: str) -> FetchResult | _Redirect:
        attempts = 0
        while True:
            try:
                outcome = self._attempt_request(url)
            except _BlockedURL:
                log.warning("fetch_live.blocked", url=_redact_url(url))
                return FetchResult(status="error", error="blocked")
            except Exception as exc:
                if _unwraps_blocked_url(exc):
                    # httpcore/httpx wrap a connect-phase guard failure (the
                    # network backend's own TOCTOU re-check) in their own
                    # ConnectError; the original _BlockedURL only survives on
                    # the __cause__/__context__ chain (016 review stack).
                    log.warning("fetch_live.blocked", url=_redact_url(url))
                    return FetchResult(status="error", error="blocked")
                if _is_timeout_error(exc):
                    if attempts < 1:
                        log.warning("fetch_live.retry", url=_redact_url(url), reason="timeout")
                        self._sleep(RETRY_BACKOFF_S)
                        attempts += 1
                        continue
                    log.warning("fetch_live.timeout", url=_redact_url(url))
                    return FetchResult(status="error", error="timeout")
                log.warning(
                    "fetch_live.fetch_error",
                    url=_redact_url(url),
                    exc_type=type(exc).__name__,
                )
                return FetchResult(status="error", error="fetch_error")

            if isinstance(outcome, _RetryableStatus):
                if attempts < 1:
                    log.warning(
                        "fetch_live.retry",
                        url=_redact_url(url),
                        status_code=outcome.status_code,
                    )
                    self._sleep(RETRY_BACKOFF_S)
                    attempts += 1
                    continue
                log.warning(
                    "fetch_live.retry_exhausted",
                    url=_redact_url(url),
                    status_code=outcome.status_code,
                )
                return FetchResult(status="error", error="fetch_error")
            return outcome

    def _attempt_request(self, url: str) -> FetchResult | _Redirect | _RetryableStatus:
        guarded = _guard_url(url, self._resolver)
        host = _host_from_guarded_url(guarded)
        with self._global_semaphore, self._host_slot(host):
            log.info("fetch_live.request", url=_redact_url(guarded))
            with self._client.stream("GET", guarded) as response:
                return self._response_outcome(guarded, response)

    def _host_slot(self, host: str) -> _HostSlot:
        return _HostSlot(self._host_state(host), self._clock, self._sleep)

    def _host_state(self, host: str) -> _HostState:
        with self._hosts_lock:
            state = self._hosts.get(host)
            if state is None:
                state = _HostState(
                    semaphore=threading.Semaphore(PER_HOST_MAX_CONCURRENCY),
                    lock=threading.Lock(),
                )
                self._hosts[host] = state
            return state

    def _response_outcome(
        self, url: str, response: httpx.Response
    ) -> FetchResult | _Redirect | _RetryableStatus:
        status_code = response.status_code
        if status_code in _REDIRECT_STATUSES:
            redirect_url = _redirect_url(url, response.headers.get("location"))
            if redirect_url is None:
                return FetchResult(status="error", error="fetch_error")
            return _Redirect(redirect_url)
        if status_code in _RETRYABLE_STATUSES:
            return _RetryableStatus(status_code)
        if status_code in {401, 402}:
            return FetchResult(status="error", error="paywall")
        if status_code == 403:
            body_result = self._read_capped_body(response)
            if isinstance(body_result, FetchResult):
                return body_result
            body = body_result
            try:
                error = "paywall" if _has_paywall_marker(body) else "blocked_by_host"
                return FetchResult(status="error", error=error)
            finally:
                self._release_accounted_bytes(len(body))
        if status_code in {404, 410} or 400 <= status_code < 500:
            return FetchResult(status="error", error="not_found")
        if status_code != 200:
            return FetchResult(status="error", error="fetch_error")

        body_result = self._read_capped_body(response)
        if isinstance(body_result, FetchResult):
            return body_result
        body = body_result
        if not body:
            return FetchResult(status="error", error="empty")
        content_type = _classify_content(response.headers.get("content-type"), body)
        if content_type == "text/html" and _has_paywall_marker(body):
            self._release_accounted_bytes(len(body))
            return FetchResult(status="error", error="paywall")
        return FetchResult(status="ok", content_type=content_type, body=body)

    def _read_capped_body(self, response: httpx.Response) -> bytes | FetchResult:
        content_length = response.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_DOCUMENT_BYTES:
                    return FetchResult(status="error", error="too_large")
            except ValueError:
                pass

        # Reserve the full document cap up-front rather than accounting chunk by
        # chunk: a stream that blocks on the byte budget mid-download while
        # already holding accounted bytes can deadlock the whole pool (every
        # stream waiting on releases only other streams can produce). Blocking
        # only here — while this stream holds nothing — makes the budget
        # deadlock-impossible by construction, keeps the strict MAX_INFLIGHT
        # bound, and never trusts Content-Length. The reservation shrinks to the
        # actual body size on completion (the part release_body later frees).
        self._account_bytes(MAX_DOCUMENT_BYTES)
        body = bytearray()
        try:
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                if len(body) + len(chunk) > MAX_DOCUMENT_BYTES:
                    self._release_accounted_bytes(MAX_DOCUMENT_BYTES)
                    return FetchResult(status="error", error="too_large")
                body.extend(chunk)
        except Exception:
            self._release_accounted_bytes(MAX_DOCUMENT_BYTES)
            raise
        self._release_accounted_bytes(MAX_DOCUMENT_BYTES - len(body))
        return bytes(body)

    def _account_bytes(self, n_bytes: int) -> None:
        if n_bytes <= 0:
            return
        with self._byte_condition:
            deadline = time.monotonic() + BYTE_BUDGET_WAIT_TIMEOUT_S
            while self._inflight_bytes + n_bytes > MAX_INFLIGHT_BYTES:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not self._byte_condition.wait(timeout=remaining):
                    # ponytail: converts a lease-accounting leak from a silent hang
                    # into a loud failure; the budget can never legitimately stay
                    # full this long.
                    raise RuntimeError(
                        f"byte budget wedged after {BYTE_BUDGET_WAIT_TIMEOUT_S:.0f}s: "
                        f"_inflight_bytes={self._inflight_bytes}, requested={n_bytes}"
                    )
            self._inflight_bytes += n_bytes

    def _release_accounted_bytes(self, n_bytes: int) -> None:
        if n_bytes <= 0:
            return
        with self._byte_condition:
            self._release_accounted_bytes_locked(n_bytes)

    def _release_accounted_bytes_locked(self, n_bytes: int) -> None:
        self._inflight_bytes = max(0, self._inflight_bytes - n_bytes)
        self._byte_condition.notify_all()

    def _register_body_lease(self, n_bytes: int, releases_required: int) -> None:
        if n_bytes <= 0:
            return
        with self._byte_condition:
            self._body_leases.setdefault(n_bytes, deque()).append(max(1, releases_required))


class _HostSlot:
    def __init__(self, state: _HostState, clock: _Clock, sleep: _Sleep) -> None:
        self._state = state
        self._clock = clock
        self._sleep = sleep

    def __enter__(self) -> None:
        self._state.semaphore.acquire()
        with self._state.lock:
            now = self._clock()
            if self._state.last_start_at is not None:
                wait_s = PER_HOST_MIN_INTERVAL_S - (now - self._state.last_start_at)
                if wait_s > 0:
                    self._sleep(wait_s)
                    now = self._clock()
            self._state.last_start_at = now

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        self._state.semaphore.release()


def _default_resolver(host: str, port: int) -> Sequence[Any]:
    return socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)


def _strip_fragment(url: str) -> str:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def _guard_url(url: str, resolver: _Resolver) -> str:
    stripped = _strip_fragment(url)
    try:
        parsed = urlsplit(stripped)
        port = parsed.port
    except ValueError as exc:
        raise _BlockedURL(str(exc)) from exc
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise _BlockedURL("unsupported scheme")
    if parsed.username is not None or parsed.password is not None:
        raise _BlockedURL("userinfo not allowed")
    if parsed.hostname is None:
        raise _BlockedURL("missing host")
    _resolve_and_validate(
        parsed.hostname,
        port if port is not None else _default_port(parsed.scheme),
        resolver,
    )
    return stripped


def _resolve_and_validate(host: str, port: int, resolver: _Resolver) -> list[_Address]:
    answers = resolver(host, port)
    addresses: list[_Address] = []
    for family, socktype, proto, _canonname, sockaddr in answers:
        raw_ip = sockaddr[0]
        ip = ipaddress.ip_address(raw_ip)
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        if _is_refused_ip(ip):
            raise _BlockedURL("refused address class")
        addresses.append(
            _Address(
                family=socket.AddressFamily(family),
                socktype=socket.SocketKind(socktype),
                proto=int(proto),
                sockaddr=sockaddr,
                ip=ip,
            )
        )
    if not addresses:
        raise socket.gaierror("no DNS answers")
    return addresses


def _is_refused_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def _default_port(scheme: str) -> int:
    return 443 if scheme.lower() == "https" else 80


def _host_from_guarded_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.hostname is None:
        raise _BlockedURL("missing host")
    return parsed.hostname.lower()


def _redirect_url(base_url: str, location: str | None) -> str | None:
    if location is None or not location.strip():
        return None
    try:
        joined = urljoin(base_url, location.strip())
        parsed = urlsplit(joined)
        _ = parsed.port
        if not parsed.scheme or not parsed.netloc:
            return None
    except ValueError:
        return None
    return _strip_fragment(joined)


def _classify_content(header_content_type: str | None, body: bytes) -> str:
    if body.startswith(b"%PDF"):
        return "application/pdf"
    base_header = (header_content_type or "").split(";", 1)[0].strip().lower()
    prefix = body[:512].lstrip().lower()
    if base_header == "text/html" or prefix.startswith((b"<html", b"<!doctype html")):
        return "text/html"
    return "text/plain"


def _has_paywall_marker(body: bytes) -> bool:
    head = body[:5000].decode("utf-8", errors="replace").lower()
    return any(marker in head for marker in PAYWALL_MARKERS)


def _unwraps_blocked_url(exc: BaseException) -> bool:
    """True if ``exc`` or anything on its cause/context chain is a ``_BlockedURL``."""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        if isinstance(current, _BlockedURL):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def _is_timeout_error(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            TimeoutError,
            httpx.TimeoutException,
            httpcore.TimeoutException,
        ),
    )


def _clone_fetch_result(result: FetchResult) -> FetchResult:
    return FetchResult(
        status=result.status,
        content_type=result.content_type,
        body=result.body,
        error=result.error,
    )


def select_document_fetcher(live: bool) -> DocumentFetcher:
    """Select the full-text fetcher for the skeleton entrypoint.

    Args:
        live: Whether the operator selected live mode via the skeleton's single
            live flag.

    Returns:
        ``LiveDocumentFetcher`` in live mode, otherwise ``FixtureFetcher``.
    """
    if live:
        fetcher = LiveDocumentFetcher()
        assert fetcher.mode == "live"
        return fetcher
    return FixtureFetcher()
