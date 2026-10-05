"""Shared two-stage clustering coordination and validation.

The engine owns the common shape used by clustering components: discover labels
openly, then assign known units in bounded batches with deterministic validation.
Prompt construction and substrate-specific payload rendering stay behind backend
adapters; the engine only reads opaque unit ids plus label/description text.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from typing import Any, Literal, Protocol

import structlog

from policy_atlas.core import tracing
from policy_atlas.core.tags import has_control_character
from policy_atlas.core.usage import UsageAccumulator, UsageResult

log = structlog.get_logger()

_DEFAULT_REJECTION_DETAIL_MAX_LEN = 500
_DEFAULT_REJECTION_REASON_CAP = 20


@dataclass(frozen=True)
class ClusterUnit:
    """One clustering unit with an opaque id and prompt-facing payload.

    Attributes:
        unit_id: Stable id used for assignment validation.
        payload: Substrate-specific prompt payload; not inspected by the engine.
    """

    unit_id: str
    payload: Any


@dataclass(frozen=True)
class ClusterLabel:
    """One discovered clustering label.

    Attributes:
        label: Short label copied exactly during assignment.
        description: One-line description of the label.
    """

    label: str
    description: str


@dataclass(frozen=True)
class ClusterAssignment:
    """One raw assignment returned by a backend.

    Attributes:
        unit_id: Opaque unit id being assigned.
        label: Discovered label or the component residual label.
    """

    unit_id: str
    label: str


type AssignmentOutput = Mapping[str, str] | Sequence[ClusterAssignment]


class ClusteringBackend(Protocol):
    """Backend seam for two-stage clustering.

    Implementations build component-specific prompts and parse provider output
    structurally. The engine performs semantic validation and retry/repair
    coordination.
    """

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        """Discover labels for a unit set.

        Args:
            units: Units to cluster, in deterministic order.
            min_labels: Minimum accepted label count.
            max_labels: Maximum accepted label count.

        Returns:
            Raw discovered labels and token usage.
        """
        ...

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[AssignmentOutput]:
        """Assign one batch to fixed labels.

        Args:
            batch: Units to assign, in deterministic order.
            labels: Validated labels discovered in stage 1.

        Returns:
            Raw id-to-label assignments and token usage.
        """
        ...


class InvalidDiscoveryOutput(ValueError):
    """Discovery output violated code-enforced label constraints."""


class ClusteringFailure(Exception):
    """Failure raised when clustering cannot produce a valid result.

    Attributes:
        error: Machine-readable failure summary.
    """

    error: str

    def __init__(self, error: str) -> None:
        """Create a clustering failure.

        Args:
            error: Failure summary.
        """
        super().__init__(error)
        self.error = error


@dataclass(frozen=True)
class CallBudgetPlan:
    """Computed model-call budget for one clustering run.

    Attributes:
        batch_count: Assignment batch count for the unit set.
        baseline: Calls expected without retries or repairs.
        maximum: Hard call ceiling including discovery retries and repairs.
    """

    batch_count: int
    baseline: int
    maximum: int


@dataclass
class CallBudget:
    """Mutable call budget guard.

    Attributes:
        maximum: Maximum calls allowed.
        count: Calls reserved so far.
    """

    maximum: int
    count: int = 0

    def reserve(self) -> None:
        """Reserve one model call.

        Raises:
            ClusteringFailure: If the call budget has already been exhausted.
        """
        if self.count >= self.maximum:
            raise ClusteringFailure("call budget exceeded")
        self.count += 1


@dataclass(frozen=True)
class ClusteringPolicy:
    """Validation and coordination policy for one clustering caller.

    Attributes:
        min_labels: Minimum accepted discovery label count.
        max_labels: Maximum accepted discovery label count.
        assignment_batch_size: Maximum known units in one assignment call.
        discovery_retry_cap: Discovery retries after the first attempt.
        assignment_repair_cap: Repair calls after the first assignment attempt,
            per batch.
        residual_label: Label used by the component for unplaced units.
        unresolved_policy: ``"fail"`` raises if repair leaves unplaced units;
            ``"residual"`` assigns them to ``residual_label``.
        label_max: Maximum label length in characters.
        description_max: Maximum description length in characters.
        label_key: Normalizer used for duplicate-label detection.
        forbidden_label_reason: Hook returning a rejection reason for a label,
            or ``None`` when the label is allowed.
        label_noun: Noun used in validation error strings.
        log_event_prefix: Prefix for structlog events emitted by the engine.
        max_concurrent_batches: Worker count for first-round assignment fan-out.
        rejection_reason_cap: Maximum rejection details retained in the result.
        rejection_detail_max_len: Maximum length of one retained rejection detail.
    """

    min_labels: int
    max_labels: int
    assignment_batch_size: int
    discovery_retry_cap: int
    assignment_repair_cap: int
    residual_label: str
    unresolved_policy: Literal["fail", "residual"]
    label_max: int
    description_max: int
    label_key: Callable[[str], str] = str.casefold
    forbidden_label_reason: Callable[[int, str], str | None] = lambda _index, _label: None
    label_noun: str = "label"
    log_event_prefix: str = "clustering"
    max_concurrent_batches: int = 1
    rejection_reason_cap: int = _DEFAULT_REJECTION_REASON_CAP
    rejection_detail_max_len: int = _DEFAULT_REJECTION_DETAIL_MAX_LEN


@dataclass(frozen=True)
class ClusteringResult:
    """Completed clustering result.

    Attributes:
        labels: Validated discovered labels.
        assignments: Exhaustive unit assignment mapping, including residual
            assignments.
        residual_ids: Unit ids assigned to the residual label.
        discovery_retries_used: Count of discovery retries consumed before
            success.
        assignment_repair_calls_used: Count of assignment repair calls made.
        discovery_rejections: Bounded discovery rejection details.
        rejection_reasons: Bounded rejection details across discovery and
            assignment validation.
        call_budget: Computed call-budget plan.
        calls_used: Calls reserved by the engine.
        usage_totals: Token-usage totals accumulated from successful backend
            calls.
    """

    labels: list[ClusterLabel]
    assignments: dict[str, str]
    residual_ids: list[str]
    discovery_retries_used: int
    assignment_repair_calls_used: int
    discovery_rejections: list[str]
    rejection_reasons: list[str]
    call_budget: CallBudgetPlan
    calls_used: int
    usage_totals: dict[str, int]


@dataclass(frozen=True)
class AssignmentAttempt:
    """One first-round assignment attempt.

    Attributes:
        batch_index: One-based batch index.
        batch: Units assigned by the attempt.
        assignments: Raw backend assignments, or ``None`` when the call failed.
        error_type: Exception type name when the call failed.
        error_detail: Bounded exception detail when the call failed.
    """

    batch_index: int
    batch: list[ClusterUnit]
    assignments: AssignmentOutput | None
    error_type: str | None
    error_detail: str | None = None


@dataclass(frozen=True)
class AssignmentValidation:
    """Validated assignment response plus repair-driving residue.

    Attributes:
        valid: Accepted unit-id to label assignments.
        residue: Units requiring repair or residual placement.
        invented_count: Assignments naming ids outside the known batch.
        missing_count: Known batch ids omitted from the response.
        unknown_label_count: Assignments naming labels outside the fixed list.
        conflicting_count: Known ids assigned to conflicting labels.
        duplicate_same_label_count: Duplicate same-label assignments ignored.
    """

    valid: dict[str, str]
    residue: list[ClusterUnit]
    invented_count: int
    missing_count: int
    unknown_label_count: int
    conflicting_count: int
    duplicate_same_label_count: int


def call_budget_for_unit_count(
    unit_count: int,
    *,
    assignment_batch_size: int,
    discovery_retry_cap: int,
    assignment_repair_cap: int,
) -> CallBudgetPlan:
    """Compute the hard call budget for a clustering run.

    Args:
        unit_count: Number of units to cluster.
        assignment_batch_size: Maximum units per assignment call.
        discovery_retry_cap: Discovery retries after the first attempt.
        assignment_repair_cap: Repair calls after the first assignment attempt,
            per batch.

    Returns:
        Batch count, no-retry baseline and hard maximum call count.

    Raises:
        ValueError: If counts or caps are invalid.
    """
    if unit_count < 0:
        raise ValueError("unit_count must be non-negative")
    if assignment_batch_size <= 0:
        raise ValueError("assignment_batch_size must be positive")
    if discovery_retry_cap < 0:
        raise ValueError("discovery_retry_cap must be non-negative")
    if assignment_repair_cap < 0:
        raise ValueError("assignment_repair_cap must be non-negative")

    batch_count = math.ceil(unit_count / assignment_batch_size)
    baseline = 1 + batch_count
    maximum = 1 + discovery_retry_cap + batch_count * (1 + assignment_repair_cap)
    return CallBudgetPlan(batch_count=batch_count, baseline=baseline, maximum=maximum)


def validate_discovered_labels(
    labels: list[ClusterLabel],
    *,
    policy: ClusteringPolicy,
) -> list[ClusterLabel]:
    """Validate and normalize discovered labels.

    Args:
        labels: Candidate labels from discovery output.
        policy: Component validation policy.

    Returns:
        Labels with label and description stripped.

    Raises:
        InvalidDiscoveryOutput: If count, length, control-character, duplicate
            or forbidden-label constraints are violated.
    """
    _validate_policy(policy)
    if not policy.min_labels <= len(labels) <= policy.max_labels:
        raise InvalidDiscoveryOutput(
            f"{policy.label_noun} count {len(labels)} outside bounds "
            f"[{policy.min_labels}, {policy.max_labels}]"
        )

    normalized: list[ClusterLabel] = []
    seen_labels: set[str] = set()
    for index, candidate in enumerate(labels):
        label = candidate.label.strip()
        description = candidate.description.strip()
        if not label:
            raise InvalidDiscoveryOutput(f"{policy.label_noun} {index} has empty name")
        if not description:
            raise InvalidDiscoveryOutput(
                f"{policy.label_noun} {index} has empty description"
            )
        if len(label) > policy.label_max:
            raise InvalidDiscoveryOutput(
                f"{policy.label_noun} {index} name exceeds {policy.label_max} chars"
            )
        if len(description) > policy.description_max:
            raise InvalidDiscoveryOutput(
                f"{policy.label_noun} {index} description exceeds "
                f"{policy.description_max} chars"
            )
        if has_control_character(label):
            raise InvalidDiscoveryOutput(
                f"{policy.label_noun} {index} name contains a control character"
            )
        if has_control_character(description):
            raise InvalidDiscoveryOutput(
                f"{policy.label_noun} {index} description contains a control character"
            )
        forbidden_reason = policy.forbidden_label_reason(index, label)
        if forbidden_reason is not None:
            raise InvalidDiscoveryOutput(forbidden_reason)
        label_key = policy.label_key(label)
        if label_key in seen_labels:
            raise InvalidDiscoveryOutput(f"duplicate {policy.label_noun} name: {label}")
        seen_labels.add(label_key)
        normalized.append(ClusterLabel(label=label, description=description))
    return normalized


def cluster_units(
    units: list[ClusterUnit],
    *,
    backend: ClusteringBackend,
    policy: ClusteringPolicy,
) -> ClusteringResult:
    """Cluster units with open discovery and validated batched assignment.

    Args:
        units: Units to cluster, in deterministic order.
        backend: Component-specific backend adapter.
        policy: Bounds, validation and repair policy.

    Returns:
        Validated clustering result with exhaustive assignments.

    Raises:
        ClusteringFailure: If discovery exhausts, assignment exhausts, call
            budget is exceeded, or input ids are not unique.
        ValueError: If policy parameters are invalid.
    """
    _validate_policy(policy)
    _validate_units(units)
    budget_plan = call_budget_for_unit_count(
        len(units),
        assignment_batch_size=policy.assignment_batch_size,
        discovery_retry_cap=policy.discovery_retry_cap,
        assignment_repair_cap=policy.assignment_repair_cap,
    )
    budget = CallBudget(maximum=budget_plan.maximum)
    usage_totals = UsageAccumulator()

    if not units:
        return ClusteringResult(
            labels=[],
            assignments={},
            residual_ids=[],
            discovery_retries_used=0,
            assignment_repair_calls_used=0,
            discovery_rejections=[],
            rejection_reasons=[],
            call_budget=budget_plan,
            calls_used=budget.count,
            usage_totals=usage_totals.payload(),
        )

    discovery_rejections: list[str] = []
    rejection_reasons: list[str] = []
    labels, discovery_retries_used = _discover_labels(
        backend=backend,
        units=units,
        policy=policy,
        budget=budget,
        usage_totals=usage_totals,
        discovery_rejections=discovery_rejections,
        rejection_reasons=rejection_reasons,
    )
    if not labels:
        assignments = {unit.unit_id: policy.residual_label for unit in units}
        return ClusteringResult(
            labels=[],
            assignments=assignments,
            residual_ids=[unit.unit_id for unit in units],
            discovery_retries_used=discovery_retries_used,
            assignment_repair_calls_used=0,
            discovery_rejections=discovery_rejections,
            rejection_reasons=rejection_reasons,
            call_budget=budget_plan,
            calls_used=budget.count,
            usage_totals=usage_totals.payload(),
        )

    assignments, repair_calls_used = _assign_units(
        backend=backend,
        units=units,
        labels=labels,
        policy=policy,
        budget=budget,
        usage_totals=usage_totals,
        rejection_reasons=rejection_reasons,
    )
    residual_ids = [
        unit.unit_id for unit in units if assignments.get(unit.unit_id) == policy.residual_label
    ]
    return ClusteringResult(
        labels=labels,
        assignments=assignments,
        residual_ids=residual_ids,
        discovery_retries_used=discovery_retries_used,
        assignment_repair_calls_used=repair_calls_used,
        discovery_rejections=discovery_rejections,
        rejection_reasons=rejection_reasons,
        call_budget=budget_plan,
        calls_used=budget.count,
        usage_totals=usage_totals.payload(),
    )


def run_first_assignment_round(
    *,
    backend: ClusteringBackend,
    batches: list[list[ClusterUnit]],
    labels: list[ClusterLabel],
    budget: CallBudget,
    policy: ClusteringPolicy,
) -> tuple[list[AssignmentAttempt], dict[str, int]]:
    """Run first-round assignment batches concurrently.

    Args:
        backend: Component-specific backend adapter.
        batches: Assignment batches.
        labels: Validated labels discovered in stage 1.
        budget: Mutable call budget guard.
        policy: Engine policy carrying concurrency and log-event settings.

    Returns:
        Assignment attempts in batch order plus first-round usage totals.

    Raises:
        ClusteringFailure: If reserving first-round calls exceeds the budget.
    """
    for _batch in batches:
        budget.reserve()

    submitted: list[tuple[int, list[ClusterUnit], Future[Any]]] = []
    usage_totals = UsageAccumulator()
    with ThreadPoolExecutor(max_workers=policy.max_concurrent_batches) as executor:
        for batch_index, batch in enumerate(batches, start=1):
            submitted.append(
                (
                    batch_index,
                    batch,
                    tracing.submit_with_context(
                        executor, backend.assign, batch, labels=labels
                    ),
                )
            )
        wait([future for _, _, future in submitted])

    attempts: list[AssignmentAttempt] = []
    for batch_index, batch, future in submitted:
        try:
            assignments, usage = future.result()
            usage_totals.add(usage)
        except Exception as exc:
            error_detail = _truncate_detail(str(exc), max_len=policy.rejection_detail_max_len)
            log.warning(
                f"{policy.log_event_prefix}.assignment_batch_failed",
                batch_index=batch_index,
                batch_size=len(batch),
                error_type=type(exc).__name__,
                error=error_detail,
            )
            attempts.append(
                AssignmentAttempt(
                    batch_index=batch_index,
                    batch=batch,
                    assignments=None,
                    error_type=type(exc).__name__,
                    error_detail=error_detail,
                )
            )
        else:
            attempts.append(
                AssignmentAttempt(
                    batch_index=batch_index,
                    batch=batch,
                    assignments=assignments,
                    error_type=None,
                )
            )
    return attempts, usage_totals.payload()


def validate_assignments(
    batch: list[ClusterUnit],
    assignments: AssignmentOutput,
    *,
    labels: list[ClusterLabel],
    policy: ClusteringPolicy,
) -> AssignmentValidation:
    """Validate assignments for one known batch.

    Args:
        batch: Deterministically known batch units.
        assignments: Backend assignment output.
        labels: Valid discovered labels.
        policy: Engine policy carrying the residual label.

    Returns:
        Valid assignments plus units requiring repair or residual placement.
    """
    batch_ids = {unit.unit_id for unit in batch}
    label_names = {label.label for label in labels}
    valid: dict[str, str] = {}
    residue_ids: set[str] = set()
    invented_count = 0
    unknown_label_count = 0
    raw_assignments, duplicate_same_label_count, conflicting_count = _normalize_assignments(
        assignments,
        allowed_ids=batch_ids,
    )
    residue_ids.update(
        unit_id for unit_id, label in raw_assignments.items() if label == _CONFLICTED_LABEL
    )

    for unit_id, label in raw_assignments.items():
        if unit_id not in batch_ids:
            invented_count += 1
            continue
        if label == _CONFLICTED_LABEL:
            continue
        if label == policy.residual_label or label in label_names:
            valid[unit_id] = label
        else:
            residue_ids.add(unit_id)
            unknown_label_count += 1

    missing_ids = batch_ids - set(valid) - residue_ids
    residue_ids.update(missing_ids)
    residue = [unit for unit in batch if unit.unit_id in residue_ids]
    return AssignmentValidation(
        valid=valid,
        residue=residue,
        invented_count=invented_count,
        missing_count=len(missing_ids),
        unknown_label_count=unknown_label_count,
        conflicting_count=conflicting_count,
        duplicate_same_label_count=duplicate_same_label_count,
    )


_CONFLICTED_LABEL = "\0conflicted-assignment"


def _discover_labels(
    *,
    backend: ClusteringBackend,
    units: list[ClusterUnit],
    policy: ClusteringPolicy,
    budget: CallBudget,
    usage_totals: UsageAccumulator,
    discovery_rejections: list[str],
    rejection_reasons: list[str],
) -> tuple[list[ClusterLabel], int]:
    for attempt in range(policy.discovery_retry_cap + 1):
        budget.reserve()
        try:
            raw_labels, usage = backend.discover(
                units,
                min_labels=policy.min_labels,
                max_labels=policy.max_labels,
            )
            usage_totals.add(usage)
            labels = validate_discovered_labels(raw_labels, policy=policy)
        except InvalidDiscoveryOutput as exc:
            error_type = type(exc).__name__
            error_detail = _truncate_detail(
                str(exc), max_len=policy.rejection_detail_max_len
            )
            _append_rejection(discovery_rejections, error_detail, policy=policy)
            _append_rejection(rejection_reasons, error_detail, policy=policy)
        except Exception as exc:
            error_type = type(exc).__name__
            error_detail = _truncate_detail(
                str(exc), max_len=policy.rejection_detail_max_len
            )
            _append_rejection(discovery_rejections, error_detail, policy=policy)
            _append_rejection(rejection_reasons, error_detail, policy=policy)
        else:
            return labels, attempt
        log.warning(
            f"{policy.log_event_prefix}.discovery_invalid",
            attempt=attempt + 1,
            retry_cap=policy.discovery_retry_cap,
            error_type=error_type,
            error=error_detail,
        )
    last_detail = discovery_rejections[-1] if discovery_rejections else "no detail captured"
    raise ClusteringFailure(
        f"discovery failed after {policy.discovery_retry_cap + 1} attempts: {last_detail}"
    )


def _assign_units(
    *,
    backend: ClusteringBackend,
    units: list[ClusterUnit],
    labels: list[ClusterLabel],
    policy: ClusteringPolicy,
    budget: CallBudget,
    usage_totals: UsageAccumulator,
    rejection_reasons: list[str],
) -> tuple[dict[str, str], int]:
    first_round, first_round_usage = run_first_assignment_round(
        backend=backend,
        batches=_batches(units, batch_size=policy.assignment_batch_size),
        labels=labels,
        budget=budget,
        policy=policy,
    )
    usage_totals.add_payload(first_round_usage)

    assignments: dict[str, str] = {}
    repair_calls_used = 0
    for attempt in first_round:
        batch_assignments, repair_rounds = _resolve_assignment_batch(
            backend=backend,
            attempt=attempt,
            labels=labels,
            policy=policy,
            budget=budget,
            usage_totals=usage_totals,
            rejection_reasons=rejection_reasons,
        )
        assignments.update(batch_assignments)
        repair_calls_used += repair_rounds
    return assignments, repair_calls_used


def _resolve_assignment_batch(
    *,
    backend: ClusteringBackend,
    attempt: AssignmentAttempt,
    labels: list[ClusterLabel],
    policy: ClusteringPolicy,
    budget: CallBudget,
    usage_totals: UsageAccumulator,
    rejection_reasons: list[str],
) -> tuple[dict[str, str], int]:
    validation = validate_assignments(
        attempt.batch,
        attempt.assignments or {},
        labels=labels,
        policy=policy,
    )
    _record_assignment_rejections(validation, rejection_reasons, policy=policy)

    if not validation.residue:
        return validation.valid, 0

    log.info(
        f"{policy.log_event_prefix}.assignment_repair",
        batch_index=attempt.batch_index,
        residue_count=len(validation.residue),
        invented_count=validation.invented_count,
        missing_count=validation.missing_count,
        unknown_theme_count=validation.unknown_label_count,
        conflicting_count=validation.conflicting_count,
        duplicate_same_label_count=validation.duplicate_same_label_count,
        first_error_type=attempt.error_type,
        first_error_detail=attempt.error_detail,
    )
    merged = dict(validation.valid)
    residue = validation.residue
    repair_rounds = 0
    for _ in range(policy.assignment_repair_cap):
        if not residue:
            break
        budget.reserve()
        try:
            repair_assignments, usage = backend.assign(residue, labels=labels)
            usage_totals.add(usage)
        except Exception as exc:
            error_detail = _truncate_detail(
                str(exc), max_len=policy.rejection_detail_max_len
            )
            raise ClusteringFailure(
                "assignment repair failed for batch "
                f"{attempt.batch_index}: {type(exc).__name__}: {error_detail}"
            ) from exc
        repair_rounds += 1
        repair_validation = validate_assignments(
            residue,
            repair_assignments,
            labels=labels,
            policy=policy,
        )
        _record_assignment_rejections(repair_validation, rejection_reasons, policy=policy)
        merged.update(repair_validation.valid)
        residue = repair_validation.residue

    if residue:
        return _handle_unresolved_after_repair(
            merged,
            residue,
            batch_index=attempt.batch_index,
            policy=policy,
        ), repair_rounds
    return merged, repair_rounds


def _handle_unresolved_after_repair(
    valid: dict[str, str],
    residue: list[ClusterUnit],
    *,
    batch_index: int,
    policy: ClusteringPolicy,
) -> dict[str, str]:
    if policy.unresolved_policy == "fail":
        raise ClusteringFailure(
            f"assignment repair left {len(residue)} unresolved docs in batch {batch_index}"
        )
    merged = dict(valid)
    for unit in residue:
        merged[unit.unit_id] = policy.residual_label
    return merged


def _normalize_assignments(
    assignments: AssignmentOutput,
    *,
    allowed_ids: set[str],
) -> tuple[dict[str, str], int, int]:
    if isinstance(assignments, Mapping):
        return dict(assignments), 0, 0

    normalized: dict[str, str] = {}
    conflicted_ids: set[str] = set()
    duplicate_same_label_count = 0
    conflicting_count = 0
    for assignment in assignments:
        unit_id = assignment.unit_id
        label = assignment.label
        if unit_id not in allowed_ids:
            normalized[unit_id] = label
            continue
        if unit_id in conflicted_ids:
            continue
        existing = normalized.get(unit_id)
        if existing is None:
            normalized[unit_id] = label
        elif existing == label:
            duplicate_same_label_count += 1
        else:
            normalized[unit_id] = _CONFLICTED_LABEL
            conflicted_ids.add(unit_id)
            conflicting_count += 1
    return normalized, duplicate_same_label_count, conflicting_count


def _record_assignment_rejections(
    validation: AssignmentValidation,
    rejection_reasons: list[str],
    *,
    policy: ClusteringPolicy,
) -> None:
    if validation.invented_count:
        _append_rejection(
            rejection_reasons,
            f"assignment invented {validation.invented_count} unknown ids",
            policy=policy,
        )
    if validation.unknown_label_count:
        _append_rejection(
            rejection_reasons,
            f"assignment used {validation.unknown_label_count} unknown labels",
            policy=policy,
        )
    if validation.missing_count:
        _append_rejection(
            rejection_reasons,
            f"assignment omitted {validation.missing_count} known ids",
            policy=policy,
        )
    if validation.conflicting_count:
        _append_rejection(
            rejection_reasons,
            f"assignment had {validation.conflicting_count} conflicting duplicate ids",
            policy=policy,
        )


def _batches(units: list[ClusterUnit], *, batch_size: int) -> list[list[ClusterUnit]]:
    return [units[start:start + batch_size] for start in range(0, len(units), batch_size)]


def _append_rejection(
    rejection_reasons: list[str], detail: str, *, policy: ClusteringPolicy
) -> None:
    if len(rejection_reasons) >= policy.rejection_reason_cap:
        return
    rejection_reasons.append(
        _truncate_detail(detail, max_len=policy.rejection_detail_max_len)
    )


def _truncate_detail(text: str, *, max_len: int) -> str:
    return text[:max_len]


def _validate_policy(policy: ClusteringPolicy) -> None:
    if policy.min_labels < 0:
        raise ValueError("min_labels must be non-negative")
    if policy.max_labels < policy.min_labels:
        raise ValueError("max_labels must be greater than or equal to min_labels")
    if policy.assignment_batch_size <= 0:
        raise ValueError("assignment_batch_size must be positive")
    if policy.discovery_retry_cap < 0:
        raise ValueError("discovery_retry_cap must be non-negative")
    if policy.assignment_repair_cap < 0:
        raise ValueError("assignment_repair_cap must be non-negative")
    if policy.label_max <= 0:
        raise ValueError("label_max must be positive")
    if policy.description_max <= 0:
        raise ValueError("description_max must be positive")
    if policy.max_concurrent_batches <= 0:
        raise ValueError("max_concurrent_batches must be positive")
    if policy.rejection_reason_cap < 0:
        raise ValueError("rejection_reason_cap must be non-negative")
    if policy.rejection_detail_max_len <= 0:
        raise ValueError("rejection_detail_max_len must be positive")


def _validate_units(units: list[ClusterUnit]) -> None:
    seen: set[str] = set()
    for unit in units:
        if unit.unit_id in seen:
            raise ClusteringFailure(f"duplicate unit id {unit.unit_id}")
        seen.add(unit.unit_id)
