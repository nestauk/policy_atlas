"""Deterministic decision-point bundles (task 024, decision 3).

A bundle is the pre-fetched, versioned information picture attached to a lattice
pause's ``steering.pause`` event — the durable record of what the user (and, in
Phase 5, the watch) saw when deciding. Every builder here is a pure read over
persisted state: SELECTs on result tables and ``event_log`` payload JSONB, no
LLM, no recomputation of anything a component already computed. Renders are
deterministic (stable sort orders) so two calls over the same rows are identical
— the option-completeness rule's substrate (contract decision 3).

``bundle_version`` is stamped ``"v1"`` on every bundle so the eval slice and the
history projection can condition on the render shape.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    characterisation_result,
    event_log,
    grouping_result,
    project_source_snapshot,
    search_coverage_record,
    selection_result,
    source_appraisal_result,
    source_classification_result,
    source_snapshot,
)
from policy_atlas.evidence_base.assess.screen import effective_screen_rows
from policy_atlas.evidence_base.synthesis.synthesis_backend import SynthesisBackend
from policy_atlas.evidence_base.synthesis.synthesise import (
    SynthesiseContext,
    propose_synthesis_plan,
)

BUNDLE_VERSION = "v1"

#: Selection-preview cap and dropped-stratum digest cap (dev-side constants,
#: never plan content). The preview is a representative top slice, never the full
#: selected set; dropped-stratum digests are capped, never full lists.
SELECTION_PREVIEW_N = 10
DROPPED_DIGEST_CAP = 5


# --- P2: evidence-base coverage --------------------------------------------


def p2_bundle(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    characterisation_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Build the P2 coverage bundle (before select).

    Composes the characterise coverage object + a reduced themes summary (when a
    characterisation run is present), the scope's ``search_coverage_record`` rows,
    the effective screen counts by status/stage/generation, and the executed /
    zero-result queries parsed from ``search.executed`` event payloads.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        evidence_scope_id: Scope the coverage picture is over.
        characterisation_run_id: The characterisation run whose coverage/themes to
            read, or ``None`` when characterise did not run (coverage/themes are
            then ``None``).

    Returns:
        The versioned P2 bundle dict.
    """
    coverage: Any = None
    themes: list[dict[str, Any]] | None = None
    unclustered_count: int | None = None
    if characterisation_run_id is not None:
        row = conn.execute(
            sa_select(characterisation_result.c.coverage, characterisation_result.c.themes)
            .where(characterisation_result.c.project_id == project_id)
            .where(characterisation_result.c.run_id == characterisation_run_id)
        ).first()
        if row is not None:
            coverage = row.coverage
            themes_payload = row.themes if isinstance(row.themes, dict) else {}
            raw_themes = themes_payload.get("themes")
            if isinstance(raw_themes, list):
                reduced = [
                    {"name": theme.get("name"), "size": theme.get("size")}
                    for theme in raw_themes
                    if isinstance(theme, dict)
                ]
                themes = sorted(reduced, key=lambda entry: str(entry.get("name")))
            unclustered = themes_payload.get("unclustered_ids")
            unclustered_count = len(unclustered) if isinstance(unclustered, list) else 0

    coverage_rows = conn.execute(
        sa_select(
            search_coverage_record.c.acquired_by_run_id,
            search_coverage_record.c.adequacy_verdict,
            search_coverage_record.c.stop_condition,
            search_coverage_record.c.backends,
        )
        .where(search_coverage_record.c.project_id == project_id)
        .where(search_coverage_record.c.evidence_scope_id == evidence_scope_id)
        .order_by(search_coverage_record.c.created_at, search_coverage_record.c.acquired_by_run_id)
    ).all()
    search_coverage = [
        {
            "acquired_by_run_id": str(row.acquired_by_run_id),
            "adequacy_verdict": row.adequacy_verdict,
            "stop_condition": row.stop_condition,
            "backends": row.backends,
        }
        for row in coverage_rows
    ]

    effective = effective_screen_rows()
    count_rows = conn.execute(
        sa_select(
            effective.c.status,
            effective.c.screen_stage,
            effective.c.screen_generation,
            func.count().label("n"),
        )
        .where(effective.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == evidence_scope_id)
        .group_by(effective.c.status, effective.c.screen_stage, effective.c.screen_generation)
    ).all()
    screen_counts = sorted(
        (
            {
                "status": row.status,
                "screen_stage": row.screen_stage,
                "screen_generation": row.screen_generation,
                "count": row.n,
            }
            for row in count_rows
        ),
        key=lambda entry: (entry["status"], entry["screen_stage"], entry["screen_generation"]),
    )

    executed_queries, zero_result_queries = _executed_queries(
        conn, project_id=project_id, evidence_scope_id=evidence_scope_id
    )
    screened_event_counts = _source_screened_counts(
        conn, project_id=project_id, evidence_scope_id=evidence_scope_id
    )

    return {
        "bundle_version": BUNDLE_VERSION,
        "coverage": coverage,
        "themes": themes,
        "unclustered_count": unclustered_count,
        "search_coverage": search_coverage,
        "screen_counts": screen_counts,
        "screened_event_counts": screened_event_counts,
        "executed_queries": executed_queries,
        "zero_result_queries": zero_result_queries,
    }


