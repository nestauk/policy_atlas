"""Wire tests for the OpenAI search-generation backend seam."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pytest

from policy_atlas.search_generation import OpenAISearchGenerationBackend
from policy_atlas.search_prompts import (
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_VERSION,
    QueriesPayload,
    SearchQueriesWire,
)


@dataclass
class _FakeParsedMessage:
    parsed: Any


@dataclass
class _FakeChoice:
    message: _FakeParsedMessage


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]
    usage: None = None


class _FakeCompletions:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return self._response


class _FakeChat:
    def __init__(self, response: _FakeResponse) -> None:
        self.completions = _FakeCompletions(response)


class _FakeOpenAIClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.chat = _FakeChat(response)


def _backend(response: _FakeResponse) -> tuple[OpenAISearchGenerationBackend, _FakeOpenAIClient]:
    backend: OpenAISearchGenerationBackend = object.__new__(OpenAISearchGenerationBackend)
    fake_client = _FakeOpenAIClient(response)
    cast("Any", backend)._client = fake_client
    cast("Any", backend)._langfuse_client = None
    return backend, fake_client


def test_generate_queries_passes_model_and_returns_parsed_wire() -> None:
    assert SEARCH_QUERIES_PROMPT_VERSION == "search_queries_v1"
    wire = SearchQueriesWire(
        queries=["policy evaluation", "randomized trial"],
        overton_paraphrases=["Evidence about policy evaluation"],
    )
    response = _FakeResponse(choices=[_FakeChoice(message=_FakeParsedMessage(wire))])
    backend, fake_client = _backend(response)

    result, usage = backend.generate_queries(QueriesPayload(intent="policy evaluation"))

    assert result is wire
    assert usage is None
    [kwargs] = fake_client.chat.completions.calls
    assert kwargs["model"] == SEARCH_QUERIES_MODEL
    assert kwargs["model"] == "gpt-5.4-mini"
    assert kwargs["response_format"] is SearchQueriesWire


def test_generate_queries_raises_on_no_choices() -> None:
    response = _FakeResponse(choices=[])
    backend, _fake_client = _backend(response)

    with pytest.raises(RuntimeError, match="had no choices"):
        backend.generate_queries(QueriesPayload(intent="policy evaluation"))
