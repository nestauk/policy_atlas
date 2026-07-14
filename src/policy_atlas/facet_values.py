"""Pure helpers for grouping extracted findings by source-named facet values."""

from __future__ import annotations

from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

from policy_atlas.facet_grouping import (
    DESCRIPTION_MAX,
    FORBIDDEN_GROUP_LABELS,
    LABEL_MAX,
    FacetValueRecord,
    PartitionResult,
)
from policy_atlas.schema import DIRECTIVE_STRING_MAX, EFFECT_DIRECTIONS, GROUPING_FACETS
from policy_atlas.tags import has_control_character

COUNTERPART_CAP = 5
DEFAULT_FACET = "intervention"
DEFAULT_FACETS = (DEFAULT_FACET,)
FACET_COUNTERPART: dict[str, str] = {
    "intervention": "outcome",
    "outcome": "intervention",
    "population": "intervention",
}
VALUE_FACETS = frozenset(FACET_COUNTERPART)
CLAIM_THEME_FACETS = frozenset(
    ("barrier_theme", "enabler_theme", "mechanism_theme")
)


class FacetDirectiveError(ValueError):
    """Malformed scope-context grouping directive — the component fails closed."""


class InvalidPartitionOutput(ValueError):
    """Backend partition output violated id-integrity constraints.

    Raised only for unknown or double-assigned value ids — corruption that
    poisons the whole response. Label/description rule violations reject at
    group grain instead (the violating group's members flow to the repair):
    the 013 review stack found both live intervention-facet runs losing 16
    coherent groups to one over-long label under the previous
    whole-response semantics.
    """


@dataclass(frozen=True)
class FindingFacetView:
    """One finding projected onto the chosen facet.

    Attributes:
        finding_id: Stable finding identifier.
        facet_value: Raw value of the chosen facet column, or ``None``.
        counterpart_value: Raw value of the paired counterpart column, or ``None``.
        effect_direction: Finding effect direction for IOF members, or ``None``.
        kind: Finding kind (``"iof"`` or ``"icf"``).
    """

    finding_id: str
    facet_value: str | None
    counterpart_value: str | None
    effect_direction: str | None
    kind: str = "iof"


@dataclass(frozen=True)
class FacetValue:
    """One distinct normalized facet value and its finding membership.

    Attributes:
        value_id: Deterministic ``v1``...``vN`` identifier.
        normalized: Whitespace-collapsed, casefolded identity key.
        surface: Elected display form.
        finding_ids: Member finding ids in input finding order.
        counterparts: Capped elected counterpart surface forms.
    """

    value_id: str
    normalized: str
    surface: str
    finding_ids: tuple[str, ...]
    counterparts: tuple[str, ...]


@dataclass(frozen=True)
class AcceptedGroup:
    """One accepted group after semantic validation.

    Attributes:
        label: Stripped group label.
        description: Stripped group description.
        member_ids: Value ids accepted into the group.
    """

    label: str
    description: str
    member_ids: tuple[str, ...]


@dataclass(frozen=True)
class ValidatedPartition:
    """A validated backend partition and its repair-driving omissions.

    Attributes:
        groups: Accepted non-empty groups.
        ungroupable_ids: Explicitly ungroupable ids in response order.
        missing_ids: Value ids never mentioned by the response, plus the
            members of groups rejected at group grain — both flow to the
            repair.
        rejected_reasons: One bounded reason per group rejected at group
            grain; persisted into grouping provenance by the caller.
    """

    groups: tuple[AcceptedGroup, ...]
    ungroupable_ids: tuple[str, ...]
    missing_ids: frozenset[str]
    rejected_reasons: tuple[str, ...] = ()


def normalize_value(raw: str) -> str:
    """Normalize a source-named facet or counterpart value.

    Args:
        raw: Raw source-derived value.

    Returns:
        The value with whitespace collapsed and case folded.
    """
    return " ".join(raw.split()).casefold()


