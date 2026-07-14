"""Pure tests for the task-013 synthesis tool and loop layer."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_PROFILE,
    UNIT_CHAR_BUDGET,
    UNIT_POLICY,
)
from policy_atlas.extraction_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.grounding import content_hash
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import chunk_embedding, project_source_snapshot
from policy_atlas.synthesis_backend import SectionProseWire
from policy_atlas.synthesis_tools import (
    BOOST_CLAMP_MAX,
    BOOST_CLAMP_MIN,
    CANDIDATE_POOL_PER_LEG,
    OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS,
    READ_CALLS_PER_TURN_CAP,
    RETRIEVAL_UNIT_CAP,
    SECTION_TURN_CAP,
    SYNTH_CHUNK_TOP_K,
    ChunkRetriever,
    ChunkSearchResult,
    PassThroughChunkReranker,
    RetrievalScope,
    RetrievalUnitCapError,
    SynthesisDirective,
    SynthesisDirectiveError,
    ToolExchange,
    ToolValidationError,
    _group_member_ids,
    build_retrieval_scope,
    build_section_tools,
    gathered_ids,
    make_lookup_reader,
    parse_synthesis_directive,
    run_section_loop,
)
from policy_atlas.usage import UsageResult
from tests.helpers import (
    EVIDENCE_TYPE,
    now,
    seed_project_and_run,
    seed_scope,
    seed_screening_result,
    seed_select_doc,
    seed_source,
)


def _vector(first: float = 0.0, second: float = 0.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    vector[0] = first
    vector[1] = second
    return vector


class FakeEmbedder:
    mode = "stub"

    def __init__(self, vectors: dict[str, list[float]] | None = None) -> None:
        self.vectors = vectors or {}
        self.calls: list[list[str]] = []

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        return [self.vectors.get(text, _vector(1.0)) for text in texts]


class ReverseReranker:
    mode = "reverse"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def rerank(
        self, *, query: str, candidates: list[ChunkSearchResult]
    ) -> list[ChunkSearchResult]:
        self.calls.append({"query": query, "candidate_count": len(candidates)})
        return list(reversed(candidates))


class ScriptedBackend:
    mode = "stub"

    def __init__(self, turns: list[dict[str, Any]]) -> None:
        self.turns = turns
        self.calls: list[dict[str, Any]] = []

    def section_turn(
        self,
        seed: dict[str, Any],
        transcript: list[dict[str, Any]],
        *,
        force_emit: bool,
    ) -> UsageResult[dict[str, Any]]:
        self.calls.append({
            "seed": seed,
            "transcript_len": len(transcript),
            "force_emit": force_emit,
        })
        index = len(self.calls) - 1
        if index >= len(self.turns):
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
        return self.turns[index], None


def _claims(text: str = "x") -> SectionProseWire:
    return SectionProseWire.model_validate(
        {"prose": text, "claims": [{"claim_type": "reasoning", "text": text}]}
    )


def _scope(
    docs: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    units: list[dict[str, Any]],
) -> RetrievalScope:
    return RetrievalScope(docs=docs, chunks=chunks, units=units)


def _one_chunk_scope(*, selected_a: bool = False, selected_b: bool = False) -> RetrievalScope:
    docs = {
        "doc-a": {
            "title": "A",
            "origin": "uploaded",
            "primary_evidence_type": "rct",
            "text_basis": "full_text",
            "appraisal_tier": "3",
            "tags": ["housing"],
            "selected": selected_a,
        },
        "doc-b": {
            "title": "B",
            "origin": "acquired",
            "primary_evidence_type": "review",
            "text_basis": "full_text",
            "appraisal_tier": "5",
            "tags": ["health"],
            "selected": selected_b,
        },
    }
    chunks = {
        "chunk-a": {
            "content": "alpha policy evidence",
            "sequence": 1,
            "pss_id": "doc-a",
            "segmentation_policy": "manual_v1",
            "text_basis": "full_text",
        },
        "chunk-b": {
            "content": "beta policy evidence",
            "sequence": 1,
            "pss_id": "doc-b",
            "segmentation_policy": "manual_v1",
            "text_basis": "abstract_only",
        },
    }
    units = [
        {
            "unit_id": "unit-a",
            "chunk_id": "chunk-a",
            "pss_id": "doc-a",
            "vector": _vector(1.0),
            "text": "alpha policy evidence",
        },
        {
            "unit_id": "unit-b",
            "chunk_id": "chunk-b",
            "pss_id": "doc-b",
            "vector": _vector(0.1),
            "text": "beta policy evidence",
        },
    ]
    return _scope(docs, chunks, units)


def test_parse_synthesis_directive_default_absent() -> None:
    assert parse_synthesis_directive({}, grouping_group_ids=None) == SynthesisDirective()


@pytest.mark.parametrize("context", [{"synthesis": []}, {"synthesis": {"bad": 1}}])
def test_parse_synthesis_directive_rejects_non_object_and_unknown_key(
    context: dict[str, Any],
) -> None:
    with pytest.raises(SynthesisDirectiveError):
        parse_synthesis_directive(context, grouping_group_ids=None)


def test_parse_synthesis_directive_rejects_bad_sections() -> None:
    with pytest.raises(SynthesisDirectiveError, match="forbidden"):
        parse_synthesis_directive(
            {"synthesis": {"sections": [{"title": "Overview", "focus": "x"}]}},
            grouping_group_ids=None,
        )
    with pytest.raises(SynthesisDirectiveError, match="control"):
        parse_synthesis_directive(
            {"synthesis": {"sections": [{"title": "Housing\n", "focus": "x"}]}},
            grouping_group_ids=None,
        )
    with pytest.raises(SynthesisDirectiveError, match="require grouping"):
        parse_synthesis_directive(
            {
                "synthesis": {
                    "sections": [
                        {
                            "title": "Housing",
                            "focus": "x",
                            "group_ids": ["intervention:g01"],
                        }
                    ]
                }
            },
            grouping_group_ids=None,
        )
    with pytest.raises(SynthesisDirectiveError, match="<facet>:gNN"):
        parse_synthesis_directive(
            {
                "synthesis": {
                    "sections": [{"title": "Housing", "focus": "x", "group_ids": ["g1"]}]
                }
            },
            grouping_group_ids={"intervention:g01"},
        )
    with pytest.raises(SynthesisDirectiveError, match="unknown"):
        parse_synthesis_directive(
            {
                "synthesis": {
                    "sections": [
                        {"title": "Housing", "focus": "x", "group_ids": ["outcome:g02"]}
                    ]
                }
            },
            grouping_group_ids={"intervention:g01"},
        )


def test_parse_synthesis_directive_valid_sections_and_boosts_clamp() -> None:
    directive = parse_synthesis_directive(
        {
            "synthesis": {
                "sections": [
                    {
                        "title": "Rough sleeping",
                        "focus": "interventions",
                        "group_ids": ["intervention:g01"],
                    }
                ],
                "retrieval_boosts": {
                    "columns": {"origin": {"uploaded": 100}},
                    "tags": {"housing": 0.001},
                    "appraisal_tier": {"5": 2},
                },
            }
        },
        grouping_group_ids={"intervention:g01"},
    )
    assert directive.sections == [
        {
            "title": "Rough sleeping",
            "focus": "interventions",
            "group_ids": ["intervention:g01"],
        }
    ]
    assert directive.column_boosts == {"origin": {"uploaded": BOOST_CLAMP_MAX}}
    assert directive.tag_boosts == {"housing": BOOST_CLAMP_MIN}
    assert directive.appraisal_tier_boosts == {"5": 2.0}


def test_query_findings_group_id_requires_qualified_form_in_tool_loop() -> None:
    class Backend:
        def section_turn(
            self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
        ) -> UsageResult[dict[str, Any]]:
            del seed, force_emit
            if transcript:
                return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
            return {
                "tool_calls": [
                    {"tool": "query_findings", "arguments": {"group_id": "g01"}}
                ],
                "claims": None,
            }, None

    result = run_section_loop(
        Backend(),
        seed={},
        tools=build_section_tools(
            retriever=None,
            findings_reader=lambda _args: {"iof_findings": []},
            lookup_reader=lambda _args: {},
        ),
    )

    assert result["transcript"][0]["result"] == {
        "error": "group_id must use expected form <facet>:gNN"
    }
    assert result["rejected_tool_calls"] == 1


def test_run_section_loop_batches_a_turns_uncached_query_embeddings() -> None:
    """022 rider 16: N distinct search_chunks queries requested in one turn
    embed in ONE backend call, not N sequential single-text calls."""
    embedder = FakeEmbedder({"alpha": _vector(1.0), "beta": _vector(0.1)})
    retriever = ChunkRetriever(
        _one_chunk_scope(),
        embedder=embedder,
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )

    class _TwoQueryTurnBackend:
        def section_turn(
            self, seed: dict[str, Any], transcript: list[ToolExchange], *, force_emit: bool
        ) -> UsageResult[dict[str, Any]]:
            del seed, force_emit
            if transcript:
                return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None
            return {
                "tool_calls": [
                    {"tool": "search_chunks", "arguments": {"query": "alpha"}},
                    {"tool": "search_chunks", "arguments": {"query": "beta"}},
                    # A repeated query within the same turn must not double-embed.
                    {"tool": "search_chunks", "arguments": {"query": "alpha"}},
                ],
                "claims": None,
            }, None

    tools = build_section_tools(
        retriever=retriever,
        findings_reader=None,
        lookup_reader=lambda _args: {},
    )
    result = run_section_loop(
        _TwoQueryTurnBackend(), seed={}, tools=tools, retriever=retriever
    )

    assert len(embedder.calls) == 1
    assert sorted(embedder.calls[0]) == ["alpha", "beta"]
    # Retrieval stays correct/deterministic per query vector after batching.
    exchanges = result["transcript"]
    alpha_chunks = {
        chunk["chunk_record_id"]
        for exchange in exchanges
        if exchange["arguments"].get("query") == "alpha"
        for chunk in exchange["result"]["chunks"]
    }
    assert "chunk-a" in alpha_chunks


def test_query_findings_group_member_map_rejects_legacy_group_ids() -> None:
    assert _group_member_ids(
        [{"group_id": "intervention:g01", "member_finding_ids": ["f1"]}]
    ) == {"intervention:g01": {"f1"}}

    with pytest.raises(ToolValidationError, match="<facet>:gNN"):
        _group_member_ids([{"label": "Legacy label", "member_finding_ids": ["f1"]}])


def test_parse_synthesis_directive_rejects_bad_boosts() -> None:
    with pytest.raises(SynthesisDirectiveError, match="unknown column"):
        parse_synthesis_directive(
            {"synthesis": {"retrieval_boosts": {"columns": {"year": {"2024": 2}}}}},
            grouping_group_ids=None,
        )
    with pytest.raises(SynthesisDirectiveError, match="number"):
        parse_synthesis_directive(
            {"synthesis": {"retrieval_boosts": {"tags": {"housing": "more"}}}},
            grouping_group_ids=None,
        )


def test_parse_synthesis_directive_screen_confidence_defaults_and_bounds() -> None:
    directive = parse_synthesis_directive(
        {"synthesis": {"retrieval_boosts": {"screen_confidence": {}}}},
        grouping_group_ids=None,
    )
    assert directive.screen_confidence.lo == 1.0
    assert directive.screen_confidence.hi == 2.0

    directive = parse_synthesis_directive(
        {
            "synthesis": {
                "retrieval_boosts": {"screen_confidence": {"lo": 0.5, "hi": 4.0}}
            }
        },
        grouping_group_ids=None,
    )
    assert directive.screen_confidence.lo == 0.5
    assert directive.screen_confidence.hi == 4.0

    for boost in (
        {"lo": 0.49, "hi": 2.0},
        {"lo": 2.0, "hi": 1.0},
        {"lo": 1.0, "hi": 4.01},
        {"lo": True, "hi": 2.0},
    ):
        with pytest.raises(SynthesisDirectiveError, match="screen_confidence"):
            parse_synthesis_directive(
                {"synthesis": {"retrieval_boosts": {"screen_confidence": boost}}},
                grouping_group_ids=None,
            )


def test_retriever_ranking_is_deterministic_and_lexical_match_is_reachable() -> None:
    scope = _scope(
        docs={
            "doc-a": {
                "title": "A",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
            }
        },
        chunks={
            "chunk-a": {
                "content": "needle words",
                "sequence": 1,
                "pss_id": "doc-a",
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            }
        },
        units=[
            {
                "unit_id": "unit-a",
                "chunk_id": "chunk-a",
                "pss_id": "doc-a",
                "vector": _vector(0.0),
                "text": "needle words",
            }
        ],
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"needle": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    first = retriever.search("needle")
    second = retriever.search("needle")
    assert first == second
    assert [chunk["chunk_record_id"] for chunk in first] == ["chunk-a"]


def test_retriever_selection_prior_reorders_without_excluding_unselected() -> None:
    retriever = ChunkRetriever(
        _one_chunk_scope(selected_b=True),
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    results = retriever.search("policy")
    assert [chunk["chunk_record_id"] for chunk in results] == ["chunk-b", "chunk-a"]
    assert {chunk["origin"] for chunk in results} == {"selected", "unselected_screened"}
    assert retriever.provenance()["selection_prior"] == 2.0


def test_retriever_search_results_expose_chunk_text_basis_values() -> None:
    retriever = ChunkRetriever(
        _one_chunk_scope(),
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )

    results = retriever.search("policy")

    assert {chunk["chunk_record_id"]: chunk["text_basis"] for chunk in results} == {
        "chunk-a": "full_text",
        "chunk-b": "abstract_only",
    }


def test_retriever_directive_boosts_reweight_but_do_not_surface_zero_relevance() -> None:
    docs = _one_chunk_scope().docs
    docs["doc-c"] = {
        "title": "C",
        "origin": "acquired",
        "primary_evidence_type": "review",
        "text_basis": "full_text",
        "appraisal_tier": "5",
        "tags": ["boosted"],
        "selected": False,
    }
    chunks = _one_chunk_scope().chunks
    chunks["chunk-c"] = {
        "content": "irrelevant text",
        "sequence": 1,
        "pss_id": "doc-c",
        "segmentation_policy": "manual_v1",
        "text_basis": "full_text",
    }
    units = _one_chunk_scope().units
    units.append({
        "unit_id": "unit-c",
        "chunk_id": "chunk-c",
        "pss_id": "doc-c",
        "vector": _vector(0.0),
        "text": "irrelevant text",
    })
    directive = SynthesisDirective(
        column_boosts={"origin": {"acquired": 10.0}},
        tag_boosts={"boosted": 10.0, "missing": 2.0},
    )
    retriever = ChunkRetriever(
        _scope(docs, chunks, units),
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=directive,
        reranker=PassThroughChunkReranker(),
    )
    results = retriever.search("policy")
    ids = [chunk["chunk_record_id"] for chunk in results]
    assert ids[0] == "chunk-b"
    assert "chunk-c" not in ids
    assert retriever.provenance()["unmatched_boosts"] == {"tags": ["missing"]}


def test_retriever_screen_confidence_multiplier_defaults_missing_and_suppresses() -> None:
    directive = parse_synthesis_directive(
        {
            "synthesis": {
                "retrieval_boosts": {"screen_confidence": {"lo": 2.0, "hi": 4.0}}
            }
        },
        grouping_group_ids=None,
    )
    scope = _scope(
        docs={
            "doc-conf": {
                "title": "Confident",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
                "screen_confidence": 0.25,
            },
            "doc-missing": {
                "title": "Missing",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
            },
        },
        chunks={
            "chunk-conf": {
                "content": "policy confidence evidence",
                "sequence": 1,
                "pss_id": "doc-conf",
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
            "chunk-missing": {
                "content": "policy missing evidence",
                "sequence": 2,
                "pss_id": "doc-missing",
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
        },
        units=[
            {
                "unit_id": "unit-conf",
                "chunk_id": "chunk-conf",
                "pss_id": "doc-conf",
                "vector": _vector(1.0),
                "text": "policy confidence evidence",
            },
            {
                "unit_id": "unit-missing",
                "chunk_id": "chunk-missing",
                "pss_id": "doc-missing",
                "vector": _vector(1.0),
                "text": "policy missing evidence",
            },
        ],
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=directive,
        reranker=PassThroughChunkReranker(),
    )
    retriever.search("policy")
    factors = retriever.provenance()["soft_prior_factors"]
    assert factors["chunk-conf"]["screen_confidence"] == 2.5
    assert factors["chunk-conf"]["executed_multiplier"] == 2.5
    assert factors["chunk-missing"]["screen_confidence"] == 1.0
    assert factors["chunk-missing"]["executed_multiplier"] == 1.0

    suppressed = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=directive,
        reranker=PassThroughChunkReranker(),
        selection_reference_resolved=True,
    )
    suppressed.search("policy")
    suppressed_provenance = suppressed.provenance()
    assert suppressed_provenance["confidence_suppressed"] is True
    assert (
        suppressed_provenance["soft_prior_factors"]["chunk-conf"][
            "screen_confidence"
        ]
        == 1.0
    )
    assert (
        suppressed_provenance["soft_prior_factors"]["chunk-conf"][
            "confidence_suppressed"
        ]
        is True
    )


def test_retriever_soft_prior_product_clamps_and_records_raw_factors() -> None:
    scope = _scope(
        docs={
            "doc-high": {
                "title": "High",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": "5",
                "tags": ["housing"],
                "selected": True,
                "screen_confidence": 1.0,
            },
            "doc-low": {
                "title": "Low",
                "origin": "acquired",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": "1",
                "tags": ["health"],
                "selected": False,
                "screen_confidence": 0.0,
            },
        },
        chunks={
            "chunk-high": {
                "content": "policy high evidence",
                "sequence": 1,
                "pss_id": "doc-high",
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
            "chunk-low": {
                "content": "policy low evidence",
                "sequence": 2,
                "pss_id": "doc-low",
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
        },
        units=[
            {
                "unit_id": "unit-high",
                "chunk_id": "chunk-high",
                "pss_id": "doc-high",
                "vector": _vector(1.0),
                "text": "policy high evidence",
            },
            {
                "unit_id": "unit-low",
                "chunk_id": "chunk-low",
                "pss_id": "doc-low",
                "vector": _vector(1.0),
                "text": "policy low evidence",
            },
        ],
    )
    directive = SynthesisDirective(
        column_boosts={"origin": {"uploaded": 10.0, "acquired": 0.1}},
        tag_boosts={"housing": 10.0, "health": 0.1},
        appraisal_tier_boosts={"5": 10.0, "1": 0.1},
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=directive,
        reranker=PassThroughChunkReranker(),
    )
    retriever.search("policy")
    factors = retriever.provenance()["soft_prior_factors"]

    assert factors["chunk-high"]["selection"] == 2.0
    assert factors["chunk-high"]["columns"] == {"origin": {"uploaded": 10.0}}
    assert factors["chunk-high"]["tags"] == {"housing": 10.0}
    assert factors["chunk-high"]["appraisal_tier"] == 10.0
    assert factors["chunk-high"]["screen_confidence"] == 2.0
    assert factors["chunk-high"]["raw_multiplier"] == 4000.0
    assert factors["chunk-high"]["executed_multiplier"] == BOOST_CLAMP_MAX

    assert factors["chunk-low"]["raw_multiplier"] == pytest.approx(0.001)
    assert factors["chunk-low"]["executed_multiplier"] == BOOST_CLAMP_MIN


def test_retriever_reranker_invoked_and_top_k_cap_enforced() -> None:
    docs: dict[str, dict[str, Any]] = {}
    chunks: dict[str, dict[str, Any]] = {}
    units: list[dict[str, Any]] = []
    for index in range(SYNTH_CHUNK_TOP_K + 3):
        doc_id = f"doc-{index:02d}"
        chunk_id = f"chunk-{index:02d}"
        docs[doc_id] = {
            "title": f"Doc {index}",
            "origin": "uploaded",
            "primary_evidence_type": None,
            "text_basis": "full_text",
            "appraisal_tier": None,
            "tags": [],
            "selected": False,
        }
        chunks[chunk_id] = {
            "content": f"policy evidence {index}",
            "sequence": index,
            "pss_id": doc_id,
            "segmentation_policy": "manual_v1",
            "text_basis": "full_text",
        }
        units.append({
            "unit_id": f"unit-{index:02d}",
            "chunk_id": chunk_id,
            "pss_id": doc_id,
            "vector": _vector(1.0 + index / 100),
            "text": f"policy evidence {index}",
        })
    reranker = ReverseReranker()
    retriever = ChunkRetriever(
        _scope(docs, chunks, units),
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=reranker,
    )
    results = retriever.search("policy")
    assert reranker.calls == [{"query": "policy", "candidate_count": SYNTH_CHUNK_TOP_K + 3}]
    assert len(results) == SYNTH_CHUNK_TOP_K
    assert results[0]["chunk_record_id"] == "chunk-10"


def test_retriever_tie_breaks_by_unit_and_chunk_id() -> None:
    docs: dict[str, dict[str, Any]] = {
        "doc-a": {
            "title": "A",
            "origin": "uploaded",
            "primary_evidence_type": None,
            "text_basis": "full_text",
            "appraisal_tier": None,
            "tags": [],
            "selected": False,
        },
        "doc-b": {
            "title": "B",
            "origin": "uploaded",
            "primary_evidence_type": None,
            "text_basis": "full_text",
            "appraisal_tier": None,
            "tags": [],
            "selected": False,
        },
    }
    chunks: dict[str, dict[str, Any]] = {
        "a": {
            "content": "same",
            "sequence": 1,
            "pss_id": "doc-a",
            "segmentation_policy": "manual_v1",
            "text_basis": "full_text",
        },
        "b": {
            "content": "same",
            "sequence": 1,
            "pss_id": "doc-b",
            "segmentation_policy": "manual_v1",
            "text_basis": "full_text",
        },
    }
    units: list[dict[str, Any]] = [
        {
            "unit_id": "2",
            "chunk_id": "b",
            "pss_id": "doc-b",
            "vector": _vector(1.0),
            "text": "same",
        },
        {
            "unit_id": "1",
            "chunk_id": "a",
            "pss_id": "doc-a",
            "vector": _vector(1.0),
            "text": "same",
        },
    ]
    retriever = ChunkRetriever(
        _scope(docs, chunks, units),
        embedder=FakeEmbedder({"same": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    assert [result["chunk_record_id"] for result in retriever.search("same")] == ["a", "b"]


def test_retrieval_unit_cap_error_names_cap() -> None:
    error = RetrievalUnitCapError(unit_count=RETRIEVAL_UNIT_CAP + 1, cap=RETRIEVAL_UNIT_CAP)
    assert error.unit_count == RETRIEVAL_UNIT_CAP + 1
    assert error.cap == RETRIEVAL_UNIT_CAP
    assert "RETRIEVAL_UNIT_CAP" in str(error)


def test_build_section_tools_substrate_availability_and_argument_validation() -> None:
    calls = {"lookup": 0}

    def lookup_reader(arguments: dict[str, Any]) -> dict[str, Any]:
        calls["lookup"] += 1
        return {"kind": arguments["kind"], "result": {}}

    tools = build_section_tools(
        retriever=None,
        findings_reader=None,
        lookup_reader=lookup_reader,
    )
    assert set(tools) == {"lookup"}
    assert tools["lookup"]({"kind": "coverage_records"}) == {
        "kind": "coverage_records",
        "result": {},
    }
    with pytest.raises(ToolValidationError):
        tools["lookup"]({"kind": "coverage_records", "extra": True})


def test_search_chunks_char_budget_charges_only_new_content_and_repeats_stay_citable() -> None:
    scope = _one_chunk_scope()
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    tools = build_section_tools(
        retriever=retriever,
        findings_reader=lambda _args: {"findings": []},
        lookup_reader=lambda args: {"kind": args["kind"], "result": {}},
        char_budget=len("alpha policy evidence"),
    )
    first = tools["search_chunks"]({"query": "policy"})
    assert [chunk["chunk_record_id"] for chunk in first["chunks"]] == ["chunk-a"]
    assert first["chunks"][0]["text_basis"] == "full_text"
    assert first["truncated"] is True
    second = tools["search_chunks"]({"query": "policy"})
    # Contract 022 item 12: repeated records are reference-only and charge no
    # additional content budget while still conferring citation eligibility.
    assert second["chunks"] == [
        {"id": "chunk-a", "chunk_record_id": "chunk-a", "already_returned": True}
    ]
    assert second["truncated"] is True
    assert gathered_ids([
        {"tool": "search_chunks", "arguments": {}, "result": second},
    ]) == {"chunk_ids": {"chunk-a"}, "finding_ids": set()}


def test_section_tools_deduplicate_findings_and_lookup_records() -> None:
    finding = {
        "kind": "iof",
        "finding_id": "finding-1",
        "document_title": "Doc",
        "intervention": "Coaching",
    }
    tools = build_section_tools(
        retriever=None,
        findings_reader=lambda _args: {"iof_findings": [finding], "iof_truncated": False},
        lookup_reader=lambda args: {
            "kind": args["kind"],
            "result": [
                {
                    "search_coverage_record_id": "coverage-1",
                    "stop_condition": "saturated",
                }
            ],
        },
    )

    first_findings = tools["query_findings"]({"kinds": ["iof"]})
    second_findings = tools["query_findings"]({"kinds": ["iof"]})
    assert first_findings["iof_findings"] == [finding]
    assert second_findings["iof_findings"] == [
        {
            "id": "finding-1",
            "finding_id": "finding-1",
            "kind": "iof",
            "already_returned": True,
        }
    ]
    assert gathered_ids([
        {"tool": "query_findings", "arguments": {}, "result": second_findings}
    ]) == {"chunk_ids": set(), "finding_ids": {"finding-1"}}

    first_lookup = tools["lookup"]({"kind": "coverage_records"})
    second_lookup = tools["lookup"]({"kind": "coverage_records"})
    assert first_lookup["result"][0]["search_coverage_record_id"] == "coverage-1"
    assert second_lookup["already_returned"] is True
    assert second_lookup["kind"] == "coverage_records"
    assert second_lookup["id"].startswith("lookup:")


def test_search_chunks_budget_skip_and_continue_returns_later_smaller_candidate() -> None:
    doc_big = str(uuid.uuid4())
    doc_small = str(uuid.uuid4())
    scope = _scope(
        docs={
            doc_big: {
                "title": "Big",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
            },
            doc_small: {
                "title": "Small",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
            },
        },
        chunks={
            "chunk-big": {
                "content": "policy " + ("x" * 40),
                "sequence": 1,
                "pss_id": doc_big,
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
            "chunk-small": {
                "content": "tiny",
                "sequence": 2,
                "pss_id": doc_small,
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
        },
        units=[
            {
                "unit_id": "unit-big",
                "chunk_id": "chunk-big",
                "pss_id": doc_big,
                "vector": _vector(2.0),
                "text": "policy big",
            },
            {
                "unit_id": "unit-small",
                "chunk_id": "chunk-small",
                "pss_id": doc_small,
                "vector": _vector(1.0),
                "text": "policy tiny",
            },
        ],
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    tools = build_section_tools(
        retriever=retriever,
        findings_reader=None,
        lookup_reader=lambda args: {"kind": args["kind"], "result": {}},
        char_budget=len("tiny"),
    )

    result = tools["search_chunks"]({"query": "policy"})

    assert [chunk["chunk_record_id"] for chunk in result["chunks"]] == ["chunk-small"]
    assert result["truncated"] is True


def test_windowed_returns_only_for_oversized_chunks_and_use_retained_offsets() -> None:
    normal_doc = str(uuid.uuid4())
    oversized_doc = str(uuid.uuid4())
    normal_content = "normal chunk content with policy signal"
    oversized_content = (
        "a" * 900
        + "matched oversized policy unit"
        + "b" * (UNIT_CHAR_BUDGET + 200)
    )
    match_start = oversized_content.index("matched")
    match_end = match_start + len("matched oversized policy unit")
    scope = _scope(
        docs={
            normal_doc: {
                "title": "Normal",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
            },
            oversized_doc: {
                "title": "Oversized",
                "origin": "uploaded",
                "primary_evidence_type": None,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": [],
                "selected": False,
            },
        },
        chunks={
            "chunk-normal": {
                "content": normal_content,
                "sequence": 1,
                "pss_id": normal_doc,
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
            "chunk-oversized": {
                "content": oversized_content,
                "sequence": 2,
                "pss_id": oversized_doc,
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
        },
        units=[
            {
                "unit_id": "unit-normal",
                "chunk_id": "chunk-normal",
                "pss_id": normal_doc,
                "vector": _vector(1.0),
                "text": normal_content,
                "start": 5,
                "end": 15,
            },
            {
                "unit_id": "unit-oversized",
                "chunk_id": "chunk-oversized",
                "pss_id": oversized_doc,
                "vector": _vector(2.0),
                "text": oversized_content[match_start:match_end],
                "start": match_start,
                "end": match_end,
            },
        ],
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder(
            {"normal": _vector(1.0), "oversized": _vector(2.0)}
        ),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )

    normal = next(
        chunk
        for chunk in retriever.search("normal")
        if chunk["chunk_record_id"] == "chunk-normal"
    )
    assert normal["content"] == normal_content
    assert "window_start" not in normal
    oversized = retriever.search("oversized")[0]
    window_start = max(0, match_start - OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS)
    window_end = min(
        len(oversized_content),
        match_end + OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS,
    )
    assert oversized["chunk_record_id"] == "chunk-oversized"
    assert oversized["content"] == oversized_content[window_start:window_end]
    assert oversized["content"] in oversized_content
    assert oversized["window_start"] == window_start
    assert oversized["window_end"] == window_end


def test_search_chunks_scope_filters_fail_closed_per_argument_and_combine() -> None:
    doc_a = str(uuid.uuid4())
    doc_b = str(uuid.uuid4())
    scope = _scope(
        docs={
            doc_a: {
                "title": "A",
                "origin": "uploaded",
                "primary_evidence_type": EVIDENCE_TYPE,
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": ["housing"],
                "selected": False,
            },
            doc_b: {
                "title": "B",
                "origin": "uploaded",
                "primary_evidence_type": "Observational Research Studies",
                "text_basis": "full_text",
                "appraisal_tier": None,
                "tags": ["health"],
                "selected": False,
            },
        },
        chunks={
            "chunk-a": {
                "content": "alpha policy evidence",
                "sequence": 1,
                "pss_id": doc_a,
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
            "chunk-b": {
                "content": "beta policy evidence",
                "sequence": 1,
                "pss_id": doc_b,
                "segmentation_policy": "manual_v1",
                "text_basis": "full_text",
            },
        },
        units=[
            {
                "unit_id": "unit-a",
                "chunk_id": "chunk-a",
                "pss_id": doc_a,
                "vector": _vector(1.0),
                "text": "alpha policy evidence",
            },
            {
                "unit_id": "unit-b",
                "chunk_id": "chunk-b",
                "pss_id": doc_b,
                "vector": _vector(2.0),
                "text": "beta policy evidence",
            },
        ],
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"policy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    tools = build_section_tools(
        retriever=retriever,
        findings_reader=None,
        lookup_reader=lambda args: {"kind": args["kind"], "result": {}},
        group_doc_ids_by_group_id={"intervention:g01": {doc_a}},
    )

    with pytest.raises(ToolValidationError, match="doc_ids"):
        tools["search_chunks"]({"query": "policy", "doc_ids": ["not-a-uuid"]})
    with pytest.raises(ToolValidationError, match="doc_ids"):
        tools["search_chunks"]({"query": "policy", "doc_ids": [str(uuid.uuid4())]})
    with pytest.raises(ToolValidationError, match="group_ids"):
        tools["search_chunks"]({"query": "policy", "group_ids": ["intervention:g99"]})
    with pytest.raises(ToolValidationError, match="evidence_types"):
        tools["search_chunks"]({"query": "policy", "evidence_types": ["unknown"]})
    with pytest.raises(ToolValidationError, match="tags"):
        tools["search_chunks"]({"query": "policy", "tags": ["missing"]})

    result = tools["search_chunks"]({
        "query": "policy",
        "doc_ids": [doc_a],
        "group_ids": ["intervention:g01"],
        "evidence_types": [EVIDENCE_TYPE],
        "tags": ["housing"],
    })
    assert [chunk["chunk_record_id"] for chunk in result["chunks"]] == ["chunk-a"]


def test_loop_runner_voluntary_emission_before_cap() -> None:
    backend = ScriptedBackend([{"tool_calls": [], "claims": _claims()}])
    result = run_section_loop(backend, seed={}, tools={})
    assert result["turns_used"] == 1
    assert result["claims"] == _claims()
    assert result["turn_cap_hit"] is False


def test_loop_runner_forces_emission_on_cap_and_limits_tool_turns() -> None:
    turns: list[dict[str, Any]] = [
        {"tool_calls": [{"tool": "ok", "arguments": {"i": index}}], "claims": None}
        for index in range(SECTION_TURN_CAP - 1)
    ]
    turns.append({"tool_calls": [], "claims": _claims("forced")})
    result = run_section_loop(
        ScriptedBackend(turns),
        seed={},
        tools={"ok": lambda args: {"ok": args["i"]}},
    )
    assert result["turns_used"] == SECTION_TURN_CAP
    assert result["turn_cap_hit"] is True
    assert len(result["transcript"]) == SECTION_TURN_CAP - 1
    assert result["tool_call_counts"] == {"ok": SECTION_TURN_CAP - 1}


def test_loop_runner_unknown_tool_rejected_and_not_executed() -> None:
    called = False

    def sentinel(_args: dict[str, Any]) -> dict[str, Any]:
        nonlocal called
        called = True
        return {}

    backend = ScriptedBackend([
        {"tool_calls": [{"tool": "missing", "arguments": {}}], "claims": None},
        {"tool_calls": [], "claims": _claims()},
    ])
    result = run_section_loop(backend, seed={}, tools={"known": sentinel})
    assert called is False
    assert result["rejected_tool_calls"] == 1
    assert result["transcript"][0]["result"] == {"error": "unknown tool 'missing'"}


def test_loop_runner_rejects_validation_errors() -> None:
    backend = ScriptedBackend([
        {"tool_calls": [{"tool": "bad", "arguments": {"x": 1}}], "claims": None},
        {"tool_calls": [], "claims": _claims()},
    ])

    def bad(_args: dict[str, Any]) -> dict[str, Any]:
        raise ToolValidationError("bad args")

    result = run_section_loop(backend, seed={}, tools={"bad": bad})
    assert result["rejected_tool_calls"] == 1
    assert result["tool_call_counts"] == {}
    assert result["transcript"][0]["result"] == {"error": "bad args"}


def test_loop_runner_caps_read_calls_per_turn() -> None:
    """Calls past READ_CALLS_PER_TURN_CAP in one turn are refused with an
    error result and counted rejected — the prompt's "up to 6" rule is
    code-enforced, so one degenerate turn cannot blow the retrieval envelope."""
    executed: list[int] = []

    def ok(args: dict[str, Any]) -> dict[str, Any]:
        executed.append(int(args["i"]))
        return {}

    overflow = READ_CALLS_PER_TURN_CAP + 3
    backend = ScriptedBackend([
        {
            "tool_calls": [
                {"tool": "ok", "arguments": {"i": i}} for i in range(overflow)
            ],
            "claims": None,
        },
        {"tool_calls": [], "claims": _claims()},
    ])
    result = run_section_loop(backend, seed={}, tools={"ok": ok})
    assert executed == list(range(READ_CALLS_PER_TURN_CAP))
    assert result["tool_call_counts"] == {"ok": READ_CALLS_PER_TURN_CAP}
    assert result["rejected_tool_calls"] == 3
    refused = result["transcript"][READ_CALLS_PER_TURN_CAP]["result"]
    assert "read batch limit" in refused["error"]


def test_loop_runner_executes_multiple_read_calls_in_one_turn() -> None:
    """A single turn may batch several independent read-tool calls (018 C2
    round 3 cost rider): all execute, in order, within the same turn."""
    backend = ScriptedBackend([
        {
            "tool_calls": [
                {"tool": "ok", "arguments": {"i": 0}},
                {"tool": "ok", "arguments": {"i": 1}},
                {"tool": "ok", "arguments": {"i": 2}},
            ],
            "claims": None,
        },
        {"tool_calls": [], "claims": _claims()},
    ])
    result = run_section_loop(
        backend, seed={}, tools={"ok": lambda args: {"ok": args["i"]}}
    )
    assert result["turns_used"] == 2
    assert len(result["transcript"]) == 3
    assert [entry["result"] for entry in result["transcript"]] == [
        {"ok": 0},
        {"ok": 1},
        {"ok": 2},
    ]
    assert result["tool_call_counts"] == {"ok": 3}
    assert result["rejected_tool_calls"] == 0


def test_loop_runner_one_valid_read_and_one_unknown_tool_in_same_turn() -> None:
    """A batched turn mixing a valid read with an unknown tool executes the
    valid call and rejects only the unknown one — the loop continues."""
    called: list[int] = []

    def known(args: dict[str, Any]) -> dict[str, Any]:
        called.append(args["i"])
        return {"ok": args["i"]}

    backend = ScriptedBackend([
        {
            "tool_calls": [
                {"tool": "known", "arguments": {"i": 0}},
                {"tool": "missing", "arguments": {}},
            ],
            "claims": None,
        },
        {"tool_calls": [], "claims": _claims()},
    ])
    result = run_section_loop(backend, seed={}, tools={"known": known})
    assert called == [0]
    assert result["rejected_tool_calls"] == 1
    assert result["tool_call_counts"] == {"known": 1}
    assert len(result["transcript"]) == 2
    assert result["transcript"][0]["result"] == {"ok": 0}
    assert result["transcript"][1]["result"] == {"error": "unknown tool 'missing'"}
    assert result["turns_used"] == 2


def test_loop_runner_rejects_tool_calls_on_forced_emit_turn() -> None:
    backend = ScriptedBackend([
        {"tool_calls": [{"tool": "ok", "arguments": {}}], "claims": None}
    ])
    with pytest.raises(RuntimeError, match="forced emit"):
        run_section_loop(
            backend,
            seed={},
            tools={"ok": lambda _args: {}},
            turn_cap=1,
        )


def test_loop_runner_rejects_empty_non_emitting_turn() -> None:
    backend = ScriptedBackend([{"tool_calls": [], "claims": None}])
    with pytest.raises(RuntimeError, match="no claims"):
        run_section_loop(backend, seed={}, tools={})


def test_gathered_ids_extracts_chunks_and_findings() -> None:
    transcript: list[ToolExchange] = [
        {
            "tool": "search_chunks",
            "arguments": {"query": "x"},
            "result": {"chunks": [{"chunk_record_id": "c1"}, {"chunk_record_id": "c2"}]},
        },
        {
            "tool": "query_findings",
            "arguments": {},
            "result": {
                "iof_findings": [{"finding_id": "f1"}],
                "icf_findings": [{"finding_id": "f2"}],
            },
        },
        {"tool": "lookup", "arguments": {"kind": "coverage_records"}, "result": {}},
    ]
    assert gathered_ids(transcript) == {
        "chunk_ids": {"c1", "c2"},
        "finding_ids": {"f1", "f2"},
    }


def test_retriever_candidate_pool_cap_prevents_boost_only_surface() -> None:
    docs: dict[str, dict[str, Any]] = {}
    chunks: dict[str, dict[str, Any]] = {}
    units: list[dict[str, Any]] = []
    for index in range(CANDIDATE_POOL_PER_LEG + 1):
        doc_id = f"doc-{index:03d}"
        chunk_id = f"chunk-{index:03d}"
        docs[doc_id] = {
            "title": f"Doc {index}",
            "origin": "acquired" if index == CANDIDATE_POOL_PER_LEG else "uploaded",
            "primary_evidence_type": None,
            "text_basis": "full_text",
            "appraisal_tier": None,
            "tags": [],
            "selected": False,
        }
        chunks[chunk_id] = {
            "content": f"content {index}",
            "sequence": index,
            "pss_id": doc_id,
            "segmentation_policy": "manual_v1",
            "text_basis": "full_text",
        }
        units.append({
            "unit_id": f"unit-{index:03d}",
            "chunk_id": chunk_id,
            "pss_id": doc_id,
            "vector": _vector(1.0),
            "text": f"content {index}",
        })
    retriever = ChunkRetriever(
        _scope(docs, chunks, units),
        embedder=FakeEmbedder({"content": _vector(1.0)}),
        directive=SynthesisDirective(column_boosts={"origin": {"acquired": 10.0}}),
        reranker=PassThroughChunkReranker(),
    )
    ids = [result["chunk_record_id"] for result in retriever.search("content")]
    assert f"chunk-{CANDIDATE_POOL_PER_LEG:03d}" not in ids


def test_loop_runner_malformed_emission_consumes_turn_and_recovers() -> None:
    """A MalformedEmissionError is a turn-consuming error exchange (the model
    reads the bounded error as data and re-emits); on the forced final turn it
    is a structural failure, never an extension."""
    from policy_atlas.synthesis_backend import SectionProseWire
    from policy_atlas.synthesis_tools import (
        MalformedEmissionError,
        run_section_loop,
    )

    class _Backend:
        mode = "stub"

        def section_turn(
            self,
            seed: dict[str, Any],
            transcript: list[ToolExchange],
            *,
            force_emit: bool,
        ) -> UsageResult[Any]:
            del seed
            if not transcript:
                raise MalformedEmissionError("gap.sparsity: Input should be an object")
            assert transcript[0]["tool"] == "emit_section"
            assert "invalid" in transcript[0]["result"]["error"]
            return {"tool_calls": [], "claims": SectionProseWire(prose="", claims=[])}, None

    result = run_section_loop(_Backend(), seed={}, tools={})
    assert result["claims"] is not None
    assert result["turns_used"] == 2
    assert result["rejected_tool_calls"] == 1

    class _AlwaysMalformed:
        mode = "stub"

        def section_turn(
            self,
            seed: dict[str, Any],
            transcript: list[ToolExchange],
            *,
            force_emit: bool,
        ) -> UsageResult[Any]:
            del seed, transcript, force_emit
            raise MalformedEmissionError("still malformed")

    with pytest.raises(RuntimeError, match="forced final turn"):
        run_section_loop(_AlwaysMalformed(), seed={}, tools={})


def test_lookup_excludes_screened_out_doc_from_tag_reads(conn: Connection) -> None:
    """A doc screened OUT of this scope must not surface via the tag-lookup
    kinds — the lookup read boundary follows screen, the same as retrieval."""
    from policy_atlas.schema import TOPIC_THEME, source_screening_result, source_tag

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="screened out doc")
    # Override the relevant screening seeded by seed_select_doc with not_relevant.
    conn.execute(
        source_screening_result.delete().where(
            source_screening_result.c.project_source_snapshot_id == pss_id
        )
    )
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="not_relevant")
    conn.execute(
        source_tag.insert().values(
            source_tag_id=uuid.uuid4(),
            project_id=project_id,
            project_source_snapshot_id=pss_id,
            tag="housing",
            tag_type=TOPIC_THEME,
            asserted_by="characterise",
            created_by_run_id=run_id,
            created_at=now(),
        )
    )

    reader = make_lookup_reader(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        characterisation_run_id=None,
        selection_run_id=None,
        extraction_run_id=None,
        grouping_run_id=None,
    )

    docs = reader({"kind": "docs_by_tag", "tag": "housing"})
    assert docs["result"] == []

    aggregate = reader({"kind": "tag_aggregate", "by": "type"})
    assert TOPIC_THEME not in aggregate["result"]

    with pytest.raises(ToolValidationError, match="doc_id is unknown"):
        reader({"kind": "tags_by_doc", "doc_id": str(pss_id)})


def test_lookup_screening_by_doc_reaches_screening_rows(conn: Connection) -> None:
    """022 rider 16: `screening_by_doc` widens `lookup` to screening rows — a
    doc demoted out of effective relevance (unreachable via the other
    `_by_doc` kinds, per the test above) is still readable here, honestly
    across BOTH stages, not just the effective one."""
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    # seed_select_doc seeds a stage-1 relevant row; a stage-2 demotion makes
    # the doc's EFFECTIVE status not_relevant while its stage-1 history stays
    # a decided relevant row — exactly the "either stage" gap the widening
    # closes (deferred.md: 013 lookup vocabulary widening).
    pss_id = seed_select_doc(conn, project_id, run_id, scope_id, title="demoted doc")
    seed_screening_result(
        conn, project_id, run_id, scope_id, pss_id, status="not_relevant", screen_stage=2
    )

    reader = make_lookup_reader(
        conn,
        project_id=project_id,
        scope_id=scope_id,
        characterisation_run_id=None,
        selection_run_id=None,
        extraction_run_id=None,
        grouping_run_id=None,
    )

    # The scope-filtered `_by_doc` kinds cannot see this doc at all — its
    # effective status is not_relevant.
    with pytest.raises(ToolValidationError, match="doc_id is unknown"):
        reader({"kind": "tags_by_doc", "doc_id": str(pss_id)})

    result = reader({"kind": "screening_by_doc", "doc_id": str(pss_id)})
    assert result["kind"] == "screening_by_doc"
    assert result["result"] == [
        {
            "screen_stage": 1,
            "status": "relevant",
            "screen_basis": "title_abstract",
            "screen_decision_confidence": 0.9,
        },
        {
            "screen_stage": 2,
            "status": "not_relevant",
            "screen_basis": "title_abstract",
            "screen_decision_confidence": 0.95,
        },
    ]

    with pytest.raises(ToolValidationError, match="doc_id is unknown"):
        reader({"kind": "screening_by_doc", "doc_id": str(uuid.uuid4())})


def test_build_retrieval_scope_exposes_abstract_basis_search_chunks(
    conn: Connection,
) -> None:
    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    pss_id = seed_select_doc(
        conn,
        project_id,
        run_id,
        scope_id,
        title="abstract-only doc",
        text_basis="abstract",
    )
    envelope_snapshot_id = conn.execute(
        select(project_source_snapshot.c.source_snapshot_id).where(
            project_source_snapshot.c.project_source_snapshot_id == pss_id
        )
    ).scalar_one()
    content = "abstract-only subsidy evidence is visible in the envelope chunk."
    chunk_id = uuid.uuid4()
    conn.execute(
        chunk_table.insert().values(
            chunk_id=chunk_id,
            source_snapshot_id=envelope_snapshot_id,
            sequence=0,
            content=content,
            content_hash=content_hash(content),
            locator={},
            segmentation_policy="abstract_v1",
            created_at=now(),
        )
    )
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding_profile=EMBEDDING_PROFILE,
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": len(content)},
            vector=_vector(1.0),
            created_at=now(),
        )
    )

    scope = build_retrieval_scope(
        conn, project_id=project_id, scope_id=scope_id, selected_pss_ids=set()
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"subsidy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    tools = build_section_tools(
        retriever=retriever,
        findings_reader=None,
        lookup_reader=lambda args: {"kind": args["kind"], "result": {}},
    )

    result = tools["search_chunks"]({"query": "subsidy"})

    assert scope.chunks[str(chunk_id)]["text_basis"] == "abstract_only"
    assert result["chunks"][0]["chunk_record_id"] == str(chunk_id)
    assert result["chunks"][0]["text_basis"] == "abstract_only"


def _seed_chunk_and_embed(
    conn: Connection, *, snapshot_id: uuid.UUID, content: str
) -> uuid.UUID:
    chunk_id = uuid.uuid4()
    conn.execute(
        chunk_table.insert().values(
            chunk_id=chunk_id,
            source_snapshot_id=snapshot_id,
            sequence=0,
            content=content,
            content_hash=content_hash(content),
            locator={},
            segmentation_policy="manual_v1",
            created_at=now(),
        )
    )
    conn.execute(
        chunk_embedding.insert().values(
            chunk_embedding_id=uuid.uuid4(),
            chunk_id=chunk_id,
            embedding_profile=EMBEDDING_PROFILE,
            unit_policy=UNIT_POLICY,
            unit_index=0,
            unit_locator={"start": 0, "end": len(content)},
            vector=_vector(1.0),
            created_at=now(),
        )
    )
    return chunk_id


def test_search_chunks_result_carries_default_metadata_set_present_and_absent(
    conn: Connection,
) -> None:
    """ADR 0015 §8 / B-B3: chunk search results carry the owner-adopted default
    metadata set (year, evidence_type, appraisal_label, venue, cited_by) when
    each value exists and OMIT each when absent — no is_retracted anywhere."""
    from sqlalchemy import update

    from policy_atlas.schema import source_snapshot

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    # Rich doc: classification + appraisal + year + venue + cited_by.
    rich_pss = seed_select_doc(
        conn, project_id, run_id, scope_id, title="Rich metadata doc", year=2024
    )
    rich_snap = conn.execute(
        select(project_source_snapshot.c.source_snapshot_id).where(
            project_source_snapshot.c.project_source_snapshot_id == rich_pss
        )
    ).scalar_one()
    conn.execute(
        update(source_snapshot)
        .where(source_snapshot.c.source_snapshot_id == rich_snap)
        .values(
            metadata={
                "title": "Rich metadata doc",
                "abstract": "Rich abstract.",
                "year": 2024,
                "publisher_org": "Example Journal",
                "provider_fields": {"cited_by_count": 42},
            }
        )
    )
    rich_chunk = _seed_chunk_and_embed(
        conn, snapshot_id=rich_snap, content="rich subsidy evidence appears here."
    )

    # Bare doc: no classification, no appraisal, no year/venue/cited_by.
    bare_snap, bare_pss = seed_source(
        conn, project_id, meta={"title": "Bare doc"}
    )
    seed_screening_result(conn, project_id, run_id, scope_id, bare_pss, status="relevant")
    bare_chunk = _seed_chunk_and_embed(
        conn, snapshot_id=bare_snap, content="bare subsidy evidence appears here."
    )

    scope = build_retrieval_scope(
        conn, project_id=project_id, scope_id=scope_id, selected_pss_ids=set()
    )
    retriever = ChunkRetriever(
        scope,
        embedder=FakeEmbedder({"subsidy": _vector(1.0)}),
        directive=SynthesisDirective(),
        reranker=PassThroughChunkReranker(),
    )
    tools = build_section_tools(
        retriever=retriever,
        findings_reader=None,
        lookup_reader=lambda args: {"kind": args["kind"], "result": {}},
    )
    results = {
        chunk["chunk_record_id"]: chunk
        for chunk in tools["search_chunks"]({"query": "subsidy"})["chunks"]
    }

    rich = results[str(rich_chunk)]
    assert rich["year"] == 2024
    assert rich["evidence_type"]  # the seeded classification value
    assert rich["appraisal_label"] == "3"
    assert rich["venue"] == "Example Journal"
    assert rich["cited_by"] == 42
    assert "is_retracted" not in rich

    bare = results[str(bare_chunk)]
    for key in ("year", "evidence_type", "appraisal_label", "venue", "cited_by"):
        assert key not in bare
    assert "is_retracted" not in bare


def test_make_findings_reader_record_carries_default_metadata_set(
    conn: Connection,
) -> None:
    """ADR 0015 §8 / B-B3: the findings reader joins classification + appraisal
    (scoped to project + evidence scope, outerjoin) and attaches the default
    metadata set to each finding record, omit-if-absent."""
    from policy_atlas.schema import (
        extraction_result,
        intervention_outcome_finding,
        selection_result,
        source_appraisal_result,
        source_classification_result,
        source_extraction_record,
    )
    from policy_atlas.synthesis_tools import make_findings_reader
    from tests.helpers import EVIDENCE_TYPE

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(
        conn,
        project_id,
        meta={
            "title": "Finding doc",
            "year": 2021,
            "publisher_org": "Study Press",
            "provider_fields": {"cited_by_count": 9},
        },
    )
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")
    conn.execute(
        source_classification_result.insert().values(
            source_classification_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            classified_by_run_id=run_id,
            primary_evidence_type=EVIDENCE_TYPE,
            classified_at=now(),
        )
    )
    conn.execute(
        source_appraisal_result.insert().values(
            source_appraisal_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            appraised_by_run_id=run_id,
            quality_score=4,
            rubric_version="test-rubric",
            appraised_at=now(),
        )
    )
    extraction_record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=extraction_record_id,
            project_id=project_id,
            source_snapshot_id=snap_id,
            project_source_snapshot_id=pss_id,
            extraction_fingerprint="fp-findings-reader",
            status="extracted",
            basis="full_text",
            error=None,
            finding_count=1,
            run_id=run_id,
            created_at=now(),
        )
    )
    conn.execute(
        intervention_outcome_finding.insert().values(
            finding_id=finding_id,
            project_id=project_id,
            extraction_record_id=extraction_record_id,
            intervention="Coaching",
            outcome="Scores",
            population=None,
            comparator=None,
            effect_direction="increase",
            estimate_level="study",
            study_design=None,
            stratum_qualifiers=[],
            statistics={},
            causality_by_design=None,
            is_primary=None,
            is_prevalence_only=None,
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[],
            excluded={},
            flags={},
            created_at=now(),
        )
    )
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=run_id,
            extraction_provenance={
                "profiles": {IOF_PROFILE_ID: {"fingerprint": "t"}}
            },
            docs=[
                {
                    "pss_id": str(pss_id),
                    "basis": "full_text",
                    "profiles": {
                        IOF_PROFILE_ID: {
                            "status": "extracted",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(extraction_record_id),
                        }
                    },
                }
            ],
            counts={
                "selected": 1,
                "profiles": {IOF_PROFILE_ID: {"findings": {"total": 1}}},
            },
            flags={},
            created_at=now(),
        )
    )

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    findings = reader({})["iof_findings"]
    assert len(findings) == 1
    record = findings[0]
    assert record["year"] == 2021
    assert record["evidence_type"] == EVIDENCE_TYPE
    assert record["appraisal_label"] == "4"
    assert record["venue"] == "Study Press"
    assert record["cited_by"] == 9
    assert "is_retracted" not in record


def _seed_reader_finding(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    snap_id: uuid.UUID,
    classification_evidence_type: str | None = None,
    extraction_record_evidence_type: str | None = None,
    effect_basis: str | None = None,
    study_geography: str | None = None,
    field_coverage: dict[str, str] | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed one finding ready for ``make_findings_reader``; returns (record_id, finding_id).

    Kept minimal (no appraisal row) — task 020 C tests only exercise
    effect_basis/study_geography carriage and the evidence-type live-vs-provenance
    split, not the full ADR 0015 default metadata set (already pinned above).
    """
    from policy_atlas.schema import (
        extraction_result,
        intervention_outcome_finding,
        selection_result,
        source_classification_result,
        source_extraction_record,
    )

    if classification_evidence_type is not None:
        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_source_snapshot_id=pss_id,
                project_id=project_id,
                classified_by_run_id=run_id,
                primary_evidence_type=classification_evidence_type,
                classified_at=now(),
            )
        )
    extraction_record_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    conn.execute(
        source_extraction_record.insert().values(
            extraction_record_id=extraction_record_id,
            project_id=project_id,
            source_snapshot_id=snap_id,
            project_source_snapshot_id=pss_id,
            extraction_fingerprint=f"fp-{extraction_record_id}",
            status="extracted",
            basis="full_text",
            primary_evidence_type=extraction_record_evidence_type,
            error=None,
            finding_count=1,
            run_id=run_id,
            created_at=now(),
        )
    )
    conn.execute(
        intervention_outcome_finding.insert().values(
            finding_id=finding_id,
            project_id=project_id,
            extraction_record_id=extraction_record_id,
            intervention="Coaching",
            outcome="Scores",
            population=None,
            comparator=None,
            effect_direction="increase",
            estimate_level="study",
            study_design=None,
            study_geography=study_geography,
            stratum_qualifiers=[],
            statistics={},
            causality_by_design=None,
            effect_basis=effect_basis,
            is_primary=None,
            is_prevalence_only=None,
            field_coverage=field_coverage if field_coverage is not None else {},
            grounding=[],
            created_at=now(),
        )
    )
    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[],
            excluded={},
            flags={},
            created_at=now(),
        )
    )
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=run_id,
            extraction_provenance={
                "profiles": {IOF_PROFILE_ID: {"fingerprint": "t"}}
            },
            docs=[
                {
                    "pss_id": str(pss_id),
                    "basis": "full_text",
                    "profiles": {
                        IOF_PROFILE_ID: {
                            "status": "extracted",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(extraction_record_id),
                        }
                    },
                }
            ],
            counts={
                "selected": 1,
                "profiles": {IOF_PROFILE_ID: {"findings": {"total": 1}}},
            },
            flags={},
            created_at=now(),
        )
    )
    return extraction_record_id, finding_id


