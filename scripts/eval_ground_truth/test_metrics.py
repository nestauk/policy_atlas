"""Self-check for the pure scoring functions (no network, no DB).

Run: uv run --project backend python scripts/eval_ground_truth/test_metrics.py
"""

from ground_truth import normalize_doi
from run_and_score import _months_earlier, _recall, clean_review_title, partition_screened


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1234/AbC") == "10.1234/abc"
    assert normalize_doi("10.1234/AbC") == "10.1234/abc"
    assert normalize_doi(None) is None
    assert normalize_doi("") is None


def test_record_key() -> None:
    """The identity a document is scored on, DOI first, Overton id as fallback."""
    from ground_truth import record_key

    # A DOI always wins, whichever backend supplied the record.
    assert record_key({"doi": "https://doi.org/10.1/AbC", "backend": "openalex"}) == "10.1/abc"
    assert record_key({"doi": "10.1/a", "backend": "overton", "backend_record_id": "P1"}) == "10.1/a"
    # No DOI, from Overton: the policy document id keeps it scorable.
    assert record_key({"backend": "overton", "backend_record_id": "P9"}) == "overton:P9"
    # No DOI, from OpenAlex: nothing to match on.
    assert record_key({"backend": "openalex", "backend_record_id": "W1"}) is None
    assert record_key({}) is None
    assert record_key(None) is None


def test_overton_query_variants() -> None:
    """Overton's keyword index treats punctuation literally, so a title is
    asked for in more than one spelling — but only when that changes anything."""
    from ground_truth import _match_form, _overton_query_variants

    variants = _overton_query_variants("Children's experiences of loneliness: 2018")
    # The colon is dropped (it is field-prefix syntax), and both apostrophe
    # spellings are tried — the straight one alone finds nothing in Overton.
    assert variants[0] == 'title:"Children\'s experiences of loneliness  2018"'
    assert any("’" in v for v in variants)
    assert all(":" not in v.split("title:", 1)[-1].replace('"', "") for v in variants)

    # No apostrophe -> no extra spellings, so the common case stays at one
    # precise query plus one bare fallback.
    assert len(_overton_query_variants("Tackling loneliness evidence review")) == 2

    # Matching folds the two apostrophes together, so the spelling Overton
    # happens to use does not depress the similarity score.
    assert _match_form("Children’s") == _match_form("Children's")


def test_ground_truth_keys_union() -> None:
    from ground_truth import GroundTruth

    gt = GroundTruth(
        dois={"10.1/a"}, resolvable_fraction=1.0, source="url", overton_ids={"overton:P9"}
    )
    assert gt.keys == {"10.1/a", "overton:P9"}
    # A DOI-mode ground truth has no Overton half, so keys == dois exactly.
    assert GroundTruth(dois={"10.1/a"}, resolvable_fraction=1.0, source="doi").keys == {"10.1/a"}


def test_recall() -> None:
    assert _recall({"a", "b"}, {"a", "b", "c"}) == 2 / 3
    assert _recall(set(), {"a"}) == 0.0
    assert _recall({"a"}, set()) == 0.0  # no ground truth -> undefined, treated as 0


def test_partition_screened() -> None:
    ground_truth_dois = {"10.1/a", "10.1/b"}
    screened = [
        {"doi": "10.1/a"},  # in ground truth
        {"doi": "10.1/b"},  # in ground truth
        {"doi": "10.1/c"},  # unexplained
        {"doi": None},  # no doi -> unexplained (can't be confirmed against ground truth)
    ]
    dois, in_ground_truth, unexplained = partition_screened(screened, ground_truth_dois)
    assert dois == {"10.1/a", "10.1/b", "10.1/c"}
    assert in_ground_truth == [{"doi": "10.1/a"}, {"doi": "10.1/b"}]
    assert unexplained == [{"doi": "10.1/c"}, {"doi": None}]


