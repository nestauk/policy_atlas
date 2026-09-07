"""Contract-bulk test suite for the group component (task 012, Task 7).

Covers the remaining named coverage not already exercised elsewhere: schema
constraint rejections on ``grouping_result`` (direct-insert level, the extract
style), no-side-effects invariants (plan finding 8), a mixed-status referenced
extraction run (plan finding 7), harness-level wiring, and delete-order
integrity. Component happy-path/edge coverage lives in ``test_group.py``;
value/directive/partition-repair unit coverage lives in ``test_facet_values.py``
and ``test_facet_grouping.py``; injection/cap/misbehaving-backend judgment
coverage lives in ``test_group_judgment.py``. All rows ride the ``conn``
fixture's per-test rollback (the repo-wide delete-order precedent — see
``test_extract_contract.py``'s task-011 delete-order test — never commits for
real; this file follows the same shape).
"""

from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

from policy_atlas.core import events
from policy_atlas.core.inference import StubEchoProvider
from policy_atlas.core.schema import (
    extraction_result,
    grouping_result,
    intervention_outcome_finding,
    runs,
    selection_result,
    source_extraction_record,
    source_tag,
)
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from policy_atlas.runtime.harness import run_harness
from policy_atlas.runtime.run_spec import Plan, compile
from tests.helpers import (
    delete_task_data,
    now,
    seed_run,
    seed_scope,
    seed_source,
    seed_task_and_run,
)

from .test_group import (
    SeededExtraction,
    _finding_values,
    _group_row,
    _payload_finding_ids,
    _run_group,
    seed_extraction,
)

# --- Local seeding / value helpers -------------------------------------------


def _grouping_result_values(
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    run_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    facet: str = "intervention",
    **over: Any,
) -> dict[str, Any]:
    """A minimal valid ``grouping_result`` row, overridable per test."""
    values: dict[str, Any] = {
        "grouping_result_id": uuid.uuid4(),
        "task_id": task_id,
        "evidence_scope_id": scope_id,
        "run_id": run_id,
        "extraction_run_id": extraction_run_id,
        "grouping_provenance": {"facets": [facet]},
        "groups": {
            facet: {
                "groups": [],
                "ungrouped": {},
                "no_value": {},
                "overall_direction_spread": {},
            }
        },
        "counts": {facet: {}},
        "flags": {facet: []},
        "created_at": now(),
    }
    values.update(over)
    return values