def parse_grouping_directive(context: dict[str, Any]) -> tuple[list[str], str]:
    """Parse the scope-context grouping directive.

    Args:
        context: Scope context JSON-like mapping.

    Returns:
        ``(facets, facet_source)`` where source is ``"default"`` or
        ``"scope_context"``.

    Raises:
        FacetDirectiveError: If the directive is malformed or names an
            unsupported facet.
    """
    if "grouping" not in context or context["grouping"] == {}:
        return list(DEFAULT_FACETS), "default"

    directive = context["grouping"]
    if not isinstance(directive, dict):
        raise FacetDirectiveError("grouping directive must be an object")

    unknown_keys = set(directive) - {"facet", "facets"}
    if unknown_keys:
        # Bounded echo (012 review, security lane): keys are untrusted JSONB text
        # and the message lands in the component.failed event payload.
        shown = sorted(repr(key)[:DIRECTIVE_STRING_MAX] for key in unknown_keys)[:5]
        raise FacetDirectiveError(f"grouping directive has unknown keys: {shown}")

    if "facet" in directive and "facets" in directive:
        raise FacetDirectiveError("grouping directive must not mix facet and facets")

    if "facets" in directive:
        raw_facets = directive["facets"]
        if not isinstance(raw_facets, list) or not raw_facets:
            raise FacetDirectiveError("grouping facets must be a non-empty list")
        facets = [_validate_grouping_facet(facet) for facet in raw_facets]
    else:
        facets = [_validate_grouping_facet(directive.get("facet"))]

    seen: set[str] = set()
    for facet in facets:
        if facet in seen:
            raise FacetDirectiveError(f"duplicate grouping facet: {facet}")
        seen.add(facet)

    return facets, "scope_context"


def _validate_grouping_facet(facet: Any) -> str:
    if not isinstance(facet, str):
        raise FacetDirectiveError("grouping facet must be a string")
    if len(facet) > DIRECTIVE_STRING_MAX:
        raise FacetDirectiveError(
            f"grouping facet exceeds {DIRECTIVE_STRING_MAX} characters"
        )
    if has_control_character(facet):
        raise FacetDirectiveError("grouping facet contains a control character")
    if facet not in GROUPING_FACETS:
        raise FacetDirectiveError(f"unsupported grouping facet: {facet}")
    return facet


def extract_facet_values(
    findings: Sequence[FindingFacetView],
) -> tuple[list[FacetValue], list[str]]:
    """Extract deterministic distinct facet values from finding projections.

    Args:
        findings: Finding projections in source query order.

    Returns:
        A pair of deterministic facet values and finding ids with no usable
        facet value.
    """
    raw_by_value: dict[str, list[str]] = {}
    finding_ids_by_value: dict[str, list[str]] = {}
    counterparts_by_value: dict[str, list[str]] = {}
    no_value_finding_ids: list[str] = []

    for finding in findings:
        if finding.facet_value is None or not finding.facet_value.strip():
            no_value_finding_ids.append(finding.finding_id)
            continue

        normalized = normalize_value(finding.facet_value)
        raw_by_value.setdefault(normalized, []).append(finding.facet_value)
        finding_ids_by_value.setdefault(normalized, []).append(finding.finding_id)

        if finding.counterpart_value is not None and finding.counterpart_value.strip():
            counterparts_by_value.setdefault(normalized, []).append(finding.counterpart_value)

    values: list[FacetValue] = []
    for index, normalized in enumerate(sorted(raw_by_value), start=1):
        values.append(
            FacetValue(
                value_id=f"v{index}",
                normalized=normalized,
                surface=_elect_surface(raw_by_value[normalized]),
                finding_ids=tuple(finding_ids_by_value[normalized]),
                counterparts=_elect_counterparts(counterparts_by_value.get(normalized, [])),
            )
        )

    return values, no_value_finding_ids


def value_records(values: Sequence[FacetValue]) -> list[FacetValueRecord]:
    """Convert extracted facet values into prompt data records.

    Args:
        values: Deterministic facet values.

    Returns:
        Facet value records accepted by ``group_facet_v1``.
    """
    return [
        {
            "id": value.value_id,
            "value": value.surface,
            "finding_count": len(value.finding_ids),
            "counterparts": list(value.counterparts),
        }
        for value in values
    ]


