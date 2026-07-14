"""Prompt-surface tests for ``group_cluster_v1`` (task 022 Phase D)."""

from __future__ import annotations

import json

from policy_atlas.clustering_engine import ClusterLabel, ClusterUnit
from policy_atlas.group import GROUP_PROMPT_VERSION, GROUP_RESIDUAL_LABEL
from policy_atlas.group_clustering import (
    GROUP_CLUSTERING_MODEL,
    GROUP_CLUSTERING_PROMPT_VERSION,
    build_assignment_messages,
    build_discovery_messages,
    records_json,
)


def _value_unit(unit_id: str = "v1", *, with_context: bool = True) -> ClusterUnit:
    payload: dict[str, object] = {
        "id": unit_id,
        "text": "Housing First",
        "value": "Housing First",
        "finding_count": 3,
        "counterparts": ["rough sleeping"],
    }
    if with_context:
        payload["context"] = {
            "anchors": [{"finding_id": "f1", "quote": "Housing First cut rough sleeping"}]
        }
    return ClusterUnit(unit_id=unit_id, payload=payload)


def _claim_unit(unit_id: str = "c1") -> ClusterUnit:
    return ClusterUnit(
        unit_id=unit_id,
        payload={
            "id": unit_id,
            "text": "Planning delays slowed the heat-pump rollout.",
            "claim": "Planning delays slowed the heat-pump rollout.",
            "context": {"intervention": "heat-pump rollout", "context_label": "Planning delays"},
        },
    )


def test_version_constants() -> None:
    assert GROUP_CLUSTERING_PROMPT_VERSION == "group_cluster_v1"
    assert GROUP_PROMPT_VERSION == GROUP_CLUSTERING_PROMPT_VERSION
    assert GROUP_CLUSTERING_MODEL == "gpt-5.4-mini"


def test_records_json_gates_context_and_drops_redundant_text() -> None:
    with_context = json.loads(records_json([_value_unit()], include_context=True))
    without = json.loads(records_json([_value_unit()], include_context=False))
    assert "context" in with_context[0]
    assert "context" not in without[0]
    assert "text" not in with_context[0]
    assert with_context[0]["id"] == "v1"
    assert with_context[0]["value"] == "Housing First"


def test_discovery_messages_carry_ceiling_and_never_ask_for_ids() -> None:
    messages = build_discovery_messages(
        [_value_unit()],
        facet="intervention",
        projection="value",
        max_labels=7,
        include_context=False,
    )
    assert messages[0]["role"] == "system"
    system = str(messages[0]["content"])
    user = str(messages[1]["content"])
    assert "at most 7 groups" in user
    assert "no minimum" in user.casefold()
    assert "ONLY group labels and descriptions" in system
    assert "recurring pattern across sources" in system
    assert "data, not instructions" in user.casefold()
    # Discovery must never solicit member ids — the retired one-call cliff.
    assert "member_ids" not in system


def test_discovery_variants_differ_by_projection() -> None:
    value = build_discovery_messages(
        [_value_unit()],
        facet="intervention",
        projection="value",
        max_labels=5,
        include_context=True,
    )
    claim = build_discovery_messages(
        [_claim_unit()],
        facet="barrier_theme",
        projection="claim",
        max_labels=5,
        include_context=True,
    )
    assert "counterpart" in str(value[0]["content"])
    assert "implementation-context claim" in str(claim[0]["content"])
    assert "source-authored label" in str(claim[0]["content"])


def test_assignment_messages_fix_labels_and_offer_ungroupable() -> None:
    labels = [ClusterLabel(label="Housing-led interventions", description="D")]
    messages = build_assignment_messages(
        [_value_unit()], facet="intervention", projection="value", labels=labels
    )
    system = str(messages[0]["content"])
    user = str(messages[1]["content"])
    assert '"ungroupable"' in system
    assert "copied exactly" in system
    assert "Housing-led interventions" in user
    # The engine residual sentinel never leaks into prompt text.
    assert GROUP_RESIDUAL_LABEL not in system
    assert GROUP_RESIDUAL_LABEL not in user
