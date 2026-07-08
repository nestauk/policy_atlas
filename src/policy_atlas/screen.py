"""Screen component: consensus envelope screen plus full-text confirmation."""

from __future__ import annotations

import uuid
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

import structlog
from sqlalchemy import exists, func
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection
from sqlalchemy.sql.selectable import Subquery

from policy_atlas import events
from policy_atlas.prompt_fields import clamp_reason
from policy_atlas.schema import (
    chunk,
    project_source_snapshot,
    source_screening_result,
    source_snapshot,
)
from policy_atlas.screen_prompt import (
    SCREEN_QUORUM,
    SCREEN_REPS,
    STAGE2_REPS,
    STAGE2_WINDOW_CHAR_BUDGET,
    ScreenEnvelopePayload,
    ScreenFullTextPayload,
    ScreenRepWire,
)
from policy_atlas.screening_backend import ScreeningBackend, StubScreeningBackend
from policy_atlas.windowing import greedy_windows

log = structlog.get_logger()

ScreenStatus = Literal["relevant", "not_relevant", "failed"]
ScreenBasis = Literal["title_abstract", "title_only", "full_text"]

SCREEN_RETRY_CAP = 1
MAX_CONCURRENT_STAGE1 = 12
MAX_CONCURRENT_STAGE2 = 4


@dataclass(frozen=True)
class ScreenContext:
    """Scope-level input to screen.

    Attributes:
        scope_id: Evidence scope being screened.
        intent: Scope intent used by relevance prompts.
        context: Scope context JSONB, optionally carrying
            ``{"screening": {"stage": 1 | 2}}``.
    """

    scope_id: uuid.UUID
    intent: str
    context: dict[str, Any]


class ScreenDirectiveError(Exception):
    """Malformed screening directive; screen fails closed."""


@dataclass
class _CallBudget:
    maximum: int
    used: int = 0

    def reserve(self) -> bool:
        if self.used >= self.maximum:
            return False
        self.used += 1
        return True


@dataclass(frozen=True)
class _RepOutcome:
    rep: ScreenRepWire | None = None
    error_type: str | None = None

    @property
    def failed(self) -> bool:
        return self.rep is None


@dataclass(frozen=True)
class _Stage1Doc:
    pss_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    metadata: dict[str, Any]
    basis: Literal["title_abstract", "title_only"]
    payload: ScreenEnvelopePayload


@dataclass(frozen=True)
class _Stage2Doc:
    pss_id: uuid.UUID
    source_snapshot_id: uuid.UUID
    metadata: dict[str, Any]
    chunks: list[tuple[uuid.UUID, str]]


def effective_screen_rows() -> Subquery:
    """Return the highest-stage non-failed screening row per scope/source.

    Raw ``status='relevant'`` joins are structurally wrong under two-stage
    screening rows: demoted docs leak in, and confirmed docs can be read twice.
    Consumers should join this selectable instead and then filter its effective
    ``status``/``screen_stage`` columns.

    Returns:
        A SQLAlchemy subquery exposing all ``source_screening_result`` columns
        for the effective row.
    """
    ranked = (
        sa_select(
            source_screening_result,
            func.row_number()
            .over(
                partition_by=(
                    source_screening_result.c.evidence_scope_id,
                    source_screening_result.c.project_source_snapshot_id,
                ),
                order_by=source_screening_result.c.screen_stage.desc(),
            )
            .label("_screen_rank"),
        )
        .where(source_screening_result.c.status != "failed")
        .subquery("screen_ranked")
    )
    return (
        sa_select(
            *[
                getattr(ranked.c, column.name)
                for column in source_screening_result.columns
            ]
        )
        .where(ranked.c._screen_rank == 1)
        .subquery("effective_screen_rows")
    )


def _metadata(raw: Any) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, dict) else {}


def _text_value(metadata: dict[str, Any], key: str) -> str:
    value = metadata.get(key)
    return value if isinstance(value, str) else ""


