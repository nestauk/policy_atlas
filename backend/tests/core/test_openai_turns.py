"""The shared model calls on a real SDK client, against the Responses endpoint.

The client's network layer is an ``httpx.MockTransport``: nothing leaves the machine,
and each test sees the exact request body the SDK sent, with its timeout.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any, cast

import httpx
import openai
import pytest
from openai.types.responses.response import IncompleteDetails
from pydantic import BaseModel
from structlog.testing import capture_logs

from policy_atlas.core import tracing
from policy_atlas.core.openai_client import (
    AnswerCutOff,
    ModelRefusal,
    ModelTurn,
    ToolCall,
    parse_structured,
    send_turn,
    stream_turn,
)
from policy_atlas.core.usage import TokenUsage
from tests.helpers import (
    cut_off_response,
    refusal_response,
    refusal_stream_events,
    response_usage,
    structured_response,
    text_response,
    text_stream_events,
    tool_call_response,
)

_USAGE = response_usage(input_tokens=11, output_tokens=7, cached=4, cache_write=2, reasoning=3)
_TOKENS = TokenUsage(prompt=11, completion=7, total=18, cached=4, cache_write=2, reasoning=3)
_PARAMETERS = {"type": "object", "properties": {"q": {"type": "string"}}}
_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "lookup",
            "description": "Look a thing up.",
            "parameters": _PARAMETERS,
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
            yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n".encode()

    def close(self) -> None:
        self._closed = True


def _client(
    respond: Callable[[], httpx.Response],
) -> tuple[openai.OpenAI, list[dict[str, Any]]]:
    sent: list[dict[str, Any]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        sent.append(
            {
                "path": request.url.path,
                **json.loads(request.content),
                "timeout": request.extensions["timeout"],
            }
        )
        return respond()

    client = openai.OpenAI(
        api_key="throwaway",
        base_url="http://model.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handle)),
    )
    return client, sent


def _streaming(events: list[Any]) -> Callable[[], httpx.Response]:
    wire = [event if isinstance(event, dict) else event.to_dict() for event in events]
    return lambda: httpx.Response(
        200, headers={"content-type": "text/event-stream"}, stream=_Wire(wire)
    )


def _stream(events: list[Any]) -> Any:
    client, _sent = _client(_streaming(events))
    return stream_turn(client, label="test stream", model="gpt-test", messages=[])


def test_send_turn_translates_the_request_and_reads_text_tool_calls_and_usage() -> None:
    answer = tool_call_response(("lookup", {"q": "x"}), text="thinking aloud", usage=_USAGE)
    client, sent = _client(lambda: httpx.Response(200, json=answer.to_dict()))

    turn = send_turn(
        client,
        label="test turn",
        model="gpt-test",
        messages=[
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "find x"},
        ],
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
        tool_calls=(ToolCall(name="lookup", arguments='{"q": "x"}', call_id="call_0"),),
        usage=_TOKENS,
        carried=turn.carried,
    )
    assert sent == [
        {
            "path": "/v1/responses",
            "model": "gpt-test",
            "input": [
                {"role": "system", "content": "be brief"},
                {"role": "user", "content": "find x"},
            ],
            "reasoning": {"effort": "low"},
            "tools": [
                {
                    "type": "function",
                    "name": "lookup",
                    "description": "Look a thing up.",
                    "parameters": _PARAMETERS,
                    "strict": False,
                }
            ],
            "tool_choice": "required",
            "parallel_tool_calls": True,
            "max_output_tokens": 500,
            "include": ["reasoning.encrypted_content"],
            "store": False,
            "prompt_cache_options": {"mode": "explicit"},
            "timeout": {"connect": 30, "read": 30, "write": 30, "pool": 30},
        }
    ]


class _Answer(BaseModel):
    text: str


def test_parse_structured_sends_the_class_schema_and_parses_the_answer_text() -> None:
    client, sent = _client(
        lambda: httpx.Response(200, json=structured_response(_Answer(text="hi")).to_dict())
    )

    parsed, usage = parse_structured(
        client,
        messages=[{"role": "user", "content": "say hi"}],
        response_format=_Answer,
        usage_event="test.usage",
        label="test parse",
        model="gpt-test",
        reasoning_effort="none",
        prompt_cache="auto",
        timeout_s=20,
        max_completion_tokens=100,
    )

    assert parsed == _Answer(text="hi")
    assert usage == TokenUsage(prompt=10, completion=5, total=15, cached=0, reasoning=0)
    text_format = sent[0]["text"]["format"]
    assert (text_format["type"], text_format["name"], text_format["strict"]) == (
        "json_schema",
        "_Answer",
        True,
    )
    assert text_format["schema"]["properties"] == {"text": {"title": "Text", "type": "string"}}
    assert sent[0]["store"] is False


def test_parse_structured_with_no_answer_text_is_not_parsed() -> None:
    client, _sent = _client(lambda: httpx.Response(200, json=text_response("").to_dict()))

    with pytest.raises(RuntimeError, match="test parse response was not parsed"):
        parse_structured(
            client,
            messages=[{"role": "user", "content": "say hi"}],
            response_format=_Answer,
            usage_event="test.usage",
            label="test parse",
            model="gpt-test",
            reasoning_effort="none",
            prompt_cache="auto",
            timeout_s=20,
        )


def test_a_completed_stream_yields_text_pieces_in_order_and_usage_after_the_loop() -> None:
    client, sent = _client(_streaming(text_stream_events(["Hel", "", "lo"], usage=_USAGE)))

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
    assert stream.usage == _TOKENS
    assert stream.carried is not None
    assert sent[0]["stream"] is True
    assert sent[0]["store"] is False
    assert "stream_options" not in sent[0]


def test_a_stream_cut_off_hands_out_its_text_then_raises_answer_cut_off() -> None:
    stream = _stream(text_stream_events(["cut ", "off"], ending="incomplete", usage=_USAGE))
    pieces: list[str] = []

    with pytest.raises(AnswerCutOff) as caught:
        pieces.extend(stream)
    assert pieces == ["cut ", "off"]
    assert stream.usage == _TOKENS
    assert (caught.value.label, caught.value.usage) == ("test stream", _TOKENS)
    assert not tracing._retryable(caught.value)


def test_a_refused_stream_raises_model_refusal_when_the_loop_ends() -> None:
    stream = _stream(refusal_stream_events())

    with pytest.raises(ModelRefusal) as caught:
        list(stream)
    assert caught.value.label == "test stream"
    assert not tracing._retryable(caught.value)


def _parse(client: openai.OpenAI) -> Any:
    return parse_structured(
        client,
        messages=[{"role": "user", "content": "say hi"}],
        response_format=_Answer,
        usage_event="test.usage",
        label="test parse",
        model="gpt-test",
        reasoning_effort="none",
        prompt_cache="auto",
        timeout_s=20,
    )


def test_parse_structured_cut_off_raises_answer_cut_off_and_logs_usage() -> None:
    client, _sent = _client(
        lambda: httpx.Response(200, json=cut_off_response('{"text": "h', usage=_USAGE).to_dict())
    )

    with capture_logs() as logs, pytest.raises(AnswerCutOff) as caught:
        _parse(client)
    assert (caught.value.label, caught.value.usage) == ("test parse", _TOKENS)
    assert [entry["event"] for entry in logs] == ["test.usage"]
    assert not tracing._retryable(caught.value)


def test_parse_structured_refusal_raises_model_refusal() -> None:
    client, _sent = _client(lambda: httpx.Response(200, json=refusal_response().to_dict()))

    with pytest.raises(ModelRefusal) as caught:
        _parse(client)
    assert caught.value.label == "test parse"


def test_send_turn_cut_off_raises_answer_cut_off() -> None:
    client, _sent = _client(
        lambda: httpx.Response(200, json=cut_off_response("half", usage=_USAGE).to_dict())
    )

    with pytest.raises(AnswerCutOff) as caught:
        send_turn(client, label="test turn", model="gpt-test", messages=[])
    assert (caught.value.label, caught.value.usage) == ("test turn", _TOKENS)


def test_send_turn_refusal_raises_model_refusal() -> None:
    client, _sent = _client(lambda: httpx.Response(200, json=refusal_response().to_dict()))

    with pytest.raises(ModelRefusal) as caught:
        send_turn(client, label="test turn", model="gpt-test", messages=[])
    assert caught.value.label == "test turn"


@pytest.mark.parametrize(
    "final",
    [
        text_stream_events([], ending="failed")[-1],
        {"type": "error", "code": "server_error", "message": "boom", "sequence_number": 1},
    ],
    ids=["failed", "error"],
)
def test_a_failed_stream_raises_a_provider_error_that_is_not_tried_again(final: Any) -> None:
    stream = _stream([*text_stream_events(["Hel"])[:-1], final])
    pieces = iter(stream)

    assert next(pieces) == "Hel"
    with pytest.raises(openai.APIError) as caught:
        next(pieces)
    assert not isinstance(caught.value, openai.APIConnectionError)
    assert not tracing._retryable(caught.value)


def test_a_stream_with_no_final_event_raises_a_connection_error() -> None:
    stream = _stream(text_stream_events(["Hel", "lo"])[:-1])

    with pytest.raises(openai.APIConnectionError) as caught:
        list(stream)
    assert tracing._retryable(caught.value)


@pytest.mark.parametrize("call", [send_turn, stream_turn])
def test_an_unknown_request_key_raises_type_error(call: Callable[..., Any]) -> None:
    client, sent = _client(lambda: httpx.Response(500))

    with pytest.raises(TypeError, match="temperature"):
        call(client, label="test", model="gpt-test", messages=[], temperature=0)
    assert sent == []


def test_close_stops_a_stream_quietly() -> None:
    stream = _stream(text_stream_events(list("abcdef")))
    pieces = iter(stream)

    assert next(pieces) == "a"
    stream.close()
    assert list(pieces) == []


def test_a_failed_answer_raises_a_provider_error_with_its_message() -> None:
    failed = cast(Any, text_stream_events([], ending="failed")[-1]).response
    client, _sent = _client(lambda: httpx.Response(200, json=failed.to_dict()))

    with pytest.raises(openai.APIError, match="The model failed") as caught:
        send_turn(client, label="test turn", model="gpt-test", messages=[])
    assert not tracing._retryable(caught.value)


def test_an_answer_stopped_by_the_content_filter_raises_model_refusal() -> None:
    answer = cut_off_response("half").model_copy(
        update={"incomplete_details": IncompleteDetails(reason="content_filter")}
    )
    client, _sent = _client(lambda: httpx.Response(200, json=answer.to_dict()))

    with pytest.raises(ModelRefusal, match="content_filter"):
        send_turn(client, label="test turn", model="gpt-test", messages=[])


def test_extra_body_keys_other_than_the_prompt_cache_options_raise_type_error() -> None:
    client, sent = _client(lambda: httpx.Response(500))

    with pytest.raises(TypeError, match="store"):
        send_turn(client, label="test", model="gpt-test", messages=[], extra_body={"store": True})
    assert sent == []
