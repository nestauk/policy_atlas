"""Wire tests for the OpenAI search-generation backend seam."""

from __future__ import annotations

from typing import Any, cast

import pytest

from policy_atlas.evidence_base.sourcing.search_generation import OpenAISearchGenerationBackend
from policy_atlas.evidence_base.sourcing.search_prompts import (
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_VERSION,
    QueriesPayload,
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
