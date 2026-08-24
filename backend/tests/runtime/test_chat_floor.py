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


def test_floor_derives_claims_for_uncovered_citations() -> None:
    """A surviving citation with no claim gets a sentence-derived claim mapping."""
    floored = apply_citation_floor(
        _answer("First finding stands [1]. Unrelated remark.", ["chunk-a"]),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert len(floored.citations) == 1
    assert len(floored.claims) == 1
    derived = floored.claims[0]
    assert derived["derived"] is True
    assert derived["citation_ns"] == [1]
    assert derived["text"] == "First finding stands [1]."
    start, end = derived["span"]
    assert floored.prose[start:end] == derived["text"]


def test_floor_derives_a_claim_only_for_the_uncovered_occurrence() -> None:
    """Two markers of one citation: a span-bearing claim covers only its own sentence."""
    floored = apply_citation_floor(
        _answer(
            "Claim A stands [1]. Claim B stands [1].",
            ["chunk-a"],
            [ChatClaimWire(text="Claim B stands", citation_indexes=[1])],
        ),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert len(floored.citations) == 1
    assert len(floored.claims) == 2
    original, derived = floored.claims
    assert original["text"] == "Claim B stands"
    assert "derived" not in original
    assert derived["derived"] is True
    assert derived["citation_ns"] == [1]
    assert derived["text"] == "Claim A stands [1]."
    start, end = derived["span"]
    assert floored.prose[start:end] == derived["text"]


def test_floor_skips_derivation_when_every_occurrence_is_span_covered() -> None:
    """Two markers of one citation, each covered by its own span-bearing claim."""
    floored = apply_citation_floor(
        _answer(
            "Claim A stands [1]. Claim B stands [1].",
            ["chunk-a"],
            [
                ChatClaimWire(text="Claim A stands", citation_indexes=[1]),
                ChatClaimWire(text="Claim B stands", citation_indexes=[1]),
            ],
        ),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert len(floored.claims) == 2
    assert all("derived" not in claim for claim in floored.claims)


def test_floor_span_less_claim_covers_only_the_first_occurrence() -> None:
    """A claim with no verbatim-matching span covers only the first occurrence."""
    floored = apply_citation_floor(
        _answer(
            "Claim A stands [1]. Claim B stands [1].",
            ["chunk-a"],
            [ChatClaimWire(text="Summary text not verbatim in the prose", citation_indexes=[1])],
        ),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert len(floored.claims) == 2
    original, derived = floored.claims
    assert original["span"] is None
    assert derived["derived"] is True
    assert derived["citation_ns"] == [1]
    assert derived["text"] == "Claim B stands [1]."


def test_floor_scrubs_stray_artifact_tokens() -> None:
    """Lone angle-bracket provider tokens never survive into the persisted prose."""
    floored = apply_citation_floor(
        _answer(
            "The evidence supports this [1].\n\n<lemma>",
            ["chunk-a"],
            [ChatClaimWire(text="The evidence supports this", citation_indexes=[1])],
        ),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert "<lemma>" not in floored.prose
    assert floored.prose == "The evidence supports this [1]."


def test_floor_strips_trailing_structured_json_blob() -> None:
    """A leaked terminal citations/claims JSON dump never reaches the display prose."""
    blob = (
        '{"citations":[{"id":"chunk-a","quote":"q"}],'
        '"claims":[{"text":"x","citations":["chunk-a"]}]}'
    )
    floored = apply_citation_floor(
        _answer(
            f"The evidence supports this [1].\n\n{blob}",
            ["chunk-a"],
            [ChatClaimWire(text="The evidence supports this", citation_indexes=[1])],
        ),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert floored.prose == "The evidence supports this [1]."
    assert len(floored.citations) == 1


def test_floor_keeps_json_quoted_mid_prose() -> None:
    """JSON the answer legitimately quotes mid-prose is content, not a leak."""
    prose = 'The API returns {"status": "ok"} on success [1]. That is the contract.'
    floored = apply_citation_floor(
        _answer(
            prose, ["chunk-a"], [ChatClaimWire(text="That is the contract.", citation_indexes=[1])]
        ),
        tool_chunk_ids={"chunk-a"},
        tool_finding_ids=set(),
        frame_chunk_ids=set(),
        appraised_chunk_ids={"chunk-a"},
    )
    assert '{"status": "ok"}' in floored.prose
