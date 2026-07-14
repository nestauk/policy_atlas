"""Tests for the shared two-stage clustering engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest

from policy_atlas.clustering_engine import (
    AssignmentOutput,
    ClusterAssignment,
    ClusteringFailure,
    ClusteringPolicy,
    ClusterLabel,
    ClusterUnit,
    InvalidDiscoveryOutput,
    cluster_units,
    validate_discovered_labels,
)
from policy_atlas.usage import TokenUsage, UsageResult


def _policy(
    *,
    min_labels: int = 1,
    max_labels: int = 3,
    unresolved_policy: Literal["fail", "residual"] = "fail",
    assignment_repair_cap: int = 1,
) -> ClusteringPolicy:
    return ClusteringPolicy(
        min_labels=min_labels,
        max_labels=max_labels,
        assignment_batch_size=50,
        discovery_retry_cap=1,
        assignment_repair_cap=assignment_repair_cap,
        residual_label="unclustered",
        unresolved_policy=unresolved_policy,
        label_max=20,
        description_max=40,
        forbidden_label_reason=lambda index, label: (
            f"label {index} forbidden: {label}" if label.casefold() == "forbidden" else None
        ),
        label_noun="label",
    )


@dataclass
class _Backend:
    discovery_outputs: list[list[ClusterLabel]]
    assignment_outputs: list[AssignmentOutput]

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        del units, min_labels, max_labels
        return (
            self.discovery_outputs.pop(0),
            TokenUsage(prompt=1, completion=2, total=3, cached=0),
        )

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[AssignmentOutput]:
        del batch, labels
        return (
            self.assignment_outputs.pop(0),
            TokenUsage(prompt=4, completion=5, total=9, cached=1),
        )


def test_discovery_validation_strips_and_rejects_forbidden_labels() -> None:
    labels = validate_discovered_labels(
        [ClusterLabel(label=" Housing ", description=" Homes ")],
        policy=_policy(),
    )

    assert labels == [ClusterLabel(label="Housing", description="Homes")]
    with pytest.raises(InvalidDiscoveryOutput, match="forbidden"):
        validate_discovered_labels(
            [ClusterLabel(label="Forbidden", description="Valid")],
            policy=_policy(),
        )


def test_min_zero_discovery_skips_assignment_and_residuals_all_units() -> None:
    units = [
        ClusterUnit(unit_id="u1", payload={"text": "one"}),
        ClusterUnit(unit_id="u2", payload={"text": "two"}),
    ]
    backend = _Backend(discovery_outputs=[[]], assignment_outputs=[])

    result = cluster_units(
        units,
        backend=backend,
        policy=_policy(min_labels=0, max_labels=3, unresolved_policy="residual"),
    )

    assert result.labels == []
    assert result.assignments == {"u1": "unclustered", "u2": "unclustered"}
    assert result.residual_ids == ["u1", "u2"]
    assert result.calls_used == 1
    assert result.call_budget.maximum == 4


def test_assignment_unknown_label_conflict_and_unknown_id_repair_once() -> None:
    units = [
        ClusterUnit(unit_id="u1", payload={}),
        ClusterUnit(unit_id="u2", payload={}),
        ClusterUnit(unit_id="u3", payload={}),
    ]
    labels = [ClusterLabel(label="A", description="Alpha")]
    backend = _Backend(
        discovery_outputs=[labels],
        assignment_outputs=[
            [
                ClusterAssignment(unit_id="u1", label="A"),
                ClusterAssignment(unit_id="invented", label="A"),
                ClusterAssignment(unit_id="u2", label="missing-label"),
                ClusterAssignment(unit_id="u3", label="A"),
                ClusterAssignment(unit_id="u3", label="B"),
            ],
            {"u2": "A", "u3": "A"},
        ],
    )

    result = cluster_units(units, backend=backend, policy=_policy())

    assert result.assignments == {"u1": "A", "u2": "A", "u3": "A"}
    assert result.assignment_repair_calls_used == 1
    assert result.residual_ids == []
    assert result.usage_totals == {"prompt": 9, "completion": 12, "total": 21, "cached": 2}
    assert "assignment invented 1 unknown ids" in result.rejection_reasons
    assert "assignment used 1 unknown labels" in result.rejection_reasons
    assert "assignment had 1 conflicting duplicate ids" in result.rejection_reasons


def test_residual_policy_places_units_left_unresolved_after_repair() -> None:
    units = [ClusterUnit(unit_id="u1", payload={}), ClusterUnit(unit_id="u2", payload={})]
    backend = _Backend(
        discovery_outputs=[[ClusterLabel(label="A", description="Alpha")]],
        assignment_outputs=[{}, {}],
    )

    result = cluster_units(
        units,
        backend=backend,
        policy=_policy(unresolved_policy="residual"),
    )

    assert result.assignments == {"u1": "unclustered", "u2": "unclustered"}
    assert result.residual_ids == ["u1", "u2"]
    assert result.assignment_repair_calls_used == 1


def test_fail_policy_raises_when_repair_leaves_units_unresolved() -> None:
    units = [ClusterUnit(unit_id="u1", payload={})]
    backend = _Backend(
        discovery_outputs=[[ClusterLabel(label="A", description="Alpha")]],
        assignment_outputs=[{}, {}],
    )

    with pytest.raises(ClusteringFailure, match="assignment repair left 1 unresolved"):
        cluster_units(units, backend=backend, policy=_policy(unresolved_policy="fail"))


def test_discovery_rejection_details_are_bounded() -> None:
    units = [ClusterUnit(unit_id="u1", payload={})]
    backend = _Backend(
        discovery_outputs=[
            [ClusterLabel(label="x" * 50, description="Alpha")],
            [ClusterLabel(label="A", description="Alpha")],
        ],
        assignment_outputs=[{"u1": "A"}],
    )
    policy = _policy()

    result = cluster_units(units, backend=backend, policy=policy)

    assert result.discovery_retries_used == 1
    assert result.discovery_rejections == ["label 0 name exceeds 20 chars"]
