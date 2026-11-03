"""Zero-egress tests for the hardened live document fetcher."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import httpx
import pytest
from structlog.testing import capture_logs

from policy_atlas.evidence_search.sourcing import fetch_live
from policy_atlas.evidence_search.sourcing.fetch_live import (
    MAX_DOCUMENT_BYTES,
    MAX_INFLIGHT_BYTES,
    PAYWALL_MARKERS,
    REDIRECT_HOP_CAP,
    RETRY_BACKOFF_S,
    LiveDocumentFetcher,
    _BlockedURL,
    _PinnedIPNetworkBackend,
)
from policy_atlas.evidence_search.sourcing.ingest_full_text import _redact_url

PUBLIC_IP = "93.184.216.34"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _addrinfo(ip: str, port: int) -> tuple[int, int, int, str, tuple[Any, ...]]:
    if ":" in ip:
        return (socket.AF_INET6, socket.SOCK_STREAM, 6, "", (ip, port, 0, 0))
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))


def _resolver_for(
    host_ips: Mapping[str, Sequence[str]] | None = None,
) -> Callable[[str, int], Sequence[Any]]:
    mapping = {host.lower(): tuple(ips) for host, ips in (host_ips or {}).items()}

    def resolver(host: str, port: int) -> Sequence[Any]:
        ips = mapping.get(host.lower(), (PUBLIC_IP,))
        return [_addrinfo(ip, port) for ip in ips]

    return resolver


def _fetcher(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    resolver: Callable[[str, int], Sequence[Any]] | None = None,
    clock: FakeClock | None = None,
) -> tuple[LiveDocumentFetcher, list[httpx.Request], FakeClock]:
    requests: list[httpx.Request] = []
    fake_clock = clock or FakeClock()

    def recording_handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    return (
        LiveDocumentFetcher(
            resolver=resolver or _resolver_for(),
            clock=fake_clock.clock,
            sleep=fake_clock.sleep,
            transport=httpx.MockTransport(recording_handler),
        ),
        requests,
        fake_clock,
    )


def _ok_response(
    body: bytes = b"body",
    *,
    content_type: str = "text/plain",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    merged = {"content-type": content_type}
    if headers is not None:
        merged.update(headers)
    return httpx.Response(200, headers=merged, content=body)


@pytest.mark.parametrize("url", ["ftp://example.com/doc.pdf", "file:///etc/passwd"])
def test_scheme_refusal_blocks_without_transport(url: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    fetcher, _, _ = _fetcher(handler)

    result = fetcher.fetch(url)

    assert result.status == "error"
    assert result.error == "blocked"


def test_userinfo_refusal_blocks_without_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    fetcher, _, _ = _fetcher(handler)

    result = fetcher.fetch("https://user:pass@example.com/doc.pdf")

    assert result.status == "error"
    assert result.error == "blocked"


@pytest.mark.parametrize(
    "ip",
    [
        "10.0.0.1",
        "127.0.0.1",
        "169.254.169.254",
        "224.0.0.1",
        "240.0.0.1",
        "0.0.0.0",
        "::ffff:127.0.0.1",
        "100.64.0.1",  # CGNAT (RFC 6598) — not previously private/reserved-flagged
        "::ffff:100.64.0.1",
    ],
)
def test_refused_ip_classes_block(ip: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    fetcher, _, _ = _fetcher(handler, resolver=_resolver_for({"example.com": [ip]}))

    result = fetcher.fetch("https://example.com/doc.pdf")

    assert result.status == "error"
    assert result.error == "blocked"


def test_public_ip_still_allowed() -> None:
    """The ``is_global`` tightening (016 review stack) must not refuse ordinary
    public addresses — the allowed-case complement to ``test_refused_ip_classes_block``."""
    fetcher, requests, _ = _fetcher(
        lambda request: _ok_response(b"ok"),
        resolver=_resolver_for({"example.com": [PUBLIC_IP]}),
    )

    result = fetcher.fetch("https://example.com/doc.pdf")

    assert result.status == "ok"
    assert len(requests) == 1
    fetcher.release_body(len(result.body or b""))


def test_mixed_good_and_bad_answer_set_blocks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("transport must not be called")

    fetcher, _, _ = _fetcher(
        handler,
        resolver=_resolver_for({"example.com": [PUBLIC_IP, "127.0.0.1"]}),
    )

    result = fetcher.fetch("https://example.com/doc.pdf")

    assert result.status == "error"
    assert result.error == "blocked"


def test_redirect_to_private_host_blocks_at_hop() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://private.example/secret"})

    fetcher, requests, _ = _fetcher(
        handler,
        resolver=_resolver_for({
            "public.example": [PUBLIC_IP],
            "private.example": ["10.0.0.1"],
        }),
    )

    result = fetcher.fetch("https://public.example/doc")

    assert result.status == "error"
    assert result.error == "blocked"
    assert [request.url.host for request in requests] == ["public.example"]


@pytest.mark.parametrize("headers", [{}, {"location": "http://example.com:bad/doc"}])
def test_redirect_missing_or_unparseable_location_returns_fetch_error(
    headers: dict[str, str],
) -> None:
    fetcher, requests, _ = _fetcher(lambda request: httpx.Response(302, headers=headers))

    result = fetcher.fetch("https://example.com/doc")

    assert result.status == "error"
    assert result.error == "fetch_error"
    assert len(requests) == 1


def test_redirect_hop_cap_exceeded_blocks() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        current = int(request.url.path.rsplit("/", 1)[-1])
        return httpx.Response(302, headers={"location": f"/hop/{current + 1}"})

    fetcher, requests, _ = _fetcher(handler)

    result = fetcher.fetch("https://example.com/hop/0")

    assert result.status == "error"
    assert result.error == "blocked"
    assert len(requests) == REDIRECT_HOP_CAP + 1


def test_content_length_over_cap_returns_too_large() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-length": str(MAX_DOCUMENT_BYTES + 1)})

    fetcher, _, _ = _fetcher(handler)

    result = fetcher.fetch("https://example.com/huge.pdf")

    assert result.status == "error"
    assert result.error == "too_large"


def test_streamed_body_over_cap_returns_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fetch_live, "MAX_DOCUMENT_BYTES", 5)

    fetcher, _, _ = _fetcher(lambda request: _ok_response(b"123456"))

    result = fetcher.fetch("https://example.com/stream")

    assert result.status == "error"
    assert result.error == "too_large"
    assert fetcher._inflight_bytes == 0


@pytest.mark.parametrize(
    ("body", "header", "expected"),
    [
        (b"%PDF-1.7\nbytes", "application/octet-stream", "application/pdf"),
        (b"<!doctype html><html><p>ok</p>", "application/pdf", "text/html"),
        (b"plain words", "application/octet-stream", "text/plain"),
    ],
)
def test_magic_byte_content_classification(body: bytes, header: str, expected: str) -> None:
    fetcher, _, _ = _fetcher(lambda request: _ok_response(body, content_type=header))

    result = fetcher.fetch("https://example.com/doc")

    assert result.status == "ok"
    assert result.content_type == expected
    assert result.body == body
    fetcher.release_body(len(body))


@pytest.mark.parametrize(
    ("status_code", "body", "expected"),
    [
        (401, b"", "paywall"),
        (402, b"", "paywall"),
        (403, f"<html>{PAYWALL_MARKERS[0]}</html>".encode(), "paywall"),
        (403, b"Forbidden", "blocked_by_host"),
        (404, b"", "not_found"),
        (451, b"", "not_found"),
    ],
)
def test_access_failure_ladder_statuses(
    status_code: int, body: bytes, expected: str
) -> None:
    fetcher, _, _ = _fetcher(
        lambda request: httpx.Response(
            status_code, headers={"content-type": "text/html"}, content=body
        )
    )

    result = fetcher.fetch("https://example.com/doc")

    assert result.status == "error"
    assert result.error == expected


def test_200_html_paywall_marker_returns_paywall() -> None:
    body = f"<html>Please {PAYWALL_MARKERS[4]}</html>".encode()
    fetcher, _, _ = _fetcher(lambda request: _ok_response(body, content_type="text/html"))

    result = fetcher.fetch("https://example.com/doc")

    assert result.status == "error"
    assert result.error == "paywall"
    assert fetcher._inflight_bytes == 0


def test_200_empty_body_returns_empty() -> None:
    fetcher, _, _ = _fetcher(lambda request: _ok_response(b""))

    result = fetcher.fetch("https://example.com/empty")

    assert result.status == "error"
    assert result.error == "empty"


def test_retry_429_then_200_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429)
        return _ok_response(b"ok")

    fetcher, _, clock = _fetcher(handler)

    result = fetcher.fetch("https://example.com/retry")

    assert result.status == "ok"
    assert result.body == b"ok"
    assert calls == 2
    assert clock.sleeps == [RETRY_BACKOFF_S]
    fetcher.release_body(2)


def test_retry_503_twice_returns_fetch_error() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    fetcher, _, clock = _fetcher(handler)

    result = fetcher.fetch("https://example.com/retry")

    assert result.status == "error"
    assert result.error == "fetch_error"
    assert calls == 2
    assert clock.sleeps == [RETRY_BACKOFF_S]


def test_timeout_retried_then_timeout() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timed out", request=request)

    fetcher, _, clock = _fetcher(handler)

    result = fetcher.fetch("https://example.com/timeout")

    assert result.status == "error"
    assert result.error == "timeout"
    assert calls == 2
    assert clock.sleeps == [RETRY_BACKOFF_S]


def test_wrapped_blocked_url_classified_as_blocked() -> None:
    """016 review stack: httpcore/httpx wrap a connect-phase guard failure (the
    network backend's own TOCTOU re-check) in their own ``ConnectError`` — the
    original ``_BlockedURL`` survives only on the ``__cause__`` chain, and must
    still classify as ``blocked``, never the generic ``fetch_error``."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom") from _BlockedURL("refused address class")

    fetcher, _, _ = _fetcher(handler)

    result = fetcher.fetch("https://example.com/doc.pdf")

    assert result.status == "error"
    assert result.error == "blocked"