def _optional_text_value(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    return value if isinstance(value, str) else None


def _screen_basis(metadata: dict[str, Any]) -> Literal["title_abstract", "title_only"]:
    abstract = _text_value(metadata, "abstract")
    return "title_abstract" if abstract.strip() else "title_only"


def _parse_screen_stage(context: dict[str, Any]) -> Literal[1, 2]:
    raw = context.get("screening")
    if raw is None:
        return 1
    if not isinstance(raw, dict):
        raise ScreenDirectiveError("screening directive must be an object")
    unknown = set(raw) - {"stage"}
    if unknown:
        raise ScreenDirectiveError("screening directive contains unknown keys")
    if "stage" not in raw:
        return 1
    stage = raw["stage"]
    if isinstance(stage, bool) or not isinstance(stage, int):
        raise ScreenDirectiveError("screening directive stage must be an integer")
    if stage not in (1, 2):
        raise ScreenDirectiveError("screening directive stage must be 1 or 2")
    return cast("Literal[1, 2]", stage)


def _rep_payload(outcome: _RepOutcome) -> dict[str, Any]:
    if outcome.rep is None:
        return {"failed": True, "error": outcome.error_type or "RuntimeError"}
    return {
        "decision": outcome.rep.decision,
        "confidence": float(outcome.rep.confidence),
        "reason": clamp_reason(outcome.rep.reason),
    }


def _vote_decision(rep: ScreenRepWire) -> Literal["relevant", "not_relevant"]:
    return "relevant" if rep.decision in ("relevant", "unsure") else "not_relevant"


def _p_relevant(rep: ScreenRepWire) -> float:
    if rep.decision == "relevant":
        return float(rep.confidence)
    if rep.decision == "not_relevant":
        return 1.0 - float(rep.confidence)
    return 0.5


def _insert_screen_row(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
    status: ScreenStatus,
    basis: ScreenBasis | None,
    confidence: float | None,
    stage: Literal[1, 2],
) -> None:
    conn.execute(
        source_screening_result.insert().values(
            source_screening_result_id=uuid.uuid4(),
            evidence_scope_id=scope_id,
            project_source_snapshot_id=pss_id,
            project_id=project_id,
            screened_by_run_id=run_id,
            status=status,
            screen_basis=basis,
            screen_decision_confidence=confidence,
            screen_stage=stage,
            screened_at=datetime.now(UTC),
        )
    )


def _append_screened_event(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    scope_id: uuid.UUID,
    source_snapshot_id: uuid.UUID,
    pss_id: uuid.UUID,
    status: ScreenStatus,
    basis: ScreenBasis | None,
    confidence: float | None,
    stage: Literal[1, 2],
    reps: list[dict[str, Any]],
    agreement: dict[str, int],
    flags: list[str],
) -> None:
    events.append(
        conn,
        project_id=project_id,
        run_id=run_id,
        event_type="source.screened",
        payload={
            "source_snapshot_id": str(source_snapshot_id),
            "project_source_snapshot_id": str(pss_id),
            "evidence_scope_id": str(scope_id),
            "status": status,
            "screen_basis": basis,
            "screen_decision_confidence": confidence,
            "screen_stage": stage,
            "reps": reps,
            "agreement": agreement,
            "aggregation_flags": flags,
        },
    )


def _load_stage1_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
    intent: str,
) -> list[_Stage1Doc]:
    rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            source_snapshot.c.metadata,
        )
        .join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        )
        .where(project_source_snapshot.c.project_id == project_id)
        .where(
            ~exists().where(
                (source_screening_result.c.evidence_scope_id == scope_id)
                & (
                    source_screening_result.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id
                )
                & (source_screening_result.c.status != "failed")
                & (source_screening_result.c.screen_stage == 1)
            )
        )
        .order_by(project_source_snapshot.c.ingested_at)
    ).fetchall()

    docs: list[_Stage1Doc] = []
    for row in rows:
        metadata = _metadata(row.metadata)
        basis = _screen_basis(metadata)
        docs.append(
            _Stage1Doc(
                pss_id=cast("uuid.UUID", row.project_source_snapshot_id),
                source_snapshot_id=cast("uuid.UUID", row.source_snapshot_id),
                metadata=metadata,
                basis=basis,
                payload=ScreenEnvelopePayload(
                    pss_id=str(row.project_source_snapshot_id),
                    title=_text_value(metadata, "title"),
                    abstract=_optional_text_value(metadata, "abstract"),
                    abstract_source=_optional_text_value(metadata, "abstract_source"),
                    intent=intent,
                    metadata=metadata,
                ),
            )
        )
    return docs


