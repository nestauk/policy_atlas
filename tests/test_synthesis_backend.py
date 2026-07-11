"""Pure tests for synthesis backends and grounding judge stubs."""

from __future__ import annotations

import json
import uuid
from types import TracebackType
from typing import Any, Literal, cast

import pytest
from structlog.testing import capture_logs

from policy_atlas import tracing
from policy_atlas.grounding_judge import StubGroundingJudgeBackend, build_envelope
from policy_atlas.synthesis_backend import (
    CLAIM_TEXT_MAX,
    EMISSION_CLAIMS_MAX,
    ClaimWire,
    GapPayloadWire,
    OpenAISynthesisBackend,
    RepairItemWire,
    SectionProposalWire,
    SectionRepairWire,
    SectionTurn,
    StubSynthesisBackend,
    _salvage_section,
)
from policy_atlas.synthesis_tools import ToolExchange, run_section_loop


def _seed(
    *,
    intent: str = "What does evidence say?",
    available_tools: list[str] | None = None,
    available_claim_types: list[str] | None = None,
    substrate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "section_index": 0,
        "intent": intent,
        "section": {
            "title": "Housing outcomes",
            "focus": "Evidence on housing outcomes.",
            "group_ids": ["g1"],
        },
        "available_tools": available_tools or ["search_chunks", "query_findings", "lookup"],
        "available_claim_types": available_claim_types
        or ["chunk", "finding", "pattern", "theme", "gap", "reasoning"],
        "substrate": substrate
        or {
            "characterisation": {"themes": [{"theme_id": "theme-1"}]},
            "grouping": {"groups": [{"group_id": "g1"}]},
        },
        "computed_spread": {"increase": 2, "mixed": 1},
    }


def _search_exchange(content: str = "Alpha evidence content for citation.") -> ToolExchange:
    return {
        "tool": "search_chunks",
        "arguments": {"query": "Housing outcomes"},
        "result": {
            "chunks": [
                {
                    "chunk_record_id": "chunk-1",
                    "content": content,
                    "origin": "selected",
                }
            ]
        },
    }


def _finding_exchange() -> ToolExchange:
    return {
        "tool": "query_findings",
        "arguments": {},
        "result": {
            "findings": [
                {"finding_id": "finding-1"},
                {"finding_id": "finding-2"},
                {"finding_id": "finding-3"},
            ]
        },
    }


def test_stub_proposal_default_shape_and_group_assignment() -> None:
    backend = StubSynthesisBackend()
    proposal, usage = backend.propose_sections(
        intent="Housing\u0007 support for families",
        substrate={"grouping": {"groups": [{"group_id": "g1"}, {"id": "g2"}]}},
    )

    assert usage is None
    assert isinstance(proposal, SectionProposalWire)
    assert len(proposal.sections) == 2
    assert proposal.sections[0].title == "Evidence on: Housing support for families"
    assert proposal.sections[0].group_ids == ["g1", "g2"]
    assert proposal.sections[1].title == "Coverage and gaps in the assembled evidence"


def test_stub_section_turn_default_tool_ordering_is_gated() -> None:
    backend = StubSynthesisBackend()
    seed = _seed(available_tools=["lookup", "search_chunks"])

    first, first_usage = backend.section_turn(seed, [], force_emit=False)
    assert first_usage is None
    assert first == {
        "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "Housing outcomes"}}],
        "claims": None,
    }

    second, second_usage = backend.section_turn(seed, [_search_exchange()], force_emit=False)
    assert second_usage is None
    assert second == {
        "tool_calls": [{"tool": "lookup", "arguments": {"kind": "characterisation_summary"}}],
        "claims": None,
    }


# --- Live section-turn parsing: multi-read-tool-call turns (018 C2 round 3) ---


class _FakeFunctionCall:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, name: str, arguments: str) -> None:
        self.function = _FakeFunctionCall(name, arguments)


