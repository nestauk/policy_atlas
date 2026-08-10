"""Shape tests for the OpenAI chat adapter's tool and streaming paths."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend, _chat_messages
from policy_atlas.runtime.chat_prompt import ChatAnswerWire
from tests.helpers import FakeChoice, FakeParsedMessage, FakeParseResponse


@dataclass
class _Function:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    function: _Function


@dataclass
class _ToolMessage:
    tool_calls: list[_ToolCall]


@dataclass
class _ToolChoice:
    message: _ToolMessage


@dataclass
class _ToolResponse:
    choices: list[_ToolChoice]
    usage: Any = None


@dataclass
class _Delta:
    content: str | None


@dataclass
class _StreamChoice:
    delta: _Delta


@dataclass
class _Chunk:
    choices: list[_StreamChoice]


class _Completions:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, Any]] = []
        self.parse_calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.create_calls.append(kwargs)
        if kwargs.get("stream"):
            return iter(
                [
                    _Chunk([_StreamChoice(_Delta("Hello "))]),
                    _Chunk([_StreamChoice(_Delta("world."))]),
                ]
            )
        return _ToolResponse(
            [_ToolChoice(_ToolMessage([_ToolCall(_Function("search_chunks", '{"query":"q"}'))]))]
        )

    def parse(self, **kwargs: Any) -> FakeParseResponse:
        self.parse_calls.append(kwargs)
        return FakeParseResponse(
            choices=[FakeChoice(message=FakeParsedMessage(ChatAnswerWire(
                prose="Hello world.", citations=[], claims=[]
            )))],
            usage=None,
        )


class _Client:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": _Completions()})()


def _backend() -> tuple[OpenAIChatBackend, _Completions]:
    backend = OpenAIChatBackend(api_key="test-key")
    client = _Client()
    backend._client = client  # type: ignore[assignment]
    return backend, client.chat.completions


def test_live_adapter_uses_only_read_tools_for_non_terminal_turn() -> None:
    """Non-terminal turns use the closed tool schema set and parse arguments."""
    backend, completions = _backend()
    result, _ = backend.chat_turn(
        [{"role": "user", "content": "Question"}], [], force_emit=False, max_output_tokens=123
    )

    assert result == {
        "answer": None,
        "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "q"}}],
    }
    call = completions.create_calls[0]
    assert {tool["function"]["name"] for tool in call["tools"]} == {
        "search_chunks", "query_findings", "lookup"
    }
    assert call["max_completion_tokens"] == 123


def test_live_adapter_streams_text_then_parses_atomic_answer() -> None:
    """Only prose chunks cross the callback; citations remain in the final parse."""
    backend, completions = _backend()
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
    assert completions.create_calls[0]["stream"] is True
    assert completions.parse_calls[0]["response_format"] is ChatAnswerWire


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
