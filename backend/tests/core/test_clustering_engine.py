"""Tests for the shared two-stage clustering engine."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import pytest

from policy_atlas.core.clustering_engine import (
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
from policy_atlas.core.usage import TokenUsage, UsageResult
from tests import progress_recorder


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
    assert result.usage_totals == {
        "prompt": 9,
        "completion": 12,
        "total": 21,
        "cached": 2,
        "cache_write": 0,
        "reasoning": 0,
    }
    assert "assignment invented 1 unknown ids" in result.rejection_reasons
    assert "assignment used 1 unknown labels" in result.rejection_reasons
    assert "assignment had 1 conflicting duplicate ids" in result.rejection_reasons


def test_assignment_repair_cap_above_one_grants_further_rounds() -> None:
    units = [
        ClusterUnit(unit_id="u1", payload={}),
        ClusterUnit(unit_id="u2", payload={}),
    ]
    labels = [ClusterLabel(label="A", description="Alpha")]
    backend = _Backend(
        discovery_outputs=[labels],
        assignment_outputs=[
            {"u1": "A", "u2": "missing-label"},  # first attempt: u2 unresolved
            {"u2": "missing-label"},  # repair round 1: still unresolved
            {"u2": "A"},  # repair round 2: resolves under cap=2
        ],
    )

    result = cluster_units(units, backend=backend, policy=_policy(assignment_repair_cap=2))

    assert result.assignments == {"u1": "A", "u2": "A"}
    assert result.assignment_repair_calls_used == 2
    assert result.residual_ids == []


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


# --- Live progress (task 058, N2) ---


def test_first_round_publishes_batches_done_of_total(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = progress_recorder.install(monkeypatch)
    units = [ClusterUnit(unit_id=f"u{i}", payload={}) for i in range(1, 4)]
    labels = [ClusterLabel(label="A", description="Alpha")]
    backend = _Backend(
        discovery_outputs=[labels],
        assignment_outputs=[
            [
                ClusterAssignment(unit_id="u1", label="A"),
                ClusterAssignment(unit_id="u2", label="A"),
            ],
            [ClusterAssignment(unit_id="u3", label="A")],
        ],
    )
    policy = replace(_policy(), assignment_batch_size=2, progress_key="longlist.batches")

    cluster_units(units, backend=backend, policy=policy)

    assert [(c["done"], c["total"], c["unit"]) for c in calls] == [
        (0, 2, "batches"),
        (1, 2, "batches"),
        (2, 2, "batches"),
    ]
    assert calls[-1]["activity"] == "Assigning sources to options · batch 2 of 2"


def test_repair_call_does_not_move_the_batch_count(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = progress_recorder.install(monkeypatch)
    units = [ClusterUnit(unit_id="u1", payload={}), ClusterUnit(unit_id="u2", payload={})]
    labels = [ClusterLabel(label="A", description="Alpha")]
    backend = _Backend(
        discovery_outputs=[labels],
        assignment_outputs=[[ClusterAssignment(unit_id="u1", label="A")], {"u2": "A"}],
    )
    policy = replace(_policy(), progress_key="characterise.batches")

    result = cluster_units(units, backend=backend, policy=policy)

    assert result.assignment_repair_calls_used == 1
    assert [c["done"] for c in calls] == [0, 1]


def test_no_progress_key_publishes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = progress_recorder.install(monkeypatch)
    units = [ClusterUnit(unit_id="u1", payload={})]
    backend = _Backend(
        discovery_outputs=[[ClusterLabel(label="A", description="Alpha")]],
        assignment_outputs=[[ClusterAssignment(unit_id="u1", label="A")]],
    )

    cluster_units(units, backend=backend, policy=_policy())

    assert calls == []


def test_each_caller_names_its_progress_key() -> None:
    from policy_atlas.evidence_search.corpus.characterise import _characterise_clustering_policy
    from policy_atlas.evidence_search.group.group import _group_policy
    from policy_atlas.options_scoping.longlist.longlist import _option_policy
    from policy_atlas.options_scoping.theme.theme import _theme_policy

    assert _characterise_clustering_policy(min_themes=2, max_themes=6).progress_key == (
        "characterise.batches"
    )
    assert _group_policy(unit_count=10).progress_key == "group.batches"
    assert _option_policy(8).progress_key == "longlist.batches"
    assert _theme_policy(4).progress_key == "theme.batches"


def test_labels_are_handed_over_after_discovery_and_before_assignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task 058, round 9: the characterise stage shows its themes while it assigns."""
    order: list[str] = []
    units = [ClusterUnit(unit_id="u1", payload={})]
    labels = [
        ClusterLabel(label="A", description="Alpha"),
        ClusterLabel(label="B", description="Beta"),
    ]

    class _Ordered(_Backend):
        def assign(
            self, batch: list[ClusterUnit], *, labels: list[ClusterLabel]
        ) -> UsageResult[AssignmentOutput]:
            order.append("assign")
            return super().assign(batch, labels=labels)

    backend = _Ordered(
        discovery_outputs=[labels],
        assignment_outputs=[[ClusterAssignment(unit_id="u1", label="A")]],
    )
    seen: list[list[str]] = []

    def on_labels(found: list[ClusterLabel]) -> None:
        order.append("labels")
        seen.append([label.label for label in found])

    cluster_units(units, backend=backend, policy=replace(_policy(), on_labels=on_labels))
    assert order == ["labels", "assign"]
    assert seen == [["A", "B"]]

    # The characterise stage publishes them as the themes found; the others do not.
    from policy_atlas.core import liveness
    from policy_atlas.evidence_search.corpus.characterise import _characterise_clustering_policy
    from policy_atlas.evidence_search.group.group import _group_policy
    from policy_atlas.options_scoping.longlist.longlist import _option_policy
    from policy_atlas.options_scoping.theme.theme import _theme_policy

    published: list[list[tuple[str, str | None]]] = []
    monkeypatch.setattr(liveness, "publish_themes", lambda themes: published.append(list(themes)))
    policy = _characterise_clustering_policy(min_themes=2, max_themes=6)
    assert policy.on_labels is not None
    policy.on_labels([labels[0], ClusterLabel(label="B", description="")])
    assert published == [[("A", "Alpha"), ("B", None)]]
    assert _group_policy(unit_count=10).on_labels is None
    assert _option_policy(8).on_labels is None
    assert _theme_policy(4).on_labels is None
