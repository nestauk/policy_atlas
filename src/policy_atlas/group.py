"""Group component: multi-facet theming over extracted findings.

The component reads one explicitly referenced extraction roll-up, resolves the
run's finding set once, then fans out separate clustering-engine runs per
requested facet. Value facets cluster normalized source-named reference values;
claim-theme facets cluster ICF claim prose scoped by ``context_type``.
"""

from __future__ import annotations

import hashlib
import json
import math
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, Protocol, cast

import structlog
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.clustering_engine import (
    AssignmentOutput,
    ClusteringBackend,
    ClusteringFailure,
    ClusteringPolicy,
    ClusteringResult,
    ClusterLabel,
    ClusterUnit,
    call_budget_for_unit_count,
    cluster_units,
)
from policy_atlas.extract import record_ids_by_profile
from policy_atlas.facet_grouping import (
    DESCRIPTION_MAX,
    FACET_VALUE_CAP,
    FORBIDDEN_GROUP_LABELS,
    LABEL_MAX,
    VALUE_SURFACE_MAX,
)
from policy_atlas.facet_values import (
    CLAIM_THEME_FACETS,
    FACET_COUNTERPART,
    VALUE_FACETS,
    AcceptedGroup,
    FacetValue,
    FindingFacetView,
    InvalidPartitionOutput,
    assert_grouping_invariants,
    build_groups_payload,
    extract_facet_values,
    parse_grouping_directive,
)
from policy_atlas.group_clustering import (
    GROUP_CLUSTERING_PROMPT_VERSION,
    UNGROUPABLE_WIRE_WORD,
    ProjectionKind,
)
from policy_atlas.group_clustering import (
    GROUP_RESIDUAL_LABEL as _GROUP_RESIDUAL_LABEL,
)
from policy_atlas.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.schema import (
    extraction_result,
    finding_reference_union,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
)
from policy_atlas.tags import has_control_character
from policy_atlas.usage import UsageAccumulator, UsageResult

log = structlog.get_logger()

REJECTION_REASON_CAP = 20
REJECTION_REASON_MAX = 200
# Prompt-payload bounds for claim-theme units (mirrors VALUE_SURFACE_MAX on the
# value path; ICF text fields carry no extraction-time length bound).
CLAIM_SURFACE_MAX = 1000
CONTEXT_LABEL_SURFACE_MAX = 160
GROUP_ASSIGNMENT_BATCH_SIZE = 50
GROUP_DISCOVERY_RETRY_CAP = 1
GROUP_ASSIGNMENT_REPAIR_CAP = 1
GROUP_CONTEXT_DISCOVERY_UNIT_LIMIT = 120
GROUP_RESIDUAL_LABEL = _GROUP_RESIDUAL_LABEL
GROUP_PROMPT_VERSION: str = GROUP_CLUSTERING_PROMPT_VERSION

FailureClass = Literal[
    "cap_exceeded",
    "backend_error",
    "discovery_exhausted",
    "assignment_exhausted",
    "validation_failed",
]

CLAIM_THEME_CONTEXT_TYPES: dict[str, str] = {
    "barrier_theme": "barrier",
    "enabler_theme": "enabler",
    "mechanism_theme": "mechanism",
}


class GroupError(Exception):
    """Structural group failure for corrupt shared input or cross-facet invariants."""


