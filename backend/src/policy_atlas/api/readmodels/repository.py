"""Batched SQLAlchemy Core projections for the API's durable read models."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable, Mapping
from functools import cmp_to_key
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.api.contract import (
    EVIDENCE_STATUS_INCLUDED,
    ArtefactOut,
    BlockOut,
    ChunkContextOut,
    CitationOut,
    CitedInOut,
    ClaimOut,
    CoverageBackendDetailOut,
    CoverageOut,
    CoverageQueryOut,
    CoverageSnapshotOut,
    DecisionOut,
    EvidenceItemOut,
    FacetGroupsOut,
    FindingOut,
    FunnelOut,
    GapOut,
    GroupOut,
    GroupsOut,
    IcfFindingOut,
    IofFindingOut,
    IofStatisticsOut,
    LandscapeOut,
    Page,
    PageMeta,
    ReferenceOut,
    SectionOut,
    SourceDossierOut,
    SourceTagOut,
    ThemeOut,
    ThemeRefItemOut,
    ThemeRefOut,
    ThemeSourceOut,
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
    source_tag,
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


def _provider_landing_page(metadata: Mapping[str, Any]) -> str | None:
    """Return a retained provider URL without exposing provider metadata itself."""
    provider = metadata.get("provider_fields")
    if not isinstance(provider, Mapping):
        return None
    for key in ("document_url", "pdf_url"):
        value = provider.get(key)
        if isinstance(value, str) and value:
            return value
    for location_key in ("primary_location", "best_oa_location"):
        location = provider.get(location_key)
        if isinstance(location, Mapping):
            value = location.get("landing_page_url")
            if isinstance(value, str) and value:
                return value
    return None


def _url(metadata: Mapping[str, Any], source_locator: str | None = None) -> str | None:
    """Apply the public source-URL fallback ladder."""
    landing_page = _metadata_text(metadata, "landing_page_url")
    if landing_page is not None:
        return landing_page
    if source_locator:
        return source_locator
    provider_url = _provider_landing_page(metadata)
    if provider_url is not None:
        return provider_url
    doi = _metadata_text(metadata, "doi")
    return f"https://doi.org/{doi}" if doi is not None else None


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
                citation.join(annotation, citation.c.annotation_id == annotation.c.annotation_id)
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


def landscape_out(
    conn: Connection, project_id: uuid.UUID, *, scope: Literal["cited"] | None = None
) -> LandscapeOut:
    """Return whole-screened-in or latest-artefact-cited distributions.

    Args:
        conn: Open database connection.
        project_id: Owning project.
        scope: ``"cited"`` restricts distributions to latest-artefact citations.

    Returns:
        Landscape distributions for the requested corpus scope.
    """
    relevant_ids = [
        key
        for key, value in _effective_screens(conn, project_id).items()
        if value.status == "relevant"
    ]
    if scope == "cited":
        synthesis = _latest_synthesis(conn, project_id)
        cited_snapshots = (
            _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
        )
        if cited_snapshots:
            relevant_ids = list(
                conn.execute(
                    select(project_source_snapshot.c.project_source_snapshot_id).where(
                        project_source_snapshot.c.project_id == project_id,
                        project_source_snapshot.c.project_source_snapshot_id.in_(relevant_ids),
                        (
                            project_source_snapshot.c.source_snapshot_id.in_(cited_snapshots)
                            | project_source_snapshot.c.full_text_snapshot_id.in_(cited_snapshots)
                        ),
                    )
                ).scalars()
            )
        else:
            relevant_ids = []
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
                member_ids = _uuid_members(item.get("member_ids"))
                size: Any
                if scope == "cited":
                    size = sum(member_id in relevant_ids for member_id in member_ids)
                    if size == 0:
                        continue
                else:
                    size = item.get("size")
                raw_theme_id = item.get("theme_id")
                try:
                    theme_id = uuid.UUID(raw_theme_id) if isinstance(raw_theme_id, str) else None
                except ValueError:
                    theme_id = None
                themes.append(
                    ThemeOut(
                        name=item["name"],
                        description=cast(str, item.get("description") or ""),
                        size=size if isinstance(size, int) else 0,
                        theme_id=theme_id,
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


def _screen_event_reason(payload: Mapping[str, Any], status: str) -> str | None:
    """Pick the rep reason that explains the aggregated screen decision.

    Reps vote; the first reason from a rep agreeing with the final status
    wins ('unsure' votes count toward relevant, mirroring `_vote_decision`),
    falling back to any rep's reason.
    """
    reps = payload.get("reps")
    if not isinstance(reps, list):
        return None
    candidates = [
        rep
        for rep in reps
        if isinstance(rep, Mapping) and isinstance(rep.get("reason"), str) and rep["reason"]
    ]
    for rep in candidates:
        decision = rep.get("decision")
        if decision == status or (status == "relevant" and decision == "unsure"):
            return cast(str, rep["reason"])
    return cast(str, candidates[0]["reason"]) if candidates else None


def _source_reason_maps(
    conn: Connection, project_id: uuid.UUID
) -> tuple[dict[uuid.UUID, str], dict[uuid.UUID, str]]:
    """Latest per-source screening/classification reasons from the event log.

    The assess LLMs' one-sentence reasons are event-payload-only (never
    result-row columns). Latest sequence wins, which tracks the effective
    screen for append-only re-screens; failed screens carry no decision and
    are skipped.
    """
    rows = conn.execute(
        select(event_log.c.event_type, event_log.c.payload)
        .where(
            event_log.c.project_id == project_id,
            event_log.c.event_type.in_(("source.screened", "source.classified")),
        )
        .order_by(event_log.c.sequence)
    ).all()
    screen_reasons: dict[uuid.UUID, str] = {}
    classification_reasons: dict[uuid.UUID, str] = {}
    for row in rows:
        payload = row.payload if isinstance(row.payload, Mapping) else {}
        try:
            pss_id = uuid.UUID(str(payload.get("project_source_snapshot_id")))
        except (TypeError, ValueError):
            continue
        if row.event_type == "source.classified":
            reason = payload.get("reason")
            if isinstance(reason, str) and reason:
                classification_reasons[pss_id] = reason
        else:
            status = payload.get("status")
            if status not in ("relevant", "not_relevant"):
                continue
            reason = _screen_event_reason(payload, status)
            if reason is not None:
                screen_reasons[pss_id] = reason
    return screen_reasons, classification_reasons


def _expand_evidence_statuses(values: Iterable[str]) -> set[str]:
    """Expand the `Included` filter shortcut into its ladder positions."""
    expanded: set[str] = set()
    for value in values:
        if value == "Included":
            expanded.update(EVIDENCE_STATUS_INCLUDED)
        else:
            expanded.add(value)
    return expanded


def evidence_page(
    conn: Connection,
    project_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    statuses: Iterable[str] | None = None,
    cited: bool | None = None,
    sort: Literal["title", "year", "type", "strength", "status"] | None = None,
    order: Literal["asc", "desc"] | None = None,
    theme: uuid.UUID | None = None,
    origin: str | None = None,
    evidence_type: str | None = None,
    strength: str | None = None,
) -> Page[EvidenceItemOut]:
    """Return one evidence page, deriving status project-wide before paging.

    `status`/`cited`/`theme` filters are collection-true: status is derived for
    every project source (bounded — one project's worth of rows, the
    `funnel_out` precedent) before filtering and paginating, so
    `total_items` reflects the filtered collection, never the unfiltered
    project total or the page size. Sorting likewise runs over that complete
    collection before pagination; ingestion order remains the
    stable tie-breaker.
    """
    target_statuses = _expand_evidence_statuses(statuses) if statuses else None
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
    ).all()
    screens = _effective_screens(conn, project_id)
    screen_reasons, classification_reasons = _source_reason_maps(conn, project_id)
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
    appraisals = _latest_row_by_id(
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
    extracted = set(
        conn.execute(
            select(source_extraction_record.c.project_source_snapshot_id)
            .where(
                source_extraction_record.c.project_id == project_id,
                source_extraction_record.c.finding_count > 0,
            )
            .distinct()
        ).scalars()
    )
    selection = _latest_selection(conn, project_id)
    selected = _selected_ids(selection["selected"]) if selection is not None else set()
    synthesis = _latest_synthesis(conn, project_id)
    cited_snapshots = (
        _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
    )
    themed_sources = (
        set(
            conn.execute(
                select(source_tag.c.project_source_snapshot_id).where(
                    source_tag.c.project_id == project_id,
                    source_tag.c.theme_id == theme,
                )
            ).scalars()
        )
        if theme is not None
        else None
    )
    sortable_items: list[tuple[EvidenceItemOut, int | None]] = []
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
        screen = screens.get(row.project_source_snapshot_id)
        row_cited = (
            row.source_snapshot_id in cited_snapshots
            or row.full_text_snapshot_id in cited_snapshots
        )
        if row_cited:
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
        if target_statuses is not None and status not in target_statuses:
            continue
        if cited is not None and row_cited != cited:
            continue
        if themed_sources is not None and row.project_source_snapshot_id not in themed_sources:
            continue
        classification = classifications.get(row.project_source_snapshot_id)
        appraisal = appraisals.get(row.project_source_snapshot_id)
        item_origin = _origin(row.origin, metadata)
        evidence_type_value = classification.primary_evidence_type if classification else None
        tier = SCORE_LABELS.get(appraisal.quality_score) if appraisal else None
        if origin is not None and item_origin != origin:
            continue
        if evidence_type is not None and evidence_type_value != evidence_type:
            continue
        if strength is not None and tier != strength:
            continue
        sortable_items.append(
            (
                EvidenceItemOut(
                    source_id=row.project_source_snapshot_id,
                    title=_title(metadata, row.source_locator),
                    year=_year(metadata),
                    venue=_venue(metadata),
                    origin=item_origin,
                    status=cast(Any, status),
                    status_reason=reason,
                    evidence_type=evidence_type_value,
                    appraisal_tier=tier,
                    cited=row_cited,
                    url=_url(metadata, row.source_locator),
                    screen_confidence=screen.screen_decision_confidence if screen else None,
                    screen_basis=screen.screen_basis if screen else None,
                    screen_stage=screen.screen_stage if screen else None,
                    screen_status=cast(Any, screen.status)
                    if screen
                    and screen.status in {"relevant", "not_relevant", "excluded_retracted"}
                    else None,
                    screen_reason=screen_reasons.get(row.project_source_snapshot_id),
                    classification_reason=classification_reasons.get(
                        row.project_source_snapshot_id
                    ),
                    read_in_full=row.full_text_status == "ingested",
                ),
                appraisal.quality_score if appraisal is not None else None,
            )
        )
    if sort is not None:
        direction = order or ("desc" if sort == "year" else "asc")

        def compare(
            left: tuple[EvidenceItemOut, int | None],
            right: tuple[EvidenceItemOut, int | None],
        ) -> int:
            return _compare_evidence_sort(left, right, sort=sort, direction=direction)

        sortable_items.sort(key=cmp_to_key(compare))
    items = [item for item, _score in sortable_items]
    total = len(items)
    page_items = items[(page - 1) * page_size : page * page_size]
    return Page(
        data=page_items, pagination=PageMeta(page=page, page_size=page_size, total_items=total)
    )


_EVIDENCE_STATUS_SORT_RANK = {
    "found": 0,
    "screened_out": 1,
    "relevant": 2,
    "not_selected": 3,
    "selected": 4,
    "read_in_full": 5,
    "findings_extracted": 6,
    "cited": 7,
    "unavailable": 8,
}


def _compare_evidence_sort(
    left: tuple[EvidenceItemOut, int | None],
    right: tuple[EvidenceItemOut, int | None],
    *,
    sort: Literal["title", "year", "type", "strength", "status"],
    direction: Literal["asc", "desc"],
) -> int:
    """Compare two already-projected evidence rows with nulls always last."""
    left_item, left_score = left
    right_item, right_score = right
    left_value: str | int | None
    right_value: str | int | None
    if sort == "title":
        left_value, right_value = left_item.title.casefold(), right_item.title.casefold()
    elif sort == "year":
        left_value, right_value = left_item.year, right_item.year
    elif sort == "type":
        left_value, right_value = left_item.evidence_type, right_item.evidence_type
    elif sort == "strength":
        left_value, right_value = left_score, right_score
    else:
        left_value = _EVIDENCE_STATUS_SORT_RANK[left_item.status]
        right_value = _EVIDENCE_STATUS_SORT_RANK[right_item.status]
    if left_value is None:
        return 0 if right_value is None else 1
    if right_value is None:
        return -1
    if left_value == right_value:
        return 0
    if isinstance(left_value, str):
        right_text = cast(str, right_value)
        result = -1 if left_value < right_text else 1
    else:
        right_rank = cast(int, right_value)
        result = -1 if left_value < right_rank else 1
    return result if direction == "asc" else -result


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


def _finding_ids_for_group(
    conn: Connection,
    project_id: uuid.UUID,
    *,
    facet: str | None,
    group: str | None,
    group_id: str | None,
) -> set[uuid.UUID] | None:
    """Resolve a `facet`+`group` or `group_id` filter to member finding ids.

    Returns `None` when no group filter was requested (caller does not
    restrict); returns a possibly-empty set otherwise — an unknown facet,
    group label, or `group_id` resolves to no members, i.e. an empty result,
    per the router's param-validation conventions for unrecognised values.
    """
    if group_id is None and facet is None and group is None:
        return None
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.project_id == project_id)
        .order_by(grouping_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    matches: set[uuid.UUID] = set()
    if not isinstance(payload, Mapping):
        return matches
    for payload_facet, facet_data in payload.items():
        if not isinstance(payload_facet, str) or not isinstance(facet_data, Mapping):
            continue
        for entry in facet_data.get("groups", []):
            if not isinstance(entry, Mapping):
                continue
            if group_id is not None:
                if entry.get("group_id") != group_id:
                    continue
            elif payload_facet != facet or entry.get("label") != group:
                continue
            members = entry.get("member_finding_ids")
            if not isinstance(members, list):
                continue
            for member in members:
                try:
                    matches.add(uuid.UUID(str(member)))
                except (TypeError, ValueError):
                    continue
    return matches


def findings_page(
    conn: Connection,
    project_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    profile: str | None = None,
    facet: str | None = None,
    group: str | None = None,
    group_id: str | None = None,
    source_id: uuid.UUID | None = None,
) -> Page[FindingOut]:
    """Page IOF and ICF findings with profile-discriminated durable detail.

    `profile`, `facet`+`group` (or `group_id`), and `source_id` filter the
    collection before pagination, so `total_items` reflects the filtered
    collection (collection-true counts), never the unfiltered total.
    """

    def where_clauses(finding: Any) -> list[Any]:
        clauses: list[Any] = [finding.c.project_id == project_id]
        if source_id is not None:
            clauses.append(source_extraction_record.c.project_source_snapshot_id == source_id)
        return clauses

    iof_rows = (
        conn.execute(
            select(
                intervention_outcome_finding,
                source_extraction_record.c.project_source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(_finding_source_join(intervention_outcome_finding))
            .where(*where_clauses(intervention_outcome_finding))
        )
        .mappings()
        .all()
        if profile in (None, "iof")
        else []
    )
    icf_rows = (
        conn.execute(
            select(
                implementation_context_finding,
                source_extraction_record.c.project_source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(_finding_source_join(implementation_context_finding))
            .where(*where_clauses(implementation_context_finding))
        )
        .mappings()
        .all()
        if profile in (None, "icf")
        else []
    )
    rows = [("iof", row) for row in iof_rows] + [("icf", row) for row in icf_rows]
    rows.sort(key=lambda item: (item[1]["created_at"], item[1]["finding_id"]), reverse=True)
    group_filter_ids = _finding_ids_for_group(
        conn, project_id, facet=facet, group=group, group_id=group_id
    )
    if group_filter_ids is not None:
        rows = [item for item in rows if item[1]["finding_id"] in group_filter_ids]
    total = len(rows)
    rows = rows[(page - 1) * page_size : page * page_size]
    relevance = _latest_relevance(conn, project_id)
    groups = _finding_groups(conn, project_id)
    items: list[FindingOut] = []
    for profile, row in rows:
        metadata = row["metadata"] if isinstance(row["metadata"], Mapping) else {}
        common = {
            "finding_id": row["finding_id"],
            "statement": row["intervention"] if profile == "iof" else row["claim"],
            "source_id": row["project_source_snapshot_id"],
            "source_title": _title(metadata, row["source_locator"]),
            "relevance": cast(Any, relevance.get(str(row["finding_id"]))),
            "quote": _grounding_value(row["grounding"], "quote"),
            "quote_verified": _grounding_value(row["grounding"], "quote_verified"),
            "groups": groups.get(row["finding_id"], {}),
        }
        if profile == "iof":
            statistics = row["statistics"] if isinstance(row["statistics"], Mapping) else {}
            items.append(
                IofFindingOut(
                    **common,
                    intervention=row["intervention"],
                    outcome=row["outcome"],
                    effect_direction=row["effect_direction"],
                    statistics=IofStatisticsOut.model_validate(statistics),
                    comparator=row["comparator"],
                    estimate_level=row["estimate_level"],
                    causality_by_design=row["causality_by_design"],
                    is_primary=row["is_primary"],
                    stratum_qualifiers=cast(list[dict[str, str]], row["stratum_qualifiers"]),
                    effect_basis=row["effect_basis"],
                    study_geography=row["study_geography"],
                    population=row["population"],
                    setting=row["setting"],
                    study_design=row["study_design"],
                )
            )
        else:
            items.append(
                IcfFindingOut(
                    **common,
                    context_type=row["context_type"],
                    claim=row["claim"],
                    context_label=row["context_label"],
                    intervention=row["intervention"],
                    outcome=row["outcome"],
                    population=row["population"],
                    setting=row["setting"],
                    study_geography=row["study_geography"],
                    study_design=row["study_design"],
                    claim_level=row["claim_level"],
                    claim_basis=row["claim_basis"],
                    level=row["level"],
                    resource_requirements=row["resource_requirements"],
                    workforce_requirements=row["workforce_requirements"],
                )
            )
    return Page(data=items, pagination=PageMeta(page=page, page_size=page_size, total_items=total))


def _finding_source_join(finding: Any) -> Any:
    """Join either finding table to its envelope source."""
    return (
        finding.join(
            source_extraction_record,
            finding.c.extraction_record_id == source_extraction_record.c.extraction_record_id,
        )
        .join(
            project_source_snapshot,
            project_source_snapshot.c.project_source_snapshot_id
            == source_extraction_record.c.project_source_snapshot_id,
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == project_source_snapshot.c.source_snapshot_id,
        )
    )


def _grounding_value(grounding: Any, key: str) -> Any | None:
    """Return one honest grounding value from the first stored anchor."""
    if not isinstance(grounding, list) or not grounding or not isinstance(grounding[0], Mapping):
        return None
    value = grounding[0].get(key)
    if key == "quote_verified":
        return value if isinstance(value, bool) else None
    return value if isinstance(value, str) else None


def _finding_groups(conn: Connection, project_id: uuid.UUID) -> dict[uuid.UUID, dict[str, str]]:
    """Map latest grouping memberships to public facet-to-label values."""
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.project_id == project_id)
        .order_by(grouping_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not isinstance(payload, Mapping):
        return {}
    result: dict[uuid.UUID, dict[str, str]] = {}
    for facet, facet_data in payload.items():
        if not isinstance(facet, str) or not isinstance(facet_data, Mapping):
            continue
        for group in facet_data.get("groups", []):
            if not isinstance(group, Mapping) or not isinstance(group.get("label"), str):
                continue
            members = group.get("member_finding_ids")
            if not isinstance(members, list):
                continue
            for member in members:
                try:
                    result.setdefault(uuid.UUID(str(member)), {})[facet] = group["label"]
                except (TypeError, ValueError):
                    continue
    return result


_EVENT_KINDS = {
    "component.completed",
    "component.failed",
    "component.skipped",
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
        "component.completed": "Completed an evidence-base step.",
        "component.failed": "An evidence-base step failed.",
        "component.skipped": "Skipped an evidence-base step.",
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
    characterisation_themes = _characterisation_theme_refs(conn, project_id, synthesis)
    grouping_themes = _grouping_theme_refs(conn, project_id, synthesis)
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
    block_rows = (
        {
            row.block_id: row
            for row in conn.execute(
                select(
                    block.c.block_id,
                    block.c.content,
                    block.c.summary,
                    block.c.summary_status,
                ).where(block.c.block_id.in_(ids))
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
    # Bibliographic authority is the document's ENVELOPE snapshot; a cited
    # full-text snapshot is only the textual authority (its metadata carries
    # fetch facts, never a title). Every display read resolves through the
    # envelope — unconditionally, not as a fallback.
    snapshot_to_pss: dict[uuid.UUID, uuid.UUID] = {}
    pss_to_envelope: dict[uuid.UUID, uuid.UUID] = {}
    for row in conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
        ).where(project_source_snapshot.c.project_id == project_id)
    ).all():
        snapshot_to_pss[row.source_snapshot_id] = row.project_source_snapshot_id
        pss_to_envelope[row.project_source_snapshot_id] = row.source_snapshot_id
        if row.full_text_snapshot_id is not None:
            snapshot_to_pss[row.full_text_snapshot_id] = row.project_source_snapshot_id

    def _envelope_id(snapshot_id: uuid.UUID) -> uuid.UUID:
        pss_id = snapshot_to_pss.get(snapshot_id)
        return pss_to_envelope.get(pss_id, snapshot_id) if pss_id is not None else snapshot_id

    envelope_ids = {_envelope_id(snapshot_id) for snapshot_id in snapshots}
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
                ).where(source_snapshot.c.source_snapshot_id.in_(envelope_ids))
            ).all()
        }
        if envelope_ids
        else {}
    )
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
    # The classified evidence type is the appraisal rubric's scoring input —
    # surfaced with the label so the UI can say WHY a citation carries a band.
    citation_classifications = _latest_row_by_id(
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
            pss_id = snapshot_to_pss.get(snapshot_id)
            # Reference identity is the DOCUMENT, not the snapshot: abstract-
            # and full-text-grounded quotes from one source share one entry.
            doc_key = pss_id if pss_id is not None else snapshot_id
            if doc_key not in refs:
                refs[doc_key] = len(refs) + 1
                reference_order.append(doc_key)
            source_meta, locator_text = meta.get(_envelope_id(snapshot_id), ({}, "Unknown source"))
            score_row = appraisal.get(pss_id) if pss_id is not None else None
            payload = row.payload if isinstance(row.payload, Mapping) else {}
            claim_citations.append(
                CitationOut(
                    citation_id=cited.citation_id,
                    n=refs[doc_key],
                    source_id=pss_id,
                    source_title=_title(source_meta, locator_text),
                    quote=cited.quote,
                    grounding_tier=cast(str | None, payload.get("verdict"))
                    if isinstance(payload.get("verdict"), str)
                    else None,
                    grounding_rationale=cast(str, payload.get("rationale"))
                    if isinstance(payload.get("rationale"), str)
                    else None,
                    appraisal_label=SCORE_LABELS.get(score_row.quality_score)
                    if score_row
                    else None,
                    evidence_type=(
                        classification_row.primary_evidence_type
                        if pss_id is not None
                        and (classification_row := citation_classifications.get(pss_id)) is not None
                        else None
                    ),
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
                weakly_grounded=_weakly_grounded(row.payload),
                gap=_gap_out(row.payload),
                theme=_theme_out(row.payload, characterisation_themes, grouping_themes),
            )
        )
    section_entries: dict[tuple[str, str, str | None], list[uuid.UUID]] = {}
    for spec, block_id in parsed_specs:
        role: str = cast(
            str,
            spec.get("role")
            if spec.get("role") in {"key_findings", "standard", "conclusions"}
            else "standard",
        )
        title = cast(str, spec.get("title") or "")
        focus = cast(str | None, spec.get("focus")) if isinstance(spec.get("focus"), str) else None
        section_entries.setdefault((title, role, focus), []).append(block_id)
    sections: list[SectionOut] = []
    for (title, role, focus), section_block_ids in section_entries.items():
        single_block = block_rows.get(section_block_ids[0]) if len(section_block_ids) == 1 else None
        sections.append(
            SectionOut(
                title=title,
                role=cast(Any, role),
                focus=focus,
                blocks=[
                    BlockOut(
                        block_id=block_id,
                        prose=block_rows[block_id].content if block_id in block_rows else "",
                        claims=claims_by_block.get(block_id, []),
                    )
                    for block_id in section_block_ids
                ],
                summary=single_block.summary if single_block is not None else None,
                summary_status=(
                    cast(Any, single_block.summary_status) if single_block is not None else None
                ),
            )
        )
    refs_out = []
    for doc_key in reference_order:
        # doc_key is a pss id (envelope via pss_to_envelope) or, for a
        # snapshot with no project edge, the snapshot id itself.
        ref_entry = meta.get(pss_to_envelope.get(doc_key, doc_key))
        ref_meta, ref_locator = ref_entry if ref_entry is not None else ({}, "Unknown source")
        refs_out.append(
            ReferenceOut(
                n=refs[doc_key],
                title=_title(ref_meta, ref_locator),
                year=_year(ref_meta),
                venue=_venue(ref_meta),
                # A missed metadata lookup has only the display placeholder —
                # never let that fall through _url's locator rung as a "URL".
                url=_url(ref_meta, ref_locator) if ref_entry is not None else None,
            )
        )
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
        summary=cast(str | None, artefact_row["summary"]),
        summary_status=cast(Any, artefact_row["summary_status"]),
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


def _weakly_grounded(payload: Any) -> bool | None:
    """Project stored grounding warnings without inventing a verification result."""
    if not isinstance(payload, Mapping):
        return None
    for key in ("weakly_grounded", "quote_unverified"):
        value = payload.get(key)
        if isinstance(value, bool):
            return value
    anchors = payload.get("anchors")
    if isinstance(anchors, list):
        statuses = [item.get("match_status") for item in anchors if isinstance(item, Mapping)]
        if statuses:
            return any(status != "exact" for status in statuses)
    return None


def _gap_out(payload: Any) -> GapOut | None:
    """Return the approved structured claim gap, or omit malformed legacy payloads."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("gap"), Mapping):
        return None
    gap = payload["gap"]
    caveat = gap.get("caveat")
    result: dict[str, Any] = {}
    if isinstance(gap.get("grade"), str):
        result["grade"] = gap["grade"]
    if isinstance(caveat, Mapping):
        caveat_fields = {
            key: caveat[key]
            for key in ("search_space", "adequacy_verdict", "verdict_origin")
            if isinstance(caveat.get(key), str)
        }
        if caveat_fields:
            result["caveat"] = caveat_fields
    if isinstance(gap.get("inferred"), bool):
        result["inferred"] = gap["inferred"]
    return GapOut.model_validate(result) if result else None


