"""Wire tests for the OpenAI search-generation backend seam."""

from __future__ import annotations

from typing import Any, cast

import pytest

from policy_atlas.core.usage import TokenUsage
from policy_atlas.evidence_base.sourcing.search_generation import (
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
    V2SingleQueryWire,
)
from policy_atlas.evidence_base.sourcing.search_prompts import (
    MAX_PARAPHRASES,
    N_QUERIES,
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION,
    QueriesPayload,
    ReformulatePayload,
    SearchQueriesWire,
)
from tests.helpers import FakeOpenAIParseClient, fake_parse_client


def _backend(
    fake_client: FakeOpenAIParseClient,
) -> tuple[OpenAISearchGenerationBackend, FakeOpenAIParseClient]:
    backend: OpenAISearchGenerationBackend = object.__new__(OpenAISearchGenerationBackend)
    cast("Any", backend)._client = fake_client
    cast("Any", backend)._langfuse_client = None
    return backend, fake_client


def test_generate_queries_passes_model_and_returns_parsed_wire() -> None:
    # Derived from the prompt file's name (search_queries_system_v3.txt), so
    # swapping the prompt file relabels the traces automatically.
    assert SEARCH_QUERIES_PROMPT_VERSION == "search_queries_v3"
    wire = SearchQueriesWire(
        queries=["policy evaluation", "randomized trial"],
        overton_paraphrases=["Evidence about policy evaluation"],
    )
    backend, fake_client = _backend(fake_parse_client(parsed=wire))

    result, usage = backend.generate_queries(QueriesPayload(intent="policy evaluation"))

    assert result is wire
    assert usage is None
    [kwargs] = fake_client.chat.completions.calls
    assert kwargs["model"] == SEARCH_QUERIES_MODEL
    assert kwargs["model"] == "gpt-5.4-mini"
    assert kwargs["response_format"] is SearchQueriesWire


def test_generate_queries_raises_on_no_choices() -> None:
    backend, _fake_client = _backend(fake_parse_client(choices=[]))

    with pytest.raises(RuntimeError, match="had no choices"):
        backend.generate_queries(QueriesPayload(intent="policy evaluation"))


def test_v2_generate_queries_uses_split_prompt_versions_and_aggregates_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend: V2SearchGenerationBackend = object.__new__(V2SearchGenerationBackend)
    calls: list[dict[str, Any]] = []
    openalex_counter = 0
    overton_counter = 0

    def fake_call_wire(self: V2SearchGenerationBackend, **kwargs: Any) -> tuple[V2SingleQueryWire, TokenUsage]:
        nonlocal openalex_counter, overton_counter
        calls.append(kwargs)
        if kwargs["prompt_version"] == SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION:
            openalex_counter += 1
            return (
                V2SingleQueryWire(query=f"openalex query {openalex_counter}"),
                TokenUsage(prompt=1, completion=2, total=3, cached=0),
            )
        if kwargs["prompt_version"] == SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION:
            overton_counter += 1
            return (
                V2SingleQueryWire(query=f"overton query {overton_counter}"),
                TokenUsage(prompt=1, completion=2, total=3, cached=0),
            )
        raise AssertionError(f"unexpected prompt version {kwargs['prompt_version']!r}")

    monkeypatch.setattr(V2SearchGenerationBackend, "_call_wire", fake_call_wire)

    wire, usage = backend.generate_queries(QueriesPayload(intent="policy evaluation"))

    assert wire.queries == [f"openalex query {index}" for index in range(1, N_QUERIES + 1)]
    assert wire.overton_paraphrases == [
        f"overton query {index}" for index in range(1, MAX_PARAPHRASES + 1)
    ]
    assert usage == TokenUsage(
        prompt=(N_QUERIES + MAX_PARAPHRASES),
        completion=(N_QUERIES + MAX_PARAPHRASES) * 2,
        total=(N_QUERIES + MAX_PARAPHRASES) * 3,
        cached=0,
    )
    assert len(calls) == N_QUERIES + MAX_PARAPHRASES


def test_v2_reformulate_deduplicates_provider_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend: V2SearchGenerationBackend = object.__new__(V2SearchGenerationBackend)

    def fake_call_wire(self: V2SearchGenerationBackend, **kwargs: Any) -> tuple[V2SingleQueryWire, None]:
        if kwargs["prompt_version"] == SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION:
            return V2SingleQueryWire(query="same openalex query"), None
        if kwargs["prompt_version"] == SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION:
            return V2SingleQueryWire(query="same overton query"), None
        raise AssertionError(f"unexpected prompt version {kwargs['prompt_version']!r}")

    monkeypatch.setattr(V2SearchGenerationBackend, "_call_wire", fake_call_wire)

    wire, usage = backend.reformulate(
        ReformulatePayload(
            intent="policy evaluation",
            round_index=2,
        )
    )

    assert wire.queries == ["same openalex query"]
    assert wire.overton_paraphrases == ["same overton query"]
    assert usage is None