def test_politeness_spaces_second_request_to_same_host() -> None:
    fetcher, _, clock = _fetcher(lambda request: _ok_response(b"x"))

    first = fetcher.fetch("https://example.com/one")
    fetcher.release_body(len(first.body or b""))
    second = fetcher.fetch("https://example.com/two")
    fetcher.release_body(len(second.body or b""))

    assert first.status == "ok"
    assert second.status == "ok"
    assert clock.sleeps == [1.0]


def test_cookie_and_authorization_headers_never_ride_requests() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/one":
            return _ok_response(b"one", headers={"set-cookie": "sid=SECRET; Path=/"})
        return _ok_response(b"two")

    fetcher, requests, _ = _fetcher(handler)

    first = fetcher.fetch("https://example.com/one")
    fetcher.release_body(len(first.body or b""))
    second = fetcher.fetch("https://example.com/two")
    fetcher.release_body(len(second.body or b""))

    assert first.status == "ok"
    assert second.status == "ok"
    assert [request.headers.get("user-agent") for request in requests] == [
        "policy-atlas/0.1 (+research; contact via repo)",
        "policy-atlas/0.1 (+research; contact via repo)",
    ]
    assert all("authorization" not in request.headers for request in requests)
    assert all("cookie" not in request.headers for request in requests)
    assert list(fetcher._client.cookies.jar) == []


