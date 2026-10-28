"""The evidence verdict of one link: simplified BEAM (task 054, C36; ADR 0042).

This is the only place a verdict is decided. It is computed on read, never
stored, so it cannot drift from the judgements it is made from, and the rule can
be calibrated from the evals by changing the constants below.

Each judged document gets a weight from two scores, each 0 to 3:

- **Quality Q**, from the shared appraisal score (5 or 4 → 3, 3 → 2, 2 or 1 → 1,
  unscored → 1). A web page from a publisher not on the trusted list
  (``trusted_publishers.toml``, C23) → 1. A modelling study (classify says so)
  → 2 when the judge called it robust, else 1.
- **Relevance R**, from the judge: how well the finding carries over to this
  population and place.

Weight = Q × R ÷ 9, so one perfect document weighs 1. The judge's *support*
counts strong +2, weak +1, mixed 0, refutes −2; *not about* is ignored. Per link:

- W, the total weight; S̄, the weight-averaged support (−2 to +2); and R%, the
  share of the weight that refutes.
- **Not sure: too little evidence** when W < 1; else **Confident** when
  S̄ ≥ 1 and R% < 15%; else **Not confident: evidence against** when S̄ ≤ −0.5;
  else **Not sure: mixed**.
- **Close to the threshold** when S̄ is within 0.2 of a support threshold that
  applies, or W is within 0.25 of 1: one more document could change the verdict.

The theory's confidence is the lowest verdict among its critical links
(BEAM §3.3).
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

Support = Literal["strong", "weak", "mixed", "refutes", "not_about"]
Verdict = Literal["confident", "not_sure_mixed", "not_sure_insufficient", "not_confident"]

#: The value of each support in the weighted average (BEAM Table 1).
SUPPORT_VALUE: dict[str, int] = {"strong": 2, "weak": 1, "mixed": 0, "refutes": -2}
#: Q × R of one perfect document: the weight divisor.
PERFECT = 9

# The verdict thresholds (BEAM §3.2), to calibrate from the evals.
#: Below this total weight there is too little evidence.
MIN_WEIGHT = 1.0
#: At or above this average support (and little refuting) the verdict is Confident.
CONFIDENT_SUPPORT = 1.0
#: Confident needs less than this share of the weight on refutes.
MAX_REFUTE_SHARE = 0.15
#: At or below this average support the verdict is Not confident.
AGAINST_SUPPORT = -0.5
#: How close to a threshold counts as close (average support, total weight).
NEAR_SUPPORT = 0.2
NEAR_WEIGHT = 0.25

#: Low to high: the theory's confidence is the lowest among its critical links.
VERDICT_ORDER: tuple[Verdict, ...] = (
    "not_confident",
    "not_sure_insufficient",
    "not_sure_mixed",
    "confident",
)

VERDICT_LABELS: dict[Verdict, str] = {
    "confident": "Confident",
    "not_sure_mixed": "Not sure: mixed",
    "not_sure_insufficient": "Not sure: too little evidence",
    "not_confident": "Not confident: evidence against",
}


@dataclass(frozen=True)
class DocAppraisal:
    """What the grade needs to know about one document.

    Attributes:
        score: The shared appraisal score (1 to 5), or ``None`` when the
            document has none.
        web: Whether the document is a frozen web page.
        modelling: Whether classify marked it a modelling study.
        trusted: Whether a web page's publisher is on the trusted list (C23).
    """

    score: int | None
    web: bool = False
    modelling: bool = False
    trusted: bool = False


@cache
def _trusted_hosts() -> tuple[str, ...]:
    path = Path(__file__).with_name("trusted_publishers.toml")
    return tuple(tomllib.loads(path.read_text())["hosts"])


def trusted_publisher(url: str | None) -> bool:
    """Whether a URL's host is on the trusted publisher list, or under one (C23).

    Args:
        url: The document's address.

    Returns:
        True for ``gov.uk`` and ``www.ons.gov.uk`` alike when ``gov.uk`` is listed.
    """
    host = (urlparse(url or "").hostname or "").lower().removesuffix(".")
    return any(host == h or host.endswith("." + h) for h in _trusted_hosts())


@dataclass(frozen=True)
class Judgement:
    """One judgement row, as far as the verdict reads it.

    Attributes:
        document_id: The judged document (task source snapshot id).
        support: ``strong`` · ``weak`` · ``mixed`` · ``refutes`` · ``not_about``.
        relevance: The judge's relevance, 0 to 3.
        robust_model: The judge's robust-model answer, or ``None``.
    """

    document_id: str
    support: str
    relevance: int
    robust_model: bool | None = None


@dataclass(frozen=True)
class LinkVerdict:
    """One link's verdict and the numbers behind it.

    Attributes:
        verdict: The verdict.
        near_threshold: One more document could change it.
        total_weight: W, the sum of the documents' weights.
        mean_support: S̄, the weight-averaged support; 0 when W is 0.
        refute_share: R%, the share of W that refutes; 0 when W is 0.
        n_documents: Documents that support or refute the link in any way.
    """

    verdict: Verdict
    near_threshold: bool
    total_weight: float
    mean_support: float
    refute_share: float
    n_documents: int


def quality(appraisal: DocAppraisal | None, robust_model: bool | None) -> int:
    """Quality Q, 1 to 3, of one document (C36).

    Args:
        appraisal: The document's appraisal, or ``None`` when it has none.
        robust_model: The judge's robust-model answer.

    Returns:
        Q.
    """
    if appraisal is None:
        return 1
    if appraisal.web and not appraisal.trusted:
        return 1
    if appraisal.modelling:
        return 2 if robust_model else 1
    score = appraisal.score or 0
    if score >= 4:
        return 3
    return 2 if score == 3 else 1


def weight(appraisal: DocAppraisal | None, judgement: Judgement) -> float:
    """A document's weight, Q × R ÷ 9 (0 to 1)."""
    return quality(appraisal, judgement.robust_model) * judgement.relevance / PERFECT


