"""Component tests for the group component (task 012)."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from typing import Any, cast

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core.schema import (
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    selection_result,
    source_extraction_record,
)
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_search.clustering_engine import ClusterLabel, ClusterUnit
from policy_atlas.evidence_search.extract.icf_records import PROFILE_ID as ICF_PROFILE_ID
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.evidence_search.group.facet_values import (
    FACET_VALUE_CAP,
    LABEL_MAX,
    VALUE_SURFACE_MAX,
    FacetDirectiveError,
)
from policy_atlas.evidence_search.group.group import (
    CLAIM_SURFACE_MAX,
    CONTEXT_LABEL_SURFACE_MAX,
    GROUP_PROMPT_VERSION,
    GROUP_RESIDUAL_LABEL,
    ClaimThemeUnit,
    GroupContext,
    GroupError,
    StubGroupClusteringBackend,
    _claim_cluster_units,
    _forbidden_group_label_reason,
    _load_finding_references,
    claim_theme_base_sha256,
    group_call_budget,
    group_findings,
    group_max_labels,
)
from tests.helpers import now, seed_run, seed_scope, seed_source, seed_task_and_run

DocSpec = tuple[uuid.UUID, list[dict[str, Any]]]


@dataclass(frozen=True)
class SeededExtraction:
    run_id: uuid.UUID
    selection_run_id: uuid.UUID
    record_ids: list[uuid.UUID]
    finding_ids: list[uuid.UUID]


@dataclass(frozen=True)
class SeededMixedExtraction:
    run_id: uuid.UUID
    selection_run_id: uuid.UUID
    iof_record_id: uuid.UUID
    icf_record_id: uuid.UUID
    iof_finding_ids: list[uuid.UUID]
    icf_finding_ids: list[uuid.UUID]


class ScriptedGroupClusteringBackend:
    mode = "stub"
    model = "scripted"

    def __init__(
        self,
        *,
        labels: list[ClusterLabel] | None = None,
        assignments: dict[str, str] | None = None,
        fail_discovery: bool = False,
        fail_assignment: bool = False,
    ) -> None:
        self.discovery_calls = 0
        self.assignment_calls = 0
        self.labels = labels if labels is not None else []
        self.assignments = assignments if assignments is not None else {}
        self.fail_discovery = fail_discovery
        self.fail_assignment = fail_assignment

    def for_facet(
        self,
        *,
        facet: str,
        projection: str,
        include_context_in_discovery: bool,
        guidance: list[str] | None = None,
    ) -> ScriptedGroupClusteringBackend:
        del facet, projection, include_context_in_discovery, guidance
        return self

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        del units, min_labels, max_labels
        self.discovery_calls += 1
        if self.fail_discovery:
            raise RuntimeError("backend_error: scripted discovery failure")
        return self.labels, None

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[dict[str, str]]:
        del labels
        self.assignment_calls += 1
        if self.fail_assignment:
            raise RuntimeError("backend_error: scripted assignment failure")
        return {
            unit.unit_id: self.assignments.get(unit.unit_id, "__ungrouped__")
            for unit in batch
        }, None


def seed_extraction(
    conn: Connection,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    docs: list[DocSpec],
    extraction_run_id: uuid.UUID | None = None,
    reused_record_ids: set[uuid.UUID] | None = None,
) -> SeededExtraction:
    extraction_run_id = extraction_run_id or seed_run(conn, task_id)
    selection_run_id = seed_run(conn, task_id)
    reused_record_ids = reused_record_ids or set()
    selected: list[dict[str, Any]] = []
    doc_payloads: list[dict[str, Any]] = []
    finding_ids: list[uuid.UUID] = []
    record_ids: list[uuid.UUID] = []

    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=selection_run_id,
            strategy="coverage_stratified_v1",
            budget=max(1, len(docs)),
            selection_provenance={"strategy": "test"},
            selected=selected,
            excluded={},
            flags=[],
            created_at=now(),
        )
    )

    for index, (record_id, findings) in enumerate(docs):
        snap_id, tss_id = seed_source(conn, task_id)
        selected.append({"tss_id": str(tss_id), "text_basis": "full_text"})
        status = "extracted" if findings else "no_findings"
        record_ids.append(record_id)
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                task_id=task_id,
                source_snapshot_id=snap_id,
                task_source_snapshot_id=tss_id,
                extraction_fingerprint=f"fp-{extraction_run_id}",
                status=status,
                basis="full_text",
                error=None,
                finding_count=len(findings),
                run_id=extraction_run_id,
                created_at=now(),
            )
        )
        for finding in findings:
            values = _finding_values(task_id, record_id, **finding)
            finding_ids.append(cast("uuid.UUID", values["finding_id"]))
            conn.execute(intervention_outcome_finding.insert().values(**values))
        doc_payloads.append(
            {
                "tss_id": str(tss_id),
                "basis": "full_text",
                "order": index,
                "profiles": {
                    IOF_PROFILE_ID: {
                        "status": status,
                        "finding_count": len(findings),
                        "reused": record_id in reused_record_ids,
                        "error": None,
                        "extraction_record_id": str(record_id),
                    }
                },
            }
        )

    conn.execute(
        update(selection_result)
        .where(selection_result.c.run_id == selection_run_id)
        .values(selected=selected)
    )
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "profiles": {
                    IOF_PROFILE_ID: {
                        "fingerprint": f"rollup-fp-{extraction_run_id}",
                        "profile": "test-profile",
                    }
                }
            },
            docs=doc_payloads,
            counts={
                "selected": len(docs),
                "basis": {
                    "full_text": len(docs),
                    "abstract_only": 0,
                    "shares": {"full_text": 1.0 if docs else 0.0, "abstract_only": 0.0},
                },
                "profiles": {
                    IOF_PROFILE_ID: {
                        "extracted": sum(1 for _, findings in docs if findings),
                        "no_findings": sum(1 for _, findings in docs if not findings),
                        "failed": 0,
                        "fresh": len(docs) - len(reused_record_ids),
                        "reused": len(reused_record_ids),
                        "findings": {
                            "total": len(finding_ids),
                            "quote_unverified": 0,
                            "dedup_collapsed": 0,
                            "invalid_dropped": 0,
                        },
                        "field_coverage": {},
                    }
                },
            },
            flags=[],
            created_at=now(),
        )
    )
    return SeededExtraction(
        run_id=extraction_run_id,
        selection_run_id=selection_run_id,
        record_ids=record_ids,
        finding_ids=finding_ids,
    )


def seed_mixed_extraction(
    conn: Connection,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    iof_findings: list[dict[str, Any]],
    icf_findings: list[dict[str, Any]],
    extraction_run_id: uuid.UUID | None = None,
) -> SeededMixedExtraction:
    extraction_run_id = extraction_run_id or seed_run(conn, task_id)
    selection_run_id = seed_run(conn, task_id)
    snap_id, tss_id = seed_source(conn, task_id)
    iof_record_id = uuid.uuid4()
    icf_record_id = uuid.uuid4()
    iof_finding_ids: list[uuid.UUID] = []
    icf_finding_ids: list[uuid.UUID] = []

    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=selection_run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={"strategy": "test"},
            selected=[{"tss_id": str(tss_id), "text_basis": "full_text"}],
            excluded={},
            flags=[],
            created_at=now(),
        )
    )
    for record_id, profile_id, findings in (
        (iof_record_id, IOF_PROFILE_ID, iof_findings),
        (icf_record_id, ICF_PROFILE_ID, icf_findings),
    ):
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                task_id=task_id,
                source_snapshot_id=snap_id,
                task_source_snapshot_id=tss_id,
                extraction_fingerprint=f"fp-{profile_id}-{extraction_run_id}",
                status="extracted" if findings else "no_findings",
                basis="full_text",
                error=None,
                finding_count=len(findings),
                run_id=extraction_run_id,
                created_at=now(),
            )
        )
    for finding in iof_findings:
        values = _finding_values(task_id, iof_record_id, **finding)
        iof_finding_ids.append(cast("uuid.UUID", values["finding_id"]))
        conn.execute(intervention_outcome_finding.insert().values(**values))
    for finding in icf_findings:
        values = _icf_values(task_id, icf_record_id, **finding)
        icf_finding_ids.append(cast("uuid.UUID", values["finding_id"]))
        conn.execute(implementation_context_finding.insert().values(**values))

    profile_counts = {
        IOF_PROFILE_ID: _profile_counts(iof_findings),
        ICF_PROFILE_ID: _profile_counts(icf_findings),
    }
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "profiles": {
                    IOF_PROFILE_ID: {"fingerprint": "rollup-iof", "profile": IOF_PROFILE_ID},
                    ICF_PROFILE_ID: {"fingerprint": "rollup-icf", "profile": ICF_PROFILE_ID},
                }
            },
            docs=[
                {
                    "tss_id": str(tss_id),
                    "basis": "full_text",
                    "order": 0,
                    "profiles": {
                        IOF_PROFILE_ID: {
                            "status": "extracted" if iof_findings else "no_findings",
                            "finding_count": len(iof_findings),
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(iof_record_id),
                        },
                        ICF_PROFILE_ID: {
                            "status": "extracted" if icf_findings else "no_findings",
                            "finding_count": len(icf_findings),
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(icf_record_id),
                        },
                    },
                }
            ],
            counts={
                "selected": 1,
                "basis": {
                    "full_text": 1,
                    "abstract_only": 0,
                    "shares": {"full_text": 1.0, "abstract_only": 0.0},
                },
                "profiles": profile_counts,
            },
            flags=[],
            created_at=now(),
        )
    )
    return SeededMixedExtraction(
        run_id=extraction_run_id,
        selection_run_id=selection_run_id,
        iof_record_id=iof_record_id,
        icf_record_id=icf_record_id,
        iof_finding_ids=iof_finding_ids,
        icf_finding_ids=icf_finding_ids,
    )


def _profile_counts(findings: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "selected": 1,
        "extracted": 1 if findings else 0,
        "no_findings": 0 if findings else 1,
        "failed": 0,
        "fresh": 1,
        "reused": 0,
        "findings": {
            "total": len(findings),
            "quote_unverified": 0,
            "dedup_collapsed": 0,
            "invalid_dropped": 0,
        },
        "field_coverage": {},
    }


def _finding_values(
    task_id: uuid.UUID,
    extraction_record_id: uuid.UUID,
    **overrides: Any,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "finding_id": uuid.uuid4(),
        "task_id": task_id,
        "extraction_record_id": extraction_record_id,
        "intervention": "Alpha service",
        "outcome": "Health outcome",
        "population": "Adults",
        "comparator": None,
        "effect_direction": "increase",
        "estimate_level": "study",
        "study_design": None,
        "stratum_qualifiers": [],
        "statistics": {},
        "causality_by_design": None,
        "is_primary": None,
        "is_prevalence_only": None,
        "field_coverage": {},
        "grounding": [],
        "created_at": now(),
    }
    values.update(overrides)
    return values


def _icf_values(
    task_id: uuid.UUID,
    extraction_record_id: uuid.UUID,
    **overrides: Any,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "finding_id": uuid.uuid4(),
        "task_id": task_id,
        "extraction_record_id": extraction_record_id,
        "context_type": "barrier",
        "claim": "Implementation staffing gaps slowed delivery.",
        "context_label": None,
        "intervention": "Alpha service",
        "outcome": "Attendance",
        "population": "Adults",
        "setting": None,
        "study_geography": None,
        "study_design": None,
        "claim_level": "study",
        "claim_basis": "studied",
        "level": "provider",
        "resource_requirements": None,
        "workforce_requirements": None,
        "field_coverage": {},
        "grounding": [],
        "created_at": now(),
    }
    values.update(overrides)
    return values


def _run_group(
    conn: Connection,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    *,
    run_id: uuid.UUID | None = None,
    context: dict[str, Any] | None = None,
    backend: StubGroupClusteringBackend | ScriptedGroupClusteringBackend | None = None,
) -> tuple[dict[str, Any], uuid.UUID]:
    run_id = run_id or seed_run(conn, task_id)
    summary = group_findings(
        conn,
        task_id=task_id,
        run_id=run_id,
        context=GroupContext(
            scope_id=scope_id,
            intent="This intent must not enter grouping.",
            context=context or {},
            extraction_run_id=extraction_run_id,
        ),
        group_clustering_backend=backend or StubGroupClusteringBackend(),
    )
    return summary, run_id


def _group_row(conn: Connection, task_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
    row = conn.execute(
        select(grouping_result)
        .where(grouping_result.c.task_id == task_id)
        .where(grouping_result.c.run_id == run_id)
    ).mappings().one()
    return dict(row)


def _group_count(conn: Connection, task_id: uuid.UUID) -> int:
    return conn.execute(
        select(func.count())
        .select_from(grouping_result)
        .where(grouping_result.c.task_id == task_id)
    ).scalar_one()


def _payload_finding_ids(payload: dict[str, Any]) -> set[str]:
    finding_ids: set[str] = set()
    for facet_payload in payload.values():
        if not isinstance(facet_payload, dict):
            continue
        groups = cast("list[dict[str, Any]]", facet_payload["groups"])
        ungrouped = cast("dict[str, Any]", facet_payload["ungrouped"])
        no_value = cast("dict[str, Any]", facet_payload.get("no_value", {}))
        finding_ids |= {
            finding_id
            for group in groups
            for finding_id in cast("list[str]", group["member_finding_ids"])
        } | set(cast("list[str]", ungrouped["finding_ids"])) | set(
            cast("list[str]", no_value.get("finding_ids", []))
        )
    return finding_ids


def _facet_payload(payload: dict[str, Any], facet: str = "intervention") -> dict[str, Any]:
    return cast("dict[str, Any]", payload[facet])


def _spread_total(spread: dict[str, int]) -> int:
    return sum(spread.values())


def test_happy_path_writes_rollup_summary_and_provenance(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha counseling",
                        "outcome": "Attendance",
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "Alpha coaching",
                        "outcome": "Retention",
                        "effect_direction": "decrease",
                    },
                    {
                        "intervention": "Beta home visits",
                        "outcome": "Employment",
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "Beta phone calls",
                        "outcome": "Employment",
                        "effect_direction": "no_effect",
                    },
                    {
                        "intervention": "Gamma support",
                        "outcome": "Wellbeing",
                        "effect_direction": "mixed",
                    },
                    {
                        "intervention": "stubungroupable strategy",
                        "outcome": "Wellbeing",
                        "effect_direction": "unclear",
                    },
                ],
            )
        ],
    )

    summary, group_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    row = _group_row(conn, task_id, group_run_id)

    assert summary.keys() == {
        "facet",
        "facets",
        "facet_source",
        "groups",
        "residuals",
        "counts",
        "extraction_run_id",
        "flags",
        "provenance",
        "usage_totals",
    }
    assert row["groups"].keys() == {"intervention"}
    assert row["flags"] == {
        "intervention": {
            "status": "succeeded",
            "failure_class": None,
            "groups_rejected": False,
            "value_cap_exceeded": False,
        }
    }
    assert summary["facet"] == "intervention"
    assert summary["facets"] == ["intervention"]
    assert summary["facet_source"] == "default"
    assert summary["extraction_run_id"] == str(seeded.run_id)
    assert summary["flags"] == row["flags"]
    counts = summary["counts"]["intervention"]
    groups = summary["groups"]["intervention"]
    residuals = summary["residuals"]["intervention"]
    assert counts == {
        "eligible_base": 6,
        "findings_total": 6,
        "grouped": 5,
        "ungrouped": 1,
        "no_value": 0,
        "distinct_values": 6,
        "groups": 3,
    }
    assert [group["label"] for group in groups] == ["alpha", "beta", "gamma"]
    assert [group["size"] for group in groups] == [2, 2, 1]
    assert [group["value_count"] for group in groups] == [2, 2, 1]
    assert residuals["ungrouped"]["value_count"] == 1
    assert residuals["ungrouped"]["finding_count"] == 1
    assert residuals["no_value"]["finding_count"] == 0
    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in seeded.finding_ids
    }
    assert sum(counts[key] for key in ("grouped", "ungrouped", "no_value")) == 6

    row_payload = cast("dict[str, Any]", row["groups"])
    row_overall = cast(
        "dict[str, int]",
        _facet_payload(row_payload)["overall_direction_spread"],
    )
    assert row_overall == residuals["overall_direction_spread"]
    assert sum(row_overall.values()) == 6

    provenance = cast("dict[str, Any]", row["grouping_provenance"])
    assert set(provenance) == {
        "prompt_version",
        "model",
        "mode",
        "facet",
        "facets",
        "facet_source",
        "granularity",
        "guidance",
        "value_cap",
        "call_count",
        "repair_count",
        "rejection_reasons",
        "distinct_value_count",
        "extraction_run_id",
        "facet_runs",
        "extraction_base",
    }
    assert provenance["rejection_reasons"] == []
    assert provenance["prompt_version"] == GROUP_PROMPT_VERSION
    assert provenance["model"] == "stub"
    assert provenance["mode"] == "stub"
    assert provenance["facet"] == "intervention"
    assert provenance["facets"] == ["intervention"]
    assert provenance["facet_source"] == "default"
    assert provenance["granularity"] == "standard"
    # B3 (024 steering surface): guidance absent is byte-identical to as-built.
    assert provenance["guidance"] is None
    assert provenance["value_cap"] == FACET_VALUE_CAP
    # Two-stage happy path: one discovery + one assignment call.
    assert provenance["call_count"] == 2
    assert provenance["repair_count"] == 0
    assert provenance["distinct_value_count"] == 6
    assert provenance["facet_runs"]["intervention"]["eligible_base_size"] == 6
    assert provenance["facet_runs"]["intervention"]["call_budget"] == 4
    assert provenance["facet_runs"]["intervention"]["calls_used"] == 2
    base = cast("dict[str, Any]", provenance["extraction_base"])
    assert base.keys() == {"profiles", "finding_set"}
    assert base["profiles"].keys() == {IOF_PROFILE_ID}
    iof_base = cast("dict[str, Any]", base["profiles"][IOF_PROFILE_ID])
    assert iof_base.keys() == {"extraction_fingerprint", "counts"}
    assert iof_base["extraction_fingerprint"] == f"rollup-fp-{seeded.run_id}"
    assert iof_base["counts"] == {
        "selected": 1,
        "extracted": 1,
        "no_findings": 0,
        "failed": 0,
        "findings_total": 6,
    }
    finding_id_strings = sorted(str(finding_id) for finding_id in seeded.finding_ids)
    assert base["finding_set"] == {
        "size": 6,
        "sha256": hashlib.sha256("\n".join(finding_id_strings).encode("utf-8")).hexdigest(),
    }
    assert row["counts"] == {"intervention": counts}


def test_memo_reused_docs_are_included(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    reused_record_id = uuid.uuid4()
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (uuid.uuid4(), [{"intervention": "Alpha fresh", "outcome": "Outcome"}]),
            (reused_record_id, [{"intervention": "Alpha reused", "outcome": "Outcome"}]),
        ],
        reused_record_ids={reused_record_id},
    )

    _, group_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    row = _group_row(conn, task_id, group_run_id)

    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in seeded.finding_ids
    }
    assert cast("dict[str, int]", row["counts"]["intervention"])["findings_total"] == 2


def test_foreign_run_findings_never_enter(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    run_a = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha in", "outcome": "Outcome"}])],
    )
    run_b = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Beta out", "outcome": "Outcome"}])],
    )

    _, group_run_id = _run_group(conn, task_id, scope_id, run_a.run_id)
    row = _group_row(conn, task_id, group_run_id)

    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in run_a.finding_ids
    }
    assert not _payload_finding_ids(cast("dict[str, Any]", row["groups"])) & {
        str(finding_id) for finding_id in run_b.finding_ids
    }


def test_integrity_cross_check_fails_on_corrupt_counts(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha one", "outcome": "Outcome"}])],
    )
    counts = cast(
        "dict[str, Any]",
        conn.execute(
            select(extraction_result.c.counts).where(extraction_result.c.run_id == seeded.run_id)
        ).scalar_one(),
    )
    counts["profiles"][IOF_PROFILE_ID]["findings"]["total"] = 2
    conn.execute(
        update(extraction_result)
        .where(extraction_result.c.run_id == seeded.run_id)
        .values(counts=counts)
    )

    with pytest.raises(GroupError, match="corrupt reference"):
        _run_group(conn, task_id, scope_id, seeded.run_id)
    assert _group_count(conn, task_id) == 0


def test_missing_rollup_row_fails_without_row(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    with pytest.raises(GroupError, match="run extract first"):
        _run_group(conn, task_id, scope_id, uuid.uuid4())
    assert _group_count(conn, task_id) == 0


def test_zero_findings_writes_empty_rollup_without_backend_call(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(conn, task_id, scope_id, docs=[])
    backend = StubGroupClusteringBackend()

    summary, group_run_id = _run_group(
        conn, task_id, scope_id, seeded.run_id, backend=backend
    )
    row = _group_row(conn, task_id, group_run_id)

    assert backend.calls == []
    assert summary["flags"] == {
        "intervention": {
            "status": "succeeded",
            "failure_class": None,
            "groups_rejected": False,
            "value_cap_exceeded": False,
        }
    }
    assert row["flags"] == summary["flags"]
    assert row["groups"] == {
        "intervention": {
            "groups": [],
            "ungrouped": {
                "values": [],
                "finding_ids": [],
                "member_finding_ids": [],
                "finding_kinds": [],
                "member_counts": {"iof": 0, "icf": 0},
                "direction_spread": _zero_spread(),
            },
            "no_value": {
                "finding_ids": [],
                "member_finding_ids": [],
                "finding_kinds": [],
                "member_counts": {"iof": 0, "icf": 0},
                "direction_spread": _zero_spread(),
            },
            "overall_direction_spread": _zero_spread(),
        }
    }
    assert summary["counts"]["intervention"] == {
        "eligible_base": 0,
        "findings_total": 0,
        "grouped": 0,
        "ungrouped": 0,
        "no_value": 0,
        "distinct_values": 0,
        "groups": 0,
    }


def test_all_null_population_goes_to_no_value_without_backend_call(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha service",
                        "outcome": "Outcome A",
                        "population": None,
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "Beta service",
                        "outcome": "Outcome B",
                        "population": None,
                        "effect_direction": "decrease",
                    },
                ],
            )
        ],
    )
    backend = StubGroupClusteringBackend()

    summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facets": ["population"]}},
        backend=backend,
    )
    row = _group_row(conn, task_id, group_run_id)

    assert backend.calls == []
    assert summary["facet"] == "population"
    assert summary["facet_source"] == "scope_context"
    assert summary["flags"]["population"]["status"] == "succeeded"
    assert summary["counts"]["population"]["no_value"] == 2
    assert summary["counts"]["population"]["groups"] == 0
    assert summary["residuals"]["population"]["no_value"]["finding_count"] == 2
    assert row["groups"].keys() == {"population"}
    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in seeded.finding_ids
    }


def test_mixed_unclear_directions_are_first_class_in_spreads(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha service",
                        "outcome": "Outcome A",
                        "effect_direction": "mixed",
                    },
                    {
                        "intervention": "Alpha programme",
                        "outcome": "Outcome B",
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "stubungroupable residual",
                        "outcome": "Outcome C",
                        "effect_direction": "unclear",
                    },
                ],
            )
        ],
    )

    summary, group_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    row = _group_row(conn, task_id, group_run_id)
    group = next(
        group for group in summary["groups"]["intervention"] if group["label"] == "alpha"
    )
    residual = summary["residuals"]["intervention"]["ungrouped"]

    assert group["direction_spread"]["mixed"] == 1
    assert group["direction_spread"]["increase"] == 1
    assert _spread_total(group["direction_spread"]) == group["size"]
    assert residual["direction_spread"]["unclear"] == 1
    assert _spread_total(residual["direction_spread"]) == residual["finding_count"]
    payload = cast("dict[str, Any]", row["groups"])
    stored_group = cast("list[dict[str, Any]]", _facet_payload(payload)["groups"])[0]
    assert cast("dict[str, int]", stored_group["direction_spread"])["mixed"] == 1
    assert (
        cast("dict[str, int]", _facet_payload(payload)["ungrouped"]["direction_spread"])[
            "unclear"
        ]
        == 1
    )


def test_group_membership_spans_iof_and_icf_with_iof_only_spread(
    conn: Connection,
) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    extraction_run_id = seed_run(conn, task_id)
    selection_run_id = seed_run(conn, task_id)
    snap_id, tss_id = seed_source(conn, task_id)
    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=selection_run_id,
            strategy="coverage_stratified_v1",
            budget=1,
            selection_provenance={"strategy": "test"},
            selected=[{"tss_id": str(tss_id), "text_basis": "full_text"}],
            excluded={},
            flags=[],
            created_at=now(),
        )
    )

    iof_record_id = uuid.uuid4()
    icf_record_id = uuid.uuid4()
    iof_finding_id = uuid.uuid4()
    icf_finding_id = uuid.uuid4()
    for record_id, fingerprint in (
        (iof_record_id, "fp-iof-group-bridge"),
        (icf_record_id, "fp-icf-group-bridge"),
    ):
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                task_id=task_id,
                source_snapshot_id=snap_id,
                task_source_snapshot_id=tss_id,
                extraction_fingerprint=fingerprint,
                status="extracted",
                basis="full_text",
                error=None,
                finding_count=1,
                run_id=extraction_run_id,
                created_at=now(),
            )
        )
    conn.execute(
        intervention_outcome_finding.insert().values(
            **_finding_values(
                task_id,
                iof_record_id,
                finding_id=iof_finding_id,
                intervention="Alpha service",
                outcome="Attendance",
                population="Adults",
                effect_direction="increase",
            )
        )
    )
    conn.execute(
        implementation_context_finding.insert().values(
            finding_id=icf_finding_id,
            task_id=task_id,
            extraction_record_id=icf_record_id,
            context_type="barrier",
            claim="Training gaps slowed Alpha service delivery.",
            intervention="Alpha service",
            outcome="Attendance",
            population="Adults",
            setting=None,
            study_geography=None,
            study_design=None,
            claim_level="study",
            claim_basis="studied",
            level="provider",
            resource_requirements=None,
            workforce_requirements="training",
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    profile_counts = {
        "selected": 1,
        "extracted": 1,
        "no_findings": 0,
        "failed": 0,
        "fresh": 1,
        "reused": 0,
        "findings": {
            "total": 1,
            "quote_unverified": 0,
            "dedup_collapsed": 0,
            "invalid_dropped": 0,
        },
        "basis": {
            "full_text": 1,
            "abstract_only": 0,
            "shares": {"full_text": 1.0, "abstract_only": 0.0},
        },
        "field_coverage": {},
    }
    conn.execute(
        extraction_result.insert().values(
            extraction_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "profiles": {
                    IOF_PROFILE_ID: {"fingerprint": "rollup-iof", "profile": IOF_PROFILE_ID},
                    ICF_PROFILE_ID: {"fingerprint": "rollup-icf", "profile": ICF_PROFILE_ID},
                },
                "pass_count": 1,
            },
            docs=[
                {
                    "tss_id": str(tss_id),
                    "basis": "full_text",
                    "profiles": {
                        IOF_PROFILE_ID: {
                            "status": "extracted",
                            "basis": "full_text",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(iof_record_id),
                            "order": 0,
                        },
                        ICF_PROFILE_ID: {
                            "status": "extracted",
                            "basis": "full_text",
                            "finding_count": 1,
                            "reused": False,
                            "error": None,
                            "extraction_record_id": str(icf_record_id),
                            "order": 0,
                        },
                    },
                }
            ],
            counts={
                "selected": 1,
                "basis": profile_counts["basis"],
                "profiles": {
                    IOF_PROFILE_ID: profile_counts,
                    ICF_PROFILE_ID: profile_counts,
                },
            },
            flags=[],
            created_at=now(),
        )
    )

    summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        extraction_run_id,
        backend=StubGroupClusteringBackend(),
    )

    assert summary["counts"]["intervention"]["findings_total"] == 2
    payload = cast("dict[str, Any]", _group_row(conn, task_id, group_run_id)["groups"])
    group = _facet_payload(payload)["groups"][0]
    members_by_id = dict(
        zip(group["member_finding_ids"], group["member_finding_kinds"], strict=True)
    )
    assert members_by_id == {str(iof_finding_id): "iof", str(icf_finding_id): "icf"}
    assert group["member_counts"] == {"iof": 1, "icf": 1}
    assert group["direction_spread"]["increase"] == 1
    assert sum(group["direction_spread"].values()) == 1
    assert (
        sum(
            cast(
                "dict[str, int]",
                _facet_payload(payload)["overall_direction_spread"],
            ).values()
        )
        == 1
    )
    provenance = cast(
        "dict[str, Any]", _group_row(conn, task_id, group_run_id)["grouping_provenance"]
    )
    base = cast("dict[str, Any]", provenance["extraction_base"])
    assert base["profiles"].keys() == {IOF_PROFILE_ID, ICF_PROFILE_ID}
    assert base["profiles"][IOF_PROFILE_ID]["extraction_fingerprint"] == "rollup-iof"
    assert base["profiles"][ICF_PROFILE_ID]["extraction_fingerprint"] == "rollup-icf"
    assert base["profiles"][ICF_PROFILE_ID]["counts"]["findings_total"] == 1


def test_value_reference_loader_matches_old_two_table_projection(
    conn: Connection,
) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_mixed_extraction(
        conn,
        task_id,
        scope_id,
        iof_findings=[
            {
                "finding_id": uuid.UUID(int=21),
                "intervention": "Alpha service",
                "outcome": "Attendance",
                "population": "Adults",
            }
        ],
        icf_findings=[
            {
                "finding_id": uuid.UUID(int=22),
                "context_type": "barrier",
                "claim": "Staffing slowed Alpha service.",
                "intervention": "Alpha service",
                "outcome": "Attendance",
                "population": "Adults",
            }
        ],
    )

    loaded = _load_finding_references(
        conn,
        task_id=task_id,
        extraction_record_ids_by_kind={
            "iof": [seeded.iof_record_id],
            "icf": [seeded.icf_record_id],
        },
    )

    projected = [
        {
            "finding_id": str(row["finding_id"]),
            "kind": row["kind"],
            "intervention": row["intervention"],
            "outcome": row["outcome"],
            "population": row["population"],
        }
        for row in loaded
    ]
    assert sorted(projected, key=lambda item: item["finding_id"]) == [
        {
            "finding_id": str(uuid.UUID(int=21)),
            "kind": "iof",
            "intervention": "Alpha service",
            "outcome": "Attendance",
            "population": "Adults",
        },
        {
            "finding_id": str(uuid.UUID(int=22)),
            "kind": "icf",
            "intervention": "Alpha service",
            "outcome": "Attendance",
            "population": "Adults",
        },
    ]


def test_multi_facet_value_and_claim_theme_run_writes_one_row(
    conn: Connection,
) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_mixed_extraction(
        conn,
        task_id,
        scope_id,
        iof_findings=[
            {"intervention": "Alpha service", "outcome": "Attendance"},
            {"intervention": "Beta service", "outcome": "Retention"},
        ],
        icf_findings=[
            {
                "finding_id": uuid.UUID(int=31),
                "context_type": "barrier",
                "claim": "Staff shortages slowed Alpha service delivery.",
                "context_label": "Staff shortages",
                "intervention": "Alpha service",
            },
            {
                "finding_id": uuid.UUID(int=32),
                "context_type": "barrier",
                "claim": "Training gaps delayed Beta service delivery.",
                "context_label": "Training",
                "intervention": "Beta service",
            },
        ],
    )

    summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facets": ["intervention", "barrier_theme"]}},
    )
    row = _group_row(conn, task_id, group_run_id)

    assert _group_count(conn, task_id) == 1
    assert summary["facets"] == ["intervention", "barrier_theme"]
    assert row["groups"].keys() == {"intervention", "barrier_theme"}
    assert row["counts"]["intervention"]["eligible_base"] == 4
    assert row["counts"]["barrier_theme"] == {
        "eligible_base": 2,
        "grouped": 2,
        "ungrouped": 0,
        "groups": 2,
    }
    assert row["flags"]["intervention"]["status"] == "succeeded"
    assert row["flags"]["barrier_theme"]["status"] == "succeeded"
    claim_payload = row["groups"]["barrier_theme"]
    assert "no_value" not in claim_payload
    assert claim_payload["groups"][0]["group_id"] == "barrier_theme:g01"
    assert claim_payload["groups"][0]["direction_spread"] is None
    assert row["grouping_provenance"]["facets"] == ["intervention", "barrier_theme"]
    assert row["grouping_provenance"]["facet_runs"]["barrier_theme"][
        "eligible_base_size"
    ] == 2


def test_claim_theme_eligibility_excludes_iof_and_nonmatching_icf_and_hashes_base(
    conn: Connection,
) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    barrier_id = uuid.UUID(int=41)
    enabler_id = uuid.UUID(int=42)
    seeded = seed_mixed_extraction(
        conn,
        task_id,
        scope_id,
        iof_findings=[{"intervention": "Alpha service", "outcome": "Attendance"}],
        icf_findings=[
            {
                "finding_id": barrier_id,
                "context_type": "barrier",
                "claim": "Procurement delays slowed Alpha service.",
                "context_label": "Procurement",
                "intervention": "Alpha service",
            },
            {
                "finding_id": enabler_id,
                "context_type": "enabler",
                "claim": "Senior sponsorship helped Alpha service.",
                "context_label": "Sponsorship",
                "intervention": "Alpha service",
            },
        ],
    )

    _summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facets": ["barrier_theme"]}},
    )
    row = _group_row(conn, task_id, group_run_id)

    payload_ids = _payload_finding_ids(cast("dict[str, Any]", row["groups"]))
    assert payload_ids == {str(barrier_id)}
    assert str(enabler_id) not in payload_ids
    assert not ({str(finding_id) for finding_id in seeded.iof_finding_ids} & payload_ids)
    expected_hash = claim_theme_base_sha256(
        [
            ClaimThemeUnit(
                finding_id=str(barrier_id),
                claim="Procurement delays slowed Alpha service.",
                context_label="Procurement",
                intervention="Alpha service",
            )
        ]
    )
    facet_provenance = row["grouping_provenance"]["facet_runs"]["barrier_theme"]
    assert facet_provenance["eligible_base_size"] == 1
    assert facet_provenance["eligible_base_sha256"] == expected_hash


def test_per_facet_backend_failure_isolates_to_failed_facet(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {"intervention": "Alpha service", "outcome": "Attendance"},
                    {"intervention": "Beta service", "outcome": "Retention"},
                ],
            )
        ],
    )

    _summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facets": ["intervention", "outcome"]}},
        backend=StubGroupClusteringBackend(fail_facets={"outcome"}),
    )
    row = _group_row(conn, task_id, group_run_id)

    assert row["flags"]["intervention"]["status"] == "succeeded"
    assert row["flags"]["outcome"] == {
        "status": "failed",
        "failure_class": "backend_error",
        "groups_rejected": True,
        "value_cap_exceeded": False,
    }
    assert row["counts"]["outcome"]["grouped"] == 0
    assert row["counts"]["outcome"]["ungrouped"] == 2
    assert row["grouping_provenance"]["facet_runs"]["outcome"]["rejection_reasons"]


def test_zero_discovered_groups_is_legal_all_residual_path(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {"intervention": "Alpha service", "outcome": "Attendance"},
                    {"intervention": "Beta service", "outcome": "Retention"},
                ],
            )
        ],
    )

    _summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        backend=StubGroupClusteringBackend(zero_label_facets={"intervention"}),
    )
    row = _group_row(conn, task_id, group_run_id)

    assert row["flags"]["intervention"]["status"] == "succeeded"
    assert row["counts"]["intervention"]["groups"] == 0
    assert row["counts"]["intervention"]["grouped"] == 0
    assert row["counts"]["intervention"]["ungrouped"] == 2
    assert row["groups"]["intervention"]["groups"] == []


def test_group_ceiling_and_call_budget_formula() -> None:
    assert group_max_labels(0) == 3
    assert group_max_labels(1) == 3
    assert group_max_labels(15) == 3
    assert group_max_labels(16) == 4
    assert group_max_labels(1_000) == 40
    assert group_call_budget(0) == 2
    assert group_call_budget(1) == 4


# --- D8 grouping.granularity ---


def test_group_max_labels_standard_and_absent_are_byte_identical_to_as_built() -> None:
    """Guard test: 'standard' and the default param reproduce the as-built ceiling."""
    for unit_count in (0, 1, 15, 16, 60, 1_000):
        base = group_max_labels(unit_count)
        assert group_max_labels(unit_count, granularity="standard") == base


def test_group_max_labels_coarser_halves_and_finer_doubles() -> None:
    # unit_count=60 -> base ceil(60/5)=12, comfortably inside [3, 40] both ways.
    assert group_max_labels(60) == 12
    assert group_max_labels(60, granularity="coarser") == 6
    assert group_max_labels(60, granularity="finer") == 24


def test_group_max_labels_granularity_respects_hard_floor_and_cap() -> None:
    # Small unit_count: base is already at the floor (3); coarser cannot go below it.
    assert group_max_labels(1, granularity="coarser") == 3
    # Huge unit_count: base is already at the cap (40); finer cannot exceed it.
    assert group_max_labels(1_000, granularity="finer") == 40


def test_group_granularity_flows_to_provenance_and_multiplies_ceiling(
    conn: Connection,
) -> None:
    """D8 behavioural effect: granularity multiplies the ceiling actually used,
    and is echoed verbatim in grouping_provenance."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    # Same 6-distinct-intervention fixture as the happy-path test: base ceiling
    # group_max_labels(6) == 3 (floor); "finer" doubles it to 6.
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha counseling",
                        "outcome": "Attendance",
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "Alpha coaching",
                        "outcome": "Retention",
                        "effect_direction": "decrease",
                    },
                    {
                        "intervention": "Beta home visits",
                        "outcome": "Employment",
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "Beta phone calls",
                        "outcome": "Employment",
                        "effect_direction": "no_effect",
                    },
                    {
                        "intervention": "Gamma support",
                        "outcome": "Wellbeing",
                        "effect_direction": "mixed",
                    },
                    {
                        "intervention": "Delta reach-out",
                        "outcome": "Wellbeing",
                        "effect_direction": "unclear",
                    },
                ],
            )
        ],
    )

    _summary, group_run_id = _run_group(
        conn, task_id, scope_id, seeded.run_id,
        context={"grouping": {"granularity": "finer"}},
    )
    row = _group_row(conn, task_id, group_run_id)

    assert row["grouping_provenance"]["granularity"] == "finer"
    assert row["grouping_provenance"]["facet_runs"]["intervention"]["max_labels"] == (
        group_max_labels(6, granularity="finer")
    )
    assert group_max_labels(6, granularity="finer") == 6
    assert group_call_budget(50) == 4
    assert group_call_budget(51) == 6


