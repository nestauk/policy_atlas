"""Demo read models: plain JSON-able projections over the live Policy Atlas schema.

Every function takes an open SQLAlchemy ``Connection`` (the caller manages the
transaction) plus a ``project_id`` and returns dicts/lists shaped per
``demo/API.md``. These are throwaway demo-branch read models — no writes, no
ORM, defensive against partially-run projects (a stage that has not executed
yet reads as ``None``/empty, never an exception).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.appraise import SCORE_LABELS
from policy_atlas.schema import (
    GROUPING_FACETS,
    addressable_unit,
    annotation,
    event_log,
    evidence_scope,
    grouping_result,
    intervention_outcome_finding,
    project_source_snapshot,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
    source_tag,
    synthesis_result,
)
from policy_atlas.schema import artefact as artefact_table
from policy_atlas.schema import block as block_table
from policy_atlas.schema import chunk as chunk_table
from policy_atlas.schema import citation as citation_table
from policy_atlas.screen import effective_screen_rows

# --- Shared metadata projections (acquire's envelope shape; see acquire.py mappers) ---


def _source_title(metadata: dict[str, Any], source_locator: str) -> str:
    title = metadata.get("title")
    return title if isinstance(title, str) and title else source_locator


def _source_year(metadata: dict[str, Any]) -> int | None:
    year = metadata.get("publication_year")
    if year is None:
        year = metadata.get("year")
    return year if isinstance(year, int) and not isinstance(year, bool) else None


def _source_venue(metadata: dict[str, Any]) -> str:
    venue = metadata.get("venue") or metadata.get("journal") or ""
    return venue if isinstance(venue, str) else ""


def _source_url(metadata: dict[str, Any]) -> str | None:
    url = metadata.get("landing_page_url") or metadata.get("doi")
    return url if isinstance(url, str) and url else None


def _origin_label(pss_origin: str, metadata: dict[str, Any]) -> str:
    if pss_origin == "uploaded":
        return "Uploaded"
    backend = metadata.get("backend")
    if backend == "openalex":
        return "OpenAlex"
    if backend == "overton":
        return "Overton"
    return "Acquired"


# --- Shared "latest row for project" lookups ---


def _latest_synthesis(conn: Connection, project_id: uuid.UUID) -> dict[str, Any] | None:
    row = conn.execute(
        sa_select(
            synthesis_result.c.synthesis_result_id,
            synthesis_result.c.evidence_scope_id,
            synthesis_result.c.artefact_id,
            synthesis_result.c.blocks,
        )
        .where(synthesis_result.c.project_id == project_id)
        .order_by(synthesis_result.c.created_at.desc())
        .limit(1)
    ).mappings().first()
    return dict(row) if row is not None else None


def _latest_selection(conn: Connection, project_id: uuid.UUID) -> dict[str, Any] | None:
    row = conn.execute(
        sa_select(selection_result.c.selected)
        .where(selection_result.c.project_id == project_id)
        .order_by(selection_result.c.created_at.desc())
        .limit(1)
    ).mappings().first()
    return dict(row) if row is not None else None


def _selected_pss_ids(selected: Any) -> set[uuid.UUID]:
    ids: set[uuid.UUID] = set()
    if not isinstance(selected, list):
        return ids
    for item in selected:
        if not isinstance(item, dict):
            continue
        raw = item.get("pss_id")
        if not isinstance(raw, str):
            continue
        try:
            ids.add(uuid.UUID(raw))
        except ValueError:
            continue
    return ids


def _cited_source_snapshot_ids(
    conn: Connection, artefact_id: uuid.UUID
) -> set[uuid.UUID]:
    """Return distinct chunk source-snapshot ids cited anywhere in an artefact."""
    block_ids = conn.execute(
        sa_select(block_table.c.block_id).where(block_table.c.artefact_id == artefact_id)
    ).scalars().all()
    if not block_ids:
        return set()
    rows = conn.execute(
        sa_select(chunk_table.c.source_snapshot_id)
        .distinct()
        .select_from(citation_table)
        .join(annotation, annotation.c.annotation_id == citation_table.c.annotation_id)
        .join(chunk_table, chunk_table.c.chunk_id == citation_table.c.chunk_id)
        .where(annotation.c.block_id.in_(block_ids))
        .where(annotation.c.annotation_type == "citation")
    ).scalars().all()
    return set(rows)


# --- 1. funnel ---


def funnel(conn: Connection, project_id: uuid.UUID) -> dict[str, Any]:
    """Build the acquire→synthesise funnel counts for a project.

    Args:
        conn: Open connection; caller manages the transaction.
        project_id: Project to summarise.

    Returns:
        Dict with keys ``found, relevant, screened_out, quality_checked,
        read_in_full, selected, findings, cited`` per ``demo/API.md``
        ``/funnel``. ``selected``/``cited`` are ``None`` when their stage
        (select/synthesise) has not produced a row yet.
    """
    found = conn.execute(
        sa_select(func.count())
        .select_from(project_source_snapshot)
        .where(project_source_snapshot.c.project_id == project_id)
    ).scalar_one()

    effective = effective_screen_rows()
    statuses = conn.execute(
        sa_select(effective.c.status).where(effective.c.project_id == project_id)
    ).scalars().all()
    relevant = sum(1 for status in statuses if status == "relevant")
    screened_out = sum(1 for status in statuses if status == "not_relevant")

    quality_checked = conn.execute(
        sa_select(func.count())
        .select_from(source_classification_result)
        .where(source_classification_result.c.project_id == project_id)
    ).scalar_one()

    read_in_full = conn.execute(
        sa_select(func.count())
        .select_from(project_source_snapshot)
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.full_text_status == "ingested")
    ).scalar_one()

    selection_row = _latest_selection(conn, project_id)
    selected = (
        len(selection_row["selected"])
        if selection_row is not None and isinstance(selection_row["selected"], list)
        else None
    )

    findings = conn.execute(
        sa_select(func.count())
        .select_from(intervention_outcome_finding)
        .where(intervention_outcome_finding.c.project_id == project_id)
    ).scalar_one()

    synthesis_row = _latest_synthesis(conn, project_id)
    cited = (
        len(_cited_source_snapshot_ids(conn, synthesis_row["artefact_id"]))
        if synthesis_row is not None
        else None
    )

    return {
        "found": found,
        "relevant": relevant,
        "screened_out": screened_out,
        "quality_checked": quality_checked,
        "read_in_full": read_in_full,
        "selected": selected,
        "findings": findings,
        "cited": cited,
    }


# Board-legible short forms of the classify vocabulary (the long labels wreck
# the coverage strip and donut legends).
_SHORT_TYPE_LABELS = {
    "Expert Opinion and Commentary": "Expert opinion",
    "Policy Syntheses & Guidance Documents": "Policy guidance",
    "Other (Non-evidence documents)": "Other",
    "Observational Research Studies": "Observational",
    "Qualitative & Contextual Evidence": "Qualitative",
    "RCTs and Quasi-Experimental Studies": "RCT / quasi-exp",
    "Systematic Reviews & Meta-Analyses": "Systematic reviews",
    "Modelling & Simulation": "Modelling",
    "Unknown / Insufficient information": "Unknown",
}


def _shorten_types(distribution: dict[str, Any]) -> dict[str, Any]:
    return {_SHORT_TYPE_LABELS.get(k, k): v for k, v in distribution.items()}


# --- 2. landscape ---


def landscape(conn: Connection, project_id: uuid.UUID) -> dict[str, Any] | None:
    """Return the latest characterise summary for a project.

    Reads the latest ``component.completed`` event whose payload names
    ``characterise`` (the harness event, not the ``characterisation_result``
    table — see ``harness.py`` § ``_run_scope_component``).

    Args:
        conn: Open connection; caller manages the transaction.
        project_id: Project to summarise.

    Returns:
        Dict with keys ``evidence_types, years, themes, raw_coverage`` per
        ``demo/API.md`` ``/landscape``, or ``None`` if characterise has never
        completed for this project.
    """
    payloads = conn.execute(
        sa_select(event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.event_type == "component.completed")
        .order_by(event_log.c.sequence.desc())
    ).scalars().all()

    payload: dict[str, Any] | None = None
    for candidate in payloads:
        if isinstance(candidate, dict) and candidate.get("component") == "characterise":
            payload = candidate
            break
    if payload is None:
        return None

    coverage = payload.get("coverage")
    coverage = coverage if isinstance(coverage, dict) else {}
    distributions = coverage.get("distributions")
    distributions = distributions if isinstance(distributions, dict) else {}

    evidence_types = distributions.get("primary_evidence_type", {})
    if not isinstance(evidence_types, dict):
        evidence_types = {}

    years: dict[str, Any] = {}
    for key, value in distributions.items():
        if "year" in key and isinstance(value, dict):
            years = value
            break

    themes = payload.get("themes")
    themes = themes if isinstance(themes, list) else []
    themes = sorted(themes, key=lambda t: -(t.get("size") or 0) if isinstance(t, dict) else 0)

    tags = distributions.get("tags")
    return {
        "evidence_types": _shorten_types(evidence_types),
        "years": years,
        "themes": themes,
        "publication_countries": _publication_countries(conn, project_id),
        # the tag layer, by assertion provenance: {asserter: {tag: count}} —
        # screened-in set only (characterise's base)
        "tags": tags if isinstance(tags, dict) else {},
        "raw_coverage": coverage,
    }


_COUNTRY_NAMES = {
    "GB": "United Kingdom", "US": "United States", "AU": "Australia", "CA": "Canada",
    "DE": "Germany", "FR": "France", "NL": "Netherlands", "SE": "Sweden", "DK": "Denmark",
    "NO": "Norway", "IE": "Ireland", "NZ": "New Zealand", "ES": "Spain", "IT": "Italy",
    "CH": "Switzerland", "BE": "Belgium", "FI": "Finland", "JP": "Japan", "CN": "China",
    "IN": "India", "BR": "Brazil", "IGO": "International bodies",
}


def _publication_countries(conn: Connection, project_id: uuid.UUID) -> dict[str, int]:
    """Publication-country distribution over the SCREENED-IN set only.

    Publication country — where the source was published — never study
    geography (a recorded deferred extraction field). OpenAlex:
    ``provider_fields.primary_location.source.country_code``; Overton:
    ``provider_fields.source.country``. Absent fields count as nothing
    (no 'Unknown' bar — absence is not a distribution value here).
    """
    effective = effective_screen_rows()
    relevant_pss = sa_select(effective.c.project_source_snapshot_id).where(
        effective.c.project_id == project_id, effective.c.status == "relevant"
    )
    rows = conn.execute(
        sa_select(source_snapshot.c.metadata)
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_source_snapshot_id.in_(relevant_pss))
    ).scalars().all()

    counts: dict[str, int] = {}
    for metadata in rows:
        if not isinstance(metadata, dict):
            continue
        provider_fields = metadata.get("provider_fields")
        provider_fields = provider_fields if isinstance(provider_fields, dict) else {}
        raw: Any = None
        if metadata.get("backend") == "openalex":
            raw = (
                (provider_fields.get("primary_location") or {}).get("source") or {}
            ).get("country_code")
        elif metadata.get("backend") == "overton":
            raw = (provider_fields.get("source") or {}).get("country")
        if not isinstance(raw, str) or not raw:
            continue
        label = _COUNTRY_NAMES.get(raw.upper(), raw)
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1])[:12])


# --- 3. groups ---


def groups(conn: Connection, project_id: uuid.UUID) -> dict[str, Any] | None:
    """Return the latest grouping result per facet for a project.

    Args:
        conn: Open connection; caller manages the transaction.
        project_id: Project to summarise.

    Returns:
        Dict with a single ``facets`` key (list of ``{facet, groups,
        ungrouped}``) per ``demo/API.md`` ``/groups``, or ``None`` if group
        has never run for this project.
    """
    rows = conn.execute(
        sa_select(grouping_result.c.facet, grouping_result.c.groups)
        .where(grouping_result.c.project_id == project_id)
        .order_by(grouping_result.c.facet, grouping_result.c.created_at.desc())
    ).all()

    latest_by_facet: dict[str, Any] = {}
    for row in rows:
        latest_by_facet.setdefault(row.facet, row.groups)

    if not latest_by_facet:
        return None

    facets_out: list[dict[str, Any]] = []
    for facet in GROUPING_FACETS:
        if facet not in latest_by_facet:
            continue
        payload = latest_by_facet[facet]
        payload = payload if isinstance(payload, dict) else {}

        raw_groups = payload.get("groups")
        raw_groups = raw_groups if isinstance(raw_groups, list) else []
        groups_out = [
            {
                "label": group.get("label"),
                "description": group.get("description"),
                "size": group.get("size"),
            }
            for group in raw_groups
            if isinstance(group, dict)
        ]

        ungrouped = payload.get("ungrouped")
        ungrouped = ungrouped if isinstance(ungrouped, dict) else {}
        no_value = payload.get("no_value")
        no_value = no_value if isinstance(no_value, dict) else {}
        ungrouped_finding_ids = ungrouped.get("finding_ids")
        no_value_finding_ids = no_value.get("finding_ids")
        ungrouped_count = (
            len(ungrouped_finding_ids) if isinstance(ungrouped_finding_ids, list) else 0
        ) + (len(no_value_finding_ids) if isinstance(no_value_finding_ids, list) else 0)

        facets_out.append({"facet": facet, "groups": groups_out, "ungrouped": ungrouped_count})

    return {"facets": facets_out}


# --- 4. evidence_table ---


def evidence_table(conn: Connection, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """Build the per-source evidence table for a project.

    One row per ``project_source_snapshot``, bulk-assembled (no per-row
    N+1): the base rows, effective screening, classification, appraisal,
    extraction and selection/citation state are each fetched once and joined
    in Python.

    Args:
        conn: Open connection; caller manages the transaction.
        project_id: Project to summarise.

    Returns:
        List of dicts per ``demo/API.md`` ``/evidence``.
    """
    base_rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.origin,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .select_from(project_source_snapshot)
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == project_source_snapshot.c.source_snapshot_id,
        )
        .where(project_source_snapshot.c.project_id == project_id)
    ).all()
    if not base_rows:
        return []

    # Effective screening: latest (by screened_at) effective row per pss, across
    # whatever evidence scopes this project has run.
    effective = effective_screen_rows()
    screen_by_pss: dict[uuid.UUID, tuple[str, str | None, float | None, int | None]] = {}
    latest_screened_at: dict[uuid.UUID, Any] = {}
    for row in conn.execute(
        sa_select(
            effective.c.project_source_snapshot_id,
            effective.c.status,
            effective.c.screen_basis,
            effective.c.screen_decision_confidence,
            effective.c.screen_stage,
            effective.c.screened_at,
        ).where(effective.c.project_id == project_id)
    ):
        pss_id = row.project_source_snapshot_id
        if pss_id not in latest_screened_at or row.screened_at > latest_screened_at[pss_id]:
            latest_screened_at[pss_id] = row.screened_at
            screen_by_pss[pss_id] = (
                row.status, row.screen_basis,
                row.screen_decision_confidence, row.screen_stage,
            )

    # Classification: latest (by classified_at) primary_evidence_type per pss.
    evidence_type_by_pss: dict[uuid.UUID, str] = {}
    latest_classified_at: dict[uuid.UUID, Any] = {}
    for row in conn.execute(
        sa_select(
            source_classification_result.c.project_source_snapshot_id,
            source_classification_result.c.primary_evidence_type,
            source_classification_result.c.classified_at,
        ).where(source_classification_result.c.project_id == project_id)
    ):
        pss_id = row.project_source_snapshot_id
        if pss_id not in latest_classified_at or row.classified_at > latest_classified_at[pss_id]:
            latest_classified_at[pss_id] = row.classified_at
            evidence_type_by_pss[pss_id] = row.primary_evidence_type

    # Appraisal: latest (by appraised_at) quality_score per pss.
    quality_by_pss: dict[uuid.UUID, int] = {}
    latest_appraised_at: dict[uuid.UUID, Any] = {}
    for row in conn.execute(
        sa_select(
            source_appraisal_result.c.project_source_snapshot_id,
            source_appraisal_result.c.quality_score,
            source_appraisal_result.c.appraised_at,
        ).where(source_appraisal_result.c.project_id == project_id)
    ):
        pss_id = row.project_source_snapshot_id
        if pss_id not in latest_appraised_at or row.appraised_at > latest_appraised_at[pss_id]:
            latest_appraised_at[pss_id] = row.appraised_at
            quality_by_pss[pss_id] = row.quality_score

    # Extraction: pss ids with at least one extraction record carrying findings
    # (source_extraction_record.finding_count is the maintained finding count
    # for the intervention_outcome_finding rows linked via extraction_record_id).
    findings_extracted_pss_ids: set[uuid.UUID] = set()
    for row in conn.execute(
        sa_select(
            source_extraction_record.c.project_source_snapshot_id,
            func.max(source_extraction_record.c.finding_count).label("max_finding_count"),
        )
        .where(source_extraction_record.c.project_id == project_id)
        .group_by(source_extraction_record.c.project_source_snapshot_id)
    ):
        if row.max_finding_count and row.max_finding_count > 0:
            findings_extracted_pss_ids.add(row.project_source_snapshot_id)

    # Selection: latest selection_result for the project.
    selection_row = _latest_selection(conn, project_id)
    selection_exists = selection_row is not None
    selected_pss_ids = _selected_pss_ids(
        selection_row["selected"] if selection_row is not None else None
    )

    # Citations: which source snapshots (envelope or full-text) are cited in the
    # latest artefact, mapped back onto their owning pss.
    synthesis_row = _latest_synthesis(conn, project_id)
    snapshot_to_pss: dict[uuid.UUID, uuid.UUID] = {}
    for row in base_rows:
        snapshot_to_pss[row.source_snapshot_id] = row.project_source_snapshot_id
        if row.full_text_snapshot_id is not None:
            snapshot_to_pss[row.full_text_snapshot_id] = row.project_source_snapshot_id
    cited_pss_ids: set[uuid.UUID] = set()
    if synthesis_row is not None:
        cited_snapshot_ids = _cited_source_snapshot_ids(conn, synthesis_row["artefact_id"])
        cited_pss_ids = {
            snapshot_to_pss[snapshot_id]
            for snapshot_id in cited_snapshot_ids
            if snapshot_id in snapshot_to_pss
        }

    out: list[dict[str, Any]] = []
    for row in base_rows:
        pss_id = row.project_source_snapshot_id
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        screen_status, screen_basis, screen_confidence, screen_stage = screen_by_pss.get(
            pss_id, (None, None, None, None)
        )
        source_id = str(pss_id)  # stable join key for the source detail panel

        status: str
        status_reason: str | None = None
        if pss_id in cited_pss_ids:
            status = "cited"
        elif pss_id in findings_extracted_pss_ids:
            status = "findings_extracted"
        elif pss_id in selected_pss_ids:
            status = "selected"
        elif row.full_text_status == "ingested":
            status = "read_in_full"
        elif (
            row.full_text_status in ("fetch_failed", "parse_failed")
            and screen_status == "relevant"
        ):
            status = "unavailable"
            status_reason = row.full_text_error
        elif screen_status == "relevant":
            not_selected = selection_exists and pss_id not in selected_pss_ids
            status = "not_selected" if not_selected else "relevant"
        elif screen_status == "not_relevant":
            status = "screened_out"
            status_reason = screen_basis
        else:
            status = "found"

        quality_score = quality_by_pss.get(pss_id)
        out.append(
            {
                "source_id": source_id,
                "title": _source_title(metadata, row.source_locator),
                "year": _source_year(metadata),
                "venue": _source_venue(metadata),
                "origin": _origin_label(row.origin, metadata),
                "status": status,
                "status_reason": status_reason,
                "evidence_type": evidence_type_by_pss.get(pss_id),
                "appraisal_tier": str(quality_score) if quality_score is not None else None,
                # the user sees the rubric LABEL, never the raw score
                "appraisal_label": SCORE_LABELS.get(quality_score)
                if quality_score is not None
                else None,
                "cited": pss_id in cited_pss_ids,
                "url": _source_url(metadata),
                # Hover-detail fields: the sift's own confidence + how far it read.
                "screen_confidence": screen_confidence,
                "screen_basis": screen_basis,
                "screen_stage": screen_stage,
            }
        )
    return out


# --- 5. artefact ---


def artefact(conn: Connection, project_id: uuid.UUID) -> dict[str, Any] | None:
    """Build the evidence-base artefact view for a project.

    Args:
        conn: Open connection; caller manages the transaction.
        project_id: Project to summarise.

    Returns:
        Dict per ``demo/API.md`` ``/artefact``, or ``None`` if synthesise
        has never produced a ``synthesis_result`` row for this project.
    """
    synthesis_row = _latest_synthesis(conn, project_id)
    if synthesis_row is None:
        return None

    artefact_id = synthesis_row["artefact_id"]
    evidence_scope_id = synthesis_row["evidence_scope_id"]

    artefact_row = conn.execute(
        sa_select(artefact_table.c.title).where(artefact_table.c.artefact_id == artefact_id)
    ).mappings().first()
    title = artefact_row["title"] if artefact_row is not None else ""

    question_row = conn.execute(
        sa_select(evidence_scope.c.intent)
        .where(evidence_scope.c.project_id == project_id)
        .order_by(evidence_scope.c.created_at.desc())
        .limit(1)
    ).first()
    question = question_row.intent if question_row is not None else ""

    blocks_payload = synthesis_row.get("blocks")
    blocks_payload = blocks_payload if isinstance(blocks_payload, list) else []
    section_specs = [
        block
        for block in blocks_payload
        if isinstance(block, dict) and isinstance(block.get("block_id"), str)
    ]
    block_ids = [uuid.UUID(section["block_id"]) for section in section_specs]
    block_order = {block_id: index for index, block_id in enumerate(block_ids)}

    prose_by_block: dict[uuid.UUID, str] = {}
    if block_ids:
        for row in conn.execute(
            sa_select(block_table.c.block_id, block_table.c.content).where(
                block_table.c.block_id.in_(block_ids)
            )
        ):
            prose_by_block[row.block_id] = row.content

    # ALL annotation types for these blocks, in claim order (the addressable
    # unit's locator.start tracks claim emission order within _write_section).
    # citation | pattern | theme | gap | reasoning — every one is a prose span;
    # the annotation layer is rendered IN the prose, typed.
    citation_annotations: list[dict[str, Any]] = []
    if block_ids:
        for row in conn.execute(
            sa_select(
                annotation.c.annotation_id,
                annotation.c.block_id,
                annotation.c.unit_id,
                annotation.c.annotation_type,
                annotation.c.payload,
                addressable_unit.c.locator,
                addressable_unit.c.content,
            )
            .select_from(annotation)
            .join(
                addressable_unit,
                (addressable_unit.c.block_id == annotation.c.block_id)
                & (addressable_unit.c.unit_id == annotation.c.unit_id),
            )
            .where(annotation.c.block_id.in_(block_ids))
        ):
            locator = row.locator if isinstance(row.locator, dict) else {}
            start = locator.get("start", 0)
            start = start if isinstance(start, int) else 0
            end = locator.get("end")
            citation_annotations.append(
                {
                    "annotation_id": row.annotation_id,
                    "block_id": row.block_id,
                    "unit_id": row.unit_id,
                    "annotation_type": row.annotation_type,
                    "claim_text": row.content,
                    "payload": row.payload if isinstance(row.payload, dict) else {},
                    "start": start,
                    "end": end if isinstance(end, int) else None,
                }
            )
    citation_annotations.sort(
        key=lambda entry: (block_order.get(entry["block_id"], 10_000), entry["start"])
    )

    annotation_ids = [entry["annotation_id"] for entry in citation_annotations]
    citation_rows_by_annotation: dict[uuid.UUID, list[dict[str, Any]]] = {}
    if annotation_ids:
        for row in conn.execute(
            sa_select(
                citation_table.c.citation_id,
                citation_table.c.annotation_id,
                citation_table.c.chunk_id,
                citation_table.c.quote,
                citation_table.c.verification_result,
            ).where(citation_table.c.annotation_id.in_(annotation_ids))
        ):
            citation_rows_by_annotation.setdefault(row.annotation_id, []).append(
                {
                    "citation_id": row.citation_id,
                    "chunk_id": row.chunk_id,
                    "quote": row.quote,
                    "verified": row.verification_result == "pass",
                }
            )

    chunk_ids = {
        citation["chunk_id"]
        for rows in citation_rows_by_annotation.values()
        for citation in rows
    }
    snapshot_by_chunk: dict[uuid.UUID, uuid.UUID] = {}
    if chunk_ids:
        for row in conn.execute(
            sa_select(chunk_table.c.chunk_id, chunk_table.c.source_snapshot_id).where(
                chunk_table.c.chunk_id.in_(chunk_ids)
            )
        ):
            snapshot_by_chunk[row.chunk_id] = row.source_snapshot_id

    snapshot_ids = set(snapshot_by_chunk.values())
    snapshot_meta: dict[uuid.UUID, dict[str, Any]] = {}
    if snapshot_ids:
        for row in conn.execute(
            sa_select(
                source_snapshot.c.source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            ).where(source_snapshot.c.source_snapshot_id.in_(snapshot_ids))
        ):
            metadata = row.metadata if isinstance(row.metadata, dict) else {}
            snapshot_meta[row.source_snapshot_id] = {
                "title": _source_title(metadata, row.source_locator),
                "year": _source_year(metadata),
                "venue": _source_venue(metadata),
                "url": _source_url(metadata),
            }

    # Map cited snapshots back to their owning pss (envelope or full-text
    # snapshot id) so citations can carry an appraisal tier — and so references
    # can resolve document metadata: a FULL-TEXT snapshot carries no title, so
    # its reference entry must read from the owning source's ENVELOPE snapshot
    # (otherwise references render as bare URLs with no year/venue).
    pss_rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
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
    snapshot_to_pss: dict[uuid.UUID, uuid.UUID] = {}
    for row in pss_rows:
        snapshot_to_pss[row.source_snapshot_id] = row.project_source_snapshot_id
        if row.full_text_snapshot_id is not None:
            snapshot_to_pss[row.full_text_snapshot_id] = row.project_source_snapshot_id
        envelope_metadata = row.metadata if isinstance(row.metadata, dict) else {}
        envelope = {
            "title": _source_title(envelope_metadata, row.source_locator),
            "year": _source_year(envelope_metadata),
            "venue": _source_venue(envelope_metadata),
            "url": _source_url(envelope_metadata),
        }
        for snapshot_id in (row.source_snapshot_id, row.full_text_snapshot_id):
            if snapshot_id is None or snapshot_id not in snapshot_meta:
                continue
            own = snapshot_meta[snapshot_id]
            own_title = own.get("title") or ""
            if own_title.startswith(("http://", "https://")) or not own_title:
                snapshot_meta[snapshot_id] = {**own, **{
                    k: v for k, v in envelope.items() if v not in (None, "")
                }}

    quality_by_pss: dict[uuid.UUID, int] = {}
    if snapshot_to_pss:
        for row in conn.execute(
            sa_select(
                source_appraisal_result.c.project_source_snapshot_id,
                source_appraisal_result.c.quality_score,
            )
            .where(source_appraisal_result.c.project_id == project_id)
            .where(source_appraisal_result.c.evidence_scope_id == evidence_scope_id)
        ):
            quality_by_pss[row.project_source_snapshot_id] = row.quality_score

    # Build claims per block (one annotation = one claim span, in claim-emission
    # order) and the reference table (numbered by first appearance of each
    # distinct cited snapshot).
    claims_by_block: dict[uuid.UUID, list[dict[str, Any]]] = {
        block_id: [] for block_id in block_ids
    }
    reference_numbers: dict[uuid.UUID, int] = {}
    reference_order: list[uuid.UUID] = []
    for entry in citation_annotations:
        payload = entry["payload"]
        grounding_tier = payload.get("verdict")
        claim_citations: list[dict[str, Any]] = []
        seen_refs: set[int] = set()
        for citation in citation_rows_by_annotation.get(entry["annotation_id"], []):
            snapshot_id = snapshot_by_chunk.get(citation["chunk_id"])
            if snapshot_id is None:
                continue
            meta = snapshot_meta.get(snapshot_id, {"title": "Unknown source"})
            if snapshot_id not in reference_numbers:
                reference_numbers[snapshot_id] = len(reference_order) + 1
                reference_order.append(snapshot_id)
            n = reference_numbers[snapshot_id]
            if n in seen_refs:
                continue  # one citation per distinct source per claim
            seen_refs.add(n)
            source_pss_id = snapshot_to_pss.get(snapshot_id)
            quality_score = quality_by_pss.get(source_pss_id) if source_pss_id else None
            claim_citations.append(
                {
                    "n": n,
                    "source_title": meta.get("title", "Unknown source"),
                    "quote": citation["quote"],
                    "verified": citation["verified"],
                    "grounding_tier": grounding_tier,
                    "appraisal_label": SCORE_LABELS.get(quality_score)
                    if quality_score is not None
                    else None,
                    # for the quote-in-context panel
                    "chunk_id": str(citation["chunk_id"]),
                }
            )
        claim_type = str(entry["annotation_type"])
        if claim_type not in {
            "citation",
            "gap",
            "reasoning",
            "pattern",
            "theme",
            "unspanned_assertion",
        }:
            claim_type = "reasoning"
        claims_by_block[entry["block_id"]].append(
            {
                "claim_id": str(entry["unit_id"]),
                # citation | gap | reasoning | pattern | theme | unspanned_assertion
                # drives rendering.
                "claim_type": claim_type,
                "text": entry["claim_text"],
                # Char offsets into the block prose — the claim IS a span of the
                # text, so citation chips anchor inline at span end.
                "span": {"start": entry["start"], "end": entry["end"]},
                "citations": claim_citations,
            }
        )

    sections: list[dict[str, Any]] = []
    key_findings_blocks: list[dict[str, Any]] = []
    conclusion_blocks: list[dict[str, Any]] = []
    for section in section_specs:
        block_id = uuid.UUID(section["block_id"])
        block = {
            "block_id": section["block_id"],
            "prose": prose_by_block.get(block_id, ""),
            "claims": claims_by_block.get(block_id, []),
            "gaps": [],
        }
        if not block["prose"].strip() and not block["claims"]:
            continue

        role = _block_role(section)
        if role == "key_findings":
            key_findings_blocks.append(block)
        elif role == "conclusions":
            conclusion_blocks.append(block)
        else:
            sections.append(
                {
                    "title": section.get("title", ""),
                    "role": role,
                    "blocks": [block],
                }
            )

    references = [
        {
            "n": reference_numbers[snapshot_id],
            "title": snapshot_meta.get(snapshot_id, {}).get("title", "Unknown source"),
            "year": snapshot_meta.get(snapshot_id, {}).get("year"),
            "venue": snapshot_meta.get(snapshot_id, {}).get("venue"),
            "url": snapshot_meta.get(snapshot_id, {}).get("url"),
        }
        for snapshot_id in reference_order
    ]

    # Coverage snapshot: classification counts and effective screen counts for
    # the artefact's own evidence scope; year range over the reference list.
    study_types: dict[str, int] = {}
    for row in conn.execute(
        sa_select(
            source_classification_result.c.primary_evidence_type, func.count()
        )
        .where(source_classification_result.c.project_id == project_id)
        .where(source_classification_result.c.evidence_scope_id == evidence_scope_id)
        .group_by(source_classification_result.c.primary_evidence_type)
    ):
        study_types[_SHORT_TYPE_LABELS.get(row[0], row[0])] = row[1]

    years = [reference["year"] for reference in references if reference["year"] is not None]
    year_range = {"min": min(years), "max": max(years)} if years else None

    effective = effective_screen_rows()
    scope_statuses = conn.execute(
        sa_select(effective.c.status)
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == evidence_scope_id)
    ).scalars().all()
    included = sum(1 for status in scope_statuses if status == "relevant")
    screened_out = sum(1 for status in scope_statuses if status == "not_relevant")

    return {
        "title": title,
        "question": question,
        "coverage_snapshot": {
            "source_count": len(references),
            "study_types": study_types,
            "year_range": year_range,
            "included": included,
            "screened_out": screened_out,
        },
        "key_findings": {
            "title": "Key findings",
            "blocks": key_findings_blocks,
        } if key_findings_blocks else None,
        "sections": sections,
        "conclusion": {
            "title": "Conclusions",
            "blocks": conclusion_blocks,
        } if conclusion_blocks else None,
        "references": references,
    }


def _block_role(section: dict[str, Any]) -> str:
    """Return the synthesis v2 role for a block roll-up.

    Args:
        section: One entry from ``synthesis_result.blocks``.

    Returns:
        ``key_findings``, ``conclusions`` or ``standard``. Older seeded
        projects did not carry roles, so title-based inference keeps them
        renderable.
    """
    role = section.get("role")
    if role in ("key_findings", "conclusions", "standard"):
        return role
    title = section.get("title")
    if isinstance(title, str):
        normalised = title.strip().lower().replace("-", " ")
        if normalised == "key findings":
            return "key_findings"
        if normalised in ("conclusion", "conclusions"):
            return "conclusions"
    return "standard"


# --- 6. findings (the task-011 findings layer) ---


def findings(conn: Connection, project_id: uuid.UUID, cap: int = 200) -> list[dict[str, Any]]:
    """Extracted intervention→outcome findings with their verified anchors.

    Args:
        conn: Open connection; caller manages the transaction.
        project_id: Project to read.
        cap: Maximum rows returned (newest extraction records first).

    Returns:
        One dict per finding: intervention, outcome, direction, design,
        population, headline statistic, verbatim anchor quote + verification,
        and the owning source title.
    """
    rows = conn.execute(
        sa_select(
            intervention_outcome_finding.c.finding_id,
            intervention_outcome_finding.c.intervention,
            intervention_outcome_finding.c.outcome,
            intervention_outcome_finding.c.effect_direction,
            intervention_outcome_finding.c.population,
            intervention_outcome_finding.c.comparator,
            intervention_outcome_finding.c.study_design,
            intervention_outcome_finding.c.estimate_level,
            intervention_outcome_finding.c.causality_by_design,
            intervention_outcome_finding.c.effect_basis,
            intervention_outcome_finding.c.study_geography,
            intervention_outcome_finding.c.is_primary,
            intervention_outcome_finding.c.stratum_qualifiers,
            intervention_outcome_finding.c.statistics,
            intervention_outcome_finding.c.grounding,
            intervention_outcome_finding.c.created_at,
            source_extraction_record.c.project_source_snapshot_id,
        )
        .select_from(
            intervention_outcome_finding.join(
                source_extraction_record,
                intervention_outcome_finding.c.extraction_record_id
                == source_extraction_record.c.extraction_record_id,
            )
        )
        .where(intervention_outcome_finding.c.project_id == project_id)
        .order_by(intervention_outcome_finding.c.created_at.desc())
        .limit(cap)
    ).fetchall()

    pss_ids = {row.project_source_snapshot_id for row in rows}
    titles: dict[uuid.UUID, str] = {}
    if pss_ids:
        for pss_row in conn.execute(
            sa_select(
                project_source_snapshot.c.project_source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(
                project_source_snapshot.join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(project_source_snapshot.c.project_source_snapshot_id.in_(pss_ids))
        ):
            metadata = pss_row.metadata if isinstance(pss_row.metadata, dict) else {}
            titles[pss_row.project_source_snapshot_id] = _source_title(
                metadata, pss_row.source_locator
            )

    group_labels = _finding_group_labels(conn, project_id)

    out: list[dict[str, Any]] = []
    for row in rows:
        grounding = row.grounding if isinstance(row.grounding, list) else []
        anchor = next((g for g in grounding if isinstance(g, dict) and g.get("quote")), {})
        statistics = row.statistics if isinstance(row.statistics, dict) else {}
        qualifiers = row.stratum_qualifiers if isinstance(row.stratum_qualifiers, list) else []
        out.append(
            {
                "finding_id": str(row.finding_id),
                "source_id": str(row.project_source_snapshot_id),
                "intervention": row.intervention,
                "outcome": row.outcome,
                "direction": row.effect_direction,
                "population": row.population,
                "comparator": row.comparator,
                "study_design": row.study_design,
                "estimate_level": row.estimate_level,
                "causality": row.causality_by_design,
                # 020 extraction schema v2 — nullable, absent on pre-v2 rows
                "effect_basis": row.effect_basis,
                "study_geography": row.study_geography,
                "is_primary": row.is_primary,
                # reported-only values: effect size + type, CI/SE, p, N, k, I², τ²
                "statistics": statistics,
                "statistic": statistics.get("effect_size") or statistics.get("p_value"),
                "stratum_qualifiers": qualifiers,
                "quote": anchor.get("quote"),
                "quote_verified": anchor.get("match") in ("exact", "normalized", "verified"),
                "source_title": titles.get(row.project_source_snapshot_id, "Unknown source"),
                # facet-group membership from the latest grouping run, e.g.
                # {"intervention": "Sugar levy / fiscal", "outcome": "Dietary intake"}
                "groups": group_labels.get(str(row.finding_id), {}),
            }
        )
    return out


def _finding_group_labels(
    conn: Connection, project_id: uuid.UUID
) -> dict[str, dict[str, str]]:
    """finding_id → {facet: group label} from the latest grouping run per facet."""
    labels: dict[str, dict[str, str]] = {}
    for facet in GROUPING_FACETS:
        row = conn.execute(
            sa_select(grouping_result.c.groups)
            .where(grouping_result.c.project_id == project_id)
            .where(grouping_result.c.facet == facet)
            .order_by(grouping_result.c.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        groups_obj = row if isinstance(row, dict) else {}
        group_list = groups_obj.get("groups")
        if not isinstance(group_list, list):
            continue
        for group in group_list:
            if not isinstance(group, dict):
                continue
            label = group.get("label")
            member_ids = group.get("member_finding_ids")
            if not isinstance(label, str) or not isinstance(member_ids, list):
                continue
            for finding_id in member_ids:
                labels.setdefault(str(finding_id), {})[facet] = label
    return labels


# --- 7. decision log (projection over the canonical event log) ---

_LOG_LABELS = {
    "acquire": "Search completed",
    "screen": "Screening completed",
    "classify": "Evidence types assigned",
    "appraise": "Quality appraisal completed",
    "ingest_full_text": "Full documents read",
    "characterise": "Landscape mapped",
    "select": "Close-reading shortlist chosen",
    "extract": "Findings extracted",
    "group": "Findings grouped",
    "synthesise": "Evidence base written",
}


def decision_log(conn: Connection, project_id: uuid.UUID) -> list[dict[str, Any]]:
    """The project's audit trail, readable: every run, stage and outcome.

    Every entry comes from the canonical event log — nothing is reconstructed.
    """
    entries: list[dict[str, Any]] = []
    for row in conn.execute(
        sa_select(
            event_log.c.event_type,
            event_log.c.payload,
            event_log.c.occurred_at,
            event_log.c.sequence,
        )
        .where(event_log.c.project_id == project_id)
        .order_by(event_log.c.sequence)
    ):
        payload = row.payload if isinstance(row.payload, dict) else {}
        component = payload.get("component")
        if row.event_type == "component.completed":
            counts = {
                k: v for k, v in payload.items()
                if isinstance(v, (int, float)) and k != "component"
            }
            summary = " · ".join(f"{k.replace('_', ' ')} {v}" for k, v in list(counts.items())[:4])
            text = _LOG_LABELS.get(component, component or "step")
            if summary:
                text = f"{text} — {summary}"
        elif row.event_type == "component.failed":
            text = f"{_LOG_LABELS.get(component, component or 'step')} — failed: " \
                f"{payload.get('error', 'see logs')}"
        else:
            continue  # run.started etc. add noise, not information
        detail = _decision_detail(payload)
        entries.append(
            {
                "at": row.occurred_at.isoformat(),
                "kind": row.event_type,
                "text": text,
                # the full flattened payload for the expandable row
                "detail": detail,
            }
        )
    return entries


# --- 8. search coverage (the honest-search record) ---


def coverage(conn: Connection, project_id: uuid.UUID) -> dict[str, Any] | None:
    """The latest search coverage record: where we looked and why we stopped."""
    row = conn.execute(
        sa_select(
            search_coverage_record.c.backends,
            search_coverage_record.c.stop_condition,
            search_coverage_record.c.adequacy_verdict,
            search_coverage_record.c.verdict_origin,
            search_coverage_record.c.created_at,
        )
        .where(search_coverage_record.c.project_id == project_id)
        .order_by(search_coverage_record.c.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    backends = row.backends if isinstance(row.backends, list) else []
    stop_texts = {
        "target_reached": "found enough confidently relevant sources",
        "short_circuit": "new searches stopped finding anything new",
        "budget_exhausted": "the search budget was spent",
        "breadth_truncated": "the breadth limit was reached",
        "re_searched_still_thin": "searched again and the base is still thin",
        "error": "the search hit an error",
    }
    stop_text = stop_texts.get(row.stop_condition, row.stop_condition)
    # One coherent sentence — stop reason and adequacy verdict read together,
    # so "found enough…" never sits beside a bare "inadequate".
    if row.adequacy_verdict == "adequate":
        summary = f"Searching stopped because {stop_text}. Coverage judged adequate."
    else:
        summary = (
            f"Searching stopped because {stop_text}, but the analysis still judges "
            "coverage thin — recorded, not hidden."
        )
    return {
        "backends": [b.get("backend", "?") for b in backends if isinstance(b, dict)],
        "stop_condition": row.stop_condition,
        "stop_text": stop_texts.get(row.stop_condition, row.stop_condition),
        "summary": summary,
        "adequacy": row.adequacy_verdict,
        "verdict_origin": row.verdict_origin,
    }


# --- 9. chunk context (the V2 quote-in-context panel, over frozen chunks) ---


def chunk_context(
    conn: Connection, project_id: uuid.UUID, chunk_id: uuid.UUID
) -> dict[str, Any] | None:
    """A cited chunk with its neighbours, for the quote-in-context panel.

    Chunks are the frozen content of record; ``(source_snapshot_id, sequence)``
    is unique, so the neighbours are simply sequence ± 1.
    """
    row = conn.execute(
        sa_select(
            chunk_table.c.content,
            chunk_table.c.sequence,
            chunk_table.c.source_snapshot_id,
        ).where(chunk_table.c.chunk_id == chunk_id)
    ).first()
    if row is None:
        return None
    # scope guard: the chunk's snapshot must belong to this project
    owned = conn.execute(
        sa_select(func.count())
        .select_from(project_source_snapshot)
        .where(project_source_snapshot.c.project_id == project_id)
        .where(
            (project_source_snapshot.c.source_snapshot_id == row.source_snapshot_id)
            | (project_source_snapshot.c.full_text_snapshot_id == row.source_snapshot_id)
        )
    ).scalar_one()
    if not owned:
        return None

    neighbours = {
        n_row.sequence: n_row.content
        for n_row in conn.execute(
            sa_select(chunk_table.c.sequence, chunk_table.c.content)
            .where(chunk_table.c.source_snapshot_id == row.source_snapshot_id)
            .where(chunk_table.c.sequence.in_([row.sequence - 1, row.sequence + 1]))
        )
    }
    meta_row = conn.execute(
        sa_select(source_snapshot.c.metadata, source_snapshot.c.source_locator).where(
            source_snapshot.c.source_snapshot_id == row.source_snapshot_id
        )
    ).first()
    metadata = meta_row.metadata if meta_row and isinstance(meta_row.metadata, dict) else {}
    return {
        "previous": neighbours.get(row.sequence - 1),
        "content": row.content,
        "next": neighbours.get(row.sequence + 1),
        "source_title": _source_title(metadata, meta_row.source_locator if meta_row else ""),
        "year": _source_year(metadata),
        "venue": _source_venue(metadata),
    }


# --- 10. source detail (the full per-source dossier for the slide-over) ---


def source_detail(
    conn: Connection, project_id: uuid.UUID, source_id: uuid.UUID
) -> dict[str, Any] | None:
    """Everything the backend knows about one source, panel-shaped.

    The evidence-table row (status ladder + hover fields) plus the richer
    envelope metadata, the tag layer with assertion provenance, and — when the
    source is cited — the artefact claims resting on it.
    """
    row = next(
        (r for r in evidence_table(conn, project_id) if r["source_id"] == str(source_id)),
        None,
    )
    if row is None:
        return None

    meta_row = conn.execute(
        sa_select(
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
            source_snapshot.c.metadata,
        )
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_source_snapshot_id == source_id)
        .where(project_source_snapshot.c.project_id == project_id)
    ).first()
    metadata = meta_row.metadata if meta_row and isinstance(meta_row.metadata, dict) else {}
    provider_fields = metadata.get("provider_fields")
    provider_fields = provider_fields if isinstance(provider_fields, dict) else {}

    abstract = metadata.get("abstract")
    envelope = {
        "abstract": abstract if isinstance(abstract, str) else None,
        "abstract_source": metadata.get("abstract_source"),
        "doi": metadata.get("doi"),
        "language": metadata.get("language"),
        "publisher_org": metadata.get("publisher_org"),
        "record_type": metadata.get("record_type"),
        "cited_by_count": provider_fields.get("cited_by_count")
        or provider_fields.get("citation_count"),
        "fwci": provider_fields.get("fwci"),
        "indexed_in": provider_fields.get("indexed_in"),
    }

    tag_rows = conn.execute(
        sa_select(source_tag.c.tag, source_tag.c.tag_type, source_tag.c.asserted_by)
        .where(source_tag.c.project_id == project_id)
        .where(source_tag.c.project_source_snapshot_id == source_id)
        .order_by(source_tag.c.asserted_by, source_tag.c.tag)
    ).fetchall()
    tags = [
        {"tag": t.tag, "tag_type": t.tag_type, "asserted_by": t.asserted_by}
        for t in tag_rows
    ]

    # Claims in the latest artefact citing this source (envelope or full-text
    # snapshot), each with its quote and owning section.
    cited_claims: list[dict[str, Any]] = []
    synthesis_row = _latest_synthesis(conn, project_id)
    if synthesis_row is not None and meta_row is not None:
        own_snapshots = {meta_row.source_snapshot_id}
        if meta_row.full_text_snapshot_id is not None:
            own_snapshots.add(meta_row.full_text_snapshot_id)
        section_by_block: dict[str, str] = {}
        blocks_rollup = synthesis_row.get("blocks")
        if isinstance(blocks_rollup, list):
            for section in blocks_rollup:
                if isinstance(section, dict) and section.get("block_id"):
                    section_by_block[str(section["block_id"])] = (
                        section.get("title") or section.get("focus") or ""
                    )
        block_ids = [uuid.UUID(b) for b in section_by_block]
        if block_ids:
            for claim_row in conn.execute(
                sa_select(
                    addressable_unit.c.content,
                    annotation.c.block_id,
                    citation_table.c.quote,
                    citation_table.c.verification_result,
                )
                .select_from(citation_table)
                .join(annotation, annotation.c.annotation_id == citation_table.c.annotation_id)
                .join(
                    addressable_unit,
                    (addressable_unit.c.block_id == annotation.c.block_id)
                    & (addressable_unit.c.unit_id == annotation.c.unit_id),
                )
                .join(chunk_table, chunk_table.c.chunk_id == citation_table.c.chunk_id)
                .where(annotation.c.block_id.in_(block_ids))
                .where(chunk_table.c.source_snapshot_id.in_(own_snapshots))
            ):
                cited_claims.append(
                    {
                        "claim": claim_row.content,
                        "quote": claim_row.quote,
                        "verified": claim_row.verification_result == "pass",
                        "section": section_by_block.get(str(claim_row.block_id), ""),
                    }
                )

    return {**row, **envelope, "tags": tags, "cited_claims": cited_claims}


# User-facing decision detail: an allowlist of payload numbers with plain labels.
# Everything else in a component payload is internal and never shown.
_DECISION_DETAIL_LABELS: dict[str, str] = {
    "acquired": "New sources found",
    "results_returned": "Results returned by the databases",
    "already_acquired": "Already in the project",
    "relevant": "Judged relevant",
    "not_relevant": "Screened out",
    "screen_failed": "Could not be screened",
    "classified": "Sources labelled by evidence type",
    "appraised": "Sources quality-appraised",
    "ingested": "Read in full",
    "fetch_failed": "Could not be fetched",
    "parse_failed": "Fetched but unreadable",
    "selected": "Shortlisted for close reading",
    "extracted": "Documents with findings",
    "no_findings": "Documents with nothing to extract",
    "failed": "Extraction failures",
    "total": "Findings extracted",
    "quote_unverified": "Quotes that could not be verified",
    "section_count": "Sections written",
    "themes": "Themes identified",
    "groups": "Groups formed",
    "openalex": "Queries run · OpenAlex",
    "overton": "Queries run · Overton",
}

_DECISION_STOP_TEXTS = {
    "target_reached": "Stopped: found enough confidently relevant sources",
    "short_circuit": "Stopped: new searches found nothing new",
    "budget_exhausted": "Stopped: search budget spent",
    "breadth_truncated": "Stopped: breadth limit reached",
    "re_searched_still_thin": "Searched again — base still thin",
    "error": "Stopped on an error",
}


def _decision_detail(payload: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    # queries-executed counts take priority over other per-backend numbers
    search_block = payload.get("search")
    if isinstance(search_block, dict):
        executed = search_block.get("queries_executed")
        if isinstance(executed, dict):
            for k, v in executed.items():
                if isinstance(v, (int, float)):
                    flat.setdefault(k, v)
    for key, value in payload.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            flat.setdefault(key, value)
        elif isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    flat.setdefault(k, v)
                elif isinstance(v, list):
                    flat.setdefault(k, len(v))
        elif isinstance(value, list):
            flat.setdefault(key, len(value))
    detail = {
        label: flat[key]
        for key, label in _DECISION_DETAIL_LABELS.items()
        if key in flat
    }
    stop = payload.get("stop_condition")
    if isinstance(stop, str):
        detail["How the search ended"] = _DECISION_STOP_TEXTS.get(stop, stop)
    return detail