def _executed_queries(
    conn: Connection, *, project_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse ``search.executed`` payloads for the scope, in emission order.

    Payload keys (acquire.py): ``query``/``backend``/``trust_class``/``mode``/
    ``query_origin``/``verb``/``depth``/``filters``/``status``/``result_count``/
    ``error``/``evidence_scope_id`` (+ optional ``post_filter_excluded``). A
    zero-result query is an ``ok`` call whose ``result_count`` is 0.
    """
    rows = conn.execute(
        sa_select(event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.event_type == "search.executed")
        .order_by(event_log.c.sequence)
    ).all()
    executed: list[dict[str, Any]] = []
    zero_result: list[dict[str, Any]] = []
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        if payload.get("evidence_scope_id") != str(evidence_scope_id):
            continue
        entry = {
            "query": payload.get("query"),
            "backend": payload.get("backend"),
            "query_origin": payload.get("query_origin"),
            "verb": payload.get("verb"),
            "filters": payload.get("filters"),
            "status": payload.get("status"),
            "result_count": payload.get("result_count"),
        }
        executed.append(entry)
        if payload.get("status") == "ok" and payload.get("result_count") == 0:
            zero_result.append({"query": payload.get("query"), "backend": payload.get("backend")})
    return executed, zero_result


def _source_screened_counts(
    conn: Connection, *, project_id: uuid.UUID, evidence_scope_id: uuid.UUID
) -> dict[str, int]:
    """Tally ``source.screened`` event payloads by status for the scope."""
    rows = conn.execute(
        sa_select(event_log.c.payload)
        .where(event_log.c.project_id == project_id)
        .where(event_log.c.event_type == "source.screened")
        .order_by(event_log.c.sequence)
    ).all()
    counts: dict[str, int] = {}
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        if payload.get("evidence_scope_id") != str(evidence_scope_id):
            continue
        status = payload.get("status")
        if isinstance(status, str):
            counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


# --- P3: deepening selection -----------------------------------------------


def p3_bundle(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    selection_run_id: uuid.UUID,
) -> dict[str, Any]:
    """Build the P3 selection bundle (after select).

    Reads the persisted ``selection_result`` columns (``selected``/``excluded``/
    ``flags``/``selection_provenance``/``budget``) and joins document metadata
    (title/type/tier/full-text status) for the preview and the notable
    exclusions. Composition and budget picture are derived from the persisted
    ``selected``/``excluded`` columns — no recomputation.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        selection_run_id: The select run whose ``selection_result`` to read.

    Returns:
        The versioned P3 bundle dict. ``{"bundle_version": "v1"}`` with all other
        keys empty/None when no selection row exists for the run.
    """
    row = conn.execute(
        sa_select(
            selection_result.c.evidence_scope_id,
            selection_result.c.budget,
            selection_result.c.strategy,
            selection_result.c.selected,
            selection_result.c.excluded,
            selection_result.c.flags,
            selection_result.c.selection_provenance,
        )
        .where(selection_result.c.project_id == project_id)
        .where(selection_result.c.run_id == selection_run_id)
    ).first()
    if row is None:
        return {
            "bundle_version": BUNDLE_VERSION,
            "budget": None,
            "strategy": None,
            "selection_preview": [],
            "composition_by_stratum": {},
            "full_text_availability": {},
            "budget_picture": {},
            "ranking_trust": {},
            "flags": {},
            "notable_exclusions": [],
            "dropped_strata": [],
        }

    scope_id = row.evidence_scope_id
    selected = row.selected if isinstance(row.selected, list) else []
    excluded = row.excluded if isinstance(row.excluded, dict) else {}
    flags = row.flags if isinstance(row.flags, dict) else {}
    provenance = row.selection_provenance if isinstance(row.selection_provenance, dict) else {}

    # Preview: top-N by composite score (desc), pss_id tie-break for determinism.
    ordered = sorted(
        (entry for entry in selected if isinstance(entry, dict)),
        key=lambda e: (-_as_float(e.get("composite")), str(e.get("pss_id"))),
    )
    preview_entries = ordered[:SELECTION_PREVIEW_N]
    preview_pss_ids = [str(e.get("pss_id")) for e in preview_entries]
    metadata = _doc_metadata(
        conn, project_id=project_id, evidence_scope_id=scope_id, pss_ids=preview_pss_ids
    )
    selection_preview = [
        {
            "pss_id": str(entry.get("pss_id")),
            "title": metadata.get(str(entry.get("pss_id")), {}).get("title"),
            "stratum": entry.get("stratum"),
            "evidence_type": metadata.get(str(entry.get("pss_id")), {}).get("evidence_type"),
            "quality_tier": metadata.get(str(entry.get("pss_id")), {}).get("quality_tier"),
            "reason": entry.get("reason"),
            "text_basis": entry.get("text_basis"),
        }
        for entry in preview_entries
    ]

    # Composition + budget picture per stratum, from persisted selected/excluded.
    selected_by_stratum: dict[str, int] = {}
    for entry in selected:
        if isinstance(entry, dict):
            stratum = str(entry.get("stratum"))
            selected_by_stratum[stratum] = selected_by_stratum.get(stratum, 0) + 1
    excluded_by_stratum = excluded.get("by_stratum")
    excluded_by_stratum = excluded_by_stratum if isinstance(excluded_by_stratum, dict) else {}

    strata = sorted(set(selected_by_stratum) | set(excluded_by_stratum))
    composition_by_stratum: dict[str, Any] = {}
    budget_picture: dict[str, Any] = {}
    for stratum in strata:
        reason_counts = excluded_by_stratum.get(stratum)
        reason_counts = reason_counts if isinstance(reason_counts, dict) else {}
        composition_by_stratum[stratum] = {
            "selected": selected_by_stratum.get(stratum, 0),
            "excluded": dict(sorted(reason_counts.items())),
        }
        budget_picture[stratum] = {
            "budget_exhausted": reason_counts.get("budget_exhausted", 0),
            "ranked_below_cut": reason_counts.get("ranked_below_cut", 0),
        }

    # Full-text availability of the selected set, by pss full_text_status.
    full_text_availability = _full_text_status_counts(
        conn,
        project_id=project_id,
        pss_ids=[str(e.get("pss_id")) for e in selected if isinstance(e, dict)],
    )

    # Ranking-trust signals from provenance.
    ranking_trust = {
        "effective_weights": provenance.get("effective_weights"),
        "signal_availability": provenance.get("signal_availability"),
        "backend_mode": provenance.get("backend_mode"),
        "unmatched_boosts": provenance.get("unmatched_boosts"),
    }

    # Notable exclusions digest (capped, with titles) — never the full list.
    notable = excluded.get("notable")
    notable = notable if isinstance(notable, list) else []
    notable_pss_ids = [
        str(item.get("pss_id"))
        for item in notable[:DROPPED_DIGEST_CAP]
        if isinstance(item, dict)
    ]
    notable_metadata = _doc_metadata(
        conn, project_id=project_id, evidence_scope_id=scope_id, pss_ids=notable_pss_ids
    )
    notable_exclusions = [
        {
            "pss_id": str(item.get("pss_id")),
            "flag": item.get("flag"),
            "title": notable_metadata.get(str(item.get("pss_id")), {}).get("title"),
        }
        for item in notable[:DROPPED_DIGEST_CAP]
        if isinstance(item, dict)
    ]

    # Dropped strata: strata that took zero selections (names + exclusion counts).
    # Per-stratum representative titles need the stratum->document membership,
    # which selection_result does not persist (recon: no doc-level per-stratum
    # status column); the notable-exclusions digest above carries titled examples.
    dropped_strata = [
        {"stratum": stratum, "excluded": composition_by_stratum[stratum]["excluded"]}
        for stratum in strata
        if selected_by_stratum.get(stratum, 0) == 0
    ]

    return {
        "bundle_version": BUNDLE_VERSION,
        "budget": row.budget,
        "strategy": row.strategy,
        "selection_preview": selection_preview,
        "composition_by_stratum": composition_by_stratum,
        "full_text_availability": full_text_availability,
        "budget_picture": budget_picture,
        "ranking_trust": ranking_trust,
        "flags": flags,
        "notable_exclusions": notable_exclusions,
        "dropped_strata": dropped_strata,
    }


def _as_float(value: Any) -> float:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _doc_metadata(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    evidence_scope_id: uuid.UUID,
    pss_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Return ``{pss_id: {title, evidence_type, quality_tier, full_text_status}}``.

    Joins ``project_source_snapshot`` → ``source_snapshot`` (title from metadata
    with a source-locator fallback) and left-joins classification/appraisal for
    the scope. Only the requested ids are read.
    """
    if not pss_ids:
        return {}
    ids = [uuid.UUID(pss_id) for pss_id in pss_ids]
    rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.full_text_status,
            source_snapshot.c.metadata,
            source_snapshot.c.source_locator,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
        )
        .select_from(
            project_source_snapshot.join(
                source_snapshot,
                project_source_snapshot.c.source_snapshot_id
                == source_snapshot.c.source_snapshot_id,
            )
            .outerjoin(
                source_classification_result,
                (
                    source_classification_result.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id
                )
                & (source_classification_result.c.evidence_scope_id == evidence_scope_id),
            )
            .outerjoin(
                source_appraisal_result,
                (
                    source_appraisal_result.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id
                )
                & (source_appraisal_result.c.evidence_scope_id == evidence_scope_id),
            )
        )
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.project_source_snapshot_id.in_(ids))
    ).all()
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        metadata = row.metadata if isinstance(row.metadata, dict) else {}
        title = metadata.get("title")
        if not isinstance(title, str) or not title:
            title = row.source_locator
        result[str(row.project_source_snapshot_id)] = {
            "title": title,
            "evidence_type": row.primary_evidence_type,
            "quality_tier": (
                str(row.quality_score) if row.quality_score is not None else None
            ),
            "full_text_status": row.full_text_status,
        }
    return result


