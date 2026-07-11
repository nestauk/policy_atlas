"""Tests for provider-neutral token-usage helpers (policy_atlas.usage)."""

from policy_atlas.usage import (
    TokenUsage,
    UsageAccumulator,
    token_usage_from_provider,
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
    assert acc.payload() == {"prompt": 20, "completion": 10, "total": 30, "cached": 7}


def test_usage_accumulator_add_payload_reads_cached_key() -> None:
    acc = UsageAccumulator()
    acc.add_payload({"prompt": 5, "completion": 2, "total": 7, "cached": 1})
    assert acc.cached == 1
    assert acc.payload() == {"prompt": 5, "completion": 2, "total": 7, "cached": 1}


def test_usage_accumulator_add_payload_tolerates_missing_cached() -> None:
    acc = UsageAccumulator()
    acc.add_payload({"prompt": 5, "completion": 2, "total": 7})
    assert acc.cached == 0
    assert acc.payload() == {"prompt": 5, "completion": 2, "total": 7, "cached": 0}


def test_usage_metadata_includes_cached_tokens() -> None:
    meta = usage_metadata(TokenUsage(prompt=1, completion=2, total=3, cached=4))
    assert meta == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        "cached_tokens": 4,
    }


def test_usage_metadata_none_includes_cached_tokens_none() -> None:
    assert usage_metadata(None) == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
        "cached_tokens": None,
    }