def validate_partition(
    result: PartitionResult, *, value_ids: Collection[str]
) -> ValidatedPartition:
    """Validate backend partition output and return accepted groups.

    Args:
        result: Raw backend partition output.
        value_ids: All admissible value ids for the current partition call.

    Returns:
        Accepted groups, explicit ungroupable ids, ids omitted by the output
        or freed by group-grain rejections, and the rejection reasons.

    Raises:
        InvalidPartitionOutput: If an unknown or double-assigned value id is
            found anywhere in the response (id integrity is all-or-nothing;
            label/description violations reject only the offending group).
    """
    allowed_ids = set(value_ids)
    seen_ids: set[str] = set()
    seen_labels: set[str] = set()
    accepted_groups: list[AcceptedGroup] = []
    rejected_member_ids: set[str] = set()
    rejected_reasons: list[str] = []

    for index, group in enumerate(result["groups"]):
        member_ids = group["member_ids"]
        label = group["label"].strip()
        description = group["description"].strip()

        rejection = _group_text_violation(index, label, description)
        label_key = label.casefold()
        if rejection is None and label_key in FORBIDDEN_GROUP_LABELS:
            rejection = f"group {index} uses forbidden label: {label}"
        if rejection is None and label_key in seen_labels:
            rejection = f"duplicate group label: {label}"
        if rejection is None and not member_ids:
            rejection = f"group {index} has zero member ids"

        # Id integrity is checked for every group, rejected or not — an
        # unknown or double-assigned id still poisons the whole response.
        _mark_seen_ids(member_ids, allowed_ids=allowed_ids, seen_ids=seen_ids)

        if rejection is not None:
            rejected_reasons.append(rejection)
            rejected_member_ids.update(member_ids)
            continue

        seen_labels.add(label_key)
        accepted_groups.append(
            AcceptedGroup(
                label=label,
                description=description,
                member_ids=tuple(member_ids),
            )
        )

    ungroupable_ids: list[str] = []
    for value_id in result["ungroupable"]:
        _mark_seen_ids([value_id], allowed_ids=allowed_ids, seen_ids=seen_ids)
        ungroupable_ids.append(value_id)

    return ValidatedPartition(
        groups=tuple(accepted_groups),
        ungroupable_ids=tuple(ungroupable_ids),
        missing_ids=frozenset(allowed_ids - seen_ids) | frozenset(rejected_member_ids),
        rejected_reasons=tuple(rejected_reasons),
    )


def merge_repair(
    accepted: Sequence[AcceptedGroup], repair_groups: Sequence[AcceptedGroup]
) -> list[AcceptedGroup]:
    """Merge validated repair groups into already accepted groups.

    Args:
        accepted: Groups accepted from the first partition pass.
        repair_groups: Groups accepted from the repair pass.

    Returns:
        Groups with casefold label matches merged and new labels appended.
    """
    merged = list(accepted)
    label_to_index = {group.label.casefold(): index for index, group in enumerate(merged)}

    for repair_group in repair_groups:
        label_key = repair_group.label.casefold()
        if label_key not in label_to_index:
            label_to_index[label_key] = len(merged)
            merged.append(repair_group)
            continue

        index = label_to_index[label_key]
        target = merged[index]
        merged[index] = AcceptedGroup(
            label=target.label,
            description=target.description,
            member_ids=target.member_ids + repair_group.member_ids,
        )

    return merged


def direction_spread(directions: Iterable[str]) -> dict[str, int]:
    """Count effect directions with schema directions zero-filled.

    Args:
        directions: Effect direction strings to count.

    Returns:
        Direction counts with all schema directions present.
    """
    counts = dict.fromkeys(EFFECT_DIRECTIONS, 0)
    for direction in directions:
        counts[direction] = counts.get(direction, 0) + 1
    return counts


