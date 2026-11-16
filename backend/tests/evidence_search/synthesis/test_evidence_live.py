"""Evidence shown live while a section is written (task 058, owner 2026-11-05).

Item 1: after each read tool returns, the section loop publishes the sources
its results came from. Item 2: while the write turn streams, each claim object
is read as soon as it closes, bound to the streamed prose, and published with
its cited sources. Both are display-only: the final parse must not change.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any, cast

import pytest

from policy_atlas.core import liveness
from policy_atlas.core.openai_client import JsonArrayObjectDecoder
from policy_atlas.evidence_search.synthesis import synthesis_backend as sb
from policy_atlas.evidence_search.synthesis.section_prompt import SectionProseWire
from policy_atlas.evidence_search.synthesis.synthesis_backend import (
    OpenAISynthesisBackend,
    SectionTurn,
    _salvage_section,
)
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    UNTITLED_SOURCE,
    ToolExchange,
    make_source_labeller,
    read_sources,
    run_section_loop,
    source_labelling,
    source_short_name,
)

TSS_A = str(uuid.UUID(int=0xA))
TSS_B = str(uuid.UUID(int=0xB))
TSS_C = str(uuid.UUID(int=0xC))


# --- The claims decoder ---------------------------------------------------------


def _feed_in_pieces(text: str, size: int) -> list[str]:
    decoder = JsonArrayObjectDecoder("claims")
    out: list[str] = []
    for at in range(0, len(text), size):
        out.extend(decoder.feed(text[at : at + size]))
    return out


@pytest.mark.parametrize("size", [1, 2, 3, 7, 50, 10_000])
def test_claim_objects_split_across_pieces_come_back_whole(size: int) -> None:
    payload = {
        "prose": 'Not a claim: "claims": [{"text": "decoy"}] {}',
        "claims": [
            {"claim_type": "chunk", "text": 'He said "go" {now}', "citations": [
                {"chunk_record_id": "c1", "quote": 'a \\ b } ] "q"'}
            ]},
            {"claim_type": "reasoning", "text": "plain [brackets] and {braces}"},
        ],
    }
    text = json.dumps(payload)
    closed = _feed_in_pieces(text, size)
    assert [json.loads(raw) for raw in closed] == payload["claims"]


def test_the_decoder_ignores_a_nested_claims_key_and_a_code_fence() -> None:
    nested = {"meta": {"claims": [{"text": "inner"}]}, "claims": [{"text": "outer"}]}
    text = "```json\n" + json.dumps(nested) + "\n```"
    assert [json.loads(raw) for raw in _feed_in_pieces(text, 4)] == [{"text": "outer"}]


def test_the_decoder_stops_after_the_array_closes() -> None:
    decoder = JsonArrayObjectDecoder("claims")
    assert decoder.feed('{"claims": [{"a": 1}], "later": [{"b": 2}]}') == ['{"a": 1}']
    assert decoder.done is True
    assert decoder.feed('{"c": 3}') == []


# --- Streamed claim markers --------------------------------------------------------


def _content_chunk(text: str) -> Any:
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=text))], usage=None
    )


class _StreamCompletions:
    def __init__(self, text: str, size: int) -> None:
        self._chunks = [_content_chunk(text[at : at + size]) for at in range(0, len(text), size)]
        self._chunks.append(SimpleNamespace(choices=[], usage=None))

    def create(self, **_kwargs: Any) -> Iterator[Any]:
        return iter(self._chunks)


def _backend(text: str, size: int) -> OpenAISynthesisBackend:
    backend = OpenAISynthesisBackend(api_key="sk-test-live")
    completions = _StreamCompletions(text, size)
    cast("Any", backend)._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return backend


def _seed() -> dict[str, Any]:
    return {
        "section_index": 0,
        "display_index": 2,
        "intent": "What helps?",
        "section": {"title": "Costs", "focus": "Costs.", "group_ids": []},
        "available_tools": ["search_chunks", "query_findings", "lookup"],
        "available_claim_types": ["chunk", "finding", "reasoning"],
        "substrate": {},
        "member_findings": [
            {"finding_id": "f-member", "tss_id": TSS_C, "document_title": "Member study"}
        ],
    }


def _transcript() -> list[ToolExchange]:
    return [
        {
            "tool": "search_chunks",
            "arguments": {"query": "cost"},
            "result": {
                "chunks": [
                    {"chunk_record_id": "c1", "tss_id": TSS_A, "document_title": "Alpha report"},
                    {"chunk_record_id": "c2", "tss_id": TSS_B, "document_title": f"source {TSS_B}"},
                ],
                "truncated": False,
            },
        }
    ]


_PROSE = "Costs fall when meals are free. Uptake rises with outreach. Nothing else."
_CLAIMS: list[dict[str, Any]] = [
    {
        "claim_type": "chunk",
        "text": "Costs fall when meals are free.",
        "citations": [{"chunk_record_id": "c1", "quote": "q1"}],
    },
    # Malformed: an unknown claim type. Skipped, and still counted by the final parse.
    {"claim_type": "not-a-type", "text": "Uptake rises"},
    # Does not bind: its text is not in the prose.
    {
        "claim_type": "chunk",
        "text": "A sentence the prose never had.",
        "citations": [{"chunk_record_id": "c1", "quote": "q"}],
    },
    {
        "claim_type": "finding",
        "text": "Uptake rises with outreach.",
        "cited_finding_ids": ["f-member"],
    },
    # Binds, but cites nothing: no marker.
    {"claim_type": "reasoning", "text": "Nothing else."},
    {
        "claim_type": "chunk",
        "text": "meals are free",
        "citations": [{"chunk_record_id": "c2", "quote": "q2"}],
    },
]
_REPLY = json.dumps({"prose": _PROSE, "claims": _CLAIMS})


@pytest.fixture
def published(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int, int, list[tuple[str, str]]]]:
    recorded: list[tuple[int, int, int, list[tuple[str, str]]]] = []

    def _claim(index: int, start: int, end: int, sources: Any) -> None:
        recorded.append((index, start, end, list(sources)))

    monkeypatch.setattr(sb, "publish_section_claim", _claim)
    monkeypatch.setattr(sb, "publish_section_delta", lambda *_a, **_k: None)
    return recorded


@pytest.mark.parametrize("size", [1, 5, 64, 100_000])
def test_each_bound_cited_claim_is_published_with_its_span_and_sources(
    size: int, published: list[tuple[int, int, int, list[tuple[str, str]]]]
) -> None:
    turn, _usage = _backend(_REPLY, size).section_emit_stream(_seed(), _transcript())

    first = "Costs fall when meals are free."
    second = "Uptake rises with outreach."
    second_at = _PROSE.index(second)
    # The malformed claim, the unbound one, the uncited one and the one whose
    # words overlap the first claim's span ("meals are free") get no marker.
    assert published == [
        (2, 0, len(first), [(TSS_A, "Alpha report")]),
        (2, second_at, second_at + len(second), [(TSS_C, "Member study")]),
    ]
    # The streamed markers never change the final parse.
    assert turn == {
        "tool_calls": [],
        "claims": _salvage_section(_REPLY)[0],
        "malformed_claims": 1,
    }


def test_a_raw_id_title_never_reaches_the_page(
    published: list[tuple[int, int, int, list[tuple[str, str]]]],
) -> None:
    prose = "Only the second source."
    reply = json.dumps(
        {
            "prose": prose,
            "claims": [
                {
                    "claim_type": "chunk",
                    "text": prose,
                    "citations": [{"chunk_record_id": "c2", "quote": "q"}],
                }
            ],
        }
    )
    _backend(reply, 8).section_emit_stream(_seed(), _transcript())
    assert published == [(2, 0, len(prose), [(TSS_B, UNTITLED_SOURCE)])]

    published.clear()
    with source_labelling(lambda ids: {TSS_B: "Brown 2020"} if TSS_B in ids else {}):
        _backend(reply, 8).section_emit_stream(_seed(), _transcript())
    assert published == [(2, 0, len(prose), [(TSS_B, "Brown 2020")])]


def test_a_malformed_claim_object_is_skipped_and_the_final_parse_is_unchanged(
    published: list[tuple[int, int, int, list[tuple[str, str]]]],
) -> None:
    prose = "Costs fall when meals are free."
    good = json.dumps(
        {
            "claim_type": "chunk",
            "text": prose,
            "citations": [{"chunk_record_id": "c1", "quote": "q"}],
        }
    )
    # The first claim is not valid JSON by itself (a bare word value): the
    # whole reply then fails to parse, and the turn falls back as before.
    reply = '{"prose": ' + json.dumps(prose) + ', "claims": [{"text": oops}, ' + good + "]}"
    backend = _backend(reply, 6)
    fallback_calls: list[bool] = []

    def _fallback(
        seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
    ) -> tuple[SectionTurn, None]:
        del seed, transcript
        fallback_calls.append(force_emit)
        return {"tool_calls": [], "claims": SectionProseWire(prose="Fallback.", claims=[])}, None

    cast("Any", backend).section_turn = _fallback
    turn, _usage = backend.section_emit_stream(_seed(), _transcript())
    # The good claim after the broken one still got its marker while streaming.
    assert published == [(2, 0, len(prose), [(TSS_A, "Alpha report")])]
    assert fallback_calls == [True]
    claims = turn["claims"]
    assert claims is not None and claims.prose == "Fallback."


def test_a_failing_labeller_never_fails_the_write_turn(
    published: list[tuple[int, int, int, list[tuple[str, str]]]],
) -> None:
    def _broken(_ids: Any) -> dict[str, str]:
        raise RuntimeError("database gone")

    with source_labelling(_broken):
        turn, _usage = _backend(_REPLY, 16).section_emit_stream(_seed(), _transcript())
    assert published == []
    assert turn["claims"] == _salvage_section(_REPLY)[0]


# --- Sources read ------------------------------------------------------------------


def test_read_sources_names_each_source_once_in_first_seen_order() -> None:
    result = {
        "chunks": [
            {"chunk_record_id": "c1", "tss_id": TSS_A, "document_title": "Alpha report"},
            {"chunk_record_id": "c9", "already_returned": True},
            {"chunk_record_id": "c8", "skipped_over_budget": True},
            {"chunk_record_id": "c2", "tss_id": TSS_B, "document_title": f"source {TSS_B}"},
            {"chunk_record_id": "c3", "tss_id": TSS_A, "document_title": "Alpha report"},
        ],
        "iof_findings": [{"finding_id": "f1", "tss_id": TSS_C, "document_title": "Gamma"}],
    }
    assert read_sources(result) == [
        (TSS_A, "Alpha report"),
        (TSS_B, UNTITLED_SOURCE),
        (TSS_C, "Gamma"),
    ]
    with source_labelling(lambda ids: {i: f"short {i[-1]}" for i in ids if i != TSS_C}):
        assert read_sources(result) == [
            (TSS_A, "short a"),
            (TSS_B, "short b"),
            (TSS_C, "Gamma"),
        ]
    assert read_sources({"error": "bad arguments"}) == []


def test_source_short_name_prefers_author_and_year_then_title_then_locator() -> None:
    authored = {
        "title": "A long title",
        "publication_year": 2023,
        "provider_fields": {"authorships": [{"author_name": "Jane Smith"}]},
    }
    assert source_short_name(authored, "https://x") == "Smith 2023"
    listed = {"year": 2019, "provider_fields": {"authors": ["Brown, Alex", "Lee, Kim"]}}
    assert source_short_name(listed, None) == "Brown 2019"
    published_by = {"title": "Report", "year": 2022, "publisher_org": "DfE"}
    assert source_short_name(published_by, None) == "DfE 2022"
    no_year = {"title": "Free &amp; fair meals", "publisher_org": "DfE"}
    assert source_short_name(no_year, None) == "Free & fair meals"
    assert source_short_name({}, "https://example.org/doc") == "https://example.org/doc"
    assert source_short_name({}, "") == UNTITLED_SOURCE


def test_the_labeller_reads_each_source_once() -> None:
    class _Conn:
        def __init__(self) -> None:
            self.calls = 0

        def execute(self, _statement: Any) -> list[Any]:
            self.calls += 1
            return [
                SimpleNamespace(
                    task_source_snapshot_id=uuid.UUID(TSS_A),
                    metadata={"title": "Alpha", "year": 2021, "publisher_org": "Nesta"},
                    source_locator="https://a",
                )
            ]

    conn = _Conn()
    labels = make_source_labeller(cast("Any", conn), task_id=uuid.uuid4())
    assert labels([TSS_A, TSS_B, "not-a-uuid"]) == {TSS_A: "Nesta 2021"}
    assert labels([TSS_A, TSS_B]) == {TSS_A: "Nesta 2021"}
    assert conn.calls == 1


class _ReadThenWriteBackend:
    def section_turn(
        self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
    ) -> tuple[SectionTurn, None]:
        del seed, force_emit
        if transcript:
            return {"tool_calls": [], "claims": None, "ready": True}, None
        return {
            "tool_calls": [{"tool": "search_chunks", "arguments": {"query": "cost"}}],
            "claims": None,
        }, None

    def section_emit_stream(
        self, seed: dict[str, Any], transcript: list[ToolExchange]
    ) -> tuple[SectionTurn, None]:
        del seed, transcript
        return {"tool_calls": [], "claims": SectionProseWire(prose="Done.", claims=[])}, None


def test_the_section_loop_publishes_the_sources_after_each_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        liveness,
        "publish_progress",
        lambda **kwargs: events.append(("progress", kwargs["activity"])),
    )
    monkeypatch.setattr(
        liveness,
        "publish_section_sources",
        lambda index, sources: events.append(("sources", (index, list(sources)))),
    )

    def search_chunks(_arguments: dict[str, Any]) -> dict[str, Any]:
        events.append(("read", None))
        return {
            "chunks": [
                {"chunk_record_id": "c1", "tss_id": TSS_A, "document_title": "Alpha report"},
                {"chunk_record_id": "c2", "tss_id": TSS_B, "document_title": "Beta"},
            ],
            "truncated": False,
        }

    run_section_loop(
        _ReadThenWriteBackend(),
        seed=_seed(),
        tools={"search_chunks": search_chunks},
        turn_cap=4,
    )
    read_at = events.index(("read", None))
    assert events[read_at - 1] == ("progress", "Looking for: cost")
    assert events[read_at + 1] == ("sources", (2, [(TSS_A, "Alpha report"), (TSS_B, "Beta")]))