# --- B3 grouping.guidance ---


def test_group_guidance_flows_to_provenance_and_discovery_only(conn: Connection) -> None:
    """B3 behavioural + isolation: guidance is echoed verbatim in
    grouping_provenance and reaches the stub's discover() call only — never
    assign()."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha counseling",
                        "outcome": "Attendance",
                        "effect_direction": "increase",
                    },
                    {
                        "intervention": "Beta home visits",
                        "outcome": "Employment",
                        "effect_direction": "increase",
                    },
                ],
            )
        ],
    )

    backend = StubGroupClusteringBackend()
    guidance = ["organise by policy instrument, not sector"]
    _summary, group_run_id = _run_group(
        conn, task_id, scope_id, seeded.run_id,
        context={"grouping": {"guidance": guidance}},
        backend=backend,
    )
    row = _group_row(conn, task_id, group_run_id)

    assert row["grouping_provenance"]["guidance"] == guidance
    discover_calls = [call for call in backend.calls if call.stage == "discover"]
    assign_calls = [call for call in backend.calls if call.stage == "assign"]
    assert discover_calls and all(call.guidance == guidance for call in discover_calls)
    assert assign_calls and all(call.guidance is None for call in assign_calls)


def test_group_guidance_absent_is_byte_identical_to_as_built(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha counseling",
                        "outcome": "Attendance",
                        "effect_direction": "increase",
                    },
                ],
            )
        ],
    )

    _summary, group_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    row = _group_row(conn, task_id, group_run_id)

    assert row["grouping_provenance"]["guidance"] is None


def test_value_context_payloads_are_deterministic_and_discovery_gated(
    conn: Connection,
) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    long_quote = "q" * 300
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "finding_id": uuid.UUID(int=3),
                        "intervention": "Alpha service",
                        "outcome": "Attendance",
                        "grounding": [{"quote": "third"}],
                    },
                    {
                        "finding_id": uuid.UUID(int=1),
                        "intervention": "Alpha service",
                        "outcome": "Retention",
                        "grounding": [{"quote": long_quote}],
                    },
                    {
                        "finding_id": uuid.UUID(int=2),
                        "intervention": "Alpha service",
                        "outcome": "Wellbeing",
                        "grounding": [{"quote": "second"}],
                    },
                ],
            )
        ],
    )
    backend = StubGroupClusteringBackend()

    _run_group(conn, task_id, scope_id, seeded.run_id, backend=backend)

    discover_call = next(call for call in backend.calls if call.stage == "discover")
    assign_call = next(call for call in backend.calls if call.stage == "assign")
    expected_anchors = [
        {"finding_id": str(uuid.UUID(int=1)), "quote": long_quote[:240]},
        {"finding_id": str(uuid.UUID(int=2)), "quote": "second"},
    ]
    assert discover_call.payloads[0]["context"]["anchors"] == expected_anchors
    assert assign_call.payloads[0]["context"]["anchors"] == expected_anchors

    large_scope_id = seed_scope(conn, task_id)
    large_seeded = seed_extraction(
        conn,
        task_id,
        large_scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": f"Distinct {index:03d}",
                        "outcome": "Attendance",
                        "grounding": [{"quote": f"quote {index}"}],
                    }
                    for index in range(121)
                ],
            )
        ],
    )
    large_backend = StubGroupClusteringBackend()

    _run_group(conn, task_id, large_scope_id, large_seeded.run_id, backend=large_backend)

    large_discover = next(call for call in large_backend.calls if call.stage == "discover")
    large_assign = next(call for call in large_backend.calls if call.stage == "assign")
    assert large_discover.payloads[0]["context"] == {}
    assert large_assign.payloads[0]["context"]["anchors"]


def test_mixed_unclear_findings_never_dropped_by_group(conn: Connection) -> None:
    """V2 silent-zeroing autopsy (task 020 C7): findings with effect_direction
    'mixed'/'unclear' are first-class group members, not just spread-count
    entries — every finding_id must survive into the persisted membership
    (a group, or a residual bucket), never silently dropped at aggregation."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha service",
                        "outcome": "Outcome A",
                        "effect_direction": "mixed",
                    },
                    {
                        "intervention": "Alpha programme",
                        "outcome": "Outcome B",
                        "effect_direction": "unclear",
                    },
                    {
                        "intervention": "Alpha clinic",
                        "outcome": "Outcome C",
                        "effect_direction": "increase",
                    },
                ],
            )
        ],
    )

    _summary, group_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    row = _group_row(conn, task_id, group_run_id)
    membership = _payload_finding_ids(cast("dict[str, Any]", row["groups"]))

    assert membership == {str(finding_id) for finding_id in seeded.finding_ids}


