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
    source_appraisal_result,
    source_classification_result,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.classify import SKIP_TSS_KEY, parse_skip_ids
from policy_atlas.evidence_search.assess.screen import effective_screen_rows

# v1 -> v2 (task 056, D7): the two unscored types now get an Unrated row instead of
# no row. The scores themselves did not change; the bump records that the rubric's
# reach did, so an inherited v1 appraisal is re-appraised (labels.py rubric rule).
DEFAULT_RUBRIC_VERSION = "v2-hierarchy-v2"

# The v3.0 default rubric: primary_evidence_type → quality_score (5 = strongest),
# v2's expert-calibrated five-point evidence-hierarchy rating carried forward.
# Types absent from it (Other/Non-evidence, Unknown) are never scored: since task
# 056 (D7) they are appraised as Unrated — a row with no score and
# ``unrated = true`` — so they are citable and shown as "Unrated". Keys come from
# EVIDENCE_TYPES (schema.py); a test enforces the domain is exactly EVIDENCE_TYPES
# minus the two Unrated types.
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

# The reader-facing label of an Unrated appraisal (task 056, D7). Kept apart from
# SCORE_LABELS because an Unrated row has no score, and a dict keyed by score cannot
# hold a "no score" key (wording deviation from the contract, owner 2026-11-01).
UNRATED_LABEL = "Unrated"

_NON_EVIDENCE_TYPE = "Other (Non-evidence documents)"
_UNKNOWN_TYPE = "Unknown / Insufficient information"

#: The types appraised as Unrated (no score) unless a rubric override scores them.
UNRATED_TYPES: frozenset[str] = frozenset({_NON_EVIDENCE_TYPE, _UNKNOWN_TYPE})


def appraisal_label(quality_score: int | None, *, unrated: bool = False) -> str | None:
    """Return the reader-facing strength label for one appraisal.

    The single place that turns a stored appraisal into words, so every
    surface says "Unrated" the same way.

    Args:
        quality_score: The stored score (1 to 5), or ``None``.
        unrated: The row's ``unrated`` flag.

    Returns:
        ``UNRATED_LABEL`` for an Unrated row, the ``SCORE_LABELS`` word for a
        scored row, or ``None`` when there is no appraisal at all.
    """
    if unrated:
        return UNRATED_LABEL
    return SCORE_LABELS.get(quality_score) if quality_score is not None else None


def appraisal_tier(quality_score: int | None, *, unrated: bool = False) -> str | None:
    """Return the short tier string the writer and the chat context carry.

    The tier is the score as text (``"4"``) for a scored row and
    ``UNRATED_LABEL`` for an Unrated row; ``None`` means "not appraised", which
    is what keeps a document uncitable.

    Args:
        quality_score: The stored score (1 to 5), or ``None``.
        unrated: The row's ``unrated`` flag.

    Returns:
        The tier string, or ``None`` when there is no appraisal.
    """
    if unrated:
        return UNRATED_LABEL
    return str(quality_score) if quality_score is not None else None


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
    - ``skip_task_source_snapshot_ids`` (task 045), when present, must be a
      list of id strings; it is validated here and read by
      :func:`_parse_appraisal_skip`. It never changes the rubric.

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
    unknown = set(raw) - {"rubric", SKIP_TSS_KEY}
    if unknown:
        raise AppraiseDirectiveError("appraisal directive contains unknown keys")
    if SKIP_TSS_KEY in raw:
        parse_skip_ids(raw[SKIP_TSS_KEY], AppraiseDirectiveError)
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


