"""The synthetic-corpus retrieval test (task 057 Phase 3, contract N8, D7, plan P7).

A small corpus with hand-made stub vectors and designed word overlaps
(``data/retrieval_synthetic/``) runs through a fixed list of searches. Each search
is pinned to a frozen expected result (``expected.json``): the eight returned
chunks in order with their fused scores, windows and metadata, and the whole
fused candidate list the reranker saw, in order with scores.

The expected file was generated once from the in-memory Python retriever that
task 057 replaced with one SQL statement; the SQL retriever must reproduce it
exactly (both were run side by side on it before the Python one was deleted).
To regenerate (only when the retrieval rules change on purpose), run this test
with ``RETRIEVAL_SYNTHETIC_WRITE_EXPECTED=1``, which writes the current
retriever's output, and review the diff.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Any, Literal

import pytest
from sqlalchemy.engine import Connection

from policy_atlas.core.tokens import word_tokens
from policy_atlas.evidence_search.synthesis import synthesis_tools
from policy_atlas.evidence_search.synthesis.synthesis_tools import (
    ChunkRetriever,
    ChunkSearchResult,
    SynthesisDirective,
    _ChunkScopeFilters,
    borrowed_connection,
    build_retrieval_scope,
    parse_synthesis_directive,
)
from tests.evidence_search.synthesis.retrieval_corpus import (
    CORPUS_DIR,
    LoadedCorpus,
    dense_vector,
    load_corpus,
    read_json,
)

EXPECTED_PATH = CORPUS_DIR / "expected.json"


class _StubEmbedder:
    mode = "stub"

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed_texts(
        self, texts: list[str], *, kind: Literal["document", "query"] = "document"
    ) -> list[list[float]]:
        del kind
        return [self.vectors[text] for text in texts]


class _RecordingReranker:
    """Pass-through reranker that keeps the full candidate list it was given."""

    mode = "none"

    def __init__(self) -> None:
        self.candidates: list[ChunkSearchResult] = []

    def rerank(
        self, *, query: str, candidates: list[ChunkSearchResult]
    ) -> list[ChunkSearchResult]:
        del query
        self.candidates = list(candidates)
        return candidates


def _filters(case: dict[str, Any], loaded: LoadedCorpus) -> _ChunkScopeFilters | None:
    raw = case.get("filters")
    if not raw:
        return None

    def doc_set(key: str) -> frozenset[str] | None:
        if key not in raw:
            return None
        return frozenset(str(loaded.tss_ids[name]) for name in raw[key])

    def value_set(key: str) -> frozenset[str] | None:
        return frozenset(raw[key]) if key in raw else None

    return _ChunkScopeFilters(
        doc_ids=doc_set("doc_ids"),
        group_doc_ids=doc_set("group_doc_ids"),
        evidence_types=value_set("evidence_types"),
        tags=value_set("tags"),
    )


def _record(result: ChunkSearchResult, names: dict[str, str]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "chunk": names[result["chunk_record_id"]],
        "doc": names[result["tss_id"]],
        "fused_score": result["fused_score"],
        "content_length": len(result["content"]),
        "content_sha256": hashlib.sha256(result["content"].encode()).hexdigest()[:16],
    }
    for key in (
        "document_title",
        "sequence",
        "text_basis",
        "origin",
        "appraised",
        "year",
        "evidence_type",
        "appraisal_label",
        "window_start",
        "window_end",
    ):
        if key in result:
            record[key] = result[key]
    return record


def _run_case(
    conn: Connection,
    loaded: LoadedCorpus,
    case: dict[str, Any],
    *,
    corpus: dict[str, Any],
    queries: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    query = queries[case["query"]]
    scopes = [loaded.scope_ids[name] for name in case["scopes"]]
    selection = case.get("selection", corpus["default_selection"])
    boosts = case.get("boosts")
    directive = (
        parse_synthesis_directive(
            {"synthesis": {"retrieval_boosts": boosts}}, grouping_group_ids=None
        )
        if boosts
        else SynthesisDirective()
    )
    reranker = _RecordingReranker()
    with monkeypatch.context() as patch:
        if "pool" in case:
            patch.setattr(synthesis_tools, "CANDIDATE_POOL_PER_LEG", case["pool"])
        scope = build_retrieval_scope(
            conn,
            task_id=loaded.task_id,
            scope_id=scopes[0],
            selected_tss_ids={loaded.tss_ids[name] for name in selection},
            extra_scope_ids=scopes[1:],
            connect=borrowed_connection(conn),
        )
        retriever = ChunkRetriever(
            scope,
            embedder=_StubEmbedder({query["text"]: dense_vector(query["vector"])}),
            directive=directive,
            reranker=reranker,
            selection_reference_resolved=bool(case.get("selection_reference_resolved")),
        )
        results = retriever.search(query["text"], filters=_filters(case, loaded))
    return {
        "top8": [_record(result, loaded.names) for result in results],
        "candidates": [
            [loaded.names[candidate["chunk_record_id"]], candidate["fused_score"]]
            for candidate in reranker.candidates
        ],
    }


def test_synthetic_corpus_matches_frozen_expected_output(
    conn: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = read_json("corpus.json")
    spec = read_json("cases.json")
    loaded = load_corpus(conn, corpus)
    observed = {
        case["id"]: _run_case(
            conn,
            loaded,
            case,
            corpus=corpus,
            queries=spec["queries"],
            monkeypatch=monkeypatch,
        )
        for case in spec["cases"]
    }
    if os.environ.get("RETRIEVAL_SYNTHETIC_WRITE_EXPECTED") == "1":
        EXPECTED_PATH.write_text(json.dumps(observed, indent=1, sort_keys=True) + "\n")
    expected = json.loads(EXPECTED_PATH.read_text())
    assert sorted(observed) == sorted(expected)
    mismatched = [case_id for case_id in expected if observed[case_id] != expected[case_id]]
    assert not mismatched, {case_id: observed[case_id] for case_id in mismatched}


def test_synthetic_corpus_cosine_orderings_are_unambiguous() -> None:
    """Fixture check: two units with different vectors never sit within 1e-6 of
    each other's cosine for any query, so float32 storage cannot swap them. Only
    positive cosines matter (the vector leg keeps scores above zero), and none
    sits within 1e-6 of zero."""
    corpus = read_json("corpus.json")
    spec = read_json("cases.json")
    unit_vectors: list[tuple[str, tuple[float, ...]]] = []
    for chunk_spec in corpus["chunks"]:
        units = chunk_spec.get("units") or [{"vector": chunk_spec["vector"]}]
        for index, unit in enumerate(units):
            unit_vectors.append(
                (f"{chunk_spec['name']}u{index}", tuple(dense_vector(unit["vector"])))
            )
    for query_name, query in spec["queries"].items():
        query_vector = dense_vector(query["vector"])
        query_norm = math.sqrt(math.sumprod(query_vector, query_vector))
        if query_norm == 0.0:
            continue
        scored = []
        for name, vector in unit_vectors:
            norm = math.sqrt(math.sumprod(vector, vector))
            if norm == 0.0:
                continue
            cosine = math.sumprod(query_vector, vector) / (query_norm * norm)
            if cosine <= 0.0:
                continue
            assert cosine > 1e-6, (query_name, name)
            scored.append((cosine, name, vector))
        scored.sort()
        for (low, low_name, low_vec), (high, high_name, high_vec) in zip(
            scored, scored[1:], strict=False
        ):
            if low_vec != high_vec:
                assert high - low > 1e-6, (query_name, low_name, high_name)


def test_synthetic_corpus_cases_cover_the_designed_situations() -> None:
    """Guard the corpus design against silent drift: the expected output still
    shows a chunk tie broken by id, a within-chunk unit tie won by the vector
    leg, a window on a chunk whose best unit is not its first, both scopes'
    precedence, and the empty legs."""
    expected = json.loads(EXPECTED_PATH.read_text())
    tie = expected["chunk_tie"]["top8"]
    assert [row["chunk"] for row in tie[:2]] == ["f1", "f2"]
    assert tie[0]["fused_score"] == tie[1]["fused_score"]
    unit_tie = expected["unit_tie_window"]["top8"]
    assert unit_tie[0]["chunk"] == "h1"
    assert unit_tie[0]["window_start"] == 1900 - synthesis_tools.OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS
    housing = {row["chunk"]: row for row in expected["default_housing"]["top8"]}
    margin = synthesis_tools.OVERSIZED_CHUNK_WINDOW_MARGIN_CHARS
    assert housing["a7"]["window_start"] == 1800 - margin
    for case_id in expected:
        chunks = {row[0] for row in expected[case_id]["candidates"]}
        # Screened-out, demoted and envelope-decoy chunks never surface.
        assert not chunks & {"g1", "i1", "bx1", "bx2"}, case_id
    s1 = {row["doc"]: row for row in expected["multi_scope_primary_s1"]["top8"]}
    s2 = {row["doc"]: row for row in expected["multi_scope_primary_s2"]["top8"]}
    assert s1["dE"]["evidence_type"] == "Policy Syntheses & Guidance Documents"
    assert s2["dE"]["evidence_type"] == "Modelling & Simulation"
    assert expected["no_word_overlap"]["top8"]
    assert expected["zero_query_vector"]["top8"]
    assert expected["no_query_words"]["top8"]
    assert len(expected["pool_cut"]["candidates"]) <= 6
    assert word_tokens("?! ...") == set()