def _characterisation_theme_refs(
    conn: Connection, project_id: uuid.UUID, synthesis: Mapping[str, Any]
) -> dict[str, ThemeRefItemOut]:
    """Return the artefact's own characterisation themes keyed by durable ids.

    Pinned to the synthesis row's (evidence_scope_id, characterisation_run_id)
    FK — "latest by created_at" let a later run's reused theme ids relabel an
    older committed artefact (review, 2026-07-29). No characterisation on the
    synthesis row means no themes to resolve.
    """
    if synthesis.get("characterisation_run_id") is None:
        return {}
    payload = conn.execute(
        select(characterisation_result.c.themes)
        .where(characterisation_result.c.project_id == project_id)
        .where(characterisation_result.c.evidence_scope_id == synthesis["evidence_scope_id"])
        .where(characterisation_result.c.run_id == synthesis["characterisation_run_id"])
    ).scalar_one_or_none()
    if not isinstance(payload, Mapping) or not isinstance(payload.get("themes"), list):
        return {}
    source_refs = _theme_sources_for_project_source_snapshots(
        conn,
        project_id,
        {
            member_id
            for item in payload["themes"]
            if isinstance(item, Mapping)
            for member_id in _uuid_members(item.get("member_ids"))
        },
    )
    result: dict[str, ThemeRefItemOut] = {}
    for item in payload["themes"]:
        if not isinstance(item, Mapping) or not isinstance(item.get("name"), str):
            continue
        theme_id = item.get("theme_id") or item.get("id") or item["name"]
        if not isinstance(theme_id, str) or not theme_id:
            continue
        description = item.get("description")
        size = item.get("size")
        result[theme_id] = ThemeRefItemOut(
            name=item["name"],
            description=description if isinstance(description, str) else None,
            size=size if isinstance(size, int) and not isinstance(size, bool) else None,
            sources=_resolved_theme_sources(item.get("member_ids"), source_refs),
        )
    return result


