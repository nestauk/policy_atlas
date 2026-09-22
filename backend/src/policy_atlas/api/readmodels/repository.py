"""Batched SQLAlchemy Core projections for the API's durable read models."""

from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from functools import cmp_to_key
from typing import Any, Literal, cast

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas.api.contract import (
    EVIDENCE_STATUS_INCLUDED,
    AmbitionBandOut,
    ArtefactOut,
    AuthorshipOut,
    BlockOut,
    CaseStudyCardOut,
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
    EvidenceProfileOut,
    ExclusionOut,
    FacetGroupsOut,
    FindingOut,
    FunnelOut,
    GapOut,
    GroupOut,
    GroupsOut,
    GuessOut,
    IcfFindingOut,
    InScopeOut,
    IofFindingOut,
    IofStatisticsOut,
    JudgementOut,
    LandscapeOut,
    LonglistCountsOut,
    LonglistOut,
    LonglistThemeOut,
    MostRelevantNoteOut,
    OptionDesignOut,
    OptionDocumentOut,
    OptionOut,
    OptionSummaryOut,
    Page,
    PageMeta,
    ReferenceOut,
    RelationOut,
    SectionOut,
    SourceDossierOut,
    SourceTagOut,
    ThemeOut,
    ThemeRefItemOut,
    ThemeRefOut,
    ThemeSourceOut,
    WhereTriedOut,
)
from policy_atlas.api.lifecycle import LIFECYCLE_EVENT_KINDS, both_generations
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
    finding_reference_union,
    grouping_result,
    implementation_context_finding,
    intervention_outcome_finding,
    intervention_profile_record,
    longlist_result,
    option,
    option_membership,
    option_relation,
    runs,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_extraction_record,
    source_snapshot,
    source_tag,
    synthesis_result,
    task_plan,
    task_source_snapshot,
    tss_owns_snapshot,
)
from policy_atlas.evidence_search.assess.appraise import SCORE_LABELS
from policy_atlas.evidence_search.assess.screen import effective_screen_rows
from policy_atlas.evidence_search.extract.quote_verify import build_basis, locate_unique_span
from policy_atlas.options_scoping.labels import DocumentLabels, labels_for_snapshots
from policy_atlas.options_scoping.longlist.coverage import empty_coverage
from policy_atlas.options_scoping.longlist.lever_types import (
    AMBITION_BANDS,
    AMBITION_LABELS,
    LEVER_TYPE_KEYS,
    TAXONOMY_VERSION,
)
from policy_atlas.options_scoping.longlist.where_tried import where_codes, where_group
from policy_atlas.runtime.capability_registry import OPTIONS_SCOPING, validate_plan
from policy_atlas.runtime.scoping_plan import TRANSFERABILITY_DEFAULT, ScopingPlan, find_default
from policy_atlas.runtime.steering_events import canonical_actor
from policy_atlas.runtime.steering_history import steering_history