def _seed_profiled_reader_findings(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    snap_id: uuid.UUID,
    iof_count: int,
    icf_count: int,
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    from policy_atlas.extraction_records import PROFILE_ID as IOF_PROFILE_ID
    from policy_atlas.implementation_context_records import PROFILE_ID as ICF_PROFILE_ID
    from policy_atlas.schema import (
        extraction_result,
        implementation_context_finding,
        intervention_outcome_finding,
        selection_result,
        source_extraction_record,
    )

    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={},
            selected=[{"pss_id": str(pss_id), "text_basis": "full_text"}],
            excluded={},
            flags={},
            created_at=now(),
        )
    )
    iof_record_id = uuid.uuid4()
    icf_record_id = uuid.uuid4()
    for record_id, fingerprint, count in (
        (iof_record_id, "fp-reader-iof", iof_count),
        (icf_record_id, "fp-reader-icf", icf_count),
    ):
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                project_id=project_id,
                source_snapshot_id=snap_id,
                project_source_snapshot_id=pss_id,
                extraction_fingerprint=fingerprint,
                status="extracted" if count else "no_findings",
                basis="full_text",
                error=None,
                finding_count=count,
                run_id=run_id,
                created_at=now(),
            )
        )
    iof_ids: list[uuid.UUID] = []
    for index in range(iof_count):
        finding_id = uuid.uuid4()
        iof_ids.append(finding_id)
        conn.execute(
            intervention_outcome_finding.insert().values(
                finding_id=finding_id,
                project_id=project_id,
                extraction_record_id=iof_record_id,
                intervention="Coaching",
                outcome=f"Score {index}",
                population=None,
                comparator=None,
                effect_direction="increase",
                estimate_level="study",
                study_design=None,
                study_geography=None,
                stratum_qualifiers=[],
                statistics={},
                causality_by_design=None,
                effect_basis=None,
                is_primary=None,
                is_prevalence_only=None,
                field_coverage={},
                grounding=[],
                created_at=now(),
            )
        )
    icf_ids: list[uuid.UUID] = []
    for index in range(icf_count):
        finding_id = uuid.uuid4()
        icf_ids.append(finding_id)
        conn.execute(
            implementation_context_finding.insert().values(
                finding_id=finding_id,
                project_id=project_id,
                extraction_record_id=icf_record_id,
                context_type="barrier",
                claim=f"Training gap {index} slowed delivery.",
                intervention="Coaching",
                outcome=None,
                population=None,
                setting=None,
                study_geography=None,
                study_design=None,
                claim_level="study",
                claim_basis="studied",
                level="provider",
                resource_requirements=None,
                workforce_requirements="training",
                field_coverage={},
                grounding=[],
                created_at=now(),
            )
        )

    def _profile_counts(total: int) -> dict[str, Any]:
        return {
            "selected": 1,
            "extracted": 1 if total else 0,
            "no_findings": 0 if total else 1,
            "failed": 0,
            "fresh": 1,
            "reused": 0,
            "findings": {
                "total": total,
                "quote_unverified": 0,
                "dedup_collapsed": 0,
                "invalid_dropped": 0,
            },
        }

    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=run_id,
            selection_run_id=run_id,
            extraction_provenance={
                "profiles": {
                    IOF_PROFILE_ID: {"fingerprint": "fp-reader-iof", "profile": IOF_PROFILE_ID},
                    ICF_PROFILE_ID: {"fingerprint": "fp-reader-icf", "profile": ICF_PROFILE_ID},
                },
                "pass_count": 1,
            },
            docs=[
                {
                    "pss_id": str(pss_id),
                    "basis": "full_text",
                    "profiles": {
                        IOF_PROFILE_ID: {
                            "status": "extracted" if iof_count else "no_findings",
                            "basis": "full_text",
                            "finding_count": iof_count,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(iof_record_id),
                            "order": 0,
                        },
                        ICF_PROFILE_ID: {
                            "status": "extracted" if icf_count else "no_findings",
                            "basis": "full_text",
                            "finding_count": icf_count,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(icf_record_id),
                            "order": 0,
                        },
                    },
                }
            ],
            counts={
                "selected": 1,
                "basis": {"full_text": 1, "abstract_only": 0},
                "profiles": {
                    IOF_PROFILE_ID: _profile_counts(iof_count),
                    ICF_PROFILE_ID: _profile_counts(icf_count),
                },
            },
            flags={},
            created_at=now(),
        )
    )
    return iof_ids, icf_ids