def _run_stage1_reps(
    docs: list[_Stage1Doc],
    *,
    screening_backend: ScreeningBackend,
) -> tuple[dict[int, list[_RepOutcome]], int]:
    tasks: list[tuple[int, int]] = [
        (doc_index, rep_index)
        for doc_index in range(len(docs))
        for rep_index in range(SCREEN_REPS)
    ]
    baseline = len(tasks)
    budget = _CallBudget(maximum=baseline * (1 + SCREEN_RETRY_CAP))
    log.info("screen.call_budget", stage=1, baseline=baseline, maximum=budget.maximum)

    results: dict[tuple[int, int], ScreenRepWire] = {}
    errors: dict[tuple[int, int], Exception] = {}

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STAGE1) as executor:
        submitted: list[tuple[tuple[int, int], Future[ScreenRepWire]]] = []
        for key in tasks:
            if not budget.reserve():
                errors[key] = RuntimeError("call budget exhausted")
                continue
            doc_index, rep_index = key
            submitted.append(
                (
                    key,
                    executor.submit(
                        screening_backend.screen_envelope,
                        docs[doc_index].payload,
                        rep_index=rep_index,
                    ),
                )
            )
        wait([future for _, future in submitted])
        for key, future in submitted:
            try:
                results[key] = future.result()
            except Exception as exc:  # noqa: BLE001 - reduced to type name in events
                errors[key] = exc

    retry_count = 0
    for key in list(errors):
        if not budget.reserve():
            continue
        retry_count += 1
        doc_index, rep_index = key
        try:
            results[key] = screening_backend.screen_envelope(
                docs[doc_index].payload, rep_index=rep_index
            )
        except Exception as exc:  # noqa: BLE001
            errors[key] = exc
        else:
            del errors[key]

    by_doc: dict[int, list[_RepOutcome]] = {
        doc_index: [] for doc_index in range(len(docs))
    }
    for doc_index in range(len(docs)):
        for rep_index in range(SCREEN_REPS):
            key = (doc_index, rep_index)
            if key in results:
                by_doc[doc_index].append(_RepOutcome(rep=results[key]))
            else:
                # Every key missing from results has an errors entry by
                # construction (budget denial or captured exception).
                by_doc[doc_index].append(
                    _RepOutcome(error_type=type(errors[key]).__name__)
                )
    return by_doc, retry_count


def _run_stage1(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScreenContext,
    screening_backend: ScreeningBackend,
) -> dict[str, Any]:
    docs = _load_stage1_docs(
        conn,
        project_id=project_id,
        scope_id=context.scope_id,
        intent=context.intent,
    )
    outcomes_by_doc, retries = _run_stage1_reps(docs, screening_backend=screening_backend)
    counts: dict[str, int] = {
        "screened": len(docs),
        "relevant": 0,
        "not_relevant": 0,
        "failed": 0,
        "title_abstract": 0,
        "title_only": 0,
        "unsure_reps": 0,
        "non_unanimous": 0,
        "rep_failures": 0,
        "tie_broken": 0,
        "retries": retries,
    }

    for doc_index, doc in enumerate(docs):
        outcomes = outcomes_by_doc[doc_index]
        reps_payload = [_rep_payload(outcome) for outcome in outcomes]
        survivors = [outcome.rep for outcome in outcomes if outcome.rep is not None]
        failed_reps = len(outcomes) - len(survivors)
        counts["rep_failures"] += failed_reps
        counts["unsure_reps"] += sum(1 for rep in survivors if rep.decision == "unsure")

        if len(survivors) < SCREEN_QUORUM:
            status: ScreenStatus = "failed"
            basis: ScreenBasis | None = None
            confidence: float | None = None
            agreement = {"agreeing": 0, "survivors": len(survivors)}
            flags: list[str] = []
        else:
            relevant_votes = sum(1 for rep in survivors if _vote_decision(rep) == "relevant")
            not_relevant_votes = len(survivors) - relevant_votes
            flags = []
            if relevant_votes == not_relevant_votes:
                status = "relevant"
                flags.append("tie_broken")
            elif relevant_votes > not_relevant_votes:
                status = "relevant"
            else:
                status = "not_relevant"

            # Rev 1.11: the veto needs an AFFIRMATIVE relevant dissent — a lone
            # unsure against a not_relevant majority lowers confidence through
            # the probability leg but no longer flips a consensus exclusion.
            if (
                doc.basis == "title_only"
                and status == "not_relevant"
                and any(rep.decision == "relevant" for rep in survivors)
            ):
                status = "relevant"
                flags.append("title_only_unanimity_applied")

            mean_p = sum(_p_relevant(rep) for rep in survivors) / len(survivors)
            confidence = mean_p if status == "relevant" else 1.0 - mean_p
            basis = doc.basis
            agreement = {
                "agreeing": sum(
                    1 for rep in survivors if _vote_decision(rep) == status
                ),
                "survivors": len(survivors),
            }
            if agreement["agreeing"] < agreement["survivors"]:
                counts["non_unanimous"] += 1
            if "tie_broken" in flags:
                counts["tie_broken"] += 1

        _insert_screen_row(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=context.scope_id,
            pss_id=doc.pss_id,
            status=status,
            basis=basis,
            confidence=confidence,
            stage=1,
        )
        _append_screened_event(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=context.scope_id,
            source_snapshot_id=doc.source_snapshot_id,
            pss_id=doc.pss_id,
            status=status,
            basis=basis,
            confidence=confidence,
            stage=1,
            reps=reps_payload,
            agreement=agreement,
            flags=flags,
        )

        counts[status] += 1
        if basis is not None:
            counts[basis] += 1

    return counts


