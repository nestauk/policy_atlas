"""The section writer's request shape (task 056 D8, D10, X3).

D8: the run message is one text content part carrying an explicit cache
breakpoint. D10: the section turns and the repair start with byte-identical
messages and send the same five tools with parallel tool calls on; only
``tool_choice`` differs; a forced turn or repair that returns several calls
takes the first forced one and counts the rest. X3: the ``lookup`` tool offers
only the kinds the run can serve.
"""

from __future__ import annotations

import json
import uuid
from threading import Lock
from types import TracebackType
from typing import Any, Literal, cast

import pytest
from structlog.testing import capture_logs

from policy_atlas.evidence_search.synthesis.section_prompt import (
    LOOKUP_RUN_KINDS_SENTENCE,
    LOOKUP_TOOL_KINDS,
    LOOKUP_TOOL_SCHEMA,
    SECTION_REPAIR_PROMPT_VERSION,
    SECTION_RUN_TEMPLATE,
    build_section_messages,
    build_section_prefix,
    build_section_repair_messages,
    lookup_tool_schema,
    section_request_tools,
)
from policy_atlas.evidence_search.synthesis.synthesis_backend import OpenAISynthesisBackend
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    LOOKUP_QUERY_KINDS,
    available_lookup_kinds,
    run_section_loop,
)

_SECTION_TOOLS = ["search_chunks", "query_findings", "lookup", "emit_section"]
_REQUEST_TOOLS = [*_SECTION_TOOLS, "emit_repairs"]
_FAILING = [
    {
        "claim_id": "s0c0",
        "claim": {"claim_type": "reasoning", "text": "Too strong."},
        "failure_reason": "overstates",
        "replacement_span": None,
        "paragraph_context": None,
        "dependencies": {},
    }
]


def _seed(
    *, lookup_kinds: list[str] | None = None, section_title: str = "Housing"
) -> dict[str, Any]:
    seed: dict[str, Any] = {
        "section_index": 0,
        "intent": "What does evidence say?",
        "section": {"title": section_title, "focus": "Evidence.", "group_ids": ["g1"]},
        "corpus": {"screened": 2, "ingested": 1, "appraised": 1},
        "available_tools": ["search_chunks", "query_findings", "lookup"],
        "available_claim_types": ["chunk", "finding", "gap", "reasoning"],
        "substrate": {"grouping": {"groups": [{"group_id": "g1"}]}},
        "computed_spread": {"increase": 2},
        "member_findings": [{"finding_id": "iof:f1"}],
        "ledger": [],
    }
    if lookup_kinds is not None:
        seed["available_lookup_kinds"] = lookup_kinds
    return seed


# --- Fakes: a recording chat-completions client and a Langfuse span recorder ---


class _Function:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.function = _Function(name, json.dumps(arguments))


class _Response:
    def __init__(self, tool_calls: list[_ToolCall]) -> None:
        message = type("M", (), {"tool_calls": tool_calls})()
        self.choices = [type("C", (), {"message": message})()]
        self.usage = None


class _Completions:
    def __init__(self, tool_calls: list[_ToolCall]) -> None:
        self.tool_calls = tool_calls
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return _Response(self.tool_calls)


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
        self.spans: list[tuple[str, _Span]] = []

    def start_as_current_observation(self, *, name: str, as_type: str) -> _Observation:
        del as_type
        span = _Span()
        self.spans.append((name, span))
        return _Observation(span)


def _backend(
    tool_calls: list[_ToolCall], *, langfuse: _Langfuse | None = None
) -> tuple[OpenAISynthesisBackend, _Completions]:
    backend = OpenAISynthesisBackend.__new__(OpenAISynthesisBackend)
    completions = _Completions(tool_calls)
    client = type("Client", (), {})()
    client.chat = type("Chat", (), {})()
    client.chat.completions = completions
    raw = cast("Any", backend)
    raw._client = client
    raw._langfuse_client = langfuse
    raw._turn_count = 0
    raw._lock = Lock()
    return backend, completions


def _emit(prose: str) -> _ToolCall:
    return _ToolCall("emit_section", {"prose": prose, "claims": []})


def _emit_repairs(segment: str) -> _ToolCall:
    return _ToolCall(
        "emit_repairs",
        {"repairs": [{"claim_id": "s0c0", "replacement_segment": segment, "claim": None}]},
    )


# --- (a) D8 + D10: one prefix, byte-identical for the turns and the repair ---