def _parse_appraisal_skip(raw: Any) -> frozenset[uuid.UUID]:
    """Return the documents the appraisal directive says to leave alone (task 045).

    Called after :func:`_parse_appraisal_directive` has validated ``raw``.

    Args:
        raw: The ``context["appraisal"]`` object, or ``None``.

    Returns:
        The ``skip_task_source_snapshot_ids`` as ids; empty when absent.
    """
    if not isinstance(raw, dict) or SKIP_TSS_KEY not in raw:
        return frozenset()
    return parse_skip_ids(raw[SKIP_TSS_KEY], AppraiseDirectiveError)


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
        quality_score: 1..5, 5 = strongest (v2 evidence-hierarchy rating);
            ``None`` for an Unrated document.
        rubric_version: Rubric that produced the score; ``DEFAULT_RUBRIC_VERSION``
            unless a scope-context ``appraisal.rubric`` override is in effect (D1),
            in which case it is the derived ``f"{base}+{hash8}"`` version.
        unrated: ``True`` for a document typed Unknown or Other (Non-evidence):
            it has no score and reads as "Unrated" (task 056, D7).
    """

    quality_score: int | None
    rubric_version: str
    unrated: bool = False


def appraise_sources(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    run_id: uuid.UUID,
    context: AppraiseContext,
) -> dict[str, Any]:
    """Appraise all classified evidence sources for a screening scope.

    Reads source_classification_result rows for the scope; for each whose
    primary_evidence_type is in the effective rubric's domain, inserts one
    source_appraisal_result row and emits a source.appraised event. The two
    Unrated types (``UNRATED_TYPES``) that the effective rubric does not score
    get a row too, with no score and ``unrated = true`` (task 056, D7), so
    they are citable and read as "Unrated". Already-appraised rows are
    skipped (idempotent).

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
        task_id: Owning task.
        run_id: The run recorded as appraised_by_run_id.
        context: Scope-level input naming the classified set and optionally
            carrying the appraisal directive.

    Raises:
        AppraiseDirectiveError: If ``context.context["appraisal"]`` is malformed.

    Returns:
        Counts: ``appraised`` (scored rows inserted this call), ``by_score``
        (sparse, int-keyed), ``appraised_unrated`` (Unrated rows inserted this
        call), ``skipped_non_evidence`` / ``skipped_unknown`` /
        ``unclassified`` (recomputed from current state every call),
        ``skipped_demoted`` (scored- or Unrated-domain classifications whose
        doc is no longer effective-relevant, e.g. stage-2 demoted — never
        appraised), and ``already_appraised`` (pre-existing appraisal rows for
        the scope). Since task 056 the two skipped counts read 0 under the
        default rubric, because those types are appraised as Unrated; the keys
        are kept so the summary keeps its shape and a type outside both
        domains would still be counted, never lost.
        Invariant: appraised + appraised_unrated + already_appraised +
        skipped_non_evidence + skipped_unknown + skipped_demoted =
        classification rows for the scope (+ ``resolved_elsewhere``, present
        only under a task 045 skip directive: documents whose tier a linked
        task already answers).
    """
    rubric_override = _parse_appraisal_directive(context.context.get("appraisal"))
    skip = _parse_appraisal_skip(context.context.get("appraisal"))
    effective_rubric: dict[str, int] = {**DEFAULT_RUBRIC, **rubric_override}
    rubric_version = _derive_rubric_version(rubric_override)
    # An override that scores an Unrated type wins: that type is scored this run.
    unrated_types = UNRATED_TYPES - set(effective_rubric)
    # Every type that gets a row this run, scored or Unrated.
    appraisable_types = [*effective_rubric, *sorted(unrated_types)]

    scoped_classifications = (
        (source_classification_result.c.evidence_scope_id == context.scope_id)
        & (source_classification_result.c.task_id == task_id)
    )

    # Pre-insert count: appraisal rows already present for the scope (idempotency skips).
    already_appraised = conn.execute(
        select(func.count())
        .select_from(source_appraisal_result)
        .where(source_appraisal_result.c.evidence_scope_id == context.scope_id)
        .where(source_appraisal_result.c.task_id == task_id)
    ).scalar_one()

    # Skip counts are recomputed from the full classification set on every call
    # (not the not-yet-appraised remainder), so reruns report the same numbers.
    skip_counts: dict[str, int] = {
        evidence_type: count
        for evidence_type, count in conn.execute(
            select(source_classification_result.c.primary_evidence_type, func.count())
            .where(scoped_classifications)
            .where(source_classification_result.c.primary_evidence_type.not_in(
                appraisable_types
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
        .where(effective.c.task_id == task_id)
        .where(effective.c.status == "relevant")
        .where(
            ~exists().where(
                (source_classification_result.c.evidence_scope_id == context.scope_id)
                & (source_classification_result.c.task_id == task_id)
                & (source_classification_result.c.task_source_snapshot_id
                   == effective.c.task_source_snapshot_id)
            )
        )
    ).scalar_one()

    # The write path is effective-grained too: a doc classified before a
    # stage-2 demotion must not gain an appraisal on a rerun (014 review
    # finding). The exclusion is counted below (skipped_demoted), never silent.
    appraisable_rows = conn.execute(
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            task_source_snapshot.c.source_snapshot_id,
            source_classification_result.c.primary_evidence_type,
        )
        .join_from(
            source_classification_result,
            task_source_snapshot,
            (source_classification_result.c.task_source_snapshot_id
             == task_source_snapshot.c.task_source_snapshot_id)
            & (source_classification_result.c.task_id
               == task_source_snapshot.c.task_id),
        )
        .join(
            effective,
            (effective.c.task_source_snapshot_id
             == task_source_snapshot.c.task_source_snapshot_id)
            & (effective.c.task_id == task_source_snapshot.c.task_id),
        )
        .where(effective.c.evidence_scope_id == context.scope_id)
        .where(effective.c.status == "relevant")
        .where(scoped_classifications)
        .where(source_classification_result.c.primary_evidence_type.in_(appraisable_types))
        .where(
            ~exists().where(
                (source_appraisal_result.c.evidence_scope_id == context.scope_id)
                & (source_appraisal_result.c.task_id == task_id)
                & (source_appraisal_result.c.task_source_snapshot_id
                   == task_source_snapshot.c.task_source_snapshot_id)
            )
        )
    ).fetchall()
    # Task 045: documents whose tier the label resolver already answers from a
    # linked task are left alone and counted (``resolved_elsewhere``).
    resolved_elsewhere = sum(1 for row in appraisable_rows if row[0] in skip)
    if skip:
        appraisable_rows = [row for row in appraisable_rows if row[0] not in skip]

    # Rubric-domain classifications whose doc is no longer effective-relevant
    # (stage-2 demoted): excluded from the write path above, reported here.
    # Already-appraised docs are excluded so the returned counts stay an exact
    # partition of the scope's classification rows (see Returns invariant).
    skipped_demoted = conn.execute(
        select(func.count())
        .select_from(source_classification_result)
        .where(scoped_classifications)
        .where(source_classification_result.c.primary_evidence_type.in_(appraisable_types))
        .where(
            ~exists()
            .where(effective.c.evidence_scope_id == context.scope_id)
            .where(effective.c.task_id == task_id)
            .where(
                effective.c.task_source_snapshot_id
                == source_classification_result.c.task_source_snapshot_id
            )
            .where(effective.c.status == "relevant")
        )
        .where(
            ~exists().where(
                (source_appraisal_result.c.evidence_scope_id == context.scope_id)
                & (source_appraisal_result.c.task_id == task_id)
                & (source_appraisal_result.c.task_source_snapshot_id
                   == source_classification_result.c.task_source_snapshot_id)
            )
        )
    ).scalar_one()

    by_score: dict[int, int] = {}
    appraised_unrated = 0
    appraisal_rows: list[dict[str, Any]] = []

    for tss_id, snap_id, evidence_type in appraisable_rows:
        unrated = evidence_type in unrated_types
        result = AppraiseResult(
            quality_score=None if unrated else effective_rubric[evidence_type],
            rubric_version=rubric_version,
            unrated=unrated,
        )

        appraisal_rows.append(
            {
                "source_appraisal_result_id": uuid.uuid4(),
                "evidence_scope_id": context.scope_id,
                "task_source_snapshot_id": tss_id,
                "task_id": task_id,
                "appraised_by_run_id": run_id,
                "quality_score": result.quality_score,
                "unrated": result.unrated,
                "rubric_version": result.rubric_version,
                "appraised_at": datetime.now(UTC),
            }
        )

        payload: dict[str, Any] = {
            "source_snapshot_id": str(snap_id),
            "task_source_snapshot_id": str(tss_id),
            "evidence_scope_id": str(context.scope_id),
            "quality_score": result.quality_score,
            "rubric_version": result.rubric_version,
        }
        if result.unrated:
            # Only on Unrated rows, so a scored row's event is unchanged.
            payload["unrated"] = True
        events.append(
            conn,
            task_id=task_id,
            run_id=run_id,
            event_type="source.appraised",
            payload=payload,
        )

        if result.quality_score is None:
            appraised_unrated += 1
        else:
            by_score[result.quality_score] = by_score.get(result.quality_score, 0) + 1

    # One bulk INSERT for all appraisal rows (deterministic rubric lookup, no
    # per-row DB round trip needed); event-log appends stay per-row above for
    # sequence-uniqueness. Guarded: an empty executemany raises where the loop
    # legitimately no-op'd (no appraisable rows this run).
    if appraisal_rows:
        conn.execute(source_appraisal_result.insert(), appraisal_rows)

    summary: dict[str, Any] = {
        "appraised": len(appraisable_rows) - appraised_unrated,
        "by_score": by_score,
        "appraised_unrated": appraised_unrated,
        "skipped_non_evidence": skip_counts.get(_NON_EVIDENCE_TYPE, 0),
        "skipped_unknown": skip_counts.get(_UNKNOWN_TYPE, 0),
        "skipped_demoted": skipped_demoted,
        "already_appraised": already_appraised,
        "unclassified": unclassified,
    }
    if SKIP_TSS_KEY in (context.context.get("appraisal") or {}):
        # Present only under the directive, so every other summary is unchanged;
        # it joins the partition in the Returns invariant.
        summary["resolved_elsewhere"] = resolved_elsewhere
    return summary
