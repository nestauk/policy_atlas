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

from policy_atlas.facet_grouping import (
    FACET_VALUE_CAP,
    PROMPT_VERSION,
    FacetValueRecord,
    PartitionResult,
    ProposedGroup,
    StubFacetGroupingBackend,
)
from policy_atlas.facet_values import FacetDirectiveError
from policy_atlas.group import GroupContext, GroupError, group_findings
from policy_atlas.schema import (
    extraction_result,
    grouping_result,
    intervention_outcome_finding,
    selection_result,
    source_extraction_record,
)

from .helpers import now, seed_project_and_run, seed_run, seed_scope, seed_source

DocSpec = tuple[uuid.UUID, list[dict[str, Any]]]


@dataclass(frozen=True)
class SeededExtraction:
    run_id: uuid.UUID
    selection_run_id: uuid.UUID
    record_ids: list[uuid.UUID]
    finding_ids: list[uuid.UUID]


class CountingFacetGroupingBackend:
    mode = "stub"

    def __init__(
        self,
        *,
        partition_result: PartitionResult | None = None,
        repair_result: PartitionResult | None = None,
    ) -> None:
        self.partition_calls = 0
        self.repair_calls = 0
        self.partition_result = partition_result or {"groups": [], "ungroupable": []}
        self.repair_result = repair_result or {"groups": [], "ungroupable": []}

    def partition(
        self, values: list[FacetValueRecord], *, facet: str
    ) -> PartitionResult:
        del values, facet
        self.partition_calls += 1
        return self.partition_result

    def repair(
        self,
        missing_values: list[FacetValueRecord],
        *,
        facet: str,
        accepted_groups: list[ProposedGroup],
    ) -> PartitionResult:
        del missing_values, facet, accepted_groups
        self.repair_calls += 1
        return self.repair_result


