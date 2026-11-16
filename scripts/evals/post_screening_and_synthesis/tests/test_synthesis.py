"""Offline checks for the synthesis coverage eval. No network, no database, no model calls.

Run: uv run --project backend python scripts/evals/post_screening_and_synthesis/tests/test_synthesis.py
"""

import importlib

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
score = importlib.import_module("02_run_evals").score


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


def test_score_two_denominators() -> None:
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
    # "a" is pushed, "b" is new, "c" is extracted on disk (real folder) but unpushed.
    on_disk = next(p for p in _ground_truth.GROUND_TRUTH_DIR.iterdir() if p.is_dir())
    rows = [{"Doc ID": "a"}, {"Doc ID": "b"}, {"Doc ID": on_disk.name}]
    assert pick_docs(rows, {"a"}, None) == [{"Doc ID": "b"}]
    assert pick_docs(rows, {"a"}, ["a", on_disk.name]) == [rows[0], rows[2]]


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
