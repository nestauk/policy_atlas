"""Carried turns: an answer's output items handed back on the next request of a tool loop."""

from __future__ import annotations

from typing import Any

import pytest

from policy_atlas.core.openai_client import send_turn, stream_turn
from tests.helpers import FakeResponsesClient, text_stream_events, tool_call_response

_TOOLS = [
    {
        "type": "function",
        "function": {"name": "lookup", "parameters": {"type": "object", "properties": {}}},
    }
]


def _tool_turn(client: FakeResponsesClient, **request: Any) -> Any:
    return send_turn(client, label="test turn", model="gpt-test", **request)


def _carried_turn() -> Any:
    client = FakeResponsesClient(
        tool_call_response(("lookup", {"q": "a"}), ("lookup", {"q": "b"}), text="let me look")
    )
    turn = _tool_turn(client, messages=[{"role": "user", "content": "hi"}])
    assert turn.carried is not None
    return turn.carried


def test_status_is_removed_from_items_that_are_not_messages_and_kept_on_messages() -> None:
    carried = _carried_turn()

    assert [(item["type"], "status" in item) for item in carried.items] == [
        ("message", True),
        ("function_call", False),
        ("function_call", False),
    ]


def test_a_call_with_no_result_raises() -> None:
    with pytest.raises(ValueError, match="missing"):
        _carried_turn().with_results({"call_0": "result a"})


def test_a_result_for_a_call_the_turn_did_not_make_raises() -> None:
    with pytest.raises(ValueError, match="unknown"):
        _carried_turn().with_results({"call_0": "a", "call_1": "b", "call_9": "c"})


def test_an_entry_expands_to_the_carried_items_then_one_result_per_call_in_place() -> None:
    carried = _carried_turn()
    entry = carried.with_results({"call_1": "result b", "call_0": "result a"})
    client = FakeResponsesClient(tool_call_response(("lookup", {})))

    _tool_turn(
        client,
        messages=[
            {"role": "system", "content": "be brief"},
            entry,
            {"role": "user", "content": "now write"},
        ],
    )

    assert client.calls[0]["input"] == [
        {"role": "system", "content": "be brief"},
        *carried.items,
        {"type": "function_call_output", "call_id": "call_0", "output": "result a"},
        {"type": "function_call_output", "call_id": "call_1", "output": "result b"},
        {"role": "user", "content": "now write"},
    ]


@pytest.mark.parametrize(
    ("effort", "tools", "include_sent"),
    [
        ("low", _TOOLS, True),
        ("none", _TOOLS, False),
        ("low", None, False),
        (None, _TOOLS, False),
    ],
    ids=["effort-and-tools", "effort-none", "no-tools", "no-effort"],
)
def test_reasoning_is_asked_back_exactly_when_effort_is_above_none_and_tools_are_sent(
    effort: str | None, tools: list[dict[str, Any]] | None, include_sent: bool
) -> None:
    client = FakeResponsesClient(tool_call_response(("lookup", {})))
    request: dict[str, Any] = {"messages": [{"role": "user", "content": "hi"}]}
    if effort is not None:
        request["reasoning_effort"] = effort
    if tools is not None:
        request["tools"] = tools

    _tool_turn(client, **request)

    assert ("include" in client.calls[0]) is include_sent
    if include_sent:
        assert client.calls[0]["include"] == ["reasoning.encrypted_content"]


def test_a_stream_carries_the_items_of_its_completed_event() -> None:
    client = FakeResponsesClient(text_stream_events(["Hel", "lo"]))
    stream = stream_turn(client, label="test stream", model="gpt-test", messages=[])

    assert stream.carried is None
    assert list(stream) == ["Hel", "lo"]
    assert stream.carried is not None
    assert [item["type"] for item in stream.carried.items] == ["message"]


def test_a_carried_turn_with_unanswered_calls_cannot_be_sent() -> None:
    client = FakeResponsesClient(tool_call_response(("lookup", {})))

    with pytest.raises(ValueError, match="unanswered"):
        _tool_turn(client, messages=[_carried_turn()])
    assert client.calls == []


def test_the_repr_of_a_carried_turn_shows_only_the_item_count() -> None:
    carried = _carried_turn()
    entry = carried.with_results({"call_0": "a", "call_1": "b"})

    assert repr(carried) == "CarriedTurn(3 items)"
    assert repr(entry) == "CarriedTurn(5 items)"
    assert "let me look" not in f"{carried} {entry}"
