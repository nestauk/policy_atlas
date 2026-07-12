"""Pure tests for synthesise helpers and claim validators."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from policy_atlas.grounding_judge import (
    StubGroundingJudgeBackend,
    build_envelope,
    build_judge_messages,
)
from policy_atlas.quote_verify import build_basis
from policy_atlas.synthesis_backend import (
    ClaimWire,
    GapPayloadWire,
    PatternPayloadWire,
    SectionProposalWire,
    SectionProseWire,
    SectionWire,
    SparsitySignalWire,
    StubSynthesisBackend,
    ThemePayloadWire,
)
from policy_atlas.synthesis_tools import (
    ARTEFACT_TITLE_MAX,
    REASONING_CLAIMS_MAX,
    SECTION_CAP,
    SECTION_TURN_CAP,
    _doc_record,
    _finding_record,
)
from policy_atlas.synthesise import (
    CONCLUSIONS_TITLE,
    ChunkInfo,
    ClaimDraft,
    CorpusProfile,
    CoverageRecord,
    FindingInfo,
    SectionAccounting,
    SectionSpec,
    SpliceItem,
    SubstrateView,
    _anchor_counts,
    _conclusions_focus,
    _judge_claims,
    _section_claims,
    _validate_sections,
    bind_spans,
    build_ledger,
    derive_artefact_title,
    generation_budget_max,
    splice_and_rebind,
    validate_claims,
)


def _claim(data: dict[str, Any]) -> ClaimWire:
    return ClaimWire.model_validate(data)


def _substrate() -> SubstrateView:
    chunk = ChunkInfo(
        chunk_id="11111111-1111-1111-1111-111111111111",
        pss_id="pss-1",
        source_snapshot_id="snap-1",
        sequence=0,
        content="alpha quoted evidence appears here",
        segmentation_policy="manual_v1",
        text_basis="abstract_only",
        origin="unselected_screened",
        appraised=True,
    )
    unappraised = ChunkInfo(
        chunk_id="22222222-2222-2222-2222-222222222222",
        pss_id="pss-2",
        source_snapshot_id="snap-2",
        sequence=0,
        content="beta quoted evidence appears here",
        segmentation_policy="manual_v1",
        text_basis="full_text",
        origin="selected",
        appraised=False,
    )
    finding = FindingInfo(
        finding_id="finding-1",
        pss_id="pss-1",
        source_snapshot_id="snap-finding",
        record={
            "finding_id": "finding-1",
            "effect_direction": "increase",
            "intervention": "A",
            "outcome": "B",
        },
        grounding=[
            {
                "quote": "finding anchor quote",
                "match_status": "exact",
                "quote_verified": True,
                "spans": [
                    {
                        "chunk_id": "11111111-1111-1111-1111-111111111111",
                        "start": 0,
                        "end": 20,
                    }
                ],
            }
        ],
        effect_direction="increase",
    )
    return SubstrateView(
        characterisation={
            "coverage": {
                "distributions": {"origin": {"uploaded": 2}},
                "sparsity": {"zero_count": 0},
            },
            "themes": [{"theme_id": "theme-1", "name": "Theme one"}],
        },
        selection=None,
        extraction={"counts": {"findings_total": 1}},
        grouping={
            "facet": "intervention",
            "groups": [
                {
                    "group_id": "group-1",
                    "label": "Group 1",
                    "direction_spread": {"increase": 1},
                    "member_finding_ids": ["finding-1"],
                }
            ],
        },
        corpus=CorpusProfile(
            screened_docs=2,
            ingested_docs=2,
            appraised_docs=1,
            appraised_ingested_docs=1,
            appraised_pss_ids={"pss-1"},
        ),
        coverage_records={
            "cov-ok": CoverageRecord(
                record_id="cov-ok",
                backends=[{"backend": "fixture"}],
                adequacy_verdict="adequate",
                verdict_origin="model",
            ),
            "cov-bad": CoverageRecord(
                record_id="cov-bad",
                backends=[{"backend": "fixture"}],
                adequacy_verdict="inadequate",
                verdict_origin="model",
            ),
        },
        chunk_by_id={chunk.chunk_id: chunk, unappraised.chunk_id: unappraised},
        chunks_by_pss_id={"pss-1": [chunk], "pss-2": [unappraised]},
        finding_by_id={"finding-1": finding},
        basis_by_snapshot_id={
            "snap-finding": build_basis(
                [("11111111-1111-1111-1111-111111111111", "finding anchor quote")]
            )
        },
        selected_pss_ids={"pss-2"},
    )


def _rejected_reason(claim: ClaimWire, **kwargs: Any) -> str:
    citable_finding_ids = kwargs.pop("citable_finding_ids", {"finding-1"})
    citable_chunk_ids = kwargs.pop(
        "citable_chunk_ids", {"11111111-1111-1111-1111-111111111111"}
    )
    batch = validate_claims(
        [claim],
        substrate=_substrate(),
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids=citable_finding_ids,
        citable_chunk_ids=citable_chunk_ids,
        spans=kwargs.pop("spans", [(0, 1)]),
        **kwargs,
    )
    assert len(batch.rejected) == 1
    return batch.rejected[0].reason


def test_chunk_info_carries_text_basis_values() -> None:
    substrate = _substrate()

    assert {
        chunk_id: chunk.text_basis for chunk_id, chunk in substrate.chunk_by_id.items()
    } == {
        "11111111-1111-1111-1111-111111111111": "abstract_only",
        "22222222-2222-2222-2222-222222222222": "full_text",
    }


def test_artefact_title_strips_control_chars_and_truncates() -> None:
    title = derive_artefact_title("A\x07B")
    assert title == "AB"

    long = "x" * (ARTEFACT_TITLE_MAX + 10)
    truncated = derive_artefact_title(long)
    assert len(truncated) == ARTEFACT_TITLE_MAX
    assert truncated.endswith("…")


def test_budget_formula_and_ledger_marker() -> None:
    # +1 conclusions section (rides above SECTION_CAP) + the key-findings pass
    # (emission + judge/repair/rejudge) — ADR 0015 §8.
    assert generation_budget_max() == 2 + (SECTION_CAP + 1) * (SECTION_TURN_CAP + 3) + 4

    ledger = build_ledger(
        [
            ClaimDraft(
                claim_id="s0c0",
                claim_index=0,
                claim_type="reasoning",
                text="Reasoning.",
                annotation_type="reasoning",
                payload={},
                cited_ids=["not-citable-here"],
                flags=["weak"],
            )
        ]
    )
    assert ledger == [
        {
            "claim_id": "s0c0",
            "claim_type": "reasoning",
            "text": "Reasoning.",
            "cited_ids": ["not-citable-here"],
            "flags": ["weak"],
            "ledger_note": "context, never evidence — not citable",
        }
    ]


def test_validator_reject_reasons_are_reachable() -> None:
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "11111111-1111-1111-1111-111111111111",
                            "quote": "alpha quoted evidence",
                        }
                    ],
                }
            ),
            available_claim_types={"gap", "reasoning"},
        )
        == "substrate_ungated_type"
    )
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "finding",
                    "text": "Finding claim.",
                    "cited_finding_ids": ["missing"],
                }
            )
        )
        == "uncited_finding_id"
    )
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "11111111-1111-1111-1111-111111111111",
                            "quote": "alpha quoted evidence",
                        }
                    ],
                }
            ),
            citable_chunk_ids=set(),
        )
        == "unreturned_chunk_id"
    )
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "22222222-2222-2222-2222-222222222222",
                            "quote": "beta quoted evidence",
                        }
                    ],
                }
            ),
            citable_chunk_ids={"22222222-2222-2222-2222-222222222222"},
        )
        == "unappraised_doc_citation"
    )


def test_pattern_theme_gap_and_reasoning_validation_edges() -> None:
    assert (
        _rejected_reason(
            ClaimWire(
                claim_type="pattern",
                text="Wrong count.",
                pattern=PatternPayloadWire(
                    kind="coverage_count",
                    computed_from="characterisation_coverage",
                    path=["distributions", "origin"],
                    stated={"uploaded": 99},
                    base="screened",
                ),
            )
        )
        == "pattern_mismatch"
    )
    assert (
        _rejected_reason(_claim({"claim_type": "pattern", "text": "Scanned shape."}))
        == "content_scan_prohibited"
    )
    assert (
        _rejected_reason(
            ClaimWire(
                claim_type="theme",
                text="Unknown theme.",
                theme=ThemePayloadWire(
                    source="characterisation", referenced_ids=["missing"], base="screened"
                ),
            )
        )
        == "theme_unknown_id"
    )
    assert (
        _rejected_reason(
            ClaimWire(
                claim_type="gap",
                text="Sparse gap.",
                gap=GapPayloadWire(
                    grade="acknowledged_sparsity",
                    coverage_base="screened",
                    sparsity=SparsitySignalWire(
                        path=["distributions", "origin", "uploaded"], stated_count=99
                    ),
                ),
            )
        )
        == "sparsity_mismatch"
    )

    reasoning = [
        _claim({"claim_type": "reasoning", "text": f"Reasoning {index}."})
        for index in range(4)
    ]
    batch = validate_claims(
        reasoning,
        substrate=_substrate(),
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        spans=[(index, index + 1) for index in range(len(reasoning))],
    )
    assert [rejection.reason for rejection in batch.rejected] == ["reasoning_over_cap"]


def test_gap_degradation_and_caveat_payloads() -> None:
    substrate = _substrate()
    degraded = validate_claims(
        [
            ClaimWire(
                claim_type="gap",
                text="No studies were found in the searched space.",
                gap=GapPayloadWire(
                    grade="corpus_absence",
                    coverage_base="searched",
                    coverage_record_id="cov-bad",
                ),
            )
        ],
        substrate=substrate,
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        spans=[(0, 1)],
    )
    assert degraded.drafts[0].flags == ["gap_degraded"]
    assert degraded.drafts[0].payload["gap"]["grade"] == "inferred"
    assert degraded.drafts[0].payload["gap"]["coverage_base"] == "screened"

    caveated = validate_claims(
        [
            ClaimWire(
                claim_type="gap",
                text="No studies were found in the searched space.",
                gap=GapPayloadWire(
                    grade="corpus_absence",
                    coverage_base="searched",
                    coverage_record_id="cov-ok",
                ),
            )
        ],
        substrate=substrate,
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        spans=[(0, 1)],
    )
    caveat = caveated.drafts[0].payload["gap"]["caveat"]
    assert caveat == {
        "search_space": [{"backend": "fixture"}],
        "adequacy_verdict": "adequate",
        "verdict_origin": "model",
    }


def test_reasoning_cap_binds_across_repair() -> None:
    """The per-section reasoning cap must bind across the initial and repair
    passes together, so ``reasoning_count_start`` (accepted claims from
    outside this batch) counts toward the cap."""
    claim = _claim({"claim_type": "reasoning", "text": "Reasoning claim."})

    at_cap = validate_claims(
        [claim],
        substrate=_substrate(),
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        spans=[(0, 1)],
        reasoning_count_start=REASONING_CLAIMS_MAX,
    )
    assert not at_cap.drafts
    assert [rejection.reason for rejection in at_cap.rejected] == ["reasoning_over_cap"]

    fresh = validate_claims(
        [claim],
        substrate=_substrate(),
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        spans=[(0, 1)],
        reasoning_count_start=0,
    )
    assert not fresh.rejected
    assert len(fresh.drafts) == 1


def test_finding_claim_with_empty_grounding_is_weakly_grounded() -> None:
    """A finding with zero grounding entries is the extreme anchor failure:
    nothing to verify, so the claim is flagged weakly grounded rather than
    rejected."""
    substrate = _substrate()
    finding = substrate.finding_by_id["finding-1"]
    empty_finding = replace(finding, grounding=[])
    substrate = replace(substrate, finding_by_id={"finding-1": empty_finding})

    batch = validate_claims(
        [
            _claim(
                {
                    "claim_type": "finding",
                    "text": "Finding claim.",
                    "cited_finding_ids": ["finding-1"],
                }
            )
        ],
        substrate=substrate,
        section_index=0,
        section_group_ids={"group-1"},
        citable_finding_ids={"finding-1"},
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        spans=[(0, 1)],
    )
    assert not batch.rejected
    draft = batch.drafts[0]
    assert draft.weakly_grounded is True
    assert "quote_unverified" in draft.flags
    assert draft.payload["anchors"] == [
        {"finding_id": "finding-1", "quote": None, "match_status": "failed", "spans": []}
    ]
    assert draft.citation_rows == []


def test_anchor_counts_tallies_verified_and_failed_anchors() -> None:
    claim_with_anchors = ClaimDraft(
        claim_id="s0c0",
        claim_index=0,
        claim_type="finding",
        text="Finding claim.",
        annotation_type="citation",
        payload={
            "anchors": [
                {
                    "finding_id": "finding-1",
                    "quote": None,
                    "match_status": "failed",
                    "spans": [],
                },
                {
                    "finding_id": "finding-1",
                    "quote": "finding anchor quote",
                    "match_status": "exact",
                    "spans": [{"chunk_id": "chunk-1", "start": 0, "end": 20}],
                },
            ]
        },
    )
    claim_with_citation = ClaimDraft(
        claim_id="s0c1",
        claim_index=1,
        claim_type="chunk",
        text="Chunk claim.",
        annotation_type="citation",
        payload={"citations": [{"chunk_id": "chunk-1"}]},
    )
    assert _anchor_counts([claim_with_anchors, claim_with_citation]) == (2, 1)


# --- ADR 0015 §2/§4: span binder + one-pass splice/rebind (pure) ---


def test_bind_spans_duplicate_texts_bind_ordered_cursor() -> None:
    prose = "the rate fell the rate fell"
    spans = bind_spans(prose, ["the rate fell", "the rate fell"])
    assert spans == [(0, 13), (14, 27)]
    for text, span in zip(["the rate fell", "the rate fell"], spans, strict=True):
        assert span is not None
        assert prose[span[0] : span[1]] == text


def test_bind_spans_out_of_order_binds_via_fallback_without_overlap() -> None:
    prose = "alpha beta"
    # "beta" binds forward (cursor past it), "alpha" only via the non-overlapping
    # fallback scanning from the start.
    spans = bind_spans(prose, ["beta", "alpha"])
    assert spans == [(6, 10), (0, 5)]


def test_bind_spans_overlap_empty_and_missing_are_none_fail_closed() -> None:
    # Overlap forbidden: the second "aa" can only land overlapping the first.
    assert bind_spans("aaa", ["aa", "aa"]) == [(0, 2), None]
    # Empty text never binds.
    assert bind_spans("anything", [""]) == [None]
    # Missing text never binds.
    assert bind_spans("present", ["absent"]) == [None]


def test_bind_spans_post_condition_roundtrips() -> None:
    prose = "one two three two one"
    texts = ["one", "two", "three", "one"]
    spans = bind_spans(prose, texts)
    for text, span in zip(texts, spans, strict=True):
        assert span is not None
        assert prose[span[0] : span[1]] == text


def test_splice_and_rebind_mixed_keep_replace_delete_roundtrips() -> None:
    prose = "AAA BBB CCC DDD"
    items = [
        SpliceItem(key=0, span=(0, 3), replacement=None, claim_text=None),
        SpliceItem(key=1, span=(4, 7), replacement="XXYY", claim_text="XX"),
        SpliceItem(key=2, span=(8, 11), replacement="", claim_text=None),
        SpliceItem(key=3, span=(12, 15), replacement=None, claim_text=None),
    ]
    new_prose, span_map = splice_and_rebind(prose, items)
    # Kept A and D round-trip; repaired B records the located claim text; the
    # deleted C carries no map entry.
    expected = {0: "AAA", 1: "XX", 3: "DDD"}
    for key, text in expected.items():
        span = span_map[key]
        assert span is not None
        assert new_prose[span[0] : span[1]] == text
    assert 2 not in span_map
    # The deleted segment's text is gone; the connective prose survives.
    assert "CCC" not in new_prose
    assert "XXYY" in new_prose


def test_splice_and_rebind_repaired_text_not_substring_is_validation_failure() -> None:
    prose = "AAA BBB"
    items = [
        SpliceItem(key=0, span=(0, 3), replacement=None, claim_text=None),
        # The claim text is not a substring of the replacement segment.
        SpliceItem(key=1, span=(4, 7), replacement="ZZZZ", claim_text="QQ"),
    ]
    _new_prose, span_map = splice_and_rebind(prose, items)
    assert span_map[1] is None


# --- ADR 0015 §8 / B-B3: default metadata set (owner-adopted) ---


def test_doc_record_default_metadata_present_and_absent() -> None:
    present = SimpleNamespace(
        pss_id="11111111-1111-1111-1111-111111111111",
        origin="uploaded",
        primary_evidence_type="rct",
        text_basis="full_text",
        quality_score=3,
        metadata={
            "title": "Doc with metadata",
            "year": 2024,
            "publisher_org": "Example Journal",
            "provider_fields": {"cited_by_count": 42},
        },
    )
    doc = _doc_record(present, set())
    assert doc["year"] == 2024
    assert doc["primary_evidence_type"] == "rct"
    assert doc["appraisal_tier"] == "3"
    assert doc["venue"] == "Example Journal"
    assert doc["cited_by"] == 42
    # is_retracted is never surfaced.
    assert "is_retracted" not in doc

    absent = SimpleNamespace(
        pss_id="22222222-2222-2222-2222-222222222222",
        origin="uploaded",
        primary_evidence_type=None,
        text_basis="full_text",
        quality_score=None,
        metadata={"title": "Bare doc"},
    )
    bare = _doc_record(absent, set())
    for key in ("year", "publication_year", "venue", "cited_by"):
        assert key not in bare
    assert bare["primary_evidence_type"] is None
    assert bare["appraisal_tier"] is None
    assert "is_retracted" not in bare


def test_finding_record_default_metadata_present_and_absent() -> None:
    present = SimpleNamespace(
        finding_id="finding-1",
        project_source_snapshot_id="11111111-1111-1111-1111-111111111111",
        intervention="A",
        outcome="B",
        population=None,
        comparator=None,
        effect_direction="increase",
        estimate_level=None,
        study_design=None,
        study_geography="England",
        stratum_qualifiers=[],
        statistics={},
        causality_by_design=None,
        effect_basis="observed",
        is_primary=None,
        field_coverage={},
        primary_evidence_type="systematic_review",
        quality_score=2,
        metadata={
            "title": "Finding doc",
            "publication_year": 2019,
            "publisher_org": "Review Press",
            "provider_fields": {"cited_by_count": 7},
        },
    )
    record = _finding_record(present)
    assert record["year"] == 2019
    assert record["evidence_type"] == "systematic_review"
    assert record["appraisal_label"] == "2"
    assert record["venue"] == "Review Press"
    assert record["cited_by"] == 7
    assert "is_retracted" not in record
    # Task 020 C1: effect_basis/study_geography are always-present-nullable,
    # exactly like study_design — never omit-if-absent.
    assert record["study_geography"] == "England"
    assert record["effect_basis"] == "observed"

    absent = SimpleNamespace(
        finding_id="finding-2",
        project_source_snapshot_id="22222222-2222-2222-2222-222222222222",
        intervention="A",
        outcome="B",
        population=None,
        comparator=None,
        effect_direction="increase",
        estimate_level=None,
        study_design=None,
        study_geography=None,
        stratum_qualifiers=[],
        statistics={},
        causality_by_design=None,
        effect_basis=None,
        is_primary=None,
        field_coverage={},
        primary_evidence_type=None,
        quality_score=None,
        metadata={"title": "Bare finding doc"},
    )
    bare = _finding_record(absent)
    for key in ("year", "evidence_type", "appraisal_label", "venue", "cited_by"):
        assert key not in bare
    assert "is_retracted" not in bare
    # Always-present-nullable: present even for a bare row, just None.
    assert bare["study_geography"] is None
    assert bare["effect_basis"] is None


# --- ADR 0015 §2 / B-B3: judge envelope v2 (intent + section_focus + finding
# anchored chunk text) ---


def test_build_envelope_carries_intent_and_section_focus() -> None:
    envelope = build_envelope(
        claims=[],
        chunks=[],
        section_prose="prose",
        span_map=[],
        intent="What works?",
        section_focus="key findings",
    )
    assert envelope["intent"] == "What works?"
    assert envelope["section_focus"] == "key findings"
    messages = build_judge_messages(envelope)
    user = messages[1]["content"]
    assert "What works?" in user
    assert "key findings" in user


class _CapturingJudge(StubGroundingJudgeBackend):
    def __init__(self) -> None:
        super().__init__()
        self.envelopes: list[dict[str, Any]] = []

    def judge_block(self, envelope: dict[str, Any]) -> Any:
        self.envelopes.append(envelope)
        return super().judge_block(envelope)


def test_judge_envelope_includes_finding_anchor_chunks_deduped_and_context() -> None:
    substrate = _substrate()
    anchored_chunk_id = "11111111-1111-1111-1111-111111111111"
    finding_claim = ClaimDraft(
        claim_id="s0c0",
        claim_index=0,
        claim_type="finding",
        text="Finding claim.",
        annotation_type="citation",
        payload={
            "cited_finding_ids": ["finding-1"],
            "anchors": [
                {
                    "finding_id": "finding-1",
                    "quote": "finding anchor quote",
                    "match_status": "exact",
                    "spans": [
                        {"chunk_id": anchored_chunk_id, "start": 0, "end": 20}
                    ],
                }
            ],
        },
        # Deliberately empty: the anchored chunk must still reach the envelope
        # from the anchors, not only from judge_chunk_ids.
        judge_chunk_ids=set(),
        span=(0, 14),
    )
    chunk_claim = ClaimDraft(
        claim_id="s0c1",
        claim_index=1,
        claim_type="chunk",
        text="Chunk claim.",
        annotation_type="citation",
        payload={"citations": [{"cited_chunk_record_id": anchored_chunk_id}]},
        judge_chunk_ids={anchored_chunk_id},
        span=(15, 27),
    )
    judge = _CapturingJudge()
    calls, _usage, _unspanned = _judge_claims(
        claims=[finding_claim, chunk_claim],
        substrate=substrate,
        grounding_judge_backend=judge,
        section_prose="Finding claim. Chunk claim.",
        intent="The intent",
        section_focus="A focus",
    )
    assert calls == 1
    envelope = judge.envelopes[0]
    assert envelope["intent"] == "The intent"
    assert envelope["section_focus"] == "A focus"
    chunk_ids = [chunk["chunk_record_id"] for chunk in envelope["chunks"]]
    # The anchored chunk is present exactly once (deduped against the chunk claim).
    assert chunk_ids.count(anchored_chunk_id) == 1
    anchored = next(
        chunk for chunk in envelope["chunks"] if chunk["chunk_record_id"] == anchored_chunk_id
    )
    assert anchored["content"] == "alpha quoted evidence appears here"
    assert anchored["text_basis"] == "abstract_only"
    assert anchored["segmentation_policy"] == "manual_v1"


# --- ADR 0015 §8 / B-B3: conclusions exemption + focus ---


def test_proposed_conclusion_title_rejected_but_injected_title_is_exempt() -> None:
    proposal = SectionProposalWire(
        sections=[SectionWire(title="Conclusion", focus="A verdict on the evidence.")]
    )
    _sections, reasons, _norm = _validate_sections(proposal, grouping_group_ids=None)
    assert any("title_forbidden" in reason for reason in reasons)
    # The code-injected conclusions section is exempt by construction — it never
    # passes through _validate_sections, so its title is not checked.
    injected = SectionSpec(
        title=CONCLUSIONS_TITLE, focus=_conclusions_focus("What works?"), role="conclusions"
    )
    assert injected.title == "Conclusions"
    assert injected.role == "conclusions"
    assert "What works?" in injected.focus
    assert "recommendations" in injected.focus


# --- Review-stack fixes (018 step 7): empty gate + unspanned-lane honesty ---


def test_empty_claim_type_gate_rejects_never_reopens() -> None:
    """An explicitly EMPTY claim-type gate rejects every gated type — it must
    never be treated as "unset" and silently reopen to the full substrate set
    (the key-findings intersection can be empty on a thin substrate)."""
    assert (
        _rejected_reason(
            _claim(
                {
                    "claim_type": "chunk",
                    "text": "Chunk claim.",
                    "citations": [
                        {
                            "chunk_record_id": "11111111-1111-1111-1111-111111111111",
                            "quote": "alpha quoted evidence",
                        }
                    ],
                }
            ),
            available_claim_types=set(),
        )
        == "substrate_ungated_type"
    )


def _accounting() -> SectionAccounting:
    return SectionAccounting(
        tool_call_counts={},
        tool_call_count=0,
        gathered_id_hash="",
        turns_used=0,
        turn_cap_hit=False,
    )


def _run_section_claims(
    wire: SectionProseWire,
    accounting: SectionAccounting,
    *,
    available_claim_types: set[str] | None = None,
) -> None:
    _section_claims(
        section_index=0,
        raw_claims=wire,
        seed={},
        transcript=[],
        substrate=_substrate(),
        section_group_ids={"group-1"},
        citable_finding_ids=set(),
        citable_chunk_ids={"11111111-1111-1111-1111-111111111111"},
        synthesis_backend=StubSynthesisBackend(),
        grounding_judge_backend=StubGroundingJudgeBackend(),
        available_claim_types=available_claim_types or {"gap", "chunk"},
        accounting=accounting,
    )


def test_unspanned_lane_skipped_flag_set_when_no_judged_claims() -> None:
    """Prose carried only by non-judged claim types is never scanned by the
    unspanned lane: the accounting says "skipped", never a clean zero."""
    prose = "Evidence here is thin (stub inference). A further assertive sentence."
    wire = SectionProseWire(
        prose=prose,
        claims=[
            _claim(
                {
                    "claim_type": "gap",
                    "text": "Evidence here is thin (stub inference).",
                    "gap": {"grade": "inferred", "coverage_base": "screened"},
                }
            )
        ],
    )
    accounting = _accounting()
    _run_section_claims(wire, accounting)
    assert accounting.unspanned_lane_skipped is True
    assert accounting.unspanned_assertions == 0


def test_unspanned_lane_not_skipped_when_judge_scanned() -> None:
    """A judged-type claim fires the judge lane over the prose: the skipped
    flag stays False on the scanned path."""
    prose = "As reasoning, the strands point one way (stub inference)."
    wire = SectionProseWire(
        prose=prose,
        claims=[
            _claim(
                {
                    "claim_type": "reasoning",
                    "text": "As reasoning, the strands point one way (stub inference).",
                }
            )
        ],
    )
    accounting = _accounting()
    _run_section_claims(wire, accounting, available_claim_types={"gap", "reasoning"})
    assert accounting.unspanned_lane_skipped is False
