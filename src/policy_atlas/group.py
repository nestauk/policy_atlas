"""Group component (task 012): facet-level theming over extracted findings.

The component reads one explicitly referenced extraction roll-up, resolves that
run's finding set through its recorded extraction records, asks the facet
grouping backend to partition distinct source-named facet values, derives
finding memberships deterministically, and writes one run-scoped
``grouping_result`` roll-up last.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.extract import record_ids_by_profile
from policy_atlas.extraction_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.facet_grouping import (
    FACET_GROUPING_MODEL,
    FACET_VALUE_CAP,
    PROMPT_VERSION,
    REPAIR_CAP,
    VALUE_SURFACE_MAX,
    FacetGroupingBackend,
    FacetValueRecord,
    ProposedGroup,
)
from policy_atlas.facet_values import (
    FACET_COUNTERPART,
    AcceptedGroup,
    FacetValue,
    FindingFacetView,
    InvalidPartitionOutput,
    assert_grouping_invariants,
    build_groups_payload,
    extract_facet_values,
    merge_repair,
    parse_grouping_directive,
    validate_partition,
    value_records,
)
from policy_atlas.implementation_context_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.schema import (
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
)
from policy_atlas.usage import UsageAccumulator

log = structlog.get_logger()

# Rejection reasons persist into grouping provenance bounded (013 review
# stack: the live zero-group defect was only diagnosable from traces).
REJECTION_REASON_CAP = 20


class GroupError(Exception):
    """Structural group failure — missing/corrupt upstream reference or invariant violation.

    Raised (never returned) so the harness routes it to ``component.failed``.
    """


@dataclass(frozen=True)
class GroupContext:
    """Scope-level input to group.

    Attributes:
        scope_id: Evidence scope whose extracted findings are grouped.
        intent: Scope intent, carried for wiring uniformity with other scope
            components. It is **not** consumed by grouping: the prompt sees
            only source-named facet values from the referenced extraction run.
        context: Scope context JSONB, optionally carrying a grouping directive.
        extraction_run_id: Explicit extraction run whose findings are grouped.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]
    extraction_run_id: uuid.UUID