class _FakeMessage:
    def __init__(self, tool_calls: list[_FakeToolCall]) -> None:
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, tool_calls: list[_FakeToolCall]) -> None:
        self.message = _FakeMessage(tool_calls)


class _FakeResponse:
    def __init__(self, tool_calls: list[_FakeToolCall]) -> None:
        self.choices = [_FakeChoice(tool_calls)]
        self.usage = None


class _FakeCompletions:
    def __init__(self, tool_calls: list[_FakeToolCall]) -> None:
        self._tool_calls = tool_calls
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return _FakeResponse(self._tool_calls)


class _FakeChat:
    def __init__(self, tool_calls: list[_FakeToolCall]) -> None:
        self.completions = _FakeCompletions(tool_calls)


class _FakeOpenAIClient:
    def __init__(self, tool_calls: list[_FakeToolCall]) -> None:
        self.chat = _FakeChat(tool_calls)


def _backend_with_fake_client(tool_calls: list[_FakeToolCall]) -> OpenAISynthesisBackend:
    backend: OpenAISynthesisBackend = object.__new__(OpenAISynthesisBackend)
    fake_client = _FakeOpenAIClient(tool_calls)
    cast("Any", backend)._client = fake_client
    return backend


def test_live_section_turn_parses_two_read_tool_calls_in_order() -> None:
    backend = _backend_with_fake_client([
        _FakeToolCall("search_chunks", json.dumps({"query": "housing"})),
        _FakeToolCall("query_findings", json.dumps({})),
    ])

    turn, usage = cast("Any", backend)._create_section_turn_once([], force_emit=False)

    assert usage is None
    assert turn["claims"] is None
    assert turn["tool_calls"] == [
        {"tool": "search_chunks", "arguments": {"query": "housing"}},
        {"tool": "query_findings", "arguments": {}},
    ]
    [kwargs] = cast("Any", backend)._client.chat.completions.calls
    assert kwargs["parallel_tool_calls"] is True
    assert kwargs["tool_choice"] == "required"


def test_live_section_turn_drops_emit_section_alongside_reads() -> None:
    backend = _backend_with_fake_client([
        _FakeToolCall("emit_section", json.dumps({"prose": "x", "claims": []})),
        _FakeToolCall("search_chunks", json.dumps({"query": "housing"})),
    ])

    with capture_logs() as logs:
        turn, usage = cast("Any", backend)._create_section_turn_once([], force_emit=False)

    assert usage is None
    assert turn["claims"] is None
    assert turn["tool_calls"] == [
        {"tool": "search_chunks", "arguments": {"query": "housing"}},
    ]
    assert any(entry["event"] == "synthesis.emit_with_reads_deferred" for entry in logs)


def test_scripted_turns_drive_real_loop_and_cap_forcing_falls_through() -> None:
    scripted_tool: SectionTurn = {
        "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "scripted"}}],
        "claims": None,
    }
    forced_tool: SectionTurn = {
        "tool_calls": [{"tool": "query_findings", "arguments": {}}],
        "claims": None,
    }
    backend = StubSynthesisBackend(script=[[scripted_tool, forced_tool]])
    seed = _seed(available_tools=["search_chunks"], available_claim_types=["chunk", "gap"])

    result = run_section_loop(
        backend,
        seed=seed,
        tools={
            "search_chunks": lambda _arguments: {
                "chunks": [
                    {
                        "chunk_record_id": "chunk-1",
                        "content": "Scripted chunk content.",
                        "origin": "selected",
                    }
                ]
            }
        },
        turn_cap=2,
    )

    assert result["turn_cap_hit"] is True
    assert result["tool_call_counts"] == {"search_chunks": 1}
    claims = result["claims"]
    assert claims is not None
    assert [claim.claim_type for claim in claims.claims] == ["chunk", "gap"]
    assert claims.claims[0].citations[0].quote == "Scripted chunk content."