def test_backend_failure_persists_failed_facet_with_full_residual(
    conn: Connection,
) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha one", "outcome": "Outcome"}])],
    )

    _summary, group_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        backend=StubGroupClusteringBackend(fail_facets={"intervention"}),
    )
    row = _group_row(conn, task_id, group_run_id)

    assert row["flags"]["intervention"] == {
        "status": "failed",
        "failure_class": "backend_error",
        "groups_rejected": True,
        "value_cap_exceeded": False,
    }
    payload = cast("dict[str, Any]", row["groups"])
    assert _facet_payload(payload)["groups"] == []
    assert _payload_finding_ids(payload) == {str(finding_id) for finding_id in seeded.finding_ids}


def test_determinism_over_same_extraction_run(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {"intervention": "Alpha service", "outcome": "Outcome A"},
                    {"intervention": "Alpha programme", "outcome": "Outcome B"},
                    {"intervention": "Beta service", "outcome": "Outcome C"},
                ],
            )
        ],
    )

    _, first_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    _, second_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    first = _group_row(conn, task_id, first_run_id)
    second = _group_row(conn, task_id, second_run_id)

    for key in ("groups", "counts", "flags", "grouping_provenance"):
        assert first[key] == second[key]
    assert first["run_id"] != second["run_id"]


