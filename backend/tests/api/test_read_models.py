"""Golden HTTP tests for the durable Task 025 read-model endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from policy_atlas.core import events
from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    chunk,
    citation,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    runs,
    search_coverage_record,
    selection_result,
    source_extraction_record,
    synthesis_result,
)
from tests.api.resource_support import api_client, create_project
from tests.helpers import (
    ICF_PROFILE_ID,
    IOF_PROFILE_ID,
    delete_project_data,
    now,
    seed_ingested_full_text,
    seed_scope,
    seed_screening_result,
    seed_select_doc,
    seed_source,
)


def _seed_read_model_ladder(
    engine: Engine, project_id: uuid.UUID
) -> tuple[tuple[uuid.UUID, uuid.UUID, uuid.UUID], uuid.UUID]:
    """Seed one project with a known source ladder and cited synthesis claim."""
    with engine.begin() as conn:
        run_id = uuid.uuid4()
        conn.execute(
            insert(runs).values(
                run_id=run_id,
                project_id=project_id,
                status="running",
                started_at=now(),
            )
        )
        scope_id = seed_scope(conn, project_id)
        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="search.executed",
            payload={"query": "training uptake", "result_count": 3},
        )
        selected_pss = seed_select_doc(
            conn, project_id, run_id, scope_id, title="Selected trial", year=2020
        )
        _, excluded_pss = seed_source(conn, project_id, {"title": "Excluded review", "year": 2019})
        seed_screening_result(
            conn, project_id, run_id, scope_id, excluded_pss, status="not_relevant"
        )
        _, found_pss = seed_source(conn, project_id, {"title": "Unscreened report", "year": 2018})
        full_snapshot_id = seed_ingested_full_text(
            conn,
            pss_id=selected_pss,
            chunks=[
                "Cited evidence sentence." + "B" * 900,
                "A" * 900 + "Cited evidence sentence." + "B" * 900,
                "A" * 900 + "Cited evidence sentence.",
            ],
        )
        conn.execute(
            insert(selection_result).values(
                selection_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                strategy="coverage_stratified_v1",
                budget=1,
                selection_provenance={},
                selected=[{"pss_id": str(selected_pss)}],
                excluded={},
                flags={},
                created_at=now(),
            )
        )
        record_id = uuid.uuid4()
        conn.execute(
            insert(source_extraction_record).values(
                extraction_record_id=record_id,
                project_id=project_id,
                source_snapshot_id=full_snapshot_id,
                project_source_snapshot_id=selected_pss,
                extraction_fingerprint="fixture",
                status="extracted",
                basis="full_text",
                primary_evidence_type="RCTs and Quasi-Experimental Studies",
                error=None,
                finding_count=2,
                run_id=run_id,
                created_at=now(),
            )
        )
        iof_id, icf_id = uuid.uuid4(), uuid.uuid4()
        conn.execute(
            insert(intervention_outcome_finding).values(
                finding_id=iof_id,
                project_id=project_id,
                extraction_record_id=record_id,
                intervention="Training",
                outcome="Uptake",
                effect_direction="increase",
                stratum_qualifiers=[],
                statistics={},
                field_coverage={},
                grounding=[],
                created_at=now(),
            )
        )
        conn.execute(
            insert(implementation_context_finding).values(
                finding_id=icf_id,
                project_id=project_id,
                extraction_record_id=record_id,
                context_type="barrier",
                claim="Staff time constrained implementation.",
                intervention="Training",
                field_coverage={},
                grounding=[],
                created_at=now(),
            )
        )
        conn.execute(
            insert(extraction_result).values(
                extraction_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                selection_run_id=run_id,
                extraction_provenance={
                    "profiles": {IOF_PROFILE_ID: {}, ICF_PROFILE_ID: {}},
                    "relevance": {"annotations": {str(iof_id): "priority", str(icf_id): "normal"}},
                },
                docs=[],
                counts={},
                flags={},
                created_at=now(),
            )
        )
        conn.execute(
            insert(grouping_result).values(
                grouping_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                extraction_run_id=run_id,
                grouping_provenance={},
                groups={
                    "intervention": {
                        "groups": [
                            {
                                "label": "Training",
                                "description": "Training findings",
                                "size": 2,
                                "member_finding_ids": [str(iof_id), str(icf_id)],
                            }
                        ],
                        "ungrouped": {"finding_ids": []},
                        "no_value": {"finding_ids": []},
                    }
                },
                counts={},
                flags={},
                created_at=now(),
            )
        )
        conn.execute(
            insert(search_coverage_record).values(
                search_coverage_record_id=uuid.uuid4(),
                evidence_scope_id=scope_id,
                project_id=project_id,
                acquired_by_run_id=run_id,
                backends=[],
                scope_filters={},
                stop_condition="completed",
                adequacy_verdict="adequate",
                verdict_origin="model",
                created_at=now(),
            )
        )
        artefact_id, block_id, unit_id, annotation_id, citation_id = (
            uuid.uuid4() for _ in range(5)
        )
        prose = "The evidence supports training."
        conn.execute(
            insert(artefact).values(
                artefact_id=artefact_id,
                project_id=project_id,
                title="Evidence base",
                created_at=now(),
            )
        )
        conn.execute(
            insert(block).values(
                block_id=block_id,
                artefact_id=artefact_id,
                version=1,
                content=prose,
                content_hash="fixture",
                created_at=now(),
            )
        )
        conn.execute(
            insert(addressable_unit).values(
                unit_id=unit_id,
                block_id=block_id,
                unit_type="text_span",
                locator={"start": 4, "end": 12},
                content="evidence",
                created_at=now(),
            )
        )
        conn.execute(
            insert(annotation).values(
                annotation_id=annotation_id,
                block_id=block_id,
                unit_id=unit_id,
                annotation_type="citation",
                payload={"verdict": "grounded"},
                created_at=now(),
            )
        )
        chunk_ids = (
            conn.execute(
                select(chunk.c.chunk_id)
                .where(chunk.c.source_snapshot_id == full_snapshot_id)
                .order_by(chunk.c.sequence)
            )
            .scalars()
            .all()
        )
        citation_ids = (citation_id, uuid.uuid4(), uuid.uuid4())
        for new_citation_id, chunk_id in zip(citation_ids, chunk_ids, strict=True):
            conn.execute(
                insert(citation).values(
                    citation_id=new_citation_id,
                    annotation_id=annotation_id,
                    chunk_id=chunk_id,
                    quote="Cited evidence sentence.",
                    verification_result="pass",
                    created_at=now(),
                )
            )
        conn.execute(
            insert(synthesis_result).values(
                synthesis_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                characterisation_run_id=None,
                selection_run_id=run_id,
                extraction_run_id=run_id,
                grouping_run_id=run_id,
                artefact_id=artefact_id,
                synthesis_provenance={},
                blocks=[
                    {"block_id": str(block_id), "title": "Key findings", "role": "key_findings"}
                ],
                counts={},
                flags={},
                created_at=now(),
            )
        )
        return citation_ids, found_pss


def test_read_model_goldens_and_owner_scope(tmp_path: Path, engine: Engine) -> None:
    """Assert exact ladder, screened-in distributions, artefact and context projections."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        citation_ids, _ = _seed_read_model_ladder(engine, project_id)
        try:
            funnel = client.get(f"/api/v1/projects/{project_id}/funnel", headers=owner)
            assert funnel.status_code == 200
            assert funnel.json() == {
                "found": 3,
                "relevant": 1,
                "screened_out": 1,
                "quality_checked": 1,
                "read_in_full": 1,
                "selected": 1,
                "findings": 2,
                "cited": 1,
            }
            landscape = client.get(f"/api/v1/projects/{project_id}/landscape", headers=owner).json()
            assert landscape["evidence_types"] == {"RCTs and Quasi-Experimental Studies": 1}
            assert landscape["years"] == {"2020": 1}
            evidence = client.get(
                f"/api/v1/projects/{project_id}/evidence?page=1&page_size=2", headers=owner
            )
            assert evidence.status_code == 200
            assert evidence.json()["pagination"] == {"page": 1, "page_size": 2, "total_items": 3}
            assert {row["status"] for row in evidence.json()["data"]} <= {
                "cited",
                "screened_out",
                "found",
            }
            assert (
                client.get(f"/api/v1/projects/{project_id}/evidence", headers=other).status_code
                == 404
            )
            findings = client.get(f"/api/v1/projects/{project_id}/findings", headers=owner).json()[
                "data"
            ]
            assert {(row["profile"], row["relevance"]) for row in findings} == {
                ("iof", "priority"),
                ("icf", "normal"),
            }
            assert (
                client.get(f"/api/v1/projects/{project_id}/groups", headers=owner).json()["facets"][
                    0
                ]["groups"][0]["size"]
                == 2
            )
            decisions = client.get(f"/api/v1/projects/{project_id}/decisions", headers=owner)
            assert decisions.status_code == 200
            assert decisions.json()["data"][0]["kind"] == "search.executed"
            assert decisions.json()["data"][0]["summary"] == "Executed a search query."
            coverage = client.get(f"/api/v1/projects/{project_id}/coverage", headers=owner).json()
            assert (
                coverage["sentence"]
                == "Searching stopped because completed. Coverage was judged adequate."
            )
            assert coverage["base"]["counts"] == {"found": 3, "relevant": 1, "screened_out": 1}
            artefact = client.get(f"/api/v1/projects/{project_id}/artefact", headers=owner).json()
            assert artefact["sections"][0]["role"] == "key_findings"
            assert artefact["sections"][0]["blocks"][0]["claims"][0]["citations"][0]["n"] == 1
            near_start, middle, near_end = [
                client.get(
                    f"/api/v1/projects/{project_id}/citations/{citation_id}/context",
                    headers=owner,
                ).json()
                for citation_id in citation_ids
            ]
            assert near_start["span_start"] == 0
            assert middle["span_start"] == near_end["span_start"] == 800
            # 24-char quote + 800-char window on the unclamped side(s).
            assert [len(context["context"]) for context in (near_start, middle, near_end)] == [
                824,
                1624,
                824,
            ]
            assert all(context["clamped"] is True for context in (near_start, middle, near_end))
            assert all(
                "Cited evidence sentence." in context["context"]
                for context in (near_start, middle, near_end)
            )
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)
