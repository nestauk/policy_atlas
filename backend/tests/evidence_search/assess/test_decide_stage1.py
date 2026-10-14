"""Pure decision-table tests for adaptive stage-1 screening."""

from __future__ import annotations

from typing import Literal

import pytest

from policy_atlas.evidence_search.assess.screen import decide_stage1
from policy_atlas.evidence_search.assess.screen_prompt import ScreenRepWire


def _rep(
    decision: Literal["relevant", "not_relevant", "unsure"], confidence: float
) -> ScreenRepWire:
    return ScreenRepWire(decision=decision, confidence=confidence, reason="test")


@pytest.mark.parametrize(
    ("first", "second", "status", "confidence", "flags"),
    [
        (_rep("relevant", 0.8), None, "relevant", 0.8, ()),
        (_rep("unsure", 0.9), None, "relevant", 0.5, ()),
        (_rep("not_relevant", 0.9), _rep("unsure", 0.8), "relevant", 0.3, ("second_call_kept",)),
        (_rep("not_relevant", 0.7), _rep("not_relevant", 0.9), "not_relevant", 0.8, ()),
        (_rep("not_relevant", 0.7), None, "not_relevant", 0.7, ("second_call_failed",)),
        (None, None, "failed", None, ()),
    ],
)
def test_decide_stage1_table(
    first: ScreenRepWire | None,
    second: ScreenRepWire | None,
    status: str,
    confidence: float | None,
    flags: tuple[str, ...],
) -> None:
    decision = decide_stage1(first, second)
    assert decision.status == status
    if confidence is None:
        assert decision.confidence is None
    else:
        assert decision.confidence == pytest.approx(confidence)
    assert decision.flags == flags


def test_decide_stage1_rejects_unneeded_second_reply() -> None:
    with pytest.raises(ValueError, match="second stage-1"):
        decide_stage1(_rep("relevant", 0.8), _rep("not_relevant", 0.9))