@dataclass(frozen=True)
class GroupContext:
    """Scope-level input to group.

    Attributes:
        scope_id: Evidence scope whose extracted findings are grouped.
        intent: Scope intent, carried for wiring uniformity with other scope
            components. Grouping does not consume it.
        context: Scope context JSONB, optionally carrying a grouping directive.
        extraction_run_id: Explicit extraction run whose findings are grouped.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]
    extraction_run_id: uuid.UUID


class GroupClusteringBackendFactory(Protocol):
    """Factory seam for group-side clustering backends.

    Implementations produce a ``ClusteringBackend`` for one facet/projection run.
    Phase C ships only the deterministic stub; live prompt-backed group
    backends arrive in the prompt-bearing Phase D.
    """

    @property
    def mode(self) -> str:
        """Return ``"stub"`` or a future live mode label."""
        ...

    def for_facet(
        self,
        *,
        facet: str,
        projection: ProjectionKind,
        include_context_in_discovery: bool,
    ) -> ClusteringBackend:
        """Return an engine backend for one facet run.

        Args:
            facet: Facet being clustered.
            projection: Unit projection kind.
            include_context_in_discovery: Whether discovery calls may see
                per-unit context payloads. Assignment calls always receive them.

        Returns:
            A clustering-engine backend.
        """
        ...


@dataclass(frozen=True)
class StubGroupCall:
    """One recorded deterministic stub call.

    Attributes:
        stage: ``"discover"`` or ``"assign"``.
        facet: Facet being clustered.
        projection: Unit projection kind.
        payloads: Prompt-facing unit payload copies seen by the call.
    """

    stage: Literal["discover", "assign"]
    facet: str
    projection: ProjectionKind
    payloads: list[dict[str, Any]]


class StubGroupClusteringBackend:
    """Deterministic no-egress group clustering backend for tests and local runs.

    The stub discovers groups from first-token buckets, then assigns units back
    to the discovered label set. Tokens beginning ``stubungroupable`` are never
    discovered and therefore land in the engine residual, exercising both
    discovery and assignment paths without any provider calls.
    """

    mode = "stub"
    model = "stub"

    def __init__(
        self,
        *,
        fail_facets: Collection[str] = (),
        fail_assignment_facets: Collection[str] = (),
        zero_label_facets: Collection[str] = (),
    ) -> None:
        """Create a deterministic group clustering stub.

        Args:
            fail_facets: Facets whose discovery calls raise a backend sentinel.
            fail_assignment_facets: Facets whose assignment calls raise a
                backend sentinel.
            zero_label_facets: Facets whose discovery calls return no labels.
        """
        self.fail_facets = set(fail_facets)
        self.fail_assignment_facets = set(fail_assignment_facets)
        self.zero_label_facets = set(zero_label_facets)
        self.calls: list[StubGroupCall] = []

    def for_facet(
        self,
        *,
        facet: str,
        projection: ProjectionKind,
        include_context_in_discovery: bool,
    ) -> ClusteringBackend:
        """Return a facet-scoped stub adapter.

        Args:
            facet: Facet being clustered.
            projection: Unit projection kind.
            include_context_in_discovery: Whether discovery records include
                context.

        Returns:
            A clustering backend for the requested facet.
        """
        return _StubGroupFacetBackend(
            self,
            facet=facet,
            projection=projection,
            include_context_in_discovery=include_context_in_discovery,
        )


class _StubGroupFacetBackend:
    def __init__(
        self,
        parent: StubGroupClusteringBackend,
        *,
        facet: str,
        projection: ProjectionKind,
        include_context_in_discovery: bool,
    ) -> None:
        self._parent = parent
        self._facet = facet
        self._projection = projection
        self._include_context_in_discovery = include_context_in_discovery

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        """Discover deterministic first-token labels.

        Args:
            units: Units to cluster.
            min_labels: Minimum accepted label count, ignored by the stub.
            max_labels: Maximum labels to return.

        Returns:
            Discovered labels plus no token usage.
        """
        del min_labels
        self._record("discover", units, include_context=self._include_context_in_discovery)
        if self._facet in self._parent.fail_facets:
            raise RuntimeError("backend_error: Stub group discovery failure sentinel.")
        if self._facet in self._parent.zero_label_facets:
            return [], None

        labels: list[ClusterLabel] = []
        seen: set[str] = set()
        for unit in units:
            token = _stub_token(_unit_text(unit))
            if token is None or token in seen:
                continue
            seen.add(token)
            labels.append(
                ClusterLabel(
                    label=token,
                    description=f"Units grouped by stub token '{token}'.",
                )
            )
            if len(labels) >= max_labels:
                break
        return labels, None

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[AssignmentOutput]:
        """Assign units to deterministic first-token labels.

        Args:
            batch: Units to assign.
            labels: Valid discovered labels.

        Returns:
            Unit-id to label assignments plus no token usage.
        """
        self._record("assign", batch, include_context=True)
        if self._facet in self._parent.fail_assignment_facets:
            raise RuntimeError("backend_error: Stub group assignment failure sentinel.")
        labels_by_key = {label.label.casefold(): label.label for label in labels}
        assignments: dict[str, str] = {}
        for unit in batch:
            token = _stub_token(_unit_text(unit))
            assignments[unit.unit_id] = (
                labels_by_key[token.casefold()]
                if token is not None and token.casefold() in labels_by_key
                else GROUP_RESIDUAL_LABEL
            )
        return assignments, None

    def _record(
        self,
        stage: Literal["discover", "assign"],
        units: list[ClusterUnit],
        *,
        include_context: bool,
    ) -> None:
        self._parent.calls.append(
            StubGroupCall(
                stage=stage,
                facet=self._facet,
                projection=self._projection,
                payloads=[
                    _payload_copy(unit.payload, include_context=include_context)
                    for unit in units
                ],
            )
        )


@dataclass(frozen=True)
class FindingDetail:
    """Direct finding-table detail used to enrich value-facet projections.

    Attributes:
        effect_direction: IOF effect direction when available; ``None`` for
            non-IOF findings.
        anchors: Verbatim grounding quotes in stable finding-table order.
    """

    effect_direction: str | None
    anchors: tuple[str, ...]


@dataclass(frozen=True)
class ClaimThemeUnit:
    """Eligible ICF claim-theme unit before clustering-engine projection.

    Attributes:
        finding_id: Stable finding identifier.
        claim: Claim prose used as the clustering unit text.
        context_label: Source-authored claim-theme label, when present.
        intervention: Source-named intervention context.
    """

    finding_id: str
    claim: str
    context_label: str | None
    intervention: str


@dataclass(frozen=True)
class FacetAssembly:
    """Completed in-memory assembly for one facet run.

    Attributes:
        payload: Facet-keyed grouping payload fragment.
        counts: Persisted count object for the facet.
        flag: Persisted outcome flag for the facet.
        provenance: Per-facet provenance object.
        summary_groups: Compact groups for the component summary.
        summary_residuals: Compact residual buckets for the component summary.
        usage_totals: Token/call usage accumulated for the facet.
        expected_finding_ids: Eligible-base finding IDs for invariant checks.
    """

    payload: dict[str, Any]
    counts: dict[str, int]
    flag: dict[str, Any]
    provenance: dict[str, Any]
    summary_groups: list[dict[str, Any]]
    summary_residuals: dict[str, Any]
    usage_totals: dict[str, int]
    expected_finding_ids: list[str]


def group_findings(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: GroupContext,
    group_clustering_backend: GroupClusteringBackendFactory | None = None,
) -> dict[str, Any]:
    """Group extracted findings across one or more facets.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run writing the grouping result.
        context: Scope-level group input with the explicit extraction run.
        group_clustering_backend: Group-side clustering backend factory.

    Returns:
        The grouping summary payload for ``component.completed``.

    Raises:
        GroupError: If the extraction roll-up is corrupt or the assembled
            multi-facet payload violates cross-facet invariants.
    """
    backend_factory = (
        group_clustering_backend
        if group_clustering_backend is not None
        else StubGroupClusteringBackend()
    )

    facets, facet_source = parse_grouping_directive(context.context)
    docs, extraction_profile_counts, extraction_profile_provenance, raw_counts = (
        _load_extraction_rollup(
            conn,
            project_id=project_id,
            scope_id=context.scope_id,
            extraction_run_id=context.extraction_run_id,
        )
    )
    extraction_record_ids_by_kind = _extraction_record_ids_by_kind(docs)
    references = _load_finding_references(
        conn,
        project_id=project_id,
        extraction_record_ids_by_kind=extraction_record_ids_by_kind,
    )
    expected_findings_total = _all_extraction_findings_total(raw_counts)
    if len(references) != expected_findings_total:
        raise GroupError(
            "corrupt reference: resolved "
            f"{len(references)} findings for extraction_run_id {context.extraction_run_id}, "
            f"expected {expected_findings_total}"
        )

    finding_details = _load_finding_details(
        conn,
        project_id=project_id,
        extraction_record_ids_by_kind=extraction_record_ids_by_kind,
    )
    payload: dict[str, Any] = {}
    counts: dict[str, dict[str, int]] = {}
    flags: dict[str, dict[str, Any]] = {}
    facet_provenance: dict[str, dict[str, Any]] = {}
    expected_by_facet: dict[str, list[str]] = {}
    summary_groups: dict[str, list[dict[str, Any]]] = {}
    summary_residuals: dict[str, dict[str, Any]] = {}
    usage_totals = UsageAccumulator()

    for facet in facets:
        if facet in VALUE_FACETS:
            assembly = _run_value_facet(
                facet,
                references=references,
                finding_details=finding_details,
                backend_factory=backend_factory,
            )
        elif facet in CLAIM_THEME_FACETS:
            assembly = _run_claim_theme_facet(
                conn,
                project_id=project_id,
                facet=facet,
                extraction_record_ids_by_kind=extraction_record_ids_by_kind,
                backend_factory=backend_factory,
            )
        else:
            raise GroupError(f"grouping invariant violated: unsupported facet {facet}")

        payload.update(assembly.payload)
        counts[facet] = assembly.counts
        flags[facet] = assembly.flag
        facet_provenance[facet] = assembly.provenance
        summary_groups[facet] = assembly.summary_groups
        summary_residuals[facet] = assembly.summary_residuals
        expected_by_facet[facet] = assembly.expected_finding_ids
        usage_totals.add_payload(assembly.usage_totals)

    try:
        assert_grouping_invariants(payload, finding_ids_by_facet=expected_by_facet)
    except InvalidPartitionOutput as exc:
        raise GroupError(f"grouping invariant violated: {exc}") from exc

    provenance = _build_provenance(
        backend=backend_factory,
        facets=facets,
        facet_source=facet_source,
        facet_provenance=facet_provenance,
        extraction_run_id=context.extraction_run_id,
        extraction_profile_counts=extraction_profile_counts,
        extraction_profile_provenance=extraction_profile_provenance,
        finding_ids=[str(reference["finding_id"]) for reference in references],
    )
    summary = _build_summary(
        facets=facets,
        facet_source=facet_source,
        groups=summary_groups,
        residuals=summary_residuals,
        counts=counts,
        flags=flags,
        extraction_run_id=context.extraction_run_id,
        provenance=provenance,
        usage_totals=usage_totals.payload(),
    )

    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=context.scope_id,
            run_id=run_id,
            extraction_run_id=context.extraction_run_id,
            grouping_provenance=provenance,
            groups=payload,
            counts=counts,
            flags=flags,
            created_at=datetime.now(UTC),
        )
    )
    log.info("group.completed", facets=facets, counts=counts)
    return summary


def group_max_labels(unit_count: int) -> int:
    """Compute the group discovery ceiling for one facet run.

    Args:
        unit_count: Number of eligible units in the facet run.

    Returns:
        ``ceil(N/5)`` clamped to ``[3, 40]``.
    """
    return max(3, min(40, math.ceil(unit_count / 5)))


def group_call_budget(unit_count: int) -> int:
    """Compute the hard model-call budget for one group facet run.

    Args:
        unit_count: Number of eligible units in the facet run.

    Returns:
        Maximum calls under the Phase C retry and repair policy.
    """
    return call_budget_for_unit_count(
        unit_count,
        assignment_batch_size=GROUP_ASSIGNMENT_BATCH_SIZE,
        discovery_retry_cap=GROUP_DISCOVERY_RETRY_CAP,
        assignment_repair_cap=GROUP_ASSIGNMENT_REPAIR_CAP,
    ).maximum


def _run_value_facet(
    facet: str,
    *,
    references: Sequence[Mapping[str, Any]],
    finding_details: Mapping[str, FindingDetail],
    backend_factory: GroupClusteringBackendFactory,
) -> FacetAssembly:
    views = _project_reference_rows(
        references,
        facet=facet,
        finding_details=finding_details,
    )
    values, no_value_finding_ids = extract_facet_values(views)
    finding_ids = [view.finding_id for view in views]
    base_sha = _value_base_sha256(views)
    call_budget = group_call_budget(len(values))

    failure: FailureClass | None = None
    rejection_reasons: list[str] = []
    result: ClusteringResult | None = None

    if len(values) > FACET_VALUE_CAP:
        failure = "cap_exceeded"
        rejection_reasons.append(
            f"value_cap_exceeded: {len(values)} units exceeds cap {FACET_VALUE_CAP}"
        )
    else:
        surface_error = _value_surface_error(values)
        if surface_error is not None:
            failure = "validation_failed"
            rejection_reasons.append(surface_error)

    if failure is None and values:
        units = _value_cluster_units(values, finding_details=finding_details)
        result, failure, rejection_reasons = _cluster_facet_units(
            units,
            facet=facet,
            projection="value",
            backend_factory=backend_factory,
        )
    elif failure is None:
        result = None

    groups, ungrouped_value_ids = _value_groups_from_result(values, result)
    payload = _build_value_payload(
        views,
        facet=facet,
        values=values,
        groups=groups,
        ungrouped_value_ids=ungrouped_value_ids,
        no_value_finding_ids=no_value_finding_ids,
        finding_ids=finding_ids,
    )
    counts = _build_value_counts(
        payload,
        facet=facet,
        eligible_base=len(views),
        distinct_values=len(values),
    )
    flag = _facet_flag(
        failure=failure,
        rejection_reasons=rejection_reasons if failure is not None else (
            result.rejection_reasons if result is not None else []
        ),
        value_cap_exceeded=failure == "cap_exceeded",
    )
    provenance = _facet_provenance(
        eligible_base_size=len(views),
        eligible_base_sha256=base_sha,
        call_budget=call_budget,
        calls_used=result.calls_used if result is not None else 0,
        rejection_reasons=(
            rejection_reasons
            if failure is not None
            else (result.rejection_reasons if result is not None else [])
        ),
        projection="value",
        unit_count=len(values),
        max_labels=group_max_labels(len(values)),
        assignment_repair_calls_used=(
            result.assignment_repair_calls_used if result is not None else 0
        ),
    )
    facet_payload = _facet_payload(payload, facet)
    return FacetAssembly(
        payload=payload,
        counts=counts,
        flag=flag,
        provenance=provenance,
        summary_groups=_summary_groups(cast("list[dict[str, Any]]", facet_payload["groups"])),
        summary_residuals=_value_summary_residuals(facet_payload),
        usage_totals=result.usage_totals if result is not None else UsageAccumulator().payload(),
        expected_finding_ids=finding_ids,
    )


def _run_claim_theme_facet(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    facet: str,
    extraction_record_ids_by_kind: Mapping[str, Sequence[uuid.UUID]],
    backend_factory: GroupClusteringBackendFactory,
) -> FacetAssembly:
    claims = _load_claim_theme_units(
        conn,
        project_id=project_id,
        facet=facet,
        extraction_record_ids=extraction_record_ids_by_kind.get("icf", ()),
    )
    finding_ids = [claim.finding_id for claim in claims]
    base_sha = claim_theme_base_sha256(claims)
    call_budget = group_call_budget(len(claims))

    failure: FailureClass | None = None
    rejection_reasons: list[str] = []
    result: ClusteringResult | None = None

    if len(claims) > FACET_VALUE_CAP:
        failure = "cap_exceeded"
        rejection_reasons.append(
            f"value_cap_exceeded: {len(claims)} units exceeds cap {FACET_VALUE_CAP}"
        )
    elif claims:
        units = _claim_cluster_units(claims)
        result, failure, rejection_reasons = _cluster_facet_units(
            units,
            facet=facet,
            projection="claim",
            backend_factory=backend_factory,
        )

    groups, ungrouped_finding_ids = _claim_groups_from_result(claims, result)
    payload = _build_claim_theme_payload(
        facet=facet,
        groups=groups,
        ungrouped_finding_ids=ungrouped_finding_ids,
    )
    counts = _build_claim_counts(payload, facet=facet, eligible_base=len(claims))
    flag = _facet_flag(
        failure=failure,
        rejection_reasons=rejection_reasons if failure is not None else (
            result.rejection_reasons if result is not None else []
        ),
        value_cap_exceeded=failure == "cap_exceeded",
    )
    provenance = _facet_provenance(
        eligible_base_size=len(claims),
        eligible_base_sha256=base_sha,
        call_budget=call_budget,
        calls_used=result.calls_used if result is not None else 0,
        rejection_reasons=(
            rejection_reasons
            if failure is not None
            else (result.rejection_reasons if result is not None else [])
        ),
        projection="claim",
        unit_count=len(claims),
        max_labels=group_max_labels(len(claims)),
        assignment_repair_calls_used=(
            result.assignment_repair_calls_used if result is not None else 0
        ),
    )
    facet_payload = _facet_payload(payload, facet)
    return FacetAssembly(
        payload=payload,
        counts=counts,
        flag=flag,
        provenance=provenance,
        summary_groups=_summary_groups(cast("list[dict[str, Any]]", facet_payload["groups"])),
        summary_residuals=_claim_summary_residuals(facet_payload),
        usage_totals=result.usage_totals if result is not None else UsageAccumulator().payload(),
        expected_finding_ids=finding_ids,
    )


def _cluster_facet_units(
    units: list[ClusterUnit],
    *,
    facet: str,
    projection: ProjectionKind,
    backend_factory: GroupClusteringBackendFactory,
) -> tuple[ClusteringResult | None, FailureClass | None, list[str]]:
    policy = _group_policy(unit_count=len(units))
    backend = backend_factory.for_facet(
        facet=facet,
        projection=projection,
        include_context_in_discovery=len(units) <= GROUP_CONTEXT_DISCOVERY_UNIT_LIMIT,
    )
    try:
        result = cluster_units(units, backend=backend, policy=policy)
    except ClusteringFailure as exc:
        failure = _failure_class(exc)
        return None, failure, [_bounded_reason(str(exc))]
    except Exception as exc:
        return None, "backend_error", [_bounded_reason(f"backend_error: {type(exc).__name__}")]
    return result, None, []


def _group_policy(*, unit_count: int) -> ClusteringPolicy:
    return ClusteringPolicy(
        min_labels=0,
        max_labels=group_max_labels(unit_count),
        assignment_batch_size=GROUP_ASSIGNMENT_BATCH_SIZE,
        # 4-wide assignment fan-out, matching theme_grouping.MAX_CONCURRENT_BATCHES
        # (characterise runs the same engine at this width; batch-order merge is
        # deterministic). Local literal, not an import — avoids a group→corpus edge
        # (task 023 WP10a).
        max_concurrent_batches=4,
        discovery_retry_cap=GROUP_DISCOVERY_RETRY_CAP,
        assignment_repair_cap=GROUP_ASSIGNMENT_REPAIR_CAP,
        residual_label=GROUP_RESIDUAL_LABEL,
        unresolved_policy="residual",
        label_max=LABEL_MAX,
        description_max=DESCRIPTION_MAX,
        forbidden_label_reason=_forbidden_group_label_reason,
        label_noun="group label",
        log_event_prefix="group.clustering",
        rejection_reason_cap=REJECTION_REASON_CAP,
        rejection_detail_max_len=REJECTION_REASON_MAX,
    )


def _forbidden_group_label_reason(index: int, label: str) -> str | None:
    if label.casefold() in FORBIDDEN_GROUP_LABELS:
        return f"group {index} uses forbidden label: {label}"
    # The component's own sentinels: a discovered label equal to the assignment
    # wire word or the engine residual label would collide with the residual
    # channel (mirrors characterise's UNCLUSTERED guard).
    if label.casefold() in (UNGROUPABLE_WIRE_WORD, GROUP_RESIDUAL_LABEL.casefold()):
        return f"group {index} uses reserved label: {label}"
    return None


def _failure_class(exc: ClusteringFailure) -> FailureClass:
    error = exc.error.casefold()
    if "backend_error" in error:
        return "backend_error"
    if "discovery failed" in error:
        return "discovery_exhausted"
    if "assignment" in error or "call budget" in error:
        return "assignment_exhausted"
    return "validation_failed"


def _value_groups_from_result(
    values: Sequence[FacetValue], result: ClusteringResult | None
) -> tuple[list[AcceptedGroup], set[str]]:
    if result is None:
        return [], {value.value_id for value in values}
    groups = _accepted_groups_from_result(
        [value.value_id for value in values],
        result=result,
    )
    return groups, set(result.residual_ids)


def _claim_groups_from_result(
    claims: Sequence[ClaimThemeUnit], result: ClusteringResult | None
) -> tuple[list[AcceptedGroup], list[str]]:
    if result is None:
        return [], [claim.finding_id for claim in claims]
    groups = _accepted_groups_from_result(
        [claim.finding_id for claim in claims],
        result=result,
    )
    return groups, list(result.residual_ids)


def _accepted_groups_from_result(
    ordered_unit_ids: Sequence[str], *, result: ClusteringResult
) -> list[AcceptedGroup]:
    accepted: list[AcceptedGroup] = []
    for label in result.labels:
        member_ids = tuple(
            unit_id
            for unit_id in ordered_unit_ids
            if result.assignments.get(unit_id) == label.label
        )
        if not member_ids:
            continue
        accepted.append(
            AcceptedGroup(
                label=label.label,
                description=label.description,
                member_ids=member_ids,
            )
        )
    return accepted


def _build_value_payload(
    views: Sequence[FindingFacetView],
    *,
    facet: str,
    values: Sequence[FacetValue],
    groups: Sequence[AcceptedGroup],
    ungrouped_value_ids: Collection[str],
    no_value_finding_ids: Sequence[str],
    finding_ids: Collection[str],
) -> dict[str, Any]:
    try:
        payload = build_groups_payload(
            views,
            facet=facet,
            values=values,
            groups=groups,
            ungrouped_value_ids=ungrouped_value_ids,
            no_value_finding_ids=no_value_finding_ids,
        )
        assert_grouping_invariants(payload, finding_ids=finding_ids)
    except InvalidPartitionOutput as exc:
        raise GroupError(f"grouping invariant violated: {exc}") from exc
    return payload


def _build_claim_theme_payload(
    *, facet: str, groups: Sequence[AcceptedGroup], ungrouped_finding_ids: Sequence[str]
) -> dict[str, Any]:
    group_payloads: list[dict[str, Any]] = []
    assigned: set[str] = set()
    for index, group in enumerate(groups, start=1):
        member_ids = list(group.member_ids)
        if not member_ids:
            continue
        if assigned.intersection(member_ids):
            raise GroupError("grouping invariant violated: duplicate claim id")
        assigned.update(member_ids)
        group_payloads.append(
            {
                "group_id": f"{facet}:g{index:02d}",
                "facet": facet,
                "label": group.label,
                "description": group.description,
                "member_finding_ids": member_ids,
                "member_finding_kinds": ["icf" for _ in member_ids],
                "member_counts": {"iof": 0, "icf": len(member_ids)},
                "size": len(member_ids),
                "direction_spread": None,
            }
        )
    ungrouped_ids = list(ungrouped_finding_ids)
    if assigned.intersection(ungrouped_ids):
        raise GroupError("grouping invariant violated: duplicate claim residual id")
    payload = {
        facet: {
            "groups": group_payloads,
            "ungrouped": {
                "finding_ids": ungrouped_ids,
                "member_finding_ids": ungrouped_ids,
                "finding_kinds": ["icf" for _ in ungrouped_ids],
                "member_counts": {"iof": 0, "icf": len(ungrouped_ids)},
                "direction_spread": None,
            },
            "overall_direction_spread": None,
        }
    }
    try:
        assert_grouping_invariants(
            payload,
            finding_ids=[
                finding_id
                for group in group_payloads
                for finding_id in cast("list[str]", group["member_finding_ids"])
            ] + ungrouped_ids,
        )
    except InvalidPartitionOutput as exc:
        raise GroupError(f"grouping invariant violated: {exc}") from exc
    return payload


def _build_value_counts(
    payload: dict[str, Any],
    *,
    facet: str,
    eligible_base: int,
    distinct_values: int,
) -> dict[str, int]:
    facet_payload = _facet_payload(payload, facet)
    groups = cast("list[dict[str, Any]]", facet_payload["groups"])
    ungrouped = cast("dict[str, Any]", facet_payload["ungrouped"])
    no_value = cast("dict[str, Any]", facet_payload["no_value"])
    return {
        "eligible_base": eligible_base,
        "findings_total": eligible_base,
        "grouped": sum(cast("int", group["size"]) for group in groups),
        "ungrouped": len(cast("list[str]", ungrouped["finding_ids"])),
        "no_value": len(cast("list[str]", no_value["finding_ids"])),
        "distinct_values": distinct_values,
        "groups": len(groups),
    }


def _build_claim_counts(
    payload: dict[str, Any], *, facet: str, eligible_base: int
) -> dict[str, int]:
    facet_payload = _facet_payload(payload, facet)
    groups = cast("list[dict[str, Any]]", facet_payload["groups"])
    ungrouped = cast("dict[str, Any]", facet_payload["ungrouped"])
    return {
        "eligible_base": eligible_base,
        "grouped": sum(cast("int", group["size"]) for group in groups),
        "ungrouped": len(cast("list[str]", ungrouped["finding_ids"])),
        "groups": len(groups),
    }


def _facet_flag(
    *,
    failure: FailureClass | None,
    rejection_reasons: Sequence[str],
    value_cap_exceeded: bool,
) -> dict[str, Any]:
    return {
        "status": "failed" if failure is not None else "succeeded",
        "failure_class": failure,
        "groups_rejected": bool(rejection_reasons),
        "value_cap_exceeded": value_cap_exceeded,
    }


def _facet_provenance(
    *,
    eligible_base_size: int,
    eligible_base_sha256: str,
    call_budget: int,
    calls_used: int,
    rejection_reasons: Sequence[str],
    projection: ProjectionKind,
    unit_count: int,
    max_labels: int,
    assignment_repair_calls_used: int,
) -> dict[str, Any]:
    return {
        "eligible_base_size": eligible_base_size,
        "eligible_base_sha256": eligible_base_sha256,
        "call_budget": call_budget,
        "calls_used": calls_used,
        "rejection_reasons": [
            _bounded_reason(reason) for reason in rejection_reasons[:REJECTION_REASON_CAP]
        ],
        "projection": projection,
        "unit_count": unit_count,
        "max_labels": max_labels,
        "assignment_batch_size": GROUP_ASSIGNMENT_BATCH_SIZE,
        "discovery_retry_cap": GROUP_DISCOVERY_RETRY_CAP,
        "assignment_repair_cap": GROUP_ASSIGNMENT_REPAIR_CAP,
        "assignment_repair_calls_used": assignment_repair_calls_used,
    }


def _load_extraction_rollup(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
) -> tuple[
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    row = conn.execute(
        sa_select(
            extraction_result.c.docs,
            extraction_result.c.counts,
            extraction_result.c.extraction_provenance,
        )
        .where(extraction_result.c.project_id == project_id)
        .where(extraction_result.c.evidence_scope_id == scope_id)
        .where(extraction_result.c.run_id == extraction_run_id)
    ).mappings().first()
    if row is None:
        raise GroupError(
            f"no extraction row for scope {scope_id} and extraction_run_id "
            f"{extraction_run_id} — run extract first"
        )

    docs = row["docs"]
    counts = row["counts"]
    provenance = row["extraction_provenance"]
    if not isinstance(docs, list):
        raise GroupError("corrupt reference: extraction_result.docs must be a list")
    if not isinstance(counts, dict):
        raise GroupError("corrupt reference: extraction_result.counts must be an object")
    if not isinstance(provenance, dict):
        raise GroupError(
            "corrupt reference: extraction_result.extraction_provenance must be an object"
        )
    if any(not isinstance(doc, dict) for doc in docs):
        raise GroupError("corrupt reference: extraction_result.docs entries must be objects")
    mapped_docs = cast("list[dict[str, Any]]", docs)
    counts_map = cast("dict[str, Any]", counts)
    provenance_map = cast("dict[str, Any]", provenance)
    counts_profiles = counts_map.get("profiles")
    provenance_profiles = provenance_map.get("profiles")
    if not isinstance(counts_profiles, dict) or IOF_PROFILE_ID not in counts_profiles:
        raise GroupError(
            "corrupt reference: extraction_result.counts missing the IOF profile block"
        )
    if not isinstance(provenance_profiles, dict) or IOF_PROFILE_ID not in provenance_profiles:
        raise GroupError(
            "corrupt reference: extraction_result.extraction_provenance missing "
            "the IOF profile block"
        )
    if set(counts_profiles) != set(provenance_profiles):
        raise GroupError(
            "corrupt reference: extraction_result counts and extraction_provenance "
            "name different profile sets"
        )
    profile_counts: dict[str, dict[str, Any]] = {}
    profile_provenance: dict[str, dict[str, Any]] = {}
    for profile_id, block in counts_profiles.items():
        prov_block = provenance_profiles[profile_id]
        if not isinstance(block, dict) or not isinstance(prov_block, dict):
            raise GroupError(
                f"corrupt reference: extraction_result profile block for {profile_id} "
                "must be an object"
            )
        merged = dict(block)
        for shared_key in ("selected", "basis"):
            if shared_key in counts_map:
                merged[shared_key] = counts_map[shared_key]
        profile_counts[profile_id] = merged
        profile_provenance[profile_id] = dict(prov_block)
    return (
        mapped_docs,
        profile_counts,
        profile_provenance,
        counts_map,
    )


def _extraction_record_ids_by_kind(
    docs: Sequence[dict[str, Any]]
) -> dict[str, list[uuid.UUID]]:
    by_profile = record_ids_by_profile(docs)
    by_kind: dict[str, list[uuid.UUID]] = {"iof": [], "icf": []}
    for kind, profile_id in (("iof", IOF_PROFILE_ID), ("icf", ICF_PROFILE_ID)):
        for raw_id in by_profile.get(profile_id, []):
            if not isinstance(raw_id, str):
                raise GroupError(
                    "corrupt reference: extraction_record_id must be a string"
                )
            try:
                by_kind[kind].append(uuid.UUID(raw_id))
            except ValueError as exc:
                raise GroupError(
                    "corrupt reference: extraction_record_id is not a UUID"
                ) from exc
    return by_kind


def _load_finding_references(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_record_ids_by_kind: Mapping[str, Sequence[uuid.UUID]],
) -> list[Mapping[str, Any]]:
    record_ids = [
        record_id
        for kind in ("iof", "icf")
        for record_id in extraction_record_ids_by_kind.get(kind, ())
    ]
    if not record_ids:
        return []
    rows = conn.execute(
        sa_select(
            finding_reference_union.c.finding_id,
            finding_reference_union.c.kind,
            finding_reference_union.c.extraction_record_id,
            finding_reference_union.c.intervention,
            finding_reference_union.c.outcome,
            finding_reference_union.c.population,
        )
        .where(finding_reference_union.c.project_id == project_id)
        .where(finding_reference_union.c.extraction_record_id.in_(record_ids))
        .order_by(
            finding_reference_union.c.extraction_record_id,
            finding_reference_union.c.finding_id,
        )
    ).mappings().fetchall()
    return [dict(row) for row in rows]


def _load_finding_details(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_record_ids_by_kind: Mapping[str, Sequence[uuid.UUID]],
) -> dict[str, FindingDetail]:
    details: dict[str, FindingDetail] = {}
    iof_record_ids = list(extraction_record_ids_by_kind.get("iof", ()))
    if iof_record_ids:
        rows = conn.execute(
            sa_select(
                intervention_outcome_finding.c.finding_id,
                intervention_outcome_finding.c.effect_direction,
                intervention_outcome_finding.c.grounding,
            )
            .where(intervention_outcome_finding.c.project_id == project_id)
            .where(intervention_outcome_finding.c.extraction_record_id.in_(iof_record_ids))
        ).mappings().fetchall()
        for row in rows:
            details[str(row["finding_id"])] = FindingDetail(
                effect_direction=cast("str", row["effect_direction"]),
                anchors=_anchor_quotes(row["grounding"]),
            )

    icf_record_ids = list(extraction_record_ids_by_kind.get("icf", ()))
    if icf_record_ids:
        rows = conn.execute(
            sa_select(
                implementation_context_finding.c.finding_id,
                implementation_context_finding.c.grounding,
            )
            .where(implementation_context_finding.c.project_id == project_id)
            .where(implementation_context_finding.c.extraction_record_id.in_(icf_record_ids))
        ).mappings().fetchall()
        for row in rows:
            details[str(row["finding_id"])] = FindingDetail(
                effect_direction=None,
                anchors=_anchor_quotes(row["grounding"]),
            )
    return details


def _load_claim_theme_units(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    facet: str,
    extraction_record_ids: Sequence[uuid.UUID],
) -> list[ClaimThemeUnit]:
    if not extraction_record_ids:
        return []
    context_type = CLAIM_THEME_CONTEXT_TYPES[facet]
    rows = conn.execute(
        sa_select(
            implementation_context_finding.c.finding_id,
            implementation_context_finding.c.claim,
            implementation_context_finding.c.context_label,
            implementation_context_finding.c.intervention,
        )
        .where(implementation_context_finding.c.project_id == project_id)
        .where(implementation_context_finding.c.extraction_record_id.in_(extraction_record_ids))
        .where(implementation_context_finding.c.context_type == context_type)
        .order_by(
            implementation_context_finding.c.extraction_record_id,
            implementation_context_finding.c.finding_id,
        )
    ).mappings().fetchall()
    return [
        ClaimThemeUnit(
            finding_id=str(row["finding_id"]),
            claim=cast("str", row["claim"]),
            context_label=cast("str | None", row["context_label"]),
            intervention=cast("str", row["intervention"]),
        )
        for row in rows
    ]


def _project_reference_rows(
    references: Sequence[Mapping[str, Any]],
    *,
    facet: str,
    finding_details: Mapping[str, FindingDetail],
) -> list[FindingFacetView]:
    counterpart = FACET_COUNTERPART[facet]
    views: list[FindingFacetView] = []
    for row in references:
        finding_id = str(row["finding_id"])
        detail = finding_details.get(finding_id)
        views.append(
            FindingFacetView(
                finding_id=finding_id,
                facet_value=cast("str | None", row[facet]),
                counterpart_value=cast("str | None", row[counterpart]),
                effect_direction=detail.effect_direction if detail is not None else None,
                kind=cast("str", row["kind"]),
            )
        )
    return views


def _value_cluster_units(
    values: Sequence[FacetValue],
    *,
    finding_details: Mapping[str, FindingDetail],
) -> list[ClusterUnit]:
    units: list[ClusterUnit] = []
    for value in values:
        units.append(
            ClusterUnit(
                unit_id=value.value_id,
                payload={
                    "id": value.value_id,
                    "text": value.surface,
                    "value": value.surface,
                    "finding_count": len(value.finding_ids),
                    "counterparts": list(value.counterparts),
                    "context": {
                        "anchors": _anchor_context(value.finding_ids, finding_details)
                    },
                },
            )
        )
    return units


def _claim_cluster_units(claims: Sequence[ClaimThemeUnit]) -> list[ClusterUnit]:
    units: list[ClusterUnit] = []
    for claim in claims:
        context: dict[str, str] = {
            "intervention": _bounded_surface(claim.intervention, VALUE_SURFACE_MAX)
        }
        if claim.context_label is not None and claim.context_label.strip():
            context["context_label"] = _bounded_surface(
                claim.context_label, CONTEXT_LABEL_SURFACE_MAX
            )
        text = _bounded_surface(claim.claim, CLAIM_SURFACE_MAX)
        units.append(
            ClusterUnit(
                unit_id=claim.finding_id,
                payload={
                    "id": claim.finding_id,
                    "text": text,
                    "claim": text,
                    "context": context,
                },
            )
        )
    return units


def _bounded_surface(text: str, cap: int) -> str:
    """Bound untrusted source text before it enters a clustering prompt.

    Strips control characters and truncates to ``cap`` — the claim-theme
    sibling of the value path's ``VALUE_SURFACE_MAX`` enforcement (source
    fields carry no length bound at extraction time).
    """
    cleaned = "".join(" " if has_control_character(ch) else ch for ch in text)
    if len(cleaned) > cap:
        return cleaned[: cap - 1] + "…"
    return cleaned


def _anchor_context(
    finding_ids: Sequence[str],
    finding_details: Mapping[str, FindingDetail],
) -> list[dict[str, str]]:
    anchors: list[dict[str, str]] = []
    for finding_id in sorted(finding_ids):
        detail = finding_details.get(finding_id)
        if detail is None:
            continue
        for quote in detail.anchors:
            anchors.append({"finding_id": finding_id, "quote": quote})
            if len(anchors) >= 2:
                return anchors
    return anchors


def _anchor_quotes(raw_grounding: Any) -> tuple[str, ...]:
    if not isinstance(raw_grounding, list):
        return ()
    quotes: list[str] = []
    for entry in raw_grounding:
        if not isinstance(entry, dict):
            continue
        quote = entry.get("quote")
        if isinstance(quote, str) and quote:
            quotes.append(quote[:240])
        if len(quotes) >= 2:
            break
    return tuple(quotes)


def _value_surface_error(values: Sequence[FacetValue]) -> str | None:
    for value in values:
        if len(value.surface) > VALUE_SURFACE_MAX:
            return (
                "value_surface_too_long: "
                f"facet value {value.value_id} exceeds {VALUE_SURFACE_MAX} chars"
            )
        for counterpart in value.counterparts:
            if len(counterpart) > VALUE_SURFACE_MAX:
                return (
                    "value_surface_too_long: "
                    f"facet value {value.value_id} counterpart exceeds "
                    f"{VALUE_SURFACE_MAX} chars"
                )
    return None


def _extraction_findings_total(counts: dict[str, Any]) -> int:
    findings = counts.get("findings")
    if not isinstance(findings, dict):
        raise GroupError("corrupt reference: extraction counts missing findings object")
    total = findings.get("total")
    if not isinstance(total, int):
        raise GroupError("corrupt reference: extraction counts missing findings.total")
    return total


def _all_extraction_findings_total(counts: dict[str, Any]) -> int:
    profiles = counts.get("profiles")
    if isinstance(profiles, dict):
        total = 0
        for profile_id in (IOF_PROFILE_ID, ICF_PROFILE_ID):
            block = profiles.get(profile_id)
            if not isinstance(block, dict):
                continue
            total += _extraction_findings_total(block)
        return total
    return _extraction_findings_total(counts)


def _extraction_base_counts(counts: dict[str, Any]) -> dict[str, int]:
    return {
        "selected": _required_int(counts, "selected", "extraction counts"),
        "extracted": _required_int(counts, "extracted", "extraction counts"),
        "no_findings": _required_int(counts, "no_findings", "extraction counts"),
        "failed": _required_int(counts, "failed", "extraction counts"),
        "findings_total": _extraction_findings_total(counts),
    }


def _required_int(payload: dict[str, Any], key: str, source: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise GroupError(f"corrupt reference: {source} missing integer {key}")
    return value


def _required_str(payload: dict[str, Any], key: str, source: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise GroupError(f"corrupt reference: {source} missing string {key}")
    return value


def _build_provenance(
    *,
    backend: GroupClusteringBackendFactory,
    facets: Sequence[str],
    facet_source: str,
    facet_provenance: Mapping[str, dict[str, Any]],
    extraction_run_id: uuid.UUID,
    extraction_profile_counts: dict[str, dict[str, Any]],
    extraction_profile_provenance: dict[str, dict[str, Any]],
    finding_ids: Sequence[str],
) -> dict[str, Any]:
    mode = backend.mode
    model = str(getattr(backend, "model", mode))
    rejection_reasons = [
        reason
        for facet in facets
        for reason in facet_provenance[facet]["rejection_reasons"]
    ][:REJECTION_REASON_CAP]
    return {
        "prompt_version": GROUP_PROMPT_VERSION,
        "model": model,
        "mode": mode,
        "facet": facets[0] if len(facets) == 1 else None,
        "facets": list(facets),
        "facet_source": facet_source,
        "value_cap": FACET_VALUE_CAP,
        "call_count": sum(
            cast("int", facet_provenance[facet]["calls_used"]) for facet in facets
        ),
        "repair_count": sum(
            cast("int", facet_provenance[facet]["assignment_repair_calls_used"])
            for facet in facets
        ),
        "rejection_reasons": rejection_reasons,
        "distinct_value_count": sum(
            cast("int", facet_provenance[facet]["unit_count"])
            for facet in facets
            if facet_provenance[facet]["projection"] == "value"
        ),
        "extraction_run_id": str(extraction_run_id),
        "facet_runs": {facet: facet_provenance[facet] for facet in facets},
        "extraction_base": {
            "profiles": {
                profile_id: {
                    "extraction_fingerprint": _required_str(
                        extraction_profile_provenance[profile_id],
                        "fingerprint",
                        f"extraction provenance [{profile_id}]",
                    ),
                    "counts": _extraction_base_counts(
                        extraction_profile_counts[profile_id]
                    ),
                }
                for profile_id in sorted(extraction_profile_provenance)
            },
            "finding_set": {
                "size": len(finding_ids),
                "sha256": _finding_set_sha256(finding_ids),
            },
        },
    }


def _build_summary(
    *,
    facets: Sequence[str],
    facet_source: str,
    groups: Mapping[str, list[dict[str, Any]]],
    residuals: Mapping[str, dict[str, Any]],
    counts: Mapping[str, dict[str, int]],
    flags: Mapping[str, dict[str, Any]],
    extraction_run_id: uuid.UUID,
    provenance: dict[str, Any],
    usage_totals: dict[str, int],
) -> dict[str, Any]:
    return {
        "facet": facets[0] if len(facets) == 1 else None,
        "facets": list(facets),
        "facet_source": facet_source,
        "groups": {facet: groups[facet] for facet in facets},
        "residuals": {facet: residuals[facet] for facet in facets},
        "counts": {facet: counts[facet] for facet in facets},
        "flags": {facet: flags[facet] for facet in facets},
        "extraction_run_id": str(extraction_run_id),
        "provenance": provenance,
        "usage_totals": usage_totals,
    }


def _summary_groups(groups: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "group_id": cast("str", group["group_id"]),
            "facet": cast("str", group["facet"]),
            "label": cast("str", group["label"]),
            "size": cast("int", group["size"]),
            "value_count": len(cast("list[str]", group.get("member_values", []))),
            "direction_spread": group["direction_spread"],
        }
        for group in groups
    ]


def _value_summary_residuals(facet_payload: dict[str, Any]) -> dict[str, Any]:
    ungrouped = cast("dict[str, Any]", facet_payload["ungrouped"])
    no_value = cast("dict[str, Any]", facet_payload["no_value"])
    return {
        "ungrouped": {
            "value_count": len(cast("list[str]", ungrouped["values"])),
            "finding_count": len(cast("list[str]", ungrouped["finding_ids"])),
            "direction_spread": ungrouped["direction_spread"],
        },
        "no_value": {
            "finding_count": len(cast("list[str]", no_value["finding_ids"])),
            "direction_spread": no_value["direction_spread"],
        },
        "overall_direction_spread": facet_payload["overall_direction_spread"],
    }


def _claim_summary_residuals(facet_payload: dict[str, Any]) -> dict[str, Any]:
    ungrouped = cast("dict[str, Any]", facet_payload["ungrouped"])
    return {
        "ungrouped": {
            "finding_count": len(cast("list[str]", ungrouped["finding_ids"])),
            "direction_spread": None,
        },
        "overall_direction_spread": None,
    }


def _finding_set_sha256(finding_ids: Sequence[str]) -> str:
    material = "\n".join(sorted(finding_ids)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _value_base_sha256(views: Sequence[FindingFacetView]) -> str:
    material = [
        {
            "finding_id": view.finding_id,
            "kind": view.kind,
            "facet_value": view.facet_value,
            "counterpart_value": view.counterpart_value,
        }
        for view in sorted(views, key=lambda item: item.finding_id)
    ]
    return _json_sha256(material)


def claim_theme_base_sha256(claims: Sequence[ClaimThemeUnit]) -> str:
    """Hash the claim-theme eligible base content deterministically.

    Args:
        claims: Eligible ICF claim units.

    Returns:
        SHA-256 over stable JSON containing id, prose and context fields.
    """
    material = [
        {
            "finding_id": claim.finding_id,
            "claim": claim.claim,
            "context_label": claim.context_label,
            "intervention": claim.intervention,
        }
        for claim in sorted(claims, key=lambda item: item.finding_id)
    ]
    return _json_sha256(material)


def _json_sha256(material: Any) -> str:
    encoded = json.dumps(
        material,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _facet_payload(payload: dict[str, Any], facet: str) -> dict[str, Any]:
    value = payload.get(facet)
    if not isinstance(value, dict):
        raise GroupError(f"grouping invariant violated: missing facet payload {facet}")
    return value


def _unit_text(unit: ClusterUnit) -> str:
    payload = unit.payload
    if isinstance(payload, Mapping):
        text = payload.get("text")
        if isinstance(text, str):
            return text
    return ""


def _stub_token(text: str) -> str | None:
    parts = text.split()
    if not parts:
        return None
    token = parts[0].casefold()[:LABEL_MAX]
    if token.startswith("stubungroupable"):
        return None
    return token


def _payload_copy(payload: Any, *, include_context: bool) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    copied = dict(payload)
    context = copied.get("context")
    if isinstance(context, Mapping):
        copied["context"] = dict(context) if include_context else {}
    elif not include_context:
        copied["context"] = {}
    return copied


def _bounded_reason(reason: str) -> str:
    return reason[:REJECTION_REASON_MAX]
