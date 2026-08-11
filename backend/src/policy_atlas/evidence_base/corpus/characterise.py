"""Characterise component: deterministic coverage plus run-local thematic grouping."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

import structlog
from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas.core.embeddings import EMBEDDING_PROFILE, UNIT_POLICY
from policy_atlas.core.prompt_fields import parse_guidance_channel
from policy_atlas.core.schema import (
    DIRECTIVE_STRING_MAX,
    characterisation_result,
    chunk_embedding,
    project_source_snapshot,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    source_tag,
)
from policy_atlas.core.schema import (
    chunk as chunk_table,
)
from policy_atlas.core.tags import insert_source_tags
from policy_atlas.core.usage import UsageResult
from policy_atlas.evidence_base.assess.screen import effective_screen_rows
from policy_atlas.evidence_base.clustering_engine import (
    AssignmentOutput,
    ClusteringBackend,
    ClusteringFailure,
    ClusteringPolicy,
    ClusteringResult,
    ClusterLabel,
    ClusterUnit,
    call_budget_for_unit_count,
    cluster_units,
)
from policy_atlas.evidence_base.corpus import theme_grouping
from policy_atlas.evidence_base.corpus.theme_grouping import (
    UNCLUSTERED,
    GroupingDoc,
    Theme,
    ThemeGroupingBackend,
)

log = structlog.get_logger()

_UNKNOWN_EVIDENCE_TYPE = "Unknown / Insufficient information"

# Fixed namespace for content-keyed theme identity (task 028 pin 7) — never
# rotate: theme_id = uuid5(ns, f"{project_id}:{theme_name}").
_THEME_ID_NAMESPACE = uuid.UUID("6f1cb1e2-9a4e-4b0d-8c6f-028028028028")

# D9/B5 (024 steering surface): characterise's first directive parser.
# ``themes``: fewer|standard|more scales the derived theme-count bounds;
# "standard"/absent is byte-identical to as-built (guard-tested).
# ``guidance``: the shared Family B channel shape, into the theme-DISCOVERY
# prompt only.
THEMES_VALUES = ("fewer", "standard", "more")
THEMES_MULTIPLIERS: dict[str, float] = {"fewer": 0.5, "standard": 1.0, "more": 2.0}


class CharacteriseDirectiveError(ValueError):
    """Malformed ``context["characterise"]`` directive; characterise fails closed."""


def _parse_characterise_directive(raw: Any) -> tuple[str, list[str] | None]:
    """Parse ``context["characterise"]``, characterise's first directive parser.

    Grammar: ``{themes?: "fewer"|"standard"|"more", guidance?: [str, ...]}``.
    Unknown keys reject. ``guidance`` follows the shared Family B shape
    (``parse_guidance_channel``): 1-5 non-empty, bounded, control-character-free
    strings.

    Args:
        raw: The ``context["characterise"]`` object, or ``None``.

    Returns:
        ``(themes, guidance)`` — ``themes`` defaults to ``"standard"``
        (byte-identical to as-built); ``guidance`` is ``None`` when absent.

    Raises:
        CharacteriseDirectiveError: On any malformed shape.
    """
    if raw is None:
        return "standard", None
    if not isinstance(raw, dict):
        raise CharacteriseDirectiveError("characterise directive must be an object")
    unknown = set(raw) - {"themes", "guidance"}
    if unknown:
        raise CharacteriseDirectiveError("characterise directive contains unknown keys")

    themes = "standard"
    if "themes" in raw:
        raw_themes = raw["themes"]
        if not isinstance(raw_themes, str) or raw_themes not in THEMES_VALUES:
            raise CharacteriseDirectiveError(
                f"characterise directive themes must be one of {THEMES_VALUES}"
            )
        themes = raw_themes

    guidance: list[str] | None = None
    if "guidance" in raw:
        guidance = parse_guidance_channel(
            raw["guidance"],
            error=CharacteriseDirectiveError,
            max_chars=DIRECTIVE_STRING_MAX,
        )

    return themes, guidance


@dataclass(frozen=True)
class CharacteriseContext:
    """Scope-level input to characterise.

    Attributes:
        scope_id: The evidence scope whose screened-in corpus is characterised.
        intent: The evidence-scope intent used to ground thematic grouping.
        context: Scope context JSONB, optionally carrying
            ``{"characterise": {"themes": "fewer"|"standard"|"more",
            "guidance": [str, ...]}}`` (D9/B5, 024 steering surface).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