def _stage2_text_snapshot_id(
    *,
    envelope_snapshot_id: uuid.UUID,
    full_text_snapshot_id: uuid.UUID | None,
    full_text_status: str,
    envelope_text_basis: str,
) -> uuid.UUID | None:
    if full_text_status == "ingested" and full_text_snapshot_id is not None:
        return full_text_snapshot_id
    if envelope_text_basis == "full_text":
        return envelope_snapshot_id
    return None


def _load_stage2_docs(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    scope_id: uuid.UUID,
) -> tuple[list[_Stage2Doc], int]:
    effective = effective_screen_rows()
    rows = conn.execute(
        sa_select(
            project_source_snapshot.c.project_source_snapshot_id,
            project_source_snapshot.c.source_snapshot_id,
            project_source_snapshot.c.full_text_snapshot_id,
            project_source_snapshot.c.full_text_status,
            source_snapshot.c.text_basis,
            source_snapshot.c.metadata,
        )
        .join(
            effective,
            (
                effective.c.project_source_snapshot_id
                == project_source_snapshot.c.project_source_snapshot_id
            )
            & (effective.c.project_id == project_source_snapshot.c.project_id),
        )
        .join(
            source_snapshot,
            project_source_snapshot.c.source_snapshot_id
            == source_snapshot.c.source_snapshot_id,
        )
        .where(project_source_snapshot.c.project_id == project_id)
        .where(effective.c.evidence_scope_id == scope_id)
        .where(effective.c.status == "relevant")
        .where(effective.c.screen_stage == 1)
        .where(
            ~exists().where(
                (source_screening_result.c.evidence_scope_id == scope_id)
                & (
                    source_screening_result.c.project_source_snapshot_id
                    == project_source_snapshot.c.project_source_snapshot_id
                )
                & (source_screening_result.c.status != "failed")
                & (source_screening_result.c.screen_stage == 2)
            )
        )
        .order_by(project_source_snapshot.c.ingested_at)
    ).fetchall()

    candidate_records: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, dict[str, Any]]] = []
    skipped_no_fulltext = 0
    chunk_snapshot_ids: set[uuid.UUID] = set()
    for row in rows:
        envelope_snapshot_id = cast("uuid.UUID", row.source_snapshot_id)
        chunk_snapshot_id = _stage2_text_snapshot_id(
            envelope_snapshot_id=envelope_snapshot_id,
            full_text_snapshot_id=cast("uuid.UUID | None", row.full_text_snapshot_id),
            full_text_status=cast("str", row.full_text_status),
            envelope_text_basis=cast("str", row.text_basis),
        )
        if chunk_snapshot_id is None:
            skipped_no_fulltext += 1
            continue
        chunk_snapshot_ids.add(chunk_snapshot_id)
        candidate_records.append(
            (
                cast("uuid.UUID", row.project_source_snapshot_id),
                envelope_snapshot_id,
                chunk_snapshot_id,
                _metadata(row.metadata),
            )
        )

    chunks_by_snapshot: dict[uuid.UUID, list[tuple[uuid.UUID, str]]] = {}
    if chunk_snapshot_ids:
        chunk_rows = conn.execute(
            sa_select(chunk.c.source_snapshot_id, chunk.c.chunk_id, chunk.c.content)
            .where(chunk.c.source_snapshot_id.in_(chunk_snapshot_ids))
            .order_by(chunk.c.source_snapshot_id, chunk.c.sequence)
        ).fetchall()
        for chunk_row in chunk_rows:
            snapshot_id = cast("uuid.UUID", chunk_row.source_snapshot_id)
            chunks_by_snapshot.setdefault(snapshot_id, []).append(
                (cast("uuid.UUID", chunk_row.chunk_id), cast("str", chunk_row.content))
            )

    docs = [
        _Stage2Doc(
            pss_id=pss_id,
            source_snapshot_id=source_snapshot_id,
            metadata=metadata,
            chunks=chunks_by_snapshot.get(chunk_snapshot_id, []),
        )
        for pss_id, source_snapshot_id, chunk_snapshot_id, metadata in candidate_records
    ]
    return docs, skipped_no_fulltext


