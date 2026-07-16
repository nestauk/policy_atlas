"""The trigger floor (task 024, contract decision 8).

Pure read functions over persisted state only — SELECTs on result tables and
``event_log`` payloads. No LLM, no recomputation of anything a component
already computed: every number here was written by the component's own run,
read back verbatim or aggregated by a plain ``COUNT``/``GROUP BY``. This is
the floor the orchestrator watch can never suppress (steerability-refinement
§ "The orchestrator watch", discipline 1): the watch may add escalations, it
may never remove one of these.

Each public trigger function returns the ``steer_point_triggers`` shape —
``list[dict]`` of ``{"trigger": str, "detail": <persisted evidence>}`` — so a
caller can concatenate outputs from several functions without re-shaping.
``floor_triggers`` is the per-boundary aggregator: it maps a component
boundary to the trigger classes decision 8 declares applicable there, and
always adds the universal downstream-capability-reduced check.

Thresholds below are module-level internal constants — dev-side telemetry
never plan content (017 standing owner rule, reaffirmed by the cost
adjudication folded into decision 3).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from typing import Any, Literal

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    event_log,
    extraction_result,
    grouping_result,
    search_coverage_record,
    source_appraisal_result,
    source_classification_result,
)
from policy_atlas.evidence_base.assess.screen import effective_screen_rows
from policy_atlas.runtime.steering import steer_point_triggers

__all__ = [
    "EXTRACT_FAILED_SHARE",
    "EXTRACT_VETTING_FAILED_SHARE",
    "P1_STOP_CONDITIONS",
    "P2_MIN_RELEVANT",
    "QUALITY_COLLAPSE_SCORE_MAX",
    "QUALITY_COLLAPSE_SHARE",
    "SCREEN_DEMOTE_SHARE",
    "SCREEN_FAILED_SHARE",
    "TYPE_MIX_DOMINANT_SHARE",
    "UNKNOWN_SHARE_FLOOR",
    "FloorBoundary",
    "appraisal_collapse_trigger",
    "classification_collapse_trigger",
    "downstream_capability_reduced_triggers",
    "extraction_spike_triggers",
    "floor_triggers",
    "grouping_flag_triggers",
    "p1_coverage_triggers",
    "s0_select_triggers",
    "screen_quality_collapse_trigger",
    "screened_relevant_floor_trigger",
]

# --- Class 1: S0 select signals -------------------------------------------
#
# Already built (task 017/study S0): `steering.steer_point_triggers` reads
# `selection_result.flags` and maps them to the deepening-selection triggers.
# Re-exported here, never duplicated — the deepening-selection pause keeps
# its own existing call site; this alias is for callers that want the whole
# trigger floor under one module.
s0_select_triggers = steer_point_triggers

# --- Module constants (thresholds; never plan content) --------------------

#: Class 2 (P1 coverage, after acquire): the two `search_coverage_record`
#: stop conditions that fire the floor unconditionally (contract decision 8).
P1_STOP_CONDITIONS: tuple[str, ...] = ("re_searched_still_thin", "error")

#: Class 3 (P2 pre-select): screened-relevant count floor.
P2_MIN_RELEVANT = 5

#: Classes 3/6 (classification collapse): a single primary_evidence_type
#: dominating the classified set.
TYPE_MIX_DOMINANT_SHARE = 0.8

#: Classes 3/6 (classification collapse): 'Unknown / Insufficient information'
#: share of the classified set.
UNKNOWN_SHARE_FLOOR = 0.3

# Mirrors schema.py's EVIDENCE_TYPES[-1] literal (classify.py/appraise.py/
# characterise.py precedent: each module duplicates this literal locally
# rather than importing a name schema.py doesn't export for it).
_UNKNOWN_EVIDENCE_TYPE = "Unknown / Insufficient information"

#: Classes 3/7 (appraisal collapse): quality_score at or below this is "weak".
QUALITY_COLLAPSE_SCORE_MAX = 2

#: Classes 3/7 (appraisal collapse): share of appraised docs at/below the
#: weak-score ceiling that fires the collapse.
QUALITY_COLLAPSE_SHARE = 0.7

#: Class 5 (screen quality-collapse): quorum-failure ('failed' status) share.
SCREEN_FAILED_SHARE = 0.2

#: Class 5 (screen quality-collapse): stage-2 demote share.
SCREEN_DEMOTE_SHARE = 0.5

#: Class 8 (extraction spikes): extraction-failure share of the selected set.
EXTRACT_FAILED_SHARE = 0.2

#: Class 8 (extraction spikes): vetting-failed share of the selected set.
EXTRACT_VETTING_FAILED_SHARE = 0.2

_DOWNSTREAM_EVENT_TYPES = ("component.skipped", "component.failed")


# --- Class 2: P1 coverage triggers (after acquire) -------------------------


def p1_coverage_triggers(
    conn: Connection, *, project_id: uuid.UUID, acquire_run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fired coverage triggers from the acquire run's `search_coverage_record`.

    Reads the persisted `adequacy_verdict` and `stop_condition` columns —
    never recomputed. Fires on `adequacy_verdict == 'inadequate'` and/or
    `stop_condition` in `P1_STOP_CONDITIONS` (contract decision 8); both can
    fire together off the same row.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        acquire_run_id: The acquire run whose coverage record to read.

    Returns:
        Fired trigger dicts. Empty when no coverage record exists for the run.
    """
    row = conn.execute(
        sa_select(
            search_coverage_record.c.adequacy_verdict,
            search_coverage_record.c.stop_condition,
        )
        .where(search_coverage_record.c.project_id == project_id)
        .where(search_coverage_record.c.acquired_by_run_id == acquire_run_id)
    ).first()
    if row is None:
        return []
    triggers: list[dict[str, Any]] = []
    if row.adequacy_verdict == "inadequate":
        triggers.append(
            {
                "trigger": "coverage_inadequate",
                "detail": {"adequacy_verdict": row.adequacy_verdict},
            }
        )
    if row.stop_condition in P1_STOP_CONDITIONS:
        triggers.append(
            {
                "trigger": "coverage_stop_condition",
                "detail": {"stop_condition": row.stop_condition},
            }
        )
    return triggers