def test_make_findings_reader_carries_effect_basis_and_study_geography(
    conn: Connection,
) -> None:
    """Task 020 C1: query_findings' record carries the two new finding-grain
    fields (always-present-nullable, exactly like ``study_design``)."""
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Geo doc"})
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")

    _record_id, finding_id = _seed_reader_finding(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        effect_basis="observed",
        study_geography="England",
    )

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    findings = reader({})["iof_findings"]
    record = next(f for f in findings if f["finding_id"] == str(finding_id))
    assert record["effect_basis"] == "observed"
    assert record["study_geography"] == "England"


def test_make_findings_reader_effect_basis_study_geography_null_for_v1_rows(
    conn: Connection,
) -> None:
    """Old-row tolerance: a v1 row has NULL effect_basis/study_geography and a
    field_coverage dict without the new keys — the read path passes both
    through as ``None``, never a ``KeyError``."""
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "V1 doc"})
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")

    _record_id, finding_id = _seed_reader_finding(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        effect_basis=None,
        study_geography=None,
        field_coverage={"study_design": "not_extracted"},
    )

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    findings = reader({})["iof_findings"]
    record = next(f for f in findings if f["finding_id"] == str(finding_id))
    assert record["effect_basis"] is None
    assert record["study_geography"] is None
    assert "effect_basis" not in record["field_coverage"]
    assert "study_geography" not in record["field_coverage"]


