"""Asynchronous grounding-judge enrichment for completed chat turns."""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.engine import Connection, Engine

from policy_atlas.core.schema import (
    chat_turn,
    implementation_context_finding,
    intervention_outcome_finding,
    source_extraction_record,
    source_snapshot,
)
from policy_atlas.core.schema import chunk as chunk_table
from policy_atlas.evidence_base.extract.quote_verify import QuoteMatcher, build_basis
from policy_atlas.evidence_base.synthesis.grounding_judge import (
    ENVELOPE_VERSION,
    JUDGE_MODEL,
    JUDGE_PROMPT_VERSION,
    GroundingJudgeBackend,
    build_envelope,
)
from policy_atlas.runtime.chat_floor import derive_claims_for_uncovered_citations

log = structlog.get_logger()

# Plan-time constant: one 45-second retry budget after an exception or timeout.
JUDGE_TIMEOUT_SECONDS = 45.0
_JUDGE_ATTEMPTS = 2
_VERDICT_SEVERITY = {
    "tier_1": 0,
    "tier_2": 1,
    "tier_3": 2,
    "tier_4": 3,
    "unsupported_mis_cited": 4,
}


class ChatEnrichmentError(RuntimeError):
    """Raised when a completed chat payload cannot be judged honestly."""


def _parse_ids(raw_ids: set[str]) -> set[uuid.UUID]:
    """Parse durable UUID strings, rejecting malformed citation identifiers."""
    parsed: set[uuid.UUID] = set()
    for raw_id in raw_ids:
        try:
            parsed.add(uuid.UUID(raw_id))
        except ValueError as exc:
            raise ChatEnrichmentError("citation id is not a durable UUID") from exc
    return parsed