def seed_extraction(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    *,
    docs: list[DocSpec],
    extraction_run_id: uuid.UUID | None = None,
    reused_record_ids: set[uuid.UUID] | None = None,
) -> SeededExtraction:
    extraction_run_id = extraction_run_id or seed_run(conn, project_id)
    selection_run_id = seed_run(conn, project_id)
    reused_record_ids = reused_record_ids or set()
    selected: list[dict[str, Any]] = []
    doc_payloads: list[dict[str, Any]] = []
    finding_ids: list[uuid.UUID] = []
    record_ids: list[uuid.UUID] = []

    conn.execute(
        selection_result.insert().values(
            selection_result_id=uuid.uuid4(),
            project_id=project_id,
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
        snap_id, pss_id = seed_source(conn, project_id)
        selected.append({"pss_id": str(pss_id), "text_basis": "full_text"})
        status = "extracted" if findings else "no_findings"
        record_ids.append(record_id)
        conn.execute(
            source_extraction_record.insert().values(
                extraction_record_id=record_id,
                project_id=project_id,
                source_snapshot_id=snap_id,
                project_source_snapshot_id=pss_id,
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
            values = _finding_values(project_id, record_id, **finding)
            finding_ids.append(cast("uuid.UUID", values["finding_id"]))
            conn.execute(intervention_outcome_finding.insert().values(**values))
        doc_payloads.append(
            {
                "pss_id": str(pss_id),
                "status": status,
                "basis": "full_text",
                "finding_count": len(findings),
                "reused": record_id in reused_record_ids,
                "error": None,
                "extraction_record_id": str(record_id),
                "order": index,
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
            project_id=project_id,
            evidence_scope_id=scope_id,
            run_id=extraction_run_id,
            selection_run_id=selection_run_id,
            extraction_provenance={
                "fingerprint": f"rollup-fp-{extraction_run_id}",
                "profile": "test-profile",
            },
            docs=doc_payloads,
            counts={
                "selected": len(docs),
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
                "basis": {
                    "full_text": len(docs),
                    "abstract_only": 0,
                    "shares": {"full_text": 1.0 if docs else 0.0, "abstract_only": 0.0},
                },
                "field_coverage": {},
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


def _finding_values(
    project_id: uuid.UUID,
    extraction_record_id: uuid.UUID,
    **overrides: Any,
) -> dict[str, Any]:
    values: dict[str, Any] = {
        "finding_id": uuid.uuid4(),
        "project_id": project_id,
        "extraction_record_id": extraction_record_id,
        "intervention": "Alpha service",
        "outcome": "Health outcome",
        "population": "Adults",
        "comparator": None,
        "effect_direction": "positive",
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


def _run_group(
    conn: Connection,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    *,
    run_id: uuid.UUID | None = None,
    context: dict[str, Any] | None = None,
    backend: StubFacetGroupingBackend | CountingFacetGroupingBackend | None = None,
) -> tuple[dict[str, Any], uuid.UUID]:
    run_id = run_id or seed_run(conn, project_id)
    summary = group_findings(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=GroupContext(
            scope_id=scope_id,
            intent="This intent must not enter grouping.",
            context=context or {},
            extraction_run_id=extraction_run_id,
        ),
        facet_grouping_backend=backend or StubFacetGroupingBackend(),
    )
    return summary, run_id


def _group_row(conn: Connection, project_id: uuid.UUID, run_id: uuid.UUID) -> dict[str, Any]:
    row = conn.execute(
        select(grouping_result)
        .where(grouping_result.c.project_id == project_id)
        .where(grouping_result.c.run_id == run_id)
    ).mappings().one()
    return dict(row)


def _group_count(conn: Connection, project_id: uuid.UUID) -> int:
    return conn.execute(
        select(func.count())
        .select_from(grouping_result)
        .where(grouping_result.c.project_id == project_id)
    ).scalar_one()


def _payload_finding_ids(payload: dict[str, Any]) -> set[str]:
    groups = cast("list[dict[str, Any]]", payload["groups"])
    ungrouped = cast("dict[str, Any]", payload["ungrouped"])
    no_value = cast("dict[str, Any]", payload["no_value"])
    return {
        finding_id
        for group in groups
        for finding_id in cast("list[str]", group["member_finding_ids"])
    } | set(cast("list[str]", ungrouped["finding_ids"])) | set(
        cast("list[str]", no_value["finding_ids"])
    )


def _spread_total(spread: dict[str, int]) -> int:
    return sum(spread.values())


def test_happy_path_writes_rollup_summary_and_provenance(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha counseling",
                        "outcome": "Attendance",
                        "effect_direction": "positive",
                    },
                    {
                        "intervention": "Alpha coaching",
                        "outcome": "Retention",
                        "effect_direction": "negative",
                    },
                    {
                        "intervention": "Beta home visits",
                        "outcome": "Employment",
                        "effect_direction": "positive",
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

    summary, group_run_id = _run_group(conn, project_id, scope_id, seeded.run_id)
    row = _group_row(conn, project_id, group_run_id)

    assert summary.keys() == {
        "facet",
        "facet_source",
        "groups",
        "residuals",
        "overall_direction_spread",
        "counts",
        "extraction_run_id",
        "flags",
        "provenance",
    }
    assert row["facet"] == "intervention"
    assert row["flags"] == ["ungrouped_values"]
    assert summary["facet"] == "intervention"
    assert summary["facet_source"] == "default"
    assert summary["extraction_run_id"] == str(seeded.run_id)
    assert summary["flags"] == ["ungrouped_values"]
    assert summary["counts"] == {
        "findings_total": 6,
        "grouped": 5,
        "ungrouped": 1,
        "no_value": 0,
        "distinct_values": 6,
        "groups": 3,
    }
    assert [group["label"] for group in summary["groups"]] == ["alpha", "beta", "gamma"]
    assert [group["size"] for group in summary["groups"]] == [2, 2, 1]
    assert [group["value_count"] for group in summary["groups"]] == [2, 2, 1]
    assert summary["residuals"]["ungrouped"]["value_count"] == 1
    assert summary["residuals"]["ungrouped"]["finding_count"] == 1
    assert summary["residuals"]["no_value"]["finding_count"] == 0
    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in seeded.finding_ids
    }
    assert sum(summary["counts"][key] for key in ("grouped", "ungrouped", "no_value")) == 6

    provenance = cast("dict[str, Any]", row["grouping_provenance"])
    assert provenance.keys() == {
        "prompt_version",
        "model",
        "mode",
        "facet",
        "facet_source",
        "value_cap",
        "call_count",
        "repair_count",
        "distinct_value_count",
        "extraction_run_id",
        "extraction_base",
    }
    assert provenance["prompt_version"] == PROMPT_VERSION
    assert provenance["model"] == "stub"
    assert provenance["mode"] == "stub"
    assert provenance["facet"] == "intervention"
    assert provenance["facet_source"] == "default"
    assert provenance["value_cap"] == FACET_VALUE_CAP
    assert provenance["call_count"] == 1
    assert provenance["repair_count"] == 0
    assert provenance["distinct_value_count"] == 6
    base = cast("dict[str, Any]", provenance["extraction_base"])
    assert base.keys() == {
        "extraction_fingerprint",
        "profile",
        "counts",
        "finding_set",
        "facet_coverage",
    }
    assert base["extraction_fingerprint"] == f"rollup-fp-{seeded.run_id}"
    assert base["profile"] == "test-profile"
    assert base["counts"] == {
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
    assert base["facet_coverage"] == {"values_with_findings": 6, "no_value_count": 0}
    assert row["counts"] == summary["counts"]


def test_memo_reused_docs_are_included(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    reused_record_id = uuid.uuid4()
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[
            (uuid.uuid4(), [{"intervention": "Alpha fresh", "outcome": "Outcome"}]),
            (reused_record_id, [{"intervention": "Alpha reused", "outcome": "Outcome"}]),
        ],
        reused_record_ids={reused_record_id},
    )

    _, group_run_id = _run_group(conn, project_id, scope_id, seeded.run_id)
    row = _group_row(conn, project_id, group_run_id)

    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in seeded.finding_ids
    }
    assert cast("dict[str, int]", row["counts"])["findings_total"] == 2


def test_foreign_run_findings_never_enter(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    run_a = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha in", "outcome": "Outcome"}])],
    )
    run_b = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Beta out", "outcome": "Outcome"}])],
    )

    _, group_run_id = _run_group(conn, project_id, scope_id, run_a.run_id)
    row = _group_row(conn, project_id, group_run_id)

    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in run_a.finding_ids
    }
    assert not _payload_finding_ids(cast("dict[str, Any]", row["groups"])) & {
        str(finding_id) for finding_id in run_b.finding_ids
    }


def test_integrity_cross_check_fails_on_corrupt_counts(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha one", "outcome": "Outcome"}])],
    )
    counts = cast(
        "dict[str, Any]",
        conn.execute(
            select(extraction_result.c.counts).where(extraction_result.c.run_id == seeded.run_id)
        ).scalar_one(),
    )
    counts["findings"]["total"] = 2
    conn.execute(
        update(extraction_result)
        .where(extraction_result.c.run_id == seeded.run_id)
        .values(counts=counts)
    )

    with pytest.raises(GroupError, match="corrupt reference"):
        _run_group(conn, project_id, scope_id, seeded.run_id)
    assert _group_count(conn, project_id) == 0


def test_missing_rollup_row_fails_without_row(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)

    with pytest.raises(GroupError, match="run extract first"):
        _run_group(conn, project_id, scope_id, uuid.uuid4())
    assert _group_count(conn, project_id) == 0


def test_zero_findings_writes_empty_rollup_without_backend_call(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(conn, project_id, scope_id, docs=[])
    backend = CountingFacetGroupingBackend()

    summary, group_run_id = _run_group(
        conn, project_id, scope_id, seeded.run_id, backend=backend
    )
    row = _group_row(conn, project_id, group_run_id)

    assert backend.partition_calls == 0
    assert backend.repair_calls == 0
    assert summary["flags"] == ["empty_findings"]
    assert row["flags"] == ["empty_findings"]
    assert row["groups"] == {
        "groups": [],
        "ungrouped": {"values": [], "finding_ids": [], "direction_spread": _zero_spread()},
        "no_value": {"finding_ids": [], "direction_spread": _zero_spread()},
    }
    assert summary["counts"] == {
        "findings_total": 0,
        "grouped": 0,
        "ungrouped": 0,
        "no_value": 0,
        "distinct_values": 0,
        "groups": 0,
    }


def test_all_null_population_goes_to_no_value_without_backend_call(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[
            (
                uuid.uuid4(),
                [
                    {
                        "intervention": "Alpha service",
                        "outcome": "Outcome A",
                        "population": None,
                        "effect_direction": "positive",
                    },
                    {
                        "intervention": "Beta service",
                        "outcome": "Outcome B",
                        "population": None,
                        "effect_direction": "negative",
                    },
                ],
            )
        ],
    )
    backend = CountingFacetGroupingBackend()

    summary, group_run_id = _run_group(
        conn,
        project_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facet": "population"}},
        backend=backend,
    )
    row = _group_row(conn, project_id, group_run_id)

    assert backend.partition_calls == 0
    assert backend.repair_calls == 0
    assert summary["facet"] == "population"
    assert summary["facet_source"] == "scope_context"
    assert summary["flags"] == ["all_no_value"]
    assert summary["counts"]["no_value"] == 2
    assert summary["counts"]["groups"] == 0
    assert summary["residuals"]["no_value"]["finding_count"] == 2
    assert row["facet"] == "population"
    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in seeded.finding_ids
    }


def test_mixed_unclear_directions_are_first_class_in_spreads(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
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
                        "effect_direction": "positive",
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

    summary, group_run_id = _run_group(conn, project_id, scope_id, seeded.run_id)
    row = _group_row(conn, project_id, group_run_id)
    group = next(group for group in summary["groups"] if group["label"] == "alpha")
    residual = summary["residuals"]["ungrouped"]

    assert group["direction_spread"]["mixed"] == 1
    assert group["direction_spread"]["positive"] == 1
    assert _spread_total(group["direction_spread"]) == group["size"]
    assert residual["direction_spread"]["unclear"] == 1
    assert _spread_total(residual["direction_spread"]) == residual["finding_count"]
    payload = cast("dict[str, Any]", row["groups"])
    stored_group = cast("list[dict[str, Any]]", payload["groups"])[0]
    assert cast("dict[str, int]", stored_group["direction_spread"])["mixed"] == 1
    assert cast("dict[str, int]", payload["ungrouped"]["direction_spread"])["unclear"] == 1


def test_backend_failure_raises_without_rollup_row(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha one", "outcome": "Outcome"}])],
    )

    with pytest.raises(GroupError) as excinfo:
        _run_group(
            conn,
            project_id,
            scope_id,
            seeded.run_id,
            backend=StubFacetGroupingBackend(fail=True),
        )
    assert str(excinfo.value) == "facet grouping backend failed: RuntimeError"
    assert "Stub facet grouping failure sentinel" not in str(excinfo.value)
    assert _group_count(conn, project_id) == 0


def test_determinism_over_same_extraction_run(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
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

    _, first_run_id = _run_group(conn, project_id, scope_id, seeded.run_id)
    _, second_run_id = _run_group(conn, project_id, scope_id, seeded.run_id)
    first = _group_row(conn, project_id, first_run_id)
    second = _group_row(conn, project_id, second_run_id)

    for key in ("facet", "groups", "counts", "flags", "grouping_provenance"):
        assert first[key] == second[key]
    assert first["run_id"] != second["run_id"]


def test_same_run_reexecution_is_loud_integrity_error(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
        scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha one", "outcome": "Outcome"}])],
    )
    group_run_id = seed_run(conn, project_id)

    _run_group(conn, project_id, scope_id, seeded.run_id, run_id=group_run_id)
    with pytest.raises(IntegrityError, match="uq_grr_scope_run"), conn.begin_nested():
        _run_group(conn, project_id, scope_id, seeded.run_id, run_id=group_run_id)


def test_directive_default_scope_context_and_malformed_fail_closed(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
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

    default_summary, default_run_id = _run_group(conn, project_id, scope_id, seeded.run_id)
    default_row = _group_row(conn, project_id, default_run_id)
    assert default_summary["facet"] == "intervention"
    assert default_summary["facet_source"] == "default"
    assert default_row["facet"] == "intervention"
    assert default_row["grouping_provenance"]["facet_source"] == "default"

    outcome_summary, outcome_run_id = _run_group(
        conn,
        project_id,
        scope_id,
        seeded.run_id,
        context={"grouping": {"facet": "outcome"}},
    )
    outcome_row = _group_row(conn, project_id, outcome_run_id)
    assert outcome_summary["facet"] == "outcome"
    assert outcome_summary["facet_source"] == "scope_context"
    assert outcome_row["facet"] == "outcome"
    assert outcome_row["grouping_provenance"]["facet"] == "outcome"
    assert outcome_row["grouping_provenance"]["facet_source"] == "scope_context"

    existing_group_count = _group_count(conn, project_id)
    for malformed in (
        {"grouping": {"facet": "bogus"}},
        {"grouping": {"facet": "intervention", "unknown": True}},
    ):
        backend = CountingFacetGroupingBackend()
        with pytest.raises(FacetDirectiveError):
            _run_group(
                conn,
                project_id,
                scope_id,
                seeded.run_id,
                context=malformed,
                backend=backend,
            )
        assert backend.partition_calls == 0
        assert backend.repair_calls == 0
        assert _group_count(conn, project_id) == existing_group_count


def test_value_cap_fails_before_backend_call(conn: Connection) -> None:
    project_id, _ = seed_project_and_run(conn)
    scope_id = seed_scope(conn, project_id)
    seeded = seed_extraction(
        conn,
        project_id,
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
    backend = CountingFacetGroupingBackend()

    with pytest.raises(GroupError) as excinfo:
        _run_group(conn, project_id, scope_id, seeded.run_id, backend=backend)
    assert "value_cap_exceeded" in str(excinfo.value)
    assert str(FACET_VALUE_CAP) in str(excinfo.value)
    assert "deferred large-corpus seam" in str(excinfo.value)
    assert backend.partition_calls == 0
    assert backend.repair_calls == 0
    assert _group_count(conn, project_id) == 0


def _zero_spread() -> dict[str, int]:
    return {"positive": 0, "negative": 0, "no_effect": 0, "mixed": 0, "unclear": 0}