def test_make_findings_reader_evidence_type_reads_live_classification_not_provenance(
    conn: Connection,
) -> None:
    """Adversarial finding 5: the writer envelope's ``evidence_type`` always
    reads the live ``source_classification_result``, never the
    ``source_extraction_record.primary_evidence_type`` extraction-call
    provenance column — the two may legitimately diverge (schema comment)."""
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Divergent doc"})
    seed_screening_result(conn, project_id, run_id, scope_id, pss_id, status="relevant")

    _record_id, finding_id = _seed_reader_finding(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        classification_evidence_type="RCTs and Quasi-Experimental Studies",
        extraction_record_evidence_type="Observational Research Studies",
    )

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    findings = reader({})["iof_findings"]
    record = next(f for f in findings if f["finding_id"] == str(finding_id))
    assert record["evidence_type"] == "RCTs and Quasi-Experimental Studies"


def test_make_findings_reader_returns_kind_segregated_sections(conn: Connection) -> None:
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id, meta={"title": "Both kinds"})
    iof_ids, icf_ids = _seed_profiled_reader_findings(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        iof_count=1,
        icf_count=1,
    )

    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )
    result = reader({})

    assert set(result) == {"iof_findings", "iof_truncated", "icf_findings", "icf_truncated"}
    assert result["iof_findings"][0]["finding_id"] == str(iof_ids[0])
    assert result["iof_findings"][0]["kind"] == "iof"
    assert result["icf_findings"][0]["finding_id"] == str(icf_ids[0])
    assert result["icf_findings"][0]["kind"] == "icf"
    assert "findings" not in result


