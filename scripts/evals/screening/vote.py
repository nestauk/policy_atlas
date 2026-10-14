"""Turn stage-1 screen replies into decisions for screening experiments."""

from __future__ import annotations

from dataclasses import dataclass

from policy_atlas.evidence_search.assess.screen import decide_stage1
from policy_atlas.evidence_search.assess.screen_prompt import ScreenRepWire

MAJORITY_QUORUM = 2


@dataclass(frozen=True)
class KeepDecision:
    """The eval's reading of one document's replies.

    Args:
        status: ``relevant`` (kept), ``not_relevant`` (dropped), or ``failed``
            (too few replies parsed to decide).
        confidence: Probability the status is right, or ``None`` when failed.
        flags: Short labels emitted by the selected vote rule.
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
    """Apply the historical fixed-repetition majority rule to parsed replies.

    This is ADR 0011's historical production rule, replaced in production by
    task 051's adaptive vote.

    Args:
        reps: Replies that parsed and had a confidence between 0 and 1.
        reps_requested: How many replies the run asked for. Two or more use
            the literal quorum of two. One reply is a decision by itself.
        title_only: Retained for historical call compatibility; it has no effect.

    Returns:
        The keep decision, including a confidence in ``[0, 1]`` when it decided.
    """
    need_quorum = reps_requested >= MAJORITY_QUORUM
    if not reps or (need_quorum and len(reps) < MAJORITY_QUORUM):
        return KeepDecision(status="failed", confidence=None, flags=())

    relevant_votes = sum(1 for rep in reps if _vote(rep) == "relevant")
    not_relevant_votes = len(reps) - relevant_votes
    flags: list[str] = []
    status = "relevant" if relevant_votes >= not_relevant_votes else "not_relevant"

    mean_p = sum(_p_relevant(rep) for rep in reps) / len(reps)
    confidence = mean_p if status == "relevant" else 1.0 - mean_p
    return KeepDecision(status=status, confidence=confidence, flags=tuple(flags))


def combine_adaptive(attempts: list[ScreenRepWire | None]) -> KeepDecision:
    """Apply production's adaptive stage-1 decision to up to two attempts."""
    decision = decide_stage1(
        attempts[0] if attempts else None,
        attempts[1] if len(attempts) > 1 else None,
    )
    return KeepDecision(
        status=decision.status,
        confidence=decision.confidence,
        flags=decision.flags,
    )