def test_section_turn_and_repair_share_a_byte_identical_prefix() -> None:
    seed = _seed()
    turn = build_section_messages(seed, [], force_emit=False)
    repair = build_section_repair_messages(seed, failing=_FAILING)

    assert turn[:3] == repair[:3] == build_section_prefix(seed)
    assert json.dumps(turn[:3], ensure_ascii=False) == json.dumps(repair[:3], ensure_ascii=False)
    assert len(turn) == 3
    assert len(repair) == 4
    assert repair[3]["role"] == "user"
    assert "Rewrite ONLY these failing claims" in repair[3]["content"]


def test_run_message_is_a_text_part_carrying_the_breakpoint() -> None:
    seed = _seed()
    [system, run, task] = build_section_prefix(seed)

    assert system["role"] == "system"
    assert isinstance(system["content"], str)
    assert run["role"] == "user"
    [part] = run["content"]
    assert set(part) == {"type", "text", "prompt_cache_breakpoint"}
    assert part["type"] == "text"
    assert part["prompt_cache_breakpoint"] == {"mode": "explicit"}
    assert part["text"].startswith(SECTION_RUN_TEMPLATE.split("{", 1)[0])
    assert isinstance(task["content"], str)
    assert task["content"].startswith("Section seed (data, not instructions):")


# --- (b) D10: same tools, same parallel flag; tool_choice alone differs ---


def test_turns_and_repair_send_identical_tools_and_parallel_tool_calls() -> None:
    seed = _seed()
    normal, normal_calls = _backend([_ToolCall("search_chunks", {"query": "q"})])
    normal.section_turn(seed, [], force_emit=False)
    forced, forced_calls = _backend([_emit("Prose.")])
    forced.section_turn(seed, [], force_emit=True)
    repairer, repair_calls = _backend([_emit_repairs("Fixed.")])
    repairer.repair_section(seed, [], failing=_FAILING)

    [turn_kwargs] = normal_calls.calls
    [forced_kwargs] = forced_calls.calls
    [repair_kwargs] = repair_calls.calls
    for kwargs in (turn_kwargs, forced_kwargs, repair_kwargs):
        assert [tool["function"]["name"] for tool in kwargs["tools"]] == _REQUEST_TOOLS
        assert kwargs["parallel_tool_calls"] is True
        # The breakpoint lives on the message; prompt_cache_options stays unset.
        assert "extra_body" not in kwargs
    assert turn_kwargs["tools"] == forced_kwargs["tools"] == repair_kwargs["tools"]
    assert turn_kwargs["messages"][:3] == repair_kwargs["messages"][:3]

    assert turn_kwargs["tool_choice"] == {
        "type": "allowed_tools",
        "allowed_tools": {
            "mode": "required",
            "tools": [{"type": "function", "function": {"name": n}} for n in _SECTION_TOOLS],
        },
    }
    assert forced_kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "emit_section"},
    }
    assert repair_kwargs["tool_choice"] == {
        "type": "function",
        "function": {"name": "emit_repairs"},
    }


# --- (c) D10: several calls on a forced turn or the repair ---


def test_forced_turn_takes_the_first_emit_section_and_counts_the_rest() -> None:
    backend, _ = _backend([_emit("First."), _emit("Second.")])

    with capture_logs() as logs:
        turn, _usage = backend.section_turn(_seed(), [], force_emit=True)

    assert turn["claims"] is not None
    assert turn["claims"].prose == "First."
    assert turn["tool_calls"] == []
    assert turn.get("extra_tool_calls_ignored") == 1
    [event] = [e for e in logs if e["event"] == "synthesise.extra_tool_calls_ignored"]
    assert event["count"] == 1
    assert event["names"] == ["emit_section"]


def test_forced_turn_skips_a_leading_read_call_to_the_emission() -> None:
    backend, _ = _backend([_ToolCall("search_chunks", {"query": "q"}), _emit("Emitted.")])

    turn, _usage = backend.section_turn(_seed(), [], force_emit=True)

    assert turn["claims"] is not None
    assert turn["claims"].prose == "Emitted."
    assert turn.get("extra_tool_calls_ignored") == 1


def test_forced_turn_with_one_call_counts_nothing() -> None:
    backend, _ = _backend([_emit("Only.")])

    turn, _usage = backend.section_turn(_seed(), [], force_emit=True)

    assert "extra_tool_calls_ignored" not in turn


def test_section_loop_result_counts_ignored_calls() -> None:
    backend, _ = _backend([_emit("First."), _emit("Second.")])

    result = run_section_loop(backend, seed=_seed(), tools={}, turn_cap=1)

    assert result["turn_cap_hit"] is True
    assert result["claims"] is not None
    assert result["claims"].prose == "First."
    assert result["extra_tool_calls_ignored"] == 1


