"""Golden HTTP tests for the durable Task 025 read-model endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

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
    source_appraisal_result,
    source_classification_result,
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
                "A" * 900 + " Cited evidence sentence." + "B" * 900,
                "A" * 900 + " Cited evidence sentence.",
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
        iof_chunk_id = uuid.uuid4()
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
                        "chunk_id": str(iof_chunk_id),
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
    assert (
        repository._url({"provider_fields": {"document_url": "https://provider.example"}}, None)
        == "https://provider.example"
    )
    assert repository._url({"doi": "10.1234/example"}, None) == "https://doi.org/10.1234/example"


def test_context_window_snaps_cuts_to_word_boundaries() -> None:
    """A mid-word cut drops the partial word; an unspaced run into the quote does not."""
    text = "one two three four five"
    assert repository._snap_start(text, 5, not_past=len(text)) == 8
    assert repository._snap_start(text, 4, not_past=len(text)) == 4
    assert repository._snap_start(text, 0, not_past=len(text)) == 0
    assert repository._snap_end(text, 10, not_before=0) == 7
    assert repository._snap_end(text, len(text), not_before=0) == len(text)
    glued = ("A" * 50) + " quote"
    assert repository._snap_start(glued, 10, not_past=50) == 10
    assert repository._snap_end(glued + ("B" * 50), 60, not_before=56) == 60


def test_edge_snippet_marks_both_ends_and_starts_on_a_word() -> None:
    """Neighbour snippets wrap with '...' and do not begin mid-word."""
    previous = "OFFTOPIC PREVIOUS " + ("P" * 400) + " trailing previous sentence."
    assert repository._edge_snippet(previous, from_end=True) == "...trailing previous sentence...."
    following = "leading next sentence. " + ("N" * 400) + " OFFTOPIC NEXT"
    assert repository._edge_snippet(following, from_end=False) == "...leading next sentence...."


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
            assert iof["chunk_id"] is not None
            assert iof["groups"] == {"intervention": "Training"}
            assert icf["claim"] == "Staff time constrained implementation."
            assert icf["quote_verified"] is True
            assert icf["chunk_id"] is None
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
            assert coverage["sentence"] == "Searching completed. Coverage was judged adequate."
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
            assert (
                dossier.json()["cited_in"]
                == [
                    {
                        "claim": "evidence",
                        "quote": "Cited evidence sentence.",
                        "section_title": "Key findings",
                    }
                ]
                * 3
            )
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
            assert near_start["context"].endswith("...")
            assert not near_start["context"].startswith("...")
            assert middle["context"].startswith("...")
            assert middle["context"].endswith("...")
            assert near_end["context"].startswith("...")
            assert not near_end["context"].endswith("...")
            assert all(context["clamped"] is True for context in (near_start, middle, near_end))
            assert all(
                context["context"][context["span_start"] : context["span_end"]]
                == "Cited evidence sentence."
                for context in (near_start, middle, near_end)
            )
            # Left padding is a word of A's, so the start cut snaps to the quote.
            # Right padding is unspaced B's, so the end cut stays a character window.
            assert near_end["context"] == "...Cited evidence sentence."
            assert middle["context"].startswith("...Cited evidence sentence.")
            assert len(near_start["context"]) == 827
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
                # The artefact resolves themes via the synthesis row's pinned
                # characterisation_run_id — never "latest by created_at".
                conn.execute(
                    update(synthesis_result)
                    .where(synthesis_result.c.project_id == project_id)
                    .values(characterisation_run_id=synthesis.run_id)
                )
                decoy_run_id = uuid.uuid4()
                conn.execute(
                    insert(runs).values(
                        run_id=decoy_run_id,
                        project_id=project_id,
                        status="running",
                        started_at=now(),
                    )
                )
                conn.execute(
                    insert(characterisation_result).values(
                        characterisation_id=uuid.uuid4(),
                        project_id=project_id,
                        evidence_scope_id=synthesis.evidence_scope_id,
                        run_id=decoy_run_id,
                        grouping_provenance={},
                        coverage={},
                        themes={
                            "themes": [
                                {
                                    "theme_id": "characterisation:access",
                                    "name": "DECOY — a later run reused this id",
                                    "size": 99,
                                    "member_ids": [],
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
                        "sources": [{"source_id": str(selected_pss), "title": "Selected trial"}],
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


def _seed_evidence_filter_fixture(engine: Engine, project_id: uuid.UUID) -> uuid.UUID:
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
    return scope_id


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


def test_evidence_sort_theme_filter_and_validation(tmp_path: Path, engine: Engine) -> None:
    """Evidence sorting is collection-wide, stable, and theme-id addressable."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        scope_id = _seed_evidence_filter_fixture(engine, project_id)
        theme_id = uuid.uuid4()
        with engine.begin() as conn:
            rows = conn.execute(
                select(
                    project_source_snapshot.c.project_source_snapshot_id,
                    project_source_snapshot.c.source_snapshot_id,
                    source_snapshot.c.metadata,
                )
                .select_from(
                    project_source_snapshot.join(
                        source_snapshot,
                        project_source_snapshot.c.source_snapshot_id
                        == source_snapshot.c.source_snapshot_id,
                    )
                )
                .where(project_source_snapshot.c.project_id == project_id)
            ).all()
            title_rows = {
                row.metadata["title"]: row
                for row in rows
                if isinstance(row.metadata, dict) and isinstance(row.metadata.get("title"), str)
            }
            conn.execute(
                update(source_snapshot)
                .where(
                    source_snapshot.c.source_snapshot_id == title_rows["Found 0"].source_snapshot_id
                )
                .values(metadata={"title": "alpha", "year": 2010})
            )
            conn.execute(
                update(source_snapshot)
                .where(
                    source_snapshot.c.source_snapshot_id == title_rows["Found 1"].source_snapshot_id
                )
                .values(metadata={"title": "Bravo", "year": 2025})
            )
            run_id = uuid.uuid4()
            conn.execute(
                insert(runs).values(
                    run_id=run_id, project_id=project_id, status="running", started_at=now()
                )
            )
            conn.execute(
                insert(source_classification_result).values(
                    source_classification_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=title_rows["Found 0"].project_source_snapshot_id,
                    project_id=project_id,
                    classified_by_run_id=run_id,
                    primary_evidence_type="RCTs and Quasi-Experimental Studies",
                    classified_at=now(),
                )
            )
            conn.execute(
                insert(source_appraisal_result).values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=title_rows["Found 0"].project_source_snapshot_id,
                    project_id=project_id,
                    appraised_by_run_id=run_id,
                    quality_score=4,
                    rubric_version="test",
                    appraised_at=now(),
                )
            )
            conn.execute(
                insert(source_tag).values(
                    source_tag_id=uuid.uuid4(),
                    project_id=project_id,
                    project_source_snapshot_id=title_rows["Found 1"].project_source_snapshot_id,
                    tag="Legacy Theme alpha",
                    tag_type="topic_theme",
                    asserted_by="characterise",
                    created_by_run_id=run_id,
                    created_at=now(),
                    theme_id=None,
                )
            )
            conn.execute(
                insert(source_tag).values(
                    source_tag_id=uuid.uuid4(),
                    project_id=project_id,
                    project_source_snapshot_id=title_rows["Found 0"].project_source_snapshot_id,
                    tag="Theme alpha",
                    tag_type="topic_theme",
                    asserted_by="characterise",
                    created_by_run_id=run_id,
                    created_at=now(),
                    theme_id=theme_id,
                )
            )
        try:
            by_title = client.get(
                f"/api/v1/projects/{project_id}/evidence?sort=title", headers=owner
            ).json()["data"]
            assert by_title[0]["title"] == "alpha"
            by_year = client.get(
                f"/api/v1/projects/{project_id}/evidence?sort=year", headers=owner
            ).json()["data"]
            assert [item["year"] for item in by_year if item["year"] is not None][:2] == [
                2025,
                2010,
            ]
            by_status = client.get(
                f"/api/v1/projects/{project_id}/evidence?sort=status", headers=owner
            ).json()["data"]
            ranks = {
                status: index
                for index, status in enumerate(
                    [
                        "found",
                        "screened_out",
                        "relevant",
                        "not_selected",
                        "selected",
                        "read_in_full",
                        "findings_extracted",
                        "cited",
                        "unavailable",
                    ]
                )
            }
            assert [ranks[item["status"]] for item in by_status] == sorted(
                ranks[item["status"]] for item in by_status
            )
            field_by_sort = {
                "title": "title",
                "year": "year",
                "type": "evidence_type",
                "strength": "appraisal_tier",
                "status": "status",
            }
            for sort, field in field_by_sort.items():
                for order in ("asc", "desc"):
                    ordered = client.get(
                        f"/api/v1/projects/{project_id}/evidence?sort={sort}&order={order}"
                        "&page_size=20",
                        headers=owner,
                    ).json()["data"]
                    values = [item[field] for item in ordered]
                    first_null = next(
                        (index for index, value in enumerate(values) if value is None), len(values)
                    )
                    assert all(value is None for value in values[first_null:])

            # Sorting occurs before paging. Equal titles retain the source list's
            # ingestion order, even when the tie crosses page boundaries.
            with engine.begin() as conn:
                for title in ("Found 0", "Found 1", "Found 2"):
                    snapshot_id = title_rows[title].source_snapshot_id
                    conn.execute(
                        update(source_snapshot)
                        .where(source_snapshot.c.source_snapshot_id == snapshot_id)
                        .values(metadata={"title": "Tie"})
                    )
            unsorted = client.get(
                f"/api/v1/projects/{project_id}/evidence?page_size=20", headers=owner
            ).json()["data"]
            expected_tie_order = [item["source_id"] for item in unsorted if item["title"] == "Tie"]
            sorted_ties = [
                item["source_id"]
                for page in range(1, 5)
                for item in client.get(
                    f"/api/v1/projects/{project_id}/evidence?sort=title&page={page}&page_size=2",
                    headers=owner,
                ).json()["data"]
                if item["title"] == "Tie"
            ]
            assert sorted_ties == expected_tie_order
            themed = client.get(
                f"/api/v1/projects/{project_id}/evidence?theme={theme_id}&status=found&cited=false",
                headers=owner,
            ).json()
            assert [item["title"] for item in themed["data"]] == ["Tie"]
            assert (
                client.get(
                    f"/api/v1/projects/{project_id}/evidence?theme={uuid.uuid4()}", headers=owner
                ).json()["pagination"]["total_items"]
                == 0
            )
            assert (
                client.get(
                    f"/api/v1/projects/{project_id}/evidence?order=desc", headers=owner
                ).status_code
                == 422
            )
            assert (
                client.get(
                    f"/api/v1/projects/{project_id}/evidence?sort=unknown", headers=owner
                ).status_code
                == 422
            )
            assert (
                client.get(
                    f"/api/v1/projects/{project_id}/evidence?sort=year&order=sideways",
                    headers=owner,
                ).status_code
                == 422
            )
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_artefact_summary_projection_and_multi_block_omission(
    tmp_path: Path, engine: Engine
) -> None:
    """Single-block summaries project; multi-block sections honestly omit them."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_read_model_ladder(engine, project_id)
        try:
            with engine.begin() as conn:
                artefact_id = conn.execute(
                    select(synthesis_result.c.artefact_id).where(
                        synthesis_result.c.project_id == project_id
                    )
                ).scalar_one()
                original_block_id = conn.execute(
                    select(block.c.block_id).where(block.c.artefact_id == artefact_id)
                ).scalar_one()
                conn.execute(
                    update(artefact)
                    .where(artefact.c.artefact_id == artefact_id)
                    .values(summary="Artefact takeaway.", summary_status="verified")
                )
                conn.execute(
                    update(block)
                    .where(block.c.block_id == original_block_id)
                    .values(summary="Section takeaway.", summary_status="verified")
                )
            artefact_body = client.get(
                f"/api/v1/projects/{project_id}/artefact", headers=owner
            ).json()
            assert artefact_body["summary"] == "Artefact takeaway."
            assert artefact_body["summary_status"] == "verified"
            assert artefact_body["sections"][0]["summary"] == "Section takeaway."
            assert artefact_body["sections"][0]["summary_status"] == "verified"

            with engine.begin() as conn:
                second_block_id = uuid.uuid4()
                conn.execute(
                    insert(block).values(
                        block_id=second_block_id,
                        artefact_id=artefact_id,
                        version=1,
                        content="A second physical block.",
                        content_hash="second-block",
                        summary="Must not project.",
                        summary_status="verified",
                        created_at=now(),
                    )
                )
                blocks = conn.execute(
                    select(synthesis_result.c.blocks).where(
                        synthesis_result.c.project_id == project_id
                    )
                ).scalar_one()
                conn.execute(
                    update(synthesis_result)
                    .where(synthesis_result.c.project_id == project_id)
                    .values(
                        blocks=[
                            *blocks,
                            {
                                "block_id": str(second_block_id),
                                "title": "Key findings",
                                "role": "key_findings",
                                "focus": "Training uptake",
                            },
                        ]
                    )
                )
            multi_block_section = client.get(
                f"/api/v1/projects/{project_id}/artefact", headers=owner
            ).json()["sections"][0]
            assert len(multi_block_section["blocks"]) == 2
            assert multi_block_section["summary"] is None
            assert multi_block_section["summary_status"] is None
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_landscape_cited_scope_uses_only_latest_artefact_members(
    tmp_path: Path, engine: Engine
) -> None:
    """The cited landscape excludes screened-in but uncited sources and themes."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_read_model_ladder(engine, project_id)
        try:
            with engine.begin() as conn:
                synthesis = conn.execute(
                    select(
                        synthesis_result.c.evidence_scope_id,
                        synthesis_result.c.run_id,
                    ).where(synthesis_result.c.project_id == project_id)
                ).one()
                selected_pss = conn.execute(
                    select(project_source_snapshot.c.project_source_snapshot_id)
                    .select_from(
                        project_source_snapshot.join(
                            source_snapshot,
                            project_source_snapshot.c.source_snapshot_id
                            == source_snapshot.c.source_snapshot_id,
                        )
                    )
                    .where(
                        project_source_snapshot.c.project_id == project_id,
                        source_snapshot.c.metadata["title"].astext == "Selected trial",
                    )
                ).scalar_one()
                uncited_pss = seed_select_doc(
                    conn,
                    project_id,
                    synthesis.run_id,
                    synthesis.evidence_scope_id,
                    title="Uncited relevant trial",
                    year=2021,
                )
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
                                    "theme_id": str(uuid.uuid4()),
                                    "name": "Cited theme",
                                    "description": "Contains the cited source.",
                                    "member_ids": [str(selected_pss)],
                                    "size": 1,
                                },
                                {
                                    "theme_id": str(uuid.uuid4()),
                                    "name": "Uncited theme",
                                    "description": "Contains only the uncited source.",
                                    "member_ids": [str(uncited_pss)],
                                    "size": 1,
                                },
                            ]
                        },
                        created_at=now(),
                    )
                )
            whole = client.get(f"/api/v1/projects/{project_id}/landscape", headers=owner).json()
            cited = client.get(
                f"/api/v1/projects/{project_id}/landscape?scope=cited", headers=owner
            ).json()
            assert whole["years"] == {"2020": 1, "2021": 1}
            assert cited["years"] == {"2020": 1}
            assert [theme["name"] for theme in cited["themes"]] == ["Cited theme"]
            assert (
                client.get(
                    f"/api/v1/projects/{project_id}/landscape?scope=whole", headers=owner
                ).status_code
                == 422
            )
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_landscape_geography_residual_makes_every_scope_add_up(
    tmp_path: Path, engine: Engine
) -> None:
    """Task 031 invariant 4: country bars + "Not reported" = the population drawn.

    A second relevant source is seeded with no publisher country. Before this
    slice `_geography` returning ``None`` dropped it from the chart, so the bars
    summed below the funnel's relevant count (defect 3). The cited scope keeps
    its own, smaller total — it must not be "corrected" to the funnel's.
    """
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_read_model_ladder(engine, project_id)
        try:
            with engine.begin() as conn:
                scope_id = conn.execute(
                    select(search_coverage_record.c.evidence_scope_id).where(
                        search_coverage_record.c.project_id == project_id
                    )
                ).scalar_one()
                run_id = conn.execute(
                    select(search_coverage_record.c.acquired_by_run_id).where(
                        search_coverage_record.c.project_id == project_id
                    )
                ).scalar_one()
                # A second relevant source, and the country goes on THIS one —
                # the uncited one. The ladder's cited source stays countryless,
                # so the residual is what the cited scope has to draw. Putting
                # the country on the cited source instead would make the cited
                # assertion pass even if the residual were skipped at that
                # scope, which is the whole thing this test exists to pin.
                _, uncited_with_country = seed_source(
                    conn, project_id, {"title": "Reported country", "backend": "openalex"}
                )
                seed_screening_result(
                    conn, project_id, run_id, scope_id, uncited_with_country, status="relevant"
                )
                for snapshot_id, metadata in conn.execute(
                    select(source_snapshot.c.source_snapshot_id, source_snapshot.c.metadata)
                    .select_from(
                        source_snapshot.join(
                            project_source_snapshot,
                            project_source_snapshot.c.source_snapshot_id
                            == source_snapshot.c.source_snapshot_id,
                        )
                    )
                    .where(
                        project_source_snapshot.c.project_id == project_id,
                        source_snapshot.c.metadata["title"].astext == "Reported country",
                    )
                ).all():
                    conn.execute(
                        update(source_snapshot)
                        .where(source_snapshot.c.source_snapshot_id == snapshot_id)
                        .values(metadata={**metadata, "publication_country": "GB"})
                    )

            funnel = client.get(f"/api/v1/projects/{project_id}/funnel", headers=owner).json()
            whole = client.get(f"/api/v1/projects/{project_id}/landscape", headers=owner).json()
            assert whole["geographies"] == {"GB": 1, "Not reported": 1}
            assert sum(whole["geographies"].values()) == funnel["relevant"] == 2

            cited = client.get(
                f"/api/v1/projects/{project_id}/landscape?scope=cited", headers=owner
            ).json()
            # The cited scope draws only the artefact's citations, so it sums to
            # that smaller population — not to the funnel's relevant count. The
            # residual is what it draws, which is only true because the count
            # happens inside the loop over the already-narrowed rows.
            assert cited["geographies"] == {"Not reported": 1}
            assert sum(cited["geographies"].values()) == 1 != funnel["relevant"]
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_coverage_ignores_a_superseded_questions_rounds(
    tmp_path: Path, engine: Engine
) -> None:
    """"Where I looked" describes one question, cumulatively — not the project.

    Approving a plan mints a new ``evidence_scope`` (``orchestrate.py``), so a
    re-planned project holds the abandoned question's coverage records too.
    Summing acquire runs project-wide put that question's query strings and hits
    into this question's card, beside a sentence read from the current
    question's row (review stack, task 031). Round-cumulative was the fix;
    question-cumulative was not.
    """
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_read_model_ladder(engine, project_id)
        try:
            with engine.begin() as conn:
                old_run = conn.execute(
                    select(search_coverage_record.c.acquired_by_run_id).where(
                        search_coverage_record.c.project_id == project_id
                    )
                ).scalar_one()
                events.append(
                    conn,
                    project_id=project_id,
                    run_id=old_run,
                    event_type="search.executed",
                    payload={
                        "backend": "openalex",
                        "query": "abandoned question",
                        "result_count": 99,
                    },
                )
                # The replan: a second scope, its own acquire run, its own row.
                new_scope = seed_scope(conn, project_id)
                new_run = uuid.uuid4()
                conn.execute(
                    insert(runs).values(
                        run_id=new_run,
                        project_id=project_id,
                        status="running",
                        started_at=now(),
                    )
                )
                events.append(
                    conn,
                    project_id=project_id,
                    run_id=new_run,
                    event_type="search.executed",
                    payload={
                        "backend": "openalex",
                        "query": "current question",
                        "result_count": 7,
                    },
                )
                conn.execute(
                    insert(search_coverage_record).values(
                        search_coverage_record_id=uuid.uuid4(),
                        evidence_scope_id=new_scope,
                        project_id=project_id,
                        acquired_by_run_id=new_run,
                        backends=[{"backend": "openalex", "trust_class": "academic"}],
                        scope_filters={},
                        stop_condition="completed",
                        adequacy_verdict="adequate",
                        verdict_origin="model",
                        created_at=now(),
                    )
                )

            coverage = client.get(
                f"/api/v1/projects/{project_id}/coverage", headers=owner
            ).json()
            detail = next(
                row for row in coverage["backends_detail"] if row["backend"] == "OpenAlex"
            )
            assert [query["query"] for query in detail["queries"]] == ["current question"]
            assert detail["results"] == 7, "the abandoned question's 99 hits must not count"
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def test_coverage_backend_results_sum_query_hits_across_every_round(
    tmp_path: Path, engine: Engine
) -> None:
    """Task 031 invariant 3: `results` is cumulative, not the last round only.

    A second acquire round is seeded with its own coverage record and query
    events. Before this slice `coverage_out` passed only the newest record's
    ``acquired_by_run_id``, so the pane reported round 2's hits alone beside a
    cumulative relevant count — defect 2's two grains on one line.
    """
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        _seed_read_model_ladder(engine, project_id)
        try:
            with engine.begin() as conn:
                scope_id = conn.execute(
                    select(search_coverage_record.c.evidence_scope_id).where(
                        search_coverage_record.c.project_id == project_id
                    )
                ).scalar_one()
                round_one_run = conn.execute(
                    select(search_coverage_record.c.acquired_by_run_id).where(
                        search_coverage_record.c.project_id == project_id
                    )
                ).scalar_one()
                # Round 1 already owns a coverage record from the ladder; give it
                # a named OpenAlex hit so both rounds contribute.
                events.append(
                    conn,
                    project_id=project_id,
                    run_id=round_one_run,
                    event_type="search.executed",
                    payload={"backend": "openalex", "query": "round one", "result_count": 40},
                )
                round_two_run = uuid.uuid4()
                conn.execute(
                    insert(runs).values(
                        run_id=round_two_run,
                        project_id=project_id,
                        status="running",
                        started_at=now(),
                    )
                )
                events.append(
                    conn,
                    project_id=project_id,
                    run_id=round_two_run,
                    event_type="search.executed",
                    payload={"backend": "openalex", "query": "round two", "result_count": 32},
                )
                conn.execute(
                    insert(search_coverage_record).values(
                        search_coverage_record_id=uuid.uuid4(),
                        evidence_scope_id=scope_id,
                        project_id=project_id,
                        acquired_by_run_id=round_two_run,
                        backends=[{"backend": "openalex", "trust_class": "academic"}],
                        scope_filters={},
                        stop_condition="completed",
                        adequacy_verdict="adequate",
                        verdict_origin="model",
                        created_at=now(),
                    )
                )
                # Attribute the ladder's sources to OpenAlex so the relevance
                # half of the line is actually exercised.
                for snapshot_id, metadata in conn.execute(
                    select(source_snapshot.c.source_snapshot_id, source_snapshot.c.metadata)
                    .select_from(
                        source_snapshot.join(
                            project_source_snapshot,
                            project_source_snapshot.c.source_snapshot_id
                            == source_snapshot.c.source_snapshot_id,
                        )
                    )
                    .where(project_source_snapshot.c.project_id == project_id)
                ).all():
                    conn.execute(
                        update(source_snapshot)
                        .where(source_snapshot.c.source_snapshot_id == snapshot_id)
                        .values(metadata={**metadata, "backend": "openalex"})
                    )

            coverage = client.get(
                f"/api/v1/projects/{project_id}/coverage", headers=owner
            ).json()
            detail = next(
                row for row in coverage["backends_detail"] if row["backend"] == "OpenAlex"
            )
            assert detail["results"] == 72, "both rounds' hits, not round 2's 32 alone"
            assert [query["query"] for query in detail["queries"]] == ["round one", "round two"]
            # The 027 §C.1 behaviour is deliberately untouched: relevance stays
            # project-wide per backend, so it is not a subset of the hit total.
            assert detail["relevant"] == 1
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