def build_groups_payload(
    findings: Sequence[FindingFacetView],
    *,
    facet: str,
    values: Sequence[FacetValue],
    groups: Sequence[AcceptedGroup],
    ungrouped_value_ids: Collection[str],
    no_value_finding_ids: Sequence[str],
) -> dict[str, Any]:
    """Build the run-local ``grouping_result.groups`` JSON payload.

    Args:
        findings: Finding projections for the referenced extraction run.
        facet: Grouping facet that owns this payload bucket.
        values: Extracted distinct facet values.
        groups: Accepted grouped value ids.
        ungrouped_value_ids: Explicit or repair-missing residual value ids.
        no_value_finding_ids: Finding ids with no usable facet value.

    Returns:
        JSON-serializable grouping payload.

    Raises:
        InvalidPartitionOutput: If value ids are not partitioned exactly or a
            payload finding id cannot be resolved.
    """
    value_by_id = _value_by_id(values)
    finding_direction_by_id = _finding_direction_by_id(findings)
    finding_kind_by_id = _finding_kind_by_id(findings)
    ungrouped_ids: set[str] = set()
    assigned_value_ids: set[str] = set()

    for value_id in ungrouped_value_ids:
        if value_id not in value_by_id:
            raise InvalidPartitionOutput(f"unknown id {value_id}")
        if value_id in ungrouped_ids:
            raise InvalidPartitionOutput(f"duplicate id {value_id}")
        ungrouped_ids.add(value_id)
        assigned_value_ids.add(value_id)

    group_member_sets: list[set[str]] = []
    for group in groups:
        member_set = set(group.member_ids)
        if len(member_set) != len(group.member_ids):
            raise InvalidPartitionOutput("duplicate id in group")
        for value_id in group.member_ids:
            if value_id not in value_by_id:
                raise InvalidPartitionOutput(f"unknown id {value_id}")
            if value_id in assigned_value_ids:
                raise InvalidPartitionOutput(f"duplicate id {value_id}")
            assigned_value_ids.add(value_id)
        group_member_sets.append(member_set)

    expected_value_ids = set(value_by_id)
    if assigned_value_ids != expected_value_ids:
        missing = sorted(expected_value_ids - assigned_value_ids)
        extra = sorted(assigned_value_ids - expected_value_ids)
        raise InvalidPartitionOutput(
            f"value ids are not exactly partitioned; missing={missing}, extra={extra}"
        )

    group_payloads: list[dict[str, Any]] = []
    for index, (group, member_set) in enumerate(
        zip(groups, group_member_sets, strict=True),
        start=1,
    ):
        member_values = [value.surface for value in values if value.value_id in member_set]
        member_finding_ids = [
            finding_id
            for value in values
            if value.value_id in member_set
            for finding_id in value.finding_ids
        ]
        spread = _spread_for_finding_ids(
            member_finding_ids,
            finding_direction_by_id,
            finding_kind_by_id,
        )
        group_payloads.append(
            {
                "group_id": f"{facet}:g{index:02d}",
                "facet": facet,
                "label": group.label,
                "description": group.description,
                "member_values": member_values,
                "member_finding_ids": member_finding_ids,
                "member_finding_kinds": [
                    finding_kind_by_id[finding_id] for finding_id in member_finding_ids
                ],
                "member_counts": _member_counts(member_finding_ids, finding_kind_by_id),
                "size": len(member_finding_ids),
                "direction_spread": spread,
            }
        )

    ungrouped_values = [value.surface for value in values if value.value_id in ungrouped_ids]
    ungrouped_finding_ids = [
        finding_id
        for value in values
        if value.value_id in ungrouped_ids
        for finding_id in value.finding_ids
    ]

    return {
        facet: {
            "groups": group_payloads,
            "ungrouped": {
                "values": ungrouped_values,
                "finding_ids": ungrouped_finding_ids,
                "member_finding_ids": ungrouped_finding_ids,
                "finding_kinds": [
                    finding_kind_by_id[finding_id] for finding_id in ungrouped_finding_ids
                ],
                "member_counts": _member_counts(ungrouped_finding_ids, finding_kind_by_id),
                "direction_spread": _spread_for_finding_ids(
                    ungrouped_finding_ids,
                    finding_direction_by_id,
                    finding_kind_by_id,
                ),
            },
            "no_value": {
                "finding_ids": list(no_value_finding_ids),
                "member_finding_ids": list(no_value_finding_ids),
                "finding_kinds": [
                    finding_kind_by_id[finding_id] for finding_id in no_value_finding_ids
                ],
                "member_counts": _member_counts(no_value_finding_ids, finding_kind_by_id),
                "direction_spread": _spread_for_finding_ids(
                    no_value_finding_ids,
                    finding_direction_by_id,
                    finding_kind_by_id,
                ),
            },
            "overall_direction_spread": direction_spread(
                finding.effect_direction
                for finding in findings
                if finding.kind == "iof" and finding.effect_direction is not None
            ),
        }
    }