def test_same_run_reexecution_is_loud_integrity_error(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha one", "outcome": "Outcome"}])],
    )
    group_run_id = seed_run(conn, task_id)

    _run_group(conn, task_id, scope_id, seeded.run_id, run_id=group_run_id)
    with pytest.raises(IntegrityError, match="uq_grr_scope_run"), conn.begin_nested():
        _run_group(conn, task_id, scope_id, seeded.run_id, run_id=group_run_id)


def test_directive_default_scope_context_and_malformed_fail_closed(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha intervention",
                        "outcome": "Outcome retention",
                    },
                    {
                        "intervention": "Beta intervention",
                        "outcome": "Outcome attendance",
                    },
                ],
            )
        ],
    )

    default_summary, default_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)
    default_row = _group_row(conn, task_id, default_run_id)
    assert default_summary["facet"] == "intervention"
    assert default_summary["facet_source"] == "default"
    assert default_row["groups"].keys() == {"intervention"}
    assert default_row["grouping_provenance"]["facets"] == ["intervention"]
    assert default_row["grouping_provenance"]["facet_source"] == "default"

    outcome_summary, outcome_run_id = _run_group(
        conn,
        task_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facets": ["outcome"]}},
    )
    outcome_row = _group_row(conn, task_id, outcome_run_id)
    assert outcome_summary["facet"] == "outcome"
    assert outcome_summary["facet_source"] == "scope_context"
    assert outcome_row["groups"].keys() == {"outcome"}
    assert outcome_row["grouping_provenance"]["facets"] == ["outcome"]
    assert outcome_row["grouping_provenance"]["facet"] == "outcome"
    assert outcome_row["grouping_provenance"]["facet_source"] == "scope_context"

    existing_group_count = _group_count(conn, task_id)
    for malformed in (
        {"grouping": {"facet": "bogus"}},
        {"grouping": {"facet": "intervention", "unknown": True}},
        {"grouping": {"facets": ["intervention", "intervention"]}},
    ):
        backend = StubGroupClusteringBackend()
        with pytest.raises(FacetDirectiveError):
            _run_group(
                conn,
                task_id,
                scope_id,
                seeded.run_id,
                context=malformed,
                backend=backend,
            )
        assert backend.calls == []
        assert _group_count(conn, task_id) == existing_group_count


