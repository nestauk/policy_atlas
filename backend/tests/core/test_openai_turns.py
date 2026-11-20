"""The two shared model calls, ``send_turn`` and ``stream_turn``, on a real SDK client.

The client's network layer is an ``httpx.MockTransport``: nothing leaves the machine,
and each test sees the exact request body the SDK sent, with its timeout.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import openai
import pytest

from policy_atlas.core.openai_client import (
    ModelTurn,
    ToolCall,
    send_turn,
    stream_turn,
)
from policy_atlas.core.usage import TokenUsage

_USAGE = {
    "prompt_tokens": 11,
    "completion_tokens": 7,
    "total_tokens": 18,
    "prompt_tokens_details": {"cached_tokens": 4},
    "completion_tokens_details": {"reasoning_tokens": 3},
}
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Look a thing up.",
            "parameters": {"type": "object", "properties": {"q": {"type": "string"}}},
        },
    }
]


class _Wire(httpx.SyncByteStream):
    """Server-sent events that stop arriving once the response is closed."""

    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self._closed = False

    def __iter__(self) -> Iterator[bytes]:
        for event in self._events:
            if self._closed:
                return
            yield f"data: {json.dumps(event)}\n\n".encode()
        yield b"data: [DONE]\n\n"

    def close(self) -> None:
        self._closed = True


def _client(
    respond: Callable[[], httpx.Response],
) -> tuple[openai.OpenAI, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append({**json.loads(request.content), "timeout": request.extensions["timeout"]})
        return respond()

    client = openai.OpenAI(
        api_key="throwaway",
        base_url="http://model.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    return client, sent


def _chunk(content: str | None, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    choices = [] if content is None else [{"index": 0, "delta": {"content": content}}]
    return {
        "id": "chunk",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "gpt-test",
        "choices": choices,
        "usage": usage,
    }


def _streaming(events: list[dict[str, Any]]) -> Callable[[], httpx.Response]:
    return lambda: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=_Wire(events)
    )


def test_send_turn_reads_text_tool_calls_and_usage_and_sends_the_request_unchanged() -> None:
    completion = {
        "id": "cmpl",
        "object": "chat.completion",
        "created": 0,
        "model": "gpt-test",
        "choices": [
            {
                "index": 0,
                "finish_reason": "tool_calls",
                "message": {
                    "role": "assistant",
                    "content": "thinking aloud",
                    "tool_calls": [
                        {
                            "id": "call_abc",
                            "type": "function",
                            "function": {"name": "lookup", "arguments": '{"q": "x"}'},
                        }
                    ],
                },
            }
        ],
        "usage": _USAGE,
    }
    client, sent = _client(lambda: httpx.Response(200, json=completion))
    messages = [
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "find x"},
    ]

    turn = send_turn(
        client,
        label="test turn",
        model="gpt-test",
        messages=messages,
        reasoning_effort="low",
        timeout=30,
        extra_body={"prompt_cache_options": {"mode": "explicit"}},
        tools=_TOOLS,
        tool_choice="required",
        parallel_tool_calls=True,
        max_completion_tokens=500,
    )

    assert turn == ModelTurn(
        text="thinking aloud",
        tool_calls=(ToolCall(name="lookup", arguments='{"q": "x"}', call_id="call_abc"),),
        usage=TokenUsage(prompt=11, completion=7, total=18, cached=4, reasoning=3),
    )
    assert sent == [
        {
            "model": "gpt-test",
            "messages": messages,
            "reasoning_effort": "low",
            "tools": _TOOLS,
            "tool_choice": "required",
            "parallel_tool_calls": True,
            "max_completion_tokens": 500,
            "prompt_cache_options": {"mode": "explicit"},
            "timeout": {"connect": 30, "read": 30, "write": 30, "pool": 30},
        }
    ]


def test_stream_turn_yields_text_pieces_in_order_and_usage_after_the_loop() -> None:
    events = [_chunk("Hel"), _chunk(""), _chunk("lo"), _chunk(None, usage=_USAGE)]
    client, sent = _client(_streaming(events))

    stream = stream_turn(
        client,
        label="test stream",
        model="gpt-test",
        messages=[{"role": "user", "content": "hi"}],
        reasoning_effort="low",
        timeout=30,
        stream_options={"include_usage": True},
    )

    assert list(stream) == ["Hel", "lo"]
    assert stream.usage == TokenUsage(prompt=11, completion=7, total=18, cached=4, reasoning=3)
    assert stream.carried is None
    assert sent[0]["stream"] is True
    assert sent[0]["stream_options"] == {"include_usage": True}


@pytest.mark.parametrize("call", [send_turn, stream_turn])
def test_an_unknown_request_key_raises_type_error(call: Callable[..., Any]) -> None:
    client, sent = _client(lambda: httpx.Response(500))

    with pytest.raises(TypeError, match="temperature"):
        call(client, label="test", model="gpt-test", messages=[], temperature=0)
    assert sent == []


def test_close_stops_a_stream() -> None:
    client, _sent = _client(_streaming([_chunk(piece) for piece in "abcdef"]))
    stream = stream_turn(client, label="test stream", model="gpt-test", messages=[])
    pieces = iter(stream)

    assert next(pieces) == "a"
    stream.close()
    assert list(pieces) == []