def _grouping_theme_refs(
    conn: Connection, project_id: uuid.UUID, synthesis: Mapping[str, Any]
) -> dict[str, ThemeRefItemOut]:
    """Return the artefact's own facet groups keyed by their durable group ids.

    Pinned to the synthesis row's (evidence_scope_id, grouping_run_id) FK for
    the same reason as `_characterisation_theme_refs`.
    """
    if synthesis.get("grouping_run_id") is None:
        return {}
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.project_id == project_id)
        .where(grouping_result.c.evidence_scope_id == synthesis["evidence_scope_id"])
        .where(grouping_result.c.run_id == synthesis["grouping_run_id"])
    ).scalar_one_or_none()
    if not isinstance(payload, Mapping):
        return {}
    finding_ids = {
        member_id
        for facet_payload in payload.values()
        if isinstance(facet_payload, Mapping)
        if isinstance(facet_payload.get("groups"), list)
        for group in facet_payload.get("groups", [])
        if isinstance(group, Mapping)
        for member_id in _uuid_members(group.get("member_finding_ids"))
    }
    source_refs = _theme_sources_for_findings(conn, project_id, finding_ids)
    result: dict[str, ThemeRefItemOut] = {}
    for facet, facet_payload in payload.items():
        if not isinstance(facet, str) or not isinstance(facet_payload, Mapping):
            continue
        groups = facet_payload.get("groups")
        if not isinstance(groups, list):
            continue
        for group in groups:
            if (
                not isinstance(group, Mapping)
                or not isinstance(group.get("group_id"), str)
                or not isinstance(group.get("label"), str)
            ):
                continue
            description = group.get("description")
            size = group.get("size")
            group_facet = group.get("facet")
            result[group["group_id"]] = ThemeRefItemOut(
                name=group["label"],
                description=description if isinstance(description, str) else None,
                size=size if isinstance(size, int) and not isinstance(size, bool) else None,
                facet=group_facet if isinstance(group_facet, str) else facet,
                sources=_resolved_theme_sources(group.get("member_finding_ids"), source_refs),
            )
    return result


