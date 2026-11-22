"""Shape tests for the OpenAI chat adapter's tool and streaming paths."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Literal, cast

import httpx
import openai
import pytest
from openai.types.responses.response import IncompleteDetails

from policy_atlas.core.openai_client import AnswerCutOff, ModelRefusal
from policy_atlas.core.usage import TokenUsage
from policy_atlas.runtime import chat_backend_openai
from policy_atlas.runtime.chat_backend import traceable_turn
from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend, _chat_messages
from policy_atlas.runtime.chat_prompt import ChatAnswerWire
from tests.helpers import (
    FakeResponsesClient,
    FakeStream,
    refusal_stream_events,
    response_usage,
    spy_calls,
    structured_response,
    text_stream_events,
    tool_call_response,
)


def _answer(request: dict[str, Any]) -> Any:
    """A streamed reply, a structured answer, or a read tool call, by request kind."""
    if request.get("stream"):
        return text_stream_events(["Hello ", "world."])
    if "text" in request:
        return structured_response(ChatAnswerWire(prose="Hello world.", citations=[], claims=[]))
    return tool_call_response(("search_chunks", '{"query":"q"}'))


def _backend(monkeypatch: pytest.MonkeyPatch) -> tuple[OpenAIChatBackend, dict[str, Any]]:
    """The backend, and the chat-style requests it hands to each model call, by call name."""
    backend = OpenAIChatBackend(api_key="test-key")
    backend._client = FakeResponsesClient(_answer)  # type: ignore[assignment]
    calls = {
        name: spy_calls(monkeypatch, chat_backend_openai, name)
        for name in ("send_turn", "stream_turn", "parse_structured")
    }
    return backend, calls


def test_live_adapter_uses_only_read_tools_for_non_terminal_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-terminal turns use the closed tool schema set and parse arguments."""
    backend, calls = _backend(monkeypatch)
    result, _ = backend.chat_turn(
        [{"role": "user", "content": "Question"}], [], force_emit=False, max_output_tokens=123
    )

    # ``carried`` is the in-memory model turn the loop sends back; not part of this check.
    assert traceable_turn(result) == {
        "answer": None,
        "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "q"}}],
    }
    call = calls["send_turn"][0]
    assert {tool["function"]["name"] for tool in call["tools"]} == {
        "search_chunks", "query_findings", "lookup"
    }
    assert call["max_completion_tokens"] == 123
    assert call["reasoning_effort"] == "none"