def _metadata_text(metadata: Mapping[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) and value else None


def _title(metadata: Mapping[str, Any], locator: str) -> str:
    return _metadata_text(metadata, "title") or locator


def _abstract_fields(
    metadata: Mapping[str, Any],
) -> tuple[str | None, Literal["provider", "llm_description"] | None]:
    """The document's description and its provenance label, dossier-identical."""
    abstract = _metadata_text(metadata, "abstract")
    if abstract is None:
        return None, None
    raw_source = _metadata_text(metadata, "abstract_source")
    return abstract, "llm_description" if raw_source == "llm_description" else "provider"


def _year(metadata: Mapping[str, Any]) -> int | None:
    value = metadata.get("publication_year", metadata.get("year"))
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _venue(metadata: Mapping[str, Any]) -> str | None:
    return _metadata_text(metadata, "venue") or _metadata_text(metadata, "journal")


def _institution_names(raw: Any) -> list[str]:
    """Return string institution names; a non-list shape (e.g. a bare string,
    which would iterate per character) is malformed and yields none."""
    if not isinstance(raw, list):
        return []
    return [i for i in raw if isinstance(i, str) and i]


def _authorships(metadata: Mapping[str, Any]) -> list[AuthorshipOut]:
    """Return display authorships for a source, first non-empty rung wins.

    Args:
        metadata: Envelope (or chunk-owning envelope) metadata.

    Returns:
        Named authors with their institutions (OpenAlex-shaped provider
        data), else bare author names (a plainer provider shape), else a
        single Overton corporate author (the issuing organisation), else
        an empty list. Malformed provider shapes are skipped, never raised.
    """
    provider = metadata.get("provider_fields")
    provider = provider if isinstance(provider, Mapping) else {}
    raw_authorships = provider.get("authorships")
    if isinstance(raw_authorships, list):
        named = [
            AuthorshipOut(
                name=entry["author_name"],
                institutions=_institution_names(entry.get("institutions")),
            )
            for entry in raw_authorships
            if isinstance(entry, Mapping)
            and isinstance(entry.get("author_name"), str)
            and entry.get("author_name")
        ]
        if named:
            return named
    raw_authors = provider.get("authors")
    names: list[str] = []
    if isinstance(raw_authors, str) and raw_authors:
        names = [raw_authors]
    elif isinstance(raw_authors, list):
        names = [a for a in raw_authors if isinstance(a, str) and a]
    if names:
        return [AuthorshipOut(name=name) for name in names]
    publisher_org = _metadata_text(metadata, "publisher_org")
    if _metadata_text(metadata, "backend") == "overton" and publisher_org:
        return [AuthorshipOut(name=publisher_org)]
    return []


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


#: Residual bucket for sources whose provider sent no publisher country (task
#: 031). A stable, public-vocabulary string: the frontend must not rename or
#: drop it, or the chart stops adding up to the population it draws.
GEOGRAPHY_NOT_REPORTED = "Not reported"


def publication_country(metadata: Mapping[str, Any]) -> str | None:
    """Read a document's publication country from its snapshot metadata.

    Shared by the source-geography chart and the options-scoping in-scope
    check (task 045, S9). The value is the provider's own: an ISO-3166
    alpha-2 code from OpenAlex, an Overton display name ("UK") from Overton.

    Args:
        metadata: The snapshot's envelope metadata.

    Returns:
        The publication country, or ``None`` when the provider sent none.
    """
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


def latest_row_by_id(rows: Iterable[Any], id_key: str, time_key: str) -> dict[uuid.UUID, Any]:
    """Pick the latest row per ``id_key``, comparing ``time_key`` timestamps.

    The shared effective-row discipline for every read model that resolves
    one durable id to its latest appraisal/classification/screen row
    (task 029 delta-review: exported so ``chat_turns`` reuses this instead of
    a second, parallel implementation).

    Args:
        rows: Rows carrying at least the ``id_key`` and ``time_key`` fields.
        id_key: Attribute name to group rows by.
        time_key: Attribute name whose later value wins within a group.

    Returns:
        A mapping from each distinct ``id_key`` value to its latest row.
    """
    latest: dict[uuid.UUID, Any] = {}
    for row in rows:
        key = cast(uuid.UUID, getattr(row, id_key))
        previous = latest.get(key)
        if previous is None or getattr(row, time_key) > getattr(previous, time_key):
            latest[key] = row
    return latest


def _latest_synthesis(conn: Connection, task_id: uuid.UUID) -> Any | None:
    return (
        conn.execute(
            select(synthesis_result)
            .where(synthesis_result.c.task_id == task_id)
            .order_by(
                synthesis_result.c.created_at.desc(), synthesis_result.c.synthesis_result_id.desc()
            )
            .limit(1)
        )
        .mappings()
        .one_or_none()
    )


def _latest_selection(conn: Connection, task_id: uuid.UUID) -> Any | None:
    return (
        conn.execute(
            select(selection_result)
            .where(selection_result.c.task_id == task_id)
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
        raw = item.get("tss_id")
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


def _effective_screens(conn: Connection, task_id: uuid.UUID) -> dict[uuid.UUID, Any]:
    effective = effective_screen_rows()
    rows = conn.execute(select(effective).where(effective.c.task_id == task_id)).all()
    return latest_row_by_id(rows, "task_source_snapshot_id", "screened_at")


def funnel_out(conn: Connection, task_id: uuid.UUID) -> FunnelOut:
    """Build full-flow counts, preserving missing-stage absence as ``None``."""
    found = int(
        conn.execute(
            select(func.count())
            .select_from(task_source_snapshot)
            .where(task_source_snapshot.c.task_id == task_id)
        ).scalar_one()
    )
    coverage_exists = (
        conn.execute(
            select(search_coverage_record.c.search_coverage_record_id)
            .where(search_coverage_record.c.task_id == task_id)
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    effective = _effective_screens(conn, task_id)
    statuses = [row.status for row in effective.values()]
    appraised = int(
        conn.execute(
            select(func.count())
            .select_from(source_appraisal_result)
            .where(source_appraisal_result.c.task_id == task_id)
        ).scalar_one()
    )
    full_text_rows = int(
        conn.execute(
            select(func.count())
            .select_from(task_source_snapshot)
            .where(
                task_source_snapshot.c.task_id == task_id,
                task_source_snapshot.c.full_text_status != "not_attempted",
            )
        ).scalar_one()
    )
    selection = _latest_selection(conn, task_id)
    extraction = conn.execute(
        select(extraction_result.c.extraction_result_id)
        .where(extraction_result.c.task_id == task_id)
        .limit(1)
    ).scalar_one_or_none()
    finding_count = int(
        conn.execute(
            select(func.count())
            .select_from(intervention_outcome_finding)
            .where(intervention_outcome_finding.c.task_id == task_id)
        ).scalar_one()
    ) + int(
        conn.execute(
            select(func.count())
            .select_from(implementation_context_finding)
            .where(implementation_context_finding.c.task_id == task_id)
        ).scalar_one()
    )
    synthesis = _latest_synthesis(conn, task_id)
    return FunnelOut(
        found=found if found or coverage_exists else None,
        relevant=sum(status == "relevant" for status in statuses) if statuses else None,
        screened_out=sum(status != "relevant" for status in statuses) if statuses else None,
        quality_checked=appraised if appraised else None,
        read_in_full=int(
            conn.execute(
                select(func.count())
                .select_from(task_source_snapshot)
                .where(
                    task_source_snapshot.c.task_id == task_id,
                    task_source_snapshot.c.full_text_status == "ingested",
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
    conn: Connection, task_id: uuid.UUID, *, scope: Literal["cited"] | None = None
) -> LandscapeOut:
    """Return whole-screened-in or latest-artefact-cited distributions.

    Args:
        conn: Open database connection.
        task_id: Owning task.
        scope: ``"cited"`` restricts distributions to latest-artefact citations.

    Returns:
        Landscape distributions for the requested corpus scope.
    """
    relevant_ids = [
        key
        for key, value in _effective_screens(conn, task_id).items()
        if value.status == "relevant"
    ]
    if scope == "cited":
        synthesis = _latest_synthesis(conn, task_id)
        cited_snapshots = (
            _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
        )
        if cited_snapshots:
            relevant_ids = list(
                conn.execute(
                    select(task_source_snapshot.c.task_source_snapshot_id).where(
                        task_source_snapshot.c.task_id == task_id,
                        task_source_snapshot.c.task_source_snapshot_id.in_(relevant_ids),
                        # Membership against a SET of candidate snapshots, not
                        # equality against one column — tss_owns_snapshot's
                        # `==` shape doesn't fit; stays hand-written (task 029
                        # delta-review sweep).
                        (
                            task_source_snapshot.c.source_snapshot_id.in_(cited_snapshots)
                            | task_source_snapshot.c.full_text_snapshot_id.in_(cited_snapshots)
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
            task_source_snapshot.c.task_source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .select_from(
            # Explicit onclause: task_source_snapshot carries TWO FKs into
            # source_snapshot (envelope + full-text); the implicit join is ambiguous.
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_source_snapshot_id.in_(relevant_ids))
    ).all()
    labels = labels_for_snapshots(
        conn, task_id=task_id, tss_ids=[row.task_source_snapshot_id for row in base_rows]
    )
    types: Counter[str] = Counter()
    years: Counter[str] = Counter()
    geographies: Counter[str] = Counter()
    for row in base_rows:
        metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
        label = labels.get(row.task_source_snapshot_id)
        if label is not None and label.evidence_type is not None:
            types[label.evidence_type] += 1
        year = _year(metadata)
        if year is not None:
            years[str(year)] += 1
        # Honest absence (task 031, defect 3): a source whose provider sent no
        # publisher country is counted, never dropped, so the bars plus the
        # residual always equal the population drawn — at either scope, because
        # base_rows is already narrowed. An authorship country is never
        # substituted here; the slim authorships answer a different question.
        geography = publication_country(metadata)
        geographies[geography if geography is not None else GEOGRAPHY_NOT_REPORTED] += 1
    characterisation = conn.execute(
        select(characterisation_result.c.themes)
        .where(characterisation_result.c.task_id == task_id)
        .order_by(characterisation_result.c.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    themes: list[ThemeOut] = []
    relevant_id_set = set(relevant_ids)
    if isinstance(characterisation, Mapping) and isinstance(characterisation.get("themes"), list):
        for item in characterisation["themes"]:
            if isinstance(item, Mapping) and isinstance(item.get("name"), str):
                member_ids = _uuid_members(item.get("member_ids"))
                size: Any
                if scope == "cited":
                    size = sum(member_id in relevant_id_set for member_id in member_ids)
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


def groups_out(conn: Connection, task_id: uuid.UUID) -> GroupsOut:
    """Project the latest durable facet grouping payload."""
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.task_id == task_id)
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
    wins ('unsure' votes count toward relevant, mirroring `_vote_decision`).
    No agreeing rep -> no reason: a disagreeing rep's text can argue the
    opposite of the shown status (review 028, security lane).
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
    return None


def _source_reason_maps(
    conn: Connection, task_id: uuid.UUID
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
            event_log.c.task_id == task_id,
            event_log.c.event_type.in_(("source.screened", "source.classified")),
        )
        .order_by(event_log.c.sequence)
    ).all()
    screen_reasons: dict[uuid.UUID, str] = {}
    classification_reasons: dict[uuid.UUID, str] = {}
    for row in rows:
        payload = row.payload if isinstance(row.payload, Mapping) else {}
        try:
            tss_id = uuid.UUID(
                str(
                    payload.get("task_source_snapshot_id")
                    # Pre-038 rows carry the old key; `event_log` is never rewritten.
                    or payload.get("project_source_snapshot_id")
                )
            )
        except (TypeError, ValueError):
            continue
        if row.event_type == "source.classified":
            reason = payload.get("reason")
            if isinstance(reason, str) and reason:
                classification_reasons[tss_id] = reason
        else:
            status = payload.get("status")
            if status not in ("relevant", "not_relevant"):
                continue
            reason = _screen_event_reason(payload, status)
            if reason is not None:
                screen_reasons[tss_id] = reason
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
    task_id: uuid.UUID,
    page: int,
    page_size: int,
    *,
    statuses: Iterable[str] | None = None,
    cited: bool | None = None,
    sort: Literal["title", "year", "type", "strength", "status", "relevance"] | None = None,
    order: Literal["asc", "desc"] | None = None,
    theme: uuid.UUID | None = None,
    origin: str | None = None,
    evidence_type: str | None = None,
    strength: str | None = None,
    year_from: int | None = None,
    year_to: int | None = None,
) -> Page[EvidenceItemOut]:
    """Return one evidence page, deriving status task-wide before paging.

    `status`/`cited`/`theme` filters are collection-true: status is derived for
    every task source (bounded — one task's worth of rows, the
    `funnel_out` precedent) before filtering and paginating, so
    `total_items` reflects the filtered collection, never the unfiltered
    task total or the page size. Sorting likewise runs over that complete
    collection before pagination; ingestion order remains the
    stable tie-breaker.
    """
    target_statuses = _expand_evidence_statuses(statuses) if statuses else None
    rows = conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            task_source_snapshot.c.origin,
            task_source_snapshot.c.source_snapshot_id,
            task_source_snapshot.c.full_text_snapshot_id,
            task_source_snapshot.c.full_text_status,
            task_source_snapshot.c.full_text_error,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .select_from(
            # Explicit onclause — same two-FK ambiguity as landscape_out.
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(task_source_snapshot.c.task_id == task_id)
        .order_by(
            task_source_snapshot.c.ingested_at.desc(),
            task_source_snapshot.c.task_source_snapshot_id.desc(),
        )
    ).all()
    screens = _effective_screens(conn, task_id)
    screen_reasons, classification_reasons = _source_reason_maps(conn, task_id)
    # One resolver for every label reader (task 045, S5): own rows, then a
    # linked task's pinned walk for an inherited document, else absent.
    labels = labels_for_snapshots(
        conn, task_id=task_id, tss_ids=[row.task_source_snapshot_id for row in rows]
    )
    extracted = set(
        conn.execute(
            select(source_extraction_record.c.task_source_snapshot_id)
            .where(
                source_extraction_record.c.task_id == task_id,
                source_extraction_record.c.finding_count > 0,
            )
            .distinct()
        ).scalars()
    )
    selection = _latest_selection(conn, task_id)
    selected = _selected_ids(selection["selected"]) if selection is not None else set()
    synthesis = _latest_synthesis(conn, task_id)
    cited_snapshots = (
        _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
    )
    themed_sources = (
        set(
            conn.execute(
                select(source_tag.c.task_source_snapshot_id).where(
                    source_tag.c.task_id == task_id,
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
        screen = screens.get(row.task_source_snapshot_id)
        # Python-side membership over an already-fetched row + a precomputed
        # set, not a SQL join — tss_owns_snapshot doesn't fit here (task 029
        # delta-review sweep).
        row_cited = (
            row.source_snapshot_id in cited_snapshots
            or row.full_text_snapshot_id in cited_snapshots
        )
        if row_cited:
            status, reason = "cited", None
        elif row.task_source_snapshot_id in extracted:
            status, reason = "findings_extracted", None
        elif row.task_source_snapshot_id in selected:
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
        if themed_sources is not None and row.task_source_snapshot_id not in themed_sources:
            continue
        label = labels.get(row.task_source_snapshot_id)
        quality_score = label.quality_score if label is not None else None
        item_origin = _origin(row.origin, metadata)
        evidence_type_value = label.evidence_type if label is not None else None
        tier = SCORE_LABELS.get(quality_score) if quality_score is not None else None
        year_value = _year(metadata)
        if origin is not None and item_origin != origin:
            continue
        if evidence_type is not None and evidence_type_value != evidence_type:
            continue
        if strength is not None and tier != strength:
            continue
        # Year bounds drop unknown-year rows — a bounded view never implies
        # an unknown year satisfied the bound.
        if (year_from is not None or year_to is not None) and (
            year_value is None
            or (year_from is not None and year_value < year_from)
            or (year_to is not None and year_value > year_to)
        ):
            continue
        abstract, abstract_source = _abstract_fields(metadata)
        sortable_items.append(
            (
                EvidenceItemOut(
                    source_id=row.task_source_snapshot_id,
                    title=_title(metadata, row.source_locator),
                    year=year_value,
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
                    screen_reason=screen_reasons.get(row.task_source_snapshot_id),
                    classification_reason=classification_reasons.get(
                        row.task_source_snapshot_id
                    ),
                    read_in_full=row.full_text_status == "ingested",
                    abstract=abstract,
                    abstract_source=abstract_source,
                ),
                quality_score,
            )
        )
    if sort is not None:
        direction = order or ("desc" if sort in ("year", "relevance") else "asc")

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


def _relevance_rank(item: EvidenceItemOut) -> float | None:
    """The p(relevant) spectrum: descending order = confidently relevant →
    uncertain → confidently irrelevant (owner, 2026-08-05). Retracted pins to
    the bottom of the screened set; unscreened rows are nulls (always last).
    """
    if item.screen_status == "relevant":
        return item.screen_confidence if item.screen_confidence is not None else 0.5
    if item.screen_status == "not_relevant":
        return 1.0 - item.screen_confidence if item.screen_confidence is not None else 0.5
    if item.screen_status == "excluded_retracted":
        return -1.0
    return None


def _compare_evidence_sort(
    left: tuple[EvidenceItemOut, int | None],
    right: tuple[EvidenceItemOut, int | None],
    *,
    sort: Literal["title", "year", "type", "strength", "status", "relevance"],
    direction: Literal["asc", "desc"],
) -> int:
    """Compare two already-projected evidence rows with nulls always last."""
    left_item, left_score = left
    right_item, right_score = right
    left_value: str | int | float | None
    right_value: str | int | float | None
    if sort == "title":
        left_value, right_value = left_item.title.casefold(), right_item.title.casefold()
    elif sort == "year":
        left_value, right_value = left_item.year, right_item.year
    elif sort == "type":
        left_value, right_value = left_item.evidence_type, right_item.evidence_type
    elif sort == "strength":
        left_value, right_value = left_score, right_score
    elif sort == "relevance":
        left_value, right_value = _relevance_rank(left_item), _relevance_rank(right_item)
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
        right_rank = cast(float, right_value)
        result = -1 if left_value < right_rank else 1
    return result if direction == "asc" else -result


def _latest_relevance(conn: Connection, task_id: uuid.UUID) -> dict[str, str]:
    row = conn.execute(
        select(extraction_result.c.extraction_provenance)
        .where(extraction_result.c.task_id == task_id)
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
    task_id: uuid.UUID,
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
        .where(grouping_result.c.task_id == task_id)
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
    task_id: uuid.UUID,
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
        clauses: list[Any] = [finding.c.task_id == task_id]
        if source_id is not None:
            clauses.append(source_extraction_record.c.task_source_snapshot_id == source_id)
        return clauses

    iof_rows = (
        conn.execute(
            select(
                intervention_outcome_finding,
                source_extraction_record.c.task_source_snapshot_id,
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
                source_extraction_record.c.task_source_snapshot_id,
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
        conn, task_id, facet=facet, group=group, group_id=group_id
    )
    if group_filter_ids is not None:
        rows = [item for item in rows if item[1]["finding_id"] in group_filter_ids]
    total = len(rows)
    rows = rows[(page - 1) * page_size : page * page_size]
    relevance = _latest_relevance(conn, task_id)
    groups = _finding_groups(conn, task_id)
    items: list[FindingOut] = []
    for profile, row in rows:
        metadata = row["metadata"] if isinstance(row["metadata"], Mapping) else {}
        common = {
            "finding_id": row["finding_id"],
            "statement": row["intervention"] if profile == "iof" else row["claim"],
            "source_id": row["task_source_snapshot_id"],
            "source_title": _title(metadata, row["source_locator"]),
            "relevance": cast(Any, relevance.get(str(row["finding_id"]))),
            "quote": _grounding_value(row["grounding"], "quote"),
            "quote_verified": _grounding_value(row["grounding"], "quote_verified"),
            "chunk_id": _grounding_value(row["grounding"], "chunk_id"),
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
            task_source_snapshot,
            task_source_snapshot.c.task_source_snapshot_id
            == source_extraction_record.c.task_source_snapshot_id,
        )
        .join(
            source_snapshot,
            source_snapshot.c.source_snapshot_id == task_source_snapshot.c.source_snapshot_id,
        )
    )


def _grounding_value(grounding: Any, key: str) -> Any | None:
    """Return one honest grounding value from the first stored anchor."""
    if not isinstance(grounding, list) or not grounding or not isinstance(grounding[0], Mapping):
        return None
    value = grounding[0].get(key)
    if key == "quote_verified":
        return value if isinstance(value, bool) else None
    if key == "chunk_id":
        try:
            return uuid.UUID(str(value)) if value is not None else None
        except (TypeError, ValueError):
            return None
    return value if isinstance(value, str) else None


def _finding_groups(conn: Connection, task_id: uuid.UUID) -> dict[uuid.UUID, dict[str, str]]:
    """Map latest grouping memberships to public facet-to-label values."""
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.task_id == task_id)
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


#: The user's direct actions on the longlist (task 045, contract deliverable 9:
#: "every direct action is logged as the user's turn in History"). Written by
#: :mod:`policy_atlas.api.longlist_actions`, for the buttons and the chat verbs
#: alike.
OPTION_ADDED = "option.added"
OPTION_EXCLUDED = "option.excluded"
OPTION_INCLUDED = "option.included"
OPTION_EVENT_KINDS: tuple[str, ...] = (OPTION_ADDED, OPTION_EXCLUDED, OPTION_INCLUDED)


# The allowlisted audit events. The four lifecycle kinds appear under BOTH
# generations: `event_log` is append-only, so rows written before task 038 say
# `project.renamed` / `project.archived` and must still reach the read model.
_EVENT_KINDS = {
    "component.completed",
    "component.failed",
    "component.skipped",
    "search.executed",
    "run.opened",
    "run.parked",
    "run.finished",
    "run.interrupted",
    "plan.approved",
    *OPTION_EVENT_KINDS,
} | both_generations(*LIFECYCLE_EVENT_KINDS)


def _option_event_summary(event_type: str, payload: Mapping[str, Any]) -> str:
    """One History sentence naming the verb, the option and the reason."""
    name = str(payload.get("option_name") or "an option")
    reason = payload.get("reason")
    verb = {
        OPTION_ADDED: "Added the option",
        OPTION_EXCLUDED: "Excluded the option",
        OPTION_INCLUDED: "Included the option",
    }[event_type]
    again = " again" if event_type == OPTION_INCLUDED else ""
    sentence = f"{verb} \u201c{name}\u201d{again}."
    if isinstance(reason, str) and reason.strip():
        sentence = f"{sentence[:-1]}: {reason.strip()}"
    return sentence


def _event_decision(row: Any) -> DecisionOut:
    payload = row.payload if isinstance(row.payload, Mapping) else {}
    actor = payload.get("actor") if isinstance(payload.get("actor"), str) else None
    if row.event_type in OPTION_EVENT_KINDS:
        return DecisionOut(
            sequence=int(row.sequence),
            occurred_at=row.occurred_at,
            kind=row.event_type,
            summary=_option_event_summary(row.event_type, payload),
            decided_by=cast(Any, "user") if actor else None,
            detail=dict(payload),
        )
    text = {
        "component.completed": "Completed an evidence-search step.",
        "component.failed": "An evidence-search step failed.",
        "component.skipped": "Skipped an evidence-search step.",
        "search.executed": "Executed a search query.",
        "run.opened": "Opened an evidence-search run.",
        "run.parked": "Parked the run for a check-in.",
        "run.finished": "Finished the run.",
        "run.interrupted": "Interrupted the run.",
        "plan.approved": "Approved the plan.",
        # Both generations read as the same sentence — the words on screen are
        # today's, whichever word the stored row carries.
        **dict.fromkeys(both_generations("renamed"), "Renamed the task."),
        **dict.fromkeys(both_generations("archived"), "Archived the task."),
        **dict.fromkeys(both_generations("shared_publicly"), "Made the task public."),
        **dict.fromkeys(both_generations("unshared"), "Made the task private."),
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
    conn: Connection, task_id: uuid.UUID, page: int, page_size: int
) -> Page[DecisionOut]:
    """Return steering-history decisions plus the explicitly allowlisted audit events."""
    allowed = (
        conn.execute(
            select(event_log).where(
                event_log.c.task_id == task_id, event_log.c.event_type.in_(_EVENT_KINDS)
            )
        )
        .mappings()
        .all()
    )
    decision_events: list[DecisionOut] = [_event_decision(row) for row in allowed]
    for story in steering_history(conn, task_id):
        for event in story["events"]:
            if event["event_type"] != "steering.decision":
                continue
            payload = event["payload"] if isinstance(event["payload"], Mapping) else {}
            # Pre-038 rows carry the old actor word; the set would drop them.
            decided_by = canonical_actor(payload.get("decided_by"))
            decision_events.append(
                DecisionOut(
                    sequence=int(event["sequence"]),
                    occurred_at=event["occurred_at"],
                    kind="steering.decision",
                    summary="Recorded a steering decision.",
                    decided_by=cast(Any, decided_by)
                    if decided_by in {"user", "agent", "standing_default"}
                    else None,
                    detail=dict(payload),
                )
            )
    decision_events.sort(key=lambda item: item.sequence, reverse=True)
    return Page(
        data=decision_events[(page - 1) * page_size : page * page_size],
        pagination=PageMeta(page=page, page_size=page_size, total_items=len(decision_events)),
    )


def artefact_out(conn: Connection, task_id: uuid.UUID) -> ArtefactOut | None:
    """Materialize the latest synthesis artefact with batched claims and citations."""
    synthesis = _latest_synthesis(conn, task_id)
    if synthesis is None:
        return None
    artefact_row = (
        conn.execute(select(artefact).where(artefact.c.artefact_id == synthesis["artefact_id"]))
        .mappings()
        .one_or_none()
    )
    if artefact_row is None:
        return None
    characterisation_themes = _characterisation_theme_refs(conn, task_id, synthesis)
    grouping_themes = _grouping_theme_refs(conn, task_id, synthesis)
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
    snapshot_to_tss: dict[uuid.UUID, uuid.UUID] = {}
    tss_to_envelope: dict[uuid.UUID, uuid.UUID] = {}
    for row in conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            task_source_snapshot.c.source_snapshot_id,
            task_source_snapshot.c.full_text_snapshot_id,
        ).where(task_source_snapshot.c.task_id == task_id)
    ).all():
        snapshot_to_tss[row.source_snapshot_id] = row.task_source_snapshot_id
        tss_to_envelope[row.task_source_snapshot_id] = row.source_snapshot_id
        if row.full_text_snapshot_id is not None:
            snapshot_to_tss[row.full_text_snapshot_id] = row.task_source_snapshot_id

    def _envelope_id(snapshot_id: uuid.UUID) -> uuid.UUID:
        tss_id = snapshot_to_tss.get(snapshot_id)
        return tss_to_envelope.get(tss_id, snapshot_id) if tss_id is not None else snapshot_id

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
    # The appraisal tier and the classified evidence type (the rubric's
    # scoring input, surfaced with the label so the UI can say WHY a citation
    # carries a band) — both through the label resolver (task 045, S5), over
    # the documents the citations can resolve to.
    citation_labels = labels_for_snapshots(
        conn, task_id=task_id, tss_ids=set(tss_to_envelope)
    )
    citations_by_annotation: dict[uuid.UUID, list[Any]] = {}
    for row in citation_rows:
        citations_by_annotation.setdefault(row.annotation_id, []).append(row)
    refs: dict[uuid.UUID, int] = {}
    reference_order: list[uuid.UUID] = []
    claims_by_block: dict[uuid.UUID, list[ClaimOut]] = {block_id: [] for block_id in ids}
    claims_alias_by_block: dict[uuid.UUID, dict[str, ClaimOut]] = {
        block_id: {} for block_id in ids
    }
    for row in annotations:
        locator = row.locator if isinstance(row.locator, Mapping) else {}
        start, end = locator.get("start"), locator.get("end")
        span = (start, end) if isinstance(start, int) and isinstance(end, int) else None
        row_payload = row.payload if isinstance(row.payload, Mapping) else {}
        claim_citations: list[CitationOut] = []
        for cited in citations_by_annotation.get(row.annotation_id, []):
            snapshot_id = cited.source_snapshot_id
            tss_id = snapshot_to_tss.get(snapshot_id)
            # Reference identity is the DOCUMENT, not the snapshot: abstract-
            # and full-text-grounded quotes from one source share one entry.
            doc_key = tss_id if tss_id is not None else snapshot_id
            if doc_key not in refs:
                refs[doc_key] = len(refs) + 1
                reference_order.append(doc_key)
            source_meta, locator_text = meta.get(_envelope_id(snapshot_id), ({}, "Unknown source"))
            label = citation_labels.get(tss_id) if tss_id is not None else None
            payload = row_payload
            claim_citations.append(
                CitationOut(
                    citation_id=cited.citation_id,
                    n=refs[doc_key],
                    source_id=tss_id,
                    source_title=_title(source_meta, locator_text),
                    quote=cited.quote,
                    grounding_tier=cast(str | None, payload.get("verdict"))
                    if isinstance(payload.get("verdict"), str)
                    else None,
                    grounding_rationale=cast(str, payload.get("rationale"))
                    if isinstance(payload.get("rationale"), str)
                    else None,
                    appraisal_label=SCORE_LABELS.get(label.quality_score)
                    if label is not None and label.quality_score is not None
                    else None,
                    evidence_type=label.evidence_type if label is not None else None,
                )
            )
        claim_type = (
            row.annotation_type
            if row.annotation_type
            in {"citation", "gap", "reasoning", "pattern", "theme", "unspanned_assertion"}
            else "reasoning"
        )
        claim_out = ClaimOut(
                claim_id=row.unit_id,
                claim_type=cast(Any, claim_type),
                text=row.content,
                span=span,
                citations=claim_citations,
                weakly_grounded=_weakly_grounded(row.payload),
                gap=_gap_out(row.payload),
                theme=_theme_out(row.payload, characterisation_themes, grouping_themes),
            )
        claims_by_block[row.block_id].append(claim_out)
        synthesis_claim_id = row_payload.get("claim_id")
        if isinstance(synthesis_claim_id, str):
            claims_alias_by_block[row.block_id][synthesis_claim_id] = claim_out
    section_entries: dict[tuple[str, str, str | None, str | None], list[uuid.UUID]] = {}
    for spec, block_id in parsed_specs:
        role: str = cast(
            str,
            spec.get("role")
            if spec.get("role") in {"key_findings", "case_studies", "standard", "conclusions"}
            else "standard",
        )
        title = cast(str, spec.get("title") or "")
        focus = cast(str | None, spec.get("focus")) if isinstance(spec.get("focus"), str) else None
        # Absent on every artefact synthesised before task 032 — the client
        # falls back to a shortened title rather than treating it as an error.
        nav_label = (
            cast(str | None, spec.get("nav_label"))
            if isinstance(spec.get("nav_label"), str)
            else None
        )
        section_entries.setdefault((title, role, focus, nav_label), []).append(block_id)
    # Build a lookup from block_id → rollup spec for card projection.
    spec_by_block_id: dict[uuid.UUID, Mapping[str, Any]] = {}
    for spec_item, bid in parsed_specs:
        spec_by_block_id[bid] = spec_item

    sections: list[SectionOut] = []
    for (title, role, focus, nav_label), section_block_ids in section_entries.items():
        single_block = block_rows.get(section_block_ids[0]) if len(section_block_ids) == 1 else None
        # Task case-study cards from the block rollup when role is case_studies.
        cards: list[CaseStudyCardOut] = []
        if role == "case_studies":
            for bid in section_block_ids:
                rollup_spec = spec_by_block_id.get(bid, {})
                raw_cards = rollup_spec.get("cards", [])
                if isinstance(raw_cards, list):
                    block_claims = claims_by_block.get(bid, [])
                    block_claim_by_id = {str(c.claim_id): c for c in block_claims}
                    block_claim_by_id.update(claims_alias_by_block.get(bid, {}))
                    claim_id_map = {str(c.claim_id): c.claim_id for c in block_claims}
                    for alias_id, claim in claims_alias_by_block.get(bid, {}).items():
                        claim_id_map.setdefault(alias_id, claim.claim_id)
                    for raw_card in raw_cards:
                        if not isinstance(raw_card, dict):
                            continue
                        card_id_str = raw_card.get("card_id")
                        try:
                            card_uuid = (
                                uuid.UUID(card_id_str)
                                if isinstance(card_id_str, str)
                                else uuid.uuid4()
                            )
                        except ValueError:
                            card_uuid = uuid.uuid4()
                        # Task per-card claims from stored claim_ids/spans
                        card_claims = _task_card_claims(
                            raw_card, block_claim_by_id,
                        )
                        result_claim_str = raw_card.get("result_claim_id")
                        result_claim_uuid = (
                            claim_id_map.get(result_claim_str)
                            if isinstance(result_claim_str, str)
                            else None
                        )
                        if result_claim_uuid not in {claim.claim_id for claim in card_claims}:
                            result_ordinal = raw_card.get("result_ordinal")
                            if (
                                isinstance(result_ordinal, int)
                                and not isinstance(result_ordinal, bool)
                                and 0 <= result_ordinal < len(card_claims)
                            ):
                                result_claim_uuid = card_claims[result_ordinal].claim_id
                            else:
                                result_claim_uuid = None
                        strength, design, since_year = _card_evidence_fields(
                            raw_card, card_claims,
                        )
                        cards.append(
                            CaseStudyCardOut(
                                card_id=card_uuid,
                                title=raw_card.get("title", ""),
                                prose=raw_card.get("prose", ""),
                                claims=card_claims,
                                result_claim_id=result_claim_uuid,
                                strength=strength,
                                design=design,
                                since_year=since_year,
                            )
                        )
        sections.append(
            SectionOut(
                title=title,
                role=cast(Any, role),
                focus=focus,
                nav_label=nav_label,
                blocks=[
                    BlockOut(
                        block_id=block_id,
                        prose=block_rows[block_id].content if block_id in block_rows else "",
                        claims=claims_by_block.get(block_id, []),
                    )
                    for block_id in section_block_ids
                ],
                cards=cards,
                summary=single_block.summary if single_block is not None else None,
                summary_status=(
                    cast(Any, single_block.summary_status) if single_block is not None else None
                ),
            )
        )
    refs_out = []
    for doc_key in reference_order:
        # doc_key is a tss id (envelope via tss_to_envelope) or, for a
        # snapshot with no task edge, the snapshot id itself.
        ref_entry = meta.get(tss_to_envelope.get(doc_key, doc_key))
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
                authorships=_authorships(ref_meta),
            )
        )
    study_types = {
        evidence_type: int(count)
        for evidence_type, count in conn.execute(
            select(
                source_classification_result.c.primary_evidence_type,
                func.count(),
            )
            .where(source_classification_result.c.task_id == task_id)
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
            .where(effective.c.task_id == task_id)
            .where(effective.c.evidence_scope_id == synthesis["evidence_scope_id"])
        )
        .scalars()
        .all()
    )
    reference_years = [reference.year for reference in refs_out if reference.year is not None]
    year_range = (min(reference_years), max(reference_years)) if reference_years else None
    # Task most_relevant_notes from counts JSONB (task 034 S5).
    raw_counts = synthesis.get("counts")
    raw_mrs_notes = (
        raw_counts.get("most_relevant_notes", [])
        if isinstance(raw_counts, Mapping)
        else []
    )
    mrs_notes_out = [
        MostRelevantNoteOut(source_id=str(note["source_id"]), note=str(note["note"]))
        for note in (raw_mrs_notes if isinstance(raw_mrs_notes, list) else [])
        if isinstance(note, dict)
        and isinstance(note.get("source_id"), str)
        and isinstance(note.get("note"), str)
    ]
    raw_full_report_intro = (
        raw_counts.get("full_report_intro")
        if isinstance(raw_counts, Mapping)
        else None
    )
    full_report_intro_out = (
        raw_full_report_intro.strip()
        if isinstance(raw_full_report_intro, str) and raw_full_report_intro.strip() != ""
        else None
    )
    # What kind of artefact this is and how deep its pass went, exactly as the
    # roll-up recorded them (task 044, C18): "baseline" / "scoping pass" for an
    # options-scoping baseline, absent for every Evidence search report. The
    # Result view reads these words; it never derives them.
    raw_template = raw_counts.get("template") if isinstance(raw_counts, Mapping) else None
    raw_depth_label = raw_counts.get("depth_label") if isinstance(raw_counts, Mapping) else None

    return ArtefactOut(
        artefact_id=artefact_row["artefact_id"],
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
        most_relevant_notes=mrs_notes_out,
        full_report_intro=full_report_intro_out,
        template=raw_template if isinstance(raw_template, str) else None,
        depth_label=raw_depth_label if isinstance(raw_depth_label, str) else None,
    )


def _card_evidence_fields(
    raw_card: dict[str, Any],
    card_claims: list[ClaimOut],
) -> tuple[str | None, str | None, int | None]:
    """Strength, design and year for a case-study card.

    Rollup JSONB may omit metadata when finding-level lookup missed; fill
    from the card claims' citation rows when present.

    Args:
        raw_card: One card dict from the rollup JSONB.
        card_claims: Projected claims for the card.

    Returns:
        Tuple of (strength, design, since_year).
    """
    strength = raw_card.get("strength") if isinstance(raw_card.get("strength"), str) else None
    design = raw_card.get("design") if isinstance(raw_card.get("design"), str) else None
    since_year = raw_card.get("since_year") if isinstance(raw_card.get("since_year"), int) else None
    for claim in card_claims:
        for cite in claim.citations:
            strength = strength or cite.appraisal_label
            design = design or cite.evidence_type
    return strength, design, since_year


def _task_card_claims(
    raw_card: dict[str, Any],
    block_claim_by_id: dict[str, ClaimOut],
) -> list[ClaimOut]:
    """Project per-card claims with spans re-anchored into card prose.

    Uses stored ``claim_ids`` and ``claim_spans`` from the rollup when
    available; falls back to substring matching for rollups written before
    per-card claim storage.

    Args:
        raw_card: One card dict from the rollup JSONB.
        block_claim_by_id: Block-level ClaimOut objects keyed by claim_id str.

    Returns:
        ClaimOut list with spans relative to card.prose.
    """
    card_prose = raw_card.get("prose", "")
    stored_ids = raw_card.get("claim_ids")
    stored_spans = raw_card.get("claim_spans")

    if isinstance(stored_ids, list) and stored_ids:
        span_by_id: dict[str, tuple[int, int] | None] = {}
        null_span_ids: set[str] = set()
        if isinstance(stored_spans, list):
            for entry in stored_spans:
                if isinstance(entry, dict):
                    cid = entry.get("claim_id")
                    sp = entry.get("span")
                    if isinstance(cid, str) and isinstance(sp, (list, tuple)) and len(sp) == 2:
                        span_by_id[cid] = (int(sp[0]), int(sp[1]))
                    elif isinstance(cid, str) and sp is None:
                        null_span_ids.add(cid)
        result: list[ClaimOut] = []
        trusted: list[bool] = []
        for cid in stored_ids:
            if not isinstance(cid, str):
                continue
            block_claim = block_claim_by_id.get(cid)
            if block_claim is None:
                continue
            span = span_by_id.get(cid)
            result.append(ClaimOut(
                claim_id=block_claim.claim_id,
                claim_type=block_claim.claim_type,
                text=block_claim.text,
                span=span,
                citations=block_claim.citations,
                weakly_grounded=block_claim.weakly_grounded,
                gap=block_claim.gap,
                theme=block_claim.theme,
            ))
            # A stored entry with an explicitly-null span is the write path's
            # own record that this claim's text bound into the card title, not
            # the prose (synthesise.py stores span=None on a prose miss) —
            # trust it rather than treating the miss as collision evidence.
            trusted.append(block_claim.text in card_prose or cid in null_span_ids)
        # Old case-study rollups minted aliases afresh for each card.  The
        # block alias map then resolves every colliding id to one claim, which
        # may not belong to this card.  Only trust stored aliases when their
        # resolved text is actually present in the card prose (or the write
        # path recorded the miss deliberately). An empty resolution means the
        # aliases are unusable — fall through to prose matching, don't return
        # an empty card.
        if result and all(trusted):
            return result

    # Fallback: match block claims whose text is a substring of card prose.
    # The lookup holds each claim under both its UUID and its synthesis alias,
    # so dedupe by identity before matching.
    unique_claims = {claim.claim_id: claim for claim in block_claim_by_id.values()}
    result = []
    for claim in unique_claims.values():
        pos = card_prose.find(claim.text)
        if pos >= 0:
            result.append(ClaimOut(
                claim_id=claim.claim_id,
                claim_type=claim.claim_type,
                text=claim.text,
                span=(pos, pos + len(claim.text)),
                citations=claim.citations,
                weakly_grounded=claim.weakly_grounded,
                gap=claim.gap,
                theme=claim.theme,
            ))
    result.sort(key=lambda claim: claim.span[0] if claim.span is not None else -1)
    return result


def _weakly_grounded(payload: Any) -> bool | None:
    """Map stored grounding warnings without inventing a verification result."""
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
    conn: Connection, task_id: uuid.UUID, synthesis: Mapping[str, Any]
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
        .where(characterisation_result.c.task_id == task_id)
        .where(characterisation_result.c.evidence_scope_id == synthesis["evidence_scope_id"])
        .where(characterisation_result.c.run_id == synthesis["characterisation_run_id"])
    ).scalar_one_or_none()
    if not isinstance(payload, Mapping) or not isinstance(payload.get("themes"), list):
        return {}
    source_refs = _theme_sources_for_task_source_snapshots(
        conn,
        task_id,
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
    conn: Connection, task_id: uuid.UUID, synthesis: Mapping[str, Any]
) -> dict[str, ThemeRefItemOut]:
    """Return the artefact's own facet groups keyed by their durable group ids.

    Pinned to the synthesis row's (evidence_scope_id, grouping_run_id) FK for
    the same reason as `_characterisation_theme_refs`.
    """
    if synthesis.get("grouping_run_id") is None:
        return {}
    payload = conn.execute(
        select(grouping_result.c.groups)
        .where(grouping_result.c.task_id == task_id)
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
    source_refs = _theme_sources_for_findings(conn, task_id, finding_ids)
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
    """Map resolvable member sources once, preserving stored member order."""
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


def _theme_sources_for_task_source_snapshots(
    conn: Connection, task_id: uuid.UUID, source_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ThemeSourceOut]:
    """Map task-source-snapshot ids to the envelope source display details."""
    if not source_ids:
        return {}
    rows = conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
        )
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(
            task_source_snapshot.c.task_id == task_id,
            task_source_snapshot.c.task_source_snapshot_id.in_(source_ids),
        )
    ).all()
    return {
        row.task_source_snapshot_id: ThemeSourceOut(
            source_id=row.task_source_snapshot_id,
            title=_title(
                row.metadata if isinstance(row.metadata, Mapping) else {}, row.source_locator
            ),
        )
        for row in rows
    }


def _theme_sources_for_findings(
    conn: Connection, task_id: uuid.UUID, finding_ids: set[uuid.UUID]
) -> dict[uuid.UUID, ThemeSourceOut]:
    """Map finding ids to their sources through the findings read-model join."""
    if not finding_ids:
        return {}
    result: dict[uuid.UUID, ThemeSourceOut] = {}
    for finding in (intervention_outcome_finding, implementation_context_finding):
        rows = conn.execute(
            select(
                finding.c.finding_id,
                source_extraction_record.c.task_source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(_finding_source_join(finding))
            .where(finding.c.task_id == task_id, finding.c.finding_id.in_(finding_ids))
        ).all()
        for row in rows:
            metadata = row.metadata if isinstance(row.metadata, Mapping) else {}
            result[row.finding_id] = ThemeSourceOut(
                source_id=row.task_source_snapshot_id,
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


def coverage_out(conn: Connection, task_id: uuid.UUID) -> CoverageOut | None:
    """Compose the latest coverage record as one sentence with its evidence base."""
    row = (
        conn.execute(
            select(search_coverage_record)
            .where(search_coverage_record.c.task_id == task_id)
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
    counts = funnel_out(conn, task_id).model_dump(include={"found", "relevant", "screened_out"})
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
            conn,
            task_id,
            # Same row the sentence and the backend list come from, so every
            # part of this card describes one question.
            _acquire_run_ids(conn, task_id, row["evidence_scope_id"]),
            backend_names,
        ),
    )


def _public_backend_name(value: str) -> str | None:
    """Translate a durable backend key into the closed public vocabulary."""
    return {"openalex": "OpenAlex", "overton": "Overton"}.get(value)


def _acquire_run_ids(
    conn: Connection, task_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> list[uuid.UUID]:
    """Every acquire run of one evidence scope, oldest first.

    Acquire inserts one coverage record per run, so the column holds one id per
    round (task 031) — all of them, which is what makes ``results`` cumulative
    across rounds instead of last-round-only.

    Scoped to **one question**, not the whole task: approving a plan mints a
    new ``evidence_scope`` (``agent.py``), so a re-planned task holds
    the superseded question's coverage records too. Task-wide here would put
    the abandoned question's query strings and hits into this question's card,
    beside a ``sentence`` read from the current question's row. Round-cumulative
    is the fix task 031 wanted; question-cumulative is not (review stack).

    ``relevant`` next door stays task-wide by design — screening re-screens
    the whole task pool per question (docs/knowledge/
    coverage-base-task-pool-wide.md), and the contract's invariant 3 requires
    only that the copy never imply one number contains the other.

    The order here is for readability only — what makes the read model
    deterministic is the ``sequence`` ordering on the event select that consumes
    these ids, not the order of the ids themselves.
    """
    return list(
        conn.execute(
            select(search_coverage_record.c.acquired_by_run_id)
            .where(
                search_coverage_record.c.task_id == task_id,
                search_coverage_record.c.evidence_scope_id == evidence_scope_id,
            )
            .order_by(search_coverage_record.c.created_at)
        ).scalars()
    )


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
    task_id: uuid.UUID,
    run_ids: Sequence[uuid.UUID],
    backend_names: list[str],
) -> list[CoverageBackendDetailOut]:
    """Query hits across every acquire round, beside task-wide relevance.

    ``results`` sums the query hits of every acquire run given, not just the
    newest round's (task 031, defect 2). Before this slice the caller passed the
    latest coverage row's ``acquired_by_run_id`` alone, so a deep run's third
    round reported ~72 hits beside ~200 cumulative relevant sources — two grains
    on one line.

    ``relevant`` stays the task-wide unique count per backend (the documented
    task 027 §C.1 behaviour). The two numbers are now both cumulative, but they
    still count different things: hits are per call and pre-dedupe, so
    ``relevant`` is not a subset of ``results``.

    Args:
        conn: Open read connection.
        task_id: Owning task.
        run_ids: Every acquire run whose query hits belong in the total. Empty
            yields empty query lists rather than a silent last-round figure.
        backend_names: Public backend names to report, in display order.

    Returns:
        One detail row per backend name, in the order given.
    """
    events = (
        conn.execute(
            select(event_log.c.payload)
            .where(
                event_log.c.task_id == task_id,
                event_log.c.run_id.in_(run_ids),
                event_log.c.event_type == "search.executed",
            )
            # Emission order, so the pane lists round 1's queries before round
            # 2's. Spanning several runs made this load-bearing: without it the
            # rows come back in physical order and the list is non-deterministic
            # between identical requests.
            .order_by(event_log.c.sequence)
        )
        .scalars()
        .all()
        if run_ids
        else []
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
                    task_source_snapshot,
                    effective.c.task_source_snapshot_id
                    == task_source_snapshot.c.task_source_snapshot_id,
                ).join(
                    source_snapshot,
                    task_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(effective.c.task_id == task_id, effective.c.status == "relevant")
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
    conn: Connection, task_id: uuid.UUID, source_id: uuid.UUID
) -> SourceDossierOut | None:
    """Materialize one owner-authorized source dossier from durable records only."""
    row = (
        conn.execute(
            select(
                task_source_snapshot.c.task_source_snapshot_id,
                task_source_snapshot.c.origin,
                task_source_snapshot.c.source_snapshot_id,
                task_source_snapshot.c.full_text_snapshot_id,
                task_source_snapshot.c.full_text_status,
                task_source_snapshot.c.full_text_error,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(
                task_source_snapshot.join(
                    source_snapshot,
                    task_source_snapshot.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(
                task_source_snapshot.c.task_id == task_id,
                task_source_snapshot.c.task_source_snapshot_id == source_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    metadata = row["metadata"] if isinstance(row["metadata"], Mapping) else {}
    screen = _effective_screens(conn, task_id).get(source_id)
    screen_reasons, classification_reasons = _source_reason_maps(conn, task_id)
    selection = _latest_selection(conn, task_id)
    selected = _selected_ids(selection["selected"]) if selection is not None else set()
    extracted = (
        conn.execute(
            select(source_extraction_record.c.extraction_record_id)
            .where(
                source_extraction_record.c.task_id == task_id,
                source_extraction_record.c.task_source_snapshot_id == source_id,
                source_extraction_record.c.finding_count > 0,
            )
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )
    synthesis = _latest_synthesis(conn, task_id)
    cited_ids = (
        _cited_snapshot_ids(conn, synthesis["artefact_id"]) if synthesis is not None else set()
    )
    # Python-side membership over an already-fetched row + a precomputed set,
    # not a SQL join — tss_owns_snapshot doesn't fit here (task 029
    # delta-review sweep).
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
    label = labels_for_snapshots(conn, task_id=task_id, tss_ids=[source_id]).get(source_id)
    provider_value = metadata.get("provider_fields")
    provider: Mapping[str, Any] = provider_value if isinstance(provider_value, Mapping) else {}
    abstract, abstract_source = _abstract_fields(metadata)
    tags = [
        SourceTagOut(tag=tag_row.tag, tag_type=tag_row.tag_type, asserted_by=tag_row.asserted_by)
        for tag_row in conn.execute(
            select(source_tag.c.tag, source_tag.c.tag_type, source_tag.c.asserted_by)
            .where(
                source_tag.c.task_id == task_id,
                source_tag.c.task_source_snapshot_id == source_id,
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
        evidence_type=label.evidence_type if label is not None else None,
        appraisal_tier=SCORE_LABELS.get(label.quality_score)
        if label is not None and label.quality_score is not None
        else None,
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
        abstract_source=abstract_source,
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
        cited_in=_source_cited_in(conn, task_id, source_id),
        authorships=_authorships(metadata),
    )


def _source_cited_in(
    conn: Connection, task_id: uuid.UUID, source_id: uuid.UUID
) -> list[CitedInOut]:
    """Return only latest-synthesis claims citing either snapshot linked to a source."""
    synthesis = _latest_synthesis(conn, task_id)
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
            task_source_snapshot.c.source_snapshot_id,
            task_source_snapshot.c.full_text_snapshot_id,
        ).where(
            task_source_snapshot.c.task_id == task_id,
            task_source_snapshot.c.task_source_snapshot_id == source_id,
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


# Immediate window around a located quote. Neighbour chunks are only attached
# when this window hits that edge of the current chunk, and then only a short
# snippet — never the whole adjacent chunk (that read as off-topic grey text).
_CONTEXT_SIDE_CHARS = 800
_ADJACENT_SNIPPET_CHARS = 220
_ELLIPSIS = "..."


def _adjacent_chunk(conn: Connection, source_snapshot_id: uuid.UUID, sequence: int) -> str | None:
    """Return one adjacent chunk's content when the sequence exists."""
    return conn.execute(
        select(chunk.c.content).where(
            chunk.c.source_snapshot_id == source_snapshot_id, chunk.c.sequence == sequence
        )
    ).scalar_one_or_none()


def _snap_start(text: str, index: int, *, not_past: int) -> int:
    """Advance a start cut to the next word, without crossing ``not_past``.

    A mid-word cut drops the partial word. An unspaced run that reaches the
    quote is left as-is so the window does not collapse onto the span.
    """
    if index <= 0:
        return 0
    limit = min(not_past, len(text))
    if index >= limit:
        return limit
    if not text[index].isspace() and not text[index - 1].isspace():
        at = index
        while at < limit and not text[at].isspace():
            at += 1
        if at >= limit:
            return index
        index = at
    while index < limit and text[index].isspace():
        index += 1
    return index


def _snap_end(text: str, index: int, *, not_before: int) -> int:
    """Retreat an end cut to the previous word, without crossing ``not_before``.

    A mid-word cut drops the partial word. An unspaced run out of the quote
    is left as-is so the window does not collapse onto the span.
    """
    if index >= len(text):
        return len(text)
    limit = max(not_before, 0)
    if index <= limit:
        return limit
    if not text[index - 1].isspace() and (index == len(text) or not text[index].isspace()):
        at = index
        while at > limit and not text[at - 1].isspace():
            at -= 1
        if at <= limit:
            return index
        index = at
    while index > limit and text[index - 1].isspace():
        index -= 1
    return index


def _edge_snippet(raw: str, *, from_end: bool) -> str:
    """Clip an adjacent chunk to a short seam snippet, ellipsis-marked both sides."""
    if from_end:
        start = _snap_start(raw, max(0, len(raw) - _ADJACENT_SNIPPET_CHARS), not_past=len(raw))
        snippet = raw[start:].strip()
        if snippet == "":
            snippet = raw[-_ADJACENT_SNIPPET_CHARS:].strip()
            start = max(0, len(raw) - _ADJACENT_SNIPPET_CHARS)
        prefix = _ELLIPSIS if start > 0 else ""
        return f"{prefix}{snippet}{_ELLIPSIS}"
    end = _snap_end(raw, min(len(raw), _ADJACENT_SNIPPET_CHARS), not_before=0)
    snippet = raw[:end].strip()
    if snippet == "":
        snippet = raw[:_ADJACENT_SNIPPET_CHARS].strip()
        end = min(len(raw), _ADJACENT_SNIPPET_CHARS)
    suffix = _ELLIPSIS if end < len(raw) else ""
    return f"{_ELLIPSIS}{snippet}{suffix}"


def _clamped_quote_window(
    conn: Connection,
    task_id: uuid.UUID,
    text: str,
    quote: str,
    sequence: int,
    source_snapshot_id: uuid.UUID,
) -> ChunkContextOut | None:
    """Clamp a unique quote to a local window, with short edge neighbours.

    Args:
        conn: Open connection.
        task_id: Owning task (for year/venue).
        text: The cited chunk's raw content.
        quote: The citation or chat quote, as stored.
        sequence: Chunk sequence in the snapshot.
        source_snapshot_id: Snapshot the chunk belongs to.

    Returns:
        The window, or ``None`` when the quote is absent or ambiguous.
    """
    span = locate_unique_span(build_basis([(None, text)]), quote)
    if span is None:
        return None
    position, end = span
    start_window = max(0, position - _CONTEXT_SIDE_CHARS)
    end_window = min(len(text), end + _CONTEXT_SIDE_CHARS)
    previous = None
    following = None
    if start_window == 0:
        raw = _adjacent_chunk(conn, source_snapshot_id, sequence - 1)
        if raw:
            previous = _edge_snippet(raw, from_end=True)
    if end_window == len(text):
        raw = _adjacent_chunk(conn, source_snapshot_id, sequence + 1)
        if raw:
            following = _edge_snippet(raw, from_end=False)
    start_window = _snap_start(text, start_window, not_past=position)
    end_window = _snap_end(text, end_window, not_before=end)
    prefix = _ELLIPSIS if start_window > 0 else ""
    suffix = _ELLIPSIS if end_window < len(text) else ""
    chunk_meta = _chunk_metadata(conn, task_id, source_snapshot_id)
    return ChunkContextOut(
        context=prefix + text[start_window:end_window] + suffix,
        span_start=position - start_window + len(prefix),
        span_end=end - start_window + len(prefix),
        clamped=start_window > 0 or end_window < len(text),
        previous=previous,
        next=following,
        year=_year(chunk_meta),
        venue=_venue(chunk_meta),
        authorships=_authorships(chunk_meta),
    )


def chunk_context_out(
    conn: Connection, task_id: uuid.UUID, citation_id: uuid.UUID
) -> ChunkContextOut | None:
    """Return a local window around an artefact citation's quote.

    Locates the stored quote with the same ``locate_unique_span`` locator as
    the chat/findings path (case, whitespace, curly quotes), then clamps to
    :data:`_CONTEXT_SIDE_CHARS` either side. An ambiguous or absent quote is
    honest absence, not a guessed span.
    """
    row = conn.execute(
        select(citation.c.quote, chunk.c.content, chunk.c.sequence, chunk.c.source_snapshot_id)
        .select_from(
            citation.join(annotation, citation.c.annotation_id == annotation.c.annotation_id)
            .join(block, annotation.c.block_id == block.c.block_id)
            .join(artefact, block.c.artefact_id == artefact.c.artefact_id)
            .join(chunk, chunk.c.chunk_id == citation.c.chunk_id)
        )
        .where(citation.c.citation_id == citation_id, artefact.c.task_id == task_id)
    ).one_or_none()
    if row is None:
        return None
    return _clamped_quote_window(
        conn,
        task_id,
        row.content,
        row.quote,
        row.sequence,
        row.source_snapshot_id,
    )


def chunk_quote_context_out(
    conn: Connection, task_id: uuid.UUID, chunk_id: uuid.UUID, quote: str
) -> ChunkContextOut | None:
    """Return the clamped context window for a chat citation's chunk + quote.

    The chunk must belong to the task's corpus (envelope or full-text
    snapshot link) — the same ownership boundary every read model enforces.
    Chat quotes are raw model output, so this locates the quote via
    ``quote_verify.locate_unique_span`` — the canonical overlap-aware,
    word-boundary-guarded, case-fold-round-tripped locator (task 029
    delta-review) — rather than a repository-side exact-match fast path plus
    a second, parallel normaliser. It tolerates casefold, collapsed
    whitespace and curly quotes/dashes folded to straight — NOT Unicode NFC
    composition (a composed vs. decomposed accent pair is an honest absence,
    not a match; see the locator's own docstring) — with the matched span
    converted back to the true raw span so the displayed context and
    highlight always show the real source text. An ambiguous or absent
    quote has no honest recoverable span, so this returns absence rather
    than guessing.
    """
    row = conn.execute(
        select(chunk.c.content, chunk.c.sequence, chunk.c.source_snapshot_id)
        .select_from(
            chunk.join(
                task_source_snapshot,
                tss_owns_snapshot(chunk.c.source_snapshot_id),
            )
        )
        .where(chunk.c.chunk_id == chunk_id)
        .where(task_source_snapshot.c.task_id == task_id)
        .limit(1)
    ).one_or_none()
    if row is None:
        return None
    return _clamped_quote_window(
        conn, task_id, row.content, quote, row.sequence, row.source_snapshot_id
    )


def _chunk_metadata(
    conn: Connection, task_id: uuid.UUID, source_snapshot_id: uuid.UUID
) -> Mapping[str, Any]:
    """Find the envelope metadata for either immutable snapshot linked by a TSS."""
    metadata = conn.execute(
        select(source_snapshot.c.metadata)
        .select_from(
            task_source_snapshot.join(
                source_snapshot,
                task_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(
            task_source_snapshot.c.task_id == task_id,
            tss_owns_snapshot(source_snapshot_id),
        )
    ).scalar_one_or_none()
    return metadata if isinstance(metadata, Mapping) else {}


# --- The options-scoping longlist (task 045, S12; contract deliverables 9, 11) ---
#
# Assembled, never written (D15): the option rows as they stand, the latest
# ``longlist_result`` (themes, coverage, judgements, guesses, counts) and the
# membership rows behind "Show the documents". Read-only and deterministic;
# the same rows always give the same read model.

#: The ``judgements`` key of constrain's deterministic in-scope record —
#: ``options_scoping.constrain.constrain.IN_SCOPE_EVIDENCE_KEY``, not imported
#: because that module's in-scope check imports :func:`publication_country`
#: from here. Pinned equal by a test.
LONGLIST_IN_SCOPE_KEY = "in_scope_evidence"

#: What the option card shows for the default transferability preference (D22).
TRANSFERABILITY_AT_ASSESSMENT: Literal["checked at assessment"] = "checked at assessment"

#: The default screens' ids, in the order the card lists them.
_SCREEN_ORDER: tuple[str, ...] = ("relevant", "distinct", "in_scope")
_VERDICTS = frozenset({"passes", "breaks", "cannot_check"})
_LEANINGS = frozenset({"likely_meets", "likely_falls_short", "cannot_say"})
_DOCUMENT_ROLES = frozenset({"evaluated", "described", "recommended", "mentioned"})
#: The role a linked finding's kind implies (the longlist component's rule).
_LINKED_FINDING_ROLE: dict[str, str] = {"iof": "evaluated", "icf": "described"}
_WHERE_GROUPS: tuple[str, ...] = ("where", "comparable", "other", "unknown")


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _ranked(counts: object) -> dict[str, int]:
    """A coverage counter, most frequent first (JSONB does not keep key order)."""
    items = [(str(key), _count(value)) for key, value in _as_mapping(counts).items()]
    return dict(sorted(items, key=lambda item: (-item[1], item[0])))


def _where_tried_out(raw: object) -> WhereTriedOut:
    counts = _as_mapping(raw)
    return WhereTriedOut(**{group: _count(counts.get(group)) for group in _WHERE_GROUPS})


def _latest_longlist_row(conn: Connection, task_id: uuid.UUID) -> Any | None:
    """The task's latest ``longlist_result`` row (a longlist exists iff one does)."""
    return conn.execute(
        select(longlist_result)
        .where(longlist_result.c.task_id == task_id)
        .order_by(
            longlist_result.c.created_at.desc(), longlist_result.c.longlist_result_id.desc()
        )
        .limit(1)
    ).one_or_none()


def _scoping_plan_version(
    conn: Connection, task_id: uuid.UUID, version: int | None
) -> tuple[int, ScopingPlan | None] | None:
    """One plan version (``None``: the current approved one) and its scoping plan.

    Returns:
        ``(version, plan)`` — ``plan`` is ``None`` when the payload is not a
        valid scoping plan — or ``None`` when there is no such version.
    """
    query = select(task_plan.c.version, task_plan.c.payload).where(
        task_plan.c.task_id == task_id
    )
    if version is None:
        query = query.where(task_plan.c.status == "approved").order_by(
            task_plan.c.version.desc()
        )
    else:
        query = query.where(task_plan.c.version == version)
    row = conn.execute(query.limit(1)).one_or_none()
    if row is None:
        return None
    try:
        plan = validate_plan(OPTIONS_SCOPING, row.payload)
    except ValueError:
        return int(row.version), None
    return int(row.version), plan if isinstance(plan, ScopingPlan) else None


def _option_rows(
    conn: Connection, task_id: uuid.UUID, option_id: uuid.UUID | None = None
) -> list[Any]:
    query = select(option).where(option.c.task_id == task_id)
    if option_id is not None:
        query = query.where(option.c.option_id == option_id)
    return list(conn.execute(query.order_by(option.c.created_at, option.c.option_id)))


def _option_relations(
    conn: Connection, task_id: uuid.UUID, names: Mapping[uuid.UUID, str]
) -> dict[uuid.UUID, list[RelationOut]]:
    """Each option's relations, from its own side.

    A ``part_of`` row points from the component to the package: the
    component reads ``part_of`` the package, the package ``has_part`` the
    component.
    """
    out: dict[uuid.UUID, list[RelationOut]] = {}
    rows = conn.execute(
        select(option_relation.c.from_option_id, option_relation.c.to_option_id)
        .where(option_relation.c.task_id == task_id, option_relation.c.kind == "part_of")
        .order_by(option_relation.c.created_at, option_relation.c.relation_id)
    )
    for row in rows:
        component, package = row.from_option_id, row.to_option_id
        out.setdefault(component, []).append(
            RelationOut(
                kind="part_of", other_option_id=package, other_name=names.get(package, "")
            )
        )
        out.setdefault(package, []).append(
            RelationOut(
                kind="has_part", other_option_id=component, other_name=names.get(component, "")
            )
        )
    return out


def _design_record(result: Any | None, column: str, row: Any) -> Mapping[str, Any]:
    """The result's ``judgements`` or ``guesses`` entry for the option's design version."""
    if result is None:
        return {}
    by_option = _as_mapping(_as_mapping(getattr(result, column)).get(str(row.option_id)))
    return _as_mapping(by_option.get(str(row.design_version)))


def _in_scope_out(record: Mapping[str, Any]) -> InScopeOut | None:
    check = _as_mapping(record.get(LONGLIST_IN_SCOPE_KEY))
    restriction = check.get("restriction")
    if not isinstance(restriction, str) or not restriction:
        return None
    return InScopeOut(
        restriction=restriction,
        in_scope_documents=_count(check.get("in_scope_documents")),
        documents=_count(check.get("documents")),
    )


def _exclusion_out(row: Any) -> ExclusionOut | None:
    """Why an excluded option is excluded; ``None`` for an included one.

    An included option may still carry a ``by: "user"`` record — the marker a
    user's *include again* leaves so constrain never re-excludes it — which is
    never shown.
    """
    if row.state != "excluded":
        return None
    raw = _as_mapping(row.exclusion)
    if not raw:
        return None
    return ExclusionOut(
        constraint=str(raw.get("constraint") or ""),
        reason=str(raw.get("reason") or ""),
        by="user" if raw.get("by") == "user" else "constrain",
    )


def _string_list(value: object) -> list[str]:
    return [item for item in value if isinstance(item, str)] if isinstance(value, list) else []


def _option_summary_fields(
    row: Any,
    coverage: Mapping[str, Any],
    relations: list[RelationOut],
    record: Mapping[str, Any],
) -> dict[str, Any]:
    documents = _count(coverage.get("documents"))
    in_scope = _in_scope_out(record)
    return {
        "option_id": row.option_id,
        "name": row.name,
        "description": row.description,
        "outcomes_served": _string_list(row.outcomes),
        "origin": row.origin,
        "state": row.state,
        "exclusion": _exclusion_out(row),
        "no_in_scope_evidence": bool(row.no_in_scope_evidence),
        "restriction_text": (
            in_scope.restriction if row.no_in_scope_evidence and in_scope is not None else None
        ),
        "primary_lever_type": row.primary_lever_type,
        "lever_none_fits_reason": row.lever_none_fits_reason,
        "secondary_lever_types": _string_list(row.secondary_lever_types),
        "ambition": row.ambition,
        "ambition_reason": row.ambition_reason,
        "taxonomy_version": row.taxonomy_version,
        "design_version": int(row.design_version),
        "document_count": documents,
        "evaluated_count": _count(_as_mapping(coverage.get("role")).get("evaluated")),
        "settings": list(_ranked(coverage.get("settings"))),
        "where_tried": _where_tried_out(coverage.get("where_tried")),
        "relations": relations,
        "abstract_only": documents > 0 and _count(coverage.get("abstract_only")) == documents,
        "is_entrant_with_no_documents": row.origin != "clustered" and documents == 0,
    }


def _option_coverage(result: Any | None, option_id: uuid.UUID) -> Mapping[str, Any]:
    """The option's coverage in the result; an option added since has none yet."""
    if result is not None:
        coverage = _as_mapping(result.coverage).get(str(option_id))
        if isinstance(coverage, Mapping):
            return coverage
    return empty_coverage()


def _where_label(result: Any | None, plan: ScopingPlan | None) -> str:
    labels = _as_mapping(_as_mapping(result.provenance).get("where_tried_labels")) if result else {}
    label = labels.get("where")
    if isinstance(label, str) and label:
        return label
    if plan is not None and plan.where.text.strip():
        return plan.where.text.strip()
    return "Where"


def _walk_of_run(conn: Connection, task_id: uuid.UUID, run_id: uuid.UUID) -> uuid.UUID | None:
    value = conn.execute(
        select(runs.c.capability_run_id).where(runs.c.run_id == run_id, runs.c.task_id == task_id)
    ).scalar_one_or_none()
    return value if isinstance(value, uuid.UUID) else None


def longlist_out(conn: Connection, task_id: uuid.UUID) -> LonglistOut | None:
    """Assemble the task's longlist, or ``None`` when no longlist exists.

    The latest ``longlist_result`` (by ``created_at``, the ``artefact_out``
    idiom) supplies the themes, the coverage and the run counts; every option
    row of the task is listed as it stands, so an option the user excluded or
    added since the build reads as it is now.

    Args:
        conn: Open database connection. Read-only.
        task_id: The options-scoping task.

    Returns:
        The longlist, or ``None`` (the route's 404) before the first build.
    """
    result = _latest_longlist_row(conn, task_id)
    if result is None:
        return None
    rows = _option_rows(conn, task_id)
    by_id = {row.option_id: row for row in rows}
    relations = _option_relations(conn, task_id, {row.option_id: row.name for row in rows})
    built_from = _scoping_plan_version(conn, task_id, int(result.plan_version))
    current = _scoping_plan_version(conn, task_id, None)

    themes: list[LonglistThemeOut] = []
    themed: list[uuid.UUID] = []
    for raw in result.themes if isinstance(result.themes, list) else []:
        theme = _as_mapping(raw)
        try:
            theme_id = uuid.UUID(str(theme.get("theme_id")))
        except ValueError:
            continue
        option_ids: list[uuid.UUID] = []
        for value in _string_list(theme.get("option_ids")):
            try:
                oid = uuid.UUID(value)
            except ValueError:
                continue
            if oid in by_id and oid not in themed:
                option_ids.append(oid)
                themed.append(oid)
        themes.append(
            LonglistThemeOut(
                theme_id=theme_id,
                name=str(theme.get("name") or ""),
                description=str(theme.get("description") or ""),
                option_ids=option_ids,
            )
        )
    themed_set = set(themed)
    unthemed = [row.option_id for row in rows if row.option_id not in themed_set]

    options = [
        OptionSummaryOut(
            **_option_summary_fields(
                by_id[oid],
                _option_coverage(result, oid),
                relations.get(oid, []),
                _design_record(result, "judgements", by_id[oid]),
            )
        )
        for oid in [*themed, *unthemed]
    ]
    stored = _as_mapping(result.counts)
    counts = LonglistCountsOut(
        options=len(rows),
        themes=len(themes),
        included=sum(1 for row in rows if row.state == "included"),
        excluded=sum(1 for row in rows if row.state == "excluded"),
        no_in_scope=sum(
            1 for row in rows if row.state == "included" and row.no_in_scope_evidence
        ),
        unclustered=_count(stored.get("unclustered")),
        not_an_option=_count(stored.get("not_an_option")),
        none_fits=sum(
            1
            for row in rows
            if row.primary_lever_type is None and row.lever_none_fits_reason is not None
        ),
    )
    taxonomy = _as_mapping(result.provenance).get("taxonomy_version")
    plan_version = int(result.plan_version)
    return LonglistOut(
        run_id=result.run_id,
        capability_run_id=_walk_of_run(conn, task_id, result.run_id),
        plan_version=plan_version,
        built_from_plan_version=plan_version,
        current_plan_version=current[0] if current is not None else None,
        counts=counts,
        themes=themes,
        unthemed_option_ids=unthemed,
        options=options,
        where_label=_where_label(result, built_from[1] if built_from else None),
        lever_types=list(LEVER_TYPE_KEYS),
        ambition_bands=[
            AmbitionBandOut(key=band, label=AMBITION_LABELS[band]) for band in AMBITION_BANDS
        ],
        taxonomy_version=taxonomy if isinstance(taxonomy, str) else TAXONOMY_VERSION,
    )


def _constraint_order(constraint_id: str) -> tuple[int, int, str]:
    """Requirements by number, then the three screens, then anything else."""
    prefix, _, number = constraint_id.partition("-")
    if prefix == "req" and number.isdigit():
        return 0, int(number), constraint_id
    if constraint_id in _SCREEN_ORDER:
        return 1, _SCREEN_ORDER.index(constraint_id), constraint_id
    if prefix == "pref" and number.isdigit():
        return 2, int(number), constraint_id
    return 3, 0, constraint_id


def _judgements_out(record: Mapping[str, Any]) -> list[JudgementOut]:
    out: list[JudgementOut] = []
    for constraint_id in sorted(record, key=_constraint_order):
        if constraint_id == LONGLIST_IN_SCOPE_KEY:
            continue
        entry = _as_mapping(record[constraint_id])
        verdict = entry.get("verdict")
        if verdict not in _VERDICTS:
            continue
        out.append(
            JudgementOut(
                constraint_id=constraint_id,
                constraint_text=str(entry.get("constraint_text") or constraint_id),
                verdict=cast(Any, verdict),
                reason=str(entry.get("reason") or ""),
            )
        )
    return out


def _guesses_out(record: Mapping[str, Any]) -> list[GuessOut]:
    out: list[GuessOut] = []
    for constraint_id in sorted(record, key=_constraint_order):
        entry = _as_mapping(record[constraint_id])
        leaning = entry.get("leaning")
        guess = entry.get("guess")
        if leaning not in _LEANINGS or not isinstance(guess, str):
            continue
        out.append(
            GuessOut(
                constraint_id=constraint_id,
                constraint_text=str(entry.get("constraint_text") or constraint_id),
                guess=guess,
                leaning=cast(Any, leaning),
            )
        )
    return out


def _tier_labels(tiers: object) -> dict[str, int]:
    """Coverage tiers ("1".."5", "not rated") as the appraisal's labels."""
    out: dict[str, int] = {}
    for key, value in _as_mapping(tiers).items():
        label = SCORE_LABELS.get(int(key), str(key)) if str(key).isdigit() else str(key)
        out[label] = out.get(label, 0) + _count(value)
    return dict(sorted(out.items(), key=lambda item: (-item[1], item[0])))


def _evidence_profile(coverage: Mapping[str, Any]) -> EvidenceProfileOut:
    roles = _as_mapping(coverage.get("role"))
    return EvidenceProfileOut(
        documents=_count(coverage.get("documents")),
        by_evidence_type=_ranked(coverage.get("evidence_type")),
        by_tier=_tier_labels(coverage.get("tier")),
        by_role={
            role: _count(roles.get(role))
            for role in ("evaluated", "described", "recommended", "mentioned")
        },
        where_tried=_where_tried_out(coverage.get("where_tried")),
        populations=list(_ranked(coverage.get("populations"))),
        settings=list(_ranked(coverage.get("settings"))),
        outcomes=list(_ranked(coverage.get("outcomes"))),
        flagged_not_stated=_count(coverage.get("flagged_documents")),
        inherited_labels=_count(coverage.get("inherited_labels")),
        abstract_only=_count(coverage.get("abstract_only")),
    )


def _design_out(row: Any) -> OptionDesignOut:
    raw = _as_mapping(row.design)
    return OptionDesignOut(
        name=str(raw.get("name") or row.name),
        description=str(raw.get("description") or row.description),
        design_features=_string_list(raw.get("design_features")),
        outcomes_served=_string_list(raw.get("outcomes_served")) or _string_list(row.outcomes),
        assumed=_string_list(raw.get("assumed")),
        version=int(row.design_version),
    )


def _label_fields(label: DocumentLabels | None) -> tuple[str | None, str | None]:
    if label is None or label.provenance == "absent":
        return None, None
    tier = SCORE_LABELS.get(label.quality_score) if label.quality_score is not None else None
    return label.evidence_type, tier


def _option_documents(
    conn: Connection, task_id: uuid.UUID, option_id: uuid.UUID, home: frozenset[str]
) -> list[OptionDocumentOut]:
    """The documents behind an option, one per membership row (never DOI-collapsed).

    Own records resolve through this task's document row; a linked task's
    finding resolves through the source task's document row (the reach the
    longlist component already has through the link) and, where the task
    holds the same snapshot, this task's row for its labels.
    """
    members = list(
        conn.execute(
            select(option_membership)
            .where(option_membership.c.task_id == task_id)
            .where(option_membership.c.option_id == option_id)
        )
    )
    if not members:
        return []
    own_ids = [m.unit_id for m in members if m.unit_kind == "interventions"]
    records = (
        {
            row.record_id: row
            for row in conn.execute(
                select(
                    intervention_profile_record.c.record_id,
                    intervention_profile_record.c.role,
                    intervention_profile_record.c.study_geography,
                )
                .where(intervention_profile_record.c.task_id == task_id)
                .where(intervention_profile_record.c.record_id.in_(own_ids))
            )
        }
        if own_ids
        else {}
    )
    linked = [m for m in members if m.unit_kind in _LINKED_FINDING_ROLE]
    findings: dict[tuple[uuid.UUID, uuid.UUID], Any] = {}
    if linked:
        fru = finding_reference_union
        source_tss = task_source_snapshot.alias("source_tss")
        for row in conn.execute(
            select(
                fru.c.finding_id,
                fru.c.task_id,
                fru.c.kind,
                fru.c.study_geography,
                source_snapshot.c.source_snapshot_id,
                source_snapshot.c.metadata,
                source_snapshot.c.source_locator,
            )
            .select_from(
                fru.join(
                    source_extraction_record,
                    (source_extraction_record.c.extraction_record_id == fru.c.extraction_record_id)
                    & (source_extraction_record.c.task_id == fru.c.task_id),
                )
                .join(
                    source_tss,
                    (source_tss.c.task_source_snapshot_id
                     == source_extraction_record.c.task_source_snapshot_id)
                    & (source_tss.c.task_id == fru.c.task_id),
                )
                .join(
                    source_snapshot,
                    source_snapshot.c.source_snapshot_id == source_tss.c.source_snapshot_id,
                )
            )
            .where(fru.c.task_id.in_({m.unit_task_id for m in linked}))
            .where(fru.c.finding_id.in_([m.unit_id for m in linked]))
        ):
            findings[(row.task_id, row.finding_id)] = row
    own_by_snapshot = (
        {
            row.source_snapshot_id: row.task_source_snapshot_id
            for row in conn.execute(
                select(
                    task_source_snapshot.c.source_snapshot_id,
                    task_source_snapshot.c.task_source_snapshot_id,
                )
                .where(task_source_snapshot.c.task_id == task_id)
                .where(
                    task_source_snapshot.c.source_snapshot_id.in_(
                        {row.source_snapshot_id for row in findings.values()}
                    )
                )
            )
        }
        if findings
        else {}
    )
    member_tss = {m.task_source_snapshot_id for m in members if m.task_source_snapshot_id}
    documents = (
        {
            row.task_source_snapshot_id: row
            for row in conn.execute(
                select(
                    task_source_snapshot.c.task_source_snapshot_id,
                    source_snapshot.c.metadata,
                    source_snapshot.c.source_locator,
                )
                .select_from(
                    task_source_snapshot.join(
                        source_snapshot,
                        source_snapshot.c.source_snapshot_id
                        == task_source_snapshot.c.source_snapshot_id,
                    )
                )
                .where(task_source_snapshot.c.task_id == task_id)
                .where(task_source_snapshot.c.task_source_snapshot_id.in_(member_tss))
            )
        }
        if member_tss
        else {}
    )
    labels = labels_for_snapshots(
        conn, task_id=task_id, tss_ids=member_tss | set(own_by_snapshot.values())
    )

    out: list[tuple[str, str, OptionDocumentOut]] = []
    for member in members:
        if member.unit_kind == "interventions":
            record = records.get(member.unit_id)
            document = documents.get(member.task_source_snapshot_id)
            if record is None or document is None or record.role not in _DOCUMENT_ROLES:
                continue
            tss_id = member.task_source_snapshot_id
            label = labels.get(tss_id)
            source_task_id = (
                label.source_task_id
                if label is not None and label.provenance == "inherited"
                else None
            )
            role, geography = record.role, record.study_geography
            metadata, locator = _as_mapping(document.metadata), document.source_locator
        else:
            finding = findings.get((member.unit_task_id, member.unit_id))
            if finding is None:
                continue
            tss_id = own_by_snapshot.get(finding.source_snapshot_id)
            label = labels.get(tss_id) if tss_id is not None else None
            source_task_id = member.unit_task_id
            role, geography = _LINKED_FINDING_ROLE[member.unit_kind], finding.study_geography
            metadata, locator = _as_mapping(finding.metadata), finding.source_locator
        evidence_type, tier = _label_fields(label)
        title = _title(metadata, locator)
        out.append(
            (
                title.casefold(),
                str(member.membership_id),
                OptionDocumentOut(
                    task_source_snapshot_id=tss_id,
                    title=title,
                    role=cast(Any, role),
                    evidence_type=evidence_type,
                    tier=tier,
                    design_feature_not_stated=bool(member.design_feature_not_stated),
                    where_tried_group=where_group([geography], home),
                    source_task_id=source_task_id,
                ),
            )
        )
    return [document for _, _, document in sorted(out, key=lambda item: item[:2])]


def option_out(conn: Connection, task_id: uuid.UUID, option_id: uuid.UUID) -> OptionOut | None:
    """Assemble one option's card, or ``None`` when the task holds no such option.

    Assembled from the passes' outputs, no writer (D15): the option row, its
    coverage, judgements and guesses in the latest ``longlist_result`` for
    its current design version (D10), and its membership rows. An option
    added since the last build reads with an empty profile.

    Args:
        conn: Open database connection. Read-only.
        task_id: The options-scoping task.
        option_id: The option.

    Returns:
        The card, or ``None`` (the route's 404).
    """
    rows = _option_rows(conn, task_id, option_id)
    if not rows:
        return None
    row = rows[0]
    result = _latest_longlist_row(conn, task_id)
    names = {
        oid: name
        for oid, name in conn.execute(
            select(option.c.option_id, option.c.name).where(option.c.task_id == task_id)
        )
    }
    relations = _option_relations(conn, task_id, names).get(option_id, [])
    coverage = _option_coverage(result, option_id)
    judgements = _design_record(result, "judgements", row)
    plan_row = _scoping_plan_version(
        conn, task_id, int(result.plan_version) if result is not None else None
    )
    plan = plan_row[1] if plan_row is not None else None
    home = where_codes(plan.where.text) if plan is not None else frozenset()
    design = _design_out(row)
    return OptionOut(
        **_option_summary_fields(row, coverage, relations, judgements),
        design=design,
        design_features=list(design.design_features),
        evidence=_evidence_profile(coverage),
        judgements=_judgements_out(judgements),
        guesses=_guesses_out(_design_record(result, "guesses", row)),
        transferability=(
            TRANSFERABILITY_AT_ASSESSMENT
            if plan is not None and find_default(plan, TRANSFERABILITY_DEFAULT) is not None
            else None
        ),
        in_scope=_in_scope_out(judgements),
        documents=_option_documents(conn, task_id, option_id, home),
        run_id=result.run_id if result is not None else None,
        capability_run_id=(
            _walk_of_run(conn, task_id, result.run_id) if result is not None else None
        ),
        plan_version=int(result.plan_version) if result is not None else None,
        where_label=_where_label(result, plan),
    )