# --- Class 3 (own reader): screened-relevant count floor (pre-select) ------


def screened_relevant_floor_trigger(
    conn: Connection, *, project_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fire when the scope's effective screened-relevant count is below the floor.

    Reads `screen.effective_screen_rows()` (the generation/stage read rule,
    task 024 decision 7b) and counts `status == 'relevant'` rows for the
    scope — the scope-wide effective count, never a single run's slice.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        evidence_scope_id: The scope to count relevant rows for.

    Returns:
        A single-item list when `relevant_count < P2_MIN_RELEVANT`, else empty.
    """
    effective = effective_screen_rows()
    count = conn.execute(
        sa_select(func.count())
        .select_from(effective)
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == evidence_scope_id)
        .where(effective.c.status == "relevant")
    ).scalar_one()
    if count < P2_MIN_RELEVANT:
        return [
            {
                "trigger": "screened_relevant_below_floor",
                "detail": {"relevant_count": count, "floor": P2_MIN_RELEVANT},
            }
        ]
    return []


# --- Classes 3/6: classification collapse (pre-select + after-classify) ---


def classification_collapse_trigger(
    conn: Connection, *, project_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fire on document-type-mix collapse or an Unknown-share breach.

    One reader, two call sites (contract decision 8 / steerability-refinement
    "New floor triggers"): the pre-select boundary (P2, class 3's type/quality
    picture) and the after-classify boundary (class 6) share this exact
    query and these exact constants. Reads `source_classification_result`
    grouped by `primary_evidence_type` for the scope — never recomputed.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        evidence_scope_id: The scope to aggregate classified rows for.

    Returns:
        Up to two trigger dicts: `classification_type_mix_collapse` when one
        type exceeds `TYPE_MIX_DOMINANT_SHARE`, `classification_unknown_share`
        when the Unknown share exceeds `UNKNOWN_SHARE_FLOOR`. Empty when no
        classified rows exist for the scope.
    """
    rows = conn.execute(
        sa_select(
            source_classification_result.c.primary_evidence_type,
            func.count().label("n"),
        )
        .where(source_classification_result.c.project_id == project_id)
        .where(source_classification_result.c.evidence_scope_id == evidence_scope_id)
        .group_by(source_classification_result.c.primary_evidence_type)
    ).all()
    total = sum(row.n for row in rows)
    if total == 0:
        return []
    by_type = {row.primary_evidence_type: row.n for row in rows}
    triggers: list[dict[str, Any]] = []
    dominant_type, dominant_count = max(by_type.items(), key=lambda item: item[1])
    if (dominant_count / total) > TYPE_MIX_DOMINANT_SHARE:
        triggers.append(
            {
                "trigger": "classification_type_mix_collapse",
                "detail": {
                    "primary_evidence_type": dominant_type,
                    "count": dominant_count,
                    "total": total,
                    "share": dominant_count / total,
                },
            }
        )
    unknown_count = by_type.get(_UNKNOWN_EVIDENCE_TYPE, 0)
    if (unknown_count / total) > UNKNOWN_SHARE_FLOOR:
        triggers.append(
            {
                "trigger": "classification_unknown_share",
                "detail": {
                    "unknown_count": unknown_count,
                    "total": total,
                    "share": unknown_count / total,
                },
            }
        )
    return triggers


# --- Classes 3/7: appraisal collapse (pre-select + after-appraise) --------


def appraisal_collapse_trigger(
    conn: Connection, *, project_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fire when weak scores (<= QUALITY_COLLAPSE_SCORE_MAX) dominate appraisal.

    One reader, two call sites, shared with the pre-select picture (class 3)
    and the after-appraise boundary (class 7). Reads `source_appraisal_result`
    grouped by `quality_score` for the scope — never recomputed.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        evidence_scope_id: The scope to aggregate appraised rows for.

    Returns:
        A single-item list when the weak-score share exceeds
        `QUALITY_COLLAPSE_SHARE`, else empty (incl. no appraised rows).
    """
    rows = conn.execute(
        sa_select(source_appraisal_result.c.quality_score, func.count().label("n"))
        .where(source_appraisal_result.c.project_id == project_id)
        .where(source_appraisal_result.c.evidence_scope_id == evidence_scope_id)
        .group_by(source_appraisal_result.c.quality_score)
    ).all()
    total = sum(row.n for row in rows)
    if total == 0:
        return []
    weak = sum(row.n for row in rows if row.quality_score <= QUALITY_COLLAPSE_SCORE_MAX)
    if (weak / total) > QUALITY_COLLAPSE_SHARE:
        return [
            {
                "trigger": "appraisal_quality_collapse",
                "detail": {
                    "weak_count": weak,
                    "total": total,
                    "share": weak / total,
                    "score_max": QUALITY_COLLAPSE_SCORE_MAX,
                },
            }
        ]
    return []


# --- Class 4: P4 grouping flags (after group) ------------------------------


def grouping_flag_triggers(
    conn: Connection, *, project_id: uuid.UUID, group_run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fire on any per-facet flag `grouping_result.flags` already persists.

    Reads the group run's `flags` JSONB — `{facet: {"status", "failure_class",
    "groups_rejected", "value_cap_exceeded"}}` (`group.py::_facet_flag`) —
    and surfaces every facet where `status == 'failed'`, `groups_rejected`,
    or `value_cap_exceeded` is true. Never recomputed.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        group_run_id: The group run whose `grouping_result` row to read.

    Returns:
        One trigger dict per flagged facet, each carrying the facet's
        persisted flag object verbatim. Empty when no row exists or no facet
        is flagged.
    """
    row = conn.execute(
        sa_select(grouping_result.c.flags)
        .where(grouping_result.c.project_id == project_id)
        .where(grouping_result.c.run_id == group_run_id)
    ).first()
    if row is None:
        return []
    flags = row.flags if isinstance(row.flags, dict) else {}
    triggers: list[dict[str, Any]] = []
    for facet, flag in flags.items():
        if not isinstance(flag, dict):
            continue
        if (
            flag.get("status") == "failed"
            or flag.get("groups_rejected")
            or flag.get("value_cap_exceeded")
        ):
            triggers.append(
                {"trigger": "grouping_facet_flagged", "detail": {"facet": facet, **flag}}
            )
    return triggers


# --- Class 5: screen quality-collapse --------------------------------------


def screen_quality_collapse_trigger(
    conn: Connection, *, project_id: uuid.UUID, run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fire on quorum-failure spikes or a stage-2 demote spike.

    Screen has no dedicated summary result row; its run-level counts live
    only in the `component.completed` event payload
    (`harness.py::_run_scope_component`: `{"component": "screen", **counts}`
    where `counts` is `screen.screen_sources`'s stage-specific return). Reads
    that payload for the given run — never recomputed. A stage-1 run's
    payload carries `screened`/`failed`; a stage-2 run's carries
    `stage2_screened`/`failed`/`demoted`. Both shapes are checked; whichever
    key is absent is simply not evaluated.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        run_id: The screen run whose `component.completed` payload to read.

    Returns:
        Fired trigger dicts. Empty when no `component.completed` event exists
        for the run.
    """
    row = conn.execute(
        sa_select(event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.run_id == run_id)
        .where(event_log.c.event_type == "component.completed")
        .order_by(event_log.c.sequence.desc())
        .limit(1)
    ).first()
    if row is None:
        return []
    payload = row.payload if isinstance(row.payload, dict) else {}
    triggers: list[dict[str, Any]] = []
    if "screened" in payload:
        screened = payload.get("screened") or 0
        failed = payload.get("failed") or 0
        if screened and (failed / screened) > SCREEN_FAILED_SHARE:
            triggers.append(
                {
                    "trigger": "screen_quorum_failure_spike",
                    "detail": {
                        "failed": failed,
                        "screened": screened,
                        "share": failed / screened,
                    },
                }
            )
    if "stage2_screened" in payload:
        stage2_screened = payload.get("stage2_screened") or 0
        failed2 = payload.get("failed") or 0
        demoted = payload.get("demoted") or 0
        if stage2_screened and (failed2 / stage2_screened) > SCREEN_FAILED_SHARE:
            triggers.append(
                {
                    "trigger": "screen_quorum_failure_spike",
                    "detail": {
                        "failed": failed2,
                        "stage2_screened": stage2_screened,
                        "share": failed2 / stage2_screened,
                    },
                }
            )
        if stage2_screened and (demoted / stage2_screened) > SCREEN_DEMOTE_SHARE:
            triggers.append(
                {
                    "trigger": "screen_stage2_demote_spike",
                    "detail": {
                        "demoted": demoted,
                        "stage2_screened": stage2_screened,
                        "share": demoted / stage2_screened,
                    },
                }
            )
    return triggers


# --- Class 8: extraction failure / vetting_failed spikes -------------------


def extraction_spike_triggers(
    conn: Connection, *, project_id: uuid.UUID, extract_run_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Fire on a per-profile extraction-failure or vetting-failed spike.

    Reads `extraction_result.counts` (`extract.py::_build_summary`:
    `{"selected": N, "basis": {...}, "profiles": {profile_id: {"extracted",
    "no_findings", "failed", "fresh", "reused", "vetting_failed"?, ...}}}`)
    for the run — never recomputed.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        extract_run_id: The extract run whose `extraction_result` row to read.

    Returns:
        Fired trigger dicts, one per profile per breached threshold. Empty
        when no row exists, `selected == 0`, or no profile breaches.
    """
    row = conn.execute(
        sa_select(extraction_result.c.counts)
        .where(extraction_result.c.project_id == project_id)
        .where(extraction_result.c.run_id == extract_run_id)
    ).first()
    if row is None:
        return []
    counts = row.counts if isinstance(row.counts, dict) else {}
    selected = counts.get("selected") or 0
    profiles = counts.get("profiles")
    triggers: list[dict[str, Any]] = []
    if not selected or not isinstance(profiles, dict):
        return triggers
    for profile_id, profile_counts in profiles.items():
        if not isinstance(profile_counts, dict):
            continue
        failed = profile_counts.get("failed") or 0
        if (failed / selected) > EXTRACT_FAILED_SHARE:
            triggers.append(
                {
                    "trigger": "extraction_failure_spike",
                    "detail": {
                        "profile": profile_id,
                        "failed": failed,
                        "selected": selected,
                        "share": failed / selected,
                    },
                }
            )
        vetting_failed = profile_counts.get("vetting_failed")
        if isinstance(vetting_failed, int) and (vetting_failed / selected) > (
            EXTRACT_VETTING_FAILED_SHARE
        ):
            triggers.append(
                {
                    "trigger": "extraction_vetting_failed_spike",
                    "detail": {
                        "profile": profile_id,
                        "vetting_failed": vetting_failed,
                        "selected": selected,
                        "share": vetting_failed / selected,
                    },
                }
            )
    return triggers


# --- Class 9: downstream-capability-reduced (every boundary) --------------


def downstream_capability_reduced_triggers(
    conn: Connection, *, project_id: uuid.UUID, run_ids: Iterable[uuid.UUID]
) -> list[dict[str, Any]]:
    """Fire once per `component.skipped`/`component.failed` event in the walk.

    A discretionary component that failed or was skipped leaves the rest of
    the run structurally poorer (e.g. group failed -> ungrouped synthesis).
    Reads `event_log` for the given run ids — never recomputed; the caller
    supplies the walk's attempted run ids (steering event-log attachment
    convention, contract decision 1: skip/failure events attach to the
    most-recent attempted run).

    Args:
        conn: Open read connection.
        project_id: Owning project.
        run_ids: The walk's attempted run ids to scan.

    Returns:
        One trigger dict per matching event, each detail carrying the
        persisted payload verbatim plus its `event_type`. Empty when
        `run_ids` is empty or no matching event exists.
    """
    ids = list(run_ids)
    if not ids:
        return []
    rows = conn.execute(
        sa_select(event_log.c.event_type, event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.run_id.in_(ids))
        .where(event_log.c.event_type.in_(_DOWNSTREAM_EVENT_TYPES))
        .order_by(event_log.c.sequence)
    ).all()
    triggers: list[dict[str, Any]] = []
    for event_type, payload in rows:
        detail = dict(payload) if isinstance(payload, dict) else {}
        detail["event_type"] = event_type
        triggers.append({"trigger": "downstream_capability_reduced", "detail": detail})
    return triggers


# --- The per-boundary aggregator -------------------------------------------

FloorBoundary = Literal[
    "after_acquire",
    "pre_select",
    "after_screen",
    "after_classify",
    "after_appraise",
    "after_group",
    "after_extract",
]


def floor_triggers(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    boundary_component: FloorBoundary,
    evidence_scope_id: uuid.UUID,
    run_ids: dict[str, uuid.UUID],
) -> list[dict[str, Any]]:
    """Compute every fired floor trigger applicable at one component boundary.

    Maps `boundary_component` to the decision-8 trigger classes that fire
    there (steerability-refinement "New floor triggers" + the study's
    per-component inventory), then always appends the universal
    downstream-capability-reduced check (class 9) over every run id supplied.

    S0 (class 1) is deliberately not a `boundary_component` option here — the
    deepening-selection pause keeps its own existing call site
    (`steering.steer_point_triggers`, re-exported as `s0_select_triggers`);
    this aggregator covers the new floor triggers this task adds.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        boundary_component: Which boundary the caller is at.
        evidence_scope_id: The scope (for the scope-wide readers: pre-select,
            after-classify, after-appraise).
        run_ids: Component name -> run id for every run relevant to this
            boundary. `floor_triggers` reads only the keys the boundary
            needs (e.g. `"acquire"` at `after_acquire`) plus scans every
            value for class 9.

    Returns:
        The concatenated fired-trigger list, in class-then-facet order.

    Raises:
        KeyError: `run_ids` is missing a key the boundary requires.
        ValueError: `boundary_component` is not a recognised boundary.
    """
    triggers: list[dict[str, Any]] = []
    if boundary_component == "after_acquire":
        triggers += p1_coverage_triggers(
            conn, project_id=project_id, acquire_run_id=run_ids["acquire"]
        )
    elif boundary_component == "pre_select":
        triggers += screened_relevant_floor_trigger(
            conn, project_id=project_id, evidence_scope_id=evidence_scope_id
        )
        triggers += classification_collapse_trigger(
            conn, project_id=project_id, evidence_scope_id=evidence_scope_id
        )
        triggers += appraisal_collapse_trigger(
            conn, project_id=project_id, evidence_scope_id=evidence_scope_id
        )
    elif boundary_component == "after_screen":
        triggers += screen_quality_collapse_trigger(
            conn, project_id=project_id, run_id=run_ids["screen"]
        )
    elif boundary_component == "after_classify":
        triggers += classification_collapse_trigger(
            conn, project_id=project_id, evidence_scope_id=evidence_scope_id
        )
    elif boundary_component == "after_appraise":
        triggers += appraisal_collapse_trigger(
            conn, project_id=project_id, evidence_scope_id=evidence_scope_id
        )
    elif boundary_component == "after_group":
        triggers += grouping_flag_triggers(
            conn, project_id=project_id, group_run_id=run_ids["group"]
        )
    elif boundary_component == "after_extract":
        triggers += extraction_spike_triggers(
            conn, project_id=project_id, extract_run_id=run_ids["extract"]
        )
    else:
        raise ValueError(f"unknown floor boundary_component: {boundary_component!r}")

    triggers += downstream_capability_reduced_triggers(
        conn, project_id=project_id, run_ids=run_ids.values()
    )
    return triggers
