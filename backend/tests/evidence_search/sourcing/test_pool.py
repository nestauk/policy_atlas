"""Unit tests for the pure paper and policy pool ranking helpers."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from policy_atlas.evidence_search.sourcing.pool import (
    backward_targets,
    count_references,
    country_predicate,
    forward_seeds,
    interleave,
    normalised_title,
    paper_candidates,
    policy_key,
    rank_papers,
    score_forward,
)

DATA = Path(__file__).parents[2] / "data"


def test_paper_pool_replays_recorded_experiment_fixture() -> None:
    """The production rules reproduce the fixture exported from the experiment."""
    fixture = json.loads((DATA / "pool_fixture.json").read_text())
    seeds = [(record, "generated") for record in fixture["seeds"]]
    counts = count_references(fixture["seeds"])
    seed_ids = {record["id"].rsplit("/", 1)[-1] for record in fixture["seeds"]}

    assert dict(counts) == fixture["counts"]
    assert [key for key, _ in counts.most_common()] == list(fixture["counts"])
    assert backward_targets(counts, seed_ids, 10**6) == fixture["expected_backward_targets"]

    forward = score_forward(
        fixture["forward"],
        seed_ids,
        counts,
        excluded_ids={record["id"].rsplit("/", 1)[-1] for record in fixture["backward"]},
    )
    ranked = rank_papers(paper_candidates(seeds, fixture["backward"], forward, counts))
    expected_rows = {row["openalex_id"]: row for row in fixture["expected_rows"]}

    assert [candidate.openalex_id for candidate in ranked] == fixture["expected_order"]
    for candidate in ranked:
        expected = expected_rows[candidate.openalex_id]
        assert candidate.inset == expected["inset"]
        assert candidate.coupling == expected["coupling"]
        assert candidate.wcoupling == expected["wcoupling"]
        assert candidate.specificity == expected["specificity"]


def test_interleave_round_robins_deduplicates_and_skips_missing_keys() -> None:
    """Each query gets equal rank turns while the first usable copy wins."""
    lists: list[list[dict[str, Any]]] = [
        [{"id": "a"}, {"id": "shared"}, {"id": "c"}],
        [{"id": "b"}, {"id": "shared"}],
        [{"id": None}, {"id": "d"}],
    ]

    assert [record["id"] for record in interleave(lists, lambda record: record.get("id"))] == [
        "a",
        "b",
        "shared",
        "d",
        "c",
    ]


def test_count_references_counts_seed_ids_and_keeps_tie_order() -> None:
    """A seed can itself be cited, and equal counts retain reference appearance order."""
    counts = count_references(
        [
            {
                "referenced_works": [
                    "https://openalex.org/W2",
                    "W3",
                    "https://openalex.org/W2",
                ]
            },
            {"referenced_works": ["W1", "W3"]},
        ]
    )

    assert counts == Counter({"W2": 1, "W3": 2, "W1": 1})
    assert [key for key, _ in counts.most_common()] == ["W3", "W2", "W1"]


def test_backward_targets_excludes_seeds_and_is_stable() -> None:
    """Already-selected seeds cannot consume the backward expansion budget."""
    counts = Counter({"seed": 5, "first": 3, "second": 3, "third": 2})

    assert backward_targets(counts, {"seed"}, 2) == ["first", "second"]


def test_forward_seeds_honours_global_citation_ceiling() -> None:
    """A highly cited global paper is not chased even when its in-set count is highest."""
    seeds = [
        {"id": "W1", "cited_by_count": 301},
        {"id": "W2", "cited_by_count": 20},
        {"id": "W3", "cited_by_count": 30},
    ]

    assert forward_seeds(seeds, Counter({"W1": 9, "W2": 4, "W3": 4}), top=1, max_cites=300) == [
        "W2"
    ]


def test_score_forward_excludes_known_work_and_ranks_graph_signals() -> None:
    """Forward candidates are unique and ordered by weighted then plain coupling."""
    scored = score_forward(
        [
            {"id": "Wskip-seed", "referenced_works": ["W1"]},
            {"id": "Wskip-backward", "referenced_works": ["W1"]},
            {"id": "Wa", "referenced_works": ["W1"], "cited_by_count": 2},
            {"id": "Wb", "referenced_works": ["W1", "W2"], "cited_by_count": 2},
            {"id": "Wc", "referenced_works": ["W1"], "cited_by_count": 2},
            {"id": "Wb", "referenced_works": ["W2"]},
        ],
        {"W1", "W2", "Wskip-seed"},
        Counter({"W1": 3, "W2": 1}),
        excluded_ids={"Wskip-backward"},
    )

    assert [candidate.openalex_id for candidate in scored] == ["Wb", "Wa", "Wc"]
    assert scored[0].wcoupling == 3.0
    assert scored[0].coupling == 2


def test_titles_normalise_and_titleless_records_keep_their_own_identity() -> None:
    """Title matching ignores cosmetic changes but never merges titleless documents."""
    assert normalised_title(None) == ""
    assert normalised_title("") == ""
    assert normalised_title("   ") == ""
    assert normalised_title("A, B") == "a b"
    assert (
        policy_key({"policy_document_id": "one", "title": "Old", "translated_title": "New Title"})
        == "new title"
    )
    assert policy_key({"policy_document_id": "two", "title": "..."}) == "two"
    assert policy_key({"policy_document_id": "three", "title": "A,  policy"}) == policy_key(
        {"policy_document_id": "four", "title": " a POLICY "}
    )


def test_country_predicate_is_case_insensitive_and_fails_closed() -> None:
    """Country filtering keeps known matches and drops unknown affiliations."""
    assert country_predicate({"authorships": [{"countries": ["gb"]}]}, {"GB"})
    assert not country_predicate({"authorships": [{"countries": ["US"]}]}, {"gb"})
    assert not country_predicate({}, {"GB"})
