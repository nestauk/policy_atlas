"""The "call, one retry, keep the usage, check the answer" loop of every options-scoping step."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import structlog

from policy_atlas.core.usage import TokenUsage, UsageResult

log = structlog.get_logger()

#: Attempts per model call: the call and one retry.
CALL_ATTEMPTS = 2


@dataclass(frozen=True)
class CallOutcome[T]:
    """One model call after its attempts.

    Attributes:
        name: The call's name (for logs and failure messages).
        value: The checked answer, or ``None`` when every attempt failed.
        attempts: The attempts made.
        usages: Every answered attempt's token usage, for the caller to add.
    """

    name: str
    value: T | None
    attempts: int
    usages: list[TokenUsage | None]


def call_with_retry[R, T](
    name: str,
    call: Callable[[], UsageResult[R]],
    check: Callable[[R], T | None],
    *,
    final_check: Callable[[R], T | None] | None = None,
    event: str,
) -> CallOutcome[T]:
    """Make one model call and one retry; never raises.

    A call that raises or whose answer ``check`` refuses (returns ``None``)
    is tried once more. Safe to run in a worker thread: it touches no shared
    state.

    Args:
        name: The call's name.
        call: Makes the call.
        check: The checked value of an answer, or ``None`` when it is malformed.
        final_check: When given, checks the LAST attempt in place of ``check``
            (an answer refused once and accepted on the retry).
        event: The log event prefix (``"<event>.call_failed"``,
            ``"<event>.call_malformed"``).

    Returns:
        The outcome.
    """
    usages: list[TokenUsage | None] = []
    for attempt in range(1, CALL_ATTEMPTS + 1):
        try:
            response, usage = call()
        except Exception as exc:  # fail-closed: tried again, then the caller decides
            log.warning(
                f"{event}.call_failed", call=name, attempt=attempt, error_type=type(exc).__name__
            )
            continue
        usages.append(usage)
        last = attempt == CALL_ATTEMPTS
        value = (final_check or check)(response) if last else check(response)
        if value is not None:
            return CallOutcome(name=name, value=value, attempts=attempt, usages=usages)
        log.warning(f"{event}.call_malformed", call=name, attempt=attempt)
    return CallOutcome(name=name, value=None, attempts=CALL_ATTEMPTS, usages=usages)
