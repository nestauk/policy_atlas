"""Pure tests for the task-013 synthesis tool and loop layer."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas.embeddings import EMBEDDING_DIMENSIONS, EMBEDDING_PROFILE, UNIT_POLICY
from policy_atlas.grounding import content_hash
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import chunk_embedding, project_source_snapshot
from policy_atlas.synthesis_backend import SectionProseWire
from policy_atlas.synthesis_tools import (
    BOOST_CLAMP_MAX,
    BOOST_CLAMP_MIN,
    CANDIDATE_POOL_PER_LEG,
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
    build_retrieval_scope,
    build_section_tools,
    gathered_ids,
    make_lookup_reader,
    parse_synthesis_directive,
    run_section_loop,
)
from policy_atlas.usage import UsageResult
from tests.helpers import (
    now,
    seed_project_and_run,
    seed_scope,
    seed_screening_result,
    seed_select_doc,
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
                    "sections": [{"title": "Housing", "focus": "x", "group_ids": ["g1"]}]
                }
            },
            grouping_group_ids=None,
        )
    with pytest.raises(SynthesisDirectiveError, match="unknown"):
        parse_synthesis_directive(
            {
                "synthesis": {
                    "sections": [{"title": "Housing", "focus": "x", "group_ids": ["g2"]}]
                }
            },
            grouping_group_ids={"g1"},
        )


def test_parse_synthesis_directive_valid_sections_and_boosts_clamp() -> None:
    directive = parse_synthesis_directive(
        {
            "synthesis": {
                "sections": [
                    {
                        "title": "Rough sleeping",
                        "focus": "interventions",
                        "group_ids": ["g1"],
                    }
                ],
                "retrieval_boosts": {
                    "columns": {"origin": {"uploaded": 100}},
                    "tags": {"housing": 0.001},
                    "appraisal_tier": {"5": 2},
                },
            }
        },
        grouping_group_ids={"g1"},
    )
    assert directive.sections == [
        {"title": "Rough sleeping", "focus": "interventions", "group_ids": ["g1"]}
    ]
    assert directive.column_boosts == {"origin": {"uploaded": BOOST_CLAMP_MAX}}
    assert directive.tag_boosts == {"housing": BOOST_CLAMP_MIN}
    assert directive.appraisal_tier_boosts == {"5": 2.0}


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


def test_search_chunks_char_budget_tail_drop_and_zero_budget() -> None:
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
    assert second == {"chunks": [], "truncated": True}


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


def test_loop_runner_rejects_two_tool_calls_and_validation_errors() -> None:
    backend = ScriptedBackend([
        {
            "tool_calls": [
                {"tool": "ok", "arguments": {}},
                {"tool": "ok", "arguments": {}},
            ],
            "claims": None,
        },
        {"tool_calls": [{"tool": "bad", "arguments": {"x": 1}}], "claims": None},
        {"tool_calls": [], "claims": _claims()},
    ])

    def bad(_args: dict[str, Any]) -> dict[str, Any]:
        raise ToolValidationError("bad args")

    result = run_section_loop(backend, seed={}, tools={"bad": bad})
    assert result["rejected_tool_calls"] == 2
    assert result["tool_call_counts"] == {}
    assert result["transcript"][0]["result"] == {"error": "one tool call per turn"}
    assert result["transcript"][1]["result"] == {"error": "bad args"}


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
            "result": {"findings": [{"finding_id": "f1"}, {"finding_id": "f2"}]},
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
