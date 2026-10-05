"""Self-checks for the ground-truth half of the eval: scoring keys, title cleaning, dates,
the OpenAlex retry, CSV loading and upload items, the fetchers' parsing and the sample
selection. No network, no database.

Run: uv run --project backend python scripts/evals/search/tests/test_ground_truth.py
"""

import _bootstrap  # noqa: F401
from evals_search_utils import clean_review_title, months_earlier, normalize_doi


def test_normalize_doi() -> None:
    assert normalize_doi("https://doi.org/10.1234/AbC") == "10.1234/abc"
    assert normalize_doi("10.1234/AbC") == "10.1234/abc"
    assert normalize_doi(None) is None
    assert normalize_doi("") is None


def test_record_key() -> None:
    """The identity a document is scored on, DOI first, Overton id as fallback."""
    from evals_search_utils import record_key

    # A DOI always wins, whichever backend supplied the record.
    assert (
        record_key({"doi": "https://doi.org/10.1/AbC", "backend": "openalex"})
        == "10.1/abc"
    )
    assert (
        record_key({"doi": "10.1/a", "backend": "overton", "backend_record_id": "P1"})
        == "10.1/a"
    )
    # No DOI, from Overton: the policy document id keeps it scorable.
    assert record_key({"backend": "overton", "backend_record_id": "P9"}) == "overton:P9"
    # No DOI, from OpenAlex: nothing to match on.
    assert record_key({"backend": "openalex", "backend_record_id": "W1"}) is None
    assert record_key({}) is None
    assert record_key(None) is None


def test_ground_truth_keys_union() -> None:
    from evals_search_utils import GroundTruth

    gt = GroundTruth(dois={"10.1/a"}, source="url", overton_ids={"overton:P9"})
    assert gt.keys == {"10.1/a", "overton:P9"}
    # A DOI-mode ground truth has no Overton half, so keys == dois exactly.
    assert GroundTruth(dois={"10.1/a"}, source="doi").keys == {"10.1/a"}


def test_clean_review_title() -> None:
    assert (
        clean_review_title(
            "The effect of parental leave on parents' mental health: a systematic review"
        )
        == "The effect of parental leave on parents' mental health"
    )
    assert (
        clean_review_title(
            "Universal basic income and health - A Bibliometric Analysis"
        )
        == "Universal basic income and health"
    )
    assert (
        clean_review_title(
            "Effects of X on Y: a scoping review of randomized controlled trials"
        )
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

    import evals_search_utils

    def responses(*status_codes):
        codes = list(status_codes)
        return lambda url, **_: httpx.Response(
            codes.pop(0), request=httpx.Request("GET", url)
        )

    with patch("time.sleep"):
        # A 504 then a 200: the retry wins, the caller sees only the 200.
        with patch("httpx.get", responses(504, 200)):
            assert evals_search_utils.openalex_get("/works/W1").status_code == 200
        # A genuine 404 is not transient: return it at once, do not retry.
        with patch("httpx.get", responses(404, 200)):
            assert evals_search_utils.openalex_get("/works/W1").status_code == 404
        # Always 504: give up after 5 tries and hand back the last response.
        with patch("httpx.get", responses(504, 504, 504, 504, 504)):
            assert evals_search_utils.openalex_get("/works/W1").status_code == 504

        # A connection error that later clears is also retried.
        calls = {"n": 0}

        def flaky_get(url, **_):
            calls["n"] += 1
            if calls["n"] == 1:
                raise httpx.ConnectTimeout("boom")
            return httpx.Response(200, request=httpx.Request("GET", url))

        with patch("httpx.get", flaky_get):
            assert evals_search_utils.openalex_get("/works/W1").status_code == 200


def test_months_earlier() -> None:
    assert months_earlier("2023-01-01", 1) == "2022-12-01"  # year boundary
    assert (
        months_earlier("2023-03-31", 1) == "2023-02-28"
    )  # day-overflow clamp, non-leap
    assert (
        months_earlier("2024-03-31", 1) == "2024-02-29"
    )  # day-overflow clamp, leap year
    assert months_earlier("2023-06-15", 1) == "2023-05-15"  # ordinary case


def test_load_reviews_csv() -> None:
    """The gt_reviews.csv loader: what it accepts, skips, and rejects."""
    import tempfile
    from pathlib import Path

    from upload import load_reviews as _load_reviews

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
    assert (
        reviews[1].url == "https://example.org/r"
        and reviews[1].published_before == "2023-02-17"
    )

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


def test_load_references_and_items() -> None:
    """references.csv -> per-review recall targets -> Langfuse dataset items."""
    import tempfile
    from pathlib import Path

    from upload import ReviewSpec, build_items, load_references

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
        ReviewSpec(
            title="Review A: a systematic review",
            doi="10.1/r",
            published_before="2023-01-01",
        ),
        ReviewSpec(
            title="Review C", url="https://example.org/c", published_before="2023-01-01"
        ),
    ]
    items = build_items(reviews, references, "ds")
    # Review C has no references: skipped, not uploaded with an empty target.
    assert len(items) == 1
    item = items[0]
    assert item["id"].startswith("ds:") and len(item["id"]) == len("ds:") + 32
    assert item["input"] == {"intent": "Review A", "published_before": "2023-01-01"}
    assert item["expected_output"]["keys"] == ["10.1/a", "overton:P9"]
    assert item["metadata"]["n_target"] == 2 and item["metadata"]["n_unscorable"] == 1
    assert (
        item["metadata"]["source"] == "doi"
        and item["metadata"]["review_id"] == "10.1/r"
    )