class CharacteriseFailure(Exception):
    """Failure raised after deterministic coverage has been computed.

    Attributes:
        coverage: Deterministic coverage payload for the failed run.
        error: Machine-readable failure summary.
    """

    coverage: dict[str, Any]
    error: str

    def __init__(self, *, coverage: dict[str, Any], error: str) -> None:
        """Create a characterise failure carrying the completed coverage.

        Args:
            coverage: Deterministic coverage payload.
            error: Failure summary.
        """
        super().__init__(error)
        self.coverage = coverage
        self.error = error


@dataclass(frozen=True)
class ScreenedSource:
    """Screened-in source plus cheap downstream signals."""

    pss_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    full_text_snapshot_id: uuid.UUID | None
    origin: str
    full_text_status: str
    full_text_error: str | None
    metadata: dict[str, Any]
    source_locator: str
    text_basis: str
    screen_basis: str | None
    screen_confidence: float | None
    screen_stage: int
    primary_evidence_type: str | None
    quality_score: int | None
    rubric_version: str | None


class _CharacteriseClusteringBackend(ClusteringBackend):
    def __init__(
        self,
        backend: ThemeGroupingBackend,
        *,
        intent: str,
        guidance: list[str] | None = None,
    ) -> None:
        self._backend = backend
        self._intent = intent
        self._guidance = guidance

    def discover(
        self,
        units: list[ClusterUnit],
        *,
        min_labels: int,
        max_labels: int,
    ) -> UsageResult[list[ClusterLabel]]:
        docs = [_doc_payload(unit) for unit in units]
        themes, usage = self._backend.discover(
            docs,
            intent=self._intent,
            min_themes=min_labels,
            max_themes=max_labels,
            guidance=self._guidance,
        )
        return _labels_from_themes(themes), usage

    def assign(
        self,
        batch: list[ClusterUnit],
        *,
        labels: list[ClusterLabel],
    ) -> UsageResult[AssignmentOutput]:
        docs = [_doc_payload(unit) for unit in batch]
        assignments, usage = self._backend.assign(docs, themes=_themes_from_labels(labels))
        return assignments, usage


def _share(count: int, base: int) -> float:
    return 0.0 if base == 0 else count / base


def _bucket(value: Any) -> str:
    if value is None or value == "":
        return "unknown"
    return str(value)


def _increment(distribution: dict[str, int], value: str) -> None:
    distribution[value] = distribution.get(value, 0) + 1