def test_redact_url_and_logs_drop_query_strings() -> None:
    assert (
        _redact_url("https://user:pass@example.com/path/doc.pdf?token=SECRET#frag")
        == "https://example.com/path/doc.pdf"
    )
    fetcher, _, _ = _fetcher(lambda request: _ok_response(b"ok"))

    with capture_logs() as logs:
        result = fetcher.fetch("https://example.com/path/doc.pdf?token=SECRET")

    assert result.status == "ok"
    fetcher.release_body(len(result.body or b""))
    rendered = repr(logs)
    assert "SECRET" not in rendered
    assert "?token" not in rendered
    assert "https://example.com/path/doc.pdf" in rendered


def test_error_cache_hit_does_not_rehit_transport() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    fetcher, _, _ = _fetcher(handler)

    first = fetcher.fetch("https://example.com/missing")
    second = fetcher.fetch("https://example.com/missing")

    assert first.error == "not_found"
    assert second.error == "not_found"
    assert calls == 1


def test_concurrent_duplicate_success_coalesces_transport() -> None:
    body = b"shared body"
    calls = 0
    calls_lock = threading.Lock()
    handler_entered = threading.Event()
    release_handler = threading.Event()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        with calls_lock:
            calls += 1
        handler_entered.set()
        assert release_handler.wait(2.0)
        return _ok_response(body)

    fetcher, _, _ = _fetcher(handler)
    results: list[Any] = []
    errors: list[BaseException] = []

    def run_fetch() -> None:
        try:
            results.append(fetcher.fetch("https://example.com/shared"))
        except BaseException as exc:  # pragma: no cover - surfaced by assertion below
            errors.append(exc)

    first = threading.Thread(target=run_fetch)
    second = threading.Thread(target=run_fetch)
    first.start()
    assert handler_entered.wait(2.0)
    second.start()
    release_handler.set()
    first.join(2.0)
    second.join(2.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert calls == 1
    assert [result.status for result in results] == ["ok", "ok"]
    assert fetcher._inflight_bytes == len(body)
    fetcher.release_body(len(body))
    assert fetcher._inflight_bytes == len(body)
    fetcher.release_body(len(body))
    assert fetcher._inflight_bytes == 0


def test_inflight_byte_accounting_until_release_body() -> None:
    body = b"accounted"
    fetcher, _, _ = _fetcher(lambda request: _ok_response(body))

    result = fetcher.fetch("https://example.com/body")

    assert result.status == "ok"
    assert fetcher._inflight_bytes == len(body)
    fetcher.release_body(len(body))
    assert fetcher._inflight_bytes == 0


def test_network_backend_classifies_before_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_getaddrinfo(host: str, port: int, **kwargs: Any) -> Sequence[Any]:
        return [_addrinfo("::ffff:127.0.0.1", port)]

    def fake_socket(*args: Any, **kwargs: Any) -> socket.socket:
        raise AssertionError("socket must not be opened for a blocked address")

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(socket, "socket", fake_socket)

    backend = _PinnedIPNetworkBackend()

    with pytest.raises(_BlockedURL):
        backend.connect_tcp("example.com", 443)


def test_account_bytes_wedged_budget_raises_loudly(monkeypatch: pytest.MonkeyPatch) -> None:
    """016 review stack (ponytail): a leaked byte-budget lease that never gets
    released must fail loudly with a bounded wait, never hang the pool forever."""
    monkeypatch.setattr(fetch_live, "BYTE_BUDGET_WAIT_TIMEOUT_S", 0.05)
    fetcher, _, _ = _fetcher(lambda request: _ok_response(b"x"))
    fetcher._inflight_bytes = MAX_INFLIGHT_BYTES  # simulate a wedged/leaked lease

    with pytest.raises(RuntimeError, match="wedged"):
        fetcher._account_bytes(1)


# --- Retry-After on 429 and 503 (task 057, N2) ---


def _status_then_ok(
    status: int, headers: dict[str, str]
) -> Callable[[httpx.Request], httpx.Response]:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status, headers=headers)
        return _ok_response(b"ok")

    return handler


