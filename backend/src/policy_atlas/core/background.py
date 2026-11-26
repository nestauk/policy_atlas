"""Run a piece of work on its own thread, off the request that started it."""

from __future__ import annotations

import threading
from collections.abc import Callable

import structlog

log = structlog.get_logger()


def in_background(work: Callable[[], object], *, name: str, event: str) -> threading.Thread:
    """Run ``work`` on a daemon thread; a failure is logged, never raised.

    Args:
        work: The function to run, with no arguments.
        name: The thread's name, also put on the failure log line.
        event: The log event name written when ``work`` raises.

    Returns:
        The started thread.
    """

    def run() -> None:
        try:
            work()
        except Exception:
            log.exception(event, name=name)

    thread = threading.Thread(target=run, name=name, daemon=True)
    thread.start()
    return thread