def test_stub_emission_respects_available_claim_types() -> None:
    backend = StubSynthesisBackend()
    seed = _seed(available_claim_types=["finding", "gap"])

    turn, usage = backend.section_turn(
        seed,
        [_search_exchange(), _finding_exchange()],
        force_emit=True,
    )

    assert usage is None
    assert turn["claims"] is not None
    assert [claim.claim_type for claim in turn["claims"].claims] == ["finding", "gap"]


def test_stub_chunk_quote_is_verbatim_and_fabrication_sentinel_breaks_it() -> None:
    backend = StubSynthesisBackend()
    content = "A" * 150

    normal, normal_usage = backend.section_turn(
        _seed(available_claim_types=["chunk"]),
        [_search_exchange(content)],
        force_emit=True,
    )
    assert normal_usage is None
    assert normal["claims"] is not None
    quote = normal["claims"].claims[0].citations[0].quote
    assert quote == content[:120]
    assert quote in content

    fabricated, fabricated_usage = backend.section_turn(
        _seed(intent="stubfabricate this quote", available_claim_types=["chunk"]),
        [_search_exchange(content)],
        force_emit=True,
    )
    assert fabricated_usage is None
    assert fabricated["claims"] is not None
    fabricated_quote = fabricated["claims"].claims[0].citations[0].quote
    assert fabricated_quote == "This quote is fabricated entirely and appears nowhere."
    assert fabricated_quote not in content


def test_stub_repair_rewords_down_and_repairs_or_keeps_fabricated_quote() -> None:
    backend = StubSynthesisBackend()
    transcript = [_search_exchange("Repairable source text that is safely quotable.")]
    failing = [
        {
            "claim_type": "chunk",
            "text": "Too strong.",
            "citations": [{"chunk_record_id": "chunk-1", "quote": "wrong"}],
            "rationale": "Quote not found.",
        }
    ]

    repaired, repair_usage = backend.repair_section(_seed(), transcript, failing=failing)
    assert repair_usage is None
    repaired_claim = repaired.repairs[0].claim
    assert repaired_claim is not None
    assert repaired_claim.text == "Reworded down: Too strong."
    # The claim text is an exact substring of the spliced replacement segment.
    assert repaired_claim.text in repaired.repairs[0].replacement_segment
    assert repaired_claim.citations[0].quote == transcript[0]["result"]["chunks"][0][
        "content"
    ][:60]

    fabricated = [
        {
            "claim_type": "chunk",
            "text": "Too strong.",
            "citations": [
                {
                    "chunk_record_id": "chunk-1",
                    "quote": "This fabricated quote is absent.",
                }
            ],
            "rationale": "Quote not found.",
        }
    ]
    unrepaired, unrepaired_usage = backend.repair_section(
        _seed(), transcript, failing=fabricated
    )
    assert unrepaired_usage is None
    unrepaired_claim = unrepaired.repairs[0].claim
    assert unrepaired_claim is not None
    assert unrepaired_claim.citations[0].quote == "This fabricated quote is absent."

    repairable, repairable_usage = backend.repair_section(
        _seed(intent="stubrepairable"),
        transcript,
        failing=fabricated,
    )
    assert repairable_usage is None
    repairable_claim = repairable.repairs[0].claim
    assert repairable_claim is not None
    assert repairable_claim.citations[0].quote == transcript[0]["result"]["chunks"][0][
        "content"
    ][:60]


def test_stub_grounding_judge_emits_unspanned_per_stubunspanned_line() -> None:
    """ADR 0015 §5: the stub judge flags one unspanned assertion per prose line
    containing ``stubunspanned`` (excerpt = the full line)."""
    backend = StubGroundingJudgeBackend()
    prose = "A grounded sentence.\nAn ungrounded stubunspanned assertion.\nAnother line."
    envelope = build_envelope(
        claims=[{"claim_id": "c1", "claim_type": "reasoning", "text": "t"}],
        chunks=[],
        section_prose=prose,
        span_map=[{"claim_id": "c1", "start": 0, "end": 1}],
    )

    result, _usage = backend.judge_block(envelope)

    assert [a.excerpt for a in result.unspanned_assertions] == [
        "An ungrounded stubunspanned assertion."
    ]
    assert result.unspanned_assertions[0].rationale == "Stub unspanned assertion."