def test_value_cap_fails_before_backend_call(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": f"Distinct intervention {index:03d}",
                        "outcome": "Outcome",
                    }
                    for index in range(FACET_VALUE_CAP + 1)
                ],
            )
        ],
    )
    backend = StubGroupClusteringBackend()

    _summary, group_run_id = _run_group(
        conn, task_id, scope_id, seeded.run_id, backend=backend
    )
    row = _group_row(conn, task_id, group_run_id)

    assert backend.calls == []
    assert row["flags"]["intervention"]["status"] == "failed"
    assert row["flags"]["intervention"]["failure_class"] == "cap_exceeded"
    assert row["flags"]["intervention"]["value_cap_exceeded"] is True
    assert row["counts"]["intervention"]["eligible_base"] == FACET_VALUE_CAP + 1
    assert row["counts"]["intervention"]["ungrouped"] == FACET_VALUE_CAP + 1


def test_value_surface_too_long_fails_before_backend_call(conn: Connection) -> None:
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "x" * (VALUE_SURFACE_MAX + 1),
                        "outcome": "Outcome",
                    }
                ],
            )
        ],
    )
    backend = StubGroupClusteringBackend()

    _summary, group_run_id = _run_group(
        conn, task_id, scope_id, seeded.run_id, backend=backend
    )
    row = _group_row(conn, task_id, group_run_id)

    assert backend.calls == []
    assert row["flags"]["intervention"]["status"] == "failed"
    assert row["flags"]["intervention"]["failure_class"] == "validation_failed"
    reasons = row["grouping_provenance"]["facet_runs"]["intervention"]["rejection_reasons"]
    assert any("value_surface_too_long" in reason for reason in reasons)