def _distribution(values: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        _increment(counts, _bucket(value))
    return counts


def _screen_confidence_band(value: float) -> str:
    if value < 0.5:
        return "<0.5"
    if value < 0.8:
        return "0.5-0.8"
    return ">=0.8"


def _base_counts(conn: Connection, *, project_id: uuid.UUID, scope_id: uuid.UUID) -> dict[str, int]:
    # Effective-stage-and-status grain (screen.effective_screen_rows): raw row
    # counts would double-count a confirmed doc (relevant at both stages) and
    # leak in a demoted doc (stage-1 relevant, stage-2 not_relevant) as relevant.
    effective = effective_screen_rows()
    status_counts = {
        status: int(count)
        for status, count in conn.execute(
            select(effective.c.status, func.count())
            .where(effective.c.evidence_scope_id == scope_id)
            .where(effective.c.project_id == project_id)
            .group_by(effective.c.status)
        )
    }
    project_sources = int(
        conn.execute(
            select(func.count())
            .select_from(project_source_snapshot)
            .where(project_source_snapshot.c.project_id == project_id)
        ).scalar_one()
    )
    # Docs with screening rows for this scope but no effective (non-failed) row:
    # every attempt failed. Screened-failed at the distinct-source grain, never
    # unscreened — a failed-then-retried doc has an effective row (the retry) and
    # so is excluded from this count, fixing the double-count-against-
    # project_sources bug raw rows caused.
    screen_failed = int(
        conn.execute(
            select(func.count(func.distinct(source_screening_result.c.project_source_snapshot_id)))
            .where(source_screening_result.c.evidence_scope_id == scope_id)
            .where(source_screening_result.c.project_id == project_id)
            .where(
                ~exists().where(
                    (effective.c.evidence_scope_id == scope_id)
                    & (effective.c.project_id == project_id)
                    & (
                        effective.c.project_source_snapshot_id
                        == source_screening_result.c.project_source_snapshot_id
                    )
                )
            )
        ).scalar_one()
    )
    screened_in = status_counts.get("relevant", 0)
    not_relevant = status_counts.get("not_relevant", 0)
    # excluded_retracted (task 019): a distinct, visible effective status —
    # never folded into not_relevant (don't-flatten-status, owner decision).
    excluded_retracted = status_counts.get("excluded_retracted", 0)
    return {
        "screened_in": screened_in,
        "not_relevant": not_relevant,
        "excluded_retracted": excluded_retracted,
        "screen_failed": screen_failed,
        "unscreened": (
            project_sources - screened_in - not_relevant - excluded_retracted - screen_failed
        ),
    }


def screened_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> list[ScreenedSource]:
    """Load relevant screened sources in deterministic project-source order.

    Args:
        conn: Open database connection.
        project_id: Owning project.
        scope_id: Evidence scope whose relevant sources are loaded.

    Returns:
        Screened-in sources enriched with classification and appraisal fields.
    """
    # select is stage-3 of the screening cascade (contract rev 1.10): the
    # candidate set, status and confidence all come from the one effective row
    # per (scope, pss) — never a raw source_screening_result join, which would
    # leak in demoted docs and double-read confirmed ones.
    effective = effective_screen_rows()
    full_text_snapshot = source_snapshot.alias("full_text_snapshot")
    rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.origin,
            project_source_snapshot.c.full_text_snapshot_id,
            project_source_snapshot.c.full_text_status,
            project_source_snapshot.c.full_text_error,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
            source_snapshot.c.text_basis.label("envelope_text_basis"),
            full_text_snapshot.c.text_basis.label("full_text_text_basis"),
            effective.c.screen_basis,
            effective.c.screen_decision_confidence,
            effective.c.screen_stage,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
            source_appraisal_result.c.rubric_version,
        )
        .select_from(
            effective.join(
                project_source_snapshot,
                (
                    effective.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id
                )
                & (effective.c.project_id == project_source_snapshot.c.project_id),
            )
            .join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
            .outerjoin(
                full_text_snapshot,
                project_source_snapshot.c.full_text_snapshot_id
                == full_text_snapshot.c.source_snapshot_id,
            )
            .outerjoin(
                source_classification_result,
                (
                    source_classification_result.c.evidence_scope_id
                    == effective.c.evidence_scope_id
                )
                & (source_classification_result.c.project_id == effective.c.project_id)
                & (
                    source_classification_result.c.project_source_snapshot_id
                    == effective.c.project_source_snapshot_id
                ),
            )
            .outerjoin(
                source_appraisal_result,
                (
                    source_appraisal_result.c.evidence_scope_id
                    == effective.c.evidence_scope_id
                )
                & (source_appraisal_result.c.project_id == effective.c.project_id)
                & (
                    source_appraisal_result.c.project_source_snapshot_id
                    == effective.c.project_source_snapshot_id
                ),
            )
        )
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.project_id == project_id)
        .where(effective.c.status == "relevant")
        .order_by(project_source_snapshot.c.project_source_snapshot_id)
    ).fetchall()

    sources: list[ScreenedSource] = []
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        text_basis = row.envelope_text_basis
        if row.full_text_snapshot_id is not None and row.full_text_text_basis is not None:
            text_basis = row.full_text_text_basis
        sources.append(
            ScreenedSource(
                pss_id=row.project_source_snapshot_id,
                source_snapshot_id=row.source_snapshot_id,
                full_text_snapshot_id=row.full_text_snapshot_id,
                origin=row.origin,
                full_text_status=row.full_text_status,
                full_text_error=row.full_text_error,
                metadata=metadata,
                source_locator=row.source_locator,
                text_basis=text_basis,
                screen_basis=row.screen_basis,
                screen_confidence=row.screen_decision_confidence,
                screen_stage=row.screen_stage,
                primary_evidence_type=row.primary_evidence_type,
                quality_score=row.quality_score,
                rubric_version=row.rubric_version,
            )
        )
    return sources