def group_findings(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: GroupContext,
    facet_grouping_backend: FacetGroupingBackend,
) -> dict[str, Any]:
    """Group extracted findings by one source-named facet.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run writing the grouping result.
        context: Scope-level group input with the explicit extraction run.
        facet_grouping_backend: Facet grouping seam.

    Returns:
        The grouping summary payload for ``component.completed``.

    Raises:
        GroupError: If the extraction roll-up is missing/corrupt, the value cap
            is exceeded, the backend fails, or grouping invariants fail.
    """
    facet, facet_source = parse_grouping_directive(context.context)
    docs, extraction_counts, extraction_provenance, raw_counts = _load_extraction_rollup(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        extraction_run_id=context.extraction_run_id,
    )
    extraction_record_ids_by_kind = _extraction_record_ids_by_kind(docs)
    findings = _load_findings(
        conn,
        project_id=project_id,
        extraction_record_ids_by_kind=extraction_record_ids_by_kind,
    )
    expected_findings_total = _all_extraction_findings_total(raw_counts)
    if len(findings) != expected_findings_total:
        raise GroupError(
            "corrupt reference: resolved "
            f"{len(findings)} findings for extraction_run_id {context.extraction_run_id}, "
            f"expected {expected_findings_total}"
        )

    views = _project_findings(findings, facet=facet)
    values, no_value_finding_ids = extract_facet_values(views)
    finding_ids = [view.finding_id for view in views]

    final_groups: list[AcceptedGroup] = []
    ungrouped_value_ids: set[str] = set()
    call_count = 0
    repair_count = 0
    rejection_reasons: list[str] = []
    flags: list[str] = []
    usage_totals = UsageAccumulator().payload()

    if not views:
        flags.append("empty_findings")
    elif not values:
        flags.append("all_no_value")
    else:
        if len(values) > FACET_VALUE_CAP:
            raise GroupError(
                "value_cap_exceeded: "
                f"{len(values)} distinct facet values exceeds cap {FACET_VALUE_CAP}; "
                "deferred large-corpus seam required"
            )
        for value in values:
            if len(value.surface) > VALUE_SURFACE_MAX or any(
                len(counterpart) > VALUE_SURFACE_MAX for counterpart in value.counterparts
            ):
                raise GroupError(
                    "value_surface_too_long: "
                    f"facet value {value.value_id} exceeds {VALUE_SURFACE_MAX} chars"
                )

        log.info("group.call_budget", baseline=1, maximum=1 + REPAIR_CAP)
        records = value_records(values)
        (
            final_groups,
            ungrouped_value_ids,
            call_count,
            repair_count,
            rejection_reasons,
            usage_totals,
        ) = _partition_values(
            records,
            facet=facet,
            facet_grouping_backend=facet_grouping_backend,
        )

    payload = _build_valid_payload(
        views,
        values=values,
        groups=final_groups,
        ungrouped_value_ids=ungrouped_value_ids,
        no_value_finding_ids=no_value_finding_ids,
        finding_ids=finding_ids,
    )
    counts = _build_counts(payload, findings_total=len(views), distinct_values=len(values))

    ungrouped = cast("dict[str, Any]", payload["ungrouped"])
    if cast("list[str]", ungrouped["values"]):
        flags.append("ungrouped_values")
    if repair_count:
        flags.append("repair_path_taken")
    if rejection_reasons:
        flags.append("groups_rejected")

    provenance = _build_provenance(
        backend=facet_grouping_backend,
        facet=facet,
        facet_source=facet_source,
        call_count=call_count,
        repair_count=repair_count,
        rejection_reasons=rejection_reasons,
        distinct_value_count=len(values),
        extraction_run_id=context.extraction_run_id,
        extraction_counts=extraction_counts,
        extraction_provenance=extraction_provenance,
        finding_ids=finding_ids,
        values_with_findings=len(values),
        no_value_count=len(no_value_finding_ids),
    )
    summary = _build_summary(
        facet=facet,
        facet_source=facet_source,
        payload=payload,
        counts=counts,
        extraction_run_id=context.extraction_run_id,
        flags=flags,
        provenance=provenance,
        usage_totals=usage_totals,
    )

    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=context.scope_id,
            run_id=run_id,
            extraction_run_id=context.extraction_run_id,
            facet=facet,
            grouping_provenance=provenance,
            groups=payload,
            counts=counts,
            flags=flags,
            created_at=datetime.now(UTC),
        )
    )
    log.info("group.completed", **counts)
    return summary


