"""Screen component — per-document metadata-based relevance filter.

Deterministic stub only; real LLM-based screen tool is a deferred seam.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.engine import Connection

from policy_atlas import events
from policy_atlas.schema import project_source_snapshot, source_screening_result, source_snapshot


@dataclass
class ScreenContext:
    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass
class ScreenResult:
    status: Literal["relevant", "not_relevant", "failed"]
    basis: str | None
    decision_confidence: float | None


def _stub_screen(metadata: dict[str, Any]) -> ScreenResult:
    """Deterministic, zero-egress stub. Uses metadata sentinel keys for test control."""
    if metadata.get("_stub_failed"):
        return ScreenResult(status="failed", basis=None, decision_confidence=None)

    basis = "title_abstract" if metadata.get("abstract", "").strip() else "title_only"

    if metadata.get("_stub_not_relevant"):
        return ScreenResult(status="not_relevant", basis=basis, decision_confidence=0.95)

    confidence = 0.9 if basis == "title_abstract" else 0.7
    return ScreenResult(status="relevant", basis=basis, decision_confidence=confidence)


def screen_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScreenContext,
) -> dict[str, Any]:
    """Screen all project sources against a screening scope.

    Persists one result row per source in source_screening_result.
    """
    rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .join(source_snapshot,
              project_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id)
        .where(project_source_snapshot.c.project_id == project_id)
    ).fetchall()

    counts: dict[str, int] = {
        "screened": len(rows), "relevant": 0, "not_relevant": 0,
        "failed": 0, "title_abstract": 0, "title_only": 0,
    }

    for pss_id, snap_id, snap_meta in rows:
        result = _stub_screen(snap_meta)

        conn.execute(
            source_screening_result.insert().values(
                source_screening_result_id=uuid.uuid4(),
                screening_scope_id=context.scope_id,
                project_source_snapshot_id=pss_id,
                project_id=project_id,
                screened_by_run_id=run_id,
                status=result.status,
                screen_basis=result.basis,
                screen_decision_confidence=result.decision_confidence,
                screened_at=datetime.now(UTC),
            )
        )

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="source.screened",
            payload={
                "source_snapshot_id": str(snap_id),
                "project_source_snapshot_id": str(pss_id),
                "screening_scope_id": str(context.scope_id),
                "status": result.status,
                "screen_basis": result.basis,
                "screen_decision_confidence": result.decision_confidence,
            },
        )

        counts[result.status] += 1
        if result.basis is not None:
            counts[result.basis] += 1

    return counts