def _tag_distribution(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pss_ids: list[uuid.UUID],
) -> dict[str, dict[str, int]]:
    if not pss_ids:
        return {}
    rows = conn.execute(
        select(
            source_tag.c.tag_type,
            source_tag.c.asserted_by,
            source_tag.c.tag,
            func.count(),
        )
        .where(source_tag.c.project_id == project_id)
        .where(source_tag.c.project_source_snapshot_id.in_(pss_ids))
        .group_by(source_tag.c.tag_type, source_tag.c.asserted_by, source_tag.c.tag)
        .order_by(source_tag.c.tag_type, source_tag.c.asserted_by, source_tag.c.tag)
    )
    distributions: dict[str, dict[str, int]] = {}
    for tag_type, asserted_by, tag, count in rows:
        key = f"{tag_type}/{asserted_by}"
        if key not in distributions:
            distributions[key] = {}
        distributions[key][tag] = int(count)
    return distributions


def _failed_embedding_count(conn: Connection, sources: list[ScreenedSource]) -> int:
    snapshot_to_pss: dict[uuid.UUID, set[uuid.UUID]] = {}
    for source in sources:
        snapshot_to_pss.setdefault(source.source_snapshot_id, set()).add(source.pss_id)
        if source.full_text_snapshot_id is not None:
            snapshot_to_pss.setdefault(source.full_text_snapshot_id, set()).add(source.pss_id)
    if not snapshot_to_pss:
        return 0

    missing_embedding_filter = ~exists().where(
        (chunk_embedding.c.chunk_id == chunk_table.c.chunk_id)
        & (chunk_embedding.c.embedding_profile == EMBEDDING_PROFILE)
        & (chunk_embedding.c.unit_policy == UNIT_POLICY)
    )
    rows = conn.execute(
        select(chunk_table.c.source_snapshot_id)
        .where(chunk_table.c.source_snapshot_id.in_(list(snapshot_to_pss)))
        .where(missing_embedding_filter)
    )
    failed_pss_ids: set[uuid.UUID] = set()
    for (snapshot_id,) in rows:
        failed_pss_ids.update(snapshot_to_pss[snapshot_id])
    return len(failed_pss_ids)


def _metadata_value(source: ScreenedSource, key: str) -> Any:
    return source.metadata.get(key)


def _quality_value(source: ScreenedSource) -> str:
    if source.quality_score is None:
        return "unappraised"
    return f"{source.quality_score} ({source.rubric_version})"


def _coverage(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    context: CharacteriseContext,
) -> tuple[dict[str, Any], list[ScreenedSource]]:
    sources = screened_sources(conn, project_id=project_id, scope_id=context.scope_id)
    pss_ids = [source.pss_id for source in sources]
    confidence_bands: dict[str, int] = {}
    for source in sources:
        if source.screen_confidence is not None:
            _increment(confidence_bands, _screen_confidence_band(source.screen_confidence))

    full_text_errors: dict[str, int] = {}
    for source in sources:
        if source.full_text_error is not None:
            _increment(full_text_errors, source.full_text_error)

    n = len(sources)
    distributions = {
        "origin": _distribution([source.origin for source in sources]),
        "text_basis": _distribution([source.text_basis for source in sources]),
        "full_text_status": _distribution([source.full_text_status for source in sources]),
        "full_text_error_reasons": full_text_errors,
        "primary_evidence_type": _distribution([
            source.primary_evidence_type or "unclassified" for source in sources
        ]),
        "quality": _distribution([_quality_value(source) for source in sources]),
        "screen_basis": _distribution([source.screen_basis for source in sources]),
        "screen_confidence_bands": confidence_bands,
        "year": _distribution([_metadata_value(source, "year") for source in sources]),
        "language": _distribution([_metadata_value(source, "language") for source in sources]),
        "backend": _distribution([_metadata_value(source, "backend") for source in sources]),
        "publisher_org": _distribution([
            _metadata_value(source, "publisher_org") for source in sources
        ]),
        "tags": _tag_distribution(conn, project_id=project_id, pss_ids=pss_ids),
    }
    rates = {
        "full_text_coverage": _share(
            sum(1 for source in sources if source.full_text_status == "ingested"),
            n,
        ),
        "unknown_classification_share": _share(
            sum(
                1 for source in sources
                if source.primary_evidence_type == _UNKNOWN_EVIDENCE_TYPE
            ),
            n,
        ),
        "failed_embedding_share": _share(_failed_embedding_count(conn, sources), n),
    }
    return (
        {
            "base": "screened",
            "base_counts": _base_counts(conn, project_id=project_id, scope_id=context.scope_id),
            "distributions": distributions,
            "rates": rates,
        },
        sources,
    )


