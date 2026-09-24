"""Coverage guard for the public stage vocabulary (spec § SSE).

No database needed — these tests only check that the pinned `StageKey`
Literal, `STAGE_KEYS` tuple, `PlanStageKey` Literal and the presentation/
registry dicts in `stage_vocabulary` never drift apart.
"""

from __future__ import annotations

from typing import get_args

from policy_atlas.api.contract.sse import STAGE_KEYS, StageKey
from policy_atlas.api.contract.task_agent import PlanStageKey
from policy_atlas.api.stage_vocabulary import STAGE_BY_REGISTRY, STAGE_PRESENTATION


def test_stage_keys_tuple_matches_literal() -> None:
    """`STAGE_KEYS` has exactly `StageKey`'s members, in the same order."""
    assert get_args(StageKey) == STAGE_KEYS


def test_plan_stage_key_mirrors_stage_key() -> None:
    """`PlanStageKey` (the standalone contract copy) has the same members."""
    assert set(get_args(PlanStageKey)) == set(get_args(StageKey))


def test_every_stage_key_has_a_presentation() -> None:
    """Every pinned `StageKey` has a `(label, blurb)` presentation entry."""
    assert set(STAGE_PRESENTATION) == set(get_args(StageKey))


def test_every_registry_mapping_targets_a_stage_key() -> None:
    """Every `STAGE_BY_REGISTRY` value is a valid public `StageKey`."""
    stage_keys = set(get_args(StageKey))
    for registry_component, stage in STAGE_BY_REGISTRY.items():
        assert stage in stage_keys, f"{registry_component} -> {stage} is not a StageKey"