def test_evidence_facet_filters_reasons_and_read_depth(tmp_path: Path, engine: Engine) -> None:
    """origin/evidence_type/strength filter collection-true; event reasons + read depth surface."""
    with api_client(tmp_path) as (client, owner, _other):
        project_id = uuid.UUID(create_project(client, owner))
        scope_id = _seed_evidence_filter_fixture(engine, project_id)
        with engine.begin() as conn:
            rows = conn.execute(
                select(
                    project_source_snapshot.c.project_source_snapshot_id,
                    source_snapshot.c.metadata,
                )
                .select_from(
                    project_source_snapshot.join(
                        source_snapshot,
                        project_source_snapshot.c.source_snapshot_id
                        == source_snapshot.c.source_snapshot_id,
                    )
                )
                .where(project_source_snapshot.c.project_id == project_id)
            ).all()
            by_title = {
                row.metadata["title"]: row.project_source_snapshot_id
                for row in rows
                if isinstance(row.metadata, dict) and isinstance(row.metadata.get("title"), str)
            }
            run_id = uuid.uuid4()
            conn.execute(
                insert(runs).values(
                    run_id=run_id, project_id=project_id, status="running", started_at=now()
                )
            )
            conn.execute(
                insert(source_classification_result).values(
                    source_classification_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=by_title["Selected"],
                    project_id=project_id,
                    classified_by_run_id=run_id,
                    primary_evidence_type="Systematic Review and Meta-Analysis",
                    classified_at=now(),
                )
            )
            conn.execute(
                insert(source_appraisal_result).values(
                    source_appraisal_result_id=uuid.uuid4(),
                    evidence_scope_id=scope_id,
                    project_source_snapshot_id=by_title["Selected"],
                    project_id=project_id,
                    appraised_by_run_id=run_id,
                    quality_score=2,
                    rubric_version="test",
                    appraised_at=now(),
                )
            )
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="source.screened",
                payload={
                    "project_source_snapshot_id": str(by_title["Selected"]),
                    "status": "relevant",
                    "reps": [
                        # A dissenting rep first: the surfaced reason must be
                        # the one agreeing with the aggregated decision.
                        {
                            "decision": "not_relevant",
                            "confidence": 0.4,
                            "reason": "Setting unclear",
                        },
                        {
                            "decision": "relevant",
                            "confidence": 0.9,
                            "reason": "UK primary cohort in scope",
                        },
                    ],
                },
            )
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="source.screened",
                payload={
                    "project_source_snapshot_id": str(by_title["Screened out"]),
                    "status": "not_relevant",
                    "reps": [
                        {
                            "decision": "not_relevant",
                            "confidence": 0.95,
                            "reason": "Adult-only population",
                        }
                    ],
                },
            )
            events.append(
                conn,
                project_id=project_id,
                run_id=run_id,
                event_type="source.classified",
                payload={
                    "project_source_snapshot_id": str(by_title["Selected"]),
                    "primary_evidence_type": "Systematic Review and Meta-Analysis",
                    "confidence": 0.8,
                    "reason": "Systematic review of trials",
                },
            )
            seed_ingested_full_text(conn, pss_id=by_title["Selected"], chunks=["Full text body."])
        try:
            typed = client.get(
                f"/api/v1/projects/{project_id}/evidence?evidence_type=Systematic%20Review%20and%20Meta-Analysis",
                headers=owner,
            ).json()
            assert typed["pagination"]["total_items"] == 1
            selected_row = typed["data"][0]
            assert selected_row["title"] == "Selected"
            assert selected_row["screen_reason"] == "UK primary cohort in scope"
            assert selected_row["classification_reason"] == "Systematic review of trials"
            assert selected_row["read_in_full"] is True

            limited = client.get(
                f"/api/v1/projects/{project_id}/evidence?strength=Limited", headers=owner
            ).json()
            assert limited["pagination"]["total_items"] == 1
            assert limited["data"][0]["appraisal_tier"] == "Limited"
            strong = client.get(
                f"/api/v1/projects/{project_id}/evidence?strength=Strong", headers=owner
            ).json()
            assert strong["pagination"]["total_items"] == 0

            uploaded = client.get(
                f"/api/v1/projects/{project_id}/evidence?origin=Uploaded", headers=owner
            ).json()
            assert uploaded["pagination"]["total_items"] == 6
            openalex = client.get(
                f"/api/v1/projects/{project_id}/evidence?origin=OpenAlex", headers=owner
            ).json()
            assert openalex["pagination"]["total_items"] == 0
            invalid = client.get(
                f"/api/v1/projects/{project_id}/evidence?origin=bogus", headers=owner
            )
            assert invalid.status_code == 422

            unfiltered = client.get(
                f"/api/v1/projects/{project_id}/evidence", headers=owner
            ).json()
            screened_out_row = next(
                row for row in unfiltered["data"] if row["title"] == "Screened out"
            )
            assert screened_out_row["screen_reason"] == "Adult-only population"
            assert screened_out_row["read_in_full"] is False

            dossier = client.get(
                f"/api/v1/projects/{project_id}/sources/{by_title['Selected']}", headers=owner
            ).json()
            assert dossier["screen_reason"] == "UK primary cohort in scope"
            assert dossier["classification_reason"] == "Systematic review of trials"
            assert dossier["read_in_full"] is True

            # Relevance sort (default direction desc): the p(relevant)
            # spectrum — relevant by falling confidence (0.9 seeded default
            # for both relevant rows), then not-relevant by rising confidence,
            # unscreened rows last as nulls.
            spectrum = client.get(
                f"/api/v1/projects/{project_id}/evidence?sort=relevance", headers=owner
            ).json()
            ranks = [row["screen_status"] for row in spectrum["data"]]
            assert ranks[:3].count("relevant") == 2
            assert ranks[2] == "not_relevant"
            assert all(status is None for status in ranks[3:])

            # Year bounds are collection-true and drop unknown-year rows.
            with engine.begin() as conn:
                conn.execute(
                    update(source_snapshot)
                    .where(
                        source_snapshot.c.source_snapshot_id
                        == conn.execute(
                            select(project_source_snapshot.c.source_snapshot_id).where(
                                project_source_snapshot.c.project_source_snapshot_id
                                == by_title["Screened out"]
                            )
                        ).scalar_one()
                    )
                    .values(metadata={"title": "Screened out", "year": 2015})
                )
            bounded = client.get(
                f"/api/v1/projects/{project_id}/evidence?year_from=2014&year_to=2016",
                headers=owner,
            ).json()
            assert bounded["pagination"]["total_items"] == 1
            assert bounded["data"][0]["title"] == "Screened out"
        finally:
            with engine.begin() as conn:
                delete_project_data(conn, project_id)