def test_doi_if_valid() -> None:
    from fetch_helpers import doi_if_valid

    assert doi_if_valid("No DOI") is None
    assert doi_if_valid("") is None
    assert doi_if_valid(None) is None
    assert doi_if_valid("10.1002/CL2.1125") == "10.1002/cl2.1125"
    assert doi_if_valid("https://doi.org/10.1002/cl2.1125.") == "10.1002/cl2.1125"
    assert doi_if_valid("doi: 10.23846/EGM019") == "10.23846/egm019"


def test_clean_review_title_gap_maps() -> None:
    assert clean_review_title("Human rights: an evidence gap map") == "Human rights"
    assert clean_review_title(
        "Digital interventions for loneliness: An evidence and gap map"
    ) == ("Digital interventions for loneliness")
    assert clean_review_title("Big data: a systematic map") == "Big data"
    # A title with no review-type tail is untouched.
    assert clean_review_title("Diversion") == "Diversion"


def test_not_a_review_title() -> None:
    from fetch_helpers import NOT_A_REVIEW_TITLE_RE

    assert NOT_A_REVIEW_TITLE_RE.match("PROTOCOL: Effects of X on Y")
    assert NOT_A_REVIEW_TITLE_RE.match("Erratum to: Effects of X")
    assert not NOT_A_REVIEW_TITLE_RE.match("Effects of protocol training on nurses")


def test_write_ground_truth_round_trip() -> None:
    """The fetchers' CSVs load through the same loaders as the hand-made ones."""
    import tempfile
    from pathlib import Path

    from fetch_helpers import write_ground_truth
    from upload import load_references, load_reviews

    reviews = [
        {
            "title": "Cash transfers",
            "doi": "10.1/r",
            "url": "",
            "published_before": "2020-01-01",
            "exclude": "",
        }
    ]
    refs = [
        {
            "review_title": "Cash transfers",
            "ref_title": "A",
            "label": "content",
            "doi": "10.1/a",
            "overton_id": "",
            "url": "",
            "year": 2019,
            "ref_id": "W1",
        },
        {
            "review_title": "Cash transfers",
            "ref_title": "B",
            "label": "",
            "doi": "10.1/b",
            "overton_id": "",
            "url": "",
            "year": 2019,
            "ref_id": "W2",
        },
        {
            "review_title": "Cash transfers",
            "ref_title": "C",
            "label": "content",
            "doi": "",
            "overton_id": "",
            "url": "http://x",
            "year": "",
            "ref_id": "W3",
        },
    ]
    with tempfile.TemporaryDirectory() as tmp:
        rev_path, ref_path = write_ground_truth("t", reviews, refs, out_dir=Path(tmp))
        assert [r.doi for r in load_reviews(rev_path)] == ["10.1/r"]
        target = load_references(ref_path)["Cash transfers"]
        assert set(target["titles"]) == {
            "10.1/a"
        }  # only labelled content rows with a key count
        assert target["n_unscorable"] == 1  # C: content, but no DOI and no Overton id
    try:
        write_ground_truth(
            "t", reviews, [{**refs[0], "review_title": "Other"}], out_dir=Path(tmp)
        )
    except ValueError as exc:
        assert "Other" in str(exc)
    else:
        raise AssertionError("a reference naming an unknown review must be refused")


