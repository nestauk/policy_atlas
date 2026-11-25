"""Offline checks for the synthesis coverage eval. No network, no database, no model calls.

Run: uv run --project backend python scripts/evals/post_screening_and_synthesis/tests/test_synthesis.py
"""

import importlib
import json
import logging
import os
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401
from utils import filter_test_set, mark_links, norm_title

# The scripts are numbered, so their names are not valid import statements.
_ground_truth = importlib.import_module("00_update_ground_truth")
FACT_FIELDS, KeyPoint, flatten_key_points = (
    _ground_truth.FACT_FIELDS,
    _ground_truth.KeyPoint,
    _ground_truth.flatten_key_points,
)
pick_docs = _ground_truth.pick_docs
identify_ref, load_cached_ref = (
    _ground_truth.identify_ref,
    _ground_truth.load_cached_ref,
)
score = importlib.import_module("02_run_evals").score

# The Overton script reads its API key on import. These checks make no request.
os.environ.setdefault("OVERTON_API_KEY", "unused")
_overton = importlib.import_module("determine_which_refs_are_in_overton")
normalise_url, is_url_match = _overton.normalise_url, _overton.is_url_match


def test_flatten_key_points_numbers_facts_across_points() -> None:
    points = [
        KeyPoint(point="P1", ref_labels=["1", "2"]),
        KeyPoint(point="P2", ref_labels=["3"]),
    ]
    rows = flatten_key_points(points, [["a", "b"], ["c"]])
    assert [r["fact_id"] for r in rows] == [1, 2, 3]
    assert [r["point_id"] for r in rows] == [1, 1, 2]
    assert [r["statement"] for r in rows] == ["a", "b", "c"]
    assert rows[0]["ref_labels"] == "1|2" and rows[2]["ref_labels"] == "3"
    assert rows[1]["point"] == "P1" and all(r["keep"] == "y" for r in rows)
    assert set(rows[0]) == set(FACT_FIELDS)
    assert flatten_key_points([], []) == []
    try:
        flatten_key_points(points, [["a"]])
    except ValueError:
        pass
    else:
        raise AssertionError("one facts list per point is required")


def test_score_three_denominators() -> None:
    facts = [
        {"fact_id": "1", "ref_labels": "1|2"},
        {"fact_id": "2", "ref_labels": "3"},
        {"fact_id": "3", "ref_labels": "4"},
        {"fact_id": "4", "ref_labels": "2"},
    ]
    verdicts = {
        "1": "fully_represented",
        "2": "fully_represented",
        "3": "not_represented",
        "4": "partially_represented",
    }
    s = score(facts, verdicts, ingested_labels={"1", "2"})
    assert s["n_facts"] == 4 and s["n_ingested"] == 2
    assert s["coverage_all"] == 0.5  # 2 fully of 4
    assert s["coverage_ingested"] == 0.5  # fact 1 fully, fact 4 partially
    assert s["coverage_all_lenient"] == 0.75  # facts 1, 2, 4 of 4
    assert s["coverage_ingested_lenient"] == 1.0  # facts 1 and 4
    # Fact 1 cites labels 1 and 2. With only label 2 ingested it still counts for
    # the at-least-one denominator, but not for the every-reference denominator.
    partial = score(facts, verdicts, ingested_labels={"2"})
    assert partial["n_ingested"] == 2 and partial["n_all_refs_ingested"] == 1
    assert partial["coverage_ingested"] == 0.5
    assert partial["coverage_all_refs_ingested"] == 0.0  # only fact 4, partially
    assert partial["coverage_all_refs_ingested_lenient"] == 1.0
    # A fact with no reference is in neither subset; an empty subset scores None.
    none = score([{"fact_id": "1", "ref_labels": ""}], verdicts, {"1"})
    assert none["n_all_refs_ingested"] == 0
    assert none["coverage_all_refs_ingested"] is None
    assert none["coverage_all_refs_ingested_lenient"] is None
    assert s["n_fully_represented"] == 2 and s["n_partially_represented"] == 1
    assert s["n_misrepresented"] == 0 and s["n_uncertain"] == 0
    empty = score([], {}, set())
    assert empty["coverage_all"] == 0.0 and empty["coverage_ingested"] == 0.0
    assert empty["coverage_all_lenient"] == 0.0