def test_clean_review_title() -> None:
    assert (
        clean_review_title("The effect of parental leave on parents' mental health: a systematic review")
        == "The effect of parental leave on parents' mental health"
    )
    assert (
        clean_review_title("Universal basic income and health - A Bibliometric Analysis")
        == "Universal basic income and health"
    )
    assert (
        clean_review_title("Effects of X on Y: a scoping review of randomized controlled trials")
        == "Effects of X on Y"
    )
    # No colon/dash-anchored suffix -> left untouched, even though "systematic
    # reviews" appears in the title (this is the false-positive guard).
    assert (
        clean_review_title("Barriers to conducting systematic reviews in LMICs")
        == "Barriers to conducting systematic reviews in LMICs"
    )


def test_months_earlier() -> None:
    assert _months_earlier("2023-01-01", 1) == "2022-12-01"  # year boundary
    assert _months_earlier("2023-03-31", 1) == "2023-02-28"  # day-overflow clamp, non-leap
    assert _months_earlier("2024-03-31", 1) == "2024-02-29"  # day-overflow clamp, leap year
    assert _months_earlier("2023-06-15", 1) == "2023-05-15"  # ordinary case


def _fake_run():
    """One synthetic run: two API calls, one per backend, over a 3-paper review.

    10.1/a:     returned by both backends, kept (from OpenAlex — acquire keeps
                one copy of a paper both providers found).
    10.1/b:     returned by OpenAlex only, then dropped by the cap.
    10.1/c:     never returned at all.
    overton:P9: a policy document with NO DOI — returned by Overton and kept.
                Scored on its Overton id; a DOI-only measurement loses it.
    """
    import pandas as pd

    from ground_truth import GroundTruth
    from run_and_score import QueryResult

    ground_truth = GroundTruth(
        dois={"10.1/a", "10.1/b", "10.1/c"},
        resolvable_fraction=1.0,
        source="url",
        overton_ids={"overton:P9"},
        titles={"overton:P9": "Loneliness statistics"},
    )
    openalex_records = [
        {"id": "W1", "display_name": "Paper A", "doi": "https://doi.org/10.1/A"},
        {"id": "W2", "display_name": "Paper B", "doi": "https://doi.org/10.1/b"},
        {"id": "W3", "display_name": "Off-target", "doi": "https://doi.org/10.9/z"},
    ]
    overton_records = [
        {
            "policy_document_id": "P1",
            "title": "Paper A as policy",
            "document_url": "https://example.org/p1",
            "keyed_other_identifiers": {"doi": ["10.1/a"]},
        },
        {
            "policy_document_id": "P9",
            "title": "Loneliness statistics",
            "document_url": "https://example.org/p9",
        },
    ]
    result = QueryResult(
        query="q",
        search_candidate_count=2,
        screened_relevant_count=0,
        search_recall=1 / 3,
        screen_recall=None,
        judge_calibration_rate=None,
        judge_precision_proxy=None,
        n_calibration_sampled=0,
        n_precision_sampled=0,
        search_calls=[
            {
                "backend": "openalex",
                "method": "search",
                "query": "parental leave",
                "wire_params": {"filter": "x"},
                "result_count": len(openalex_records),
                "records": openalex_records,
            },
            {
                "backend": "overton",
                "method": "search",
                "query": "how does parental leave affect parents?",
                "wire_params": None,
                "result_count": len(overton_records),
                "records": overton_records,
            },
        ],
        # What survived the cap into the database, as acquire persists it.
        search_docs=[
            {"doi": "10.1/a", "backend": "openalex", "title": "Paper A"},
            {"doi": "10.9/z", "backend": "openalex", "title": "Off-target"},
            {"backend": "overton", "backend_record_id": "P9", "title": "Loneliness statistics"},
        ],
        screened_docs=[],
    )
    gt_titles = pd.DataFrame(
        [
            {"key": "10.1/a", "space": "doi", "title": "Paper A", "year": 2020, "in_openalex": True},
            {"key": "10.1/b", "space": "doi", "title": "Paper B", "year": 2019, "in_openalex": True},
            {"key": "10.1/c", "space": "doi", "title": None, "year": None, "in_openalex": False},
            {
                "key": "overton:P9",
                "space": "overton",
                "title": "Loneliness statistics",
                "year": None,
                "in_openalex": None,
            },
        ]
    )
    return result, ground_truth, gt_titles


