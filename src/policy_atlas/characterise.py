"""Characterise component: deterministic coverage plus run-local thematic grouping."""

from __future__ import annotations

import math
import uuid
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas import grouping
from policy_atlas.embeddings import EMBEDDING_PROFILE, UNIT_POLICY
from policy_atlas.grouping import (
    UNCLUSTERED,
    GroupingDoc,
    InvalidDiscoveryOutput,
    Theme,
    ThemeGroupingBackend,
    validate_themes,
)
from policy_atlas.schema import (
    characterisation_result,
    chunk_embedding,
    project_source_snapshot,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    source_tag,
)
from policy_atlas.schema import (
    chunk as chunk_table,
)
from policy_atlas.screen import effective_screen_rows
from policy_atlas.tags import insert_source_tags

log = structlog.get_logger()

_UNKNOWN_EVIDENCE_TYPE = "Unknown / Insufficient information"


@dataclass(frozen=True)
class CharacteriseContext:
    """Scope-level input to characterise.

    Attributes:
        scope_id: The evidence scope whose screened-in corpus is characterised.
        intent: The evidence-scope intent used to ground thematic grouping.
        context: Scope context JSONB, carried for signature parity with peers.
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


@dataclass(frozen=True)
class _AssignmentAttempt:
    batch_index: int
    batch: list[GroupingDoc]
    assignments: dict[str, str] | None
    error_type: str | None


@dataclass(frozen=True)
class _AssignmentValidation:
    valid: dict[str, str]
    residue: list[GroupingDoc]
    invented_count: int
    missing_count: int
    unknown_theme_count: int


@dataclass
class _CallBudget:
    maximum: int
    coverage: dict[str, Any]
    count: int = 0

    def reserve(self) -> None:
        if self.count >= self.maximum:
            raise CharacteriseFailure(coverage=self.coverage, error="call budget exceeded")
        self.count += 1


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
    return {
        "screened_in": screened_in,
        "not_relevant": not_relevant,
        "screen_failed": screen_failed,
        "unscreened": project_sources - screened_in - not_relevant - screen_failed,
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


def _theme_bounds(n: int) -> tuple[int, int]:
    min_themes = grouping.MIN_THEMES if n >= grouping.MIN_THEMES else 1
    max_themes = min(n, grouping.MAX_THEMES)
    return min_themes, max_themes


def _call_budget(n: int) -> tuple[int, int, int]:
    batch_count = math.ceil(n / grouping.BATCH_SIZE)
    baseline = 1 + batch_count
    maximum = (
        1 + grouping.DISCOVERY_RETRY_CAP
        + batch_count * (1 + grouping.ASSIGNMENT_REPAIR_CAP)
    )
    return batch_count, baseline, maximum


def _discover_themes(
    *,
    backend: ThemeGroupingBackend,
    docs: list[GroupingDoc],
    intent: str,
    min_themes: int,
    max_themes: int,
    budget: _CallBudget,
) -> tuple[list[Theme], int]:
    for attempt in range(grouping.DISCOVERY_RETRY_CAP + 1):
        budget.reserve()
        try:
            themes = validate_themes(
                backend.discover(
                    docs,
                    intent=intent,
                    min_themes=min_themes,
                    max_themes=max_themes,
                ),
                min_themes=min_themes,
                max_themes=max_themes,
            )
        except InvalidDiscoveryOutput as exc:
            error_type = type(exc).__name__
        except Exception as exc:
            error_type = type(exc).__name__
        else:
            return themes, attempt
        log.warning(
            "characterise.discovery_invalid",
            attempt=attempt + 1,
            retry_cap=grouping.DISCOVERY_RETRY_CAP,
            error_type=error_type,
        )
    raise CharacteriseFailure(
        coverage=budget.coverage,
        error=f"discovery failed after {grouping.DISCOVERY_RETRY_CAP + 1} attempts",
    )


def _batches(docs: list[GroupingDoc]) -> list[list[GroupingDoc]]:
    return [
        docs[start:start + grouping.BATCH_SIZE]
        for start in range(0, len(docs), grouping.BATCH_SIZE)
    ]


def _validate_assignments(
    batch: list[GroupingDoc],
    assignments: dict[str, str],
    *,
    theme_names: set[str],
) -> _AssignmentValidation:
    batch_ids = {doc["id"] for doc in batch}
    valid: dict[str, str] = {}
    residue_ids: set[str] = set()
    invented_count = 0
    unknown_theme_count = 0

    for doc_id, theme in assignments.items():
        if doc_id not in batch_ids:
            invented_count += 1
            continue
        if theme == UNCLUSTERED or theme in theme_names:
            valid[doc_id] = theme
        else:
            residue_ids.add(doc_id)
            unknown_theme_count += 1

    missing_ids = batch_ids - set(valid) - residue_ids
    residue_ids.update(missing_ids)
    residue = [doc for doc in batch if doc["id"] in residue_ids]
    return _AssignmentValidation(
        valid=valid,
        residue=residue,
        invented_count=invented_count,
        missing_count=len(missing_ids),
        unknown_theme_count=unknown_theme_count,
    )


def _run_first_assignment_round(
    *,
    backend: ThemeGroupingBackend,
    batches: list[list[GroupingDoc]],
    themes: list[Theme],
    budget: _CallBudget,
) -> list[_AssignmentAttempt]:
    for _ in batches:
        budget.reserve()

    submitted: list[tuple[int, list[GroupingDoc], Future[dict[str, str]]]] = []
    with ThreadPoolExecutor(max_workers=grouping.MAX_CONCURRENT_BATCHES) as executor:
        for batch_index, batch in enumerate(batches, start=1):
            submitted.append(
                (batch_index, batch, executor.submit(backend.assign, batch, themes=themes))
            )
        wait([future for _, _, future in submitted])

    attempts: list[_AssignmentAttempt] = []
    for batch_index, batch, future in submitted:
        try:
            assignments = future.result()
        except Exception as exc:
            log.warning(
                "characterise.assignment_batch_failed",
                batch_index=batch_index,
                batch_size=len(batch),
                error_type=type(exc).__name__,
            )
            attempts.append(
                _AssignmentAttempt(
                    batch_index=batch_index,
                    batch=batch,
                    assignments=None,
                    error_type=type(exc).__name__,
                )
            )
        else:
            attempts.append(
                _AssignmentAttempt(
                    batch_index=batch_index,
                    batch=batch,
                    assignments=assignments,
                    error_type=None,
                )
            )
    return attempts


def _resolve_assignment_batch(
    *,
    backend: ThemeGroupingBackend,
    attempt: _AssignmentAttempt,
    themes: list[Theme],
    theme_names: set[str],
    budget: _CallBudget,
) -> tuple[dict[str, str], bool]:
    # A failed first call (assignments None) validates as an empty mapping: the
    # whole batch becomes missing residue, identical to the hand-built case.
    validation = _validate_assignments(
        attempt.batch,
        attempt.assignments or {},
        theme_names=theme_names,
    )

    if not validation.residue:
        return validation.valid, False

    log.info(
        "characterise.assignment_repair",
        batch_index=attempt.batch_index,
        residue_count=len(validation.residue),
        invented_count=validation.invented_count,
        missing_count=validation.missing_count,
        unknown_theme_count=validation.unknown_theme_count,
        first_error_type=attempt.error_type,
    )
    budget.reserve()
    try:
        repair_assignments = backend.assign(validation.residue, themes=themes)
    except Exception as exc:
        raise CharacteriseFailure(
            coverage=budget.coverage,
            error=f"assignment repair failed for batch {attempt.batch_index}: {type(exc).__name__}",
        ) from exc

    repair_validation = _validate_assignments(
        validation.residue,
        repair_assignments,
        theme_names=theme_names,
    )
    if repair_validation.residue:
        raise CharacteriseFailure(
            coverage=budget.coverage,
            error=(
                f"assignment repair left {len(repair_validation.residue)} unresolved "
                f"docs in batch {attempt.batch_index}"
            ),
        )
    merged = dict(validation.valid)
    merged.update(repair_validation.valid)
    return merged, True


def _assign_docs(
    *,
    backend: ThemeGroupingBackend,
    docs: list[GroupingDoc],
    themes: list[Theme],
    budget: _CallBudget,
) -> tuple[dict[str, str], int]:
    theme_names = {theme["name"] for theme in themes}
    first_round = _run_first_assignment_round(
        backend=backend,
        batches=_batches(docs),
        themes=themes,
        budget=budget,
    )
    assignments: dict[str, str] = {}
    repair_calls_used = 0
    for attempt in first_round:
        batch_assignments, repaired = _resolve_assignment_batch(
            backend=backend,
            attempt=attempt,
            themes=themes,
            theme_names=theme_names,
            budget=budget,
        )
        assignments.update(batch_assignments)
        repair_calls_used += 1 if repaired else 0
    return assignments, repair_calls_used


def _grouping_provenance(
    *,
    backend: ThemeGroupingBackend,
    discovery_retries_used: int,
    repair_calls_used: int,
) -> dict[str, Any]:
    model = grouping.DISCOVERY_MODEL if backend.mode == "live" else "stub"
    assignment_model = grouping.ASSIGNMENT_MODEL if backend.mode == "live" else "stub"
    return {
        "prompt_version": grouping.PROMPT_VERSION,
        "discovery_model": model,
        "assignment_model": assignment_model,
        "batch_size": grouping.BATCH_SIZE,
        "discovery_retry_cap": grouping.DISCOVERY_RETRY_CAP,
        "assignment_repair_cap": grouping.ASSIGNMENT_REPAIR_CAP,
        "discovery_retries_used": discovery_retries_used,
        "repair_calls_used": repair_calls_used,
        "backend_mode": backend.mode,
    }


def _theme_payload(themes: list[Theme], assignments: dict[str, str]) -> dict[str, Any]:
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
    now: datetime,
) -> None:
    insert_source_tags(
        conn,
        project_id=project_id,
        run_id=run_id,
        now=now,
        assertions=[
            (uuid.UUID(doc_id), theme_name, "characterise")
            for doc_id, theme_name in assignments.items()
            if theme_name != UNCLUSTERED
        ],
    )


def _summary(
    *,
    coverage: dict[str, Any],
    theme_payload: dict[str, Any],
    n: int,
    flags: list[str],
    provenance: dict[str, Any],
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
        CharacteriseFailure: If discovery, assignment repair, call budget or the
            grouping count invariant fails after coverage has been computed.
    """
    coverage, sources = _coverage(conn, project_id=project_id, context=context)
    docs = [_doc_for_grouping(source) for source in sources]
    n = len(docs)
    flags: list[str] = []
    discovery_retries_used = 0
    repair_calls_used = 0

    if n == 0:
        flags.append("empty_scope")
        themes: list[Theme] = []
        assignments: dict[str, str] = {}
    else:
        min_themes, max_themes = _theme_bounds(n)
        _, baseline, maximum = _call_budget(n)
        log.info("characterise.call_budget", baseline=baseline, maximum=maximum)
        budget = _CallBudget(maximum=maximum, coverage=coverage)
        themes, discovery_retries_used = _discover_themes(
            backend=theme_grouping_backend,
            docs=docs,
            intent=context.intent,
            min_themes=min_themes,
            max_themes=max_themes,
            budget=budget,
        )
        assignments, repair_calls_used = _assign_docs(
            backend=theme_grouping_backend,
            docs=docs,
            themes=themes,
            budget=budget,
        )
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
    )
    theme_payload = _theme_payload(themes, assignments)
    now = datetime.now(UTC)
    _insert_theme_tags(
        conn,
        project_id=project_id,
        run_id=run_id,
        assignments=assignments,
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
    )
