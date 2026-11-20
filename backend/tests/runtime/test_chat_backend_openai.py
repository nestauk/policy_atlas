"""Shape tests for the OpenAI chat adapter's tool and streaming paths."""

from __future__ import annotations

from typing import Any, cast

import pytest

from policy_atlas.runtime import chat_backend_openai
from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend, _chat_messages
from policy_atlas.runtime.chat_prompt import ChatAnswerWire
from tests.helpers import (
    FakeResponsesClient,
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

    assert result == {
        "answer": None,
        "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "q"}}],
    }
    call = calls["send_turn"][0]
    assert {tool["function"]["name"] for tool in call["tools"]} == {
        "search_chunks", "query_findings", "lookup"
    }
    assert call["max_completion_tokens"] == 123
    # Pin regression: gpt-5.6-terra 400s on function tools without this (H3 live check).
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
    # Pin regression: gpt-5.6-terra 400s on function tools without this (H3 live check) —
    # both the streamed-prose call and the structured-parse call carry the pin.
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
