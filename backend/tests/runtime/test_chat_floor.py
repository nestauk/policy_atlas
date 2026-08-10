"""Deterministic coverage for the chat citation floor."""

from __future__ import annotations

from policy_atlas.runtime.chat_floor import apply_citation_floor
from policy_atlas.runtime.chat_prompt import ChatAnswerWire, ChatCitationWire, ChatClaimWire


def _answer(
    prose: str,
    ids: list[str],
    claims: list[ChatClaimWire] | None = None,
    *,
    evidence_not_held: bool = False,
) -> ChatAnswerWire:
    """Build a concise raw answer fixture."""
    return ChatAnswerWire(
        prose=prose,
        citations=[ChatCitationWire(id=value, quote=f"quote {value}") for value in ids],
        claims=claims or [],
        evidence_not_held=evidence_not_held,
    )


def test_floor_strips_fabricated_id_and_its_marker() -> None:
    floored = apply_citation_floor(
        _answer("Supported [1]; invented [2].", ["chunk", "invented"]),
        tool_chunk_ids={"chunk"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk"},
    )
    assert floored.prose == "Supported [1]; invented ."
    assert [citation["id"] for citation in floored.citations] == ["chunk"]
    assert floored.stripped == [{"id": "invented", "reason": "not_citable_this_turn"}]


def test_floor_drops_out_of_range_claim_references() -> None:
    floored = apply_citation_floor(
        _answer("Claim [1].", ["chunk"], [ChatClaimWire(text="Claim", citation_indexes=[1, 2])]),
        tool_chunk_ids={"chunk"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk"},
    )
    assert floored.claims[0]["citation_ns"] == [1]


def test_floor_requires_appraisal_for_tool_chunks_but_not_frame_chunks() -> None:
    unappraised = apply_citation_floor(
        _answer("Claim [1].", ["tool"]),
        tool_chunk_ids={"tool"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
    )
    frame = apply_citation_floor(
        _answer("Claim [1].", ["frame"]),
        tool_chunk_ids=set(),
        tool_finding_ids=set(),
        frame_chunk_ids={"frame"},
    )
    assert unappraised.citations == []
    assert unappraised.stripped == [{"id": "tool", "reason": "unappraised_chunk"}]
    assert frame.citations[0]["id"] == "frame"


def test_floor_strips_orphan_markers_and_compacts_by_first_appearance() -> None:
    floored = apply_citation_floor(
        _answer("Second [2], orphan [3], first [1].", ["one", "two"]),
        tool_chunk_ids={"one", "two"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"one", "two"},
    )
    assert floored.prose == "Second [1], orphan , first [2]."
    assert [(citation["n"], citation["id"]) for citation in floored.citations] == [
        (1, "two"),
        (2, "one"),
    ]


def test_floor_drops_uncited_entries_and_recomputes_claim_span() -> None:
    floored = apply_citation_floor(
        _answer(
            "Claim [2].",
            ["unused", "used"],
            [
                ChatClaimWire(text="Claim", citation_indexes=[2]),
                ChatClaimWire(text="missing", citation_indexes=[]),
            ],
        ),
        tool_chunk_ids={"unused", "used"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"unused", "used"},
    )
    assert [(citation["n"], citation["id"]) for citation in floored.citations] == [(1, "used")]
    assert floored.claims[0] == {"text": "Claim", "span": [0, 5], "citation_ns": [1]}
    assert floored.claims[1]["span"] is None


def test_zero_survivors_warns_and_preserves_evidence_not_held() -> None:
    floored = apply_citation_floor(
        _answer("Nothing [1].", ["made-up"], evidence_not_held=True),
        tool_chunk_ids=set(),
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
    )
    assert floored.warning_not_evidence_checked is True
    assert floored.evidence_not_held is True
