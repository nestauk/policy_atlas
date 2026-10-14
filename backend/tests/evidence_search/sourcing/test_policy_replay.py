"""Replay recorded Overton result lists through the pure policy pool rules."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from policy_atlas.evidence_search.sourcing.pool import (
    SEED_RANK_SENTINEL,
    count_policy_cites,
    dedupe_policy,
    interleave,
    landmark_targets,
    rank_policy,
)

FIXTURES = sorted((Path(__file__).parents[2] / "data" / "policy_replay").glob("*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda path: path.stem)
def test_policy_pool_replays_recorded_overton_results(path: Path) -> None:
    """The policy pool reproduces each recorded manual-question fixture."""
    fixture = json.loads(path.read_text())
    expected = fixture["expected"]
    interleaved = interleave(
        fixture["result_lists"], lambda record: record.get("policy_document_id")
    )

    assert [record["policy_document_id"] for record in interleaved] == expected["interleaved"]
    deduplicated = dedupe_policy(interleaved)
    deduplicated_ids = [record["policy_document_id"] for record in deduplicated]
    assert deduplicated_ids == expected["deduplicated"]
    assert all(duplicate not in deduplicated_ids for duplicate in fixture["synthetic_ids"][:2])
    assert fixture["synthetic_ids"][2] in deduplicated_ids

    counts = count_policy_cites(deduplicated)
    assert landmark_targets(counts, set(expected["result_ids"]), 15) == expected["landmarks"]
    ranked = rank_policy(
        [(record, "paraphrase") for record in deduplicated], fixture["landmark_records"], counts
    )
    ranked_ids = [candidate.policy_document_id for candidate in ranked]

    assert ranked_ids == expected["specific"]
    assert [
        candidate.policy_document_id
        for candidate in ranked
        if candidate.record["source"]["country"] == "UK"
    ] == expected["uk_only"]
    assert ranked_ids[:50] == expected["cut_50"]
    assert all(
        candidate.origin == "landmark" and candidate.position == SEED_RANK_SENTINEL
        for candidate in ranked
        if candidate.policy_document_id
        in {record["policy_document_id"] for record in fixture["landmark_records"]}
    )