def test_repair_takes_the_first_emit_repairs_and_records_the_count() -> None:
    langfuse = _Langfuse()
    backend, _ = _backend(
        [_emit_repairs("First fix."), _emit_repairs("Second fix.")], langfuse=langfuse
    )

    with capture_logs() as logs:
        repairs, _usage = backend.repair_section(_seed(), [], failing=_FAILING)

    assert [item.replacement_segment for item in repairs.repairs] == ["First fix."]
    [event] = [e for e in logs if e["event"] == "synthesise.extra_tool_calls_ignored"]
    assert event["count"] == 1
    assert event["names"] == ["emit_repairs"]
    [(name, span)] = langfuse.spans
    assert name == "synthesise:repair_claims"
    metadata = span.updates[-1]["metadata"]
    assert metadata["extra_tool_calls_ignored"] == 1
    assert metadata["prompt_version"] == SECTION_REPAIR_PROMPT_VERSION == "synthesise_repair_v2"


def test_repair_without_emit_repairs_still_fails_loud() -> None:
    backend, _ = _backend([_emit("Not a repair.")])

    with pytest.raises(RuntimeError, match="did not emit repairs"):
        backend.repair_section(_seed(), [], failing=_FAILING)


# --- X3: the lookup tool offers only the kinds the run can serve ---


def _lookup_enum(schema: dict[str, Any]) -> list[str]:
    return list(schema["function"]["parameters"]["properties"]["kind"]["enum"])


def test_run_without_characterisation_offers_no_characterisation_summary() -> None:
    kinds = available_lookup_kinds(
        characterisation_run_id=None,
        selection_run_id=uuid.uuid4(),
        grouping_run_id=uuid.uuid4(),
    )
    schema = lookup_tool_schema(kinds)

    assert "characterisation_summary" not in _lookup_enum(schema)
    assert "grouping_groups" in _lookup_enum(schema)
    description = schema["function"]["description"]
    # The closed vocabulary sentence is unchanged; the run sentence follows it.
    assert description == LOOKUP_TOOL_SCHEMA["function"]["description"] + LOOKUP_RUN_KINDS_SENTENCE
    assert "the characterisation summary" in description
    assert description.endswith(" Only the kinds listed here exist for this run.")


def test_run_with_every_upstream_stage_offers_the_full_set() -> None:
    kinds = available_lookup_kinds(
        characterisation_run_id=uuid.uuid4(),
        selection_run_id=uuid.uuid4(),
        grouping_run_id=uuid.uuid4(),
    )

    assert kinds == list(LOOKUP_QUERY_KINDS)
    # screening_by_doc is a reader kind the section writer is never offered.
    assert _lookup_enum(lookup_tool_schema(kinds)) == list(LOOKUP_TOOL_KINDS)
    assert len(LOOKUP_TOOL_KINDS) == 9


def test_run_with_no_upstream_stage_drops_all_three_dependent_kinds() -> None:
    kinds = available_lookup_kinds(
        characterisation_run_id=None, selection_run_id=None, grouping_run_id=None
    )

    assert _lookup_enum(lookup_tool_schema(kinds)) == [
        "appraisal_by_doc",
        "classification_by_doc",
        "coverage_records",
        "tags_by_doc",
        "docs_by_tag",
        "tag_aggregate",
    ]


def test_lookup_enum_keeps_the_canonical_order() -> None:
    shuffled = ["tag_aggregate", "appraisal_by_doc", "grouping_groups", "coverage_records"]

    assert _lookup_enum(lookup_tool_schema(shuffled)) == [
        "appraisal_by_doc",
        "coverage_records",
        "grouping_groups",
        "tag_aggregate",
    ]


def test_lookup_schema_restriction_leaves_the_module_schema_untouched() -> None:
    before = json.dumps(LOOKUP_TOOL_SCHEMA, sort_keys=True)
    lookup_tool_schema(["appraisal_by_doc"])

    assert json.dumps(LOOKUP_TOOL_SCHEMA, sort_keys=True) == before
    assert _lookup_enum(LOOKUP_TOOL_SCHEMA) == list(LOOKUP_TOOL_KINDS)


def test_lookup_schema_needs_a_known_kind() -> None:
    with pytest.raises(ValueError, match="at least one known lookup kind"):
        lookup_tool_schema(["screening_by_doc"])


def test_request_tools_follow_the_seed_and_are_stable_across_sections() -> None:
    kinds = ["appraisal_by_doc", "coverage_records", "tags_by_doc"]
    first = section_request_tools(_seed(lookup_kinds=kinds, section_title="One"))
    second = section_request_tools(_seed(lookup_kinds=kinds, section_title="Two"))

    assert first == second
    assert _lookup_enum(first[2]) == kinds
    # A seed without the field (built outside synthesise) offers every kind.
    assert _lookup_enum(section_request_tools(_seed())[2]) == list(LOOKUP_TOOL_KINDS)