def _full_text_status_counts(
    conn: Connection, *, project_id: uuid.UUID, pss_ids: list[str]
) -> dict[str, int]:
    """Tally ``project_source_snapshot.full_text_status`` for the given pss ids."""
    if not pss_ids:
        return {}
    ids = [uuid.UUID(pss_id) for pss_id in pss_ids]
    rows = conn.execute(
        sa_select(
            project_source_snapshot.c.full_text_status,
            func.count().label("n"),
        )
        .where(project_source_snapshot.c.project_id == project_id)
        .where(project_source_snapshot.c.project_source_snapshot_id.in_(ids))
        .group_by(project_source_snapshot.c.full_text_status)
    ).all()
    return dict(sorted((row.full_text_status, row.n) for row in rows))


# --- P4: synthesis shape ----------------------------------------------------


def p4_bundle(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    context: SynthesiseContext,
    synthesis_backend: SynthesisBackend,
    group_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Build the P4 synthesis-shape bundle (before synthesise).

    Wires the read-only ``propose_synthesis_plan`` (022 F5) over the walk's real
    references (the ``SynthesiseContext`` the runner assembles), adds the group
    run's per-facet flags, and reserves the B2' priority-finding counts.

    Args:
        conn: Open read connection.
        project_id: Owning project.
        context: The synthesise context (scope, intent, run references) — the
            same bundle ``synthesise_scope`` resolves, so P4's inputs never drift.
        synthesis_backend: The proposal backend seam (stub or live).
        group_run_id: The group run whose ``flags`` to read, or ``None`` when
            group did not run (grouping_flags then ``None``).

    Returns:
        The versioned P4 bundle dict. ``priority_counts`` is ``None`` this
        slice — the B2' relevance annotator ships in Phase 5; None means "not
        computed", distinct from an empty ``{}`` (no priority findings).
    """
    proposal = propose_synthesis_plan(
        conn, project_id=project_id, context=context, synthesis_backend=synthesis_backend
    )
    grouping_flags: Any = None
    if group_run_id is not None:
        group_row = conn.execute(
            sa_select(grouping_result.c.flags)
            .where(grouping_result.c.project_id == project_id)
            .where(grouping_result.c.run_id == group_run_id)
        ).first()
        if group_row is not None:
            grouping_flags = group_row.flags if isinstance(group_row.flags, dict) else {}
    return {
        "bundle_version": BUNDLE_VERSION,
        "proposal": proposal,
        "grouping_flags": grouping_flags,
        "priority_counts": None,
    }
