"""Run a future's completion callback inside the caller's context variables.

A pool thread runs a future's completion callback in the thread's own, empty
context, not in the context the work was submitted under. The live-progress
helpers read the bound task and stage from context variables, so a callback
that publishes progress must carry the submitting thread's context with it.
"""

from __future__ import annotations

import contextvars
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any


def add_done_callback_in_context(
    future: Future[Any], callback: Callable[[Future[Any]], None]
) -> None:
    """Register ``callback`` on ``future`` so it runs in a copy of this context.

    Call this from the thread that submitted the work (task 058, N2). Each call
    takes its own copy, so callbacks finishing at the same moment on different
    threads never enter one context twice.

    Args:
        future: The submitted work.
        callback: Called with the finished future.
    """
    ctx = contextvars.copy_context()
    future.add_done_callback(lambda finished: ctx.run(callback, finished))