def assert_grouping_invariants(
    payload: dict[str, Any],
    *,
    finding_ids: Collection[str] | None = None,
    finding_ids_by_facet: Mapping[str, Collection[str]] | None = None,
) -> None:
    """Assert exact finding coverage and internally consistent bucket counts.

    Args:
        payload: ``grouping_result.groups`` JSON payload.
        finding_ids: Finding ids that must appear exactly once across buckets
            for every facet, used by single-facet callers.
        finding_ids_by_facet: Per-facet finding ids for multi-facet payloads
            whose eligible bases differ.

    Raises:
        InvalidPartitionOutput: If coverage, size or spread invariants fail.
    """
    if finding_ids is None and finding_ids_by_facet is None:
        raise InvalidPartitionOutput("grouping invariants require expected finding ids")
    if not isinstance(payload, dict):
        raise InvalidPartitionOutput("grouping payload must be an object")
    if not payload:
        raise InvalidPartitionOutput("grouping payload must contain at least one facet")
    for facet, facet_payload in payload.items():
        if not isinstance(facet, str) or not facet:
            raise InvalidPartitionOutput("grouping facet key must be a non-empty string")
        if not isinstance(facet_payload, dict):
            raise InvalidPartitionOutput(f"facet {facet} payload must be an object")
        expected_ids = (
            finding_ids_by_facet[facet]
            if finding_ids_by_facet is not None and facet in finding_ids_by_facet
            else finding_ids
        )
        if expected_ids is None:
            raise InvalidPartitionOutput(f"missing expected finding ids for facet {facet}")
        _assert_facet_grouping_invariants(
            facet_payload,
            finding_ids=expected_ids,
            facet=facet,
        )


