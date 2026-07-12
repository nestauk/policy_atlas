"""Classify screened-in documents by evidence type through a backend seam."""

import uuid
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas import events, tracing
from policy_atlas.classification_backend import ClassificationBackend, StubClassificationBackend
from policy_atlas.classify_prompt import (
    TAG_MAX_CHARS,
    TAGS_MAX_PER_DOC,
    ClassifyEnvelopePayload,
    ClassifyWire,
    provider_priors,
)
from policy_atlas.prompt_fields import clamp_reason
from policy_atlas.schema import (
    EVIDENCE_TYPES,
    METHODOLOGICAL_STRUCTURAL,
    project_source_snapshot,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    source_tag,
)
from policy_atlas.screen import effective_screen_rows
from policy_atlas.tags import has_control_character, insert_source_tags
from policy_atlas.usage import UsageAccumulator

log = structlog.get_logger()

MAX_CONCURRENT_CLASSIFY = 4
CLASSIFY_RETRY_CAP = 1


@dataclass
class ClassifyContext:
    """Runtime context for classifying one evidence scope."""

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass(frozen=True)
class _ClassifyDoc:
    pss_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    metadata: dict[str, Any]
    payload: ClassifyEnvelopePayload


def _metadata(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _text_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _payload_for(
    pss_id: uuid.UUID,
    metadata: dict[str, Any],
    label_rows: list[dict[str, Any]] | None = None,
) -> ClassifyEnvelopePayload:
    abstract = metadata.get("abstract")
    return ClassifyEnvelopePayload(
        pss_id=str(pss_id),
        title=_text_or_empty(metadata.get("title", "")),
        abstract=abstract if isinstance(abstract, str) and abstract else None,
        priors=provider_priors(metadata, label_rows=label_rows),
        metadata=metadata,
    )


def _label_rows_by_pss(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    pss_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    if not pss_ids:
        return {}

    grouped: dict[uuid.UUID, list[dict[str, Any]]] = {}
    rows = conn.execute(
        select(
            source_tag.c.project_source_snapshot_id,
            source_tag.c.tag,
            source_tag.c.tag_type,
            source_tag.c.asserted_by,
        )
        .where(source_tag.c.project_id == project_id)
        .where(source_tag.c.project_source_snapshot_id.in_(pss_ids))
        .where(source_tag.c.asserted_by != "classify")
        .order_by(source_tag.c.tag_type, source_tag.c.asserted_by, source_tag.c.tag)
    ).fetchall()
    for pss_id, tag, tag_type, asserted_by in rows:
        grouped.setdefault(pss_id, []).append(
            {"tag": tag, "tag_type": tag_type, "asserted_by": asserted_by}
        )
    return grouped


def _load_relevant_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> list[_ClassifyDoc]:
    effective = effective_screen_rows()
    rows = conn.execute(
        select(
            project_source_snapshot.c.project_source_snapshot_id,
            source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .join(
            effective,
            (effective.c.project_source_snapshot_id
             == project_source_snapshot.c.project_source_snapshot_id)
            & (effective.c.project_id == project_source_snapshot.c.project_id),
        )
        .join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
        )
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(project_source_snapshot.c.project_id == project_id)
        .where(
            ~exists().where(
                (source_classification_result.c.evidence_scope_id == scope_id)
                & (source_classification_result.c.project_source_snapshot_id
                   == project_source_snapshot.c.project_source_snapshot_id)
            )
        )
        .order_by(project_source_snapshot.c.project_source_snapshot_id)
    ).fetchall()

    pss_ids = [pss_id for pss_id, _, _ in rows]
    label_rows_by_pss = _label_rows_by_pss(conn, project_id=project_id, pss_ids=pss_ids)

    docs: list[_ClassifyDoc] = []
    for pss_id, source_snapshot_id, raw_metadata in rows:
        metadata = _metadata(raw_metadata)
        docs.append(
            _ClassifyDoc(
                pss_id=pss_id,
                source_snapshot_id=source_snapshot_id,
                metadata=metadata,
                payload=_payload_for(pss_id, metadata, label_rows_by_pss.get(pss_id, [])),
            )
        )
    return docs


def _count_effective_relevant(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    effective = effective_screen_rows()
    return conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(effective.c.project_id == project_id)
    ).scalar_one()


def _count_effective_skipped(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    effective = effective_screen_rows()
    effective_not_relevant = conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "not_relevant")
        .where(effective.c.project_id == project_id)
    ).scalar_one()

    screened_sources = (
        select(source_screening_result.c.project_source_snapshot_id)
        .where(source_screening_result.c.evidence_scope_id == scope_id)
        .where(source_screening_result.c.project_id == project_id)
        .group_by(source_screening_result.c.project_source_snapshot_id)
        .subquery("screened_sources")
    )
    effective_sources = (
        select(effective.c.project_source_snapshot_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.project_id == project_id)
        .subquery("effective_sources")
    )
    failed_only = conn.execute(
        select(func.count())
        .select_from(
            screened_sources.outerjoin(
                effective_sources,
                screened_sources.c.project_source_snapshot_id
                == effective_sources.c.project_source_snapshot_id,
            )
        )
        .where(effective_sources.c.project_source_snapshot_id.is_(None))
    ).scalar_one()
    return effective_not_relevant + failed_only


def _run_classification_calls(
    docs: list[_ClassifyDoc],
    *,
    classification_backend: ClassificationBackend,
) -> tuple[dict[int, ClassifyWire], dict[int, Exception], int, dict[str, int]]:
    baseline = len(docs)
    maximum = baseline * (1 + CLASSIFY_RETRY_CAP)
    log.info("classify.call_budget", baseline=baseline, maximum=maximum)

    results: dict[int, ClassifyWire] = {}
    errors: dict[int, Exception] = {}
    usage_totals = UsageAccumulator()
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CLASSIFY) as executor:
        submitted: list[tuple[int, Future[Any]]] = [
            (
                doc_index,
                tracing.submit_with_context(
                    executor, classification_backend.classify, doc.payload
                ),
            )
            for doc_index, doc in enumerate(docs)
        ]
        wait([future for _, future in submitted])
        for doc_index, future in submitted:
            try:
                wire, usage = future.result()
                results[doc_index] = wire
                usage_totals.add(usage)
            except Exception as exc:  # noqa: BLE001 — reduced to type name after retry.
                errors[doc_index] = exc

    retries = 0
    for doc_index in list(errors):
        retries += 1
        try:
            wire, usage = classification_backend.classify(docs[doc_index].payload)
            results[doc_index] = wire
            usage_totals.add(usage)
        except Exception as exc:  # noqa: BLE001
            errors[doc_index] = exc
        else:
            del errors[doc_index]

    return results, errors, retries, usage_totals.payload()


