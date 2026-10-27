"""Offline checks for the synthesis coverage eval. No network, no database, no model calls.

Run: uv run --project backend python scripts/evals/post_screening_and_synthesis/tests/test_synthesis.py
"""

import _bootstrap  # noqa: F401
from utils import load_test_set, mark_links, norm_title
from run_synthesis import score


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
        "4": "misrepresented",
    }
    s = score(facts, verdicts, ingested_labels={"1", "2"})
    assert s["n_facts"] == 4 and s["n_ingested"] == 2
    assert s["coverage_all"] == 0.5  # 2 fully of 4
    assert s["coverage_ingested"] == 0.5  # fact 1 fully, fact 4 misrepresented
    assert s["n_fully_represented"] == 2 and s["n_misrepresented"] == 1
    assert s["n_uncertain"] == 0
    empty = score([], {}, set())
    assert empty["coverage_all"] == 0.0 and empty["coverage_ingested"] == 0.0


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


def test_load_test_set_filters_and_rejects_unknown() -> None:
    assert len(load_test_set()) == 19
    assert [r["Doc ID"] for r in load_test_set(["16", "5"])] == ["5", "16"]
    try:
        load_test_set(["99"])
    except ValueError as exc:
        assert "99" in str(exc)
    else:
        raise AssertionError("unknown Doc ID should fail")


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok {name}")