def _uuid_members(values: Any) -> list[uuid.UUID]:
    """Parse the durable UUID member identifiers in their stored order."""
    if not isinstance(values, list):
        return []
    result: list[uuid.UUID] = []
    for value in values:
        try:
            result.append(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return result


def _resolved_theme_sources(
    member_ids: Any, source_refs: Mapping[uuid.UUID, ThemeSourceOut]
) -> list[ThemeSourceOut] | None:
    """Project resolvable member sources once, preserving stored member order."""
    if not isinstance(member_ids, list):
        return None
    result: list[ThemeSourceOut] = []
    seen: set[uuid.UUID] = set()
    for member_id in _uuid_members(member_ids):
        source = source_refs.get(member_id)
        if source is None or source.source_id in seen:
            continue
        seen.add(source.source_id)
        result.append(source)
    return result


def _theme_sources_for_project_source_snapshots(
    conn: Connection, project_id: uuid.UUID, source_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ThemeSourceOut]:
    """Map project-source-snapshot ids to the envelope source display details."""
    if not source_ids:
        return {}
    rows = conn.execute(
        select(
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
        .where(
            project_source_snapshot.c.project_id == project_id,
            project_source_snapshot.c.project_source_snapshot_id.in_(source_ids),
        )
    ).all()
    return {
        row.project_source_snapshot_id: ThemeSourceOut(
            source_id=row.project_source_snapshot_id,
            title=_title(
                row.metadata if isinstance(row.metadata, Mapping) else {}, row.source_locator
            ),
        )
        for row in rows
    }


def _theme_sources_for_findings(
    conn: Connection, project_id: uuid.UUID, finding_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ThemeSourceOut]:
    """Map finding ids to their sources through the findings read-model join."""
    if not finding_ids:
        return {}
    result: dict[uuid.UUID, ThemeSourceOut] = {}
    for finding in (intervention_outcome_finding, implementation_context_finding):
        rows = conn.execute(
            select(
                finding.c.finding_id,
                source_extraction_record.c.project_source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(_finding_source_join(finding))
            .where(finding.c.project_id == project_id, finding.c.finding_id.in_(finding_ids))
        ).all()
        for row in rows:
            metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
            result[row.finding_id] = ThemeSourceOut(
                source_id=row.project_source_snapshot_id,
                title=_title(metadata, row.source_locator),
            )
    return result


def _theme_out(
    payload: Any,
    characterisation_themes: Mapping[str, ThemeRefItemOut],
    grouping_themes: Mapping[str, ThemeRefItemOut],
) -> ThemeRefOut | None:
    """Resolve a theme claim's durable references, omitting stale references."""
    if not isinstance(payload, Mapping) or not isinstance(payload.get("theme"), Mapping):
        return None
    theme = payload["theme"]
    source = theme.get("source")
    referenced_ids = theme.get("referenced_ids")
    if source not in {"characterisation", "grouping"} or not isinstance(referenced_ids, list):
        return None
    references = characterisation_themes if source == "characterisation" else grouping_themes
    items = [
        references[ref] for ref in referenced_ids if isinstance(ref, str) and ref in references
    ]
    if not items:
        return None
    base = theme.get("base")
    return ThemeRefOut(
        source=source,
        base=base if isinstance(base, str) else None,
        items=items,
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
    backend_names = _coverage_backend_names(row["backends"])
    base = {
        "stop_condition": row["stop_condition"],
        "adequacy_verdict": row["adequacy_verdict"],
        "verdict_origin": row["verdict_origin"],
        "backends": backend_names,
    }
    counts = funnel_out(conn, project_id).model_dump(include={"found", "relevant", "screened_out"})
    base["counts"] = counts
    adequacy = (
        "Coverage was judged adequate."
        if row["adequacy_verdict"] == "adequate"
        else "Coverage was judged inadequate."
    )
    stop_sentence = {
        "completed": "Searching completed.",
    }.get(
        row["stop_condition"],
        f"Searching stopped because {row['stop_condition'].replace('_', ' ')}.",
    )
    return CoverageOut(
        sentence=f"{stop_sentence} {adequacy}",
        base=base,
        backends=backend_names,
        backends_detail=_backend_details(
            conn, project_id, row["acquired_by_run_id"], backend_names
        ),
    )


def _public_backend_name(value: str) -> str | None:
    """Translate a durable backend key into the closed public vocabulary."""
    return {"openalex": "OpenAlex", "overton": "Overton"}.get(value)


def _coverage_backend_names(backends: Any) -> list[str]:
    """Return coverage-record backends without trust class or execution mode."""
    if not isinstance(backends, list):
        return []
    result: list[str] = []
    for item in backends:
        key = item.get("backend") if isinstance(item, Mapping) else None
        name = _public_backend_name(key) if isinstance(key, str) else None
        if name is not None and name not in result:
            result.append(name)
    return result


def _backend_details(
    conn: Connection,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    backend_names: list[str],
) -> list[CoverageBackendDetailOut]:
    """Project post-run query counts and the documented project-wide relevance wart."""
    events = (
        conn.execute(
            select(event_log.c.payload).where(
                event_log.c.project_id == project_id,
                event_log.c.run_id == run_id,
                event_log.c.event_type == "search.executed",
            )
        )
        .scalars()
        .all()
    )
    queries: dict[str, list[CoverageQueryOut]] = {name: [] for name in backend_names}
    for payload in events:
        if not isinstance(payload, Mapping):
            continue
        backend = payload.get("backend")
        name = _public_backend_name(backend) if isinstance(backend, str) else None
        query, results = payload.get("query"), payload.get("result_count")
        if name not in queries or not isinstance(query, str) or not isinstance(results, int):
            continue
        queries[name].append(CoverageQueryOut(query=query, results=results))
    effective = effective_screen_rows()
    relevance_rows = (
        conn.execute(
            select(source_snapshot.c.metadata)
            .select_from(
                effective.join(
                    project_source_snapshot,
                    effective.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id,
                ).join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(effective.c.project_id == project_id, effective.c.status == "relevant")
        )
        .scalars()
        .all()
    )
    relevant: Counter[str] = Counter()
    for metadata in relevance_rows:
        backend = metadata.get("backend") if isinstance(metadata, Mapping) else None
        name = _public_backend_name(backend) if isinstance(backend, str) else None
        if name is not None:
            relevant[name] += 1
    return [
        CoverageBackendDetailOut(
            backend=name,
            results=sum(query.results for query in queries[name]),
            relevant=relevant[name],
            queries=queries[name],
        )
        for name in backend_names
    ]


def source_dossier_out(
    conn: Connection, project_id: uuid.UUID, source_id: uuid.UUID
) -> SourceDossierOut | None:
    """Materialize one owner-authorized source dossier from durable records only."""
    row = (
        conn.execute(
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
                project_source_snapshot.join(
                    source_snapshot,
                    project_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(
                project_source_snapshot.c.project_id == project_id,
                project_source_snapshot.c.project_source_snapshot_id == source_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    metadata = row["metadata"] if isinstance(row["metadata"], Mapping) else {}
    screen = _effective_screens(conn, project_id).get(source_id)
    screen_reasons, classification_reasons = _source_reason_maps(conn, project_id)
    selection = _latest_selection(conn, project_id)
    selected = _selected_ids(selection["selected"]) if selection is not None else set()
    extracted = (
        conn.execute(
            select(source_extraction_record.c.extraction_record_id)
            .where(
                source_extraction_record.c.project_id == project_id,
                source_extraction_record.c.project_source_snapshot_id == source_id,
                source_extraction_record.c.finding_count > 0,
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    synthesis = _latest_synthesis(conn, project_id)
    cited_ids = (
        _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
    )
    cited = row["source_snapshot_id"] in cited_ids or row["full_text_snapshot_id"] in cited_ids
    if cited:
        status, reason = "cited", None
    elif extracted:
        status, reason = "findings_extracted", None
    elif source_id in selected:
        status, reason = "selected", None
    elif row["full_text_status"] == "ingested":
        status, reason = "read_in_full", None
    elif (
        screen is not None
        and screen.status == "relevant"
        and row["full_text_status"] in {"fetch_failed", "parse_failed"}
    ):
        status, reason = "unavailable", row["full_text_error"]
    elif screen is not None and screen.status == "relevant":
        status, reason = ("not_selected", None) if selection is not None else ("relevant", None)
    elif screen is not None:
        status, reason = "screened_out", screen.screen_basis
    else:
        status, reason = "found", None
    classification = _latest_row_by_id(
        conn.execute(
            select(
                source_classification_result.c.project_source_snapshot_id,
                source_classification_result.c.primary_evidence_type,
                source_classification_result.c.classified_at,
            ).where(
                source_classification_result.c.project_id == project_id,
                source_classification_result.c.project_source_snapshot_id == source_id,
            )
        ).all(),
        "project_source_snapshot_id",
        "classified_at",
    ).get(source_id)
    appraisal = _latest_row_by_id(
        conn.execute(
            select(
                source_appraisal_result.c.project_source_snapshot_id,
                source_appraisal_result.c.quality_score,
                source_appraisal_result.c.appraised_at,
            ).where(
                source_appraisal_result.c.project_id == project_id,
                source_appraisal_result.c.project_source_snapshot_id == source_id,
            )
        ).all(),
        "project_source_snapshot_id",
        "appraised_at",
    ).get(source_id)
    provider_value = metadata.get("provider_fields")
    provider: Mapping[str, Any] = provider_value if isinstance(provider_value, Mapping) else {}
    abstract = _metadata_text(metadata, "abstract")
    raw_abstract_source = _metadata_text(metadata, "abstract_source")
    tags = [
        SourceTagOut(tag=tag_row.tag, tag_type=tag_row.tag_type, asserted_by=tag_row.asserted_by)
        for tag_row in conn.execute(
            select(source_tag.c.tag, source_tag.c.tag_type, source_tag.c.asserted_by)
            .where(
                source_tag.c.project_id == project_id,
                source_tag.c.project_source_snapshot_id == source_id,
            )
            .order_by(source_tag.c.tag_type, source_tag.c.tag, source_tag.c.asserted_by)
        ).all()
    ]
    return SourceDossierOut(
        source_id=source_id,
        title=_title(metadata, row["source_locator"]),
        year=_year(metadata),
        venue=_venue(metadata),
        origin=_origin(row["origin"], metadata),
        status=cast(Any, status),
        status_reason=reason,
        evidence_type=classification.primary_evidence_type if classification else None,
        appraisal_tier=SCORE_LABELS.get(appraisal.quality_score) if appraisal else None,
        cited=cited,
        url=_url(metadata, row["source_locator"]),
        screen_confidence=screen.screen_decision_confidence if screen else None,
        screen_basis=screen.screen_basis if screen else None,
        screen_stage=screen.screen_stage if screen else None,
        screen_status=cast(Any, screen.status)
        if screen and screen.status in {"relevant", "not_relevant", "excluded_retracted"}
        else None,
        screen_reason=screen_reasons.get(source_id),
        classification_reason=classification_reasons.get(source_id),
        read_in_full=row["full_text_status"] == "ingested",
        abstract=abstract,
        abstract_source="llm_description"
        if raw_abstract_source == "llm_description"
        else "provider"
        if abstract is not None
        else None,
        publisher=_metadata_text(metadata, "publisher_org"),
        record_type=_metadata_text(metadata, "record_type"),
        language=_metadata_text(metadata, "language"),
        doi=_metadata_text(metadata, "doi"),
        cited_by_count=provider.get("cited_by_count")
        if isinstance(provider.get("cited_by_count"), int)
        and not isinstance(provider.get("cited_by_count"), bool)
        else None,
        fwci=provider.get("fwci")
        if isinstance(provider.get("fwci"), (float, int))
        and not isinstance(provider.get("fwci"), bool)
        else None,
        tags=tags,
        cited_in=_source_cited_in(conn, project_id, source_id),
    )


def _source_cited_in(
    conn: Connection, project_id: uuid.UUID, source_id: uuid.UUID
) -> list[CitedInOut]:
    """Return only latest-synthesis claims citing either snapshot linked to a source."""
    synthesis = _latest_synthesis(conn, project_id)
    if synthesis is None:
        return []
    specs = synthesis["blocks"] if isinstance(synthesis["blocks"], list) else []
    titles = {
        uuid.UUID(item["block_id"]): item.get("title", "")
        for item in specs
        if isinstance(item, Mapping) and isinstance(item.get("block_id"), str)
    }
    if not titles:
        return []
    source = conn.execute(
        select(
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
        ).where(
            project_source_snapshot.c.project_id == project_id,
            project_source_snapshot.c.project_source_snapshot_id == source_id,
        )
    ).one_or_none()
    if source is None:
        return []
    snapshot_ids = [source.source_snapshot_id]
    if source.full_text_snapshot_id is not None:
        snapshot_ids.append(source.full_text_snapshot_id)
    rows = conn.execute(
        select(addressable_unit.c.content, citation.c.quote, annotation.c.block_id)
        .select_from(
            citation.join(annotation, citation.c.annotation_id == annotation.c.annotation_id)
            .join(addressable_unit, annotation.c.unit_id == addressable_unit.c.unit_id)
            .join(chunk, citation.c.chunk_id == chunk.c.chunk_id)
        )
        .where(annotation.c.block_id.in_(titles), chunk.c.source_snapshot_id.in_(snapshot_ids))
        .order_by(citation.c.created_at, citation.c.citation_id)
    ).all()
    return [
        CitedInOut(
            claim=row.content, quote=row.quote, section_title=cast(str, titles[row.block_id])
        )
        for row in rows
    ]


def chunk_context_out(
    conn: Connection, project_id: uuid.UUID, citation_id: uuid.UUID
) -> ChunkContextOut | None:
    """Return at most 800 characters either side of a cited, anchored source span."""
    row = conn.execute(
        select(citation.c.quote, chunk.c.content, chunk.c.sequence, chunk.c.source_snapshot_id)
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
        previous=_adjacent_chunk(conn, row.source_snapshot_id, row.sequence - 1),
        next=_adjacent_chunk(conn, row.source_snapshot_id, row.sequence + 1),
        year=_chunk_year(conn, project_id, row.source_snapshot_id),
        venue=_chunk_venue(conn, project_id, row.source_snapshot_id),
    )


def _adjacent_chunk(conn: Connection, source_snapshot_id: uuid.UUID, sequence: int) -> str | None:
    """Return one adjacent chunk's content when the sequence exists."""
    return conn.execute(
        select(chunk.c.content).where(
            chunk.c.source_snapshot_id == source_snapshot_id, chunk.c.sequence == sequence
        )
    ).scalar_one_or_none()


def _chunk_metadata(
    conn: Connection, project_id: uuid.UUID, source_snapshot_id: uuid.UUID
) -> Mapping[str, Any]:
    """Find the envelope metadata for either immutable snapshot linked by a PSS."""
    metadata = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(
            project_source_snapshot.c.project_id == project_id,
            (project_source_snapshot.c.source_snapshot_id == source_snapshot_id)
            | (project_source_snapshot.c.full_text_snapshot_id == source_snapshot_id),
        )
    ).scalar_one_or_none()
    return metadata if isinstance(metadata, Mapping) else {}


def _chunk_year(
    conn: Connection, project_id: uuid.UUID, source_snapshot_id: uuid.UUID
) -> int | None:
    """Read the publication year for a chunk through its project source link."""
    return _year(_chunk_metadata(conn, project_id, source_snapshot_id))


def _chunk_venue(
    conn: Connection, project_id: uuid.UUID, source_snapshot_id: uuid.UUID
) -> str | None:
    """Read the venue for a chunk through its project source link."""
    return _venue(_chunk_metadata(conn, project_id, source_snapshot_id))