def _load_chunks(conn: Connection, chunk_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Fetch cited chunks' immutable content and envelope metadata by durable id."""
    if not chunk_ids:
        return {}
    parsed_ids = _parse_ids(chunk_ids)
    rows = conn.execute(
        select(
            chunk_table.c.chunk_id,
            chunk_table.c.source_snapshot_id,
            chunk_table.c.segmentation_policy,
            chunk_table.c.content,
            source_snapshot.c.text_basis,
        )
        .select_from(
            chunk_table.join(
                source_snapshot,
                chunk_table.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(chunk_table.c.chunk_id.in_(parsed_ids))
    ).mappings()
    chunks = {
        str(row["chunk_id"]): {
            "chunk_record_id": str(row["chunk_id"]),
            "segmentation_policy": row["segmentation_policy"],
            "text_basis": row["text_basis"],
            "content": row["content"],
            "source_snapshot_id": str(row["source_snapshot_id"]),
        }
        for row in rows
    }
    missing = chunk_ids - set(chunks)
    if missing:
        raise ChatEnrichmentError("cited chunk is no longer available")
    return chunks


def _load_finding_rows(conn: Connection, finding_ids: set[str]) -> dict[str, dict[str, Any]]:
    """Load finding grounding and frozen-source provenance for judge anchors."""
    if not finding_ids:
        return {}
    parsed_ids = _parse_ids(finding_ids)
    found: dict[str, dict[str, Any]] = {}
    for table, kind in (
        (intervention_outcome_finding, "iof"),
        (implementation_context_finding, "icf"),
    ):
        rows = conn.execute(
            select(
                table.c.finding_id,
                table.c.grounding,
                source_extraction_record.c.source_snapshot_id,
                source_snapshot.c.metadata,
            )
            .select_from(
                table.join(
                    source_extraction_record,
                    table.c.extraction_record_id == source_extraction_record.c.extraction_record_id,
                ).join(
                    source_snapshot,
                    source_extraction_record.c.source_snapshot_id
                    == source_snapshot.c.source_snapshot_id,
                )
            )
            .where(table.c.finding_id.in_(parsed_ids))
        ).mappings()
        for row in rows:
            found[str(row["finding_id"])] = {
                "kind": kind,
                "grounding": row["grounding"],
                "source_snapshot_id": str(row["source_snapshot_id"]),
                "metadata": row["metadata"],
            }
    missing = finding_ids - set(found)
    if missing:
        raise ChatEnrichmentError("cited finding is no longer available")
    return found


def _finding_anchors(
    conn: Connection, finding_ids: set[str]
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Mirror synthesis finding-anchor resolution for the existing judge envelope."""
    findings = _load_finding_rows(conn, finding_ids)
    snapshot_ids = {record["source_snapshot_id"] for record in findings.values()}
    parsed_snapshots = _parse_ids(snapshot_ids)
    chunk_rows = conn.execute(
        select(
            chunk_table.c.chunk_id,
            chunk_table.c.source_snapshot_id,
            chunk_table.c.sequence,
            chunk_table.c.segmentation_policy,
            chunk_table.c.content,
            source_snapshot.c.text_basis,
        )
        .select_from(
            chunk_table.join(
                source_snapshot,
                chunk_table.c.source_snapshot_id == source_snapshot.c.source_snapshot_id,
            )
        )
        .where(chunk_table.c.source_snapshot_id.in_(parsed_snapshots))
        .order_by(chunk_table.c.source_snapshot_id, chunk_table.c.sequence, chunk_table.c.chunk_id)
    ).mappings()
    chunks_by_snapshot: dict[str, list[dict[str, Any]]] = {}
    all_chunks: dict[str, dict[str, Any]] = {}
    for row in chunk_rows:
        record = {
            "chunk_record_id": str(row["chunk_id"]),
            "segmentation_policy": row["segmentation_policy"],
            "text_basis": row["text_basis"],
            "content": row["content"],
            "source_snapshot_id": str(row["source_snapshot_id"]),
        }
        all_chunks[record["chunk_record_id"]] = record
        chunks_by_snapshot.setdefault(record["source_snapshot_id"], []).append(record)

    anchors_by_finding: dict[str, list[dict[str, Any]]] = {}
    required_chunk_ids: set[str] = set()
    for finding_id, finding in findings.items():
        source_id = finding["source_snapshot_id"]
        source_chunks = chunks_by_snapshot.get(source_id, [])
        if source_chunks:
            basis = build_basis(
                [(chunk["chunk_record_id"], chunk["content"]) for chunk in source_chunks]
            )
        else:
            metadata = finding["metadata"]
            abstract = metadata.get("abstract") if isinstance(metadata, dict) else ""
            basis = build_basis([(None, abstract if isinstance(abstract, str) else "")])
        anchors: list[dict[str, Any]] = []
        grounding = finding["grounding"]
        records = grounding if isinstance(grounding, list) else []
        for raw_anchor in records:
            quote = raw_anchor.get("quote") if isinstance(raw_anchor, dict) else None
            if not isinstance(quote, str) or not quote:
                anchors.append(
                    {
                        "finding_id": finding_id,
                        "kind": finding["kind"],
                        "quote": quote,
                        "match_status": "failed",
                        "spans": [],
                    }
                )
                continue
            match = QuoteMatcher(basis).find(quote)
            spans = [
                {"chunk_id": span.chunk_id, "start": span.start, "end": span.end}
                for span in match.spans
            ]
            required_chunk_ids.update(
                span["chunk_id"] for span in spans if isinstance(span["chunk_id"], str)
            )
            anchors.append(
                {
                    "finding_id": finding_id,
                    "kind": finding["kind"],
                    "quote": quote,
                    "match_status": match.status,
                    "spans": spans,
                }
            )
        if not anchors:
            anchors.append(
                {
                    "finding_id": finding_id,
                    "kind": finding["kind"],
                    "quote": None,
                    "match_status": "failed",
                    "spans": [],
                }
            )
        anchors_by_finding[finding_id] = anchors
    return anchors_by_finding, {
        chunk_id: all_chunks[chunk_id] for chunk_id in required_chunk_ids if chunk_id in all_chunks
    }


def _citation_map(payload: dict[str, Any]) -> dict[int, dict[str, Any]]:
    """Return terminal citations keyed by their compacted display number."""
    citations = payload.get("citations")
    if not isinstance(citations, list):
        raise ChatEnrichmentError("chat payload citations are malformed")
    result: dict[int, dict[str, Any]] = {}
    for citation in citations:
        if isinstance(citation, dict) and isinstance(citation.get("n"), int):
            result[citation["n"]] = citation
    return result


def _shape_envelope(
    conn: Connection, *, payload: dict[str, Any], answer: str, intent: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Mint chat claim ids and shape floored claims into ``synthesis_envelope_v2``."""
    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list):
        raise ChatEnrichmentError("chat payload claims are malformed")
    citations_by_n = _citation_map(payload)
    # Rows persisted before the floor derived claims for uncovered citations
    # (and any residual model omission) still deserve checking: derive the
    # sentence-grain mapping here symmetrically rather than failing.
    derived = derive_claims_for_uncovered_citations(
        answer, sorted(citations_by_n), raw_claims
    )
    if derived:
        raw_claims = [*raw_claims, *derived]
        payload["claims"] = raw_claims
    for index, claim in enumerate(raw_claims, start=1):
        if not isinstance(claim, dict):
            raise ChatEnrichmentError("chat payload claim is malformed")
        claim["claim_id"] = f"c{index}"

    cited_finding_ids: set[str] = set()
    for claim in raw_claims:
        citation_ns = claim.get("citation_ns")
        if not isinstance(citation_ns, list):
            continue
        for citation_n in citation_ns:
            citation = citations_by_n.get(citation_n) if isinstance(citation_n, int) else None
            if citation is not None and citation.get("kind") == "finding":
                citation_id = citation.get("id")
                if isinstance(citation_id, str):
                    cited_finding_ids.add(citation_id)
    anchors_by_finding, anchor_chunks = _finding_anchors(conn, cited_finding_ids)

    envelope_claims: list[dict[str, Any]] = []
    direct_chunk_ids: set[str] = set()
    span_map: list[dict[str, Any]] = []
    for claim in raw_claims:
        citation_ns = claim.get("citation_ns")
        numbers = citation_ns if isinstance(citation_ns, list) else []
        claim_citations = [
            citations_by_n[number]
            for number in numbers
            if isinstance(number, int) and number in citations_by_n
        ]
        if not claim_citations:
            continue
        finding_ids = [
            citation["id"]
            for citation in claim_citations
            if citation.get("kind") == "finding" and isinstance(citation.get("id"), str)
        ]
        direct_citations: list[dict[str, Any]] = []
        for citation in claim_citations:
            citation_id = citation.get("id")
            if citation.get("kind") == "chunk" and isinstance(citation_id, str):
                direct_chunk_ids.add(citation_id)
                direct_citations.append(
                    {"chunk_record_id": citation_id, "quote": citation.get("quote")}
                )
        record: dict[str, Any] = {
            "claim_id": claim["claim_id"],
            "claim_type": "finding" if finding_ids else "chunk",
            "text": claim.get("text") if isinstance(claim.get("text"), str) else "",
            "citations": direct_citations
            + [anchor for finding_id in finding_ids for anchor in anchors_by_finding[finding_id]],
        }
        if finding_ids:
            record["cited_finding_ids"] = finding_ids
        envelope_claims.append(record)
        span = claim.get("span")
        if (
            isinstance(span, list)
            and len(span) == 2
            and all(isinstance(offset, int) for offset in span)
            and 0 <= span[0] <= span[1] <= len(answer)
        ):
            span_map.append({"claim_id": claim["claim_id"], "start": span[0], "end": span[1]})

    if not envelope_claims:
        raise ChatEnrichmentError("cited chat turn has no claim-to-citation mapping")
    direct_chunks = _load_chunks(conn, direct_chunk_ids)
    chunks = [
        {key: value for key, value in record.items() if key != "source_snapshot_id"}
        for record in sorted(
            {**anchor_chunks, **direct_chunks}.values(), key=lambda item: item["chunk_record_id"]
        )
    ]
    return (
        build_envelope(
            claims=envelope_claims,
            chunks=chunks,
            section_prose=answer,
            span_map=span_map,
            intent=intent,
            section_focus="chat answer",
        ),
        raw_claims,
    )


def _judge_with_retry(judge_backend: GroundingJudgeBackend, envelope: dict[str, Any]) -> Any:
    """Run one non-blocking judge call with the plan-pinned retry policy."""
    last_error: Exception | None = None
    for _attempt in range(_JUDGE_ATTEMPTS):
        outcome: dict[str, Any] = {}

        def call(outcome: dict[str, Any] = outcome) -> None:
            try:
                outcome["result"] = judge_backend.judge_block(envelope)
            except Exception as exc:  # Preserve provider failures for the retry policy.
                outcome["error"] = exc

        worker = threading.Thread(target=call, name="policy-atlas-chat-judge", daemon=True)
        worker.start()
        worker.join(JUDGE_TIMEOUT_SECONDS)
        if worker.is_alive():
            last_error = TimeoutError("chat grounding judge timed out")
            continue
        if "error" in outcome:
            last_error = outcome["error"]
            continue
        return outcome["result"]
    raise ChatEnrichmentError("chat grounding judge failed") from last_error


def _audit(*, status: str) -> dict[str, Any]:
    """Build the durable, prompt-pinned enrichment audit metadata."""
    return {
        "status": status,
        "completed_at": datetime.now(UTC).isoformat(),
        "model_id": JUDGE_MODEL,
        "prompt_version": JUDGE_PROMPT_VERSION,
        "envelope_version": ENVELOPE_VERSION,
    }


def _apply_verdicts(payload: dict[str, Any], claims: list[dict[str, Any]], response: Any) -> None:
    """Attach a complete judge response to claims and their display citations."""
    verdicts = response.verdicts
    expected = {claim["claim_id"] for claim in claims if claim.get("citation_ns")}
    actual = [verdict.claim_id for verdict in verdicts]
    if set(actual) != expected or len(actual) != len(set(actual)):
        raise ChatEnrichmentError("chat judge verdict coverage is invalid")
    by_id = {verdict.claim_id: verdict for verdict in verdicts}
    citations_by_n = _citation_map(payload)
    for claim in claims:
        verdict = by_id.get(claim["claim_id"])
        if verdict is None:
            continue
        claim["verdict"] = verdict.verdict
        claim["weakly_grounded"] = verdict.weakly_grounded
        claim["rationale"] = verdict.rationale
        citation_ns = claim.get("citation_ns")
        for number in citation_ns if isinstance(citation_ns, list) else []:
            citation = citations_by_n.get(number) if isinstance(number, int) else None
            if citation is None:
                continue
            current = citation.get("verdict")
            if not isinstance(current, str) or _VERDICT_SEVERITY[
                verdict.verdict
            ] >= _VERDICT_SEVERITY.get(current, -1):
                citation["verdict"] = verdict.verdict
                citation["state"] = f"verdict:{verdict.verdict}"


def _cas_write(engine: Engine, *, turn_id: uuid.UUID, payload: dict[str, Any]) -> bool:
    """Persist an enrichment result only while this completed turn remains pending."""
    with engine.begin() as conn:
        written = conn.execute(
            update(chat_turn)
            .where(chat_turn.c.id == turn_id)
            .where(chat_turn.c.status == "completed")
            .where(chat_turn.c.answer_payload["enrichment"]["status"].astext == "pending")
            .values(answer_payload=payload)
        )
    return written.rowcount == 1


def enrich_chat_turn(
    engine: Engine,
    *,
    turn_id: uuid.UUID,
    judge_backend: GroundingJudgeBackend,
    langfuse_client: Any = None,
) -> None:
    """Enrich one completed, cited chat turn without delaying its streamed answer.

    Args:
        engine: Database engine for short-lived reads and one CAS write.
        turn_id: Completed chat turn to enrich.
        judge_backend: Existing grounding-judge backend seam.
        langfuse_client: Reserved tracing seam; the backend owns its judge span.
    """
    del langfuse_client
    with engine.connect() as conn:
        row = (
            conn.execute(select(chat_turn).where(chat_turn.c.id == turn_id))
            .mappings()
            .one_or_none()
        )
        if row is None:
            log.info("chat_enrichment.skipped", turn_id=str(turn_id), reason="missing_turn")
            return
        raw_payload = row["answer_payload"]
        payload = dict(raw_payload) if isinstance(raw_payload, dict) else None
        enrichment = payload.get("enrichment") if payload is not None else None
        citations = payload.get("citations") if payload is not None else None
        if (
            row["status"] != "completed"
            or payload is None
            or not isinstance(citations, list)
            or not citations
            or not isinstance(enrichment, dict)
            or enrichment.get("status") != "pending"
        ):
            log.info("chat_enrichment.skipped", turn_id=str(turn_id), reason="not_pending")
            return
        try:
            envelope, claims = _shape_envelope(
                conn,
                payload=payload,
                answer=row["answer"] if isinstance(row["answer"], str) else "",
                intent=row["user_message"],
            )
        except Exception as exc:
            payload["enrichment"] = _audit(status="failed")
            payload["enrichment"]["failure"] = type(exc).__name__
            if not _cas_write(engine, turn_id=turn_id, payload=payload):
                log.info("chat_enrichment.cas_lost", turn_id=str(turn_id))
            return

    try:
        response, _usage = _judge_with_retry(judge_backend, envelope)
        _apply_verdicts(payload, claims, response)
        payload["enrichment"] = _audit(status="enriched")
    except Exception as exc:
        payload["enrichment"] = _audit(status="failed")
        payload["enrichment"]["failure"] = type(exc).__name__

    if not _cas_write(engine, turn_id=turn_id, payload=payload):
        log.info("chat_enrichment.cas_lost", turn_id=str(turn_id))
