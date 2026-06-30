"""Classify component — per-document evidence-type classification on the screened-in set.

Deterministic stub only; real LLM-based classify tool is a deferred seam.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.schema import (
    project_source_snapshot,
    source_classification_result,
    source_screening_result,
    source_snapshot,
)


@dataclass
class ClassifyContext:
    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass
class ClassifyResult:
    primary_evidence_type: str
    open_tags: list[str] = field(default_factory=list)


def _stub_classify(metadata: dict[str, Any]) -> ClassifyResult:
    """Deterministic, zero-egress stub. Uses metadata sentinel keys for test control."""
    if metadata.get("_stub_non_evidence"):
        return ClassifyResult("Other (Non-evidence documents)")
    if metadata.get("_stub_systematic_review"):
        return ClassifyResult("Systematic Review and Meta-Analysis")
    if metadata.get("_stub_rct"):
        return ClassifyResult("RCTs and Quasi-Experimental Studies")
    if metadata.get("_stub_observational"):
        return ClassifyResult("Observational Research Studies")
    if metadata.get("_stub_modelling"):
        return ClassifyResult("Modelling & Simulation")
    if metadata.get("_stub_policy_guidance"):
        return ClassifyResult("Policy Syntheses & Guidance Documents")
    if metadata.get("_stub_qualitative"):
        return ClassifyResult("Qualitative & Contextual Evidence")
    if metadata.get("_stub_expert_opinion"):
        return ClassifyResult("Expert Opinion and Commentary")
    return ClassifyResult("Unknown / Insufficient information")


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
    ).fetchall()

    skipped = conn.execute(
        select(func.count())
        .select_from(source_screening_result)
        .where(source_screening_result.c.screening_scope_id == context.scope_id)
        .where(source_screening_result.c.status.in_(["not_relevant", "failed"]))
        .where(source_screening_result.c.project_id == project_id)
    ).scalar_one()

    by_type: dict[str, int] = {}

    for pss_id, snap_id, snap_meta in relevant_rows:
        result = _stub_classify(snap_meta)

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

    return {"classified": len(relevant_rows), "by_type": by_type, "skipped": skipped}
