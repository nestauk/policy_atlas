"""Golden HTTP tests for the durable Task 025 read-model endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Engine

from policy_atlas.api.readmodels import repository
from policy_atlas.core import events
from policy_atlas.core.schema import (
    addressable_unit,
    annotation,
    artefact,
    block,
    characterisation_result,
    chunk,
    citation,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    project_source_snapshot,
    runs,
    search_coverage_record,
    selection_result,
    source_extraction_record,
    source_snapshot,
    source_tag,
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
        selected_snapshot_id = conn.execute(
            select(project_source_snapshot.c.source_snapshot_id).where(
                project_source_snapshot.c.project_source_snapshot_id == selected_pss
            )
        ).scalar_one()
        conn.execute(
            update(source_snapshot)
            .where(source_snapshot.c.source_snapshot_id == selected_snapshot_id)
            .values(
                metadata={
                    "title": "Selected trial",
                    "year": 2020,
                    "abstract": "Provider abstract.",
                    "abstract_source": "publisher_abstract",
                    "publisher_org": "Trial Journal",
                    "record_type": "article",
                    "language": "en",
                    "doi": "10.1234/trial",
                    "provider_fields": {"cited_by_count": 12, "fwci": 1.5},
                }
            )
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
                statistics={"effect_size": 1.2, "ci_lower": 1.0, "ci_upper": 1.4},
                field_coverage={},
                grounding=[
                    {
                        "quote": "Training increased uptake.",
                        "match_status": "exact",
                        "quote_verified": True,
                    }
                ],
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
                outcome="Uptake",
                population="School staff",
                setting="Schools",
                study_geography="GB",
                study_design="Process evaluation",
                field_coverage={},
                grounding=[
                    {
                        "quote": "Staff time constrained implementation.",
                        "match_status": "exact",
                        "quote_verified": True,
                    }
                ],
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
                                "group_id": "intervention:g01",
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
            insert(source_tag).values(
                source_tag_id=uuid.uuid4(),
                project_id=project_id,
                project_source_snapshot_id=selected_pss,
                tag="School health",
                tag_type="topic_theme",
                asserted_by="openalex",
                created_by_run_id=run_id,
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
                payload={
                    "verdict": "grounded",
                    "rationale": "Quote matches the source verbatim.",
                    "weakly_grounded": False,
                    "gap": {
                        "grade": "limited",
                        "caveat": {
                            "search_space": "both backends",
                            "adequacy_verdict": "adequate",
                            "verdict_origin": "model",
                        },
                        "inferred": False,
                    },
                },
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
                    {
                        "block_id": str(block_id),
                        "title": "Key findings",
                        "role": "key_findings",
                        "focus": "Training uptake",
                    }
                ],
                counts={},
                flags={},
                created_at=now(),
            )
        )
        return citation_ids, found_pss


def test_evidence_url_fallback_ladder() -> None:
    """The public URL prefers provider landing pages, then locator, then DOI."""
    assert repository._url({"landing_page_url": "https://landing.example"}, "https://locator") == (
        "https://landing.example"
    )
    assert repository._url({}, "https://locator.example") == "https://locator.example"
    assert repository._url(
        {"provider_fields": {"document_url": "https://provider.example"}}, None
    ) == "https://provider.example"
    assert repository._url({"doi": "10.1234/example"}, None) == "https://doi.org/10.1234/example"


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
            iof = next(row for row in findings if row["profile"] == "iof")
            icf = next(row for row in findings if row["profile"] == "icf")
            assert iof["statistics"] == {
                "effect_size": 1.2,
                "effect_size_type": None,
                "ci_lower": 1.0,
                "ci_upper": 1.4,
                "standard_error": None,
                "p_value": None,
                "n": None,
                "k": None,
                "i_squared": None,
                "tau2": None,
            }
            assert iof["quote"] == "Training increased uptake."
            assert iof["quote_verified"] is True
            assert iof["groups"] == {"intervention": "Training"}
            assert icf["claim"] == "Staff time constrained implementation."
            assert icf["quote_verified"] is True
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
                == "Searching completed. Coverage was judged adequate."
            )
            assert coverage["base"]["counts"] == {"found": 3, "relevant": 1, "screened_out": 1}
            assert coverage["backends"] == []
            assert coverage["backends_detail"] == []
            artefact = client.get(f"/api/v1/projects/{project_id}/artefact", headers=owner).json()
            assert artefact["sections"][0]["role"] == "key_findings"
            assert artefact["sections"][0]["focus"] == "Training uptake"
            assert artefact["sections"][0]["blocks"][0]["claims"][0]["citations"][0]["n"] == 1
            assert artefact["sections"][0]["blocks"][0]["claims"][0]["weakly_grounded"] is False
            assert artefact["sections"][0]["blocks"][0]["claims"][0]["gap"]["grade"] == "limited"
            all_evidence = client.get(
                f"/api/v1/projects/{project_id}/evidence?page=1&page_size=3", headers=owner
            ).json()["data"]
            cited_source = next(row for row in all_evidence if row["status"] == "cited")
            # Envelope authority (027 owner feedback, 2026-07-29): a citation
            # grounded in an ingested FULL-TEXT chunk still displays the
            # document's envelope title — never the text snapshot's locator —
            # and carries the document identity + the judge's rationale.
            citation_out = artefact["sections"][0]["blocks"][0]["claims"][0]["citations"][0]
            assert citation_out["source_title"] == "Selected trial"
            assert citation_out["source_id"] == cited_source["source_id"]
            assert citation_out["grounding_rationale"] == "Quote matches the source verbatim."
            # The appraisal band's scoring input rides with the label.
            assert citation_out["evidence_type"] == "RCTs and Quasi-Experimental Studies"
            assert citation_out["appraisal_label"] == "Moderate"
            # Reference identity is the document: three citations over three
            # full-text chunks of one source yield exactly one reference entry.
            assert [
                (reference["n"], reference["title"]) for reference in artefact["references"]
            ] == [(1, "Selected trial")]
            dossier = client.get(
                f"/api/v1/projects/{project_id}/sources/{cited_source['source_id']}", headers=owner
            )
            assert dossier.status_code == 200
            assert dossier.json()["abstract_source"] == "provider"
            assert dossier.json()["fwci"] == 1.5
            assert dossier.json()["tags"] == [
                {"tag": "School health", "tag_type": "topic_theme", "asserted_by": "openalex"}
            ]
            assert dossier.json()["cited_in"] == [
                {
                    "claim": "evidence",
                    "quote": "Cited evidence sentence.",
                    "section_title": "Key findings",
                }
            ] * 3
            assert (
                client.get(
                    f"/api/v1/projects/{project_id}/sources/{cited_source['source_id']}",
                    headers=other,
                ).status_code
                == 404
            )
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


def test_artefact_theme_claim_resolves_durable_references(tmp_path: Path, engine: Engine) -> None:
    """Theme claims resolve named characterisation and grouping references honestly."""
    with api_client(tmp_path) as (client, owner, _):
        project_id = uuid.UUID(create_project(client, owner))
        _, found_pss = _seed_read_model_ladder(engine, project_id)
        try:
            with engine.begin() as conn:
                synthesis = conn.execute(
                    select(
                        synthesis_result.c.evidence_scope_id,
                        synthesis_result.c.run_id,
                    ).where(synthesis_result.c.project_id == project_id)
                ).one()
                selected_pss = conn.execute(
                    select(source_extraction_record.c.project_source_snapshot_id).where(
                        source_extraction_record.c.project_id == project_id
                    )
                ).scalar_one()
                conn.execute(
                    insert(characterisation_result).values(
                        characterisation_id=uuid.uuid4(),
                        project_id=project_id,
                        evidence_scope_id=synthesis.evidence_scope_id,
                        run_id=synthesis.run_id,
                        grouping_provenance={},
                        coverage={},
                        themes={
                            "themes": [
                                {
                                    "theme_id": "characterisation:access",
                                    "name": "Access",
                                    "description": "Access to support",
                                    "size": 3,
                                    "member_ids": [str(selected_pss), str(found_pss)],
                                }
                            ]
                        },
                        created_at=now(),
                    )
                )
                annotation_id = conn.execute(
                    select(annotation.c.annotation_id).where(
                        annotation.c.block_id.in_(
                            select(block.c.block_id).where(
                                block.c.artefact_id
                                == select(synthesis_result.c.artefact_id)
                                .where(synthesis_result.c.project_id == project_id)
                                .scalar_subquery()
                            )
                        )
                    )
                ).scalar_one()
                conn.execute(
                    update(annotation)
                    .where(annotation.c.annotation_id == annotation_id)
                    .values(
                        annotation_type="theme",
                        payload={
                            "theme": {
                                "source": "characterisation",
                                "referenced_ids": ["characterisation:access"],
                                "base": "screened",
                            }
                        },
                    )
                )
            claim = client.get(f"/api/v1/projects/{project_id}/artefact", headers=owner).json()[
                "sections"
            ][0]["blocks"][0]["claims"][0]
            assert claim["theme"] == {
                "source": "characterisation",
                "base": "screened",
                "items": [
                    {
                        "name": "Access",
                        "description": "Access to support",
                        "size": 3,
                        "facet": None,
                        "sources": [
                            {"source_id": str(selected_pss), "title": "Selected trial"},
                            {"source_id": str(found_pss), "title": "Unscreened report"},
                        ],
                    }
                ],
            }

            with engine.begin() as conn:
                conn.execute(
                    update(characterisation_result)
                    .where(characterisation_result.c.project_id == project_id)
                    .values(
                        themes={
                            "themes": [
                                {
                                    "theme_id": "characterisation:access",
                                    "name": "Access",
                                    "member_ids": [str(selected_pss), str(uuid.uuid4())],
                                }
                            ]
                        }
                    )
                )
            claim = client.get(f"/api/v1/projects/{project_id}/artefact", headers=owner).json()[
                "sections"
            ][0]["blocks"][0]["claims"][0]
            assert claim["theme"]["items"][0]["sources"] == [
                {"source_id": str(selected_pss), "title": "Selected trial"}
            ]

            with engine.begin() as conn:
                conn.execute(
                    update(annotation)
                    .where(annotation.c.annotation_id == annotation_id)
                    .values(
                        payload={
                            "theme": {
                                "source": "grouping",
                                "referenced_ids": ["intervention:g01"],
                                "base": "extracted",
                            }
                        }
                    )
                )
            claim = client.get(f"/api/v1/projects/{project_id}/artefact", headers=owner).json()[
                "sections"
            ][0]["blocks"][0]["claims"][0]
            assert claim["theme"] == {
                "source": "grouping",
                "base": "extracted",
                "items": [
                    {
                        "name": "Training",
                        "description": "Training findings",
                        "size": 2,
                        "facet": "intervention",
                        "sources": [
                            {"source_id": str(selected_pss), "title": "Selected trial"}
                        ],
                    }
                ],
            }

            with engine.begin() as conn:
                conn.execute(
                    update(annotation)
                    .where(annotation.c.annotation_id == annotation_id)
                    .values(
                        payload={
                            "theme": {
                                "source": "grouping",
                                "referenced_ids": ["intervention:g99"],
                                "base": "extracted",
                            }
                        }
                    )
                )
            claim = client.get(f"/api/v1/projects/{project_id}/artefact", headers=owner).json()[
                "sections"
            ][0]["blocks"][0]["claims"][0]
            assert claim["theme"] is None
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def _seed_evidence_filter_fixture(engine: Engine, project_id: uuid.UUID) -> None:
    """Seed evidence spanning found/screened_out/selected/not_selected for filter tests."""
    with engine.begin() as conn:
        run_id = uuid.uuid4()
        conn.execute(
            insert(runs).values(
                run_id=run_id, project_id=project_id, status="running", started_at=now()
            )
        )
        scope_id = seed_scope(conn, project_id)
        for index in range(3):
            seed_source(conn, project_id, {"title": f"Found {index}"})
        _, screened_out_pss = seed_source(conn, project_id, {"title": "Screened out"})
        seed_screening_result(
            conn, project_id, run_id, scope_id, screened_out_pss, status="not_relevant"
        )
        _, selected_pss = seed_source(conn, project_id, {"title": "Selected"})
        seed_screening_result(conn, project_id, run_id, scope_id, selected_pss, status="relevant")
        _, not_selected_pss = seed_source(conn, project_id, {"title": "Not selected"})
        seed_screening_result(
            conn, project_id, run_id, scope_id, not_selected_pss, status="relevant"
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


def test_evidence_status_filter_collection_true_counts(tmp_path: Path, engine: Engine) -> None:
    """`status` filters the collection; `total_items` reflects the filter, not the page."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_evidence_filter_fixture(engine, project_id)
        try:
            found = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=found&page=1&page_size=2",
                headers=owner,
            )
            assert found.status_code == 200
            body = found.json()
            # Collection-true: total reflects the filtered collection (3), not the
            # page length (2) and not the unfiltered project total (6).
            assert body["pagination"] == {"page": 1, "page_size": 2, "total_items": 3}
            assert len(body["data"]) == 2
            assert {row["status"] for row in body["data"]} == {"found"}

            screened_out = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=screened_out", headers=owner
            ).json()
            assert screened_out["pagination"]["total_items"] == 1
            assert screened_out["data"][0]["status"] == "screened_out"

            # `Included` = the 7 in-ladder positions, i.e. everything but
            # found/screened_out — here, selected + not_selected.
            included = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=Included", headers=owner
            ).json()
            assert included["pagination"]["total_items"] == 2
            assert {row["status"] for row in included["data"]} == {"selected", "not_selected"}

            combined = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=found&status=screened_out",
                headers=owner,
            ).json()
            assert combined["pagination"]["total_items"] == 4
            assert {row["status"] for row in combined["data"]} == {"found", "screened_out"}

            invalid = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=bogus", headers=owner
            )
            assert invalid.status_code == 422
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_evidence_cited_filter_and_combination(tmp_path: Path, engine: Engine) -> None:
    """`cited` filters the collection and combines with `status`."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_read_model_ladder(engine, project_id)
        try:
            cited_only = client.get(
                f"/api/v1/projects/{project_id}/evidence?cited=true", headers=owner
            ).json()
            assert cited_only["pagination"]["total_items"] == 1
            assert cited_only["data"][0]["status"] == "cited"

            combined = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=Included&cited=true", headers=owner
            ).json()
            assert combined["pagination"]["total_items"] == 1

            none_match = client.get(
                f"/api/v1/projects/{project_id}/evidence?status=found&cited=true", headers=owner
            ).json()
            assert none_match["pagination"]["total_items"] == 0
            assert none_match["data"] == []
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def _seed_findings_filter_fixture(
    engine: Engine, project_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]:
    """Seed two sources with three grouped findings across two facets.

    Returns (source1_pss, source2_pss, iof1_id, iof2_id, icf1_id). `iof1` and
    `icf1` are extracted from source 1; `iof2` from source 2. `iof1` groups
    into `intervention:g01` ("Training"), `iof2` into `intervention:g02`
    ("Coaching"), `icf1` into `barrier_theme:g01` ("Staffing").
    """
    with engine.begin() as conn:
        run_id = uuid.uuid4()
        conn.execute(
            insert(runs).values(
                run_id=run_id, project_id=project_id, status="running", started_at=now()
            )
        )
        scope_id = seed_scope(conn, project_id)
        snap1_id, source1_pss = seed_source(conn, project_id, {"title": "Source one"})
        snap2_id, source2_pss = seed_source(conn, project_id, {"title": "Source two"})
        record1_id, record2_id = uuid.uuid4(), uuid.uuid4()
        conn.execute(
            insert(source_extraction_record).values(
                extraction_record_id=record1_id,
                project_id=project_id,
                source_snapshot_id=snap1_id,
                project_source_snapshot_id=source1_pss,
                extraction_fingerprint="fixture-1",
                status="extracted",
                basis="full_text",
                primary_evidence_type="RCTs and Quasi-Experimental Studies",
                error=None,
                finding_count=2,
                run_id=run_id,
                created_at=now(),
            )
        )
        conn.execute(
            insert(source_extraction_record).values(
                extraction_record_id=record2_id,
                project_id=project_id,
                source_snapshot_id=snap2_id,
                project_source_snapshot_id=source2_pss,
                extraction_fingerprint="fixture-2",
                status="extracted",
                basis="full_text",
                primary_evidence_type="RCTs and Quasi-Experimental Studies",
                error=None,
                finding_count=1,
                run_id=run_id,
                created_at=now(),
            )
        )
        iof1_id, iof2_id, icf1_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        conn.execute(
            insert(intervention_outcome_finding).values(
                finding_id=iof1_id,
                project_id=project_id,
                extraction_record_id=record1_id,
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
            insert(intervention_outcome_finding).values(
                finding_id=iof2_id,
                project_id=project_id,
                extraction_record_id=record2_id,
                intervention="Coaching",
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
                finding_id=icf1_id,
                project_id=project_id,
                extraction_record_id=record1_id,
                context_type="barrier",
                claim="Staff time constrained implementation.",
                intervention="Training",
                outcome="Uptake",
                population="School staff",
                setting="Schools",
                study_geography="GB",
                study_design="Process evaluation",
                field_coverage={},
                grounding=[],
                created_at=now(),
            )
        )
        conn.execute(
            insert(selection_result).values(
                selection_result_id=uuid.uuid4(),
                project_id=project_id,
                evidence_scope_id=scope_id,
                run_id=run_id,
                strategy="coverage_stratified_v1",
                budget=2,
                selection_provenance={},
                selected=[{"pss_id": str(source1_pss)}, {"pss_id": str(source2_pss)}],
                excluded={},
                flags={},
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
                extraction_provenance={"profiles": {IOF_PROFILE_ID: {}, ICF_PROFILE_ID: {}}},
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
                                "group_id": "intervention:g01",
                                "label": "Training",
                                "description": "Training findings",
                                "size": 1,
                                "member_finding_ids": [str(iof1_id)],
                            },
                            {
                                "group_id": "intervention:g02",
                                "label": "Coaching",
                                "description": "Coaching findings",
                                "size": 1,
                                "member_finding_ids": [str(iof2_id)],
                            },
                        ],
                        "ungrouped": {"finding_ids": []},
                        "no_value": {"finding_ids": []},
                    },
                    "barrier_theme": {
                        "groups": [
                            {
                                "group_id": "barrier_theme:g01",
                                "label": "Staffing",
                                "description": "Staffing barriers",
                                "size": 1,
                                "member_finding_ids": [str(icf1_id)],
                            }
                        ],
                        "ungrouped": {"finding_ids": []},
                        "no_value": {"finding_ids": []},
                    },
                },
                counts={},
                flags={},
                created_at=now(),
            )
        )
        return source1_pss, source2_pss, iof1_id, iof2_id, icf1_id


def test_findings_profile_and_source_filters(tmp_path: Path, engine: Engine) -> None:
    """`profile` and `source_id` filter the findings collection with true counts."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        source1_pss, _source2_pss, iof1_id, iof2_id, icf1_id = _seed_findings_filter_fixture(
            engine, project_id
        )
        try:
            iof_only = client.get(
                f"/api/v1/projects/{project_id}/findings?profile=iof", headers=owner
            ).json()
            assert iof_only["pagination"]["total_items"] == 2
            assert {row["finding_id"] for row in iof_only["data"]} == {
                str(iof1_id),
                str(iof2_id),
            }

            icf_only = client.get(
                f"/api/v1/projects/{project_id}/findings?profile=icf", headers=owner
            ).json()
            assert icf_only["pagination"]["total_items"] == 1
            assert icf_only["data"][0]["finding_id"] == str(icf1_id)

            by_source = client.get(
                f"/api/v1/projects/{project_id}/findings?source_id={source1_pss}", headers=owner
            ).json()
            assert by_source["pagination"]["total_items"] == 2
            assert {row["finding_id"] for row in by_source["data"]} == {
                str(iof1_id),
                str(icf1_id),
            }

            unknown_source = client.get(
                f"/api/v1/projects/{project_id}/findings?source_id={uuid.uuid4()}", headers=owner
            ).json()
            assert unknown_source["pagination"]["total_items"] == 0
            assert unknown_source["data"] == []

            invalid_profile = client.get(
                f"/api/v1/projects/{project_id}/findings?profile=bogus", headers=owner
            )
            assert invalid_profile.status_code == 422
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_findings_group_filters_and_validation(tmp_path: Path, engine: Engine) -> None:
    """`facet`+`group` and `group_id` filter findings; bad combinations 422."""
    with api_client(tmp_path) as (client, owner, other):
        project_id = uuid.UUID(create_project(client, owner))
        _source1_pss, _source2_pss, iof1_id, iof2_id, _icf1_id = _seed_findings_filter_fixture(
            engine, project_id
        )
        try:
            by_facet_group = client.get(
                f"/api/v1/projects/{project_id}/findings?facet=intervention&group=Training",
                headers=owner,
            ).json()
            assert by_facet_group["pagination"]["total_items"] == 1
            assert by_facet_group["data"][0]["finding_id"] == str(iof1_id)

            by_group_id = client.get(
                f"/api/v1/projects/{project_id}/findings?group_id=intervention:g02", headers=owner
            ).json()
            assert by_group_id["pagination"]["total_items"] == 1
            assert by_group_id["data"][0]["finding_id"] == str(iof2_id)

            unknown_group = client.get(
                f"/api/v1/projects/{project_id}/findings?facet=intervention&group=Nope",
                headers=owner,
            ).json()
            assert unknown_group["pagination"]["total_items"] == 0
            assert unknown_group["data"] == []

            unknown_group_id = client.get(
                f"/api/v1/projects/{project_id}/findings?group_id=nope:g01", headers=owner
            ).json()
            assert unknown_group_id["pagination"]["total_items"] == 0

            combined = client.get(
                f"/api/v1/projects/{project_id}/findings"
                "?facet=intervention&group=Training&profile=iof",
                headers=owner,
            ).json()
            assert combined["pagination"]["total_items"] == 1

            facet_without_group = client.get(
                f"/api/v1/projects/{project_id}/findings?facet=intervention", headers=owner
            )
            assert facet_without_group.status_code == 422

            group_id_with_facet = client.get(
                f"/api/v1/projects/{project_id}/findings"
                "?group_id=intervention:g01&facet=intervention",
                headers=owner,
            )
            assert group_id_with_facet.status_code == 422
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)
