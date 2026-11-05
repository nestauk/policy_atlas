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
        cached: Cached prompt token count (provider prompt-cache hits, "cache reads"),
            when provided by the backend. Part of ``prompt``, not extra to it.
        cache_write: Prompt tokens the provider wrote into its prompt cache on this
            call ("cache writes"), when provided. Part of ``prompt``, not extra to it.
        reasoning: Hidden "thinking" tokens the model generated before answering,
            when provided. Part of ``completion``, not extra to it.
    """

    prompt: int | None
    completion: int | None
    total: int | None
    cached: int | None = None
    cache_write: int | None = None
    reasoning: int | None = None


type UsageResult[T] = tuple[T, TokenUsage | None]


class UsageAccumulator:
    """Mutable accumulator for component-level token totals."""

    def __init__(self) -> None:
        self.prompt = 0
        self.completion = 0
        self.total = 0
        self.cached = 0
        self.cache_write = 0
        self.reasoning = 0

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
        self.cache_write += usage.cache_write or 0
        self.reasoning += usage.reasoning or 0

    def add_payload(self, totals: Mapping[str, int]) -> None:
        """Add a pre-aggregated usage payload.

        Args:
            totals: Mapping with ``prompt``, ``completion``, and ``total`` keys, plus
                optional ``cached``, ``cache_write`` and ``reasoning`` keys (a missing
                key counts as zero, so payloads stored before those keys existed still
                add up).
        """
        self.prompt += int(totals.get("prompt", 0))
        self.completion += int(totals.get("completion", 0))
        self.total += int(totals.get("total", 0))
        self.cached += int(totals.get("cached", 0))
        self.cache_write += int(totals.get("cache_write", 0))
        self.reasoning += int(totals.get("reasoning", 0))

    def payload(self) -> dict[str, int]:
        """Return JSON-ready component totals.

        Returns:
            ``{"prompt", "completion", "total", "cached", "cache_write", "reasoning"}``,
            each an ``int``.
        """
        return {
            "prompt": self.prompt,
            "completion": self.completion,
            "total": self.total,
            "cached": self.cached,
            "cache_write": self.cache_write,
            "reasoning": self.reasoning,
        }


def add_token_usage(first: TokenUsage | None, second: TokenUsage | None) -> TokenUsage | None:
    """Add two calls' token counts into one, for a turn that made two calls.

    Each field is the sum of the two; a field neither call reported stays
    ``None``, and a field only one reported keeps that one's count.

    Args:
        first: Usage of the first call, or ``None``.
        second: Usage of the second call, or ``None``.

    Returns:
        The combined usage, or ``None`` when neither call reported any.
    """
    if first is None:
        return second
    if second is None:
        return first

    def _sum(a: int | None, b: int | None) -> int | None:
        if a is None and b is None:
            return None
        return (a or 0) + (b or 0)

    return TokenUsage(
        prompt=_sum(first.prompt, second.prompt),
        completion=_sum(first.completion, second.completion),
        total=_sum(first.total, second.total),
        cached=_sum(first.cached, second.cached),
        cache_write=_sum(first.cache_write, second.cache_write),
        reasoning=_sum(first.reasoning, second.reasoning),
    )


def token_usage_from_provider(usage: Any | None) -> TokenUsage | None:
    """Normalize a provider usage object into ``TokenUsage``.

    Reads the OpenAI-shaped breakdowns too: ``prompt_tokens_details.cached_tokens``
    (cache reads), ``prompt_tokens_details.cache_write_tokens`` (cache writes) and
    ``completion_tokens_details.reasoning_tokens`` (thinking tokens). The details
    blocks may be objects or plain dicts; a missing block or key gives ``None``.

    Args:
        usage: Any provider usage object exposing prompt/completion/total token
            attributes, or ``None``.

    Returns:
        Provider-neutral token usage, or ``None`` when the provider omitted it.
    """
    if usage is None:
        return None
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    return TokenUsage(
        prompt=_int_or_none(getattr(usage, "prompt_tokens", None)),
        completion=_int_or_none(getattr(usage, "completion_tokens", None)),
        total=_int_or_none(getattr(usage, "total_tokens", None)),
        cached=_detail(prompt_details, "cached_tokens"),
        cache_write=_detail(prompt_details, "cache_write_tokens"),
        reasoning=_detail(completion_details, "reasoning_tokens"),
    )


def _detail(details: Any, key: str) -> int | None:
    # The OpenAI SDK gives a model object; some providers/paths give a plain dict.
    # Keys the SDK model does not declare (``cache_write_tokens``) still arrive as
    # attributes, because the SDK's models keep unknown fields.
    if isinstance(details, Mapping):
        return _int_or_none(details.get(key))
    return _int_or_none(getattr(details, key, None))


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
            "cache_write_tokens": None,
            "reasoning_tokens": None,
        }
    return {
        "prompt_tokens": usage.prompt,
        "completion_tokens": usage.completion,
        "total_tokens": usage.total,
        "cached_tokens": usage.cached,
        "cache_write_tokens": usage.cache_write,
        "reasoning_tokens": usage.reasoning,
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


def usage_details(usage: TokenUsage | None) -> dict[str, Any] | None:
    """Token usage in the OpenAI shape Langfuse prices from (``usage_details``).

    In plain words: Langfuse (our tracing tool) works out the cost of each model
    call from the token counts we send it. Different kinds of token have different
    prices, so we send the breakdown, not just the totals:

    - ``prompt_tokens`` / ``completion_tokens`` / ``total_tokens`` become Langfuse's
      ``input`` / ``output`` / ``total``.
    - Each key under ``prompt_tokens_details`` becomes its own ``input_<key>`` bucket
      and is subtracted from ``input``: ``cached_tokens`` (cheap cache reads) becomes
      ``input_cached_tokens``, ``cache_write_tokens`` (dearer cache writes) becomes
      ``input_cache_write_tokens``.
    - Each key under ``completion_tokens_details`` becomes ``output_<key>`` and is
      subtracted from ``output``: ``reasoning_tokens`` (hidden thinking) becomes
      ``output_reasoning_tokens``.

    That mapping happens on the Langfuse server, not in this code; the Python SDK
    forwards this dict unchanged. The buckets are exclusive, so no token is priced
    twice. A breakdown key is sent
    only when it is non-zero. Without this block the server guesses the counts by
    re-tokenising the span's text, which misses thinking tokens and cache hits.

    Args:
        usage: Provider-neutral token usage, or ``None``.

    Returns:
        The ``usage_details`` payload, or ``None`` when the API omitted usage.
    """
    if usage is None:
        return None
    details: dict[str, Any] = {
        "prompt_tokens": usage.prompt or 0,
        "completion_tokens": usage.completion or 0,
        "total_tokens": usage.total or 0,
    }
    prompt_details: dict[str, int] = {}
    if usage.cached:
        prompt_details["cached_tokens"] = usage.cached
    if usage.cache_write:
        prompt_details["cache_write_tokens"] = usage.cache_write
    if prompt_details:
        details["prompt_tokens_details"] = prompt_details
    if usage.reasoning:
        details["completion_tokens_details"] = {"reasoning_tokens": usage.reasoning}
    return details


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
