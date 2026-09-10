"""Self-check for the eval's pure functions: scoring, CSV loading, the sweep's
output tables, and the OpenAlex retry logic (no network, no DB).

Run: uv run --project backend python scripts/eval_ground_truth/test_metrics.py
"""

from ground_truth import clean_review_title, months_earlier, normalize_doi
from search_eval import _keys_of, _recall


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


def test_ground_truth_keys_union() -> None:
    from ground_truth import GroundTruth

    gt = GroundTruth(dois={"10.1/a"}, source="url", overton_ids={"overton:P9"})
    assert gt.keys == {"10.1/a", "overton:P9"}
    # A DOI-mode ground truth has no Overton half, so keys == dois exactly.
    assert GroundTruth(dois={"10.1/a"}, source="doi").keys == {"10.1/a"}


def test_recall() -> None:
    assert _recall({"a", "b"}, {"a", "b", "c"}) == 2 / 3
    assert _recall(set(), {"a"}) == 0.0
    assert _recall({"a"}, set()) == 0.0  # no ground truth -> undefined, treated as 0


def test_keys_of() -> None:
    docs = [
        {"doi": "https://doi.org/10.1/A"},
        {"backend": "overton", "backend_record_id": "P9"},
        {"doi": None},  # no key -> dropped, cannot be matched against ground truth
    ]
    assert _keys_of(docs) == {"10.1/a", "overton:P9"}


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


def test_openalex_get_retries() -> None:
    """``openalex_get`` retries 5xx and transport errors, and returns 4xx at once.

    Never touches the network: ``httpx.get`` and ``time.sleep`` are swapped for
    fakes, so only the retry decisions are tested.
    """
    from unittest.mock import patch

    import httpx

    import ground_truth

    def responses(*status_codes):
        codes = list(status_codes)
        return lambda url, **_: httpx.Response(codes.pop(0), request=httpx.Request("GET", url))

    with patch("time.sleep"):
        # A 504 then a 200: the retry wins, the caller sees only the 200.
        with patch("httpx.get", responses(504, 200)):
            assert ground_truth.openalex_get("/works/W1").status_code == 200
        # A genuine 404 is not transient: return it at once, do not retry.
        with patch("httpx.get", responses(404, 200)):
            assert ground_truth.openalex_get("/works/W1").status_code == 404
        # Always 504: give up after 5 tries and hand back the last response.
        with patch("httpx.get", responses(504, 504, 504, 504, 504)):
            assert ground_truth.openalex_get("/works/W1").status_code == 504

        # A connection error that later clears is also retried.
        calls = {"n": 0}

        def flaky_get(url, **_):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectTimeout("boom")
            return httpx.Response(200, request=httpx.Request("GET", url))

        with patch("httpx.get", flaky_get):
            assert ground_truth.openalex_get("/works/W1").status_code == 200


def test_months_earlier() -> None:
    assert months_earlier("2023-01-01", 1) == "2022-12-01"  # year boundary
    assert months_earlier("2023-03-31", 1) == "2023-02-28"  # day-overflow clamp, non-leap
    assert months_earlier("2024-03-31", 1) == "2024-02-29"  # day-overflow clamp, leap year
    assert months_earlier("2023-06-15", 1) == "2023-05-15"  # ordinary case