def _stage2_payload(doc: _Stage2Doc, *, intent: str) -> ScreenFullTextPayload | None:
    segments = [(str(chunk_id), content) for chunk_id, content in doc.chunks]
    windows = greedy_windows(
        segments,
        char_budget=STAGE2_WINDOW_CHAR_BUDGET,
        overlap_segments=0,
    )
    if not windows:
        return None
    first_window = windows[0]
    return ScreenFullTextPayload(
        pss_id=str(doc.pss_id),
        title=_text_value(doc.metadata, "title"),
        intent=intent,
        window_index=0,
        segments=[
            {"segment_id": segment_id, "content": content}
            for segment_id, content in first_window
        ],
        metadata=doc.metadata,
    )


def _run_stage2_reps(
    payloads: dict[int, ScreenFullTextPayload],
    *,
    screening_backend: ScreeningBackend,
) -> tuple[dict[int, _RepOutcome], int]:
    tasks = list(payloads)
    baseline = len(tasks) * STAGE2_REPS
    budget = _CallBudget(maximum=baseline * (1 + SCREEN_RETRY_CAP))
    log.info("screen.call_budget", stage=2, baseline=baseline, maximum=budget.maximum)

    results: dict[int, ScreenRepWire] = {}
    errors: dict[int, Exception] = {}

    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_STAGE2) as executor:
        submitted: list[tuple[int, Future[ScreenRepWire]]] = []
        for doc_index in tasks:
            if not budget.reserve():
                errors[doc_index] = RuntimeError("call budget exhausted")
                continue
            submitted.append(
                (
                    doc_index,
                    executor.submit(screening_backend.screen_fulltext, payloads[doc_index]),
                )
            )
        wait([future for _, future in submitted])
        for doc_index, future in submitted:
            try:
                results[doc_index] = future.result()
            except Exception as exc:  # noqa: BLE001 - event gets type name only
                errors[doc_index] = exc

    retry_count = 0
    for doc_index in list(errors):
        if not budget.reserve():
            continue
        retry_count += 1
        try:
            results[doc_index] = screening_backend.screen_fulltext(payloads[doc_index])
        except Exception as exc:  # noqa: BLE001
            errors[doc_index] = exc
        else:
            del errors[doc_index]

    outcomes: dict[int, _RepOutcome] = {}
    for doc_index in tasks:
        if doc_index in results:
            outcomes[doc_index] = _RepOutcome(rep=results[doc_index])
        else:
            # Every index missing from results has an errors entry by
            # construction (budget denial or captured exception).
            outcomes[doc_index] = _RepOutcome(
                error_type=type(errors[doc_index]).__name__
            )
    return outcomes, retry_count


def _assert_stage1_relevant(
    conn: Connection,
    *,
    scope_id: uuid.UUID,
    pss_id: uuid.UUID,
) -> None:
    row = conn.execute(
        sa_select(source_screening_result.c.source_screening_result_id)
        .where(source_screening_result.c.evidence_scope_id == scope_id)
        .where(source_screening_result.c.project_source_snapshot_id == pss_id)
        .where(source_screening_result.c.screen_stage == 1)
        .where(source_screening_result.c.status == "relevant")
        .limit(1)
    ).first()
    if row is None:
        raise RuntimeError("stage-2 screening insert requires a relevant stage-1 row")


