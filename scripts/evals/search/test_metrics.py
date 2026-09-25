"""Self-check for the eval's pure functions: scoring, CSV loading, the sweep's
output tables, and the OpenAlex retry logic. No network, no database.

Run: uv run --project backend python scripts/evals/search/test_metrics.py
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
        # Key -> title, as the dataset item carries it (10.1/c deliberately has none).
        titles={"10.1/a": "Paper A", "10.1/b": "Paper B", "overton:P9": "Loneliness statistics"},
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
    return result, ground_truth


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

    result, ground_truth = _fake_run()
    meta = {
        "run_id": "shared-cap250-r1",
        "generation_backend": "shared",
        "record_cap_per_backend": 250,
    }
    runs, queries, papers = _run_frames(result, ground_truth, meta)

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

    result, ground_truth = _fake_run(screened=True)
    runs, _queries, papers = _run_frames(result, ground_truth, {"run_id": "r"})

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


def test_multi_round_depth_needs_screening() -> None:
    """standard/deep are search-screen-search loops; without screening the
    later rounds have nothing to seed from, so the eval refuses up front
    (before it touches the database — hence conn=None here)."""
    from ground_truth import GroundTruth
    from search_eval import run_one_query

    gt = GroundTruth(dois={"10.1/a"}, source="doi")
    for depth in ("standard", "deep"):
        try:
            run_one_query(None, "q", gt, published_before="2020-01-01", depth=depth, run_screen=False)
            raise AssertionError(f"{depth} without screening must be refused")
        except ValueError as exc:
            assert "run_screen=True" in str(exc)


def test_production_recall_scores() -> None:
    """Per-review scores the production experiment records: the sweep's plus rounds_run."""
    from production_recall import _mean, item_scores

    output = {"search_recall": 0.5, "n_found": 2, "n_ground_truth": 4, "n_failed_calls": 0,
              "n_screened_in": 1, "screen_recall": 0.25, "rounds_run": 2}
    names = {e.name for e in item_scores(output=output)}
    assert {"search_recall", "screen_recall", "n_found", "n_failed_calls", "rounds_run"} <= names
    # The console summary averages like Langfuse's table does; "not measured" stays None.
    assert _mean([0.5, 0.25]) == 0.375 and _mean([]) is None


def test_select_items() -> None:
    """--reviews narrows the run by item id, review id or title; no match is an error."""
    from types import SimpleNamespace

    from production_recall import select_items

    items = [
        SimpleNamespace(id="ds:922c2d87", metadata={"review_id": "10.1016/s2468", "review_title": "Parental leave"}),
        SimpleNamespace(id="ds:abcd", metadata={"review_id": "https://gov.uk/x", "review_title": "Loneliness"}),
    ]
    assert select_items(items, None) == items
    assert select_items(items, ["922c2d87"]) == items[:1]  # by item id
    assert select_items(items, ["parental LEAVE"]) == items[:1]  # by title, case-insensitive
    assert select_items(items, ["gov.uk"]) == items[1:]  # by review id
    assert select_items(items, ["parental", "lonel"]) == items  # any of several
    try:
        select_items(items, ["nothing"])
        raise AssertionError("no match must be an error")
    except ValueError as exc:
        assert "Parental leave" in str(exc)  # lists what was available


def _baseline_response(body):
    import httpx

    return httpx.Response(
        200, json=body, request=httpx.Request("GET", "https://example.test")
    )


def _baseline_get(bodies, seen=None):
    values = list(bodies)
    seen = seen if seen is not None else []

    def get(url, params, headers):
        seen.append(dict(params))
        return _baseline_response(values.pop(0))

    return get