def _fake_run(screened: bool = False):
    """One synthetic run: two API calls, one per backend, over a 3-paper review.

    10.1/a:     returned by both backends, kept (from OpenAlex — acquire keeps
                one copy of a paper both providers found).
    10.1/b:     returned by OpenAlex only, then dropped by the cap.
    10.1/c:     never returned at all.
    overton:P9: a policy document with NO DOI — returned by Overton and kept.
                Scored on its Overton id; a DOI-only measurement loses it.

    With ``screened=True`` the run also screened, and kept only 10.1/a.
    """
    from ground_truth import GroundTruth
    from search_eval import QueryResult

    ground_truth = GroundTruth(
        dois={"10.1/a", "10.1/b", "10.1/c"},
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
    search_docs = [
        {"doi": "10.1/a", "backend": "openalex", "title": "Paper A"},
        {"doi": "10.9/z", "backend": "openalex", "title": "Off-target"},
        {"backend": "overton", "backend_record_id": "P9", "title": "Loneliness statistics"},
    ]
    result = QueryResult(
        query="q",
        search_candidate_count=2,
        screened_relevant_count=1 if screened else 0,
        search_recall=1 / 3,
        screen_recall=1 / 4 if screened else None,
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
        search_docs=search_docs,
        screened_docs=search_docs[:1] if screened else [],
    )
    # Key -> title, as the dataset item carries it (10.1/c deliberately has none).
    titles = {"10.1/a": "Paper A", "10.1/b": "Paper B", "overton:P9": "Loneliness statistics"}
    return result, ground_truth, titles


def test_recording_backend_records_failed_calls() -> None:
    """A call that fails after its retries must still appear in the call list.

    Before this, a 500ed query vanished: the run's recall dropped with nothing
    in the output to say a query never ran.
    """
    from search_eval import _RecordingBackend

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
    """The gt_reviews.csv loader: what it accepts, skips, and rejects."""
    import tempfile
    from pathlib import Path

    from ground_truth_dataset import load_reviews as _load_reviews

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
    from policy_atlas.evidence_search.sourcing.search_generation import (
        OpenAISearchGenerationBackend,
        V2SearchGenerationBackend,
    )
    from search_eval import GENERATION_BACKENDS
    from sweep_record_cap import _prompt_identity

    assert GENERATION_BACKENDS == {
        "shared": OpenAISearchGenerationBackend,
        "per-provider": V2SearchGenerationBackend,
    }
    # Every arm records which prompt file(s) it read, as a name and a hash,
    # taken from the class itself so the eval cannot drift from the pipeline.
    for cls in GENERATION_BACKENDS.values():
        assert cls.prompt_files and all(f.is_file() for f in cls.prompt_files)
    assert _prompt_identity("shared")[0] == "search_queries_v3"
    assert _prompt_identity("per-provider")[0] == "search_queries_openalex_v2+search_queries_overton_v2"
    assert len(_prompt_identity("shared")[1]) == 12


def test_sweep_run_frames() -> None:
    """The three output tables built from one finished run."""
    import pandas as pd

    from sweep_record_cap import _run_frames

    result, ground_truth, titles = _fake_run()
    meta = {
        "run_id": "shared-cap250-r1",
        "generation_backend": "shared",
        "record_cap_per_backend": 250,
    }
    runs, queries, papers = _run_frames(result, ground_truth, titles, meta)

    # Every frame carries the identity columns, so the three files join.
    for frame in (runs, queries, papers):
        assert list(frame.columns)[: len(meta)] == list(meta)
        assert (frame["run_id"] == "shared-cap250-r1").all()

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
    assert papers_by_doi.loc["10.1/a", "title"] == "Paper A"

    # The numbers that go to Langfuse: the run's de-duplicated totals as the
    # trace output, and one numeric score per key.
    from sweep_record_cap import SCORE_KEYS, _summary, score_summary

    summary = _summary(runs)
    assert summary["search_recall"] == 0.5 and summary["n_found"] == 2
    assert summary["found_by_backend"] == {"openalex": 1, "overton": 1}
    # Screening was not run: no screening score is recorded, and the papers
    # column reads "not measured", not "nothing survived".
    assert "screen_recall" not in summary and "n_screened_in" not in summary
    assert papers["screened_in"].isna().all()
    scores = score_summary(output=summary)
    assert [s.name for s in scores] == [k for k in SCORE_KEYS if not k.startswith(("screen", "n_screened"))]
    assert all(isinstance(s.value, (int, float)) for s in scores)


def test_sweep_run_frames_with_screening() -> None:
    """With --screen, the runs frame and scores carry screen_recall too."""
    from sweep_record_cap import _run_frames, _summary, score_summary

    result, ground_truth, titles = _fake_run(screened=True)
    runs, _queries, papers = _run_frames(result, ground_truth, titles, {"run_id": "r"})

    by_backend = runs.set_index("backend")
    # Screening kept 10.1/a only: 1 of 4 targets overall, 1 of OpenAlex's 1, 0 of Overton's 1.
    assert by_backend.loc["all", "n_screened_in"] == 1
    assert by_backend.loc["all", "screen_recall"] == 0.25
    assert by_backend.loc["openalex", "screen_recall"] == 0.25
    assert by_backend.loc["overton", "n_screened_in"] == 0

    papers_by_key = papers.set_index("key")
    assert bool(papers_by_key.loc["10.1/a", "screened_in"])
    assert not bool(papers_by_key.loc["overton:P9", "screened_in"])
    # Never reached the database, so it cannot have been screened in either.
    assert not bool(papers_by_key.loc["10.1/b", "screened_in"])

    summary = _summary(runs)
    assert summary["screen_recall"] == 0.25 and summary["n_screened_in"] == 1
    assert {s.name for s in score_summary(output=summary)} >= {"search_recall", "screen_recall"}


def test_load_references_and_items() -> None:
    """references.csv -> per-review recall targets -> Langfuse dataset items."""
    import tempfile
    from pathlib import Path

    from ground_truth_dataset import ReviewSpec, build_items, load_references

    text = (
        "review_title,ref_title,doi,overton_id,label\n"
        "Review A: a systematic review,Paper one,https://doi.org/10.1/A,,content\n"
        "Review A: a systematic review,Paper two,,P9,content\n"
        "Review A: a systematic review,No key,,,content\n"
        "Review A: a systematic review,Background,10.1/z,,other\n"
        "Review B,Lonely,10.1/b,,content\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "references.csv"
        path.write_text(text, encoding="utf-8")
        references = load_references(path)

    target = references["Review A: a systematic review"]
    # DOIs normalised, Overton ids prefixed; 'other' rows and keyless rows excluded.
    assert target["titles"] == {"10.1/a": "Paper one", "overton:P9": "Paper two"}
    assert target["n_unscorable"] == 1

    reviews = [
        ReviewSpec(title="Review A: a systematic review", doi="10.1/r", published_before="2023-01-01"),
        ReviewSpec(title="Review C", url="https://example.org/c", published_before="2023-01-01"),
    ]
    items = build_items(reviews, references, "ds")
    # Review C has no references: skipped, not uploaded with an empty target.
    assert len(items) == 1
    item = items[0]
    assert item["id"].startswith("ds:") and len(item["id"]) == len("ds:") + 32
    assert item["input"] == {"intent": "Review A", "published_before": "2023-01-01"}
    assert item["expected_output"]["keys"] == ["10.1/a", "overton:P9"]
    assert item["metadata"]["n_target"] == 2 and item["metadata"]["n_unscorable"] == 1
    assert item["metadata"]["source"] == "doi" and item["metadata"]["review_id"] == "10.1/r"


if __name__ == "__main__":
    test_normalize_doi()
    test_record_key()
    test_ground_truth_keys_union()
    test_recall()
    test_keys_of()
    test_clean_review_title()
    test_openalex_get_retries()
    test_months_earlier()
    test_recording_backend_records_failed_calls()
    test_load_reviews_csv()
    test_sweep_cap_overrides()
    test_generation_backend_arms()
    test_sweep_run_frames()
    test_sweep_run_frames_with_screening()
    test_load_references_and_items()
    print("ok")
