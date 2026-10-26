"""The grade table (task 054, C4): every rule row, both questions, the caps."""

from typing import Any

import pytest

from policy_atlas.theory_of_change.evidence.grade import (
    DocAppraisal,
    Judgement,
    grade,
    lower,
    rule_text,
)

S, C, N = "supports", "challenges", "not_about"


def _run(rows: Any, appraisals: Any, question: Any = "elsewhere") -> Any:
    judgements = [
        Judgement(
            document_id=doc,
            stance_elsewhere=stance if question == "elsewhere" else N,
            stance_here=stance if question == "here" else N,
            robust_model=robust,
        )
        for doc, stance, robust in rows
    ]
    return grade(judgements, appraisals, question)


@pytest.mark.parametrize("question", ["elsewhere", "here"])
@pytest.mark.parametrize(
    ("rows", "appraisals", "expected", "against"),
    [
        # no document speaks
        ([], {}, "none", 0),
        ([("a", N, None)], {"a": DocAppraisal(5)}, "none", 0),
        # strong: two at 4+, no challenge at 4+
        (
            [("a", S, None), ("b", S, None)],
            {"a": DocAppraisal(5), "b": DocAppraisal(4)},
            "strong",
            0,
        ),
        # one at 4+ is only medium
        ([("a", S, None)], {"a": DocAppraisal(5)}, "medium", 0),
        # a strong challenge blocks strong; equal scores still medium
        (
            [("a", S, None), ("b", S, None), ("c", C, None)],
            {"a": DocAppraisal(5), "b": DocAppraisal(4), "c": DocAppraisal(4)},
            "medium",
            1,
        ),
        # a weaker challenge keeps strong, but raises the flag
        (
            [("a", S, None), ("b", S, None), ("c", C, None)],
            {"a": DocAppraisal(4), "b": DocAppraisal(4), "c": DocAppraisal(2)},
            "strong",
            1,
        ),
        # medium boundary: support at 3
        ([("a", S, None)], {"a": DocAppraisal(3)}, "medium", 0),
        # challenge scored higher than the best support: weak
        ([("a", S, None), ("b", C, None)], {"a": DocAppraisal(3), "b": DocAppraisal(4)}, "weak", 1),
        # only low support: weak
        ([("a", S, None)], {"a": DocAppraisal(2)}, "weak", 0),
        # only challenge: weak with the flag
        ([("a", C, None)], {"a": DocAppraisal(5)}, "weak", 1),
        # web pages never raise above weak
        (
            [("a", S, None), ("b", S, None)],
            {"a": DocAppraisal(5, web=True), "b": DocAppraisal(5, web=True)},
            "weak",
            0,
        ),
        # unscored documents (policy documents) count toward weak only
        ([("a", S, None)], {"a": DocAppraisal(None)}, "weak", 0),
        # a document with no appraisal row counts toward weak only
        ([("a", S, None)], {}, "weak", 0),
        # robust model counts as 3: medium
        ([("a", S, True)], {"a": DocAppraisal(2, modelling=True)}, "medium", 0),
        # a non-robust model stays at its score: weak
        ([("a", S, False)], {"a": DocAppraisal(2, modelling=True)}, "weak", 0),
        # robust models never make strong
        (
            [("a", S, True), ("b", S, True)],
            {"a": DocAppraisal(2, modelling=True), "b": DocAppraisal(2, modelling=True)},
            "medium",
            0,
        ),
    ],
)
def test_grade_rule_rows(
    question: Any, rows: Any, appraisals: Any, expected: Any, against: Any
) -> None:
    result = _run(rows, appraisals, question)
    assert result.grade == expected
    assert result.against == against


def test_each_question_counts_only_its_own_stance() -> None:
    judgements = [Judgement("a", S, N), Judgement("b", S, C)]
    appraisals = {"a": DocAppraisal(5), "b": DocAppraisal(5)}
    assert grade(judgements, appraisals, "elsewhere").grade == "strong"
    here = grade(judgements, appraisals, "here")
    assert (here.grade, here.against) == ("weak", 1)


def test_lower_and_rule_text() -> None:
    assert lower("strong", "weak") == "weak"
    assert lower("none", "medium") == "none"
    assert [label for label, _ in rule_text()] == ["Strong", "Medium", "Weak", "No evidence found"]