def test_stub_grounding_judge_verdict_routing() -> None:
    backend = StubGroundingJudgeBackend()
    envelope = build_envelope(
        claims=[
            {
                "claim_id": "chunk",
                "claim_type": "chunk",
                "text": "Direct source claim.",
                "citations": [{"chunk_record_id": "chunk-1", "quote": "source"}],
            },
            {
                "claim_id": "fabricated",
                "claim_type": "chunk",
                "text": "Direct source claim.",
                "citations": [{"chunk_record_id": "chunk-1", "quote": "fabricated"}],
            },
            {
                "claim_id": "finding",
                "claim_type": "finding",
                "text": "Finding-backed claim.",
                "cited_finding_ids": ["finding-1"],
            },
            {
                "claim_id": "smuggle",
                "claim_type": "reasoning",
                "text": "stubsmuggle causal assertion.",
            },
            {
                "claim_id": "reasoning",
                "claim_type": "reasoning",
                "text": "Background context.",
            },
            {
                "claim_id": "weak-theme",
                "claim_type": "theme",
                "text": "stubweak broad theme.",
            },
        ],
        chunks=[{"chunk_record_id": "chunk-1", "content": "source"}],
    )

    result, usage = backend.judge_block(envelope)

    assert usage is None
    assert [verdict.claim_id for verdict in result.verdicts] == [
        "chunk",
        "fabricated",
        "finding",
        "smuggle",
        "reasoning",
        "weak-theme",
    ]
    assert [verdict.verdict for verdict in result.verdicts] == [
        "tier_1",
        "unsupported_mis_cited",
        "tier_2",
        "unsupported_mis_cited",
        "tier_4",
        "tier_3",
    ]
    assert result.verdicts[-1].weakly_grounded is True
    assert result.verdicts[0].rationale == "Stub verdict for chunk."


def test_stub_failure_sentinels_raise() -> None:
    synthesis = StubSynthesisBackend(fail=True)
    judge = StubGroundingJudgeBackend(fail=True)

    with pytest.raises(RuntimeError, match="Stub synthesis failure sentinel."):
        synthesis.propose_sections(intent="x", substrate={})
    with pytest.raises(RuntimeError, match="Stub synthesis failure sentinel."):
        synthesis.section_turn(_seed(), [], force_emit=True)
    with pytest.raises(RuntimeError, match="Stub synthesis failure sentinel."):
        synthesis.repair_section(_seed(), [], failing=[])
    with pytest.raises(RuntimeError, match="Stub grounding judge failure sentinel."):
        judge.judge_block(build_envelope(claims=[], chunks=[]))


def test_custom_stub_payloads_are_returned() -> None:
    proposal = SectionProposalWire.model_validate(
        {"sections": [{"title": "Custom", "focus": "Custom focus."}]}
    )
    repair = SectionRepairWire(
        repairs=[
            RepairItemWire(
                replacement_segment="Custom repair.",
                claim=ClaimWire(
                    claim_type="gap",
                    text="Custom repair.",
                    gap=GapPayloadWire(grade="inferred", coverage_base="screened"),
                ),
            )
        ]
    )
    backend = StubSynthesisBackend(proposal=proposal, repair=repair)

    returned_proposal, proposal_usage = backend.propose_sections(intent="x", substrate={})
    returned_repair, repair_usage = backend.repair_section(_seed(), [], failing=[])

    assert returned_proposal is proposal
    assert proposal_usage is None
    assert returned_repair is repair
    assert repair_usage is None


def test_traced_call_no_client_path_calls_through() -> None:
    calls: list[str] = []

    def _call() -> int:
        calls.append("called")
        return 7

    assert tracing.traced_call(None, name="noop", as_type="generation", call=_call) == 7
    assert calls == ["called"]


