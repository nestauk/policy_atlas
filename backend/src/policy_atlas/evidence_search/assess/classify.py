"""Classify screened-in documents by evidence type through a backend seam."""

import uuid
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import exists, func, select
from sqlalchemy.engine import Connection

from policy_atlas.core import events, tracing
from policy_atlas.core.prompt_fields import clamp_reason, metadata_dict
from policy_atlas.core.schema import (
    EVIDENCE_TYPES,
    METHODOLOGICAL_STRUCTURAL,
    source_classification_result,
    source_screening_result,
    source_snapshot,
    source_tag,
    task_source_snapshot,
)
from policy_atlas.core.tags import has_control_character, insert_source_tags
from policy_atlas.core.usage import UsageAccumulator
from policy_atlas.evidence_search.assess.classification_backend import (
    ClassificationBackend,
    StubClassificationBackend,
)
from policy_atlas.evidence_search.assess.classify_prompt import (
    TAG_MAX_CHARS,
    TAGS_MAX_PER_DOC,
    ClassifyEnvelopePayload,
    ClassifyWire,
    provider_priors,
)
from policy_atlas.evidence_search.assess.screen import effective_screen_rows

log = structlog.get_logger()

# 12: the screen's stage-1 width; classify is provider-bound threads, not CPU
# (task 044 phase 8, owner 2026-09-17: 4 workers put ~25 documents through
# 6-7 rounds, 42-86 s measured).
MAX_CONCURRENT_CLASSIFY = 12
CLASSIFY_RETRY_CAP = 1

#: The one key of classify's directive (``context["classify"]``) and of
#: appraise's (task 045, S6; ADR 0039 decision 9): documents whose label the
#: label resolver already answers from a linked task, which the step leaves
#: alone. Written per step by the runner's ``leg_directive`` for a longlist
#: walk; absent everywhere else, and a no-op when absent.
SKIP_TSS_KEY = "skip_task_source_snapshot_ids"


class ClassifyDirectiveError(Exception):
    """Malformed classify directive; classify fails closed."""


def parse_skip_ids(raw: Any, error_cls: type[Exception]) -> frozenset[uuid.UUID]:
    """Parse a ``skip_task_source_snapshot_ids`` value, fail-closed.

    Args:
        raw: The key's value: a list of ``task_source_snapshot`` id strings.
        error_cls: The owning component's directive error.

    Returns:
        The ids (possibly empty).

    Raises:
        Exception: ``error_cls`` if the value is not a list of UUID strings.
    """
    if not isinstance(raw, list):
        raise error_cls(f"{SKIP_TSS_KEY} must be a list")
    ids: set[uuid.UUID] = set()
    for item in raw:
        if not isinstance(item, str):
            raise error_cls(f"{SKIP_TSS_KEY} must hold id strings")
        try:
            ids.add(uuid.UUID(item))
        except ValueError:
            raise error_cls(f"{SKIP_TSS_KEY} holds a malformed id") from None
    return frozenset(ids)


def _parse_classify_directive(raw: Any) -> frozenset[uuid.UUID]:
    """Parse the scope-context classify directive (``context["classify"]``).

    Grammar: ``{skip_task_source_snapshot_ids?: [tss_id, ...]}``. Unknown keys
    reject; a malformed id list rejects. Absent or empty means no directive:
    classify behaves exactly as before the key existed.

    Args:
        raw: The ``context["classify"]`` object, or ``None``.

    Returns:
        The documents to leave unclassified (empty when there is none).

    Raises:
        ClassifyDirectiveError: On any malformed shape.
    """
    if raw is None:
        return frozenset()
    if not isinstance(raw, dict):
        raise ClassifyDirectiveError("classify directive must be an object")
    unknown = set(raw) - {SKIP_TSS_KEY}
    if unknown:
        raise ClassifyDirectiveError("classify directive contains unknown keys")
    if SKIP_TSS_KEY not in raw:
        return frozenset()
    return parse_skip_ids(raw[SKIP_TSS_KEY], ClassifyDirectiveError)


@dataclass
class ClassifyContext:
    """Runtime context for classifying one evidence scope."""

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


@dataclass(frozen=True)
class _ClassifyDoc:
    tss_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    metadata: dict[str, Any]
    payload: ClassifyEnvelopePayload


def _text_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _payload_for(
    tss_id: uuid.UUID,
    metadata: dict[str, Any],
    label_rows: list[dict[str, Any]] | None = None,
) -> ClassifyEnvelopePayload:
    abstract = metadata.get("abstract")
    return ClassifyEnvelopePayload(
        tss_id=str(tss_id),
        title=_text_or_empty(metadata.get("title", "")),
        abstract=abstract if isinstance(abstract, str) and abstract else None,
        priors=provider_priors(metadata, label_rows=label_rows),
        metadata=metadata,
    )


