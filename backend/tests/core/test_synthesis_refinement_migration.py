"""Migration coverage for task 022 Phase B synthesis-refinement schema changes.

Two catalog generations (plan D9): below revision c1a7f4e9b0d2 the Task key is
``project_id`` and the snapshot key ``project_source_snapshot_id``, so the
pre-migration dataset reflects the live shape; at head the same rows are
addressed through ``core.schema``'s post-rename metadata.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy import inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    block,
    evidence_scope,
    extraction_result,
    finding_reference_union,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    selection_result,
    source_extraction_record,
    synthesis_result,
)
from policy_atlas.evidence_search.extract.iof_records import PROFILE_ID as IOF_PROFILE_ID
from tests.conftest import _alembic_cfg
from tests.core.legacy_catalog import (
    legacy_table,
    seed_legacy_run,
    seed_legacy_task_and_run,
)
from tests.helpers import delete_task_data, now, seed_run, seed_source, seed_task_and_run

PRE_MIGRATION_REVISION = "2f9d7e1c4a6b"


def _json_text(sql: str, *json_params: str) -> Any:
    return sa.text(sql).bindparams(
        *(sa.bindparam(name, type_=postgresql.JSONB()) for name in json_params)
    )


def _seed_selection_extraction(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    selection_run_id: uuid.UUID,
    extraction_run_id: uuid.UUID,
    legacy: bool = False,
) -> None:
    """Seed the selection + extraction results the grouping row depends on.

    Args:
        conn: Open connection on the revision being exercised.
        task_id: Task the results belong to.
        scope_id: Evidence scope the results belong to.
        selection_run_id: Run that produced the selection.
        extraction_run_id: Run that produced the extraction.
        legacy: Seed BELOW revision c1a7f4e9b0d2, where the column is still
            ``project_id`` (plan D9).
    """
    selections = legacy_table(conn, "selection_result") if legacy else selection_result
    extractions = legacy_table(conn, "extraction_result") if legacy else extraction_result
    task_key = "project_id" if legacy else "task_id"
    conn.execute(
        selections.insert().values(**{
            "selection_result_id": uuid.uuid4(),
            task_key: task_id,
            "evidence_scope_id": scope_id,
            "run_id": selection_run_id,
            "strategy": "coverage_stratified_v1",
            "budget": 1,
            "selection_provenance": {"strategy": "migration-test"},
            "selected": [],
            "excluded": {},
            "flags": [],
            "created_at": now(),
        })
    )
    conn.execute(
        extractions.insert().values(**{
            "extraction_result_id": uuid.uuid4(),
            task_key: task_id,
            "evidence_scope_id": scope_id,
            "run_id": extraction_run_id,
            "selection_run_id": selection_run_id,
            "extraction_provenance": {
                "profiles": {IOF_PROFILE_ID: {"fingerprint": "fp-migration"}}
            },
            "docs": [],
            "counts": {
                "selected": 0,
                "profiles": {
                    IOF_PROFILE_ID: {
                        "extracted": 0,
                        "no_findings": 0,
                        "failed": 0,
                        "fresh": 0,
                        "reused": 0,
                        "findings": {"total": 0},
                        "field_coverage": {},
                    }
                },
            },
            "flags": [],
            "created_at": now(),
        })
    )


def _old_groups_payload() -> dict[str, Any]:
    return {
        "groups": [
            {
                "label": "Alpha",
                "description": "Alpha references.",
                "member_values": ["Alpha service"],
                "member_finding_ids": ["finding-alpha"],
                "size": 1,
                "direction_spread": {"increase": 1},
            },
            {
                "label": "Beta",
                "description": "Beta references.",
                "member_values": ["Beta service"],
                "member_finding_ids": ["finding-beta"],
                "size": 1,
                "direction_spread": {"decrease": 1},
            },
        ],
        "ungrouped": {"values": [], "finding_ids": []},
        "no_value": {"finding_ids": []},
        "overall_direction_spread": {"increase": 1, "decrease": 1},
    }


def _seed_pre_migration_dataset(conn: Connection) -> dict[str, uuid.UUID]:
    """Seed the whole pre-022 dataset BELOW revision c1a7f4e9b0d2 (plan D9)."""
    task_id, synthesis_run_id = seed_legacy_task_and_run(conn)
    scope_id = uuid.uuid4()
    selection_run_id = seed_legacy_run(conn, task_id)
    extraction_run_id = seed_legacy_run(conn, task_id)
    grouping_run_id = seed_legacy_run(conn, task_id)
    artefact_id = uuid.uuid4()
    block_id = uuid.uuid4()
    unit_id = uuid.uuid4()
    annotation_id = uuid.uuid4()
    synthesis_result_id = uuid.uuid4()

    conn.execute(
        legacy_table(conn, "evidence_scope").insert().values(
            evidence_scope_id=scope_id,
            project_id=task_id,
            intent="Migration test scope",
            context={},
            created_at=now(),
        )
    )
    _seed_selection_extraction(
        conn,
        task_id=task_id,
        scope_id=scope_id,
        selection_run_id=selection_run_id,
        extraction_run_id=extraction_run_id,
        legacy=True,
    )
    conn.execute(
        _json_text(
            """
            INSERT INTO grouping_result (
                grouping_result_id,
                project_id,
                evidence_scope_id,
                run_id,
                extraction_run_id,
                facet,
                grouping_provenance,
                groups,
                counts,
                flags,
                created_at
            )
            VALUES (
                :grouping_result_id,
                :project_id,
                :evidence_scope_id,
                :run_id,
                :extraction_run_id,
                :facet,
                :grouping_provenance,
                :groups,
                :counts,
                :flags,
                :created_at
            )
            """,
            "grouping_provenance",
            "groups",
            "counts",
            "flags",
        ),
        {
            "grouping_result_id": uuid.uuid4(),
            "project_id": task_id,
            "evidence_scope_id": scope_id,
            "run_id": grouping_run_id,
            "extraction_run_id": extraction_run_id,
            "facet": "intervention",
            "grouping_provenance": {"facet": "intervention", "mode": "stub"},
            "groups": _old_groups_payload(),
            "counts": {"findings_total": 2, "groups": 2},
            "flags": ["old_flag"],
            "created_at": now(),
        },
    )

    conn.execute(
        legacy_table(conn, "artefact").insert().values(
            artefact_id=artefact_id,
            project_id=task_id,
            title="Migration artefact",
            created_at=now(),
        )
    )
    conn.execute(
        block.insert().values(
            block_id=block_id,
            artefact_id=artefact_id,
            version=1,
            content="Theme claim.",
            content_hash="hash",
            created_at=now(),
        )
    )
    conn.execute(
        addressable_unit.insert().values(
            unit_id=unit_id,
            block_id=block_id,
            unit_type="text_span",
            locator={"start": 0, "end": 12},
            content="Theme claim.",
            created_at=now(),
        )
    )
    conn.execute(
        annotation.insert().values(
            annotation_id=annotation_id,
            block_id=block_id,
            unit_id=unit_id,
            annotation_type="theme",
            payload={
                "claim_id": "s0c0",
                "claim_type": "theme",
                "theme": {
                    "source": "grouping",
                    "referenced_ids": ["Alpha", "g2", "unknown"],
                    "base": "grouping",
                },
                "cited_ids": ["Alpha", "g2", "unknown"],
            },
            created_at=now(),
        )
    )
    conn.execute(
        legacy_table(conn, "synthesis_result").insert().values(
            synthesis_result_id=synthesis_result_id,
            project_id=task_id,
            evidence_scope_id=scope_id,
            run_id=synthesis_run_id,
            selection_run_id=selection_run_id,
            extraction_run_id=extraction_run_id,
            grouping_run_id=grouping_run_id,
            artefact_id=artefact_id,
            synthesis_provenance={},
            blocks=[
                {
                    "title": "Grouped section",
                    "focus": "Grouped focus",
                    "block_id": str(block_id),
                    "group_ids": ["Alpha", "Beta", "unknown"],
                }
            ],
            counts={},
            flags={},
            created_at=now(),
        )
    )
    return {
        "task_id": task_id,
        "scope_id": scope_id,
        "grouping_run_id": grouping_run_id,
        "annotation_id": annotation_id,
        "synthesis_result_id": synthesis_result_id,
    }


def test_synthesis_refinement_migration_rewrites_grouping_and_consumers(
    engine: Engine,
) -> None:
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)
    conn = engine.connect()
    trans = conn.begin()
    ids = _seed_pre_migration_dataset(conn)
    trans.commit()
    conn.close()

    try:
        command.upgrade(cfg, "head")
        conn = engine.connect()
        trans = conn.begin()
        try:
            columns = {c["name"] for c in inspect(engine).get_columns("grouping_result")}
            assert "facet" not in columns

            grouping = conn.execute(
                select(
                    grouping_result.c.groups,
                    grouping_result.c.counts,
                    grouping_result.c.flags,
                    grouping_result.c.grouping_provenance,
                ).where(grouping_result.c.run_id == ids["grouping_run_id"])
            ).one()
            assert grouping.groups.keys() == {"intervention"}
            facet_payload = grouping.groups["intervention"]
            assert [group["group_id"] for group in facet_payload["groups"]] == [
                "intervention:g01",
                "intervention:g02",
            ]
            assert {group["facet"] for group in facet_payload["groups"]} == {"intervention"}
            assert grouping.counts == {"intervention": {"findings_total": 2, "groups": 2}}
            assert grouping.flags == {"intervention": ["old_flag"]}
            assert grouping.grouping_provenance["facets"] == ["intervention"]

            synthesis = conn.execute(
                select(synthesis_result.c.blocks).where(
                    synthesis_result.c.synthesis_result_id == ids["synthesis_result_id"]
                )
            ).scalar_one()
            assert synthesis[0]["group_ids"] == [
                "intervention:g01",
                "intervention:g02",
                "unknown",
            ]
            payload = conn.execute(
                select(annotation.c.payload).where(
                    annotation.c.annotation_id == ids["annotation_id"]
                )
            ).scalar_one()
            assert payload["theme"]["referenced_ids"] == [
                "intervention:g01",
                "intervention:g02",
                "unknown",
            ]
            assert payload["cited_ids"] == [
                "intervention:g01",
                "intervention:g02",
                "unknown",
            ]
        finally:
            trans.rollback()
            conn.close()
    finally:
        command.upgrade(cfg, "head")
        conn = engine.connect()
        trans = conn.begin()
        try:
            delete_task_data(conn, ids["task_id"])
            trans.commit()
        finally:
            conn.close()


def test_synthesis_refinement_migration_downgrade_round_trips_one_facet(
    engine: Engine,
) -> None:
    cfg = _alembic_cfg()
    command.downgrade(cfg, PRE_MIGRATION_REVISION)
    conn = engine.connect()
    trans = conn.begin()
    ids = _seed_pre_migration_dataset(conn)
    trans.commit()
    conn.close()

    try:
        command.upgrade(cfg, "head")
        command.downgrade(cfg, PRE_MIGRATION_REVISION)
        conn = engine.connect()
        trans = conn.begin()
        try:
            grouping = conn.execute(
                sa.text(
                    """
                    SELECT facet, groups, counts, flags, grouping_provenance
                    FROM grouping_result
                    WHERE run_id = :run_id
                    """
                ),
                {"run_id": ids["grouping_run_id"]},
            ).mappings().one()
            assert grouping["facet"] == "intervention"
            assert "intervention" not in grouping["groups"]
            assert [group["label"] for group in grouping["groups"]["groups"]] == [
                "Alpha",
                "Beta",
            ]
            assert all(
                "group_id" not in group and "facet" not in group
                for group in grouping["groups"]["groups"]
            )
            assert grouping["counts"] == {"findings_total": 2, "groups": 2}
            assert grouping["flags"] == ["old_flag"]
            assert "facets" not in grouping["grouping_provenance"]

            synthesis = conn.execute(
                select(synthesis_result.c.blocks).where(
                    synthesis_result.c.synthesis_result_id == ids["synthesis_result_id"]
                )
            ).scalar_one()
            assert synthesis[0]["group_ids"] == ["Alpha", "Beta", "unknown"]
            payload = conn.execute(
                select(annotation.c.payload).where(
                    annotation.c.annotation_id == ids["annotation_id"]
                )
            ).scalar_one()
            assert payload["theme"]["referenced_ids"] == ["Alpha", "Beta", "unknown"]
            assert payload["cited_ids"] == ["Alpha", "Beta", "unknown"]
        finally:
            trans.rollback()
            conn.close()
    finally:
        command.upgrade(cfg, "head")
        conn = engine.connect()
        trans = conn.begin()
        try:
            delete_task_data(conn, ids["task_id"])
            trans.commit()
        finally:
            conn.close()


def test_synthesis_refinement_downgrade_refuses_multifacet_grouping(
    engine: Engine,
) -> None:
    cfg = _alembic_cfg()
    command.upgrade(cfg, "head")
    conn = engine.connect()
    trans = conn.begin()
    task_id, _ = seed_task_and_run(conn)
    scope_id = uuid.uuid4()
    selection_run_id = seed_run(conn, task_id)
    extraction_run_id = seed_run(conn, task_id)
    grouping_run_id = seed_run(conn, task_id)
    conn.execute(
        evidence_scope.insert().values(
            evidence_scope_id=scope_id,
            task_id=task_id,
            intent="Multifacet downgrade refusal",
            context={},
            created_at=now(),
        )
    )
    _seed_selection_extraction(
        conn,
        task_id=task_id,
        scope_id=scope_id,
        selection_run_id=selection_run_id,
        extraction_run_id=extraction_run_id,
    )
    conn.execute(
        grouping_result.insert().values(
            grouping_result_id=uuid.uuid4(),
            task_id=task_id,
            evidence_scope_id=scope_id,
            run_id=grouping_run_id,
            extraction_run_id=extraction_run_id,
            grouping_provenance={"facets": ["intervention", "outcome"]},
            groups={
                "intervention": {"groups": [], "ungrouped": {}, "no_value": {}},
                "outcome": {"groups": [], "ungrouped": {}, "no_value": {}},
            },
            counts={"intervention": {}, "outcome": {}},
            flags={"intervention": [], "outcome": []},
            created_at=now(),
        )
    )
    trans.commit()
    conn.close()

    try:
        with pytest.raises(RuntimeError, match="multi-facet"):
            command.downgrade(cfg, PRE_MIGRATION_REVISION)
    finally:
        command.upgrade(cfg, "head")
        conn = engine.connect()
        trans = conn.begin()
        try:
            delete_task_data(conn, task_id)
            trans.commit()
        finally:
            conn.close()


def test_finding_reference_union_projects_iof_and_icf_shared_columns(
    conn: Connection,
) -> None:
    task_id, run_id = seed_task_and_run(conn)
    snap_id, tss_id = seed_source(conn, task_id)
    iof_record_id = uuid.uuid4()
    icf_record_id = uuid.uuid4()
    iof_finding_id = uuid.uuid4()
    icf_finding_id = uuid.uuid4()
    for record_id, fingerprint in (
        (iof_record_id, "fp-union-iof"),
        (icf_record_id, "fp-union-icf"),
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
                run_id=run_id,
                created_at=now(),
            )
        )
    conn.execute(
        intervention_outcome_finding.insert().values(
            finding_id=iof_finding_id,
            task_id=task_id,
            extraction_record_id=iof_record_id,
            intervention="Alpha service",
            outcome="Attendance",
            population="Adults",
            setting="clinic",
            comparator=None,
            effect_direction="increase",
            estimate_level="study",
            study_design="RCT",
            study_geography="England",
            stratum_qualifiers=[],
            statistics={},
            causality_by_design=None,
            effect_basis="observed",
            is_primary=None,
            is_prevalence_only=None,
            field_coverage={},
            grounding=[],
            created_at=now(),
        )
    )
    conn.execute(
        implementation_context_finding.insert().values(
            finding_id=icf_finding_id,
            task_id=task_id,
            extraction_record_id=icf_record_id,
            context_type="barrier",
            claim="Training gaps slowed delivery.",
            context_label=None,
            intervention="Alpha service",
            outcome=None,
            population="Adults",
            setting="clinic",
            study_geography="England",
            study_design="process evaluation",
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

    rows = conn.execute(
        select(finding_reference_union).where(
            finding_reference_union.c.finding_id.in_([iof_finding_id, icf_finding_id])
        )
    ).mappings().all()
    by_kind = {row["kind"]: row for row in rows}
    assert set(by_kind) == {"iof", "icf"}
    assert by_kind["iof"]["outcome"] == "Attendance"
    assert by_kind["iof"]["study_design"] == "RCT"
    assert by_kind["icf"]["outcome"] is None
    assert by_kind["icf"]["study_design"] == "process evaluation"
    assert {
        "finding_id",
        "kind",
        "extraction_record_id",
        "task_id",
        "intervention",
        "outcome",
        "population",
        "setting",
        "study_geography",
        "study_design",
    } <= set(rows[0])
