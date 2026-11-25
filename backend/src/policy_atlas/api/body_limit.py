"""Refuse request bodies above a size limit, before any route or sign-in check reads them.

This is a plain ASGI middleware. ASGI (Asynchronous Server Gateway Interface) is the
interface between the web server (uvicorn) and the app: the server hands the app the
request body as a series of messages, and the app sends its reply back as messages.
Sitting between the two lets the limiter count the body without buffering it.
"""

from __future__ import annotations

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from policy_atlas.api.contract import ErrorBody, ErrorEnvelope

#: The largest body any request may send unless a row below allows more.
DEFAULT_LIMIT = 1_000_000

#: Routes that may send more: (method, anchored path pattern, limit in bytes).
#: The theory of change upload carries a 10 MB file as base64 text (at most
#: 14,000,000 characters) plus a file name and a short message.
LARGER_LIMITS: tuple[tuple[str, re.Pattern[str], int], ...] = (
    ("POST", re.compile(r"/api/v1/tasks/[0-9a-fA-F-]{32,36}/toc/uploads"), 15_000_000),
)


class _BodyTooLarge(Exception):
    """The body passed the limit after the reply had started; the server drops the line."""


def limit_for(method: str, path: str) -> int:
    """Return the largest body, in bytes, a request may send.

    Args:
        method: The HTTP method, upper case.
        path: The request path.

    Returns:
        The limit of the first matching row in ``LARGER_LIMITS``, else ``DEFAULT_LIMIT``.
    """
    for row_method, pattern, limit in LARGER_LIMITS:
        if method == row_method and pattern.fullmatch(path):
            return limit
    return DEFAULT_LIMIT


class BodyLimitMiddleware:
    """Reply 413 (payload too large) to a request whose body passes its limit.

    Two checks. A request that declares a ``Content-Length`` above the limit is
    refused at once, and the app behind the limiter is never called. Every body is
    also counted as it arrives, because a body can come in chunks with no
    ``Content-Length`` at all (or with one that lies). When the count passes the
    limit, the app is told the client has gone (an ``http.disconnect`` message), and
    anything it then tries to send is dropped. If no reply had started, the limiter
    sends the 413 itself. If one had, it sends nothing more and raises, so the server
    closes the connection rather than finish a cut-off reply.

    The 413 is written here, in the API's usual error shape, because the app's own
    error handlers sit inside this middleware and never see the request.

    Args:
        app: The ASGI app to protect.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Run one request through the limit; other connection types pass straight on."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = limit_for(scope["method"], scope["path"])
        if _declared_length(scope) > limit:
            await _too_large(scope, receive, send)
            return

        received = 0
        exceeded = False
        started = False

        async def counted_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal started
            if exceeded:
                return
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counted_receive, guarded_send)
        except Exception:
            # The app may fail on the cut-off body; that failure is the limit's doing.
            if not exceeded:
                raise
        if exceeded:
            if started:
                raise _BodyTooLarge
            await _too_large(scope, receive, send)


def _declared_length(scope: Scope) -> int:
    """Return the request's ``Content-Length``, or 0 when it has none or it is not a number.

    A missing or unreadable header is not trusted either way: the running count
    still applies to every byte that arrives.
    """
    for name, value in scope["headers"]:
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return 0
    return 0


async def _too_large(scope: Scope, receive: Receive, send: Send) -> None:
    """Send the 413 reply in the API's error envelope."""
    envelope = ErrorEnvelope(
        error=ErrorBody(code="payload_too_large", message="request body is too large")
    )
    response = JSONResponse(status_code=413, content=envelope.model_dump(exclude_none=True))
    await response(scope, receive, send)
