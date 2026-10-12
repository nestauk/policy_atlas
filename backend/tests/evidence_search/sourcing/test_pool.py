"""Unit tests for the pure paper and policy pool ranking helpers."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from policy_atlas.evidence_search.sourcing.pool import (
    PaperCandidate,
    backward_targets,
    count_references,
    country_predicate,
    dedupe_papers,
    forward_seeds,
    interleave,
    normalised_title,
    paper_candidates,
    policy_key,
    rank_mix,
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


def _cand(work_id: str, **fields: Any) -> PaperCandidate:
    record = {
        "id": f"https://openalex.org/{work_id}",
        "display_name": fields.pop("title", work_id),
        "publication_year": fields.pop("year", 2010),
        "authorships": [
            {"author": {"display_name": name}} for name in fields.pop("authors", ["A Author"])
        ],
    }
    cited = fields.pop("cited", 0)
    inset = fields.pop("inset", 0)
    return PaperCandidate(
        record=record,
        origin=fields.pop("origin", "generated"),
        seed_rank=fields.pop("seed_rank", 0),
        inset=inset,
        coupling=fields.pop("coupling", 0),
        wcoupling=fields.pop("wcoupling", 0.0),
        forward_rank=0,
        cited_by_count=cited,
        specificity=fields.pop("specificity", float(inset)),
    )


def test_dedupe_papers_needs_same_title_and_authors_and_keeps_the_cited_copy() -> None:
    """A preprint and its journal copy collapse to the cited copy; other authors stay."""
    preprint = _cand("W1", title="Criticality in networks", cited=0, seed_rank=0)
    journal = _cand("W2", title="Criticality in Networks.", cited=36, seed_rank=5)
    other_authors = _cand("W3", title="Criticality in networks", authors=["B Other"], cited=2)
    untitled_a = _cand("W4", title="", cited=0)
    untitled_b = _cand("W5", title="", cited=0)

    kept = dedupe_papers([preprint, journal, other_authors, untitled_a, untitled_b])

    assert [c.openalex_id for c in kept] == ["W2", "W3", "W4", "W5"]


def test_rank_mix_alternates_relevant_seminal_and_novel_then_the_rest() -> None:
    """Round-robin over the three strata, each paper once, specificity order for the rest."""
    hit_twice = _cand("W1", year=2010, cited=5, inset=1, specificity=1.0)
    hit_once = _cand("W2", year=2024, cited=1, inset=0, specificity=0.5)
    seminal = _cand(
        "W3", year=2003, cited=900, inset=40, specificity=20.0, origin="snowball_backward"
    )
    novel_graph = _cand(
        "W4", year=2025, cited=0, inset=0, specificity=3.0, origin="snowball_forward"
    )
    old_graph = _cand(
        "W5", year=1999, cited=10, inset=2, specificity=2.0, origin="snowball_backward"
    )
    lists = [[hit_twice.record, hit_once.record], [hit_twice.record]]

    order = [
        c.openalex_id
        for c in rank_mix(
            [old_graph, novel_graph, seminal, hit_once, hit_twice], lists, novel_from_year=2021
        )
    ]

    # relevant W1, seminal W3, novel W2 (query-returned beats graph-only), relevant W2 taken,
    # so next relevant is exhausted; seminal next is W5 (inset 2), novel W4, then the rest.
    assert order == ["W1", "W3", "W2", "W5", "W4"]


def test_rank_mix_counts_citing_the_seeds_as_three_query_lists() -> None:
    """A paper no query returned but that cites many seeds joins the relevant stratum."""
    hit_once = _cand("W1", year=2010, cited=5, inset=0)
    couples = _cand(
        "W2", year=2010, cited=0, inset=0, coupling=6, wcoupling=9.5, origin="snowball_forward"
    )
    seminal = _cand(
        "W3", year=2003, cited=900, inset=40, specificity=20.0, origin="snowball_backward"
    )
    lists = [[hit_once.record]]

    with_coupling = [
        c.openalex_id for c in rank_mix([seminal, couples, hit_once], lists, novel_from_year=2021)
    ]
    without = [
        c.openalex_id
        for c in rank_mix(
            [seminal, couples, hit_once], lists, novel_from_year=2021, coupling_lists=0
        )
    ]

    # Three lists at rank 1 (3/61) beat one list at rank 1 (1/61): W2 leads relevant.
    assert with_coupling == ["W2", "W3", "W1"]
    assert without == ["W1", "W3", "W2"]
