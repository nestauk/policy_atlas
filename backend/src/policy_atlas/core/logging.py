"""Structured logging setup — mandatory from first scaffold slice.

Call configure_logging() at every entrypoint before any log call.
Never use stdlib logging or print statements; all calls go through structlog.
"""

import logging
import os
import re
from urllib.parse import unquote

import structlog

UNSUBSCRIBE_PATH = "/api/v1/unsubscribe"
RESUBSCRIBE_PATH = "/api/v1/resubscribe"
_TOKEN_ENDINGS = ("/unsubscribe", "/resubscribe")


def configure_logging() -> None:
    """JSON in deployed environments (LOG_FORMAT=json); console-pretty locally.

    Also adds :func:`drop_token_from_access_log` to uvicorn's access log, on
    both hosts: the ops host answers 404 to the unsubscribe paths but would
    still log the line.
    """
    install_access_log_filter()
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if os.getenv("LOG_FORMAT") == "json":
        # Structured traceback (a JSON-serializable list of frames) so
        # log.error(..., exc_info=True) renders the exception in JSON output.
        # show_locals=False: the default dumps every frame's local variables,
        # which carried user text and secret prefixes into CloudWatch.
        processors.append(
            structlog.processors.ExceptionRenderer(
                structlog.tracebacks.ExceptionDictTransformer(show_locals=False)
            )
        )
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Formats exc_info into an "exception" string field before the console
        # renderer, so log.error(..., exc_info=True) renders the traceback.
        processors.append(structlog.processors.format_exc_info)
        processors.append(structlog.dev.ConsoleRenderer())

    # httpx logs every request at INFO with the FULL url — query string
    # included, and both search providers carry their api_key there. structlog's
    # PrintLoggerFactory bypasses stdlib logging so this is inert today, but a
    # single `logging.basicConfig(level=INFO)` (a notebook, a script, a future
    # log shipper) would publish provider credentials on every search call.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        # No cache_logger_on_first_use: a cached module-level logger ignores
        # later reconfiguration, which breaks structlog.testing.capture_logs
        # for every test that runs after anything calls create_app.
        cache_logger_on_first_use=False,
    )


def drop_token_from_access_log(record: logging.LogRecord) -> bool:
    """Remove the query string from uvicorn's access line for the two routes.

    The unsubscribe token rides in the query string of the unsubscribe and
    resubscribe addresses, and it is a secret. uvicorn logs each request as
    ``'%s - "%s %s HTTP/%s" %d'`` with ``record.args`` = (client address,
    method, path with query, HTTP version, status code). When the path, with
    its percent-encoding decoded once, lower-cased, repeated slashes made one
    and trailing slashes dropped, ends with ``/unsubscribe`` or
    ``/resubscribe``, this replaces the query part of the third argument before
    the line is formatted; every other line is left exactly as it is. The loose
    match also catches odd forms (``//unsubscribe``, ``/API/V1/Unsubscribe``)
    that answer 404 but would still log the token.

    Args:
        record: One ``uvicorn.access`` log record.

    Returns:
        Always ``True``: the line is kept, only its token is removed.
    """
    args = record.args
    if isinstance(args, tuple) and len(args) == 5 and isinstance(args[2], str):
        path, sep, _query = args[2].partition("?")
        plain = re.sub(r"/+", "/", unquote(path).lower()).rstrip("/")
        if sep and plain.endswith(_TOKEN_ENDINGS):
            record.args = (*args[:2], f"{path}?token=[removed]", *args[3:])
    return True


def install_access_log_filter() -> None:
    """Add :func:`drop_token_from_access_log` to the ``uvicorn.access`` logger.

    ``Logger.addFilter`` skips a filter that is already there, so building
    the app twice still leaves one.
    """
    logging.getLogger("uvicorn.access").addFilter(drop_token_from_access_log)