def _run_stage2(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScreenContext,
    screening_backend: ScreeningBackend,
) -> dict[str, Any]:
    docs, skipped_no_fulltext = _load_stage2_docs(
        conn, project_id=project_id, scope_id=context.scope_id
    )
    payloads: dict[int, ScreenFullTextPayload] = {}
    empty_fulltext: set[int] = set()
    for doc_index, doc in enumerate(docs):
        payload = _stage2_payload(doc, intent=context.intent)
        if payload is None:
            empty_fulltext.add(doc_index)
        else:
            payloads[doc_index] = payload

    outcomes_by_doc, retries = _run_stage2_reps(
        payloads, screening_backend=screening_backend
    )
    counts: dict[str, int] = {
        "stage2_screened": len(docs),
        "confirmed": 0,
        "demoted": 0,
        "failed": 0,
        "skipped_no_fulltext": skipped_no_fulltext,
        "stage2_unsure": 0,
        "retries": retries,
    }

    for doc_index, doc in enumerate(docs):
        if doc_index in empty_fulltext:
            outcome = _RepOutcome(error_type="RuntimeError")
        else:
            outcome = outcomes_by_doc[doc_index]
        reps_payload = [_rep_payload(outcome)]
        flags: list[str] = []

        if outcome.rep is None:
            status: ScreenStatus = "failed"
            basis: ScreenBasis | None = None
            confidence: float | None = None
            agreement = {"agreeing": 0, "survivors": 0}
            counts["failed"] += 1
        elif outcome.rep.decision == "not_relevant":
            status = "not_relevant"
            basis = "full_text"
            confidence = float(outcome.rep.confidence)
            agreement = {"agreeing": 1, "survivors": 1}
            counts["demoted"] += 1
        else:
            status = "relevant"
            basis = "full_text"
            confidence = (
                0.5 if outcome.rep.decision == "unsure" else float(outcome.rep.confidence)
            )
            agreement = {"agreeing": 1, "survivors": 1}
            counts["confirmed"] += 1
            if outcome.rep.decision == "unsure":
                flags.append("stage2_unsure_referred_back")
                counts["stage2_unsure"] += 1

        _assert_stage1_relevant(conn, scope_id=context.scope_id, pss_id=doc.pss_id)
        _insert_screen_row(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=context.scope_id,
            pss_id=doc.pss_id,
            status=status,
            basis=basis,
            confidence=confidence,
            stage=2,
        )
        _append_screened_event(
            conn,
            project_id=project_id,
            run_id=run_id,
            scope_id=context.scope_id,
            source_snapshot_id=doc.source_snapshot_id,
            pss_id=doc.pss_id,
            status=status,
            basis=basis,
            confidence=confidence,
            stage=2,
            reps=reps_payload,
            agreement=agreement,
            flags=flags,
        )

    return counts


def screen_sources(
    conn: Connection,
    *,
    project_id: uuid.UUID,
    run_id: uuid.UUID,
    context: ScreenContext,
    screening_backend: ScreeningBackend | None = None,
) -> dict[str, Any]:
    """Screen project sources against a scope.

    Args:
        conn: Open database connection; all writes occur in its transaction.
        project_id: Owning project id.
        run_id: Run id responsible for rows/events.
        context: Scope-level screening context and optional stage directive.
        screening_backend: Screening backend. ``None`` resolves to the
            deterministic ``StubScreeningBackend``.

    Returns:
        Stage-specific summary counts.

    Raises:
        ScreenDirectiveError: If ``context.context["screening"]`` is malformed.
        RuntimeError: If a stage-2 insert would violate the no-rescue invariant.
    """
    backend = screening_backend if screening_backend is not None else StubScreeningBackend()
    stage = _parse_screen_stage(context.context)
    if stage == 1:
        return _run_stage1(
            conn,
            project_id=project_id,
            run_id=run_id,
            context=context,
            screening_backend=backend,
        )
    return _run_stage2(
        conn,
        project_id=project_id,
        run_id=run_id,
        context=context,
        screening_backend=backend,
    )
