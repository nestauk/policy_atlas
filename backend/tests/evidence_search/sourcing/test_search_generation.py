"""Wire tests for the OpenAI search-generation backend seam."""

from __future__ import annotations

from typing import Any, Literal, cast

import boto3
import pytest
from botocore.stub import Stubber

from policy_atlas.core.usage import TokenUsage
from policy_atlas.evidence_search.sourcing import search_generation, search_live
from policy_atlas.evidence_search.sourcing.search_generation import (
    CLAUDE_QUERY_TOOL_NAME,
    SEARCH_QUERIES_CLAUDE_SYSTEM_PROMPT,
    ClaudeSearchGenerationBackend,
    OpenAISearchGenerationBackend,
    V2SearchGenerationBackend,
    V2SingleQueryWire,
)
from policy_atlas.evidence_search.sourcing.search_prompts import (
    MAX_PARAPHRASES,
    N_QUERIES,
    SEARCH_QUERIES_MODEL,
    SEARCH_QUERIES_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OPENALEX_PROMPT_VERSION,
    SEARCH_QUERIES_V2_OVERTON_PROMPT_VERSION,
    QueriesPayload,
    ReformulatePayload,
    SearchQueriesWire,
    SearchSuggestWire,
    SuggestPayload,
    build_queries_messages,
)
from policy_atlas.runtime import agent
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
    assert kwargs["model"] == "gpt-5.6-luna"
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

    def fake_call_wire(
        self: V2SearchGenerationBackend, **kwargs: Any
    ) -> tuple[V2SingleQueryWire, TokenUsage]:
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

    def fake_call_wire(
        self: V2SearchGenerationBackend, **kwargs: Any
    ) -> tuple[V2SingleQueryWire, None]:
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