def test_make_findings_reader_kind_filter_mismatch_fails_closed(conn: Connection) -> None:
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id)
    _seed_profiled_reader_findings(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        iof_count=1,
        icf_count=1,
    )
    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )

    with pytest.raises(ToolValidationError, match="effect_direction requires iof"):
        reader({"kinds": ["icf"], "effect_direction": "increase"})
    with pytest.raises(ToolValidationError, match="context_type requires icf"):
        reader({"kinds": ["iof"], "context_type": "barrier"})
    # Omitted kinds defaults to both — a kind-specific filter must still fail
    # closed, never return the other kind unfiltered alongside.
    with pytest.raises(ToolValidationError, match="effect_direction requires iof"):
        reader({"effect_direction": "increase"})
    with pytest.raises(ToolValidationError, match="context_type requires icf"):
        reader({"context_type": "barrier"})
    with pytest.raises(ToolValidationError, match="context_type requires icf"):
        reader({"kinds": ["iof", "icf"], "context_type": "barrier"})


def test_make_findings_reader_group_filter_requires_resolved_qualified_ids(
    conn: Connection,
) -> None:
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id)
    iof_ids, _icf_ids = _seed_profiled_reader_findings(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        iof_count=2,
        icf_count=0,
    )
    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=[
            {
                "group_id": "intervention:g01",
                "member_finding_ids": [str(iof_ids[0])],
            }
        ],
    )

    result = reader({"kinds": ["iof"], "group_id": "intervention:g01"})
    assert [finding["finding_id"] for finding in result["iof_findings"]] == [
        str(iof_ids[0])
    ]
    with pytest.raises(ToolValidationError, match="<facet>:gNN"):
        reader({"kinds": ["iof"], "group_id": "g01"})
    with pytest.raises(ToolValidationError, match="unknown group_id"):
        reader({"kinds": ["iof"], "group_id": "intervention:g99"})
    with pytest.raises(ToolValidationError, match="<facet>:gNN"):
        make_findings_reader(
            conn,
            project_id=project_id,
            extraction_run_id=run_id,
            evidence_scope_id=scope_id,
            grouping_groups=[{"label": "Legacy", "member_finding_ids": [str(iof_ids[0])]}],
        )