def test_get_3ie_map_rows() -> None:
    from getters.get_3ie import build_rows, map_rows

    data = {
        "interventions": [
            {
                "map_layout_group_id": 1,
                "map_layout_group_title": "Systems",
                "sub_levels": [
                    {
                        "map_layout_group_id": 11,
                        "map_layout_group_title": " Police  reform ",
                    },
                    {"map_layout_group_id": 12, "map_layout_group_title": "Courts"},
                ],
            },
            {"map_layout_group_id": 2, "map_layout_group_title": "Flat row"},
        ],
        "interventions_outcomes": {
            "11": {
                "a": {"bubbles": [{"records": [{"id": "s1"}, {"id": "s2"}]}]},
                "b": {"bubbles": [{"records": [{"id": "s2"}]}]},
            },
            "2": {"a": {"bubbles": [{"records": [{"id": 3}]}]}},
        },
        "project_records": {
            "s1": {
                "id": "s1",
                "title": "One",
                "doi": "10.1234/one",
                "year_of_publication": "2015",
                "url": "u1",
            },
            "s2": {
                "id": "s2",
                "title": "Two",
                "doi": "No DOI",
                "year_of_publication": "2019",
                "url": "u2",
            },
            "3": {
                "id": 3,
                "title": "Three",
                "doi": "",
                "year_of_publication": "",
                "url": "",
            },
        },
    }
    assert map_rows(data) == [
        ("11", "Police reform", {"s1", "s2"}),
        ("12", "Courts", set()),
        ("2", "Flat row", {"3"}),
    ]
    egm = {
        "title": "Rule of law: an evidence gap map",
        "url": "https://x/egm/rol",
        "year": "2020",
    }
    reviews, refs = build_rows(egm, data, min_studies=2)
    assert [
        (
            r["title"],
            r["level"],
            r["n_references"],
            r["n_with_doi"],
            r["published_before"],
        )
        for r in reviews
    ] == [
        ("Rule of law", "map", 3, 1, "2019-12-31"),
        ("Rule of law: Police reform", "intervention", 2, 1, "2019-12-31"),
    ]
    assert reviews[1]["url"] == "https://x/egm/rol#intervention=11"
    row_refs = [r for r in refs if r["review_title"] == "Rule of law: Police reform"]
    assert [(r["ref_id"], r["doi"], r["label"]) for r in row_refs] == [
        ("3ie:s1", "10.1234/one", "content"),
        ("3ie:s2", "", "content"),
    ]


def test_get_yef_strands() -> None:
    from getters.get_yef import MAP_SCOPE, build_rows, strands

    csv_data = {
        "rows": [
            [
                {
                    "id": 100,
                    "title": "Toolkit strand",
                    "parentId": None,
                    "isColumn": True,
                }
            ],
            [
                {"id": 101, "title": "Uncategorised", "parentId": 100},
                {"id": 102, "title": "Mentoring ", "parentId": 100},
                {"id": 103, "title": "CCTV", "parentId": 100},
            ],
            [
                {"id": 200, "title": "Outcomes", "parentId": None},
                {"id": 201, "title": "Violence", "parentId": 200},
            ],
        ]
    }
    names = strands(csv_data)
    assert names == {102: "Mentoring", 103: "CCTV"}
    items = [
        {
            "ItemId": 1,
            "Title": "M1",
            "DOI": "10.1234/m1",
            "Year": "2018",
            "URL": "",
            "Codes": [{"AttributeId": 102}, {"AttributeId": 201}],
        },
        {
            "ItemId": 2,
            "Title": "M2",
            "DOI": "",
            "Year": "2021",
            "URL": "http://m2",
            "Codes": [{"AttributeId": 102}],
        },
        {
            "ItemId": 3,
            "Title": "C1",
            "DOI": "",
            "Year": "",
            "URL": "",
            "Codes": [{"AttributeId": 103}],
        },
    ]
    reviews, refs = build_rows(items, names, min_studies=2)
    assert [
        (r["title"], r["level"], r["n_references"], r["published_before"])
        for r in reviews
    ] == [
        (MAP_SCOPE, "map", 3, "2021-12-31"),
        (f"{MAP_SCOPE}: Mentoring", "intervention", 2, "2021-12-31"),
    ]
    assert [r["ref_id"] for r in refs if r["review_title"].endswith("Mentoring")] == [
        "yef:1",
        "yef:2",
    ]


