"""A chat answer sends the model's own earlier tool turns back, and nothing of them is kept.

The live chat backend runs against a fake Responses client; each tool turn carries
a reasoning item with a marker, so a leak into a trace, a log or a stored row shows.
"""

from __future__ import annotations

import json
import uuid
from types import TracebackType
from typing import Any, Literal

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from structlog.testing import capture_logs

from policy_atlas.api import answer_core, chat_turns
from policy_atlas.core.schema import chat_turn, event_log
from policy_atlas.runtime.chat_backend_openai import OpenAIChatBackend
from policy_atlas.runtime.chat_prompt import ChatAnswerWire, ChatCitationWire
from tests.api.test_chat_turns import _chat, _citable_tools, _walk
from tests.helpers import (
    FakeResponsesClient,
    _response,
    response_usage,
    structured_response,
    text_stream_events,
)
from tests.runtime.test_runner import _cleanup

_MARKER = "ENCRYPTED-REASONING-MARKER"
_PROSE = "The evidence addresses this [1]."
_SEARCH_RESULT_TEXT = json.dumps(
    _citable_tools()["search_chunks"]({}), ensure_ascii=False, sort_keys=True
)


class _Model:
    """Answers tool turns with a marked reasoning item and one search, then the reply."""

    def __init__(self) -> None:
        self.tool_turns: list[Any] = []

    def __call__(self, request: dict[str, Any]) -> Any:
        if request.get("stream"):
            return text_stream_events([_PROSE])
        if "text" in request:
            return structured_response(
                ChatAnswerWire(
                    prose=_PROSE,
                    citations=[ChatCitationWire(id="test-chunk", quote="Evidence text.")],
                    claims=[],
                )
            )
        turn = len(self.tool_turns) + 1
        response = _response(
            [
                {
                    "type": "reasoning",
                    "id": f"rs_{turn}",
                    "summary": [],
                    "encrypted_content": f"{_MARKER}-{turn}",
                    "status": "completed",
                },
                {
                    "type": "function_call",
                    "id": f"fc_{turn}",
                    "call_id": f"call_t{turn}",
                    "name": "search_chunks",
                    "arguments": json.dumps({"query": f"q{turn}"}),
                    "status": "completed",
                },
            ],
            response_usage(),
        )
        self.tool_turns.append(response)
        return response


def _items(response: Any) -> list[dict[str, Any]]:
    """The output items as the module carries them (``status`` off non-messages)."""
    items = []
    for item in response.output:
        plain = item.model_dump(exclude_none=True)
        if plain["type"] != "message":
            plain.pop("status", None)
        items.append(plain)
    return items


def _carried(model: _Model, turns: int) -> list[dict[str, Any]]:
    """The first ``turns`` tool turns as carried items, each followed by its result."""
    out: list[dict[str, Any]] = []
    for number, response in enumerate(model.tool_turns[:turns], start=1):
        out += _items(response)
        out.append(
            {
                "type": "function_call_output",
                "call_id": f"call_t{number}",
                "output": _SEARCH_RESULT_TEXT,
            }
        )
    return out


class _Span:
    def __init__(self) -> None:
        self.updates: list[dict[str, Any]] = []

    def update(self, **payload: Any) -> None:
        self.updates.append(payload)


class _Observation:
    def __init__(self, span: _Span) -> None:
        self._span = span

    def __enter__(self) -> _Span:
        return self._span

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        return False


class _Langfuse:
    def __init__(self) -> None:
        self.spans: list[_Span] = []

    def start_as_current_observation(self, *, name: str, as_type: str) -> _Observation:
        del name, as_type
        span = _Span()
        self.spans.append(span)
        return _Observation(span)


def _leaks(value: Any) -> bool:
    text = json.dumps(value, default=repr, ensure_ascii=False)
    return any(marker in text for marker in (_MARKER, "Carried", "function_call_output"))


@pytest.fixture
def answered(
    engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> Any:
    """Two chat answers in one conversation on the live backend; yields what they left."""
    task_id: uuid.UUID | None = None
    try:
        task_id, scope_id, conversation_id = _chat(engine)
        _walk(engine, task_id=task_id, scope_id=scope_id, status="succeeded")
        monkeypatch.setattr(answer_core, "build_section_tools", _citable_tools)
        model = _Model()
        langfuse = _Langfuse()
        backend = OpenAIChatBackend(api_key="test-key", langfuse_client=langfuse)  # type: ignore[arg-type]
        client = FakeResponsesClient(model)
        backend._client = client  # type: ignore[assignment]
        with capture_logs() as logs:
            for question in ("What does the evidence say?", "And what else?"):
                chat_turns.run_chat_turn(
                    engine,
                    task_id=task_id,
                    conversation_id=conversation_id,
                    user_id="chat-owner",
                    message=question,
                    client_turn_id=uuid.uuid4(),
                    chat_backend=backend,
                    langfuse_client=langfuse,
                )
        with engine.connect() as conn:
            rows = [
                dict(row)
                for table, column in ((chat_turn, chat_turn.c.conversation_id), (event_log, None))
                for row in conn.execute(
                    select(table).where(
                        column == conversation_id if column is not None
                        else event_log.c.task_id == task_id
                    )
                ).mappings()
            ]
        yield {"model": model, "client": client, "langfuse": langfuse, "logs": logs, "rows": rows}
    finally:
        _cleanup(engine, task_id)


def _first_answer_requests(client: FakeResponsesClient) -> list[dict[str, Any]]:
    """The requests of the first answer: its tool turns, then the reply and the parse."""
    end = next(index for index, call in enumerate(client.calls) if "text" in call)
    return client.calls[: end + 1]


def test_each_tool_turn_reaches_the_next_tool_turn_with_its_result(answered: Any) -> None:
    tool_requests = [
        call
        for call in _first_answer_requests(answered["client"])
        if not call.get("stream") and "text" not in call
    ]
    assert len(tool_requests) >= 2
    second = tool_requests[1]["input"]
    carried = _carried(answered["model"], 1)
    assert second[-len(carried):] == carried


@pytest.mark.parametrize("request_kind", ["reply", "parse"])
def test_every_tool_turn_reaches_the_reply_and_the_parse(
    answered: Any, request_kind: str
) -> None:
    requests = _first_answer_requests(answered["client"])
    tool_turns = len([call for call in requests if not call.get("stream") and "text" not in call])
    [request] = [
        call
        for call in requests
        if (call.get("stream") if request_kind == "reply" else "text" in call)
    ]
    sent = request["input"]
    carried = _carried(answered["model"], tool_turns)
    start = sent.index(carried[0])
    assert sent[start : start + len(carried)] == carried


def test_the_next_answer_starts_from_the_stored_history_with_nothing_carried(
    answered: Any,
) -> None:
    calls = answered["client"].calls
    first_of_second = calls[len(_first_answer_requests(answered["client"]))]
    assert _MARKER not in json.dumps(first_of_second["input"])


@pytest.mark.parametrize("where", ["trace", "log", "stored rows"])
def test_nothing_carried_reaches_a_trace_a_log_or_a_stored_row(
    answered: Any, where: str
) -> None:
    # The carried turns did go out on the requests.
    assert _MARKER in json.dumps(answered["client"].calls[-1]["input"])
    if where == "trace":
        values = [update for span in answered["langfuse"].spans for update in span.updates]
    elif where == "log":
        values = answered["logs"]
    else:
        values = answered["rows"]
    assert values
    assert not any(_leaks(value) for value in values)