def test_mark_links_numbers_external_links_only() -> None:
    html = (
        '<p>See <a href="https://example.org/a">a <b>study</b>&nbsp;here</a> and '
        '<a href="https://post.parliament.uk/x">site</a> and '
        '<a href="https://example.org/b">another</a>.</p>'
    )
    marked, refs = mark_links(html)
    assert refs == [
        ("a study here", "https://example.org/a"),
        ("another", "https://example.org/b"),
    ]
    assert "a <b>study</b>&nbsp;here [1]" in marked and "another [2]" in marked
    assert (
        'href="https://post.parliament.uk/x">site</a>' in marked
    )  # untouched, unnumbered


def test_norm_title() -> None:
    assert norm_title("Résumé: a Review!") == "resume a review"
    assert norm_title(None) == ""


def test_normalise_url_ignores_scheme_www_slash_and_query() -> None:
    assert (
        normalise_url("https://www.unicef.org/a/b/")
        == normalise_url("http://UNICEF.org/a/b?x=1#y")
        == "unicef.org/a/b"
    )
    assert normalise_url("https://unicef.org/a/c") != normalise_url(
        "https://unicef.org/a/b"
    )
    assert normalise_url(None) == ""


def test_is_url_match_accepts_same_page_and_parent_page_only() -> None:
    landing = "https://www.gov.uk/government/publications/ai-in-education"
    assert is_url_match(
        landing + "/", "http://gov.uk/government/publications/ai-in-education"
    )
    assert is_url_match(landing + "/the-html-attachment", landing)
    # Not a parent: a sibling with the same prefix, a child, and a host with no path.
    assert not is_url_match(landing + "-module-2", landing)
    assert not is_url_match(landing, landing + "/the-html-attachment")
    assert not is_url_match(landing, "https://www.gov.uk/")
    assert is_url_match("https://www.heathrow.com/", "https://heathrow.com")
    # A candidate with no URL must not match a reference with no URL.
    assert not is_url_match("", None)


def test_filter_test_set_keeps_sheet_order_and_rejects_unknown() -> None:
    rows = [{"Doc ID": "a"}, {"Doc ID": "b"}, {"Doc ID": "c"}]
    assert filter_test_set(rows, None) == rows
    assert [r["Doc ID"] for r in filter_test_set(rows, ["c", "a"])] == ["a", "c"]
    try:
        filter_test_set(rows, ["no_such_briefing"])
    except ValueError as exc:
        assert "no_such_briefing" in str(exc)
    else:
        raise AssertionError("unknown Doc ID should fail")


def test_pick_docs_new_in_sheet_unless_already_on_disk() -> None:
    # "a" is pushed, "b" is new, "c" is extracted on disk but unpushed.
    rows = [{"Doc ID": "a"}, {"Doc ID": "b"}, {"Doc ID": "c"}]
    real_dir = _ground_truth.GROUND_TRUTH_DIR
    # ground_truth/ is not in git (CI has none), so the test makes its own folder.
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "c").mkdir()
        (Path(tmp) / "c" / "references.csv").touch()
        _ground_truth.GROUND_TRUTH_DIR = Path(tmp)
        try:
            assert pick_docs(rows, {"a"}, None) == [{"Doc ID": "b"}]
            assert pick_docs(rows, {"a"}, ["a", "c"]) == [rows[0], rows[2]]
        finally:
            _ground_truth.GROUND_TRUTH_DIR = real_dir


def test_load_cached_ref_only_for_the_same_reference() -> None:
    ref = {"label": "12", "title": "Noise & Health.", "doi": "10.1/X", "url": "u"}
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "12.json"
        assert load_cached_ref(path, ref) is None  # nothing cached yet
        record = {"label": "12", "status": "dropped", "ref": identify_ref(ref)}
        path.write_text(json.dumps(record), encoding="utf-8")
        assert load_cached_ref(path, ref) == record
        # A change of case or punctuation in the title is the same reference.
        assert load_cached_ref(path, {**ref, "title": "noise &  health"}) == record
        # A change of words is not: the known cost is one fetch too many.
        assert load_cached_ref(path, {**ref, "title": "noise and health"}) is None
        # Label 12 now has a corrected URL, or is another paper.
        assert load_cached_ref(path, {**ref, "url": "v"}) is None
        assert load_cached_ref(path, {**ref, "doi": "10.1/y"}) is None
        # A record written before identities were stored cannot be trusted.
        path.write_text(json.dumps({"label": "12"}), encoding="utf-8")
        assert load_cached_ref(path, ref) is None


if __name__ == "__main__":
    logging.disable(logging.WARNING)  # the stale-cache warnings are expected here
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
