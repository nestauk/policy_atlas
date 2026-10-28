"""The verdict rule (task 054, C36): simplified BEAM, every branch, Q and the near flag."""

from typing import Any

import pytest

from policy_atlas.theory_of_change.evidence.grade import (
    DocAppraisal,
    Judgement,
    link_verdict,
    lowest,
    quality,
    rule_text,
)


def _verdict(rows: list[tuple[str, int, int]]) -> Any:
    """``(support, Q, R)`` per document; Q comes from an appraisal score that maps to it."""
    score = {1: 2, 2: 3, 3: 5}
    judgements = [Judgement(f"d{i}", support, r) for i, (support, _, r) in enumerate(rows)]
    appraisals = {f"d{i}": DocAppraisal(score[q]) for i, (_, q, _) in enumerate(rows)}
    return link_verdict(judgements, appraisals)


def test_the_beam_worked_example() -> None:
    # BEAM doc §4: mixed Q2 R3, weak Q2 R1, refutes Q2 R2.
    result = _verdict([("mixed", 2, 3), ("weak", 2, 1), ("refutes", 2, 2)])
    assert round(result.total_weight, 2) == 1.33
    assert result.mean_support == -0.5
    assert round(result.refute_share, 2) == 0.33
    assert result.verdict == "not_confident"
    assert result.near_threshold
    assert result.n_documents == 3


@pytest.mark.parametrize(
    ("rows", "verdict", "near"),
    [
        # Nothing found, or only not_about: too little evidence.
        ([], "not_sure_insufficient", False),
        ([("not_about", 3, 0)], "not_sure_insufficient", False),
        # One strong, partly relevant study: W 6/9 < 1, and 0.33 away from 1, so not near.
        ([("strong", 3, 2)], "not_sure_insufficient", False),
        # W 8/9 is within 0.25 of 1: near.
        ([("strong", 2, 2), ("strong", 2, 2)], "not_sure_insufficient", True),
        # Two strong, fully relevant studies: Confident, far from every threshold.
        ([("strong", 3, 3), ("strong", 3, 3)], "confident", False),
        # Supportive on average (S̄ 0.67) but a third of the weight against: mixed.
        ([("strong", 3, 3), ("strong", 3, 3), ("refutes", 3, 3)], "not_sure_mixed", False),
        # Clearly against.
        ([("refutes", 3, 3), ("refutes", 3, 3)], "not_confident", False),
        # S̄ exactly 1.0 with W 2: Confident, and on the threshold.
        ([("strong", 3, 3), ("mixed", 3, 3)], "confident", True),
    ],
)
def test_each_verdict_branch(rows: Any, verdict: str, near: bool) -> None:
    result = _verdict(rows)
    assert (result.verdict, result.near_threshold) == (verdict, near)


@pytest.mark.parametrize(
    ("appraisal", "robust", "q"),
    [
        (None, None, 1),
        (DocAppraisal(None), None, 1),
        (DocAppraisal(5), None, 3),
        (DocAppraisal(4), None, 3),
        (DocAppraisal(3), None, 2),
        (DocAppraisal(2), None, 1),
        (DocAppraisal(1), None, 1),
        # A web page off the trusted list counts 1, whatever its score.
        (DocAppraisal(5, web=True), None, 1),
        (DocAppraisal(5, web=True, trusted=True), None, 3),
        # A modelling study: 2 when the judge called it robust, else 1.
        (DocAppraisal(5, modelling=True), True, 2),
        (DocAppraisal(5, modelling=True), False, 1),
        (DocAppraisal(5, modelling=True), None, 1),
    ],
)
def test_quality_mapping(appraisal: Any, robust: Any, q: int) -> None:
    assert quality(appraisal, robust) == q


def test_the_lowest_verdict_is_the_theory_confidence() -> None:
    assert lowest(["confident", "not_sure_mixed", "not_sure_insufficient"]) == (
        "not_sure_insufficient"
    )
    assert lowest(["not_sure_mixed", "not_confident"]) == "not_confident"
    assert lowest([]) is None


def test_the_rule_text_names_every_verdict() -> None:
    labels = [label for label, _ in rule_text()]
    assert labels[:4] == [
        "Confident",
        "Not sure: mixed",
        "Not sure: too little evidence",
        "Not confident: evidence against",
    ]
