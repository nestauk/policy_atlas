"""Batched SQLAlchemy Core projections for the API's durable read models."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any, Literal, cast

from sqlalchemy import func, literal, select
from sqlalchemy.engine import Connection

from policy_atlas.api.contract import (
    ArtefactOut,
    BlockOut,
    ChunkContextOut,
    CitationOut,
    ClaimOut,
    CoverageOut,
    CoverageSnapshotOut,
    DecisionOut,
    EvidenceItemOut,
    FacetGroupsOut,
    FindingOut,
    FunnelOut,
    GroupOut,
    GroupsOut,
    LandscapeOut,
    Page,
    PageMeta,
    ReferenceOut,
    SectionOut,
    ThemeOut,
)
from policy_atlas.core.schema import (
    GROUPING_FACETS,
    addressable_unit,
    annotation,
    artefact,
    block,
    characterisation_result,
    chunk,
    citation,
    event_log,
    evidence_scope,
    extraction_result,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    project_source_snapshot,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
    synthesis_result,
)
from policy_atlas.evidence_base.assess.appraise import SCORE_LABELS
from policy_atlas.evidence_base.assess.screen import effective_screen_rows
from policy_atlas.runtime.steering_history import steering_history


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _title(metadata: Mapping[str, Any], locator: str) -> str:
    return _metadata_text(metadata, "title") or locator


def _year(metadata: Mapping[str, Any]) -> int | None:
    value = metadata.get("publication_year", metadata.get("year"))
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _venue(metadata: Mapping[str, Any]) -> str | None:
    return _metadata_text(metadata, "venue") or _metadata_text(metadata, "journal")


def _url(metadata: Mapping[str, Any]) -> str | None:
    return _metadata_text(metadata, "landing_page_url") or _metadata_text(metadata, "doi")


def _geography(metadata: Mapping[str, Any]) -> str | None:
    """Read provider publication geography when the acquired snapshot carries it."""
    direct = _metadata_text(metadata, "publication_country")
    if direct is not None:
        return direct
    provider = metadata.get("provider_fields")
    if not isinstance(provider, Mapping):
        return None
    source = provider.get("source")
    if metadata.get("backend") == "overton" and isinstance(source, Mapping):
        country = source.get("country")
        return country if isinstance(country, str) and country else None
    location = provider.get("primary_location")
    if metadata.get("backend") == "openalex" and isinstance(location, Mapping):
        source = location.get("source")
        if isinstance(source, Mapping):
            country = source.get("country_code")
            return country if isinstance(country, str) and country else None
    return None


def _origin(origin: str, metadata: Mapping[str, Any]) -> Literal["OpenAlex", "Overton", "Uploaded"]:
    if origin == "uploaded":
        return "Uploaded"
    backend = metadata.get("backend")
    if backend == "overton":
        return "Overton"
    # Acquisition currently has only OpenAlex and Overton backends.  Keep the
    # public vocabulary closed rather than exposing the internal "acquired".
    return "OpenAlex"


def _latest_row_by_id(rows: Iterable[Any], id_key: str, time_key: str) -> dict[uuid.UUID, Any]:
    latest: dict[uuid.UUID, Any] = {}
    for row in rows:
        key = cast(uuid.UUID, getattr(row, id_key))
        previous = latest.get(key)
        if previous is None or getattr(row, time_key) > getattr(previous, time_key):
            latest[key] = row
    return latest


def _latest_synthesis(conn: Connection, project_id: uuid.UUID) -> Any | None:
    return (
        conn.execute(
            select(synthesis_result)
            .where(synthesis_result.c.project_id == project_id)
            .order_by(
                synthesis_result.c.created_at.desc(), synthesis_result.c.synthesis_result_id.desc()
            )
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )


def _latest_selection(conn: Connection, project_id: uuid.UUID) -> Any | None:
    return (
        conn.execute(
            select(selection_result)
            .where(selection_result.c.project_id == project_id)
            .order_by(
                selection_result.c.created_at.desc(), selection_result.c.selection_result_id.desc()
            )
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )


def _selected_ids(value: Any) -> set[uuid.UUID]:
    selected: set[uuid.UUID] = set()
    if not isinstance(value, list):
        return selected
    for item in value:
        if not isinstance(item, Mapping):
            continue
        raw = item.get("pss_id")
        try:
            selected.add(uuid.UUID(str(raw)))
        except (TypeError, ValueError):
            continue
    return selected


def _cited_snapshot_ids(conn: Connection, artefact_id: uuid.UUID) -> set[uuid.UUID]:
    return set(
        conn.execute(
            select(chunk.c.source_snapshot_id)
            .distinct()
            .select_from(
                citation.join(
                    annotation, citation.c.annotation_id == annotation.c.annotation_id
                )
                .join(chunk, citation.c.chunk_id == chunk.c.chunk_id)
                .join(block, block.c.block_id == annotation.c.block_id)
            )
            .where(block.c.artefact_id == artefact_id)
        ).scalars()
    )


def _effective_screens(conn: Connection, project_id: uuid.UUID) -> dict[uuid.UUID, Any]:
    effective = effective_screen_rows()
    rows = conn.execute(select(effective).where(effective.c.project_id == project_id)).all()
    return _latest_row_by_id(rows, "project_source_snapshot_id", "screened_at")


def funnel_out(conn: Connection, project_id: uuid.UUID) -> FunnelOut:
    """Build full-flow counts, preserving missing-stage absence as ``None``."""
    found = int(
        conn.execute(
            select(func.count())
            .select_from(project_source_snapshot)
            .where(project_source_snapshot.c.project_id == project_id)
        ).scalar_one()
    )
    coverage_exists = (
        conn.execute(
            select(search_coverage_record.c.search_coverage_record_id)
            .where(search_coverage_record.c.project_id == project_id)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    effective = _effective_screens(conn, project_id)
    statuses = [row.status for row in effective.values()]
    appraised = int(
        conn.execute(
            select(func.count())
            .select_from(source_appraisal_result)
            .where(source_appraisal_result.c.project_id == project_id)
        ).scalar_one()
    )
    full_text_rows = int(
        conn.execute(
            select(func.count())
            .select_from(project_source_snapshot)
            .where(
                project_source_snapshot.c.project_id == project_id,
                project_source_snapshot.c.full_text_status != "not_attempted",
            )
        ).scalar_one()
    )
    selection = _latest_selection(conn, project_id)
    extraction = conn.execute(
        select(extraction_result.c.extraction_result_id)
        .where(extraction_result.c.project_id == project_id)
        .limit(1)
    ).scalar_one_or_none()
    finding_count = int(
        conn.execute(
            select(func.count())
            .select_from(intervention_outcome_finding)
            .where(intervention_outcome_finding.c.project_id == project_id)
        ).scalar_one()
    ) + int(
        conn.execute(
            select(func.count())
            .select_from(implementation_context_finding)
            .where(implementation_context_finding.c.project_id == project_id)
        ).scalar_one()
    )
    synthesis = _latest_synthesis(conn, project_id)
    return FunnelOut(
        found=found if found or coverage_exists else None,
        relevant=sum(status == "relevant" for status in statuses) if statuses else None,
        screened_out=sum(status != "relevant" for status in statuses) if statuses else None,
        quality_checked=appraised if appraised else None,
        read_in_full=int(
            conn.execute(
                select(func.count())
                .select_from(project_source_snapshot)
                .where(
                    project_source_snapshot.c.project_id == project_id,
                    project_source_snapshot.c.full_text_status == "ingested",
                )
            ).scalar_one()
        )
        if full_text_rows
        else None,
        selected=len(_selected_ids(selection["selected"])) if selection is not None else None,
        findings=finding_count if extraction is not None else None,
        cited=len(_cited_snapshot_ids(conn, synthesis["artefact_id"]))
        if synthesis is not None
        else None,
    )


def landscape_out(conn: Connection, project_id: uuid.UUID) -> LandscapeOut:
    """Return distributions computed only over effective screened-in rows."""
    relevant_ids = [
        key
        for key, value in _effective_screens(conn, project_id).items()
        if value.status == "relevant"
    ]
    if not relevant_ids:
        return LandscapeOut()
    base_rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .select_from(
            # Explicit onclause: project_source_snapshot carries TWO FKs into
            # source_snapshot (envelope + full-text); the implicit join is ambiguous.
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_source_snapshot_id.in_(relevant_ids))
    ).all()
    classifications = _latest_row_by_id(
        conn.execute(
            select(
                source_classification_result.c.project_source_snapshot_id,
                source_classification_result.c.primary_evidence_type,
                source_classification_result.c.classified_at,
            ).where(source_classification_result.c.project_id == project_id)
        ).all(),
        "project_source_snapshot_id",
        "classified_at",
    )
    types: Counter[str] = Counter()
    years: Counter[str] = Counter()
    geographies: Counter[str] = Counter()
    for row in base_rows:
        metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
        classification = classifications.get(row.project_source_snapshot_id)
        if classification is not None:
            types[classification.primary_evidence_type] += 1
        year = _year(metadata)
        if year is not None:
            years[str(year)] += 1
        geography = _geography(metadata)
        if geography is not None:
            geographies[geography] += 1
    characterisation = conn.execute(
        select(characterisation_result.c.themes)
        .where(characterisation_result.c.project_id == project_id)
        .order_by(characterisation_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    themes: list[ThemeOut] = []
    if isinstance(characterisation, Mapping) and isinstance(characterisation.get("themes"), list):
        for item in characterisation["themes"]:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                size = item.get("size")
                themes.append(
                    ThemeOut(
                        name=item["name"],
                        description=cast(str, item.get("description") or ""),
                        size=size if isinstance(size, int) else 0,
                    )
                )
    return LandscapeOut(
        evidence_types=dict(types),
        years=dict(years),
        themes=themes,
        geographies=dict(geographies) if geographies else None,
    )


def groups_out(conn: Connection, project_id: uuid.UUID) -> GroupsOut:
    """Project the latest durable facet grouping payload."""
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.project_id == project_id)
        .order_by(grouping_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(payload, Mapping):
        return GroupsOut()
    facets: list[FacetGroupsOut] = []
    order = [*GROUPING_FACETS, *sorted(key for key in payload if key not in GROUPING_FACETS)]
    for facet in order:
        item = payload.get(facet)
        if not isinstance(item, Mapping):
            continue
        groups = [
            GroupOut(
                label=cast(str, group.get("label") or ""),
                description=cast(str, group.get("description") or ""),
                size=cast(int, group.get("size") or 0),
            )
            for group in item.get("groups", [])
            if isinstance(group, Mapping)
        ]
        residual = 0
        for key in ("ungrouped", "no_value"):
            value = item.get(key)
            if isinstance(value, Mapping) and isinstance(value.get("finding_ids"), list):
                residual += len(value["finding_ids"])
        facets.append(FacetGroupsOut(facet=facet, groups=groups, ungrouped=residual))
    return GroupsOut(facets=facets)


def evidence_page(
    conn: Connection, project_id: uuid.UUID, page: int, page_size: int
) -> Page[EvidenceItemOut]:
    """Return one evidence page using a fixed number of batched source queries."""
    total = int(
        conn.execute(
            select(func.count())
            .select_from(project_source_snapshot)
            .where(project_source_snapshot.c.project_id == project_id)
        ).scalar_one()
    )
    rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.origin,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .select_from(
            # Explicit onclause — same two-FK ambiguity as landscape_out.
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
        .order_by(
            project_source_snapshot.c.ingested_at.desc(),
            project_source_snapshot.c.project_source_snapshot_id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    page_ids = [row.project_source_snapshot_id for row in rows]
    screens = _effective_screens(conn, project_id)
    classifications = (
        _latest_row_by_id(
            conn.execute(
                select(
                    source_classification_result.c.project_source_snapshot_id,
                    source_classification_result.c.primary_evidence_type,
                    source_classification_result.c.classified_at,
                ).where(
                    source_classification_result.c.project_id == project_id,
                    source_classification_result.c.project_source_snapshot_id.in_(page_ids),
                )
            ).all(),
            "project_source_snapshot_id",
            "classified_at",
        )
        if page_ids
        else {}
    )
    appraisals = (
        _latest_row_by_id(
            conn.execute(
                select(
                    source_appraisal_result.c.project_source_snapshot_id,
                    source_appraisal_result.c.quality_score,
                    source_appraisal_result.c.appraised_at,
                ).where(
                    source_appraisal_result.c.project_id == project_id,
                    source_appraisal_result.c.project_source_snapshot_id.in_(page_ids),
                )
            ).all(),
            "project_source_snapshot_id",
            "appraised_at",
        )
        if page_ids
        else {}
    )
    extracted = (
        set(
            conn.execute(
                select(source_extraction_record.c.project_source_snapshot_id)
                .where(
                    source_extraction_record.c.project_id == project_id,
                    source_extraction_record.c.project_source_snapshot_id.in_(page_ids),
                    source_extraction_record.c.finding_count > 0,
                )
                .distinct()
            ).scalars()
        )
        if page_ids
        else set()
    )
    selection = _latest_selection(conn, project_id)
    selected = _selected_ids(selection["selected"]) if selection is not None else set()
    synthesis = _latest_synthesis(conn, project_id)
    cited_snapshots = (
        _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
    )
    items: list[EvidenceItemOut] = []
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
        screen = screens.get(row.project_source_snapshot_id)
        cited = (
            row.source_snapshot_id in cited_snapshots
            or row.full_text_snapshot_id in cited_snapshots
        )
        if cited:
            status, reason = "cited", None
        elif row.project_source_snapshot_id in extracted:
            status, reason = "findings_extracted", None
        elif row.project_source_snapshot_id in selected:
            status, reason = "selected", None
        elif row.full_text_status == "ingested":
            status, reason = "read_in_full", None
        elif (
            screen is not None
            and screen.status == "relevant"
            and row.full_text_status in {"fetch_failed", "parse_failed"}
        ):
            status, reason = "unavailable", row.full_text_error
        elif screen is not None and screen.status == "relevant":
            status, reason = ("not_selected", None) if selection is not None else ("relevant", None)
        elif screen is not None:
            status, reason = "screened_out", screen.screen_basis
        else:
            status, reason = "found", None
        classification = classifications.get(row.project_source_snapshot_id)
        appraisal = appraisals.get(row.project_source_snapshot_id)
        items.append(
            EvidenceItemOut(
                source_id=row.project_source_snapshot_id,
                title=_title(metadata, row.source_locator),
                year=_year(metadata),
                venue=_venue(metadata),
                origin=_origin(row.origin, metadata),
                status=cast(Any, status),
                status_reason=reason,
                evidence_type=classification.primary_evidence_type if classification else None,
                appraisal_tier=SCORE_LABELS.get(appraisal.quality_score) if appraisal else None,
                cited=cited,
                url=_url(metadata),
            )
        )
    return Page(data=items, pagination=PageMeta(page=page, page_size=page_size, total_items=total))


def _latest_relevance(conn: Connection, project_id: uuid.UUID) -> dict[str, str]:
    row = conn.execute(
        select(extraction_result.c.extraction_provenance)
        .where(extraction_result.c.project_id == project_id)
        .order_by(extraction_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(row, Mapping) or not isinstance(row.get("relevance"), Mapping):
        return {}
    values = row["relevance"].get("annotations")
    return (
        {str(key): value for key, value in values.items() if value in {"priority", "normal"}}
        if isinstance(values, Mapping)
        else {}
    )


def findings_page(
    conn: Connection, project_id: uuid.UUID, page: int, page_size: int
) -> Page[FindingOut]:
    """Page IOF and ICF findings with source attribution in two union queries."""
    iof = select(
        intervention_outcome_finding.c.finding_id.label("finding_id"),
        intervention_outcome_finding.c.intervention.label("statement"),
        intervention_outcome_finding.c.extraction_record_id,
        intervention_outcome_finding.c.created_at,
        literal("iof").label("profile"),
    ).where(intervention_outcome_finding.c.project_id == project_id)
    icf = select(
        implementation_context_finding.c.finding_id.label("finding_id"),
        implementation_context_finding.c.claim.label("statement"),
        implementation_context_finding.c.extraction_record_id,
        implementation_context_finding.c.created_at,
        literal("icf").label("profile"),
    ).where(implementation_context_finding.c.project_id == project_id)
    union = iof.union_all(icf).subquery("all_findings")
    total = int(conn.execute(select(func.count()).select_from(union)).scalar_one())
    rows = conn.execute(
        select(
            union.c.finding_id,
            union.c.statement,
            union.c.created_at,
            union.c.profile,
            source_extraction_record.c.project_source_snapshot_id,
            source_extraction_record.c.extraction_record_id,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .select_from(
            union.join(
                source_extraction_record,
                union.c.extraction_record_id == source_extraction_record.c.extraction_record_id,
            )
            .join(
                project_source_snapshot,
                project_source_snapshot.c.project_source_snapshot_id
                == source_extraction_record.c.project_source_snapshot_id,
            )
            .join(
                source_snapshot,
                source_snapshot.c.source_snapshot_id
                == project_source_snapshot.c.source_snapshot_id,
            )
        )
        .order_by(union.c.created_at.desc(), union.c.finding_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    relevance = _latest_relevance(conn, project_id)
    items = []
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
        items.append(
            FindingOut(
                finding_id=row.finding_id,
                statement=row.statement,
                source_id=row.project_source_snapshot_id,
                source_title=_title(metadata, row.source_locator),
                profile=cast(Literal["iof", "icf"], row.profile),
                relevance=cast(Any, relevance.get(str(row.finding_id))),
            )
        )
    return Page(data=items, pagination=PageMeta(page=page, page_size=page_size, total_items=total))


_EVENT_KINDS = {
    "search.executed",
    "project.renamed",
    "project.archived",
    "run.opened",
    "run.parked",
    "run.finished",
    "run.interrupted",
    "plan.approved",
}


def _event_decision(row: Any) -> DecisionOut:
    payload = row.payload if isinstance(row.payload, Mapping) else {}
    actor = payload.get("actor") if isinstance(payload.get("actor"), str) else None
    text = {
        "search.executed": "Executed a search query.",
        "project.renamed": "Renamed the project.",
        "project.archived": "Archived the project.",
        "run.opened": "Opened an evidence-base run.",
        "run.parked": "Parked the run for a check-in.",
        "run.finished": "Finished the run.",
        "run.interrupted": "Interrupted the run.",
        "plan.approved": "Approved the plan.",
    }[row.event_type]
    return DecisionOut(
        sequence=int(row.sequence),
        occurred_at=row.occurred_at,
        kind=row.event_type,
        summary=text,
        decided_by=cast(Any, "user") if actor else None,
        detail=dict(payload),
    )


def decisions_page(
    conn: Connection, project_id: uuid.UUID, page: int, page_size: int
) -> Page[DecisionOut]:
    """Return steering-history decisions plus the explicitly allowlisted audit events."""
    allowed = (
        conn.execute(
            select(event_log).where(
                event_log.c.project_id == project_id, event_log.c.event_type.in_(_EVENT_KINDS)
            )
        )
        .mappings()
        .all()
    )
    decision_events: list[DecisionOut] = [_event_decision(row) for row in allowed]
    for story in steering_history(conn, project_id):
        for event in story["events"]:
            if event["event_type"] != "steering.decision":
                continue
            payload = event["payload"] if isinstance(event["payload"], Mapping) else {}
            decision_events.append(
                DecisionOut(
                    sequence=int(event["sequence"]),
                    occurred_at=event["occurred_at"],
                    kind="steering.decision",
                    summary="Recorded a steering decision.",
                    decided_by=cast(Any, payload.get("decided_by"))
                    if payload.get("decided_by") in {"user", "orchestrator", "standing_default"}
                    else None,
                    detail=dict(payload),
                )
            )
    decision_events.sort(key=lambda item: item.sequence, reverse=True)
    return Page(
        data=decision_events[(page - 1) * page_size : page * page_size],
        pagination=PageMeta(page=page, page_size=page_size, total_items=len(decision_events)),
    )


def artefact_out(conn: Connection, project_id: uuid.UUID) -> ArtefactOut | None:
    """Materialize the latest synthesis artefact with batched claims and citations."""
    synthesis = _latest_synthesis(conn, project_id)
    if synthesis is None:
        return None
    artefact_row = (
        conn.execute(select(artefact).where(artefact.c.artefact_id == synthesis["artefact_id"]))
        .mappings()
        .one_or_none()
    )
    if artefact_row is None:
        return None
    scope = conn.execute(
        select(evidence_scope.c.intent).where(
            evidence_scope.c.evidence_scope_id == synthesis["evidence_scope_id"]
        )
    ).scalar_one_or_none()
    specs = synthesis["blocks"] if isinstance(synthesis["blocks"], list) else []
    parsed_specs = [
        (item, uuid.UUID(item["block_id"]))
        for item in specs
        if isinstance(item, Mapping) and isinstance(item.get("block_id"), str)
    ]
    ids = [entry[1] for entry in parsed_specs]
    prose = (
        {
            row.block_id: row.content
            for row in conn.execute(
                select(block.c.block_id, block.c.content).where(block.c.block_id.in_(ids))
            ).all()
        }
        if ids
        else {}
    )
    annotations = (
        conn.execute(
            select(
                annotation.c.annotation_id,
                annotation.c.block_id,
                annotation.c.annotation_type,
                annotation.c.payload,
                addressable_unit.c.unit_id,
                addressable_unit.c.content,
                addressable_unit.c.locator,
            )
            .select_from(
                annotation.join(
                    addressable_unit,
                    (annotation.c.block_id == addressable_unit.c.block_id)
                    & (annotation.c.unit_id == addressable_unit.c.unit_id),
                )
            )
            .where(annotation.c.block_id.in_(ids))
        ).all()
        if ids
        else []
    )
    annotation_ids = [row.annotation_id for row in annotations]
    citation_rows = (
        conn.execute(
            select(
                citation.c.citation_id,
                citation.c.annotation_id,
                citation.c.chunk_id,
                citation.c.quote,
                annotation.c.payload,
                chunk.c.source_snapshot_id,
            )
            .select_from(
                citation.join(
                    annotation, citation.c.annotation_id == annotation.c.annotation_id
                ).join(chunk, citation.c.chunk_id == chunk.c.chunk_id)
            )
            .where(citation.c.annotation_id.in_(annotation_ids))
        ).all()
        if annotation_ids
        else []
    )
    snapshots = {row.source_snapshot_id for row in citation_rows}
    meta = (
        {
            row.source_snapshot_id: (
                row.metadata if isinstance(row.metadata, Mapping) else {},
                row.source_locator,
            )
            for row in conn.execute(
                select(
                    source_snapshot.c.source_snapshot_id,
                    source_snapshot.c.metadata,
                    source_snapshot.c.source_locator,
                ).where(source_snapshot.c.source_snapshot_id.in_(snapshots))
            ).all()
        }
        if snapshots
        else {}
    )
    snapshot_to_pss: dict[uuid.UUID, uuid.UUID] = {}
    for row in conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
        ).where(project_source_snapshot.c.project_id == project_id)
    ).all():
        snapshot_to_pss[row.source_snapshot_id] = row.project_source_snapshot_id
        if row.full_text_snapshot_id is not None:
            snapshot_to_pss[row.full_text_snapshot_id] = row.project_source_snapshot_id
    appraisal = _latest_row_by_id(
        conn.execute(
            select(
                source_appraisal_result.c.project_source_snapshot_id,
                source_appraisal_result.c.quality_score,
                source_appraisal_result.c.appraised_at,
            ).where(source_appraisal_result.c.project_id == project_id)
        ).all(),
        "project_source_snapshot_id",
        "appraised_at",
    )
    citations_by_annotation: dict[uuid.UUID, list[Any]] = {}
    for row in citation_rows:
        citations_by_annotation.setdefault(row.annotation_id, []).append(row)
    refs: dict[uuid.UUID, int] = {}
    reference_order: list[uuid.UUID] = []
    claims_by_block: dict[uuid.UUID, list[ClaimOut]] = {block_id: [] for block_id in ids}
    for row in annotations:
        locator = row.locator if isinstance(row.locator, Mapping) else {}
        start, end = locator.get("start"), locator.get("end")
        span = (start, end) if isinstance(start, int) and isinstance(end, int) else None
        claim_citations: list[CitationOut] = []
        for cited in citations_by_annotation.get(row.annotation_id, []):
            snapshot_id = cited.source_snapshot_id
            if snapshot_id not in refs:
                refs[snapshot_id] = len(refs) + 1
                reference_order.append(snapshot_id)
            source_meta, locator_text = meta.get(snapshot_id, ({}, "Unknown source"))
            pss_id = snapshot_to_pss.get(snapshot_id)
            score_row = appraisal.get(pss_id) if pss_id is not None else None
            payload = row.payload if isinstance(row.payload, Mapping) else {}
            claim_citations.append(
                CitationOut(
                    citation_id=cited.citation_id,
                    n=refs[snapshot_id],
                    source_title=_title(source_meta, locator_text),
                    quote=cited.quote,
                    grounding_tier=cast(str | None, payload.get("verdict"))
                    if isinstance(payload.get("verdict"), str)
                    else None,
                    appraisal_label=SCORE_LABELS.get(score_row.quality_score)
                    if score_row
                    else None,
                )
            )
        claim_type = (
            row.annotation_type
            if row.annotation_type
            in {"citation", "gap", "reasoning", "pattern", "theme", "unspanned_assertion"}
            else "reasoning"
        )
        claims_by_block[row.block_id].append(
            ClaimOut(
                claim_id=row.unit_id,
                claim_type=cast(Any, claim_type),
                text=row.content,
                span=span,
                citations=claim_citations,
            )
        )
    sections: list[SectionOut] = []
    for spec, block_id in parsed_specs:
        role = (
            spec.get("role")
            if spec.get("role") in {"key_findings", "standard", "conclusions"}
            else "standard"
        )
        sections.append(
            SectionOut(
                title=cast(str, spec.get("title") or ""),
                role=cast(Any, role),
                blocks=[
                    BlockOut(
                        block_id=block_id,
                        prose=prose.get(block_id, ""),
                        claims=claims_by_block.get(block_id, []),
                    )
                ],
            )
        )
    refs_out = [
        ReferenceOut(
            n=refs[snapshot_id],
            title=_title(
                meta.get(snapshot_id, ({}, "Unknown source"))[0],
                meta.get(snapshot_id, ({}, "Unknown source"))[1],
            ),
            year=_year(meta.get(snapshot_id, ({}, ""))[0]),
            venue=_venue(meta.get(snapshot_id, ({}, ""))[0]),
            url=_url(meta.get(snapshot_id, ({}, ""))[0]),
        )
        for snapshot_id in reference_order
    ]
    study_types = {
        evidence_type: int(count)
        for evidence_type, count in conn.execute(
            select(
                source_classification_result.c.primary_evidence_type,
                func.count(),
            )
            .where(source_classification_result.c.project_id == project_id)
            .where(
                source_classification_result.c.evidence_scope_id == synthesis["evidence_scope_id"]
            )
            .group_by(source_classification_result.c.primary_evidence_type)
        )
    }
    effective = effective_screen_rows()
    screen_statuses = (
        conn.execute(
            select(effective.c.status)
            .where(effective.c.project_id == project_id)
            .where(effective.c.evidence_scope_id == synthesis["evidence_scope_id"])
        )
        .scalars()
        .all()
    )
    reference_years = [reference.year for reference in refs_out if reference.year is not None]
    year_range = (min(reference_years), max(reference_years)) if reference_years else None
    return ArtefactOut(
        title=artefact_row["title"],
        question=scope or "",
        coverage_snapshot=CoverageSnapshotOut(
            source_count=len(refs_out),
            study_types=study_types,
            year_range=year_range,
            included=sum(status == "relevant" for status in screen_statuses),
            screened_out=sum(status != "relevant" for status in screen_statuses),
        ),
        sections=sections,
        references=refs_out,
    )


def coverage_out(conn: Connection, project_id: uuid.UUID) -> CoverageOut | None:
    """Compose the latest coverage record as one sentence with its evidence base."""
    row = (
        conn.execute(
            select(search_coverage_record)
            .where(search_coverage_record.c.project_id == project_id)
            .order_by(search_coverage_record.c.created_at.desc())
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    base = {
        "stop_condition": row["stop_condition"],
        "adequacy_verdict": row["adequacy_verdict"],
        "verdict_origin": row["verdict_origin"],
        "backends": row["backends"],
    }
    counts = funnel_out(conn, project_id).model_dump(include={"found", "relevant", "screened_out"})
    base["counts"] = counts
    adequacy = (
        "Coverage was judged adequate."
        if row["adequacy_verdict"] == "adequate"
        else "Coverage was judged inadequate."
    )
    return CoverageOut(
        sentence=f"Searching stopped because {row['stop_condition'].replace('_', ' ')}. {adequacy}",
        base=base,
    )


def chunk_context_out(
    conn: Connection, project_id: uuid.UUID, citation_id: uuid.UUID
) -> ChunkContextOut | None:
    """Return at most 800 characters either side of a cited, anchored source span."""
    row = conn.execute(
        select(citation.c.quote, chunk.c.content)
        .select_from(
            citation.join(annotation, citation.c.annotation_id == annotation.c.annotation_id)
            .join(block, annotation.c.block_id == block.c.block_id)
            .join(artefact, block.c.artefact_id == artefact.c.artefact_id)
            .join(chunk, chunk.c.chunk_id == citation.c.chunk_id)
        )
        .where(citation.c.citation_id == citation_id, artefact.c.project_id == project_id)
    ).one_or_none()
    if row is None:
        return None
    quote = row.quote
    text = row.content
    # Citation rows keep a verified quote but not a character interval.  An
    # ambiguous repeated quote has no honest recoverable span, so this seam is
    # absent rather than guessing at a document position.
    if text.count(quote) != 1:
        return None
    position = text.find(quote)
    if position < 0:
        return None
    end = position + len(quote)
    start_window = max(0, position - 800)
    end_window = min(len(text), end + 800)
    return ChunkContextOut(
        context=text[start_window:end_window],
        span_start=position - start_window,
        span_end=end - start_window,
        clamped=start_window > 0 or end_window < len(text),
    )