def test_make_findings_reader_iof_only_run_reports_icf_not_extracted(
    conn: Connection,
) -> None:
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id)
    _record_id, finding_id = _seed_reader_finding(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
    )
    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )

    result = reader({})
    assert [finding["finding_id"] for finding in result["iof_findings"]] == [
        str(finding_id)
    ]
    assert result["icf_findings"] == "not extracted in this run"
    assert "icf_truncated" not in result
    assert set(reader({"kinds": ["iof"]})) == {"iof_findings", "iof_truncated"}


def test_make_findings_reader_caps_per_kind(conn: Connection) -> None:
    from policy_atlas.synthesis_tools import make_findings_reader

    project_id, run_id = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    snap_id, pss_id = seed_source(conn, project_id)
    _seed_profiled_reader_findings(
        conn,
        project_id=project_id,
        run_id=run_id,
        scope_id=scope_id,
        pss_id=pss_id,
        snap_id=snap_id,
        iof_count=101,
        icf_count=3,
    )
    reader = make_findings_reader(
        conn,
        project_id=project_id,
        extraction_run_id=run_id,
        evidence_scope_id=scope_id,
        grouping_groups=None,
    )

    result = reader({})
    assert len(result["iof_findings"]) == 100
    assert result["iof_truncated"] is True
    assert len(result["icf_findings"]) == 3
    assert result["icf_truncated"] is False