def test_baseline_records_of() -> None:
    from baseline_recall import Fetched, records_of
    from ground_truth import record_key

    common = dict(
        request={},
        page_size=100,
        n_failed_calls=0,
        complete=True,
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    semantic = Fetched(
        pages=[
            {
                "data": [
                    {"paperId": "S1", "externalIds": {"DOI": "10.1/A"}, "title": "S"},
                    {"paperId": "S2", "externalIds": None, "title": "No key"},
                ]
            }
        ],
        **common,
    )
    consensus = Fetched(
        pages=[{"results": [{"paper_id": "C1", "doi": "10.1/C", "title": "C"}]}],
        **common,
    )
    openalex = Fetched(
        pages=[{"results": [{"id": "W1", "doi": "10.1/O", "display_name": "O"}]}],
        **common,
    )
    assert records_of("semantic-scholar", semantic)[0] == {
        "doi": "10.1/A",
        "backend": "semantic-scholar",
        "backend_record_id": "S1",
        "title": "S",
    }
    assert record_key(records_of("semantic-scholar", semantic)[1]) is None
    assert records_of("consensus", consensus)[0]["backend_record_id"] == "C1"
    assert records_of("openalex-raw", openalex)[0]["title"] == "O"


def test_baseline_cutoffs() -> None:
    from baseline_recall import (
        consensus_cutoff,
        fetch_consensus,
        fetch_openalex_raw,
        openalex_cutoff,
        semantic_scholar_cutoff,
        semantic_scholar_query,
    )

    assert semantic_scholar_cutoff("2019-03-15") == ":2019-03-15"
    assert openalex_cutoff("2019-03-15") == "to_publication_date:2019-03-15"
    assert consensus_cutoff("2019-03-15") == {"year_max": "2019", "month_max": "3"}
    assert consensus_cutoff("2019-11-01")["month_max"] == "11"
    assert semantic_scholar_query("work-life balance") == "work life balance"
    seen = []
    fetch_consensus(
        "work-life balance",
        "2019-03-15",
        get=_baseline_get([{"results": [], "page_size": 300, "is_end": True}], seen),
        api_key="secret",
    )
    fetch_openalex_raw(
        "work-life balance", "2019-03-15", get=_baseline_get([{"results": []}], seen)
    )
    assert all(
        params["query"] == "work-life balance" for params in seen if "query" in params
    )
    assert (
        next(params for params in seen if "search" in params)["search"]
        == "work-life balance"
    )


def test_baseline_paging_semantic_scholar() -> None:
    from baseline_recall import fetch_semantic_scholar

    seen = []
    fetched = fetch_semantic_scholar(
        "q",
        "2020-01-01",
        get=_baseline_get(
            [{"data": [{"paperId": "1"}], "next": 100}, {"data": [{"paperId": "2"}]}],
            seen,
        ),
        api_key="x",
    )
    assert len(fetched.pages) == 2 and [p["offset"] for p in seen] == ["0", "100"]
    assert (
        len(
            fetch_semantic_scholar(
                "q", "2020-01-01", get=_baseline_get([{"data": []}]), api_key="x"
            ).pages
        )
        == 1
    )
    full = {"data": [{"paperId": str(i)} for i in range(100)]}
    assert (
        len(
            fetch_semantic_scholar(
                "q", "2020-01-01", get=_baseline_get([full]), api_key="x"
            ).pages
        )
        == 1
    )
    pages = [
        {"data": [{"paperId": f"{i}-{j}"} for j in range(100)], "next": (i + 1) * 100}
        for i in range(11)
    ]
    seen = []
    assert (
        len(
            fetch_semantic_scholar(
                "q", "2020-01-01", get=_baseline_get(pages, seen), api_key="x"
            ).pages
        )
        == 10
    )
    assert [p["offset"] for p in seen] == [str(i * 100) for i in range(10)]


def test_baseline_paging_consensus() -> None:
    from baseline_recall import fetch_consensus

    seen = []
    pages = [
        {
            "results": [{"paper_id": "1"}],
            "page_size": 300,
            "is_end": False,
            "next_page": 1,
        },
        {"results": [{"paper_id": "2"}], "page_size": 300, "is_end": True},
    ]
    fetched = fetch_consensus(
        "q", "2020-01-01", get=_baseline_get(pages, seen), api_key="x"
    )
    assert (
        seen[0]["page"] == "0"
        and seen[0]["page_size"] == "1000"
        and seen[1]["page_size"] == "300"
        and fetched.page_size == 300
    )
    assert (
        len(
            fetch_consensus(
                "q",
                "2020-01-01",
                get=_baseline_get([{"results": [], "page_size": 300, "is_end": False}]),
                api_key="x",
            ).pages
        )
        == 1
    )
    # Page size 300: pages 0-2 give 900 results. Page 3 at 300 would pass 1,000 and
    # Consensus answers 400, so the last request is page 9 at size 100, then stop.
    # Pages can hold a few results fewer than their size, and Consensus sends no
    # next_page on the page before the ceiling; positions, not counts, drive the rule.
    full = [
        {
            "results": [{"paper_id": "0"}] * 297,
            "page_size": 300,
            "is_end": False,
            "next_page": 1,
        },
        {
            "results": [{"paper_id": "1"}] * 300,
            "page_size": 300,
            "is_end": False,
            "next_page": 2,
        },
        {
            "results": [{"paper_id": "2"}] * 299,
            "page_size": 300,
            "is_end": False,
            "next_page": None,
        },
        {"results": [{"paper_id": "last"}] * 100, "page_size": 100, "is_end": False},
    ]
    seen = []
    fetched = fetch_consensus(
        "q", "2020-01-01", get=_baseline_get(full, seen), api_key="x"
    )
    assert [(p["page"], p["page_size"]) for p in seen] == [
        ("0", "1000"),
        ("1", "300"),
        ("2", "300"),
        ("9", "100"),
    ]
    assert len(fetched.pages) == 4 and fetched.page_size == 300
    # Page size 750 (Deep plan): page 0 at 750, then page 3 at 250.
    deep = [
        {"results": [{}] * 750, "page_size": 750, "is_end": False},
        {"results": [{}] * 250, "page_size": 250, "is_end": False},
    ]
    seen = []
    fetch_consensus("q", "2020-01-01", get=_baseline_get(deep, seen), api_key="x")
    assert [(p["page"], p["page_size"]) for p in seen] == [("0", "1000"), ("3", "250")]
    # Fewer than 1,000 results in total: stops on is_end without a remainder request.
    short = [
        {"results": [{}] * 300, "page_size": 300, "is_end": False},
        {"results": [{}] * 40, "page_size": 300, "is_end": True},
    ]
    assert (
        len(
            fetch_consensus(
                "q", "2020-01-01", get=_baseline_get(short), api_key="x"
            ).pages
        )
        == 2
    )


def test_baseline_paging_openalex() -> None:
    from baseline_recall import fetch_openalex_raw

    seen = []
    short = fetch_openalex_raw(
        "q", "2020-01-01", get=_baseline_get([{"results": [{}]}], seen)
    )
    assert (
        len(short.pages) == 1
        and seen[0]["per-page"] == "200"
        and seen[0]["filter"] == "to_publication_date:2020-01-01"
    )
    full = [{"results": [{"id": str(j)} for j in range(200)]} for _ in range(6)]
    assert (
        len(fetch_openalex_raw("q", "2020-01-01", get=_baseline_get(full)).pages) == 5
    )


def test_baseline_retry() -> None:
    import httpx

    from baseline_recall import fetch_openalex_raw, make_getter

    sleeps = []
    values = [httpx.Response(429, headers={"retry-after": "3"}), httpx.Response(200)]
    getter = make_getter(
        "semantic-scholar",
        sleep=sleeps.append,
        get=lambda *args, **kwargs: values.pop(0),
    )
    assert getter("url", {}, {}).status_code == 200 and 3.0 in sleeps
    sleeps = []
    getter = make_getter(
        "semantic-scholar",
        sleep=sleeps.append,
        get=lambda *args, **kwargs: httpx.Response(503),
    )
    assert getter("url", {}, {}).status_code == 503 and sleeps[-3:] == [1.0, 2.0, 4.0]

    def failing(url, params, headers):
        return httpx.Response(503)

    fetched = fetch_openalex_raw("q", "2020-01-01", get=failing)
    assert fetched.n_failed_calls == 1 and not fetched.complete and fetched.pages == []
    # A full page, then a failure: the page already fetched is kept, the fetch is
    # marked incomplete, and nothing is raised.
    full_page = {"results": [{"id": str(j)} for j in range(200)]}
    answers = [_baseline_response(full_page), httpx.Response(503)]

    def then_failing(url, params, headers):
        return answers.pop(0)

    fetched = fetch_openalex_raw("q", "2020-01-01", get=then_failing)
    assert (
        fetched.n_failed_calls == 1 and not fetched.complete and len(fetched.pages) == 1
    )


def test_baseline_cache_round_trip() -> None:
    import json
    import tempfile
    from pathlib import Path

    from baseline_recall import (
        Fetched,
        cache_path,
        load_or_fetch,
        read_cache,
        write_cache,
    )

    fetched = Fetched(
        [{"results": []}], {"query": "q"}, 100, 0, True, "2026-01-01T00:00:00+00:00"
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        path = cache_path("consensus", "item", root)
        write_cache(
            path, arm="consensus", intent="q", cutoff="2020-01-01", fetched=fetched
        )
        assert (
            read_cache(path).pages == fetched.pages
            and read_cache(path).page_size == 100
        )
        calls = []
        assert load_or_fetch(
            "consensus",
            item_id="item",
            intent="q",
            cutoff="2020-01-01",
            cache_dir=root,
            fetcher=lambda *_: calls.append(1),
        )[1]
        incomplete = Fetched([], {}, 100, 1, False, fetched.fetched_at)
        write_cache(
            path, arm="consensus", intent="q", cutoff="2020-01-01", fetched=incomplete
        )

        def replacement(*_):
            return fetched

        assert not load_or_fetch(
            "consensus",
            item_id="item",
            intent="q",
            cutoff="2020-01-01",
            cache_dir=root,
            fetcher=replacement,
        )[1]
        assert not load_or_fetch(
            "consensus",
            item_id="item",
            intent="q",
            cutoff="2020-01-01",
            cache_dir=root,
            refresh=True,
            fetcher=replacement,
        )[1]
        assert set(json.loads(path.read_text())) == {
            "arm",
            "intent",
            "cutoff",
            "request",
            "page_size",
            "fetched_at",
            "complete",
            "n_failed_calls",
            "pages",
        }
        assert (
            "x-api-key" not in path.read_text()
            and path.name.endswith(".json")
            and len(path.stem) == 16
        )


def test_baseline_slice_and_cost() -> None:
    from baseline_recall import (
        Fetched,
        cost_usd,
        pages_for_cap,
        score_arm,
        slice_at_cap,
    )
    from ground_truth import GroundTruth

    records = [{"doi": "10/a"}, {"doi": "10/a"}, {"doi": "10/b"}]
    assert len(slice_at_cap(records, 2)) == 1 and len(slice_at_cap(records, 3)) == 2
    pages = [{"results": [{}] * 20}, {"results": [{}] * 150}, {"results": [{}] * 300}]
    assert (
        cost_usd("consensus", pages) == 0.3
        and cost_usd("semantic-scholar", pages) == 0.0
    )
    fetched = Fetched(
        [{"meta": {"cost_usd": 0.2}, "results": [{"doi": "10/a"}]}],
        {},
        200,
        0,
        True,
        "2026-01-01T00:00:00+00:00",
    )
    assert cost_usd("openalex-raw", pages_for_cap(fetched, 200)) == 0.2
    # A cited DOI in position N+1 is outside cap N, so it is not found at that cap.
    later = Fetched(
        [{"meta": {"cost_usd": 0.1}, "results": [{"doi": "10/x"}, {"doi": "10/a"}]}],
        {},
        200,
        0,
        True,
        "2026-01-01T00:00:00+00:00",
    )
    target = GroundTruth(dois={"10/a"}, source="doi")
    assert score_arm("openalex-raw", later, target, 1)["n_found"] == 0
    assert score_arm("openalex-raw", later, target, 2)["n_found"] == 1
    # The cache path scores exactly like the live path.
    import tempfile
    from pathlib import Path

    from baseline_recall import cache_path, read_cache, write_cache

    with tempfile.TemporaryDirectory() as tmp:
        path = cache_path("openalex-raw", "item", Path(tmp))
        write_cache(
            path, arm="openalex-raw", intent="q", cutoff="2020-01-01", fetched=later
        )
        for cap in (1, 2, 50):
            assert score_arm(
                "openalex-raw", read_cache(path), target, cap
            ) == score_arm("openalex-raw", later, target, cap)
    assert (
        score_arm(
            "openalex-raw", fetched, GroundTruth(dois={"10/a"}, source="doi"), 200
        )["n_found"]
        == 1
    )


def test_baseline_score_evaluator() -> None:
    from baseline_recall import BASELINE_SCORE_KEYS, score_baseline

    output = {key: 1 for key in BASELINE_SCORE_KEYS} | {"n_ground_truth": 2}
    assert [
        evaluation.name for evaluation in score_baseline(output=output)
    ] == BASELINE_SCORE_KEYS


def test_history_cost_column() -> None:
    """The ``variable cost`` column: summed api_cost_usd, or summed trace cost."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    from history import HEADER, fetch_runs, render_row

    def score(name, value):
        return SimpleNamespace(name=name, value=value)

    def page(data):
        return SimpleNamespace(data=data)

    scores_by_trace = {
        "t1": [score("search_recall", 0.5), score("api_cost_usd", 0.10)],
        "t2": [score("search_recall", 0.25), score("api_cost_usd", 0.20)],
        "t3": [score("search_recall", 0.5)],
        "t4": [score("search_recall", 0.5)],
    }
    items_by_run = {
        "baseline": [SimpleNamespace(trace_id="t1"), SimpleNamespace(trace_id="t2")],
        "pipeline": [SimpleNamespace(trace_id="t3"), SimpleNamespace(trace_id="t4")],
    }
    trace_cost = {"t3": 0.45, "t4": 0.55}
    trace_calls: list[str] = []

    runs = [
        SimpleNamespace(
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            name="baseline",
            metadata={},
        ),
        SimpleNamespace(
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            name="pipeline",
            metadata={},
        ),
    ]

    class _Trace:
        @staticmethod
        def get(trace_id):
            trace_calls.append(trace_id)
            return SimpleNamespace(total_cost=trace_cost.get(trace_id))

    class _Scores:
        @staticmethod
        def get_many(trace_id, limit=100):
            return page(scores_by_trace[trace_id])

    class _DatasetRunItems:
        @staticmethod
        def list(dataset_id, run_name, limit=100):
            return page(items_by_run[run_name])

    class _Datasets:
        @staticmethod
        def get(name):
            return SimpleNamespace(id="ds1")

        @staticmethod
        def get_runs(name, limit=100):
            return page(runs)

    client = SimpleNamespace(
        api=SimpleNamespace(
            datasets=_Datasets(),
            dataset_run_items=_DatasetRunItems(),
            scores=_Scores(),
            trace=_Trace(),
        )
    )

    rows = fetch_runs(client, "ds")
    by_name = {r["run"]: r for r in rows}

    baseline = by_name["baseline"]
    assert abs(baseline["cost"] - 0.30) < 1e-9
    assert baseline["cost_kind"] == "api"
    assert baseline["search_recall"] == 0.375
    assert "t1" not in trace_calls and "t2" not in trace_calls

    pipeline = by_name["pipeline"]
    assert pipeline["cost"] == 1.0
    assert pipeline["cost_kind"] == "llm"

    row_baseline = render_row(baseline)
    row_pipeline = render_row(pipeline)
    assert "$0.30 api" in row_baseline
    assert "$1.00 llm" in row_pipeline

    no_cost_row = dict(baseline)
    no_cost_row["cost"] = None
    assert render_row(no_cost_row).count("n/a") >= 1
    tiny = dict(baseline)
    tiny["cost"] = 0.002
    assert "$0.0020 api" in render_row(tiny)

    header_line = HEADER.splitlines()[0]
    assert header_line.count("|") == row_baseline.count("|")


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
    test_multi_round_depth_needs_screening()
    test_production_recall_scores()
    test_select_items()
    test_baseline_records_of()
    test_baseline_cutoffs()
    test_baseline_paging_semantic_scholar()
    test_baseline_paging_consensus()
    test_baseline_paging_openalex()
    test_baseline_retry()
    test_baseline_cache_round_trip()
    test_baseline_slice_and_cost()
    test_baseline_score_evaluator()
    test_history_cost_column()
    print("ok")
