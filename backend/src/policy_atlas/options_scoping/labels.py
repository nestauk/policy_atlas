"""The label resolver: a document's evidence type and quality tier, with provenance.

Task 045, D23 / S5 (ADR 0039 decision 9). An options-scoping task inherits a
linked Evidence search task's documents; their classification and appraisal
are **read across**, never copied or re-run. One resolver answers "what type
and tier does this document carry, and where did that come from" for every
reader that shows a label: the Sources tab read models, the Result's
citations, the answer core's citation labels, and (Phase 5) the longlist's
coverage.

Resolution order, per document of this task:

1. **Own** — this task's latest classification and appraisal rows, the
   effective-row discipline every reader already used (latest row per
   ``task_source_snapshot_id``, task-wide).
2. **Inherited** — only when the task has an inbound ``task_link``: through
   each link (oldest first) to the source task's ``task_source_snapshot`` row
   for the *same* content-addressed snapshot, and that row's classification and
   appraisal **in the scope of the link's pinned walk**. The first link that
   holds a label for the document wins.
3. **Absent** — neither.

Each field resolves own first, then inherited, so a document this task
re-appraised under the current rubric keeps its inherited classification and
its own fresh tier. ``provenance`` is ``inherited`` whenever any field came
through a link (and ``source_task_id`` / ``source_run_id`` name it), ``own``
when every label is this task's, ``absent`` when there is none.

**The rubric rule.** An inherited appraisal whose ``rubric_version`` differs
from the current rubric is not mixed in: its ``quality_score`` is withheld and
``stale_rubric`` is set; the appraise skip (task 045 S6) leaves such a
document to appraise, which re-appraises it deterministically.

**Reach.** A task with no inbound link resolves own rows only and reads no
other task's rows at all — an Evidence search task's readers gain no
cross-task reach. A link grants no read of the source task (ADR 0037
decision 2); the labels a link carries are the same reach ``inherit`` already
has, and nothing is ever written for the reading task.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import and_, exists, select
from sqlalchemy.engine import Connection

from policy_atlas.core.schema import (
    capability_run,
    source_appraisal_result,
    source_classification_result,
    task_link,
    task_source_snapshot,
)
from policy_atlas.evidence_search.assess.appraise import DEFAULT_RUBRIC_VERSION

#: Where a document's labels came from.
LabelProvenance = Literal["own", "inherited", "absent"]


@dataclass(frozen=True)
class DocumentLabels:
    """One document's evidence type and quality tier, with where they came from.

    Args:
        evidence_type: The classified primary evidence type, or ``None``.
        quality_score: The appraisal score (1..5), or ``None`` — including
            when an inherited appraisal is under a stale rubric.
        rubric_version: The rubric the appraisal used, or ``None`` when there
            is no appraisal.
        provenance: ``own``, ``inherited`` or ``absent``.
        source_task_id: The linked task a label was read from, when inherited.
        source_run_id: The pinned walk (``capability_run``) of that link.
        stale_rubric: ``True`` when the inherited appraisal's rubric differs
            from the current one and its score was withheld.
    """

    evidence_type: str | None
    quality_score: int | None
    rubric_version: str | None
    provenance: LabelProvenance
    source_task_id: uuid.UUID | None = None
    source_run_id: uuid.UUID | None = None
    stale_rubric: bool = False


_ABSENT = DocumentLabels(
    evidence_type=None, quality_score=None, rubric_version=None, provenance="absent"
)


def _latest_by_tss(rows: Any, time_key: str) -> dict[uuid.UUID, Any]:
    latest: dict[uuid.UUID, Any] = {}
    for row in rows:
        previous = latest.get(row.task_source_snapshot_id)
        if previous is None or getattr(row, time_key) > getattr(previous, time_key):
            latest[row.task_source_snapshot_id] = row
    return latest


def _has_inbound_link(conn: Connection, task_id: uuid.UUID) -> bool:
    return bool(
        conn.execute(select(exists().where(task_link.c.target_task_id == task_id))).scalar()
    )


def _inherited_rows(
    conn: Connection, task_id: uuid.UUID, tss_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, Any]:
    """Return, per document, the first link's labels for it (oldest link first).

    One query: this task's document → every inbound link → the link's pinned
    walk (its scope) → the source task's row for the same snapshot → that
    row's classification and appraisal in the pinned scope.
    """
    own = task_source_snapshot.alias("own")
    source = task_source_snapshot.alias("source")
    rows = conn.execute(
        select(
            own.c.task_source_snapshot_id,
            task_link.c.source_task_id,
            task_link.c.source_capability_run_id,
            source_classification_result.c.primary_evidence_type,
            source_appraisal_result.c.quality_score,
            source_appraisal_result.c.rubric_version,
        )
        .select_from(
            own.join(task_link, task_link.c.target_task_id == own.c.task_id)
            .join(
                capability_run,
                and_(
                    capability_run.c.capability_run_id == task_link.c.source_capability_run_id,
                    capability_run.c.task_id == task_link.c.source_task_id,
                ),
            )
            .join(
                source,
                and_(
                    source.c.task_id == task_link.c.source_task_id,
                    source.c.source_snapshot_id == own.c.source_snapshot_id,
                ),
            )
            .outerjoin(
                source_classification_result,
                and_(
                    source_classification_result.c.task_id == source.c.task_id,
                    source_classification_result.c.task_source_snapshot_id
                    == source.c.task_source_snapshot_id,
                    source_classification_result.c.evidence_scope_id
                    == capability_run.c.evidence_scope_id,
                ),
            )
            .outerjoin(
                source_appraisal_result,
                and_(
                    source_appraisal_result.c.task_id == source.c.task_id,
                    source_appraisal_result.c.task_source_snapshot_id
                    == source.c.task_source_snapshot_id,
                    source_appraisal_result.c.evidence_scope_id
                    == capability_run.c.evidence_scope_id,
                ),
            )
        )
        .where(own.c.task_id == task_id)
        .where(own.c.task_source_snapshot_id.in_(tss_ids))
        .order_by(task_link.c.created_at.asc(), task_link.c.link_id.asc())
    ).all()
    first: dict[uuid.UUID, Any] = {}
    for row in rows:
        if row.task_source_snapshot_id in first:
            continue
        if row.primary_evidence_type is None and row.quality_score is None:
            continue
        first[row.task_source_snapshot_id] = row
    return first


def labels_for_snapshots(
    conn: Connection, *, task_id: uuid.UUID, tss_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, DocumentLabels]:
    """Resolve each document's evidence type and quality tier, with provenance.

    Args:
        conn: Open database connection. Read-only: nothing is written.
        task_id: The reading task.
        tss_ids: This task's ``task_source_snapshot`` ids to resolve. Ids of
            another task resolve to nothing (every query is task-scoped).

    Returns:
        One entry per requested id — ``provenance="absent"`` where the task
        and its links hold no label for the document.
    """
    ids = set(tss_ids)
    if not ids:
        return {}
    classifications = _latest_by_tss(
        conn.execute(
            select(
                source_classification_result.c.task_source_snapshot_id,
                source_classification_result.c.primary_evidence_type,
                source_classification_result.c.classified_at,
            )
            .where(source_classification_result.c.task_id == task_id)
            .where(source_classification_result.c.task_source_snapshot_id.in_(ids))
        ).all(),
        "classified_at",
    )
    appraisals = _latest_by_tss(
        conn.execute(
            select(
                source_appraisal_result.c.task_source_snapshot_id,
                source_appraisal_result.c.quality_score,
                source_appraisal_result.c.rubric_version,
                source_appraisal_result.c.appraised_at,
            )
            .where(source_appraisal_result.c.task_id == task_id)
            .where(source_appraisal_result.c.task_source_snapshot_id.in_(ids))
        ).all(),
        "appraised_at",
    )
    # Own rows only, and no other table touched, unless something links here.
    unresolved = {
        tss_id for tss_id in ids if tss_id not in classifications or tss_id not in appraisals
    }
    inherited = (
        _inherited_rows(conn, task_id, unresolved)
        if unresolved and _has_inbound_link(conn, task_id)
        else {}
    )

    resolved: dict[uuid.UUID, DocumentLabels] = {}
    for tss_id in ids:
        own_class = classifications.get(tss_id)
        own_appraisal = appraisals.get(tss_id)
        link_row = inherited.get(tss_id)
        used_link = False
        evidence_type: str | None = None
        if own_class is not None:
            evidence_type = own_class.primary_evidence_type
        elif link_row is not None and link_row.primary_evidence_type is not None:
            evidence_type = link_row.primary_evidence_type
            used_link = True
        quality_score: int | None = None
        rubric_version: str | None = None
        stale = False
        if own_appraisal is not None:
            quality_score = own_appraisal.quality_score
            rubric_version = own_appraisal.rubric_version
        elif link_row is not None and link_row.quality_score is not None:
            used_link = True
            rubric_version = link_row.rubric_version
            if rubric_version == DEFAULT_RUBRIC_VERSION:
                quality_score = link_row.quality_score
            else:
                stale = True
        if used_link:
            assert link_row is not None
            resolved[tss_id] = DocumentLabels(
                evidence_type=evidence_type,
                quality_score=quality_score,
                rubric_version=rubric_version,
                provenance="inherited",
                source_task_id=link_row.source_task_id,
                source_run_id=link_row.source_capability_run_id,
                stale_rubric=stale,
            )
        elif own_class is not None or own_appraisal is not None:
            resolved[tss_id] = DocumentLabels(
                evidence_type=evidence_type,
                quality_score=quality_score,
                rubric_version=rubric_version,
                provenance="own",
            )
        else:
            resolved[tss_id] = _ABSENT
    return resolved
