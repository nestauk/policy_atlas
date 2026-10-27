"""The evidence grade of one link on one question (task 054, C4; ADR 0042).

This is the only place a grade is decided. It is computed on read, never
stored, so it cannot drift from the judgements it is made from, and the rule can
be tuned from the evals by changing the constants below.

The rule, once per question (*worked elsewhere*, *holds here*):

- **Strong**: two or more supporting documents at appraisal score 4 or 5, and
  no challenging document at 4 or 5.
- **Medium**: not strong; at least one supporting document at score 3 or above;
  no challenging document scored higher than the best supporting one.
- **Weak**: some documents speak to the link, but neither rule holds.
- **No evidence found**: no judged document speaks to the link.

Web pages and documents without an appraisal score count toward *weak* and the
evidence-against flag, never toward *medium* or *strong*. A modelling study the
judge marked robust counts as score 3: it can support *medium*, never *strong*.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

Grade = Literal["strong", "medium", "weak", "none"]
Question = Literal["elsewhere", "here"]

#: Appraisal scores that count toward a strong and a medium grade.
STRONG_SCORE = 4
MEDIUM_SCORE = 3
#: Supporting documents at the strong score a strong grade needs.
STRONG_MIN_SUPPORTS = 2
#: The score a robust modelling study counts as (W15): medium, never strong.
ROBUST_MODEL_SCORE = 3

#: Low to high; the canvas colours a link by the lower of its two grades.
GRADE_ORDER: tuple[Grade, ...] = ("none", "weak", "medium", "strong")

GRADE_LABELS: dict[Grade, str] = {
    "strong": "Strong",
    "medium": "Medium",
    "weak": "Weak",
    "none": "No evidence found",
}


@dataclass(frozen=True)
class DocAppraisal:
    """What the grade needs to know about one document.

    Attributes:
        score: The shared appraisal score (1 to 5), or ``None`` when the
            document has none.
        web: Whether the document is a frozen web page.
        modelling: Whether classify marked it a modelling study.
    """

    score: int | None
    web: bool = False
    modelling: bool = False


@dataclass(frozen=True)
class Judgement:
    """One judgement row, as far as the grade reads it.

    Attributes:
        document_id: The judged document (task source snapshot id).
        stance_elsewhere: ``supports`` · ``challenges`` · ``not_about``.
        stance_here: The same, for *holds here*.
        robust_model: The judge's robust-model answer, or ``None``.
    """

    document_id: str
    stance_elsewhere: str
    stance_here: str
    robust_model: bool | None = None


@dataclass(frozen=True)
class GradeResult:
    """One question's grade.

    Attributes:
        grade: The grade.
        against: How many documents challenge the link (the flag shows when > 0).
        supports: How many documents support it.
    """

    grade: Grade
    against: int
    supports: int


def counted_score(judgement: Judgement, appraisal: DocAppraisal | None) -> int:
    """The score a document counts with toward medium and strong; 0 = never."""
    if appraisal is None or appraisal.web or appraisal.score is None:
        return 0
    if appraisal.modelling and judgement.robust_model:
        return ROBUST_MODEL_SCORE
    return appraisal.score


def grade(
    judgements: Iterable[Judgement],
    appraisals: Mapping[str, DocAppraisal],
    question: Question,
) -> GradeResult:
    """Grade one link on one question.

    Args:
        judgements: The link's judgements whose item hash equals its counted
            hash (the caller filters; C19).
        appraisals: Document id → its appraisal.
        question: ``elsewhere`` or ``here``.

    Returns:
        The grade, with the support and challenge counts.
    """
    supports: list[int] = []
    challenges: list[int] = []
    for judgement in judgements:
        stance = judgement.stance_elsewhere if question == "elsewhere" else judgement.stance_here
        score = counted_score(judgement, appraisals.get(judgement.document_id))
        if stance == "supports":
            supports.append(score)
        elif stance == "challenges":
            challenges.append(score)
    if not supports and not challenges:
        return GradeResult(grade="none", against=0, supports=0)
    best_support = max(supports, default=0)
    best_challenge = max(challenges, default=0)
    if (
        sum(1 for score in supports if score >= STRONG_SCORE) >= STRONG_MIN_SUPPORTS
        and best_challenge < STRONG_SCORE
    ):
        result: Grade = "strong"
    elif best_support >= MEDIUM_SCORE and best_challenge <= best_support:
        result = "medium"
    else:
        result = "weak"
    return GradeResult(grade=result, against=len(challenges), supports=len(supports))


def lower(a: Grade, b: Grade) -> Grade:
    """Return the lower of two grades (the canvas colour of a link)."""
    return a if GRADE_ORDER.index(a) <= GRADE_ORDER.index(b) else b


def rule_text() -> list[tuple[str, str]]:
    """The grade rule as the reading guide shows it, from the same constants.

    Returns:
        ``(label, rule)`` pairs, strongest first.
    """
    return [
        (
            GRADE_LABELS["strong"],
            f"At least {STRONG_MIN_SUPPORTS} supporting studies of the strongest designs "
            f"(appraisal score {STRONG_SCORE} or 5: systematic reviews, trials, "
            f"quasi-experiments), and none of those designs against.",
        ),
        (
            GRADE_LABELS["medium"],
            f"At least one supporting study scored {MEDIUM_SCORE} or above (a robust "
            "model counts here), and nothing against it scored higher.",
        ),
        (
            GRADE_LABELS["weak"],
            "Some documents speak to the step, but only weaker designs, web pages or "
            "policy documents support it, or the evidence against outweighs it.",
        ),
        (
            GRADE_LABELS["none"],
            "The search ran, and no document read speaks to the step.",
        ),
    ]