def _seed_artefact_citation(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    chunks: tuple[str, ...],
    quote: str,
    cite_sequence: int,
) -> uuid.UUID:
    """Insert one artefact citation over a snapshot's chunks; return citation id."""
    snapshot_id, _ = seed_source(conn, project_id)
    cited_chunk_id: uuid.UUID | None = None
    for sequence, content in enumerate(chunks):
        chunk_id = uuid.uuid4()
        conn.execute(
            insert(chunk).values(
                chunk_id=chunk_id,
                source_snapshot_id=snapshot_id,
                sequence=sequence,
                content=content,
                content_hash=f"ctx-{sequence}",
                locator={"start": 0, "end": len(content)},
                segmentation_policy="manual_v1",
                created_at=now(),
            )
        )
        if sequence == cite_sequence:
            cited_chunk_id = chunk_id
    assert cited_chunk_id is not None
    artefact_id, block_id, unit_id, annotation_id, citation_id = (uuid.uuid4() for _ in range(5))
    conn.execute(
        insert(artefact).values(
            artefact_id=artefact_id, project_id=project_id, title="Evidence base", created_at=now()
        )
    )
    conn.execute(
        insert(block).values(
            block_id=block_id,
            artefact_id=artefact_id,
            version=1,
            content="claim",
            content_hash="ctx",
            created_at=now(),
        )
    )
    conn.execute(
        insert(addressable_unit).values(
            unit_id=unit_id,
            block_id=block_id,
            unit_type="text_span",
            locator={"start": 0, "end": 5},
            content="claim",
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
    conn.execute(
        insert(citation).values(
            citation_id=citation_id,
            annotation_id=annotation_id,
            chunk_id=cited_chunk_id,
            quote=quote,
            verification_result="pass",
            created_at=now(),
        )
    )
    return citation_id


def test_artefact_citation_context_tolerates_quote_normalisation(
    tmp_path: Path, engine: Engine
) -> None:
    """Curly quotes / case still locate a unique span (same locator as chat)."""
    project_id: uuid.UUID | None = None
    with api_client(tmp_path) as (client, owner, _):
        try:
            project_id = uuid.UUID(create_project(client, owner))
            raw_span = "The report found “Clear   Evidence”\nacross studies."
            content = "Before text. " + "x" * 900 + " " + raw_span + " " + "y" * 900
            with engine.begin() as conn:
                citation_id = _seed_artefact_citation(
                    conn,
                    project_id=project_id,
                    chunks=(content,),
                    quote='the report found "clear evidence" across studies.',
                    cite_sequence=0,
                )
            response = client.get(
                f"/api/v1/projects/{project_id}/citations/{citation_id}/context",
                headers=owner,
            )
            assert response.status_code == 200
            body = response.json()
            assert raw_span in body["context"]
            assert body["context"][body["span_start"] : body["span_end"]] == raw_span
        finally:
            if project_id is not None:
                with engine.begin() as conn:
                    delete_project_data(conn, project_id)


def test_citation_context_keeps_neighbours_as_short_edge_snippets(
    tmp_path: Path, engine: Engine
) -> None:
    """Whole adjacent chunks are not attached; only a short edge snippet is."""
    project_id: uuid.UUID | None = None
    with api_client(tmp_path) as (client, owner, _):
        try:
            project_id = uuid.UUID(create_project(client, owner))
            previous = "OFFTOPIC PREVIOUS " + ("P" * 400) + " trailing previous sentence."
            quoted = "The quoted evidence span."
            middle = ("x" * 900) + f" {quoted} " + ("y" * 900)
            following = "leading next sentence. " + ("N" * 400) + " OFFTOPIC NEXT"
            with engine.begin() as conn:
                mid_id = _seed_artefact_citation(
                    conn,
                    project_id=project_id,
                    chunks=(previous, middle, following),
                    quote=quoted,
                    cite_sequence=1,
                )
            mid = client.get(
                f"/api/v1/projects/{project_id}/citations/{mid_id}/context",
                headers=owner,
            ).json()
            assert quoted in mid["context"]
            assert mid["previous"] is None
            assert mid["next"] is None
            assert "OFFTOPIC PREVIOUS" not in (mid["context"] or "")
            assert "OFFTOPIC NEXT" not in (mid["context"] or "")

            with engine.begin() as conn:
                start_id = _seed_artefact_citation(
                    conn,
                    project_id=project_id,
                    chunks=(previous, quoted + " " + ("y" * 900), following),
                    quote=quoted,
                    cite_sequence=1,
                )
            start = client.get(
                f"/api/v1/projects/{project_id}/citations/{start_id}/context",
                headers=owner,
            ).json()
            assert start["previous"] is not None
            assert start["previous"].startswith("...")
            assert start["previous"].endswith("...")
            assert "trailing previous sentence." in start["previous"]
            assert "OFFTOPIC PREVIOUS" not in start["previous"]
            assert len(start["previous"]) <= 226

            with engine.begin() as conn:
                end_id = _seed_artefact_citation(
                    conn,
                    project_id=project_id,
                    chunks=(previous, ("x" * 900) + " " + quoted, following),
                    quote=quoted,
                    cite_sequence=1,
                )
            end = client.get(
                f"/api/v1/projects/{project_id}/citations/{end_id}/context",
                headers=owner,
            ).json()
            assert end["next"] is not None
            assert end["next"].startswith("...")
            assert end["next"].endswith("...")
            assert "leading next sentence." in end["next"]
            assert "OFFTOPIC NEXT" not in end["next"]
            assert len(end["next"]) <= 226
        finally:
            if project_id is not None:
                with engine.begin() as conn:
                    delete_project_data(conn, project_id)


def test_citation_context_starts_and_ends_on_whole_words(
    tmp_path: Path, engine: Engine
) -> None:
    """The clamped window drops partial words and wraps truncated sides with '...'."""
    project_id: uuid.UUID | None = None
    with api_client(tmp_path) as (client, owner, _):
        try:
            project_id = uuid.UUID(create_project(client, owner))
            quote = "The quoted evidence span."
            content = ("alpha " * 200) + quote + " " + ("omega " * 200)
            with engine.begin() as conn:
                citation_id = _seed_artefact_citation(
                    conn,
                    project_id=project_id,
                    chunks=(content,),
                    quote=quote,
                    cite_sequence=0,
                )
            body = client.get(
                f"/api/v1/projects/{project_id}/citations/{citation_id}/context",
                headers=owner,
            ).json()
            assert body["context"].startswith("...")
            assert body["context"].endswith("...")
            inner = body["context"].removeprefix("...").removesuffix("...")
            assert inner.startswith("alpha ")
            assert inner.endswith("omega")
            assert body["context"][body["span_start"] : body["span_end"]] == quote
        finally:
            if project_id is not None:
                with engine.begin() as conn:
                    delete_project_data(conn, project_id)
