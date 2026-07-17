"""Appraise component — per-document evidence-hierarchy score over the classified set.

The v3.0 light pass is deterministic *by design*, not a stub: a document-type-based
tier that maps each classification's ``primary_evidence_type`` through the default
rubric (v2's expert-calibrated five-point hierarchy carried forward). The steerable
plan-carried rubric and the full-text second pass are deferred seams.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas.core import events
from policy_atlas.core.schema import (
    EVIDENCE_TYPES,
    project_source_snapshot,
    source_appraisal_result,
    source_classification_result,
)
from policy_atlas.evidence_base.assess.screen import effective_screen_rows

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


class AppraiseDirectiveError(Exception):
    """Malformed appraisal directive; appraise fails closed."""


def _parse_appraisal_directive(raw: Any) -> dict[str, int]:
    """Parse the scope-context appraisal directive into a partial rubric override.

    Mirrors the select ``_parse_directive`` house pattern (unknown keys
    rejected, types validated, fail-closed throughout). Grammar:
    ``{rubric?: {evidence_type: tier}}``.

    - Unknown top-level keys (anything but ``rubric``) reject.
    - ``rubric``, when present, must be a non-empty partial map. Its keys
      must be exact strings from ``EVIDENCE_TYPES`` (schema.py's closed
      type vocabulary) — anything else rejects. Its values must be ints
      1..5 — anything else (including bool, float, out-of-range) rejects.
    - An empty ``rubric`` map rejects: a directive with no scoring effect
      is meaningless and must not silently no-op.

    Args:
        raw: The ``context["appraisal"]`` object, or ``None``.

    Returns:
        The partial ``evidence_type -> tier`` override map. ``{}`` when no
        directive is present (``raw`` is ``None`` or an empty object).

    Raises:
        AppraiseDirectiveError: On any malformed shape.
    """
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise AppraiseDirectiveError("appraisal directive must be an object")
    if not raw:
        return {}
    unknown = set(raw) - {"rubric"}
    if unknown:
        raise AppraiseDirectiveError("appraisal directive contains unknown keys")
    if "rubric" not in raw:
        return {}

    rubric_raw = raw["rubric"]
    if not isinstance(rubric_raw, dict) or not rubric_raw:
        raise AppraiseDirectiveError("appraisal directive rubric must be a non-empty object")

    override: dict[str, int] = {}
    for evidence_type, tier in rubric_raw.items():
        if evidence_type not in EVIDENCE_TYPES:
            raise AppraiseDirectiveError(
                "appraisal directive rubric contains an unknown evidence type"
            )
        if isinstance(tier, bool) or not isinstance(tier, int):
            raise AppraiseDirectiveError("appraisal directive rubric tier must be an integer")
        if not 1 <= tier <= 5:
            raise AppraiseDirectiveError(
                "appraisal directive rubric tier must be between 1 and 5"
            )
        override[evidence_type] = tier
    return override


def _derive_rubric_version(override: dict[str, int]) -> str:
    """Derive the ``rubric_version`` for an (optionally overridden) rubric.

    No override -> ``DEFAULT_RUBRIC_VERSION`` byte-identical (guard-tested).
    An override derives ``f"{DEFAULT_RUBRIC_VERSION}+{hash8}"`` where
    ``hash8`` is the first 8 hex characters of the sha256 digest of the
    override's canonical JSON (``json.dumps(override, sort_keys=True,
    separators=(",", ":"))``) — deterministic: the same override always
    derives the same version string, and travels in every
    ``source_appraisal_result.rubric_version`` row exactly as the base
    version does today.

    Args:
        override: The partial ``evidence_type -> tier`` override map (``{}``
            for no override).

    Returns:
        The ``rubric_version`` string to persist on every appraisal row
        produced by this run.
    """
    if not override:
        return DEFAULT_RUBRIC_VERSION
    canonical_json = json.dumps(override, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:8]
    return f"{DEFAULT_RUBRIC_VERSION}+{digest}"


@dataclass
class AppraiseContext:
    """Scope-level input to an appraise run.

    Attributes:
        scope_id: The screening scope whose classified set is appraised.
        intent: The scope's research intent (from evidence_scope.intent).
        context: The scope's context JSONB (from evidence_scope.context).
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass
class AppraiseResult:
    """One document's appraisal outcome.

    Attributes:
        quality_score: 1..5, 5 = strongest (v2 evidence-hierarchy rating).
        rubric_version: Rubric that produced the score; ``DEFAULT_RUBRIC_VERSION``
            unless a scope-context ``appraisal.rubric`` override is in effect (D1),
            in which case it is the derived ``f"{base}+{hash8}"`` version.
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
    primary_evidence_type is in the effective rubric's domain, inserts one
    source_appraisal_result row and emits a source.appraised event. Types
    outside the effective rubric's domain are skipped and counted, never
    scored. Already-appraised rows are skipped (idempotent).

    D1 steering: ``context.context["appraisal"]`` may carry
    ``{"rubric": {evidence_type: tier}}``, a partial override parsed
    fail-closed by ``_parse_appraisal_directive``. The effective rubric is
    DEFAULT_RUBRIC overlaid with the override (the override's types and
    tiers win; unmentioned types keep their default tier); the effective
    rubric's key set is this run's appraisability domain, so overriding a
    normally non-appraisable type (e.g. "Other (Non-evidence documents)")
    makes it scorable for this run — a deliberate consequence of the
    override, not special-cased away. ``rubric_version`` is derived from the
    override (``_derive_rubric_version``) and travels on every row this run
    produces, exactly as the unversioned default does today. No override
    reproduces today's behaviour byte-for-byte.

    Args:
        conn: Open database connection; all writes occur within its transaction.
        project_id: Owning project.
        run_id: The run recorded as appraised_by_run_id.
        context: Scope-level input naming the classified set and optionally
            carrying the appraisal directive.

    Raises:
        AppraiseDirectiveError: If ``context.context["appraisal"]`` is malformed.

    Returns:
        Counts: ``appraised`` (rows inserted this call), ``by_score`` (sparse,
        int-keyed), ``skipped_non_evidence`` / ``skipped_unknown`` /
        ``unclassified`` (recomputed from current state every call),
        ``skipped_demoted`` (rubric-domain classifications whose doc is no
        longer effective-relevant, e.g. stage-2 demoted — never appraised),
        and ``already_appraised`` (pre-existing appraisal rows for the scope).
        Invariant: appraised + already_appraised + skipped_non_evidence +
        skipped_unknown + skipped_demoted = classification rows for the scope.
    """
    rubric_override = _parse_appraisal_directive(context.context.get("appraisal"))
    effective_rubric: dict[str, int] = {**DEFAULT_RUBRIC, **rubric_override}
    rubric_version = _derive_rubric_version(rubric_override)

    scoped_classifications = (
        (source_classification_result.c.evidence_scope_id == context.scope_id)
        & (source_classification_result.c.project_id == project_id)
    )

    # Pre-insert count: appraisal rows already present for the scope (idempotency skips).
    already_appraised = conn.execute(
        select(func.count())
        .select_from(source_appraisal_result)
        .where(source_appraisal_result.c.evidence_scope_id == context.scope_id)
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
                list(effective_rubric)
            ))
            .group_by(source_classification_result.c.primary_evidence_type)
        ).fetchall()
    }

    # Relevant-but-unclassified rows: reported, never processed — makes a
    # skipped-classify misconfiguration visible. Anti-join, not count subtraction
    # (no FK guarantees classification rows are a subset of screening rows).
    # Effective-relevant via the helper: a raw status='relevant' join would count
    # a stage-2-demoted doc's superseded stage-1 row as "relevant but
    # unclassified", even though classify correctly skips it.
    effective = effective_screen_rows()
    unclassified = conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.evidence_scope_id == context.scope_id)
        .where(effective.c.project_id == project_id)
        .where(effective.c.status == "relevant")
        .where(
            ~exists().where(
                (source_classification_result.c.evidence_scope_id == context.scope_id)
                & (source_classification_result.c.project_id == project_id)
                & (source_classification_result.c.project_source_snapshot_id
                   == effective.c.project_source_snapshot_id)
            )
        )
    ).scalar_one()

    # The write path is effective-grained too: a doc classified before a
    # stage-2 demotion must not gain an appraisal on a rerun (014 review
    # finding). The exclusion is counted below (skipped_demoted), never silent.
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
        .join(
            effective,
            (effective.c.project_source_snapshot_id
             == project_source_snapshot.c.project_source_snapshot_id)
            & (effective.c.project_id == project_source_snapshot.c.project_id),
        )
        .where(effective.c.evidence_scope_id == context.scope_id)
        .where(effective.c.status == "relevant")
        .where(scoped_classifications)
        .where(source_classification_result.c.primary_evidence_type.in_(list(effective_rubric)))
        .where(
            ~exists().where(
                (source_appraisal_result.c.evidence_scope_id == context.scope_id)
                & (source_appraisal_result.c.project_id == project_id)
                & (source_appraisal_result.c.project_source_snapshot_id
                   == project_source_snapshot.c.project_source_snapshot_id)
            )
        )
    ).fetchall()

    # Rubric-domain classifications whose doc is no longer effective-relevant
    # (stage-2 demoted): excluded from the write path above, reported here.
    # Already-appraised docs are excluded so the returned counts stay an exact
    # partition of the scope's classification rows (see Returns invariant).
    skipped_demoted = conn.execute(
        select(func.count())
        .select_from(source_classification_result)
        .where(scoped_classifications)
        .where(source_classification_result.c.primary_evidence_type.in_(list(effective_rubric)))
        .where(
            ~exists()
            .where(effective.c.evidence_scope_id == context.scope_id)
            .where(effective.c.project_id == project_id)
            .where(
                effective.c.project_source_snapshot_id
                == source_classification_result.c.project_source_snapshot_id
            )
            .where(effective.c.status == "relevant")
        )
        .where(
            ~exists().where(
                (source_appraisal_result.c.evidence_scope_id == context.scope_id)
                & (source_appraisal_result.c.project_id == project_id)
                & (source_appraisal_result.c.project_source_snapshot_id
                   == source_classification_result.c.project_source_snapshot_id)
            )
        )
    ).scalar_one()

    by_score: dict[int, int] = {}
    appraisal_rows: list[dict[str, Any]] = []

    for pss_id, snap_id, evidence_type in appraisable_rows:
        result = AppraiseResult(
            quality_score=effective_rubric[evidence_type],
            rubric_version=rubric_version,
        )

        appraisal_rows.append(
            {
                "source_appraisal_result_id": uuid.uuid4(),
                "evidence_scope_id": context.scope_id,
                "project_source_snapshot_id": pss_id,
                "project_id": project_id,
                "appraised_by_run_id": run_id,
                "quality_score": result.quality_score,
                "rubric_version": result.rubric_version,
                "appraised_at": datetime.now(UTC),
            }
        )

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="source.appraised",
            payload={
                "source_snapshot_id": str(snap_id),
                "project_source_snapshot_id": str(pss_id),
                "evidence_scope_id": str(context.scope_id),
                "quality_score": result.quality_score,
                "rubric_version": result.rubric_version,
            },
        )

        by_score[result.quality_score] = by_score.get(result.quality_score, 0) + 1

    # One bulk INSERT for all appraisal rows (deterministic rubric lookup, no
    # per-row DB round trip needed); event-log appends stay per-row above for
    # sequence-uniqueness. Guarded: an empty executemany raises where the loop
    # legitimately no-op'd (no appraisable rows this run).
    if appraisal_rows:
        conn.execute(source_appraisal_result.insert(), appraisal_rows)

    return {
        "appraised": len(appraisable_rows),
        "by_score": by_score,
        "skipped_non_evidence": skip_counts.get(_NON_EVIDENCE_TYPE, 0),
        "skipped_unknown": skip_counts.get(_UNKNOWN_TYPE, 0),
        "skipped_demoted": skipped_demoted,
        "already_appraised": already_appraised,
        "unclassified": unclassified,
    }