def test_get_sr4all_filter() -> None:
    from getters.get_sr4all import DEFAULT_FIELDS, wanted

    ok = {
        "field": "Psychology",
        "doi": "10.1/x",
        "research_questions": ["q"],
        "language": "en",
        "referenced_works_count": 40,
        "title": "X: a systematic review",
    }
    assert wanted(ok, set(DEFAULT_FIELDS), 30)
    assert not wanted({**ok, "field": "Medicine"}, set(DEFAULT_FIELDS), 30)
    assert not wanted({**ok, "research_questions": []}, set(DEFAULT_FIELDS), 30)
    assert not wanted({**ok, "referenced_works_count": 29}, set(DEFAULT_FIELDS), 30)
    assert not wanted({**ok, "title": "Protocol for X"}, set(DEFAULT_FIELDS), 30)
    assert not wanted({**ok, "language": "de"}, set(DEFAULT_FIELDS), 30)


def test_get_campbell_select() -> None:
    from getters.get_campbell import select_reviews

    works = [
        {
            "id": "W1",
            "title": "Hot spots policing",
            "doi": "10.1/1",
            "publication_date": "2019-05-01",
            "referenced_works_count": 100,
        },
        {
            "id": "W2",
            "title": "PROTOCOL: Hot spots policing",
            "doi": "10.1/2",
            "publication_date": "2018-01-01",
            "referenced_works_count": 100,
        },
        {
            "id": "W3",
            "title": "Hot spots policing",
            "doi": "10.1/3",
            "publication_date": "2023-01-01",
            "referenced_works_count": 150,
        },  # update: same title
        {
            "id": "W4",
            "title": "Short one",
            "doi": "10.1/4",
            "publication_date": "2019-01-01",
            "referenced_works_count": 10,
        },
        {
            "id": "W5",
            "title": "No DOI",
            "doi": None,
            "publication_date": "2019-01-01",
            "referenced_works_count": 100,
        },
    ]
    assert [w["id"] for w in select_reviews(works, min_refs=30)] == ["W1"]


