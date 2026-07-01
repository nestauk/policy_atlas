"""Classify component — per-document evidence-type classification on the screened-in set.

Deterministic stub only; real LLM-based classify tool is a deferred seam.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.schema import (
    EVIDENCE_TYPES,
    project_source_snapshot,
    source_classification_result,
    source_screening_result,
    source_snapshot,
)

log = structlog.get_logger()
_UNKNOWN_EVIDENCE_TYPE = EVIDENCE_TYPES[-1]


@dataclass
class ClassifyContext:
    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass
class ClassifyResult:
    primary_evidence_type: str
    open_tags: list[str] = field(default_factory=list)


# Maps metadata sentinel keys to evidence types; first matching sentinel wins.
# Values are taken from EVIDENCE_TYPES (the authoritative list in schema.py).
_STUB_MAP: tuple[tuple[str, str], ...] = (
    ("_stub_non_evidence",      "Other (Non-evidence documents)"),
    ("_stub_systematic_review", "Systematic Review and Meta-Analysis"),
    ("_stub_rct",               "RCTs and Quasi-Experimental Studies"),
    ("_stub_observational",     "Observational Research Studies"),
    ("_stub_modelling",         "Modelling & Simulation"),
    ("_stub_policy_guidance",   "Policy Syntheses & Guidance Documents"),
    ("_stub_qualitative",       "Qualitative & Contextual Evidence"),
    ("_stub_expert_opinion",    "Expert Opinion and Commentary"),
)


def _stub_classify(metadata: dict[str, Any]) -> ClassifyResult:
    """Deterministic, zero-egress stub. Uses metadata sentinel keys for test control."""
    for sentinel, evidence_type in _STUB_MAP:
        if metadata.get(sentinel):
            return ClassifyResult(evidence_type)
    return ClassifyResult(_UNKNOWN_EVIDENCE_TYPE)


def classify_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ClassifyContext,
) -> dict[str, Any]:
    """Classify all relevant sources for a screening scope.

    Reads source_screening_result rows with status='relevant' for the scope,
    inserts one source_classification_result per relevant source, and emits
    source.classified events. Sources with status='not_relevant' or 'failed' are skipped.

    If no screen has been run for the scope, returns 0 classified (correct — nothing to do).
    """
    relevant_rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .join(
            source_screening_result,
            (source_screening_result.c.project_source_snapshot_id
             == project_source_snapshot.c.project_source_snapshot_id)
            & (source_screening_result.c.project_id == project_source_snapshot.c.project_id),
        )
        .join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
        )
        .where(source_screening_result.c.screening_scope_id == context.scope_id)
        .where(source_screening_result.c.status == "relevant")
        .where(project_source_snapshot.c.project_id == project_id)
        .where(
            ~exists().where(
                (source_classification_result.c.screening_scope_id == context.scope_id)
                & (source_classification_result.c.project_source_snapshot_id
                   == project_source_snapshot.c.project_source_snapshot_id)
            )
        )
    ).fetchall()

    skipped = conn.execute(
        select(func.count())
        .select_from(source_screening_result)
        .where(source_screening_result.c.screening_scope_id == context.scope_id)
        .where(source_screening_result.c.status.in_(["not_relevant", "failed"]))
        .where(source_screening_result.c.project_id == project_id)
    ).scalar_one()

    # Every relevant row is either in relevant_rows (to classify now) or already classified
    # from a prior call on this scope (idempotency skip) — no join needed, unlike relevant_rows,
    # since this count doesn't need source_snapshot.metadata.
    total_relevant = conn.execute(
        select(func.count())
        .select_from(source_screening_result)
        .where(source_screening_result.c.screening_scope_id == context.scope_id)
        .where(source_screening_result.c.status == "relevant")
        .where(source_screening_result.c.project_id == project_id)
    ).scalar_one()
    already_classified = total_relevant - len(relevant_rows)

    by_type: dict[str, int] = {}

    for pss_id, snap_id, snap_meta in relevant_rows:
        try:
            result = _stub_classify(snap_meta)
        except Exception as exc:
            log.warning(
                "classify.doc_failed",
                project_id=str(project_id),
                run_id=str(run_id),
                screening_scope_id=str(context.scope_id),
                project_source_snapshot_id=str(pss_id),
                error=str(exc),
            )
            result = ClassifyResult(_UNKNOWN_EVIDENCE_TYPE)

        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                screening_scope_id=context.scope_id,
                project_source_snapshot_id=pss_id,
                project_id=project_id,
                classified_by_run_id=run_id,
                primary_evidence_type=result.primary_evidence_type,
                open_tags=result.open_tags,
                classified_at=datetime.now(UTC),
            )
        )

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="source.classified",
            payload={
                "source_snapshot_id": str(snap_id),
                "project_source_snapshot_id": str(pss_id),
                "screening_scope_id": str(context.scope_id),
                "primary_evidence_type": result.primary_evidence_type,
                "open_tags": result.open_tags,
            },
        )

        by_type[result.primary_evidence_type] = by_type.get(result.primary_evidence_type, 0) + 1

    return {
        "classified": len(relevant_rows),
        "by_type": by_type,
        "skipped": skipped,
        "already_classified": already_classified,
    }