def link_verdict(
    judgements: Iterable[Judgement], appraisals: Mapping[str, DocAppraisal]
) -> LinkVerdict:
    """The verdict of one link.

    Sums are kept in whole Q × R units, so the thresholds are exact (the BEAM
    worked example's S̄ is exactly −0.5).

    Args:
        judgements: The link's judgements whose item hash equals its counted
            hash (the caller filters; C19).
        appraisals: Document id → its appraisal.

    Returns:
        The verdict with W, S̄, R% and the document count.
    """
    units = supported = refuting = documents = 0
    for judgement in judgements:
        value = SUPPORT_VALUE.get(judgement.support)
        if value is None:
            continue
        documents += 1
        unit = quality(appraisals.get(judgement.document_id), judgement.robust_model) * max(
            judgement.relevance, 0
        )
        units += unit
        supported += unit * value
        if judgement.support == "refutes":
            refuting += unit
    total = units / PERFECT
    mean = supported / units if units else 0.0
    share = refuting / units if units else 0.0
    verdict: Verdict
    if total < MIN_WEIGHT:
        verdict = "not_sure_insufficient"
    elif mean >= CONFIDENT_SUPPORT and share < MAX_REFUTE_SHARE:
        verdict = "confident"
    elif mean <= AGAINST_SUPPORT:
        verdict = "not_confident"
    else:
        verdict = "not_sure_mixed"
    near = abs(total - MIN_WEIGHT) <= NEAR_WEIGHT or (
        total >= MIN_WEIGHT
        and any(abs(mean - t) <= NEAR_SUPPORT for t in (CONFIDENT_SUPPORT, AGAINST_SUPPORT))
    )
    return LinkVerdict(
        verdict=verdict,
        near_threshold=near,
        total_weight=total,
        mean_support=mean,
        refute_share=share,
        n_documents=documents,
    )


def lowest(verdicts: Iterable[Verdict]) -> Verdict | None:
    """The lowest verdict, or ``None`` when there is none (the theory's confidence)."""
    return min(verdicts, key=VERDICT_ORDER.index, default=None)


def rule_text() -> list[tuple[str, str]]:
    """The verdict rule as the reading guide shows it, from the same constants.

    Returns:
        ``(label, rule)`` pairs, best first.
    """
    return [
        (
            VERDICT_LABELS["confident"],
            f"The documents add up to at least one strong, relevant study (total weight "
            f"{MIN_WEIGHT:g}), on average they support the step (average "
            f"{CONFIDENT_SUPPORT:+g} or more, on a scale from -2 to +2), and less than "
            f"{MAX_REFUTE_SHARE:.0%} of the weight is against it.",
        ),
        (
            VERDICT_LABELS["not_sure_mixed"],
            "Enough evidence, but it neither clearly supports nor clearly refutes the step.",
        ),
        (
            VERDICT_LABELS["not_sure_insufficient"],
            f"The documents add up to less than one strong, relevant study (total weight "
            f"under {MIN_WEIGHT:g}), including when none was found.",
        ),
        (
            VERDICT_LABELS["not_confident"],
            f"Enough evidence, and on average it is against the step (average "
            f"{AGAINST_SUPPORT:+g} or lower).",
        ),
        (
            "How a document weighs",
            "Quality (from its study design, 1 to 3) times relevance to this population "
            "and place (0 to 3), divided by 9. Strongly supports counts +2, weakly "
            "supports +1, mixed 0, refutes -2.",
        ),
    ]
