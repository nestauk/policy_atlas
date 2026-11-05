"""Tests for provider-neutral token-usage helpers (policy_atlas.core.usage)."""

from policy_atlas.core.usage import (
    TokenUsage,
    UsageAccumulator,
    token_usage_from_provider,
    usage_details,
    usage_metadata,
)


class _FakePromptTokensDetails:
    def __init__(self, cached_tokens: int) -> None:
        self.cached_tokens = cached_tokens


class _FakeUsageWithCached:
    def __init__(self) -> None:
        self.prompt_tokens = 100
        self.completion_tokens = 20
        self.total_tokens = 120
        self.prompt_tokens_details = _FakePromptTokensDetails(cached_tokens=7)


class _FakeUsageWithoutDetails:
    def __init__(self) -> None:
        self.prompt_tokens = 50
        self.completion_tokens = 10
        self.total_tokens = 60


def test_token_usage_from_provider_reads_cached_tokens_detail() -> None:
    usage = token_usage_from_provider(_FakeUsageWithCached())
    assert usage is not None
    assert usage.cached == 7


def test_token_usage_from_provider_without_details_yields_cached_none() -> None:
    usage = token_usage_from_provider(_FakeUsageWithoutDetails())
    assert usage is not None
    assert usage.cached is None


def test_usage_accumulator_add_sums_cached() -> None:
    acc = UsageAccumulator()
    acc.add(TokenUsage(prompt=10, completion=5, total=15, cached=3))
    acc.add(TokenUsage(prompt=10, completion=5, total=15, cached=4))
    assert acc.cached == 7
    assert acc.payload() == {
        "prompt": 20,
        "completion": 10,
        "total": 30,
        "cached": 7,
        "cache_write": 0,
        "reasoning": 0,
    }


def test_usage_accumulator_add_payload_reads_cached_key() -> None:
    acc = UsageAccumulator()
    acc.add_payload({"prompt": 5, "completion": 2, "total": 7, "cached": 1})
    assert acc.cached == 1
    assert acc.payload() == {
        "prompt": 5,
        "completion": 2,
        "total": 7,
        "cached": 1,
        "cache_write": 0,
        "reasoning": 0,
    }


def test_usage_accumulator_add_payload_tolerates_missing_cached() -> None:
    acc = UsageAccumulator()
    acc.add_payload({"prompt": 5, "completion": 2, "total": 7})
    assert acc.cached == 0
    assert acc.payload() == {
        "prompt": 5,
        "completion": 2,
        "total": 7,
        "cached": 0,
        "cache_write": 0,
        "reasoning": 0,
    }


def test_usage_metadata_includes_cached_tokens() -> None:
    meta = usage_metadata(TokenUsage(prompt=1, completion=2, total=3, cached=4))
    assert meta == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        "cached_tokens": 4,
        "cache_write_tokens": None,
        "reasoning_tokens": None,
    }


def test_usage_metadata_none_includes_cached_tokens_none() -> None:
    assert usage_metadata(None) == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cached_tokens": None,
        "cache_write_tokens": None,
        "reasoning_tokens": None,
    }


def test_token_usage_from_provider_rejects_boolean_fields() -> None:
    """bool is an int subclass: a True/False usage field is invalid data and
    must land as None (absent), never be coerced to 1/0."""

    class _BoolUsage:
        prompt_tokens = True
        completion_tokens = 10
        total_tokens = 60

    usage = token_usage_from_provider(_BoolUsage())
    assert usage is not None
    assert usage.prompt is None
    assert usage.completion == 10


def test_usage_details_uses_openai_shape_with_cached_detail() -> None:
    assert usage_details(TokenUsage(prompt=100, completion=20, total=120, cached=7)) == {
        "prompt_tokens": 100,
        "completion_tokens": 20,
        "total_tokens": 120,
        "prompt_tokens_details": {"cached_tokens": 7},
    }


def test_usage_details_omits_cached_detail_when_absent_and_none_for_no_usage() -> None:
    assert usage_details(TokenUsage(prompt=5, completion=1, total=6)) == {
        "prompt_tokens": 5,
        "completion_tokens": 1,
        "total_tokens": 6,
    }
    assert usage_details(None) is None


# --- Cache writes and reasoning tokens (task 056, need N1) -------------------


class _Details:
    """Attribute-style details block (the OpenAI SDK model shape)."""

    def __init__(self, **fields: int) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Usage:
    def __init__(
        self,
        *,
        prompt_details: object | None = None,
        completion_details: object | None = None,
    ) -> None:
        self.prompt_tokens = 1000
        self.completion_tokens = 300
        self.total_tokens = 1300
        self.prompt_tokens_details = prompt_details
        self.completion_tokens_details = completion_details


