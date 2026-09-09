"""Tests for the ranking backend seam and ranked-output validation."""

from __future__ import annotations

from typing import cast

import pytest

from policy_atlas.evidence_search.corpus.ranking import (
    SCORE_MAX,
    SCORE_MIN,
    OpenAIRankingBackend,
    RankedDoc,
    StubRankingBackend,
    validate_ranked,
)
from policy_atlas.evidence_search.corpus.theme_grouping import GroupingDoc


def _batch(size: int) -> list[GroupingDoc]:
    return [
        {
            "id": f"doc-{index}",
            "title": f"Document {index}",
            "abstract": f"Abstract for document {index}.",
        }
        for index in range(size)
    ]


def test_stub_ranking_is_deterministic_and_exhaustive() -> None:
    batch = _batch(30)
    backend = StubRankingBackend()

    first, first_usage = backend.rank(batch, intent="Assess policy evidence.")
    second, second_usage = backend.rank(batch, intent="Assess policy evidence.")

    assert first_usage is None
    assert second_usage is None
    assert first == second
    assert [ranked["doc_id"] for ranked in first] == [doc["id"] for doc in batch]
    assert len({ranked["doc_id"] for ranked in first}) == len(batch)
    assert all(SCORE_MIN <= ranked["score"] <= SCORE_MAX for ranked in first)
    assert len({ranked["score"] for ranked in first}) >= 3


def test_validate_ranked_drops_bad_entries_and_normalizes_valid_entries() -> None:
    batch_ids = {
        "conflict",
        "identical",
        "bool-score",
        "too-high",
        "too-low",
        "non-int",
        "empty-reason",
        "long-reason",
        "control-reason",
        "valid",
        "missing",
    }
    ranked = cast(
        "list[RankedDoc]",
        [
            {"doc_id": "invented", "score": 5, "reason": "Not in the batch."},
            {"doc_id": "conflict", "score": 4, "reason": "First reason."},
            {"doc_id": "conflict", "score": 4, "reason": "Second reason."},
            {"doc_id": "identical", "score": 7, "reason": "  Same reason.  "},
            {"doc_id": "identical", "score": 7, "reason": "Same reason."},
            {"doc_id": "bool-score", "score": True, "reason": "Bool is not int."},
            {"doc_id": "too-high", "score": 11, "reason": "Too high."},
            {"doc_id": "too-low", "score": -1, "reason": "Too low."},
            {"doc_id": "non-int", "score": "8", "reason": "String score."},
            {"doc_id": "empty-reason", "score": 5, "reason": "   "},
            {"doc_id": "long-reason", "score": 5, "reason": "x" * 241},
            {"doc_id": "control-reason", "score": 5, "reason": "Bad\u0007reason."},
            {"doc_id": "valid", "score": 8, "reason": "  Direct evidence fit.  "},
        ],
    )

    assert validate_ranked(batch_ids, ranked) == {
        "identical": {
            "doc_id": "identical",
            "score": 7,
            "reason": "Same reason.",
        },
        "valid": {
            "doc_id": "valid",
            "score": 8,
            "reason": "Direct evidence fit.",
        },
    }


def test_openai_ranking_backend_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIRankingBackend()


def test_openai_ranking_backend_no_langfuse_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)

    backend = OpenAIRankingBackend(api_key="sk-test", langfuse_client=None)

    assert backend.mode == "live"