def _bounded_tags(tags: list[str]) -> tuple[list[str], int]:
    accepted: list[str] = []
    seen: set[str] = set()
    rejected = 0
    for raw_tag in tags:
        tag = raw_tag.strip()
        if not tag:
            continue
        if len(tag) > TAG_MAX_CHARS or has_control_character(tag):
            rejected += 1
            continue
        if tag in seen:
            continue
        seen.add(tag)
        accepted.append(tag)

    if len(accepted) > TAGS_MAX_PER_DOC:
        rejected += len(accepted) - TAGS_MAX_PER_DOC
        accepted = accepted[:TAGS_MAX_PER_DOC]

    return accepted, rejected


def classify_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ClassifyContext,
    classification_backend: ClassificationBackend | None = None,
) -> dict[str, Any]:
    """Classify all relevant sources for a screening scope.

    Reads the effective screening row per source, classifies effective-relevant
    unclassified sources, inserts one classification row per successful backend
    answer, writes bounded methodological/structural tags, and emits one
    ``source.classified`` event per successful row. Backend failures leave no
    row, so the same source is retried by the next run.

    Args:
        conn: Open database connection; all writes use its active transaction.
        project_id: Owning project.
        run_id: Run recording classification results.
        context: Evidence-scope context for the classify component.
        classification_backend: Optional classification seam. Defaults to the
            deterministic zero-egress stub backend.

    Returns:
        Component summary payload for ``component.completed``.
    """
    if classification_backend is None:
        classification_backend = StubClassificationBackend()

    docs = _load_relevant_docs(conn, project_id=project_id, scope_id=context.scope_id)
    skipped = _count_effective_skipped(conn, project_id=project_id, scope_id=context.scope_id)
    total_relevant = _count_effective_relevant(
        conn, project_id=project_id, scope_id=context.scope_id
    )
    already_classified = total_relevant - len(docs)

    by_type: dict[str, int] = {}
    classified = 0
    failed = 0
    tags_written = 0
    tags_rejected = 0

    results, errors, retries, usage_totals = _run_classification_calls(
        docs, classification_backend=classification_backend
    )

    for doc_index, doc in enumerate(docs):
        error = errors.get(doc_index)
        if error is not None:
            failed += 1
            log.warning(
                "classify.doc_failed",
                project_id=str(project_id),
                run_id=str(run_id),
                evidence_scope_id=str(context.scope_id),
                project_source_snapshot_id=str(doc.pss_id),
                error=type(error).__name__,
            )
            continue

        wire = results[doc_index]
        evidence_type = wire.primary_evidence_type
        # Explicit raise, not assert: the closed-vocabulary check must
        # survive `python -O`.
        if evidence_type not in EVIDENCE_TYPES:
            raise RuntimeError(f"classify returned out-of-vocabulary type: {evidence_type!r}")

        written_tags, rejected = _bounded_tags(list(wire.tags))
        if rejected:
            log.warning(
                "classify.tags_rejected",
                project_id=str(project_id),
                run_id=str(run_id),
                evidence_scope_id=str(context.scope_id),
                project_source_snapshot_id=str(doc.pss_id),
                tags_rejected=rejected,
            )

        classified_at = datetime.now(UTC)
        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=context.scope_id,
                project_source_snapshot_id=doc.pss_id,
                project_id=project_id,
                classified_by_run_id=run_id,
                primary_evidence_type=evidence_type,
                classified_at=classified_at,
            )
        )
        insert_source_tags(
            conn,
            project_id=project_id,
            run_id=run_id,
            now=classified_at,
            assertions=[(doc.pss_id, tag, "classify") for tag in written_tags],
            tag_type=METHODOLOGICAL_STRUCTURAL,
        )

        events.append(
            conn,
            project_id=project_id,
            run_id=run_id,
            event_type="source.classified",
            payload={
                "source_snapshot_id": str(doc.source_snapshot_id),
                "project_source_snapshot_id": str(doc.pss_id),
                "evidence_scope_id": str(context.scope_id),
                "primary_evidence_type": evidence_type,
                "confidence": float(wire.confidence),
                "reason": clamp_reason(wire.reason),
                "tags": written_tags,
            },
        )

        classified += 1
        tags_written += len(written_tags)
        tags_rejected += rejected
        by_type[evidence_type] = by_type.get(evidence_type, 0) + 1

    return {
        "classified": classified,
        "by_type": by_type,
        "skipped": skipped,
        "already_classified": already_classified,
        "failed": failed,
        "tags_written": tags_written,
        "tags_rejected": tags_rejected,
        "retries": retries,
        "usage_totals": usage_totals,
    }