def _seed_mixed_status_extraction(
    conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """Seed one extraction run: two extracted docs, one no_findings, one extraction_failed.

    Mirrors the docs[]/counts shape ``seed_extraction`` (test_group.py) writes, but
    that helper only models extracted/no_findings status; this adds the
    extraction_failed doc plan finding 7 requires.
    """
    extraction_run_id = seed_run(conn, task_id)
    selection_run_id = seed_run(conn, task_id)
    selected: list[dict[str, Any]] = []
    doc_payloads: list[dict[str, Any]] = []
    finding_ids: list[uuid.UUID] = []

    specs: list[tuple[str, list[dict[str, Any]]]] = [
        ("extracted", [{"intervention": "Alpha service", "outcome": "Outcome A"}]),
        ("extracted", [{"intervention": "Beta service", "outcome": "Outcome B"}]),
        ("no_findings", []),
        ("extraction_failed", []),
    ]
    for status, findings in specs:
        record_id = uuid.uuid4()
        snap_id, tss_id = seed_source(conn, task_id)
        selected.append({"tss_id": str(tss_id), "text_basis": "full_text"})
        error = "invalid_records" if status == "extraction_failed" else None
        conn.execute(source_extraction_record.insert().values(
            extraction_record_id=record_id,
            task_id=task_id,
            source_snapshot_id=snap_id,
            task_source_snapshot_id=tss_id,
            extraction_fingerprint=f"fp-{extraction_run_id}-{status}",
            status=status,
            basis="full_text",
            error=error,
            finding_count=len(findings),
            run_id=extraction_run_id,
            created_at=now(),
        ))
        for finding in findings:
            values = _finding_values(task_id, record_id, **finding)
            finding_ids.append(cast("uuid.UUID", values["finding_id"]))
            conn.execute(intervention_outcome_finding.insert().values(**values))
        doc_payloads.append({
            "tss_id": str(tss_id),
            "basis": "full_text",
            "profiles": {
                IOF_PROFILE_ID: {
                    "status": status,
                    "finding_count": len(findings),
                    "reused": False,
                    "error": error,
                    "extraction_record_id": str(record_id),
                }
            },
        })

    conn.execute(selection_result.insert().values(
        selection_result_id=uuid.uuid4(),
        task_id=task_id,
        evidence_scope_id=scope_id,
        run_id=selection_run_id,
        strategy="coverage_stratified_v1",
        budget=len(specs),
        selection_provenance={"strategy": "test"},
        selected=selected,
        excluded={},
        flags=[],
        created_at=now(),
    ))
    conn.execute(extraction_result.insert().values(
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
            "selected": len(specs),
            "basis": {
                "full_text": len(specs), "abstract_only": 0,
                "shares": {"full_text": 1.0, "abstract_only": 0.0},
            },
            "profiles": {
                IOF_PROFILE_ID: {
                    "extracted": 2,
                    "no_findings": 1,
                    "failed": 1,
                    "fresh": len(specs),
                    "reused": 0,
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
    ))
    return extraction_run_id, finding_ids


def _full_rows(
    conn: Connection, table: Any, task_id: uuid.UUID, pk_col: str
) -> list[dict[str, Any]]:
    """Snapshot every column of every row for a task, in a stable order."""
    rows = conn.execute(select(table).where(table.c.task_id == task_id)).mappings().all()
    return sorted((dict(row) for row in rows), key=lambda row: str(row[pk_col]))


_BANNED_EVALUATIVE_KEYS = {
    "verdict", "consensus", "strength", "recommendation",
    "effectiveness", "evaluation", "score",
}


def _collect_keys(obj: Any) -> set[str]:
    """Recursively collect every dict key found anywhere inside ``obj``."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(key)
            keys |= _collect_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _collect_keys(item)
    return keys


def _seed_one_doc_extraction(
    conn: Connection, task_id: uuid.UUID, scope_id: uuid.UUID
) -> SeededExtraction:
    return seed_extraction(
        conn, task_id, scope_id,
        docs=[(uuid.uuid4(), [{"intervention": "Alpha service", "outcome": "Outcome"}])],
    )


# --- 1. Schema constraints on grouping_result --------------------------------


@pytest.mark.parametrize("facet", ["intervention", "outcome", "population"])
def test_grr_per_facet_payload_key_accepted(conn: Connection, facet: str) -> None:
    """Sanctioned shape change: facet is now the persisted JSON key, not a row column."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = _seed_one_doc_extraction(conn, task_id, scope_id)
    group_run_id = seed_run(conn, task_id)

    conn.execute(grouping_result.insert().values(
        **_grouping_result_values(task_id, scope_id, group_run_id, seeded.run_id, facet=facet)
    ))

    stored = conn.execute(
        select(grouping_result.c.groups, grouping_result.c.grouping_provenance)
        .where(grouping_result.c.run_id == group_run_id)
    ).one()
    assert stored.groups.keys() == {facet}
    assert stored.grouping_provenance["facets"] == [facet]


def test_grr_row_level_facet_column_and_check_removed() -> None:
    """Sanctioned shape change: ``facet`` moved to group grain."""
    assert "facet" not in grouping_result.c
    assert "ck_grr_facet" not in {
        constraint.name for constraint in grouping_result.constraints
    }


def test_grr_scope_task_fk_rejected(conn: Connection) -> None:
    """A scope from ANOTHER task is rejected (fk_grr_scope_task).

    Isolated from fk_grr_extraction by pointing extraction_run_id at a real
    extraction for the foreign scope — that pair is valid, only the
    (scope, task) pair is not.
    """
    task_a, _ = seed_task_and_run(conn)
    group_run_a = seed_run(conn, task_a)

    task_b, _ = seed_task_and_run(conn)
    scope_b = seed_scope(conn, task_b)
    seeded_b = _seed_one_doc_extraction(conn, task_b, scope_b)

    with pytest.raises(IntegrityError, match="fk_grr_scope_task"), conn.begin_nested():
        conn.execute(grouping_result.insert().values(**_grouping_result_values(
            task_a, scope_b, group_run_a, seeded_b.run_id
        )))


def test_grr_run_task_fk_rejected(conn: Connection) -> None:
    """A run from ANOTHER task is rejected (fk_grr_run_task).

    Isolated: scope and extraction_run_id stay valid for task_a; only the
    run belongs elsewhere.
    """
    task_a, _ = seed_task_and_run(conn)
    scope_a = seed_scope(conn, task_a)
    seeded_a = _seed_one_doc_extraction(conn, task_a, scope_a)
    _task_b, run_b = seed_task_and_run(conn)

    with pytest.raises(IntegrityError, match="fk_grr_run_task"), conn.begin_nested():
        conn.execute(grouping_result.insert().values(**_grouping_result_values(
            task_a, scope_a, run_b, seeded_a.run_id
        )))


def test_grr_extraction_fk_rejected_no_row(conn: Connection) -> None:
    """An extraction_run_id with no extraction_result row for that scope is rejected."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    group_run_id = seed_run(conn, task_id)

    with pytest.raises(IntegrityError, match="fk_grr_extraction"), conn.begin_nested():
        conn.execute(grouping_result.insert().values(**_grouping_result_values(
            task_id, scope_id, group_run_id, uuid.uuid4()
        )))


def test_grr_extraction_fk_rejected_wrong_scope(conn: Connection) -> None:
    """An extraction run that exists, but for a DIFFERENT scope, is rejected."""
    task_id, _ = seed_task_and_run(conn)
    scope_a = seed_scope(conn, task_id)
    scope_b = seed_scope(conn, task_id)
    seeded_b = _seed_one_doc_extraction(conn, task_id, scope_b)
    group_run_id = seed_run(conn, task_id)

    with pytest.raises(IntegrityError, match="fk_grr_extraction"), conn.begin_nested():
        conn.execute(grouping_result.insert().values(**_grouping_result_values(
            task_id, scope_a, group_run_id, seeded_b.run_id
        )))


def test_grr_scope_run_unique_rejected(conn: Connection) -> None:
    """A second raw insert for the same (scope, run) is rejected (uq_grr_scope_run)."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = _seed_one_doc_extraction(conn, task_id, scope_id)
    group_run_id = seed_run(conn, task_id)

    conn.execute(grouping_result.insert().values(
        **_grouping_result_values(task_id, scope_id, group_run_id, seeded.run_id)
    ))
    with pytest.raises(IntegrityError, match="uq_grr_scope_run"), conn.begin_nested():
        conn.execute(grouping_result.insert().values(**_grouping_result_values(
            task_id, scope_id, group_run_id, seeded.run_id
        )))


# --- 2. No-side-effects invariants (plan finding 8) --------------------------


def test_group_findings_no_side_effects_and_no_evaluative_keys(conn: Connection) -> None:
    """group_findings touches nothing but grouping_result, and never writes an evaluative key."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    # Unrelated source_tag rows the component must never touch.
    _snap_id, tss_id = seed_source(conn, task_id)
    tag_run_id = seed_run(conn, task_id)
    for asserted_by in ("openalex", "overton"):
        conn.execute(source_tag.insert().values(
            source_tag_id=uuid.uuid4(),
            task_id=task_id,
            task_source_snapshot_id=tss_id,
            tag="Housing Policy",
            tag_type="topic_theme",
            asserted_by=asserted_by,
            created_by_run_id=tag_run_id,
            created_at=now(),
        ))

    seeded = seed_extraction(
        conn, task_id, scope_id,
        docs=[(uuid.uuid4(), [
            {"intervention": "Alpha counselling", "outcome": "Attendance"},
            {"intervention": "Alpha coaching", "outcome": "Retention"},
            {"intervention": "Beta home visits", "outcome": "Employment"},
        ])],
    )

    before_tags = _full_rows(conn, source_tag, task_id, "source_tag_id")
    before_findings = _full_rows(conn, intervention_outcome_finding, task_id, "finding_id")
    before_group_count = conn.execute(
        select(func.count()).select_from(grouping_result)
        .where(grouping_result.c.task_id == task_id)
    ).scalar_one()

    summary, group_run_id = _run_group(conn, task_id, scope_id, seeded.run_id)

    after_tags = _full_rows(conn, source_tag, task_id, "source_tag_id")
    after_findings = _full_rows(conn, intervention_outcome_finding, task_id, "finding_id")
    assert after_tags == before_tags
    assert after_findings == before_findings

    after_group_count = conn.execute(
        select(func.count()).select_from(grouping_result)
        .where(grouping_result.c.task_id == task_id)
    ).scalar_one()
    assert after_group_count == before_group_count + 1

    row = _group_row(conn, task_id, group_run_id)
    all_keys = (
        _collect_keys(row["groups"])
        | _collect_keys(row["counts"])
        | _collect_keys(row["flags"])
        | _collect_keys(row["grouping_provenance"])
        | _collect_keys(summary)
    )
    lowered = {key.lower() for key in all_keys}
    assert not (lowered & _BANNED_EVALUATIVE_KEYS)


# --- 3. Mixed-status referenced run (plan finding 7) -------------------------


def test_mixed_status_docs_group_only_extracted_findings(conn: Connection) -> None:
    """Extracted, no_findings and extraction_failed docs coexist; only extracted findings group."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    extraction_run_id, finding_ids = _seed_mixed_status_extraction(conn, task_id, scope_id)
    assert len(finding_ids) == 2

    summary, group_run_id = _run_group(conn, task_id, scope_id, extraction_run_id)
    row = _group_row(conn, task_id, group_run_id)

    assert _payload_finding_ids(cast("dict[str, Any]", row["groups"])) == {
        str(finding_id) for finding_id in finding_ids
    }
    assert summary["counts"]["intervention"]["findings_total"] == len(finding_ids)
    assert row["counts"]["intervention"]["findings_total"] == len(finding_ids)


# --- 4. Harness-level wiring --------------------------------------------------


def test_harness_group_component_success_default_backend(conn: Connection) -> None:
    """compile + run_harness with no group backend proves the stub default."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = _seed_one_doc_extraction(conn, task_id, scope_id)

    rid = seed_run(conn, task_id)
    plan = Plan(component="group", evidence_scope_id=scope_id, extraction_run_id=seeded.run_id)
    config = compile(plan)
    outcome = run_harness(
        conn, config=config, task_id=task_id, run_id=rid, provider=StubEchoProvider()
    )

    log_entries = events.read(conn, task_id)
    summary = outcome["summary"]
    assert summary is not None
    payload = summary
    assert {"facet", "groups", "residuals", "counts"} <= set(payload.keys())

    run_completed = [e for e in log_entries if e["event_type"] == "run.completed"]
    assert len(run_completed) == 1
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert run_row.status == "succeeded"

    count = conn.execute(
        select(func.count()).select_from(grouping_result).where(grouping_result.c.run_id == rid)
    ).scalar_one()
    assert count == 1


def test_harness_group_component_missing_extraction_fails(conn: Connection) -> None:
    """A group Plan naming an extraction run with no roll-up row fails loud, no row written."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)

    rid = seed_run(conn, task_id)
    plan = Plan(component="group", evidence_scope_id=scope_id, extraction_run_id=uuid.uuid4())
    config = compile(plan)
    run_harness(conn, config=config, task_id=task_id, run_id=rid, provider=StubEchoProvider())

    log_entries = events.read(conn, task_id)
    failed = [
        e for e in log_entries
        if e["event_type"] == "component.failed" and e["payload"].get("component") == "group"
    ]
    assert len(failed) == 1
    assert "run extract first" in failed[0]["payload"]["error"]

    count = conn.execute(
        select(func.count()).select_from(grouping_result).where(grouping_result.c.run_id == rid)
    ).scalar_one()
    assert count == 0

    run_failed = [e for e in log_entries if e["event_type"] == "run.failed"]
    assert len(run_failed) == 1
    run_row = conn.execute(select(runs).where(runs.c.run_id == rid)).one()
    assert run_row.status == "failed"


# --- 5. Delete-order integrity ------------------------------------------------


def test_delete_task_data_removes_grouping_result(conn: Connection) -> None:
    """delete_task_data removes grouping_result rows without an IntegrityError."""
    task_id, _ = seed_task_and_run(conn)
    scope_id = seed_scope(conn, task_id)
    seeded = _seed_one_doc_extraction(conn, task_id, scope_id)
    _run_group(conn, task_id, scope_id, seeded.run_id)

    delete_task_data(conn, task_id)

    count = conn.execute(
        select(func.count()).select_from(grouping_result)
        .where(grouping_result.c.task_id == task_id)
    ).scalar_one()
    assert count == 0