def _label_rows_by_tss(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    tss_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[dict[str, Any]]]:
    if not tss_ids:
        return {}

    grouped: dict[uuid.UUID, list[dict[str, Any]]] = {}
    rows = conn.execute(
        select(
            source_tag.c.task_source_snapshot_id,
            source_tag.c.tag,
            source_tag.c.tag_type,
            source_tag.c.asserted_by,
        )
        .where(source_tag.c.task_id == task_id)
        .where(source_tag.c.task_source_snapshot_id.in_(tss_ids))
        .where(source_tag.c.asserted_by != "classify")
        .order_by(source_tag.c.tag_type, source_tag.c.asserted_by, source_tag.c.tag)
    ).fetchall()
    for tss_id, tag, tag_type, asserted_by in rows:
        grouped.setdefault(tss_id, []).append(
            {"tag": tag, "tag_type": tag_type, "asserted_by": asserted_by}
        )
    return grouped


def _load_relevant_docs(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    skip: frozenset[uuid.UUID] = frozenset(),
) -> list[_ClassifyDoc]:
    effective = effective_screen_rows()
    query = (
        select(
            task_source_snapshot.c.task_source_snapshot_id,
            source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .join(
            effective,
            (effective.c.task_source_snapshot_id
             == task_source_snapshot.c.task_source_snapshot_id)
            & (effective.c.task_id == task_source_snapshot.c.task_id),
        )
        .join(
            source_snapshot,
            task_source_snapshot.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
        )
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(task_source_snapshot.c.task_id == task_id)
        .where(
            ~exists().where(
                (source_classification_result.c.evidence_scope_id == scope_id)
                & (source_classification_result.c.task_source_snapshot_id
                   == task_source_snapshot.c.task_source_snapshot_id)
            )
        )
        .order_by(task_source_snapshot.c.task_source_snapshot_id)
    )
    if skip:
        query = query.where(task_source_snapshot.c.task_source_snapshot_id.not_in(skip))
    rows = conn.execute(query).fetchall()

    tss_ids = [tss_id for tss_id, _, _ in rows]
    label_rows_by_tss = _label_rows_by_tss(conn, task_id=task_id, tss_ids=tss_ids)

    docs: list[_ClassifyDoc] = []
    for tss_id, source_snapshot_id, raw_metadata in rows:
        metadata = metadata_dict(raw_metadata)
        docs.append(
            _ClassifyDoc(
                tss_id=tss_id,
                source_snapshot_id=source_snapshot_id,
                metadata=metadata,
                payload=_payload_for(tss_id, metadata, label_rows_by_tss.get(tss_id, [])),
            )
        )
    return docs


def _count_unclassified_in(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
    ids: frozenset[uuid.UUID],
) -> int:
    """Count effective-relevant, not-yet-classified documents among ``ids``."""
    effective = effective_screen_rows()
    return int(
        conn.execute(
            select(func.count())
            .select_from(effective)
            .where(effective.c.evidence_scope_id == scope_id)
            .where(effective.c.task_id == task_id)
            .where(effective.c.status == "relevant")
            .where(effective.c.task_source_snapshot_id.in_(ids))
            .where(
                ~exists().where(
                    (source_classification_result.c.evidence_scope_id == scope_id)
                    & (source_classification_result.c.task_source_snapshot_id
                       == effective.c.task_source_snapshot_id)
                )
            )
        ).scalar_one()
    )


def _count_effective_relevant(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    effective = effective_screen_rows()
    return conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(effective.c.task_id == task_id)
    ).scalar_one()


def _count_effective_skipped(
    conn: Connection,
    *,
    task_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> int:
    effective = effective_screen_rows()
    # task 019: excluded_retracted docs never reach classify eligibility
    # (_load_relevant_docs filters status == 'relevant') but still have an
    # effective screening row, so they must land in this "skipped" bucket —
    # otherwise the classified+skipped+already_classified funnel invariant
    # would silently drop them. Named a distinct bucket in screen's own
    # summary, but classify's "skipped" is already a blended catch-all
    # (not_relevant + all-attempts-failed), so folding it in here is not the
    # don't-flatten-status violation that lumping it into a literal
    # "not_relevant" would be.
    effective_not_relevant_or_excluded_retracted = conn.execute(
        select(func.count())
        .select_from(effective)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status.in_(("not_relevant", "excluded_retracted")))
        .where(effective.c.task_id == task_id)
    ).scalar_one()

    screened_sources = (
        select(source_screening_result.c.task_source_snapshot_id)
        .where(source_screening_result.c.evidence_scope_id == scope_id)
        .where(source_screening_result.c.task_id == task_id)
        .group_by(source_screening_result.c.task_source_snapshot_id)
        .subquery("screened_sources")
    )
    effective_sources = (
        select(effective.c.task_source_snapshot_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.task_id == task_id)
        .subquery("effective_sources")
    )
    failed_only = conn.execute(
        select(func.count())
        .select_from(
            screened_sources.outerjoin(
                effective_sources,
                screened_sources.c.task_source_snapshot_id
                == effective_sources.c.task_source_snapshot_id,
            )
        )
        .where(effective_sources.c.task_source_snapshot_id.is_(None))
    ).scalar_one()
    return effective_not_relevant_or_excluded_retracted + failed_only


def _run_classification_calls(
    docs: list[_ClassifyDoc],
    *,
    classification_backend: ClassificationBackend,
) -> tuple[dict[int, ClassifyWire], dict[int, Exception], int, dict[str, int]]:
    baseline = len(docs)
    maximum = baseline * (1 + CLASSIFY_RETRY_CAP)
    log.info("classify.call_budget", baseline=baseline, maximum=maximum)

    # The process-wide classify slots (task 045, S2): every walk in the
    # process shares one budget of provider calls, so a longlist walk and its
    # option searches do not each take twelve. Imported here, not at module
    # level: the slots module sizes itself from this module's constant.
    from policy_atlas.runtime.walk_pool import CLASSIFY_SLOTS

    def classify_in_slot(payload: ClassifyEnvelopePayload) -> Any:
        with CLASSIFY_SLOTS:
            return classification_backend.classify(payload)

    results: dict[int, ClassifyWire] = {}
    errors: dict[int, Exception] = {}
    usage_totals = UsageAccumulator()
    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_CLASSIFY) as executor:
        submitted: list[tuple[int, Future[Any]]] = [
            (
                doc_index,
                tracing.submit_with_context(executor, classify_in_slot, doc.payload),
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
            wire, usage = classify_in_slot(docs[doc_index].payload)
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
    task_id: uuid.UUID,
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

    Task 045: ``context.context["classify"]`` may carry
    ``{"skip_task_source_snapshot_ids": [...]}`` (parsed fail-closed by
    ``_parse_classify_directive``) — documents whose type the label resolver
    already answers from a linked task. They are left unclassified and
    counted as ``resolved_elsewhere``; with no directive nothing changes.

    Args:
        conn: Open database connection; all writes use its active transaction.
        task_id: Owning task.
        run_id: Run recording classification results.
        context: Evidence-scope context for the classify component.
        classification_backend: Optional classification seam. Defaults to the
            deterministic zero-egress stub backend.

    Returns:
        Component summary payload for ``component.completed``.

    Raises:
        ClassifyDirectiveError: If ``context.context["classify"]`` is malformed.
    """
    if classification_backend is None:
        classification_backend = StubClassificationBackend()

    skip = _parse_classify_directive(context.context.get("classify"))
    docs = _load_relevant_docs(conn, task_id=task_id, scope_id=context.scope_id, skip=skip)
    skipped = _count_effective_skipped(conn, task_id=task_id, scope_id=context.scope_id)
    total_relevant = _count_effective_relevant(
        conn, task_id=task_id, scope_id=context.scope_id
    )
    resolved_elsewhere = (
        _count_unclassified_in(conn, task_id=task_id, scope_id=context.scope_id, ids=skip)
        if skip
        else 0
    )
    already_classified = total_relevant - len(docs) - resolved_elsewhere

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
                task_id=str(task_id),
                run_id=str(run_id),
                evidence_scope_id=str(context.scope_id),
                task_source_snapshot_id=str(doc.tss_id),
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
                task_id=str(task_id),
                run_id=str(run_id),
                evidence_scope_id=str(context.scope_id),
                task_source_snapshot_id=str(doc.tss_id),
                tags_rejected=rejected,
            )

        classified_at = datetime.now(UTC)
        conn.execute(
            source_classification_result.insert().values(
                source_classification_result_id=uuid.uuid4(),
                evidence_scope_id=context.scope_id,
                task_source_snapshot_id=doc.tss_id,
                task_id=task_id,
                classified_by_run_id=run_id,
                primary_evidence_type=evidence_type,
                classified_at=classified_at,
            )
        )
        insert_source_tags(
            conn,
            task_id=task_id,
            run_id=run_id,
            now=classified_at,
            assertions=[(doc.tss_id, tag, "classify") for tag in written_tags],
            tag_type=METHODOLOGICAL_STRUCTURAL,
        )

        events.append(
            conn,
            task_id=task_id,
            run_id=run_id,
            event_type="source.classified",
            payload={
                "source_snapshot_id": str(doc.source_snapshot_id),
                "task_source_snapshot_id": str(doc.tss_id),
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

    summary: dict[str, Any] = {
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
    if SKIP_TSS_KEY in (context.context.get("classify") or {}):
        # Present only under the directive, so every other summary is unchanged.
        summary["resolved_elsewhere"] = resolved_elsewhere
    return summary
