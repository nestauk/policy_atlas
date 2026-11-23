"""The section loop sends the model's own earlier turns back, and nothing of them is kept.

The live backend runs against a fake Responses client; each model turn carries a
reasoning item with a marker, so a leak into a trace, a log or the transcript shows.
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Literal

import pytest
from structlog.testing import capture_logs

from policy_atlas.evidence_search.synthesis.section_prompt import (
    NOT_USED_TOOL_RESULT,
    SECTION_WRITE_TURN_MESSAGE,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import OpenAISynthesisBackend
from policy_atlas.evidence_search.synthesis.synthesis_tools import run_section_loop
from tests.helpers import FakeResponsesClient, _response, response_usage, text_stream_events

_MARKER = "ENCRYPTED-REASONING-MARKER"
_SEARCH_RESULT = {"chunks": [{"chunk_record_id": "chunk-1", "content": "Alpha evidence."}]}
_SECTION_JSON = json.dumps({"prose": "Housing improved.", "claims": []})


def _seed() -> dict[str, Any]:
    return {
        "section_index": 0,
        "intent": "What does evidence say?",
        "section": {"title": "Housing outcomes", "focus": "Housing.", "group_ids": ["g1"]},
        "corpus": {"screened": 2, "ingested": 1, "appraised": 1},
        "available_tools": ["search_chunks", "query_findings", "lookup"],
        "available_claim_types": ["chunk", "reasoning"],
        "substrate": {"grouping": {"groups": [{"group_id": "g1"}]}},
    }


def _turn(turn: int, *calls: tuple[str, Any]) -> Any:
    """A model turn: one reasoning item (with the marker), then the calls in order."""
    output: list[dict[str, Any]] = [
        {
            "type": "reasoning",
            "id": f"rs_{turn}",
            "summary": [],
            "encrypted_content": f"{_MARKER}-{turn}",
            "status": "completed",
        }
    ]
    output += [
        {
            "type": "function_call",
            "id": f"fc_{turn}_{index}",
            "call_id": f"call_t{turn}_{index}",
            "name": name,
            "arguments": json.dumps(arguments) if not isinstance(arguments, str) else arguments,
            "status": "completed",
        }
        for index, (name, arguments) in enumerate(calls)
    ]
    return _response(output, response_usage())


def _items(response: Any) -> list[dict[str, Any]]:
    """The output items as the module carries them (``status`` off non-messages)."""
    items = []
    for item in response.output:
        plain = item.model_dump(exclude_none=True)
        if plain["type"] != "message":
            plain.pop("status", None)
        items.append(plain)
    return items


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


def _run(*turns: Any) -> tuple[dict[str, Any], FakeResponsesClient, _Langfuse, list[Any]]:
    """Run one section loop whose model answers ``turns`` in order, then streams the section."""
    client = FakeResponsesClient(*turns, text_stream_events([_SECTION_JSON]))
    langfuse = _Langfuse()
    backend = OpenAISynthesisBackend(api_key="sk-test", langfuse_client=langfuse)  # type: ignore[arg-type]
    backend._client = client  # type: ignore[assignment]
    with capture_logs() as logs:
        result = run_section_loop(
            backend,
            seed=_seed(),
            tools={"search_chunks": lambda _arguments: _SEARCH_RESULT},
            turn_cap=6,
            langfuse_client=langfuse,
        )
    return dict(result), client, langfuse, logs


def _history(request: dict[str, Any]) -> list[Any]:
    """The request's input after the section prefix (system, run and task messages)."""
    history: list[Any] = request["input"][3:]
    return history


def _output(call_id: str, text: str) -> dict[str, Any]:
    return {"type": "function_call_output", "call_id": call_id, "output": text}


def _search_result_text() -> str:
    return json.dumps(_SEARCH_RESULT, ensure_ascii=False, sort_keys=True)


def test_a_read_turn_is_sent_back_with_its_results_on_the_next_turn_and_the_write() -> None:
    first = _turn(1, ("search_chunks", {"query": "housing"}))
    _result, client, _langfuse, _logs = _run(first, _turn(2, ("write_section", {})))

    carried = [*_items(first), _output("call_t1_0", _search_result_text())]
    assert _history(client.calls[1]) == carried
    assert client.calls[2]["stream"] is True
    assert _history(client.calls[2]) == [
        *carried,
        {"role": "user", "content": SECTION_WRITE_TURN_MESSAGE},
    ]


def test_a_call_the_loop_did_not_run_gets_the_not_used_result() -> None:
    first = _turn(1, ("search_chunks", {"query": "housing"}), ("write_section", {}))
    _result, client, _langfuse, _logs = _run(first, _turn(2, ("write_section", {})))

    assert _history(client.calls[1]) == [
        *_items(first),
        _output("call_t1_0", _search_result_text()),
        _output("call_t1_1", NOT_USED_TOOL_RESULT),
    ]


def test_the_ready_turn_is_never_sent_back() -> None:
    first = _turn(1, ("search_chunks", {"query": "housing"}))
    ready = _turn(2, ("write_section", {}))
    _result, client, _langfuse, _logs = _run(first, ready)

    sent = json.dumps(_history(client.calls[2]))
    assert "rs_2" not in sent
    assert "call_t2_0" not in sent


def test_a_malformed_emission_is_sent_back_with_its_error_as_that_calls_result() -> None:
    malformed = _turn(1, ("emit_section", "{not json"), ("write_section", {}))
    result, client, _langfuse, _logs = _run(malformed, _turn(2, ("write_section", {})))

    [error_exchange] = result["transcript"]
    assert error_exchange["tool"] == "emit_section"
    assert _history(client.calls[1]) == [
        *_items(malformed),
        _output(
            "call_t1_0",
            json.dumps(error_exchange["result"], ensure_ascii=False, sort_keys=True),
        ),
        _output("call_t1_1", NOT_USED_TOOL_RESULT),
    ]


def _leaks(value: Any) -> bool:
    text = json.dumps(value, default=repr, ensure_ascii=False)
    return any(
        marker in text
        for marker in (_MARKER, "Carried", "function_call_output", NOT_USED_TOOL_RESULT)
    )


@pytest.mark.parametrize("where", ["trace", "log", "transcript"])
def test_nothing_carried_reaches_a_trace_a_log_or_the_transcript(where: str) -> None:
    result, client, langfuse, logs = _run(
        _turn(1, ("search_chunks", {"query": "housing"}), ("write_section", {})),
        _turn(2, ("search_chunks", {"query": "more"})),
        _turn(3, ("write_section", {})),
    )
    # The carried turns did go out on the requests.
    assert _MARKER in json.dumps(client.calls[-1]["input"])

    if where == "trace":
        updates = [update for span in langfuse.spans for update in span.updates]
        assert updates
        assert not any(_leaks(update) for update in updates)
    elif where == "log":
        assert logs
        assert not any(_leaks(entry) for entry in logs)
    else:
        assert result["transcript"] == [
            {"tool": "search_chunks", "arguments": {"query": "housing"}, "result": _SEARCH_RESULT},
            {"tool": "search_chunks", "arguments": {"query": "more"}, "result": _SEARCH_RESULT},
        ]
        assert not _leaks(result)