def _assert_facet_grouping_invariants(
    payload: dict[str, Any], *, finding_ids: Collection[str], facet: str
) -> None:
    expected = Counter(finding_ids)
    actual: Counter[str] = Counter()
    size_total = 0

    groups = cast(list[dict[str, Any]], payload["groups"])
    for index, group in enumerate(groups):
        if group.get("facet") != facet:
            raise InvalidPartitionOutput(f"group {index} facet does not match payload key")
        expected_group_id = f"{facet}:g{index + 1:02d}"
        if group.get("group_id") != expected_group_id:
            raise InvalidPartitionOutput(f"group {index} group_id is not deterministic")
        size = cast(int, group["size"])
        if size == 0:
            raise InvalidPartitionOutput(f"group {index} has size 0")
        member_finding_ids = cast(list[str], group["member_finding_ids"])
        actual.update(member_finding_ids)
        size_total += size
        if len(member_finding_ids) != size:
            raise InvalidPartitionOutput(f"group {index} size does not match finding ids")
        member_kinds = cast(list[str], group["member_finding_kinds"])
        if len(member_kinds) != len(member_finding_ids):
            raise InvalidPartitionOutput(f"group {index} kind count does not match finding ids")
        member_counts = cast(dict[str, int], group["member_counts"])
        if sum(member_counts.values()) != size:
            raise InvalidPartitionOutput(f"group {index} member counts do not sum to size")
        if member_counts != _counts_from_kinds(member_kinds):
            raise InvalidPartitionOutput(f"group {index} member counts do not match kinds")
        spread = group["direction_spread"]
        if spread is not None:
            typed_spread = cast(dict[str, int], spread)
            if sum(typed_spread.values()) != member_counts.get("iof", 0):
                raise InvalidPartitionOutput(
                    f"group {index} direction spread does not sum to IOF members"
                )

    ungrouped = cast(dict[str, Any], payload["ungrouped"])
    no_value = cast(dict[str, Any] | None, payload.get("no_value"))
    ungrouped_finding_ids = _bucket_finding_ids(ungrouped)
    no_value_ids = _bucket_finding_ids(no_value) if no_value is not None else []
    actual.update(ungrouped_finding_ids)
    actual.update(no_value_ids)
    size_total += len(ungrouped_finding_ids) + len(no_value_ids)

    _assert_residual_spread(ungrouped, "ungrouped")
    if no_value is not None:
        _assert_residual_spread(no_value, "no_value")

    overall = payload.get("overall_direction_spread")
    overall_counts = _bucket_member_counts(groups, ungrouped, no_value)
    if overall is not None and sum(
        cast(dict[str, int], overall).values()
    ) != overall_counts.get("iof", 0):
        raise InvalidPartitionOutput("overall direction spread does not sum to IOF members")

    if actual != expected:
        raise InvalidPartitionOutput("finding ids are not covered exactly once")
    if size_total != len(finding_ids):
        raise InvalidPartitionOutput("bucket sizes do not sum to finding count")


def _elect_surface(raw_values: Sequence[str]) -> str:
    counts = Counter(raw_values)
    return min(counts, key=lambda value: (-counts[value], value))


def _elect_counterparts(raw_values: Sequence[str]) -> tuple[str, ...]:
    raw_by_normalized: dict[str, list[str]] = {}
    for raw_value in raw_values:
        raw_by_normalized.setdefault(normalize_value(raw_value), []).append(raw_value)

    ranked = sorted(
        (
            (len(values), _elect_surface(values))
            for values in raw_by_normalized.values()
        ),
        key=lambda item: (-item[0], item[1]),
    )
    return tuple(surface for _, surface in ranked[:COUNTERPART_CAP])


def _group_text_violation(index: int, label: str, description: str) -> str | None:
    if not label:
        return f"group {index} has empty label"
    if len(label) > LABEL_MAX:
        return f"group {index} label exceeds {LABEL_MAX} chars"
    if has_control_character(label):
        return f"group {index} label contains a control character"
    if not description:
        return f"group {index} has empty description"
    if len(description) > DESCRIPTION_MAX:
        return f"group {index} description exceeds {DESCRIPTION_MAX} chars"
    if has_control_character(description):
        return f"group {index} description contains a control character"
    return None


def _mark_seen_ids(
    ids: Iterable[str], *, allowed_ids: set[str], seen_ids: set[str]
) -> None:
    for value_id in ids:
        if value_id not in allowed_ids:
            raise InvalidPartitionOutput(f"unknown id {value_id}")
        if value_id in seen_ids:
            raise InvalidPartitionOutput(f"duplicate id {value_id}")
        seen_ids.add(value_id)


def _value_by_id(values: Sequence[FacetValue]) -> dict[str, FacetValue]:
    value_by_id: dict[str, FacetValue] = {}
    for value in values:
        if value.value_id in value_by_id:
            raise InvalidPartitionOutput(f"duplicate id {value.value_id}")
        value_by_id[value.value_id] = value
    return value_by_id


def _finding_direction_by_id(findings: Sequence[FindingFacetView]) -> dict[str, str]:
    directions: dict[str, str] = {}
    for finding in findings:
        if finding.finding_id in directions:
            raise InvalidPartitionOutput(f"duplicate finding id {finding.finding_id}")
        if finding.kind == "iof":
            if finding.effect_direction is None:
                raise InvalidPartitionOutput(f"IOF finding missing direction {finding.finding_id}")
            directions[finding.finding_id] = finding.effect_direction
    return directions