def test_live_adapter_streams_text_then_parses_atomic_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only prose chunks cross the callback; citations remain in the final parse."""
    backend, calls = _backend(monkeypatch)
    deltas: list[str] = []
    result, _ = backend.chat_turn(
        [{"role": "user", "content": "Question"}],
        [],
        force_emit=True,
        max_output_tokens=123,
        on_delta=deltas.append,
    )

    assert deltas == ["Hello ", "world."]
    assert result["answer"] is not None
    assert result["answer"].prose == "Hello world."
    # The streamed call goes through stream_turn, and the client is asked to stream.
    assert len(calls["stream_turn"]) == 1
    assert cast("Any", backend._client).calls[0]["stream"] is True
    assert calls["parse_structured"][0]["response_format"] is ChatAnswerWire
    assert calls["stream_turn"][0]["reasoning_effort"] == "none"
    assert calls["parse_structured"][0]["reasoning_effort"] == "none"


def test_tool_transcript_is_json_data_not_message_instructions() -> None:
    """Control characters remain JSON-encoded in the synthesis-precedent tool transcript."""
    messages = _chat_messages(
        [{"role": "system", "content": "rules"}],
        [
            {
                "tool": "search_chunks",
                "arguments": {"query": "q"},
                "result": {"content": "bad\u0007"},
            }
        ],
        force_emit=False,
    )

    assert messages[-1]["role"] == "tool"
    assert "\\u0007" in messages[-1]["content"]


_QUESTION = [{"role": "user", "content": "Question"}]


def _replying(*streams: Any) -> FakeResponsesClient:
    """A client that gives each scripted reply stream in turn, then structured answers."""
    queue = list(streams)

    def answer(request: dict[str, Any]) -> Any:
        if request.get("stream"):
            return queue.pop(0)
        return _answer(request)

    return FakeResponsesClient(answer)


def _live(client: FakeResponsesClient, monkeypatch: pytest.MonkeyPatch) -> tuple[
    OpenAIChatBackend, list[float]
]:
    backend = OpenAIChatBackend(api_key="test-key")
    backend._client = client  # type: ignore[assignment]
    waits: list[float] = []
    monkeypatch.setattr(chat_backend_openai, "time", SimpleNamespace(sleep=waits.append))
    return backend, waits


def _streams(client: FakeResponsesClient) -> int:
    return sum(1 for call in client.calls if call.get("stream"))


def _dropped() -> openai.APIConnectionError:
    return openai.APIConnectionError(request=httpx.Request("POST", "http://model.test"))


def test_a_reply_cut_off_at_the_token_limit_keeps_the_text_already_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _replying(text_stream_events(["Hello ", "world."], ending="incomplete"))
    backend, _waits = _live(client, monkeypatch)
    deltas: list[str] = []

    result, _usage = backend.chat_turn(
        _QUESTION, [], force_emit=True, max_output_tokens=123, on_delta=deltas.append
    )

    assert deltas == ["Hello ", "world."]
    assert result["answer"] is not None
    assert result["answer"].prose == "Hello world."
    assert _streams(client) == 1


def test_a_reply_that_fails_before_its_first_piece_is_tried_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = text_stream_events(["Hello ", "world."])
    client = _replying(FakeStream(events, fail_after=0, error=_dropped()), events)
    backend, waits = _live(client, monkeypatch)
    deltas: list[str] = []

    result, _usage = backend.chat_turn(
        _QUESTION, [], force_emit=True, max_output_tokens=123, on_delta=deltas.append
    )

    assert _streams(client) == 2
    assert deltas == ["Hello ", "world."]
    assert result["answer"] is not None
    assert result["answer"].prose == "Hello world."
    assert waits == [1.0]


def test_a_reply_that_fails_after_its_first_piece_is_not_tried_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = text_stream_events(["Hello ", "world."])
    client = _replying(FakeStream(events, fail_after=2, error=_dropped()), events)
    backend, waits = _live(client, monkeypatch)
    deltas: list[str] = []

    with pytest.raises(openai.APIConnectionError):
        backend.chat_turn(
            _QUESTION, [], force_emit=True, max_output_tokens=123, on_delta=deltas.append
        )
    assert _streams(client) == 1
    assert deltas == ["Hello "]
    assert waits == []


def test_the_answer_counts_the_reply_tokens_beside_the_parse_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reply = response_usage(input_tokens=100, output_tokens=40, cached=60)
    client = _replying(text_stream_events(["Hello ", "world."], usage=reply))
    backend, _waits = _live(client, monkeypatch)

    _result, usage = backend.chat_turn(
        _QUESTION, [], force_emit=True, max_output_tokens=123, on_delta=lambda _t: None
    )

    # The parse answer's usage is the builder's default: 10 in, 5 out.
    assert usage == TokenUsage(prompt=110, completion=45, total=155, cached=60, reasoning=0)


def _stopped_tool_turn(
    reason: Literal["max_output_tokens", "content_filter"],
    *calls: tuple[str, str],
    text: str = "",
) -> Any:
    """A tool turn the provider stopped for ``reason``, its items left incomplete."""
    answer = tool_call_response(*calls, text=text)
    return answer.model_copy(
        update={
            "status": "incomplete",
            "incomplete_details": IncompleteDetails(reason=reason),
            "output": [item.model_copy(update={"status": "incomplete"}) for item in answer.output],
        }
    )


def test_a_tool_turn_cut_off_at_the_token_limit_returns_its_call_with_empty_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cut = _stopped_tool_turn("max_output_tokens", ("search_chunks", '{"query": "unfini'))
    backend, _waits = _live(FakeResponsesClient(cut), monkeypatch)

    result, usage = backend.chat_turn(_QUESTION, [], force_emit=False, max_output_tokens=123)

    # The turn does not raise: the cut call comes back with empty arguments, and
    # with no ``carried`` entry.
    assert result == {"answer": None, "tool_calls": [{"tool": "search_chunks", "arguments": {}}]}
    assert usage == TokenUsage(prompt=10, completion=5, total=15, cached=0, reasoning=0)


def test_a_tool_turn_cut_off_before_any_tool_call_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cut = _stopped_tool_turn("max_output_tokens", text="Let me")
    backend, _waits = _live(FakeResponsesClient(cut), monkeypatch)

    with pytest.raises(AnswerCutOff):
        backend.chat_turn(_QUESTION, [], force_emit=False, max_output_tokens=123)


def test_a_tool_turn_stopped_by_the_content_filter_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped = _stopped_tool_turn("content_filter", ("search_chunks", '{"query": "q'))
    backend, _waits = _live(FakeResponsesClient(stopped), monkeypatch)

    with pytest.raises(ModelRefusal):
        backend.chat_turn(_QUESTION, [], force_emit=False, max_output_tokens=123)


def test_a_reply_refused_before_any_text_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    backend, _waits = _live(_replying(refusal_stream_events()), monkeypatch)

    with pytest.raises(ModelRefusal):
        backend.chat_turn(_QUESTION, [], force_emit=True, max_output_tokens=123)


def test_a_reply_refused_after_its_first_piece_keeps_that_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = [*text_stream_events(["Hello "])[:-1], *refusal_stream_events()[1:]]
    backend, _waits = _live(_replying(events), monkeypatch)
    deltas: list[str] = []

    result, _usage = backend.chat_turn(
        _QUESTION, [], force_emit=True, max_output_tokens=123, on_delta=deltas.append
    )

    assert deltas == ["Hello "]
    assert result["answer"] is not None
    assert result["answer"].prose == "Hello "