@pytest.mark.parametrize(
    ("status", "retry_after", "expected_wait"),
    [
        (429, "7", 7.0),  # seconds, honoured
        (503, "7", 7.0),
        (429, "90", fetch_live.RETRY_AFTER_CAP_S),  # capped at 30 s
        (429, "soon", RETRY_BACKOFF_S),  # malformed: today's wait
        (503, "-3", RETRY_BACKOFF_S),  # not a whole number of seconds: malformed
        (500, "7", RETRY_BACKOFF_S),  # only 429 and 503 carry a usable Retry-After
    ],
)
def test_retry_after_is_honoured_on_429_and_503(
    status: int, retry_after: str, expected_wait: float
) -> None:
    fetcher, requests, clock = _fetcher(_status_then_ok(status, {"retry-after": retry_after}))

    result = fetcher.fetch("https://example.com/busy")

    assert result.status == "ok"
    assert len(requests) == 2
    assert clock.sleeps == [expected_wait]
    fetcher.release_body(2)


def test_retry_after_http_date_header() -> None:
    from datetime import UTC, datetime, timedelta
    from email.utils import format_datetime

    when = format_datetime(datetime.now(UTC) + timedelta(seconds=12), usegmt=True)
    fetcher, _, clock = _fetcher(_status_then_ok(429, {"retry-after": when}))

    assert fetcher.fetch("https://example.com/busy").status == "ok"
    assert len(clock.sleeps) == 1 and 9.0 <= clock.sleeps[0] <= 12.0
    fetcher.release_body(2)


def test_retry_after_seconds_parser() -> None:
    from datetime import UTC, datetime

    now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC)
    parse = fetch_live.retry_after_seconds
    assert parse("7", now=now) == 7.0
    assert parse(" 7 ", now=now) == 7.0
    assert parse("0", now=now) == 0.0
    assert parse("90", now=now) == 30.0
    assert parse("Tue, 03 Nov 2026 12:00:20 GMT", now=now) == 20.0
    assert parse("Tue, 03 Nov 2026 12:05:00 GMT", now=now) == 30.0  # capped
    assert parse("Tue, 03 Nov 2026 11:59:00 GMT", now=now) == 0.0  # in the past
    assert parse(None, now=now) is None
    assert parse("", now=now) is None
    assert parse("7.5", now=now) is None
    assert parse("not a date", now=now) is None


def test_retry_wait_past_the_deadline_is_not_started() -> None:
    """A wait that would end inside the deadline's margin is given up: one
    request, no sleep (the per-document deadline, task 057 D4)."""
    from policy_atlas.evidence_search.sourcing.ingest_full_text import FETCH_DEADLINE

    fetcher, requests, clock = _fetcher(_status_then_ok(429, {"retry-after": "7"}))
    token = FETCH_DEADLINE.set(clock.now + 10.0)  # 7 s wait > 10 - 5 s margin
    try:
        result = fetcher.fetch("https://example.com/busy")
    finally:
        FETCH_DEADLINE.reset(token)

    assert result.status == "error"
    assert len(requests) == 1
    assert clock.sleeps == []