def test_invalid_discovered_label_fails_facet_not_component(conn: Connection) -> None:
    """Phase C repin: discovery label validation is facet-local."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = seed_extraction(
        conn,
        task_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {"intervention": "Alpha service", "outcome": "Outcome A"},
                    {"intervention": "Beta service", "outcome": "Outcome B"},
                    {"intervention": "Gamma service", "outcome": "Outcome C"},
                ],
            )
        ],
    )
    backend = ScriptedGroupClusteringBackend(
        labels=[ClusterLabel(label="x" * (LABEL_MAX + 1), description="Fine.")]
    )

    summary, group_run_id = _run_group(
        conn, task_id, scope_id, seeded.run_id, backend=backend
    )
    row = _group_row(conn, task_id, group_run_id)

    assert backend.discovery_calls == 2
    assert backend.assignment_calls == 0
    assert summary["counts"]["intervention"]["groups"] == 0
    assert summary["counts"]["intervention"]["ungrouped"] == 3
    assert summary["flags"]["intervention"] == {
        "status": "failed",
        "failure_class": "discovery_exhausted",
        "groups_rejected": True,
        "value_cap_exceeded": False,
    }
    reasons = row["grouping_provenance"]["facet_runs"]["intervention"]["rejection_reasons"]
    assert reasons and f"exceeds {LABEL_MAX} chars" in reasons[0]


def _zero_spread() -> dict[str, int]:
    return {"increase": 0, "decrease": 0, "no_effect": 0, "mixed": 0, "unclear": 0}


# --- Review-stack fixes (022 step 7): sentinel labels + bounded claim surfaces


def test_forbidden_group_label_rejects_component_sentinels() -> None:
    assert _forbidden_group_label_reason(0, "Ungroupable") is not None
    assert _forbidden_group_label_reason(1, GROUP_RESIDUAL_LABEL) is not None
    assert _forbidden_group_label_reason(2, "Heat pump tariffs") is None


def test_claim_cluster_units_bound_untrusted_surfaces() -> None:
    hostile_label = "x" * (CONTEXT_LABEL_SURFACE_MAX * 4)
    long_claim = "c" * (CLAIM_SURFACE_MAX + 50)
    unit = _claim_cluster_units(
        [
            ClaimThemeUnit(
                finding_id="f-1",
                claim=long_claim,
                context_label=hostile_label,
                intervention="heat\x00pumps\nrollout",
            )
        ]
    )[0]
    payload = unit.payload
    assert len(payload["claim"]) <= CLAIM_SURFACE_MAX
    assert payload["claim"] == payload["text"]
    assert len(payload["context"]["context_label"]) <= CONTEXT_LABEL_SURFACE_MAX
    # Control characters (incl. newlines) are replaced with spaces, never kept.
    assert payload["context"]["intervention"] == "heat pumps rollout"