def test_recording_backend_records_failed_calls() -> None:
    """A call that fails after its retries must still appear in the call list.

    Before this, a 500ed query vanished: the run's recall dropped with nothing
    in the output to say a query never ran.
    """
    from run_and_score import _RecordingBackend

    class _Boom:
        name = "openalex"
        trust_class = "academic_aggregator"
        mode = "live"
        caps = None

        def search(self, query, *, wire_params=None, max_results=None):
            raise RuntimeError("search transport error host=api.openalex.org status_code=500")

    calls: list[dict] = []
    backend = _RecordingBackend(_Boom(), calls)

    # The failure must propagate — search_loop relies on catching it.
    try:
        backend.search("loneliness interventions", wire_params={"filter": "x"})
        raise AssertionError("the failure should have been re-raised")
    except RuntimeError:
        pass

    assert len(calls) == 1
    assert calls[0]["query"] == "loneliness interventions"
    assert calls[0]["result_count"] == 0
    assert calls[0]["records"] == []
    assert "status_code=500" in calls[0]["error"]


def test_load_reviews_csv() -> None:
    """The --reviews CSV loader: what it accepts, skips, and rejects."""
    import tempfile
    from pathlib import Path

    from sweep_record_cap import _load_reviews

    def load(text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reviews.csv"
            path.write_text(text, encoding="utf-8")
            return _load_reviews(path)

    header = "title,url,doi,published_before,exclude\n"

    reviews = load(
        header
        + "A DOI review,,10.1/a,,\n"
        + "A URL review,https://example.org/r,,2023-02-17,\n"
        + "An excluded one,,10.1/c,,yes\n"
    )
    assert [r.title for r in reviews] == ["A DOI review", "A URL review"]
    # A DOI row needs no date — it comes from OpenAlex.
    assert reviews[0].doi == "10.1/a" and reviews[0].published_before is None
    assert reviews[1].url == "https://example.org/r" and reviews[1].published_before == "2023-02-17"

    # A URL row with no date cannot be run: there is nothing to derive one from.
    try:
        load(header + "No date,https://example.org/r,,,\n")
        raise AssertionError("a url row without published_before must be rejected")
    except ValueError as exc:
        assert "published_before" in str(exc)

    # A DOI wins over a URL, since its reference list needs no LLM transcription.
    both = load(header + "Both,https://example.org/r,10.1/a,,\n")
    assert both[0].doi == "10.1/a" and both[0].url is None

    # Bad rows are reported together, not one run at a time.
    try:
        load(header + ",,10.1/a,,\n" + "No identifier,,,,\n")
        raise AssertionError("bad rows must be rejected")
    except ValueError as exc:
        assert "2 unusable row(s)" in str(exc)


def test_sweep_cap_overrides() -> None:
    """The cap overrides sweep_record_cap.py applies before each run."""
    from sweep_record_cap import DEPTH, RESULT_CAP_PER_BACKEND, _apply_caps

    constants = _apply_caps(250)
    assert constants["record_cap_per_backend"] == 250
    assert constants["result_cap_per_backend"] == RESULT_CAP_PER_BACKEND
    assert constants["round_cap"] == 1, f"{DEPTH} must stay a single-round search"


def test_generation_backend_arms() -> None:
    """The two arms compared: one shared prompt vs one prompt per provider."""
    from policy_atlas.evidence_base.sourcing import search_prompts
    from policy_atlas.evidence_base.sourcing.search_generation import (
        OpenAISearchGenerationBackend,
        V2SearchGenerationBackend,
    )
    from run_and_score import GENERATION_BACKENDS

    assert GENERATION_BACKENDS == {
        "v1": OpenAISearchGenerationBackend,
        "v2": V2SearchGenerationBackend,
    }
    # Each arm's prompt files, so a rename in search_prompts.py fails here
    # rather than silently changing what the eval compares.
    assert search_prompts.SEARCH_QUERIES_PROMPT_FILE.name == "search_queries_system_v3.txt"
    assert (
        search_prompts.SEARCH_QUERIES_V2_OPENALEX_PROMPT_FILE.name
        == "search_queries_openalex_system_v2.txt"
    )
    assert (
        search_prompts.SEARCH_QUERIES_V2_OVERTON_PROMPT_FILE.name
        == "search_queries_overton_system_v2.txt"
    )


def test_sweep_run_frames() -> None:
    """The three output tables built from one finished run."""
    import pandas as pd

    from sweep_record_cap import _run_frames

    result, ground_truth, gt_titles = _fake_run()
    meta = {
        "run_id": "v1-cap250-r1",
        "generation_backend_variant": "v1",
        "record_cap_per_backend": 250,
    }
    runs, queries, papers = _run_frames(result, ground_truth, gt_titles, meta)

    # Every frame carries the identity columns, so the three files join.
    for frame in (runs, queries, papers):
        assert list(frame.columns)[: len(meta)] == list(meta)
        assert (frame["run_id"] == "v1-cap250-r1").all()

    by_backend = runs.set_index("backend")
    assert by_backend.loc["openalex", "n_api_records"] == 3
    assert by_backend.loc["overton", "n_api_records"] == 2
    # 10.1/a is kept once, under OpenAlex — Overton must not be credited too.
    assert by_backend.loc["openalex", "n_found"] == 1
    # Overton earns exactly the DOI-less policy document, which is the whole
    # point of the second key space.
    assert by_backend.loc["overton", "n_found"] == 1
    assert by_backend.loc["all", "n_found"] == 2
    assert by_backend.loc["all", "n_api_records"] == 5
    assert by_backend.loc["all", "n_ground_truth"] == 4
    assert round(by_backend.loc["all", "search_recall"], 4) == 0.5

    assert list(queries["query"]) == ["parental leave", "how does parental leave affect parents?"]
    assert list(queries["gt_hits"]) == [2, 2]

    papers_by_doi = papers.set_index("key")
    # Returned by both providers, kept from one.
    assert papers_by_doi.loc["10.1/a", "returned_by"] == "openalex+overton"
    assert papers_by_doi.loc["10.1/a", "kept_from"] == "openalex"
    assert bool(papers_by_doi.loc["10.1/a", "reached_db"])
    # Fetched and then dropped by the cap — the row the sweep exists to find.
    assert bool(papers_by_doi.loc["10.1/b", "returned_by_api"])
    assert not bool(papers_by_doi.loc["10.1/b", "reached_db"])
    # Never returned by any query.
    assert not bool(papers_by_doi.loc["10.1/c", "returned_by_api"])
    # Empty rather than a backend name (pandas renders the None as a blank cell).
    assert pd.isna(papers_by_doi.loc["10.1/c", "returned_by"])
    # The DOI-less policy document is found, and labelled as the Overton half
    # of the target so the two spaces can be scored apart.
    assert papers_by_doi.loc["overton:P9", "space"] == "overton"
    assert papers_by_doi.loc["overton:P9", "kept_from"] == "overton"
    assert bool(papers_by_doi.loc["overton:P9", "reached_db"])


if __name__ == "__main__":
    test_normalize_doi()
    test_record_key()
    test_overton_query_variants()
    test_ground_truth_keys_union()
    test_recall()
    test_partition_screened()
    test_clean_review_title()
    test_months_earlier()
    test_recording_backend_records_failed_calls()
    test_load_reviews_csv()
    test_sweep_cap_overrides()
    test_generation_backend_arms()
    test_sweep_run_frames()
    print("ok")