class _InnerBackend:
    """Record delegated Claude-backend calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def reformulate(self, payload: ReformulatePayload) -> tuple[SearchQueriesWire, None]:
        self.calls.append(("reformulate", payload))
        return SearchQueriesWire(queries=[], overton_paraphrases=[]), None

    def suggest(self, payload: SuggestPayload) -> tuple[SearchSuggestWire, None]:
        self.calls.append(("suggest", payload))
        return SearchSuggestWire(papers=[]), None


def _bedrock_client() -> Any:
    return boto3.client(
        "bedrock-runtime",
        region_name="eu-west-2",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
    )


def _claude_backend(
    monkeypatch: pytest.MonkeyPatch,
    *,
    client: Any,
    model: str = "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
    inner: _InnerBackend | None = None,
) -> ClaudeSearchGenerationBackend:
    monkeypatch.setattr(
        search_generation,
        "route",
        lambda: type("Route", (), {"search_queries": type("Search", (), {"model": model})()})(),
    )
    return ClaudeSearchGenerationBackend(client=client, inner=cast("Any", inner or _InnerBackend()))


def _expected_converse_params(payload: QueriesPayload, model: str) -> dict[str, Any]:
    return {
        "modelId": model,
        "system": [{"text": SEARCH_QUERIES_CLAUDE_SYSTEM_PROMPT}],
        "messages": [
            {"role": "user", "content": [{"text": build_queries_messages(payload)[1]["content"]}]}
        ],
        "inferenceConfig": {"maxTokens": 8_192},
        "toolConfig": {
            "tools": [
                {
                    "toolSpec": {
                        "name": CLAUDE_QUERY_TOOL_NAME,
                        "description": (
                            "Return the generated search queries for the research question."
                        ),
                        "inputSchema": {"json": SearchQueriesWire.model_json_schema()},
                    }
                }
            ],
            "toolChoice": {"tool": {"name": CLAUDE_QUERY_TOOL_NAME}},
        },
    }


def _converse_response(*, tool_use: list[dict[str, Any]], usage: dict[str, Any]) -> dict[str, Any]:
    return {
        "output": {"message": {"role": "assistant", "content": tool_use}},
        "stopReason": "tool_use",
        "usage": usage,
        "metrics": {"latencyMs": 1},
    }


def _response_method(response: dict[str, Any]) -> Any:
    def converse(_self: Any, **_kwargs: Any) -> dict[str, Any]:
        return response

    return converse


def test_claude_generate_queries_sends_converse_request_and_parses_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = QueriesPayload(intent="policy evaluation")
    client = _bedrock_client()
    backend = _claude_backend(monkeypatch, client=client)
    response = _converse_response(
        tool_use=[
            {
                "toolUse": {
                    "toolUseId": "tool-1",
                    "name": CLAUDE_QUERY_TOOL_NAME,
                    "input": {
                        "queries": ["policy evaluation", "randomized trial"],
                        "overton_paraphrases": ["Evidence about policy evaluation"],
                    },
                }
            }
        ],
        usage={"inputTokens": 11, "outputTokens": 7, "totalTokens": 18, "cacheReadInputTokens": 3},
    )
    with Stubber(client) as stubber:
        stubber.add_response(
            "converse",
            response,
            _expected_converse_params(payload, "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
        )
        wire, usage = backend.generate_queries(payload)

    assert wire == SearchQueriesWire(
        queries=["policy evaluation", "randomized trial"],
        overton_paraphrases=["Evidence about policy evaluation"],
    )
    assert usage == TokenUsage(prompt=11, completion=7, total=18, cached=3)


def test_claude_generate_queries_uses_route_model_only_in_model_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = QueriesPayload(intent="policy evaluation")
    model = "eu.anthropic.claude-sonnet-5"
    default_params = _expected_converse_params(
        payload, "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    )
    alternate_params = _expected_converse_params(payload, model)
    assert {key: value for key, value in default_params.items() if key != "modelId"} == {
        key: value for key, value in alternate_params.items() if key != "modelId"
    }
    client = _bedrock_client()
    backend = _claude_backend(monkeypatch, client=client, model=model)
    with Stubber(client) as stubber:
        stubber.add_response(
            "converse",
            _converse_response(
                tool_use=[
                    {
                        "toolUse": {
                            "toolUseId": "tool-1",
                            "name": CLAUDE_QUERY_TOOL_NAME,
                            "input": {"queries": [], "overton_paraphrases": []},
                        }
                    }
                ],
                usage={"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
            ),
            alternate_params,
        )
        backend.generate_queries(payload)


def test_claude_generate_queries_rejects_invalid_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = QueriesPayload(intent="policy evaluation")
    good_usage = {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2}
    tool = {"toolUseId": "a", "name": CLAUDE_QUERY_TOOL_NAME, "input": {}}
    cases = [
        (_converse_response(tool_use=[], usage=good_usage), "no tool call"),
        (
            _converse_response(
                tool_use=[{"toolUse": tool}, {"toolUse": {**tool, "toolUseId": "b"}}],
                usage=good_usage,
            ),
            "2 tool calls",
        ),
        (
            _converse_response(
                tool_use=[{"toolUse": {**tool, "name": "wrong"}}], usage=good_usage
            ),
            "unexpected tool name",
        ),
        (
            _converse_response(
                tool_use=[{"toolUse": {**tool, "input": "wrong"}}], usage=good_usage
            ),
            "not an object",
        ),
        (
            _converse_response(
                tool_use=[{"toolUse": {**tool, "input": {"overton_paraphrases": []}}}],
                usage=good_usage,
            ),
            "failed validation",
        ),
        (
            _converse_response(
                tool_use=[
                    {
                        "toolUse": {
                            **tool,
                            "input": {"queries": [], "overton_paraphrases": []},
                        }
                    }
                ],
                usage={"inputTokens": 1, "totalTokens": 1},
            ),
            "usage fields",
        ),
        (
            _converse_response(
                tool_use=[
                    {
                        "toolUse": {
                            **tool,
                            "input": {"queries": [], "overton_paraphrases": []},
                        }
                    }
                ],
                usage={"inputTokens": "1", "outputTokens": 1, "totalTokens": 2},
            ),
            "usage fields must be integers",
        ),
    ]
    for response, match in cases:
        client = type("InvalidResponseClient", (), {"converse": _response_method(response)})()
        backend = _claude_backend(monkeypatch, client=client)
        with pytest.raises(RuntimeError, match=match):
            backend.generate_queries(payload)


class _RecordingSpan:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(self, **kwargs: Any) -> None:
        self.updates.append(kwargs)

    def __enter__(self) -> _RecordingSpan:
        return self

    def __exit__(self, *_exc: Any) -> Literal[False]:
        return False


class _RecordingLangfuse:
    def __init__(self) -> None:
        self.span = _RecordingSpan()
        self.opened: list[tuple[str, str]] = []

    def start_as_current_observation(self, *, name: str, as_type: str) -> _RecordingSpan:
        self.opened.append((name, as_type))
        return self.span


def test_claude_generate_queries_trace_carries_model_and_prompt_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rubric item 13: the Langfuse span names the Claude model and the new prompt version."""
    payload = QueriesPayload(intent="policy evaluation")
    response = _converse_response(
        tool_use=[
            {
                "toolUse": {
                    "toolUseId": "a",
                    "name": CLAUDE_QUERY_TOOL_NAME,
                    "input": {"queries": ["q"], "overton_paraphrases": []},
                }
            }
        ],
        usage={"inputTokens": 5, "outputTokens": 2, "totalTokens": 7},
    )
    client = type("GoodClient", (), {"converse": _response_method(response)})()
    _claude_backend(monkeypatch, client=client)  # pins the route the backend reads
    langfuse = _RecordingLangfuse()
    backend = ClaudeSearchGenerationBackend(
        client=client, inner=cast("Any", _InnerBackend()), langfuse_client=cast("Any", langfuse)
    )

    backend.generate_queries(payload)

    assert langfuse.opened == [("search:generate_queries", "generation")]
    [update] = langfuse.span.updates
    assert update["model"] == "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert update["metadata"]["prompt_version"] == "search_queries_claude_v1"
    assert update["usage_details"]["prompt_tokens"] == 5


