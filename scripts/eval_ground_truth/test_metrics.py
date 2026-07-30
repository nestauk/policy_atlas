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


if __name__ == "__main__":
    test_normalize_doi()
    test_recall()
    test_partition_screened()
    test_clean_review_title()
    test_months_earlier()
    print("ok")