def _load_extraction_rollup(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
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
    iof_counts = dict(counts_profiles[IOF_PROFILE_ID])
    for shared_key in ("selected", "basis"):
        if shared_key in counts_map:
            iof_counts[shared_key] = counts_map[shared_key]
    return (
        mapped_docs,
        iof_counts,
        dict(provenance_profiles[IOF_PROFILE_ID]),
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


def _load_findings(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    extraction_record_ids_by_kind: Mapping[str, Sequence[uuid.UUID]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    iof_record_ids = list(extraction_record_ids_by_kind.get("iof", []))
    if iof_record_ids:
        rows = conn.execute(
            sa_select(
                intervention_outcome_finding.c.finding_id,
                intervention_outcome_finding.c.extraction_record_id,
                intervention_outcome_finding.c.intervention,
                intervention_outcome_finding.c.outcome,
                intervention_outcome_finding.c.population,
                intervention_outcome_finding.c.effect_direction,
            )
            .where(intervention_outcome_finding.c.project_id == project_id)
            .where(intervention_outcome_finding.c.extraction_record_id.in_(iof_record_ids))
            .order_by(
                intervention_outcome_finding.c.extraction_record_id,
                intervention_outcome_finding.c.finding_id,
            )
        ).mappings().fetchall()
        findings.extend({"kind": "iof", **dict(row)} for row in rows)

    icf_record_ids = list(extraction_record_ids_by_kind.get("icf", []))
    if icf_record_ids:
        rows = conn.execute(
            sa_select(
                implementation_context_finding.c.finding_id,
                implementation_context_finding.c.extraction_record_id,
                implementation_context_finding.c.intervention,
                implementation_context_finding.c.outcome,
                implementation_context_finding.c.population,
            )
            .where(implementation_context_finding.c.project_id == project_id)
            .where(implementation_context_finding.c.extraction_record_id.in_(icf_record_ids))
            .order_by(
                implementation_context_finding.c.extraction_record_id,
                implementation_context_finding.c.finding_id,
            )
        ).mappings().fetchall()
        findings.extend({"kind": "icf", "effect_direction": None, **dict(row)} for row in rows)
    return findings


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


def _project_findings(findings: Sequence[dict[str, Any]], *, facet: str) -> list[FindingFacetView]:
    counterpart = FACET_COUNTERPART[facet]
    views: list[FindingFacetView] = []
    for row in findings:
        views.append(
            FindingFacetView(
                finding_id=str(row["finding_id"]),
                facet_value=cast("str | None", row[facet]),
                counterpart_value=cast("str | None", row[counterpart]),
                effect_direction=cast("str | None", row["effect_direction"]),
                kind=cast("str", row["kind"]),
            )
        )
    return views


def _partition_values(
    records: list[FacetValueRecord],
    *,
    facet: str,
    facet_grouping_backend: FacetGroupingBackend,
) -> tuple[list[AcceptedGroup], set[str], int, int, list[str], dict[str, int]]:
    call_count = 0
    repair_count = 0
    all_value_ids = [record["id"] for record in records]
    rejection_reasons: list[str] = []
    usage_totals = UsageAccumulator()

    try:
        call_count += 1
        raw, usage = facet_grouping_backend.partition(records, facet=facet)
        usage_totals.add(usage)
    except Exception as exc:
        raise GroupError(f"facet grouping backend failed: {type(exc).__name__}") from exc

    accepted: list[AcceptedGroup]
    ungroupable_ids: set[str]
    repair_records: list[FacetValueRecord] = []
    repair_value_ids: set[str] = set()
    repair_accepted_groups: list[ProposedGroup] = []

    try:
        validated = validate_partition(raw, value_ids=all_value_ids)
    except InvalidPartitionOutput as exc:
        rejection_reasons.append(f"partition: {exc}")
        accepted = []
        ungroupable_ids = set()
        repair_records = records
        repair_value_ids = set(all_value_ids)
    else:
        rejection_reasons.extend(
            f"partition: {reason}" for reason in validated.rejected_reasons
        )
        accepted = list(validated.groups)
        ungroupable_ids = set(validated.ungroupable_ids)
        if validated.missing_ids:
            repair_value_ids = set(validated.missing_ids)
            repair_records = [
                record for record in records if record["id"] in validated.missing_ids
            ]
            repair_accepted_groups = _proposed_groups(validated.groups)

    if repair_records:
        repair_count += 1
        try:
            repair_raw, usage = facet_grouping_backend.repair(
                repair_records,
                facet=facet,
                accepted_groups=repair_accepted_groups,
            )
            usage_totals.add(usage)
        except Exception as exc:
            raise GroupError(f"facet grouping backend failed: {type(exc).__name__}") from exc

        try:
            repair_validated = validate_partition(repair_raw, value_ids=repair_value_ids)
        except InvalidPartitionOutput as exc:
            rejection_reasons.append(f"repair: {exc}")
            still_missing_ids = set(repair_value_ids)
        else:
            rejection_reasons.extend(
                f"repair: {reason}" for reason in repair_validated.rejected_reasons
            )
            accepted = merge_repair(accepted, repair_validated.groups)
            ungroupable_ids.update(repair_validated.ungroupable_ids)
            still_missing_ids = set(repair_validated.missing_ids)
        ungroupable_ids.update(still_missing_ids)

    bounded_reasons = [reason[:200] for reason in rejection_reasons[:REJECTION_REASON_CAP]]
    return (
        accepted,
        ungroupable_ids,
        call_count,
        repair_count,
        bounded_reasons,
        usage_totals.payload(),
    )


def _proposed_groups(groups: Sequence[AcceptedGroup]) -> list[ProposedGroup]:
    return [
        {
            "label": group.label,
            "description": group.description,
            "member_ids": list(group.member_ids),
        }
        for group in groups
    ]


def _build_valid_payload(
    views: Sequence[FindingFacetView],
    *,
    values: Sequence[FacetValue],
    groups: Sequence[AcceptedGroup],
    ungrouped_value_ids: Collection[str],
    no_value_finding_ids: Sequence[str],
    finding_ids: Collection[str],
) -> dict[str, Any]:
    try:
        payload = build_groups_payload(
            views,
            values=values,
            groups=groups,
            ungrouped_value_ids=ungrouped_value_ids,
            no_value_finding_ids=no_value_finding_ids,
        )
        assert_grouping_invariants(payload, finding_ids=finding_ids)
    except InvalidPartitionOutput as exc:
        raise GroupError(f"grouping invariant violated: {exc}") from exc
    return payload


def _build_counts(
    payload: dict[str, Any], *, findings_total: int, distinct_values: int
) -> dict[str, int]:
    groups = cast("list[dict[str, Any]]", payload["groups"])
    ungrouped = cast("dict[str, Any]", payload["ungrouped"])
    no_value = cast("dict[str, Any]", payload["no_value"])
    return {
        "findings_total": findings_total,
        "grouped": sum(cast("int", group["size"]) for group in groups),
        "ungrouped": len(cast("list[str]", ungrouped["finding_ids"])),
        "no_value": len(cast("list[str]", no_value["finding_ids"])),
        "distinct_values": distinct_values,
        "groups": len(groups),
    }


def _build_provenance(
    *,
    backend: FacetGroupingBackend,
    facet: str,
    facet_source: str,
    call_count: int,
    repair_count: int,
    rejection_reasons: Sequence[str],
    distinct_value_count: int,
    extraction_run_id: uuid.UUID,
    extraction_counts: dict[str, Any],
    extraction_provenance: dict[str, Any],
    finding_ids: Sequence[str],
    values_with_findings: int,
    no_value_count: int,
) -> dict[str, Any]:
    mode = backend.mode
    model = FACET_GROUPING_MODEL if mode == "live" else str(getattr(backend, "model", mode))
    return {
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "mode": mode,
        "facet": facet,
        "facet_source": facet_source,
        "value_cap": FACET_VALUE_CAP,
        "call_count": call_count,
        "repair_count": repair_count,
        "rejection_reasons": list(rejection_reasons),
        "distinct_value_count": distinct_value_count,
        "extraction_run_id": str(extraction_run_id),
        "extraction_base": {
            "extraction_fingerprint": _required_str(
                extraction_provenance, "fingerprint", "extraction provenance"
            ),
            "profile": _required_str(extraction_provenance, "profile", "extraction provenance"),
            "counts": _extraction_base_counts(extraction_counts),
            "finding_set": {
                "size": len(finding_ids),
                "sha256": _finding_set_sha256(finding_ids),
            },
            "facet_coverage": {
                "values_with_findings": values_with_findings,
                "no_value_count": no_value_count,
            },
        },
    }


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


def _finding_set_sha256(finding_ids: Sequence[str]) -> str:
    material = "\n".join(sorted(finding_ids)).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _build_summary(
    *,
    facet: str,
    facet_source: str,
    payload: dict[str, Any],
    counts: dict[str, int],
    extraction_run_id: uuid.UUID,
    flags: list[str],
    provenance: dict[str, Any],
    usage_totals: dict[str, int],
) -> dict[str, Any]:
    groups = cast("list[dict[str, Any]]", payload["groups"])
    ungrouped = cast("dict[str, Any]", payload["ungrouped"])
    no_value = cast("dict[str, Any]", payload["no_value"])
    return {
        "facet": facet,
        "facet_source": facet_source,
        "groups": [
            {
                "label": cast("str", group["label"]),
                "size": cast("int", group["size"]),
                "value_count": len(cast("list[str]", group["member_values"])),
                "direction_spread": cast("dict[str, int]", group["direction_spread"]),
            }
            for group in groups
        ],
        "residuals": {
            "ungrouped": {
                "value_count": len(cast("list[str]", ungrouped["values"])),
                "finding_count": len(cast("list[str]", ungrouped["finding_ids"])),
                "direction_spread": cast("dict[str, int]", ungrouped["direction_spread"]),
            },
            "no_value": {
                "finding_count": len(cast("list[str]", no_value["finding_ids"])),
                "direction_spread": cast("dict[str, int]", no_value["direction_spread"]),
            },
        },
        "overall_direction_spread": cast(
            "dict[str, int]", payload["overall_direction_spread"]
        ),
        "counts": counts,
        "extraction_run_id": str(extraction_run_id),
        "flags": flags,
        "provenance": provenance,
        "usage_totals": usage_totals,
    }