def test_claude_reformulate_and_suggest_delegate_to_inner_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inner = _InnerBackend()
    backend = _claude_backend(monkeypatch, client=_bedrock_client(), inner=inner)
    reformulate = ReformulatePayload(intent="policy evaluation", round_index=2)
    suggest = SuggestPayload(intent="policy evaluation")

    assert backend.reformulate(reformulate) == (
        SearchQueriesWire(queries=[], overton_paraphrases=[]),
        None,
    )
    assert backend.suggest(suggest) == (SearchSuggestWire(papers=[]), None)
    assert inner.calls == [("reformulate", reformulate), ("suggest", suggest)]


@pytest.mark.parametrize(
    ("backend_name", "expected"),
    [("claude", "claude"), ("openai", "openai")],
)
def test_live_planner_selects_search_generation_backend_from_route(
    monkeypatch: pytest.MonkeyPatch, backend_name: str, expected: str
) -> None:
    class _LiveFetcher:
        mode = "live"

    class _SelectedBackend:
        def __init__(self, name: str) -> None:
            self.name = name

    def _factory(*_args: Any, **_kwargs: Any) -> object:
        return object()

    monkeypatch.setattr(
        agent,
        "route",
        lambda: type(
            "Route", (), {"search_queries": type("Search", (), {"backend": backend_name})()}
        )(),
    )
    monkeypatch.setattr(agent, "live_embedding_backend", _factory)
    monkeypatch.setattr(agent, "LiveDocumentFetcher", _LiveFetcher)
    monkeypatch.setattr(search_live, "live_search_backends", lambda: [])
    monkeypatch.setattr(agent, "OpenAIPlannerBackend", _factory)
    monkeypatch.setattr(
        search_generation,
        "ClaudeSearchGenerationBackend",
        lambda **_kwargs: _SelectedBackend("claude"),
    )
    monkeypatch.setattr(
        search_generation,
        "OpenAISearchGenerationBackend",
        lambda **_kwargs: _SelectedBackend("openai"),
    )
    for name in (
        "OpenAIThemeGroupingBackend",
        "OpenAIScreeningBackend",
        "OpenAIClassificationBackend",
        "OpenAIRankingBackend",
        "OpenAIExtractionBackend",
        "OpenAIFindingVetterBackend",
        "OpenAIICFExtractionBackend",
        "OpenAIICFFindingVetterBackend",
        "OpenAIGroupClusteringBackendFactory",
        "OpenAISynthesisBackend",
        "OpenAIGroundingJudgeBackend",
    ):
        monkeypatch.setattr(agent, name, _factory)

    _planner, backends = agent.live_planner_and_backends(None)

    assert cast("_SelectedBackend", backends.search_generation).name == expected