def _doc_for_grouping(source: ScreenedSource) -> GroupingDoc:
    title_value = source.metadata.get("title")
    title = title_value if isinstance(title_value, str) and title_value else source.source_locator
    abstract_value = source.metadata.get("abstract")
    abstract = abstract_value if isinstance(abstract_value, str) else None
    return {"id": str(source.pss_id), "title": title, "abstract": abstract}


def _theme_bounds(n: int, *, themes: str = "standard") -> tuple[int, int]:
    """Derive theme-count bounds for one characterise run.

    D9 (024 steering surface): ``themes`` scales the as-built derived bounds —
    "fewer" halves and "more" doubles both bounds (rounded); "standard" (the
    default) is byte-identical to as-built. The hard floors respected after
    scaling are the same ones the unscaled bounds already enforce: never fewer
    than 1 theme, and never more themes than there are documents (``n``).

    Args:
        n: Number of documents being characterised.
        themes: D9 ``characterise.themes`` value.

    Returns:
        ``(min_themes, max_themes)``.
    """
    min_themes = theme_grouping.MIN_THEMES if n >= theme_grouping.MIN_THEMES else 1
    max_themes = min(n, theme_grouping.MAX_THEMES)
    if themes == "standard":
        return min_themes, max_themes
    multiplier = THEMES_MULTIPLIERS[themes]
    scaled_min = max(1, min(n, round(min_themes * multiplier)))
    scaled_max = max(1, min(n, round(max_themes * multiplier)))
    if scaled_min > scaled_max:
        scaled_min = scaled_max
    return scaled_min, scaled_max


def _call_budget(n: int) -> tuple[int, int, int]:
    plan = call_budget_for_unit_count(
        n,
        assignment_batch_size=theme_grouping.BATCH_SIZE,
        discovery_retry_cap=theme_grouping.DISCOVERY_RETRY_CAP,
        assignment_repair_cap=theme_grouping.ASSIGNMENT_REPAIR_CAP,
    )
    return plan.batch_count, plan.baseline, plan.maximum


def _cluster_characterise_docs(
    *,
    backend: ThemeGroupingBackend,
    docs: list[GroupingDoc],
    intent: str,
    coverage: dict[str, Any],
    themes: str = "standard",
    guidance: list[str] | None = None,
) -> ClusteringResult:
    min_themes, max_themes = _theme_bounds(len(docs), themes=themes)
    _, baseline, maximum = _call_budget(len(docs))
    log.info("characterise.call_budget", baseline=baseline, maximum=maximum)
    try:
        return cluster_units(
            [ClusterUnit(unit_id=doc["id"], payload=doc) for doc in docs],
            backend=_CharacteriseClusteringBackend(backend, intent=intent, guidance=guidance),
            policy=_characterise_clustering_policy(
                min_themes=min_themes,
                max_themes=max_themes,
            ),
        )
    except ClusteringFailure as exc:
        raise CharacteriseFailure(coverage=coverage, error=exc.error) from exc


def _characterise_clustering_policy(*, min_themes: int, max_themes: int) -> ClusteringPolicy:
    return ClusteringPolicy(
        min_labels=min_themes,
        max_labels=max_themes,
        assignment_batch_size=theme_grouping.BATCH_SIZE,
        discovery_retry_cap=theme_grouping.DISCOVERY_RETRY_CAP,
        assignment_repair_cap=theme_grouping.ASSIGNMENT_REPAIR_CAP,
        residual_label=UNCLUSTERED,
        unresolved_policy="fail",
        label_max=theme_grouping.THEME_NAME_MAX,
        description_max=theme_grouping.THEME_DESC_MAX,
        forbidden_label_reason=_forbidden_theme_reason,
        label_noun="theme",
        log_event_prefix="characterise",
        max_concurrent_batches=theme_grouping.MAX_CONCURRENT_BATCHES,
    )


