"""Appraise component — per-document evidence-hierarchy score over the classified set.

The v3.0 light pass is deterministic *by design*, not a stub: a document-type-based
tier that maps each classification's ``primary_evidence_type`` through the default
rubric (v2's expert-calibrated five-point hierarchy carried forward). The steerable
plan-carried rubric and the full-text second pass are deferred seams.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.schema import (
    project_source_snapshot,
    source_appraisal_result,
    source_classification_result,
    source_screening_result,
)

log = structlog.get_logger()

DEFAULT_RUBRIC_VERSION = "v2-hierarchy-v1"

# The v3.0 default rubric: primary_evidence_type → quality_score (5 = strongest),
# v2's expert-calibrated five-point evidence-hierarchy rating carried forward.
# Its domain defines appraisability: types absent from it (Other/Non-evidence,
# Unknown) are skipped-and-counted, never scored. Keys come from EVIDENCE_TYPES
# (schema.py); a test enforces the domain is exactly EVIDENCE_TYPES minus the two
# non-appraisable types.
DEFAULT_RUBRIC: dict[str, int] = {
    "Systematic Review and Meta-Analysis":   5,
    "RCTs and Quasi-Experimental Studies":   4,
    "Observational Research Studies":        3,
    "Modelling & Simulation":                2,
    "Policy Syntheses & Guidance Documents": 2,
    "Qualitative & Contextual Evidence":     2,
    "Expert Opinion and Commentary":         1,
}

# Presentation copy only — applied at read time (UI, reports, exports); never persisted,
# never in event payloads (a stored label could drift from its score; rewording is a
# one-dict change with no migration). Policy team owns the wording — retune freely.
SCORE_LABELS: dict[int, str] = {
    5: "Very strong",
    4: "Strong",
    3: "Moderate",
    2: "Limited",
    1: "Weak",
}

_NON_EVIDENCE_TYPE = "Other (Non-evidence documents)"
_UNKNOWN_TYPE = "Unknown / Insufficient information"


@dataclass
class AppraiseContext:
    """Scope-level input to an appraise run.

    Attributes:
        scope_id: The screening scope whose classified set is appraised.
        intent: The scope's research intent (from screening_scope.intent).
        context: The scope's context JSONB (from screening_scope.context).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass
class AppraiseResult:
    """One document's appraisal outcome.

    Attributes:
        quality_score: 1..5, 5 = strongest (v2 evidence-hierarchy rating).
        rubric_version: Rubric that produced the score; always
            DEFAULT_RUBRIC_VERSION in v3.0.
    """

    quality_score: int
    rubric_version: str


def appraise_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: AppraiseContext,
) -> dict[str, Any]:
    """Appraise all classified evidence sources for a screening scope.

    Reads source_classification_result rows for the scope; for each whose
    primary_evidence_type is in DEFAULT_RUBRIC, inserts one
    source_appraisal_result row and emits a source.appraised event. Types
    outside the rubric's domain (Non-evidence, Unknown) are skipped and
    counted, never scored. Already-appraised rows are skipped (idempotent).

    Args:
        conn: Open database connection; all writes occur within its transaction.
        project_id: Owning project.
        run_id: The run recorded as appraised_by_run_id.
        context: Scope-level input naming the classified set.

    Returns:
        Counts: ``appraised`` (rows inserted this call), ``by_score`` (sparse,
        int-keyed), ``skipped_non_evidence`` / ``skipped_unknown`` /
        ``unclassified`` (recomputed from current state every call), and
        ``already_appraised`` (pre-existing appraisal rows for the scope).
        Invariant: appraised + already_appraised + skipped_non_evidence +
        skipped_unknown = classification rows for the scope.
    """
    scoped_classifications = (
        (source_classification_result.c.screening_scope_id == context.scope_id)
        & (source_classification_result.c.project_id == project_id)
    )

    # Pre-insert count: appraisal rows already present for the scope (idempotency skips).
    already_appraised = conn.execute(
        select(func.count())
        .select_from(source_appraisal_result)
        .where(source_appraisal_result.c.screening_scope_id == context.scope_id)
        .where(source_appraisal_result.c.project_id == project_id)
    ).scalar_one()

    # Skip counts are recomputed from the full classification set on every call
    # (not the not-yet-appraised remainder), so reruns report the same numbers.
    skip_counts: dict[str, int] = {
        evidence_type: count
        for evidence_type, count in conn.execute(
            select(source_classification_result.c.primary_evidence_type, func.count())
            .where(scoped_classifications)
            .where(source_classification_result.c.primary_evidence_type.not_in(
                list(DEFAULT_RUBRIC)
            ))
            .group_by(source_classification_result.c.primary_evidence_type)
        ).fetchall()
    }

    # Relevant-but-unclassified rows: reported, never processed — makes a
    # skipped-classify misconfiguration visible. Anti-join, not count subtraction
    # (no FK guarantees classification rows are a subset of screening rows).
    unclassified = conn.execute(
        select(func.count())
        .select_from(source_screening_result)
        .where(source_screening_result.c.screening_scope_id == context.scope_id)
        .where(source_screening_result.c.project_id == project_id)
        .where(source_screening_result.c.status == "relevant")
        .where(
            ~exists().where(
                (source_classification_result.c.screening_scope_id == context.scope_id)
                & (source_classification_result.c.project_source_snapshot_id
                   == source_screening_result.c.project_source_snapshot_id)
            )
        )
    ).scalar_one()

    appraisable_rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            source_classification_result.c.primary_evidence_type,
        )
        .join_from(
            source_classification_result,
            project_source_snapshot,
            (source_classification_result.c.project_source_snapshot_id
             == project_source_snapshot.c.project_source_snapshot_id)
            & (source_classification_result.c.project_id
               == project_source_snapshot.c.project_id),
        )
        .where(scoped_classifications)
        .where(source_classification_result.c.primary_evidence_type.in_(list(DEFAULT_RUBRIC)))
        .where(
            ~exists().where(
                (source_appraisal_result.c.screening_scope_id == context.scope_id)
                & (source_appraisal_result.c.project_source_snapshot_id
                   == project_source_snapshot.c.project_source_snapshot_id)
            )
        )
    ).fetchall()

    by_score: dict[int, int] = {}

    for pss_id, snap_id, evidence_type in appraisable_rows:
        result = AppraiseResult(
            quality_score=DEFAULT_RUBRIC[evidence_type],
            rubric_version=DEFAULT_RUBRIC_VERSION,
        )

        conn.execute(
            source_appraisal_result.insert().values(
                source_appraisal_result_id=uuid.uuid4(),
                screening_scope_id=context.scope_id,
                project_source_snapshot_id=pss_id,
                project_id=project_id,
                appraised_by_run_id=run_id,
                quality_score=result.quality_score,
                rubric_version=result.rubric_version,
                appraised_at=datetime.now(UTC),
            )
        )

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="source.appraised",
            payload={
                "source_snapshot_id": str(snap_id),
                "project_source_snapshot_id": str(pss_id),
                "screening_scope_id": str(context.scope_id),
                "quality_score": result.quality_score,
                "rubric_version": result.rubric_version,
            },
        )

        by_score[result.quality_score] = by_score.get(result.quality_score, 0) + 1

    return {
        "appraised": len(appraisable_rows),
        "by_score": by_score,
        "skipped_non_evidence": skip_counts.get(_NON_EVIDENCE_TYPE, 0),
        "skipped_unknown": skip_counts.get(_UNKNOWN_TYPE, 0),
        "already_appraised": already_appraised,
        "unclassified": unclassified,
    }