def _finding_kind_by_id(findings: Sequence[FindingFacetView]) -> dict[str, str]:
    kinds: dict[str, str] = {}
    for finding in findings:
        if finding.finding_id in kinds:
            raise InvalidPartitionOutput(f"duplicate finding id {finding.finding_id}")
        kinds[finding.finding_id] = finding.kind
    return kinds


def _spread_for_finding_ids(
    finding_ids: Iterable[str],
    finding_direction_by_id: dict[str, str],
    finding_kind_by_id: dict[str, str],
) -> dict[str, int]:
    directions: list[str] = []
    for finding_id in finding_ids:
        kind = finding_kind_by_id.get(finding_id)
        if kind is None:
            raise InvalidPartitionOutput(f"unknown finding id {finding_id}")
        if kind != "iof":
            continue
        if finding_id not in finding_direction_by_id:
            raise InvalidPartitionOutput(f"IOF finding missing direction {finding_id}")
        directions.append(finding_direction_by_id[finding_id])
    return direction_spread(directions)


def _assert_residual_spread(bucket: dict[str, Any], name: str) -> None:
    finding_ids = _bucket_finding_ids(bucket)
    finding_kinds = cast(list[str], bucket["finding_kinds"])
    if len(finding_kinds) != len(finding_ids):
        raise InvalidPartitionOutput(f"{name} kind count does not match finding ids")
    member_counts = cast(dict[str, int], bucket["member_counts"])
    if sum(member_counts.values()) != len(finding_ids):
        raise InvalidPartitionOutput(f"{name} member counts do not sum to finding ids")
    if member_counts != _counts_from_kinds(finding_kinds):
        raise InvalidPartitionOutput(f"{name} member counts do not match kinds")
    spread = bucket["direction_spread"]
    if spread is not None and sum(
        cast(dict[str, int], spread).values()
    ) != member_counts.get("iof", 0):
        raise InvalidPartitionOutput(f"{name} direction spread does not sum to IOF members")


def _bucket_finding_ids(bucket: dict[str, Any]) -> list[str]:
    raw_finding_ids = bucket.get("finding_ids")
    raw_member_finding_ids = bucket.get("member_finding_ids")
    if raw_finding_ids is None and raw_member_finding_ids is None:
        raise InvalidPartitionOutput("residual bucket missing finding ids")
    if raw_finding_ids is None:
        return cast(list[str], raw_member_finding_ids)
    if raw_member_finding_ids is not None and raw_member_finding_ids != raw_finding_ids:
        raise InvalidPartitionOutput("residual finding id aliases disagree")
    return cast(list[str], raw_finding_ids)


def _member_counts(
    finding_ids: Iterable[str], finding_kind_by_id: dict[str, str]
) -> dict[str, int]:
    counts = {"iof": 0, "icf": 0}
    for finding_id in finding_ids:
        kind = finding_kind_by_id.get(finding_id)
        if kind is None:
            raise InvalidPartitionOutput(f"unknown finding id {finding_id}")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _counts_from_kinds(kinds: Iterable[str]) -> dict[str, int]:
    counts = {"iof": 0, "icf": 0}
    for kind in kinds:
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _bucket_member_counts(
    groups: Sequence[dict[str, Any]],
    ungrouped: dict[str, Any],
    no_value: dict[str, Any] | None,
) -> dict[str, int]:
    counts = {"iof": 0, "icf": 0}
    for group in groups:
        for kind, count in cast(dict[str, int], group["member_counts"]).items():
            counts[kind] = counts.get(kind, 0) + count
    buckets = (ungrouped,) if no_value is None else (ungrouped, no_value)
    for bucket in buckets:
        for kind, count in cast(dict[str, int], bucket["member_counts"]).items():
            counts[kind] = counts.get(kind, 0) + count
    return counts