def _forbidden_theme_reason(index: int, label: str) -> str | None:
    if label.casefold() == UNCLUSTERED:
        return f"theme {index} name collides with the {UNCLUSTERED!r} sentinel"
    return None


def _doc_payload(unit: ClusterUnit) -> GroupingDoc:
    return cast("GroupingDoc", unit.payload)


def _labels_from_themes(themes: list[Theme]) -> list[ClusterLabel]:
    return [
        ClusterLabel(label=theme["name"], description=theme["description"])
        for theme in themes
    ]


def _themes_from_labels(labels: list[ClusterLabel]) -> list[Theme]:
    return [
        {"name": label.label, "description": label.description}
        for label in labels
    ]


def _grouping_provenance(
    *,
    backend: ThemeGroupingBackend,
    discovery_retries_used: int,
    repair_calls_used: int,
    discovery_rejections: list[str],
    themes: str = "standard",
    guidance: list[str] | None = None,
) -> dict[str, Any]:
    model = theme_grouping.DISCOVERY_MODEL if backend.mode == "live" else "stub"
    assignment_model = theme_grouping.ASSIGNMENT_MODEL if backend.mode == "live" else "stub"
    return {
        "prompt_version": theme_grouping.PROMPT_VERSION,
        "discovery_model": model,
        "assignment_model": assignment_model,
        "batch_size": theme_grouping.BATCH_SIZE,
        "discovery_retry_cap": theme_grouping.DISCOVERY_RETRY_CAP,
        "assignment_repair_cap": theme_grouping.ASSIGNMENT_REPAIR_CAP,
        "discovery_retries_used": discovery_retries_used,
        "discovery_rejections": discovery_rejections,
        "repair_calls_used": repair_calls_used,
        "backend_mode": backend.mode,
        # D9/B5 (024 steering surface): executed themes bound directive and
        # guidance, echoed verbatim — "standard"/absent are byte-identical to
        # as-built.
        "themes": themes,
        "guidance": list(guidance) if guidance else None,
    }


def _theme_payload(
    themes: list[Theme],
    assignments: dict[str, str],
    theme_ids: dict[str, uuid.UUID],
) -> dict[str, Any]:
    member_ids_by_theme: dict[str, list[str]] = {theme["name"]: [] for theme in themes}
    unclustered_ids: list[str] = []
    for doc_id, theme_name in assignments.items():
        if theme_name == UNCLUSTERED:
            unclustered_ids.append(doc_id)
        else:
            member_ids_by_theme[theme_name].append(doc_id)
    return {
        "themes": [
            {
                "theme_id": str(theme_ids[theme["name"]]),
                "name": theme["name"],
                "description": theme["description"],
                "member_ids": member_ids_by_theme[theme["name"]],
                "size": len(member_ids_by_theme[theme["name"]]),
            }
            for theme in themes
        ],
        "unclustered_ids": unclustered_ids,
    }


def _insert_theme_tags(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    assignments: dict[str, str],
    theme_ids: dict[str, uuid.UUID],
    now: datetime,
) -> None:
    for theme_name, theme_id in theme_ids.items():
        insert_source_tags(
            conn,
            project_id=project_id,
            run_id=run_id,
            now=now,
            assertions=[
                (uuid.UUID(doc_id), theme_name, "characterise")
                for doc_id, assigned_theme in assignments.items()
                if assigned_theme == theme_name
            ],
            theme_id=theme_id,
        )


def _summary(
    *,
    coverage: dict[str, Any],
    theme_payload: dict[str, Any],
    n: int,
    flags: list[str],
    provenance: dict[str, Any],
    usage_totals: dict[str, int],
) -> dict[str, Any]:
    unclustered_ids = theme_payload["unclustered_ids"]
    return {
        "coverage": coverage,
        "themes": [
            {
                "name": theme["name"],
                "description": theme["description"],
                "size": theme["size"],
            }
            for theme in theme_payload["themes"]
        ],
        "unclustered": {
            "count": len(unclustered_ids),
            "share": _share(len(unclustered_ids), n),
        },
        "flags": flags,
        "provenance": provenance,
        "usage_totals": usage_totals,
    }