def test_select_ground_truth() -> None:
    """The sample picker: the quality check, the topic rotation, labels and the 10-in-100 subset."""
    import csv
    import tempfile
    from pathlib import Path

    from upload import load_references, load_reviews
    from select_sample import mini_sample, pick, rejection, select, topic, write_sample

    def review(
        title,
        n_refs,
        n_doi,
        cutoff="2020-01-01",
        level="review",
        dup=False,
        dataset="campbell",
    ):
        return {
            "title": title,
            "doi": "10.1/x",
            "url": "",
            "published_before": cutoff,
            "exclude": "",
            "dataset": dataset,
            "review_id": title,
            "level": level,
            "n_references": n_refs,
            "n_with_doi": n_doi,
            "research_questions": "",
            "_n_refs": n_refs,
            "_n_doi": n_doi,
            "_dup_title": dup,
        }

    today = "2026-10-05"
    assert rejection(review("ok", 100, 90), today) is None
    assert "whole gap map" in rejection(review("m", 100, 90, level="map"), today)
    assert "twice" in rejection(review("d", 100, 90, dup=True), today)
    for bad in (
        "X: A Systematic Review Protocol",
        "Updated protocol: Y",
        "Editorial: Z",
        "Searching: a guide to W",
    ):
        assert "not a review" in rejection(review(bad, 100, 90), today)
    assert (
        rejection(
            review(
                "Guidance for engagement in health guideline development: A scoping review",
                100,
                90,
            ),
            today,
        )
        is None
    )
    assert "fewer than 20" in rejection(review("few", 30, 19), today)
    assert "more than 300" in rejection(review("big", 301, 300), today)
    assert "under 70%" in rejection(review("grey", 100, 69), today)
    assert (
        rejection(review("yef grey", 100, 51, dataset="yef"), today) is None
    )  # YEF floor is 50%
    assert "before 2010" in rejection(
        review("old", 100, 90, cutoff="2009-12-31"), today
    )
    assert "not in the past" in rejection(
        review("living", 100, 90, cutoff="2026-12-31"), today
    )
    # Topics rotate: three mental-health reviews and one school review, quota 2 -> one of each.
    rows = [
        review("Depression therapy A", 100, 100),
        review("Anxiety B", 100, 99),
        review("Suicide C", 100, 98),
        review("School reading D", 100, 80),
    ]
    picked = pick(rows, 2)
    assert {topic(r["title"]) for r in picked} == {"mental health", "education"}
    assert (
        picked[0]["title"] == "School reading D"
        or picked[1]["title"] == "School reading D"
    )
    # Gap-map rows rotate across maps (the title prefix), best DOI share first.
    maps = [
        review("Food: A", 50, 50, dataset="3ie"),
        review("Food: B", 50, 49, dataset="3ie"),
        review("Energy: C", 50, 40, dataset="3ie"),
    ]
    assert [r["title"] for r in pick(maps, 2)] == ["Energy: C", "Food: A"]
    # End to end on tiny files: labels become content, the loaders accept both samples,
    # and the small sample is the head of the big one.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        import select_sample as sel

        for name in sel.QUOTAS:
            titles = [f"{name} review {i}: topic {i}" for i in range(4)]
            with (root / f"{name}_reviews.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sel.REVIEW_COLUMNS)
                writer.writeheader()
                for t in titles:
                    writer.writerow(
                        {
                            "title": t,
                            "doi": "",
                            "url": f"https://x/{t}",
                            "published_before": "2021-12-31",
                            "level": "intervention",
                            "dataset": name,
                            "review_id": t,
                        }
                    )
            with (root / f"{name}_references.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=sel.REFERENCE_COLUMNS)
                writer.writeheader()
                for t in titles:
                    for j in range(25):
                        writer.writerow(
                            {
                                "review_title": t,
                                "ref_title": f"ref {j}",
                                "label": "",
                                "doi": f"10.1/{t}-{j}",
                            }
                        )
        picks, reasons = select(root, today)
        assert all(len(rows) == 4 for rows in picks.values())
        assert all(dict(c) == {"passing": 4} for c in reasons.values())
        chosen = tuple(
            rows[i]["title"]
            for n, rows in picks.items()
            for i in range({"yef": 1}.get(n, 3))
        )
        small = mini_sample(picks, chosen)
        try:
            mini_sample(picks, ("not in the hundred",))
            raise AssertionError("an unknown title must be refused")
        except ValueError:
            pass
        rv, rf = write_sample("sample_100", picks, root)
        rv10, rf10 = write_sample("sample_10", small, root)
        assert len(load_reviews(rv)) == 16 and len(load_reviews(rv10)) == 10
        targets = load_references(rf)
        assert len(targets) == 16 and all(
            len(t["titles"]) == 25 for t in targets.values()
        )
        big = {r.title for r in load_reviews(rv)}
        assert {r.title for r in load_reviews(rv10)} <= big
        with rv.open() as handle:
            labelled = {
                row["dataset"]: row["target_labelled"] for row in csv.DictReader(handle)
            }
        assert labelled == {
            "campbell": "no",
            "3ie": "yes",
            "sr4all": "no",
            "yef": "yes",
        }


if __name__ == "__main__":
    test_normalize_doi()
    test_record_key()
    test_ground_truth_keys_union()
    test_clean_review_title()
    test_openalex_get_retries()
    test_months_earlier()
    test_load_reviews_csv()
    test_load_references_and_items()
    test_doi_if_valid()
    test_clean_review_title_gap_maps()
    test_not_a_review_title()
    test_write_ground_truth_round_trip()
    test_get_3ie_map_rows()
    test_get_yef_strands()
    test_get_sr4all_filter()
    test_get_campbell_select()
    test_select_ground_truth()
    print("ok")