def test_provider_usage_with_both_details_reads_cache_write_and_reasoning() -> None:
    usage = token_usage_from_provider(
        _Usage(
            prompt_details=_Details(cached_tokens=200, cache_write_tokens=500),
            completion_details=_Details(reasoning_tokens=120),
        )
    )
    assert usage == TokenUsage(
        prompt=1000,
        completion=300,
        total=1300,
        cached=200,
        cache_write=500,
        reasoning=120,
    )
    assert usage_details(usage) == {
        "prompt_tokens": 1000,
        "completion_tokens": 300,
        "total_tokens": 1300,
        "prompt_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 500},
        "completion_tokens_details": {"reasoning_tokens": 120},
    }


def test_provider_usage_with_dict_shaped_details() -> None:
    usage = token_usage_from_provider(
        _Usage(
            prompt_details={"cached_tokens": 3, "cache_write_tokens": 4},
            completion_details={"reasoning_tokens": 5},
        )
    )
    assert usage is not None
    assert (usage.cached, usage.cache_write, usage.reasoning) == (3, 4, 5)


def test_provider_usage_with_only_cache_write() -> None:
    usage = token_usage_from_provider(_Usage(prompt_details=_Details(cache_write_tokens=500)))
    assert usage is not None
    assert (usage.cached, usage.cache_write, usage.reasoning) == (None, 500, None)
    assert usage_details(usage) == {
        "prompt_tokens": 1000,
        "completion_tokens": 300,
        "total_tokens": 1300,
        "prompt_tokens_details": {"cache_write_tokens": 500},
    }


def test_provider_usage_with_only_reasoning() -> None:
    usage = token_usage_from_provider(_Usage(completion_details=_Details(reasoning_tokens=120)))
    assert usage is not None
    assert (usage.cached, usage.cache_write, usage.reasoning) == (None, None, 120)
    assert usage_details(usage) == {
        "prompt_tokens": 1000,
        "completion_tokens": 300,
        "total_tokens": 1300,
        "completion_tokens_details": {"reasoning_tokens": 120},
    }


def test_provider_usage_with_neither_detail() -> None:
    usage = token_usage_from_provider(_Usage())
    assert usage is not None
    assert (usage.cached, usage.cache_write, usage.reasoning) == (None, None, None)
    assert usage_details(usage) == {
        "prompt_tokens": 1000,
        "completion_tokens": 300,
        "total_tokens": 1300,
    }


def test_usage_details_omits_zero_breakdown_keys() -> None:
    usage = TokenUsage(prompt=10, completion=5, total=15, cached=0, cache_write=0, reasoning=0)
    assert usage_details(usage) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "total_tokens": 15,
    }


def test_provider_usage_rejects_boolean_breakdown_fields() -> None:
    usage = token_usage_from_provider(
        _Usage(
            prompt_details=_Details(cache_write_tokens=True),
            completion_details=_Details(reasoning_tokens=False),
        )
    )
    assert usage is not None
    assert usage.cache_write is None
    assert usage.reasoning is None


def test_real_openai_sdk_usage_keeps_undeclared_cache_write_field() -> None:
    """The OpenAI SDK model does not declare ``cache_write_tokens``; providers that
    send it (via the OpenAI-compatible API) must still reach ``cache_write``."""
    from openai.types.completion_usage import CompletionUsage

    raw = CompletionUsage.model_validate(
        {
            "prompt_tokens": 1000,
            "completion_tokens": 300,
            "total_tokens": 1300,
            "prompt_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 500},
            "completion_tokens_details": {"reasoning_tokens": 120},
        }
    )
    usage = token_usage_from_provider(raw)
    assert usage is not None
    assert (usage.cached, usage.cache_write, usage.reasoning) == (200, 500, 120)


def test_usage_accumulator_sums_cache_write_and_reasoning() -> None:
    acc = UsageAccumulator()
    acc.add(TokenUsage(prompt=10, completion=5, total=15, cache_write=6, reasoning=2))
    acc.add(TokenUsage(prompt=10, completion=5, total=15, cached=1, reasoning=3))
    acc.add(None)
    acc.add_payload({"prompt": 1, "completion": 1, "total": 2, "cache_write": 4, "reasoning": 1})
    assert acc.payload() == {
        "prompt": 21,
        "completion": 11,
        "total": 32,
        "cached": 1,
        "cache_write": 10,
        "reasoning": 6,
    }


def test_usage_accumulator_add_payload_tolerates_missing_new_keys() -> None:
    acc = UsageAccumulator()
    acc.add_payload({"prompt": 5, "completion": 2, "total": 7, "cached": 1})
    assert acc.cache_write == 0
    assert acc.reasoning == 0


def test_usage_metadata_includes_cache_write_and_reasoning() -> None:
    meta = usage_metadata(
        TokenUsage(prompt=1, completion=2, total=3, cached=4, cache_write=5, reasoning=6)
    )
    assert meta == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        "cached_tokens": 4,
        "cache_write_tokens": 5,
        "reasoning_tokens": 6,
    }