def characterise_scope(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: CharacteriseContext,
    theme_grouping_backend: ThemeGroupingBackend,
) -> dict[str, Any]:
    """Characterise a screened evidence scope.

    Deterministic coverage is always computed first. The thematic grouping stage
    then discovers themes and assigns documents with code-owned validation and one
    targeted repair call per invalid batch. Duplicate-same-theme assignments are
    handled at the ``ThemeGroupingBackend.assign`` seam before this caller receives the
    mapping. No tags or characterisation row are written until grouping fully
    succeeds; on grouping failure, ``CharacteriseFailure`` carries the coverage.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run writing the characterisation.
        context: Scope-level characterise input.
        theme_grouping_backend: The live or stub theme grouping backend.

    Returns:
        Landscape summary payload for ``component.completed``.

    Raises:
        CharacteriseDirectiveError: If ``context.context["characterise"]`` is
            malformed.
        CharacteriseFailure: If discovery, assignment repair, call budget or the
            grouping count invariant fails after coverage has been computed.
    """
    themes_directive, guidance = _parse_characterise_directive(
        context.context.get("characterise")
    )
    coverage, sources = _coverage(conn, project_id=project_id, context=context)
    docs = [_doc_for_grouping(source) for source in sources]
    n = len(docs)
    flags: list[str] = []
    discovery_retries_used = 0
    discovery_rejections: list[str] = []
    repair_calls_used = 0
    usage_totals = {"prompt": 0, "completion": 0, "total": 0, "cached": 0}

    if n == 0:
        flags.append("empty_scope")
        themes: list[Theme] = []
        assignments: dict[str, str] = {}
    else:
        clustering = _cluster_characterise_docs(
            backend=theme_grouping_backend,
            docs=docs,
            intent=context.intent,
            coverage=coverage,
            themes=themes_directive,
            guidance=guidance,
        )
        themes = _themes_from_labels(clustering.labels)
        assignments = clustering.assignments
        discovery_retries_used = clustering.discovery_retries_used
        discovery_rejections = clustering.discovery_rejections
        repair_calls_used = clustering.assignment_repair_calls_used
        usage_totals = clustering.usage_totals
        if repair_calls_used:
            flags.append("repair_path_taken")

    grouped = sum(1 for theme_name in assignments.values() if theme_name != UNCLUSTERED)
    unclustered_count = sum(1 for theme_name in assignments.values() if theme_name == UNCLUSTERED)
    if grouped + unclustered_count != n:
        raise CharacteriseFailure(
            coverage=coverage,
            error=(
                "grouping invariant violated: "
                f"screened_in={n} grouped={grouped} unclustered={unclustered_count}"
            ),
        )

    provenance = _grouping_provenance(
        backend=theme_grouping_backend,
        discovery_retries_used=discovery_retries_used,
        repair_calls_used=repair_calls_used,
        discovery_rejections=discovery_rejections,
        themes=themes_directive,
        guidance=guidance,
    )
    # Content-keyed (project, name) identity: deterministic across re-runs so
    # stub runs stay byte-identical and a re-characterise that keeps a theme's
    # name keeps its id (theme-filter bookmarks survive).
    theme_ids = {
        theme["name"]: uuid.uuid5(_THEME_ID_NAMESPACE, f"{project_id}:{theme['name']}")
        for theme in themes
    }
    theme_payload = _theme_payload(themes, assignments, theme_ids)
    now = datetime.now(UTC)
    _insert_theme_tags(
        conn,
        project_id=project_id,
        run_id=run_id,
        assignments=assignments,
        theme_ids=theme_ids,
        now=now,
    )
    conn.execute(
        characterisation_result.insert().values(
            characterisation_id=uuid.uuid4(),
            project_id=project_id,
            evidence_scope_id=context.scope_id,
            run_id=run_id,
            grouping_provenance=provenance,
            coverage=coverage,
            themes=theme_payload,
            created_at=now,
        )
    )
    return _summary(
        coverage=coverage,
        theme_payload=theme_payload,
        n=n,
        flags=flags,
        provenance=provenance,
        usage_totals=usage_totals,
    )