class _FakeSpan:
    def __init__(self) -> None:
        self.closed = False
        self.updates: list[dict[str, Any]] = []

    def update(self, **payload: Any) -> None:
        self.updates.append(payload)


class _FakeObservation:
    def __init__(self, span: _FakeSpan) -> None:
        self._span = span

    def __enter__(self) -> _FakeSpan:
        return self._span

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exc_type, exc, traceback
        self._span.closed = True
        return False


class _FakeLangfuse:
    def __init__(self) -> None:
        self.spans: list[tuple[str, str, _FakeSpan]] = []
        self.sessions: list[str] = []

    def start_as_current_observation(self, *, name: str, as_type: str) -> _FakeObservation:
        span = _FakeSpan()
        self.spans.append((name, as_type, span))
        return _FakeObservation(span)

    def update_current_trace(self, *, session_id: str) -> None:
        self.sessions.append(session_id)


def test_traced_call_after_hook_runs_inside_span() -> None:
    fake_client = _FakeLangfuse()
    events: list[tuple[str, bool]] = []

    result = tracing.traced_call(
        cast(Any, fake_client),
        name="generated",
        as_type="generation",
        call=lambda: "result",
        update=lambda span, value: events.append(("update", span.closed)),
        after=lambda span, value: events.append(("after", span.closed)),
    )

    assert result == "result"
    assert events == [("update", False), ("after", False)]
    assert fake_client.spans[0][0:2] == ("generated", "generation")
    assert fake_client.spans[0][2].closed is True


def test_component_span_applies_langfuse_session() -> None:
    fake_client = _FakeLangfuse()
    session_id = uuid.uuid4()

    with tracing.component_span(
        cast(Any, fake_client),
        run_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        component="synthesise",
        session_id=session_id,
    ):
        pass

    assert fake_client.sessions == [str(session_id)]
    assert fake_client.spans[0][0].startswith("run:synthesise:")
    assert [span[1] for span in fake_client.spans] == ["span", "span"]
    assert fake_client.spans[1][0] == "component:synthesise"


def test_salvage_section_caps_emission_at_max() -> None:
    """One oversized emission must not drive unbounded writes: overflow claims
    beyond EMISSION_CLAIMS_MAX are salvaged as malformed, never validated."""
    overflow = 7
    total = EMISSION_CLAIMS_MAX + overflow
    arguments = json.dumps({
        "prose": "Prose.",
        "claims": [
            {"claim_type": "reasoning", "text": f"Reasoning claim {index}."}
            for index in range(total)
        ]
    })

    section, malformed = _salvage_section(arguments)

    assert len(section.claims) == EMISSION_CLAIMS_MAX
    assert malformed == overflow


def test_salvage_section_rejects_oversized_claim_text() -> None:
    """A claim whose text exceeds CLAIM_TEXT_MAX is counted malformed and
    dropped, not returned as a valid claim."""
    long_text = "x" * (CLAIM_TEXT_MAX + 1)
    arguments = json.dumps({
        "prose": "Short claim.",
        "claims": [
            {"claim_type": "reasoning", "text": "Short claim."},
            {"claim_type": "reasoning", "text": long_text},
        ]
    })

    section, malformed = _salvage_section(arguments)

    assert [claim.text for claim in section.claims] == ["Short claim."]
    assert malformed == 1


def test_salvage_section_rejects_missing_and_oversized_prose() -> None:
    """Missing/non-str prose and over-cap prose are turn-consuming malformed
    emissions (ADR 0015 §1)."""
    from policy_atlas.synthesis_backend import SECTION_PROSE_MAX
    from policy_atlas.synthesis_tools import MalformedEmissionError

    with pytest.raises(MalformedEmissionError):
        _salvage_section(json.dumps({"claims": []}))
    with pytest.raises(MalformedEmissionError):
        _salvage_section(json.dumps({"prose": 5, "claims": []}))
    with pytest.raises(MalformedEmissionError):
        _salvage_section(
            json.dumps({"prose": "x" * (SECTION_PROSE_MAX + 1), "claims": []})
        )
