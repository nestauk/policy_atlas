"""Turn stage-1 screen replies into the keep-or-drop the app would record.

The rule is the one in ``evidence_search.assess.screen``: ``unsure`` votes to
keep, a tie keeps, and a document with no abstract flips back to keep when any
reply said ``relevant``. A run that asked for several replies needs at least
``SCREEN_QUORUM`` replies that parsed; a one-reply run decides from that
single reply, which is the cheaper experiment.
"""

from __future__ import annotations

from dataclasses import dataclass

from policy_atlas.evidence_search.assess.screen_prompt import (
    SCREEN_QUORUM,
    ScreenRepWire,
)


@dataclass(frozen=True)
class KeepDecision:
    """The eval's reading of one document's replies.

    Args:
        status: ``relevant`` (kept), ``not_relevant`` (dropped), or ``failed``
            (too few replies parsed to decide).
        confidence: Probability the status is right, or ``None`` when failed.
        flags: Short labels such as ``tie_broken`` or ``title_only_unanimity_applied`` (the production names).
    """

    status: str
    confidence: float | None
    flags: tuple[str, ...]


def _vote(rep: ScreenRepWire) -> str:
    return "relevant" if rep.decision in ("relevant", "unsure") else "not_relevant"


def _p_relevant(rep: ScreenRepWire) -> float:
    if rep.decision == "relevant":
        return float(rep.confidence)
    if rep.decision == "not_relevant":
        return 1.0 - float(rep.confidence)
    return 0.5


def combine_reps(
    reps: list[ScreenRepWire],
    *,
    reps_requested: int,
    title_only: bool,
) -> KeepDecision:
    """Apply the stage-1 keep rule to the replies that parsed.

    Args:
        reps: Replies that parsed and had a confidence between 0 and 1.
        reps_requested: How many replies the run asked for. Two or more use
            the production quorum. One reply is a decision by itself.
        title_only: True when the document has no abstract. Only then does a
            single ``relevant`` reply overturn a ``not_relevant`` majority.

    Returns:
        The keep decision, including a confidence in ``[0, 1]`` when it decided.
    """
    need_quorum = reps_requested >= SCREEN_QUORUM
    if not reps or (need_quorum and len(reps) < SCREEN_QUORUM):
        return KeepDecision(status="failed", confidence=None, flags=())

    relevant_votes = sum(1 for rep in reps if _vote(rep) == "relevant")
    not_relevant_votes = len(reps) - relevant_votes
    flags: list[str] = []
    if relevant_votes == not_relevant_votes:
        status = "relevant"
        flags.append("tie_broken")
    elif relevant_votes > not_relevant_votes:
        status = "relevant"
    else:
        status = "not_relevant"

    if (
        title_only
        and status == "not_relevant"
        and any(rep.decision == "relevant" for rep in reps)
    ):
        status = "relevant"
        flags.append("title_only_unanimity_applied")

    mean_p = sum(_p_relevant(rep) for rep in reps) / len(reps)
    confidence = mean_p if status == "relevant" else 1.0 - mean_p
    return KeepDecision(status=status, confidence=confidence, flags=tuple(flags))
