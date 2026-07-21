"""Provider-neutral token-usage helpers for model backend seams."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import structlog
from openai.types.completion_usage import CompletionUsage

log = structlog.get_logger()


@dataclass(frozen=True)
class TokenUsage:
    """Token counts for one model call.

    Args:
        prompt: Prompt/input token count, when provided by the backend.
        completion: Completion/output token count, when provided by the backend.
        total: Total token count, when provided by the backend.
        cached: Cached prompt token count (provider prompt-cache hits), when provided by
            the backend.
    """

    prompt: int | None
    completion: int | None
    total: int | None
    cached: int | None = None


type UsageResult[T] = tuple[T, TokenUsage | None]


class UsageAccumulator:
    """Mutable accumulator for component-level token totals."""

    def __init__(self) -> None:
        self.prompt = 0
        self.completion = 0
        self.total = 0
        self.cached = 0

    def add(self, usage: TokenUsage | None) -> None:
        """Add one call's usage counts, ignoring unavailable fields.

        Args:
            usage: Usage counts for one model call, or ``None``.
        """
        if usage is None:
            return
        self.prompt += usage.prompt or 0
        self.completion += usage.completion or 0
        self.total += usage.total or 0
        self.cached += usage.cached or 0

    def add_payload(self, totals: Mapping[str, int]) -> None:
        """Add a pre-aggregated usage payload.

        Args:
            totals: Mapping with ``prompt``, ``completion``, and ``total`` keys.
        """
        self.prompt += int(totals.get("prompt", 0))
        self.completion += int(totals.get("completion", 0))
        self.total += int(totals.get("total", 0))
        self.cached += int(totals.get("cached", 0))

    def payload(self) -> dict[str, int]:
        """Return JSON-ready component totals.

        Returns:
            ``{"prompt": int, "completion": int, "total": int, "cached": int}``.
        """
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
            "cached": self.cached,
        }


def token_usage_from_provider(usage: Any | None) -> TokenUsage | None:
    """Normalize a provider usage object into ``TokenUsage``.

    Args:
        usage: Any provider usage object exposing prompt/completion/total token
            attributes, or ``None``.

    Returns:
        Provider-neutral token usage, or ``None`` when the provider omitted it.
    """
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    return TokenUsage(
        prompt=_int_or_none(getattr(usage, "prompt_tokens", None)),
        completion=_int_or_none(getattr(usage, "completion_tokens", None)),
        total=_int_or_none(getattr(usage, "total_tokens", None)),
        cached=_int_or_none(getattr(details, "cached_tokens", None)),
    )


def _token_usage_metadata(usage: TokenUsage | None) -> dict[str, int | None]:
    """Return Langfuse/log metadata keys for one usage block.

    Args:
        usage: Provider-neutral token usage, or ``None``.

    Returns:
        Metadata using the historical ``*_tokens`` key names.
    """
    if usage is None:
        return {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
            "cached_tokens": None,
        }
    return {
        "prompt_tokens": usage.prompt,
        "completion_tokens": usage.completion,
        "total_tokens": usage.total,
        "cached_tokens": usage.cached,
    }


def usage_metadata(usage: CompletionUsage | TokenUsage | None) -> dict[str, int | None]:
    """Token usage as log/span metadata; all-``None`` when the API omitted usage.

    Shared by the live chat backends so the usage shape lives in one place.

    Args:
        usage: The response's usage block, provider-neutral usage, or ``None``.
    """
    if isinstance(usage, TokenUsage):
        return _token_usage_metadata(usage)
    return _token_usage_metadata(token_usage_from_provider(usage))


def log_usage(event: str, usage: CompletionUsage | None) -> None:
    """Log one model call's token usage (``None``-safe).

    Args:
        event: The structlog event name.
        usage: The response's usage block, or ``None``.
    """
    log.info(event, **usage_metadata(usage))


def _int_or_none(value: Any) -> int | None:
    # bool is an int subclass — a True/False usage field is invalid, not 1/0.
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None
